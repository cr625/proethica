"""
Case Role Matching Service

Intelligently matches LLM-extracted participant roles from cases to existing ontology roles.
Uses semantic similarity followed by LLM validation to ensure accurate matching.

Example:
- LLM extracts: "County Client"
- Semantic similarity finds: ["Client Representative Role", "Public Official Role"] 
- LLM validates: "Yes, County Client is similar to Client Representative Role"
- Result: High-confidence match with reasoning
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import json

from app.services.llm_service import LLMService
from app.services.embedding_service import EmbeddingService
from app.models.world import World
from app.services.role_description_service import RoleDescriptionService
from app.services.ontology_entity_service import OntologyEntityService
from app.utils.label_normalization import normalize_role_label

logger = logging.getLogger(__name__)

class CaseRoleMatchingService:
    """Service for matching case-extracted roles to ontology roles with LLM validation."""
    
    def __init__(self):
        self.llm_service = LLMService()
        self.embedding = EmbeddingService.get_instance()
        self.role_desc = RoleDescriptionService()
        self.ontology_service = OntologyEntityService.get_instance()
        # Semantic similarity threshold and number of candidates
        self.confidence_threshold = 0.4
        self.top_k_candidates = 3
        
    def _embed_texts(self, texts):
        """Embed a list of texts using the shared EmbeddingService."""
        try:
            return np.array([self.embedding.get_embedding(t) for t in texts])
        except Exception as e:
            logger.error(f"Failed to embed texts: {e}")
            return None
    
    def match_role_to_ontology(self, llm_role: str, ontology_roles: List[Dict], world: Optional[World] = None) -> Dict:
        """
        Match an LLM-extracted role to ontology roles using semantic similarity + LLM validation.
        
        Args:
            llm_role: Role extracted by LLM (e.g., "County Client", "Ethics Committee Member")
            ontology_roles: List of ontology role dictionaries with 'label', 'description', 'id'
            
        Returns:
            Dict with matching results:
        
        try:
                "semantic_confidence": 0.85,
                "llm_agreed": True,
                "llm_reasoning": "County Client is a specific type of client representative...",
                "semantic_candidates": [...],
                "matching_method": "semantic_llm_validated"
            }
        """
        # If a world is provided, prefer aggregating roles across base and derived ontologies
        if world is not None:
            try:
                entities = self.ontology_service.get_entities_for_world(world)
                if entities and isinstance(entities, dict) and 'entities' in entities:
                    aggregated = entities['entities'].get('role', [])
                elif isinstance(entities, list):
                    aggregated = entities
                else:
                    aggregated = []
                
                if aggregated:
                    ontology_roles = aggregated
                    logger.info(f"Using aggregated {len(ontology_roles)} roles across world ontologies for matching")
            except Exception as e:
                logger.warning(f"Falling back to provided ontology_roles due to aggregation error: {e}")

        if not llm_role or not ontology_roles:
            return self._create_no_match_result(llm_role)
        
        try:
            logger.info(f"Matching LLM role '{llm_role}' against {len(ontology_roles)} ontology roles")
            norm_llm = normalize_role_label(llm_role)
            
            # Step 1: Semantic similarity matching
            semantic_candidates = self._find_semantic_candidates(llm_role, ontology_roles)
            
            if not semantic_candidates:
                logger.info(f"No semantic candidates found for '{llm_role}' above threshold {self.confidence_threshold}")
                return self._create_no_match_result(llm_role, semantic_candidates=[])
            
            # Step 2: LLM validation of top candidates
            llm_validation = self._validate_matches_with_llm(llm_role, semantic_candidates)
            
            # Step 3: Combine results
            best_match = self._select_best_match(semantic_candidates, llm_validation)

            # If no best match, attempt exact-normalized label equality as a fallback
            if not best_match:
                for idx, c in enumerate(semantic_candidates):
                    cand_label = c["role"].get("label", "")
                    if normalize_role_label(cand_label) == norm_llm:
                        best_match = {
                            "role": c["role"],
                            "semantic_score": c["semantic_score"],
                            "llm_confidence": 0.6,
                            "llm_agreed": True,
                            "combined_confidence": c["semantic_score"]
                        }
                        logger.info(f"Normalization fallback matched '{llm_role}' -> '{cand_label}'")
                        break
            
            # Generate standardized description regardless of match success
            desc_payload = self.role_desc.generate(llm_role, world=world)

            result = {
                "matched_role": best_match["role"] if best_match else None,
                "semantic_confidence": best_match["semantic_score"] if best_match else 0.0,
                "llm_agreed": best_match["llm_agreed"] if best_match else False,
                "llm_reasoning": llm_validation.get("reasoning", ""),
                "semantic_candidates": semantic_candidates,
                "matching_method": "semantic_llm_validated",
                "original_llm_role": llm_role,
                "normalized_llm_role": norm_llm,
                "suggested_description": desc_payload.get("description", ""),
                "suggested_obligations": desc_payload.get("obligations", []),
                "parent_suggestion": desc_payload.get("parent_suggestion")
            }
            
            if best_match:
                logger.info(f"✅ Matched '{llm_role}' → '{best_match['role']['label']}' "
                          f"(semantic: {best_match['semantic_score']:.2f}, LLM agreed: {best_match['llm_agreed']})")
            else:
                logger.info(f"❌ No valid match found for '{llm_role}'")
            
            return result
            
        except Exception as e:
            logger.error(f"Error matching role '{llm_role}': {e}")
            return self._create_error_result(llm_role, str(e))
    
    def _find_semantic_candidates(self, llm_role: str, ontology_roles: List[Dict]) -> List[Dict]:
        """Find top semantic similarity candidates using embeddings."""
        # Build texts and compute embeddings via provider-priority service
        llm_role_text = self._create_role_text(llm_role, "")
        ontology_role_texts = [
            self._create_role_text(role.get('label', ''), role.get('description', ''))
            for role in ontology_roles
        ]
        all_texts = [llm_role_text] + ontology_role_texts
        embeddings = self._embed_texts(all_texts)
        if embeddings is None:
            logger.warning("Embedding provider unavailable, skipping semantic matching")
            return []
        try:
            # Calculate similarities
            llm_embedding = embeddings[0:1]
            ontology_embeddings = embeddings[1:]

            similarities = cosine_similarity(llm_embedding, ontology_embeddings)[0]

            # Create candidates with scores
            candidates: List[Dict] = []
            for i, similarity in enumerate(similarities):
                if similarity >= self.confidence_threshold:
                    candidates.append({
                        "role": ontology_roles[i],
                        "semantic_score": float(similarity),
                        "rank": len(candidates) + 1
                    })

            # Sort by similarity and take top K
            candidates = sorted(candidates, key=lambda x: x["semantic_score"], reverse=True)[:self.top_k_candidates]

            logger.info(f"Found {len(candidates)} semantic candidates above threshold {self.confidence_threshold}")
            for c in candidates:
                logger.info(f"  - {c['role']['label']}: {c['semantic_score']:.3f}")

            return candidates

        except Exception as e:
            logger.error(f"Error in semantic matching: {e}")
            return []
    
    def _create_role_text(self, label: str, description: str) -> str:
        """Create text representation of a role for embedding."""
        text = label
        if description:
            text += f" - {description}"
        return text
    
    def _validate_matches_with_llm(self, llm_role: str, candidates: List[Dict]) -> Dict:
        """Ask LLM to validate semantic matches and provide reasoning."""
        if not candidates:
            return {"best_match": None, "reasoning": "No semantic candidates to validate"}
        
        try:
            # Create prompt for LLM validation
            candidates_text = "\n".join([
                f"{i+1}. {c['role']['label']} (similarity: {c['semantic_score']:.2f})\n"
                f"   Description: {c['role'].get('description', 'No description')}"
                for i, c in enumerate(candidates)
            ])
            
            validation_prompt = f"""You are an expert in professional roles and ontology matching. 
            
TASK: Determine if the extracted role matches any of the ontology roles.

EXTRACTED ROLE: "{llm_role}"

ONTOLOGY ROLE CANDIDATES (ranked by semantic similarity):
{candidates_text}

ANALYSIS REQUIRED:
1. Is the extracted role "{llm_role}" semantically equivalent to any of the ontology roles?
2. Consider professional context, hierarchy, and specific vs. general roles
3. A "County Client" could match "Client Representative Role" if it represents the same professional function

EXAMPLES OF GOOD MATCHES:
- "County Client" → "Client Representative Role" (County is a type of client)
- "Ethics Committee Member" → "Professional Society" (Ethics committees are professional oversight bodies)
- "Structural Engineer" → "Structural Engineer Role" (Exact match)
- "Project Manager" → "Engineering Manager Role" (Similar management functions)

EXAMPLES OF POOR MATCHES:
- "County Client" → "Professional Engineer Role" (Completely different functions)
- "Public" → "Client Representative Role" (Too generic vs. specific)

FORMAT: Return JSON only:
{{
    "best_match_index": 0,  // Index of best match (0-based) or null if no good match
    "confidence": 0.85,     // Confidence in the match (0.0-1.0)
    "reasoning": "County Client is a specific type of client representative representing government entities..."
}}

Return only valid JSON, no explanations."""

            # Get LLM response
            response_data = self.llm_service.generate_response(validation_prompt)
            response = response_data.get('analysis', response_data.get('response', '')) if isinstance(response_data, dict) else str(response_data)
            
            # Parse response
            response_clean = self._clean_json_response(response)
            validation_result = json.loads(response_clean)
            
            logger.info(f"LLM validation result: {validation_result}")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error in LLM validation: {e}")
            return {"best_match_index": None, "confidence": 0.0, "reasoning": f"Validation error: {str(e)}"}
    
    def _clean_json_response(self, response: str) -> str:
        """Clean LLM response to extract JSON."""
        response_clean = response.strip()
        
        # Remove markdown code blocks
        if response_clean.startswith('```json'):
            response_clean = response_clean[7:]
        elif response_clean.startswith('```'):
            response_clean = response_clean[3:]
        
        if response_clean.endswith('```'):
            response_clean = response_clean[:-3]
        
        return response_clean.strip()
    
    def _select_best_match(self, semantic_candidates: List[Dict], llm_validation: Dict) -> Optional[Dict]:
        """Select the best match combining semantic similarity and LLM validation."""
        best_match_index = llm_validation.get("best_match_index")
        llm_confidence = llm_validation.get("confidence", 0.0)
        
        # Must have LLM agreement and reasonable confidence
        if best_match_index is None or llm_confidence < 0.5:
            return None
        
        # Validate index bounds
        if best_match_index < 0 or best_match_index >= len(semantic_candidates):
            logger.warning(f"LLM returned invalid match index {best_match_index}")
            return None
        
        candidate = semantic_candidates[best_match_index]
        
        return {
            "role": candidate["role"],
            "semantic_score": candidate["semantic_score"],
            "llm_confidence": llm_confidence,
            "llm_agreed": True,
            "combined_confidence": (candidate["semantic_score"] + llm_confidence) / 2.0
        }
    
    def batch_match_roles(self, llm_roles: List[str], ontology_roles: List[Dict], world: Optional[World] = None) -> Dict[str, Dict]:
        """Batch match multiple LLM roles to ontology roles for efficiency."""
        results = {}
        
        logger.info(f"Batch matching {len(llm_roles)} LLM roles against {len(ontology_roles)} ontology roles")
        
        for llm_role in llm_roles:
            results[llm_role] = self.match_role_to_ontology(llm_role, ontology_roles, world=world)
        
        # Log summary
        matched_count = sum(1 for r in results.values() if r.get("matched_role"))
        logger.info(f"Batch matching complete: {matched_count}/{len(llm_roles)} roles matched")
        
        return results
    
    def _create_no_match_result(self, llm_role: str, semantic_candidates: List = None) -> Dict:
        """Create result for when no match is found."""
        return {
            "matched_role": None,
            "semantic_confidence": 0.0,
            "llm_agreed": False,
            "llm_reasoning": "No suitable ontology match found",
            "semantic_candidates": semantic_candidates or [],
            "matching_method": "semantic_llm_validated",
            "original_llm_role": llm_role
        }
    
    def _create_error_result(self, llm_role: str, error: str) -> Dict:
        """Create result for when matching fails due to error."""
        return {
            "matched_role": None,
            "semantic_confidence": 0.0,
            "llm_agreed": False,
            "llm_reasoning": f"Matching failed: {error}",
            "semantic_candidates": [],
            "matching_method": "error",
            "original_llm_role": llm_role,
            "error": error
        }
