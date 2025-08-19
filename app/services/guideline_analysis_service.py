"""
Service for analyzing guidelines and extracting ontology concepts.
Clean version without backward compatibility - requires proper ontology structure.
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional, Tuple, Set
import logging
import re

from app import db
from app.utils.llm_utils import get_llm_client
from app.services.mcp_client import MCPClient
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper
from app.models.entity_triple import EntityTriple

# Set up logging
logger = logging.getLogger(__name__)

class GuidelineAnalysisService:
    """
    Service for analyzing guidelines, extracting concepts, and generating RDF triples.
    This service requires GuidelineConceptTypes to be defined in the ontology.
    """
    
    def __init__(self):
        self.mcp_client = MCPClient.get_instance()
        # Check if we should use mock responses
        self.use_mock_responses = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "false").lower() == "true"
        if self.use_mock_responses:
            logger.info("GuidelineAnalysisService initialized with mock response mode enabled")
        
        # Cache for guideline concept types
        self._guideline_concept_types = None
        
        # Initialize type mapper for intelligent type mapping
        self.type_mapper = GuidelineConceptTypeMapper()
        logger.info("GuidelineAnalysisService initialized with intelligent type mapping")
        
    def _get_guideline_concept_types(self) -> Dict[str, Dict[str, str]]:
        """
        Retrieve GuidelineConceptTypes from the ontology.
        Raises RuntimeError if types cannot be retrieved.
        """
        if self._guideline_concept_types is not None:
            return self._guideline_concept_types
            
        logger.info("Querying ontology for GuidelineConceptTypes")
        
        # Query the ontology for GuidelineConceptTypes
        mcp_url = self.mcp_client.mcp_url
        if not mcp_url:
            raise RuntimeError("MCP server URL not configured")
            
        try:
            response = requests.post(
                f"{mcp_url}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "call_tool",
                    "params": {
                        "name": "query_ontology",
                        "arguments": {
                            "sparql_query": """
                                PREFIX : <http://proethica.org/ontology/intermediate#>
                                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                                
                                SELECT ?type ?label ?comment WHERE {
                                    ?type rdf:type :GuidelineConceptType .
                                    ?type rdfs:label ?label .
                                    OPTIONAL { ?type rdfs:comment ?comment }
                                }
                                ORDER BY ?label
                            """
                        }
                    },
                    "id": 1
                },
                timeout=30
            )
            
            logger.info(f"MCP server response status: {response.status_code}")
            
            if response.status_code != 200:
                raise RuntimeError(f"MCP server returned status {response.status_code}")
                
            result = response.json()
            logger.info(f"MCP server response keys: {list(result.keys())}")
            
            if "error" in result:
                raise RuntimeError(f"MCP server error: {result['error']}")
                
            if "result" not in result or "bindings" not in result["result"]:
                logger.error(f"Invalid MCP response structure: {result}")
                raise RuntimeError("Invalid response from MCP server")
                
            concept_types = {}
            for binding in result["result"]["bindings"]:
                type_uri = binding.get("type", {}).get("value", "")
                type_name = type_uri.split("#")[-1].lower()
                label = binding.get("label", {}).get("value", "")
                comment = binding.get("comment", {}).get("value", "")
                
                concept_types[type_name] = {
                    "uri": type_uri,
                    "label": label,
                    "description": comment,
                    "examples": self._extract_examples_from_comment(comment)
                }
            
            if not concept_types:
                raise RuntimeError("No GuidelineConceptTypes found in ontology")
                
            # Validate we have the expected 9 types (including constraint)
            expected_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability", "constraint"}
            found_types = set(concept_types.keys())
            
            if found_types != expected_types:
                missing = expected_types - found_types
                extra = found_types - expected_types
                error_msg = "Ontology GuidelineConceptTypes mismatch."
                if missing:
                    error_msg += f" Missing: {missing}."
                if extra:
                    error_msg += f" Unexpected: {extra}."
                raise RuntimeError(error_msg)
            
            self._guideline_concept_types = concept_types
            logger.info(f"Successfully loaded {len(concept_types)} GuidelineConceptTypes from ontology")
            return concept_types
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to query MCP server: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving GuidelineConceptTypes: {str(e)}")
    
    def _extract_examples_from_comment(self, comment: str) -> List[str]:
        """Extract examples from a comment string."""
        if not comment or "Examples include" not in comment:
            return []
        
        # Extract the part after "Examples include"
        examples_part = comment.split("Examples include")[-1]
        # Remove trailing period and split by comma
        examples = [ex.strip() for ex in examples_part.rstrip(".").split(",")]
        return examples

    @staticmethod
    def _role_definition_text() -> str:
        """Canonical role definition injected into prompts and used for validation."""
        return (
            "Role (in this project): A social position within a profession or practice context, "
            "typically named as a concrete title (e.g., Professional Engineer, Project Manager, Inspector, Architect, Public Official). "
            "A Role has expectations and attendant obligations and is often governed by codes or principles. "
            "Do NOT treat activities, obligations, principles, programs, or processes (e.g., Continuing Professional Development, Public Safety, Confidentiality) as roles."
        )
        
    def extract_concepts(self, content: str, ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract concepts from guideline content using ontology-defined types.
        
        Args:
            content: The text content of the guideline document
            ontology_source: Optional ontology source identifier
            
        Returns:
            Dict containing the extracted concepts or error information
        """
        try:
            logger.info(f"Extracting concepts from guideline content")
            
            # Get concept types from ontology (will raise error if not available)
            try:
                concept_types = self._get_guideline_concept_types()
            except RuntimeError as e:
                logger.error(f"Cannot extract concepts without ontology types: {str(e)}")
                return {"error": f"Ontology configuration error: {str(e)}"}
            
            # If mock responses are enabled, return mock concepts
            if self.use_mock_responses:
                logger.info("Using mock concept response mode")
                mock_concepts = self._generate_mock_concepts(content, concept_types)
                enriched = self._prioritize_and_enrich_roles(mock_concepts)
                return {
                    "concepts": enriched,
                    "mock": True,
                    "message": "Using mock guideline responses"
                }
            
            # If Gemini is explicitly requested, skip MCP and use Gemini path directly
            use_gemini = os.getenv('USE_GEMINI_FOR_GUIDELINES', 'false').lower() == 'true'
            if not use_gemini:
                # Try MCP server first
                try:
                    mcp_url = self.mcp_client.mcp_url
                    if mcp_url:
                        logger.info(f"Using MCP server for concept extraction")
                    
                        response = requests.post(
                            f"{mcp_url}/jsonrpc",
                            json={
                                "jsonrpc": "2.0",
                                "method": "call_tool",
                                "params": {
                                    "name": "extract_guideline_concepts",
                                    "arguments": {
                                        "content": content[:50000],  # Limit content length
                                        "ontology_source": ontology_source,
                                        "concept_types": list(concept_types.keys())
                                    }
                                },
                                "id": 1
                            },
                            timeout=60
                        )
                    
                        if response.status_code == 200:
                            result = response.json()
                            if "result" in result and "concepts" in result["result"]:
                                concepts = result["result"]["concepts"]
                                # Validate and map concept types using intelligent type mapper
                                valid_types = set(concept_types.keys())
                                for concept in concepts:
                                    # MCP server returns "category" field, map it to "type" for consistency
                                    original_type = concept.get("type") or concept.get("category")
                                    concept["type"] = original_type  # Ensure type field is set
                                    if original_type not in valid_types:
                                        logger.info(f"Mapping invalid type '{original_type}' for concept '{concept.get('label', 'Unknown')}'")
                                        
                                        # Use type mapper to get better mapping
                                        mapping_result = self.type_mapper.map_concept_type(
                                            llm_type=original_type,
                                            concept_description=concept.get("description", ""),
                                            concept_name=concept.get("label", "")
                                        )
                                        
                                        # Store original type and mapping metadata (two-tier approach)
                                        concept["original_llm_type"] = original_type
                                        concept["type"] = mapping_result.mapped_type
                                        concept["type_mapping_confidence"] = mapping_result.confidence
                                        concept["needs_type_review"] = mapping_result.needs_review
                                        concept["mapping_justification"] = mapping_result.justification
                                        concept["semantic_label"] = mapping_result.semantic_label
                                        concept["mapping_source"] = mapping_result.mapping_source
                                        
                                        logger.info(f"Mapped '{original_type}' → '{mapping_result.mapped_type}' (confidence: {mapping_result.confidence:.2f})")
                                    else:
                                        # Type is already valid - add exact match metadata
                                        concept["original_llm_type"] = original_type
                                        concept["type_mapping_confidence"] = 1.0
                                        concept["needs_type_review"] = False
                                        concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                                        concept["semantic_label"] = original_type
                                        concept["mapping_source"] = "exact_match"

                                # If concepts look category-only, add heuristic role candidates
                                if self._looks_category_only(concepts):
                                    logger.info("Category-only extraction detected; augmenting with heuristic role detection")
                                    roles = self._extract_roles_heuristic(content)
                                    if roles:
                                        concepts.extend(roles)

                                # Post-process to prioritize roles and add role classification
                                concepts = self._prioritize_and_enrich_roles(concepts)
                                result["result"]["concepts"] = concepts
                                return result["result"]
                except Exception as e:
                    logger.warning(f"MCP server error, falling back to LLM: {str(e)}")
            
            # Direct LLM processing (uses Gemini if enabled)
            debug_info: Dict[str, Any] = {"provider": "gemini" if use_gemini else "llm"}
            # Strategy when Gemini is enabled: 1) roles-only pass; 2) general pass; 3) merge with semantic guard
            if use_gemini:
                # Pass 1: Roles only
                roles_only = self._extract_roles_only_with_llm(content, concept_types)
                roles_before = [c for c in roles_only]
                # Guard: enforce semantics (drop or reclassify non-roles)
                roles_only = self._enforce_role_semantics(roles_only)
                # Compute guard stats
                orig_role_labels = {(c.get('label','').strip().lower(), 'role') for c in roles_before if (c.get('type') or '').lower() == 'role'}
                kept_roles = [(c.get('label','').strip().lower(), (c.get('type') or '').lower()) for c in roles_only]
                reclassified = sum(1 for c in roles_only if (c.get('type') or '').lower() != 'role')
                kept_count = sum(1 for lbl, t in kept_roles if t == 'role' and (lbl, 'role') in orig_role_labels)
                dropped_count = max(0, len(orig_role_labels) - kept_count - reclassified)
                debug_info.update({
                    "roles_only_before": len(roles_before),
                    "roles_kept": kept_count,
                    "roles_reclassified": reclassified,
                    "roles_dropped": dropped_count,
                    "sample_roles": [c.get('label') for c in roles_only[:5] if (c.get('type') or '').lower() == 'role']
                })
                # If empty after guard, retry once with corrective instruction
                if not roles_only:
                    logger.info("No valid roles found; retrying with corrective instruction")
                    roles_only = self._extract_roles_only_with_llm(content, concept_types, corrective=True)
                    roles_only = self._enforce_role_semantics(roles_only)
                    debug_info["roles_after_retry"] = len([c for c in roles_only if (c.get('type') or '').lower() == 'role'])

                # Pass 2: General concepts
                general = self._extract_concepts_with_llm(content, concept_types)
                general_list = general.get("concepts", []) if isinstance(general, dict) else []
                # Remove any items that the guard would deem mislabeled roles
                general_list = self._enforce_role_semantics(general_list)
                debug_info["general_count"] = len(general_list)

                # Merge with de-duplication by label+type
                def key(c):
                    return (c.get('label', '').strip().lower(), (c.get('type') or c.get('primary_type') or '').lower())
                merged: Dict[Tuple[str, str], Dict[str, Any]] = {}
                for c in roles_only + general_list:
                    merged[key(c)] = c
                concepts_merged = list(merged.values())
                concepts_final = self._prioritize_and_enrich_roles(concepts_merged)
                logger.info(f"Gemini extraction debug: {debug_info}")
                # If Gemini produced no concepts, fall back to MCP server call
                if not concepts_final:
                    try:
                        mcp_url = self.mcp_client.mcp_url
                        if mcp_url:
                            logger.info("Gemini returned 0 concepts; attempting MCP fallback extract_guideline_concepts")
                            response = requests.post(
                                f"{mcp_url}/jsonrpc",
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "call_tool",
                                    "params": {
                                        "name": "extract_guideline_concepts",
                                        "arguments": {
                                            "content": content[:50000],
                                            "ontology_source": None,
                                            "concept_types": list(concept_types.keys())
                                        }
                                    },
                                    "id": 1
                                },
                                timeout=60
                            )
                            if response.status_code == 200:
                                result = response.json()
                                if "result" in result and "concepts" in result["result"]:
                                    concepts = result["result"]["concepts"]
                                    # Normalize types and enrich like in the MCP-first branch
                                    valid_types = set(concept_types.keys())
                                    for concept in concepts:
                                        original_type = concept.get("type") or concept.get("category")
                                        concept["type"] = original_type
                                        if original_type not in valid_types:
                                            mapping_result = self.type_mapper.map_concept_type(
                                                llm_type=original_type,
                                                concept_description=concept.get("description", ""),
                                                concept_name=concept.get("label", "")
                                            )
                                            concept["original_llm_type"] = original_type
                                            concept["type"] = mapping_result.mapped_type
                                            concept["type_mapping_confidence"] = mapping_result.confidence
                                            concept["needs_type_review"] = mapping_result.needs_review
                                            concept["mapping_justification"] = mapping_result.justification
                                            concept["semantic_label"] = mapping_result.semantic_label
                                            concept["mapping_source"] = mapping_result.mapping_source
                                        else:
                                            concept["original_llm_type"] = original_type
                                            concept["type_mapping_confidence"] = 1.0
                                            concept["needs_type_review"] = False
                                            concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                                            concept["semantic_label"] = original_type
                                            concept["mapping_source"] = "exact_match"
                                    # Heuristic augmentation if category-only
                                    if self._looks_category_only(concepts):
                                        roles = self._extract_roles_heuristic(content)
                                        if roles:
                                            concepts.extend(roles)
                                    concepts_final = self._prioritize_and_enrich_roles(concepts)
                                    debug_info["provider"] = "gemini->mcp_fallback"
                                    logger.info("MCP fallback produced %d concepts", len(concepts_final))
                                    return {"concepts": concepts_final, "debug_info": debug_info}
                    except Exception as fb_err:
                        logger.warning(f"MCP fallback after Gemini failure errored: {fb_err}")
                return {"concepts": concepts_final, "debug_info": debug_info}
            else:
                # Non-Gemini path remains as before
                llm_result = self._extract_concepts_with_llm(content, concept_types)
                if "concepts" in llm_result:
                    _concepts = llm_result.get("concepts", [])
                    if self._looks_category_only(_concepts):
                        logger.info("Category-only LLM extraction; augmenting with heuristic role detection")
                        roles = self._extract_roles_heuristic(content)
                        if roles:
                            _concepts.extend(roles)
                    # Guard semantics in all cases
                    before_roles = len([c for c in _concepts if (c.get('type') or '').lower() == 'role'])
                    _concepts = self._enforce_role_semantics(_concepts)
                    after_roles = len([c for c in _concepts if (c.get('type') or '').lower() == 'role'])
                    logger.info(f"LLM extraction guard: roles before={before_roles}, after={after_roles}")
                    llm_result["concepts"] = self._prioritize_and_enrich_roles(_concepts)
                llm_result.setdefault("debug_info", {})
                llm_result["debug_info"].update(debug_info)
                return llm_result
                
        except Exception as e:
            logger.error(f"Error in extract_concepts: {str(e)}")
            return {"error": str(e)}
    
    def _extract_concepts_with_llm(self, content: str, concept_types: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        """Extract concepts using direct LLM calls. Supports Anthropic/OpenAI or Gemini when explicitly enabled.

        Behavior:
        - If USE_GEMINI_FOR_GUIDELINES=true and GOOGLE_API_KEY set, use Gemini with a role-centric prompt and no fallbacks.
        - Otherwise, use Anthropic/OpenAI via get_llm_client as before.
        """
        # Get LLM client (may be Gemini if enabled)
        try:
            llm_client = get_llm_client()
        except RuntimeError as e:
            logger.error(f"LLM client not available: {str(e)}")
            return {"error": f"LLM client not available: {str(e)}"}
        
        # Build dynamic prompt
        type_descriptions = []
        for type_name, type_info in concept_types.items():
            examples = ", ".join(type_info.get("examples", []))
            if examples:
                type_descriptions.append(
                    f"- {type_info['label']}: {type_info['description']} (e.g., {examples})"
                )
            else:
                type_descriptions.append(
                    f"- {type_info['label']}: {type_info['description']}"
                )
        
        type_list = "\n".join(type_descriptions)
        valid_types = "|".join(concept_types.keys())
        
        # Build prompts; if Gemini client, use a stricter, role-focused instruction and JSON schema
        use_gemini = os.getenv('USE_GEMINI_FOR_GUIDELINES', 'false').lower() == 'true'

        role_first_instructions = (
            "You are analyzing engineering ethics guidelines to extract ontology concepts. "
            "Absolutely prioritize extracting concrete Role titles that appear in the text. "
            "Distinguish professional roles (licensed/official/manager/engineer/architect/inspector) "
            "from participant roles (client/owner/public/community/resident/stakeholder). "
            "Do not output generic categories like 'Role' or 'Principle' by themselves. "
            f"Definition of Role to apply strictly: {self._role_definition_text()} "
            "Only include items explicitly present or unmistakably implied."
        )

        system_prompt = (
            f"{role_first_instructions}\n\nConcept types to identify:\n{type_list}\n\n"
            f"For each concept, provide: label, description, type in {{{valid_types}}}, confidence (0-1)."
        )

        user_prompt = (
            f"Extract high-confidence concepts from the following guideline text. "
            f"Return only a JSON array, no commentary.\n\n{content[:10000]}\n\n"
            "Example output format: [\n  {\n    \"label\": \"Professional Engineer\",\n    \"description\": \"Licensed engineer responsible for ...\",\n    \"type\": \"role\",\n    \"confidence\": 0.9\n  }\n]"
        )
        
        try:
            # Special handling for Gemini client
            if hasattr(llm_client, 'GenerativeModel') or hasattr(llm_client, 'generate_content'):
                try:
                    # google.generativeai API: build model name and send
                    model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                    model = getattr(llm_client, 'GenerativeModel', None)
                    if model is None:
                        # Some versions expose models via genai.GenerativeModel
                        model = llm_client.GenerativeModel
                    gen = model(model_name)
                    resp = gen.generate_content([
                        {"role": "user", "parts": system_prompt},
                        {"role": "user", "parts": user_prompt}
                    ])
                    text = resp.text if hasattr(resp, 'text') else str(resp)
                    if not text:
                        return {"error": "No response from Gemini", "concepts": []}
                    concepts = self._parse_llm_response(text, set(concept_types.keys()))
                    return {"concepts": self._prioritize_and_enrich_roles(concepts)}
                except Exception as ge:
                    # If Gemini was explicitly requested, fail fast without fallback
                    if use_gemini:
                        raise
                    logger.warning(f"Gemini call failed, falling back to non-Gemini path: {ge}")
            # Default path: Anthropic/OpenAI
            response_text = self._call_llm(llm_client, system_prompt, user_prompt)
            if response_text:
                concepts = self._parse_llm_response(response_text, set(concept_types.keys()))
                if concepts:
                    logger.info(f"Extracted {len(concepts)} concepts using LLM")
                    return {"concepts": concepts}
                else:
                    return {"error": "Failed to parse LLM response", "concepts": []}
            else:
                return {"error": "No response from LLM", "concepts": []}
        except Exception as e:
            logger.error(f"LLM extraction error: {str(e)}")
            return {"error": f"LLM error: {str(e)}", "concepts": []}

    def _extract_roles_only_with_llm(self, content: str, concept_types: Dict[str, Dict[str, str]], corrective: bool = False) -> List[Dict[str, Any]]:
        """Extract only Role concepts using the currently selected LLM client. If corrective=True, adds extra guardrails/examples."""
        try:
            llm_client = get_llm_client()
        except RuntimeError as e:
            logger.error(f"LLM client not available for roles-only: {e}")
            return []

        valid_types = set(concept_types.keys())
        assert 'role' in valid_types

        base_instruction = (
            f"Extract ONLY Role concepts from the text below. A Role must match: {self._role_definition_text()} "
            "Do not include activities, obligations, principles, or processes. Return 3-12 roles if present."
        )
        if corrective:
            base_instruction += (
                " Previous attempt included non-roles like 'Continuing Professional Development'. "
                "That is an obligation/program, not a role. Provide only titled roles (e.g., Professional Engineer, Project Manager, Inspector, Architect, Public Official)."
            )
        roles_system = base_instruction
        roles_user = (
            f"Text:\n{content[:10000]}\n\nReturn only a JSON array with items of the form: "
            "[{\"label\": \"Professional Engineer\", \"description\": \"...\", \"type\": \"role\", \"confidence\": 0.9}]"
        )

        try:
            # Gemini branch
            llm_is_gemini = hasattr(llm_client, 'GenerativeModel') or hasattr(llm_client, 'generate_content')
            if llm_is_gemini:
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = getattr(llm_client, 'GenerativeModel', None) or llm_client.GenerativeModel
                gen = model(model_name)
                resp = gen.generate_content([
                    {"role": "user", "parts": roles_system},
                    {"role": "user", "parts": roles_user}
                ])
                text = resp.text if hasattr(resp, 'text') else str(resp)
            else:
                # Anthropic/OpenAI path
                text = self._call_llm(llm_client, roles_system, roles_user)
            if not text:
                return []
            concepts = self._parse_llm_response(text, {'role'})
            # Keep only type=='role' concepts
            return [c for c in concepts if (c.get('type') or '').lower() == 'role']
        except Exception as e:
            logger.error(f"Roles-only extraction error: {e}")
            return []

    def _enforce_role_semantics(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop or reclassify items mislabeled as roles; keep the rest unchanged.

        Heuristics: role labels often end with titles like Engineer, Manager, Architect, Inspector, Officer, Official, Planner, Reviewer, Technician, Analyst, Director, Supervisor.
        Non-roles include nouns like Development, Training, Safety, Confidentiality, Competence, Compliance, Program, Policy, Code, Standard.
        """
        if not concepts:
            return concepts

        title_suffixes = [
            'engineer', 'manager', 'architect', 'inspector', 'officer', 'official', 'planner', 'reviewer',
            'technician', 'analyst', 'director', 'supervisor', 'auditor', 'consultant', 'contractor'
        ]
        non_role_keywords = [
            'development', 'training', 'safety', 'confidentiality', 'competence', 'compliance', 'program',
            'policy', 'code', 'standard', 'procedure', 'risk assessment', 'ethics', 'public safety'
        ]

        def looks_like_role(label: str) -> bool:
            l = (label or '').strip().lower()
            if not l:
                return False
            # Disallow obvious non-role terms
            for kw in non_role_keywords:
                if kw in l:
                    return False
            # Allow roles with common suffixes
            for suf in title_suffixes:
                if l.endswith(suf) or l.endswith(suf + 's'):
                    return True
            # Allow multiword titles including 'public/city/state ... engineer/officer/official'
            if any(word in l for word in ['engineer', 'officer', 'official', 'manager', 'architect', 'inspector']):
                return True
            return False

        cleaned: List[Dict[str, Any]] = []
        stakeholder_terms = {
            'client', 'clients', 'employer', 'employers', 'public', 'customer', 'customers', 'user', 'users',
            'community', 'communities', 'supplier', 'suppliers', 'vendor', 'vendors', 'regulator', 'regulators',
            'authority', 'authorities', 'government', 'governments', 'stakeholder', 'stakeholders'
        }
        for c in concepts:
            t = (c.get('type') or c.get('primary_type') or '').lower()
            if t != 'role':
                cleaned.append(c)
                continue
            label = c.get('label', '')
            if looks_like_role(label):
                cleaned.append(c)
            else:
                # Treat common stakeholders as roles (stakeholder classification)
                lbl_norm = (label or '').strip().lower()
                if lbl_norm in stakeholder_terms:
                    c2 = dict(c)
                    c2['type'] = 'role'
                    c2['role_classification'] = c2.get('role_classification') or 'stakeholder'
                    c2['mapping_justification'] = 'semantic_guard: preserved as stakeholder role for scenario participation'
                    c2['needs_type_review'] = False
                    cleaned.append(c2)
                    continue
                # Reclassify obvious non-roles if we can infer; otherwise drop and mark
                text = f"{label} {c.get('description','')}".lower()
                new_type = None
                if any(kw in text for kw in ['safety', 'integrity', 'welfare', 'fairness']):
                    new_type = 'principle'
                elif any(kw in text for kw in ['training', 'development', 'comply', 'must', 'shall', 'maintain', 'confidentiality', 'conflict of interest']):
                    new_type = 'obligation'
                elif any(kw in text for kw in ['program', 'policy', 'code', 'standard', 'procedure']):
                    new_type = 'resource'
                # Apply reclassification or drop
                if new_type:
                    c2 = dict(c)
                    c2['original_llm_type'] = c2.get('original_llm_type') or 'role'
                    c2['type'] = new_type
                    c2['needs_type_review'] = True
                    c2['mapping_justification'] = 'semantic_guard: reclassified non-role as more appropriate type'
                    c2['mapping_source'] = 'semantic_guard'
                    cleaned.append(c2)
                else:
                    # Drop ambiguous non-role labelled as role
                    logger.info(f"Dropping mislabeled role concept: {label}")
        return cleaned
    
    def _call_llm(self, llm_client, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Make LLM API call."""
        try:
            model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-sonnet-4-20250514')
            
            # Modern Claude API
            if hasattr(llm_client, 'messages'):
                response = llm_client.messages.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
                
                if hasattr(response, 'content') and len(response.content) > 0:
                    return response.content[0].text
                    
        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            
        return None
    
    def _parse_llm_response(self, response: str, valid_types: set) -> List[Dict[str, Any]]:
        """Parse and validate concepts from LLM response using intelligent type mapping."""
        try:
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                concepts = json.loads(json_match.group())
                
                # Validate each concept
                validated_concepts = []
                for concept in concepts:
                    # Ensure required fields
                    if not all(field in concept for field in ["label", "description", "type"]):
                        logger.warning(f"Skipping concept missing required fields: {concept}")
                        continue
                    
                    original_type = concept["type"]
                    
                    # Validate and map concept type
                    if original_type not in valid_types:
                        logger.info(f"Mapping invalid type '{original_type}' for concept '{concept['label']}'")
                        
                        # Use type mapper to get better mapping
                        mapping_result = self.type_mapper.map_concept_type(
                            llm_type=original_type,
                            concept_description=concept.get("description", ""),
                            concept_name=concept.get("label", "")
                        )
                        
                        # Store original type and mapping metadata
                        concept["original_llm_type"] = original_type
                        concept["type"] = mapping_result.mapped_type
                        concept["type_mapping_confidence"] = mapping_result.confidence
                        concept["needs_type_review"] = mapping_result.needs_review
                        concept["mapping_justification"] = mapping_result.justification
                        
                        logger.info(f"Mapped '{original_type}' → '{mapping_result.mapped_type}' (confidence: {mapping_result.confidence:.2f})")
                    else:
                        # Type is already valid - no mapping needed
                        concept["original_llm_type"] = original_type
                        concept["type_mapping_confidence"] = 1.0  # Perfect confidence for exact match
                        concept["needs_type_review"] = False
                        concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                    
                    # Add default confidence if missing
                    if "confidence" not in concept:
                        concept["confidence"] = 0.7
                        
                    validated_concepts.append(concept)
                
                return validated_concepts
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Error parsing concepts: {e}")
            
        return []

    def _prioritize_and_enrich_roles(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reorder concepts to put roles first and classify roles as professional vs participant.

        Adds fields to role concepts:
        - role_classification: "professional" | "participant"
        - suggested_parent_class_uri: intermediate ProfessionalRole or ParticipantRole
        - role_signals: keywords that triggered the classification
        """
        if not concepts:
            return concepts

        professional_keywords = [
            "engineer", "licensed", "professional", "pe", "p.e.", "regulator", "official",
            "inspector", "manager", "architect", "planner", "reviewer", "board", "committee"
        ]
        participant_keywords = [
            "client", "customer", "owner", "public", "community", "resident", "citizen",
            "stakeholder", "user", "vendor"
        ]

        def classify_role(label: str, description: str) -> Tuple[str, List[str]]:
            text = f"{label} {description}".lower()
            hits = []
            role_type = "participant"
            for kw in professional_keywords:
                if kw in text:
                    hits.append(kw)
            if hits:
                role_type = "professional"
            else:
                for kw in participant_keywords:
                    if kw in text:
                        hits.append(kw)
                        role_type = "participant"
                        break
            return role_type, hits

        enriched: List[Dict[str, Any]] = []
        for c in concepts:
            c2 = dict(c)
            type_lower = (c2.get("type") or c2.get("primary_type") or "").lower()
            if type_lower == "role":
                role_type, hits = classify_role(c2.get("label", ""), c2.get("description", ""))
                c2["role_classification"] = role_type
                c2["role_signals"] = hits
                if role_type == "professional":
                    c2["suggested_parent_class_uri"] = "http://proethica.org/ontology/intermediate#ProfessionalRole"
                else:
                    c2["suggested_parent_class_uri"] = "http://proethica.org/ontology/intermediate#ParticipantRole"
            enriched.append(c2)

        # Stable sort: roles to the top, then by confidence desc if available
        def sort_key(item: Dict[str, Any]):
            t = (item.get("type") or item.get("primary_type") or "").lower()
            is_role = 0 if t == "role" else 1
            conf = item.get("confidence", 0)
            return (is_role, -conf)

        enriched.sort(key=sort_key)
        return enriched

    def _looks_category_only(self, concepts: List[Dict[str, Any]]) -> bool:
        """Detect when extraction yielded mostly generic category labels and no roles."""
        if not concepts:
            return False
        n = len(concepts)
        if n < 8 or n > 30:
            return False
        generic = 0
        roles = 0
        for c in concepts:
            t = (c.get("type") or c.get("primary_type") or "").strip().lower()
            l = (c.get("label") or "").strip()
            if t == "role":
                roles += 1
            if l and (l.lower() == t or l == t.title()):
                generic += 1
        return roles == 0 and (generic / float(n)) >= 0.6

    def _extract_roles_heuristic(self, text: str) -> List[Dict[str, Any]]:
        """Heuristic extraction of Role concepts from raw text when upstream returns generic categories only."""
        if not text:
            return []
        candidates = set()
        patterns = [
            r"\bprofessional engineer(s)?\b",
            r"\blicensed engineer(s)?\b",
            r"\b(structural|civil|mechanical|electrical|software|systems) engineer(s)?\b",
            r"\bproject manager(s)?\b",
            r"\bengineering manager(s)?\b",
            r"\binspector(s)?\b",
            r"\b(public|city|county|state|federal) official(s)?\b",
            r"\b(public|city|county) engineer(s)?\b",
            r"\barchitect(s)?\b",
            r"\breviewer(s)?\b",
            r"\bethics committee( member)?s?\b",
            r"\bboard of (ethics|review)\b",
            r"\bclient(s)?\b",
            r"\bowner(s)?\b",
            r"\bcontractor(s)?\b",
            r"\bsubcontractor(s)?\b",
            r"\bcommunity member(s)?\b",
            r"\bresident(s)?\b",
            r"\bthe public\b",
            r"\bvendor(s)?\b",
            r"\bsupplier(s)?\b",
        ]
        for pat in patterns:
            for m in re.finditer(pat, text, flags=re.IGNORECASE):
                label = m.group(0)
                norm = " ".join(w.capitalize() if w.lower() not in ("of", "the") else w.lower() for w in label.split())
                candidates.add(norm)
        # Capture capitalized forms like "County Engineer", "City Engineer"
        for m in re.finditer(r"\b([A-Z][a-z]+) Engineer(s)?\b", text):
            candidates.add(m.group(0))
        roles = []
        seen = set()
        for label in sorted(candidates):
            key = label.rstrip('s').lower()
            if key in seen:
                continue
            seen.add(key)
            roles.append({
                "label": label,
                "description": f"Role referenced in guideline: {label}",
                "type": "role",
                "confidence": 0.6
            })
        return roles
    
    def _generate_mock_concepts(self, content: str, concept_types: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Generate mock concepts for testing."""
        mock_concepts = []
        
        # Add one concept of each type for testing
        if "engineer" in content.lower():
            mock_concepts.append({
                "label": "Professional Engineer",
                "description": "A licensed engineer responsible for public safety",
                "type": "role",
                "confidence": 0.9
            })
            
        if "safety" in content.lower():
            mock_concepts.append({
                "label": "Public Safety",
                "description": "The paramount duty to protect public health, safety, and welfare",
                "type": "principle",
                "confidence": 0.95
            })
            
        if "confidential" in content.lower():
            mock_concepts.append({
                "label": "Maintain Confidentiality",
                "description": "The obligation to protect client confidential information",
                "type": "obligation",
                "confidence": 0.85
            })
            
        # Add at least one of each type if content is long enough
        if len(content) > 100:
            mock_concepts.extend([
                {
                    "label": "Budget Constraints",
                    "description": "Financial limitations affecting project decisions",
                    "type": "state",
                    "confidence": 0.7
                },
                {
                    "label": "Technical Standards",
                    "description": "Engineering codes and specifications",
                    "type": "resource",
                    "confidence": 0.8
                },
                {
                    "label": "Design Review",
                    "description": "Systematic evaluation of engineering designs",
                    "type": "action",
                    "confidence": 0.75
                },
                {
                    "label": "Project Completion",
                    "description": "The finalization of an engineering project",
                    "type": "event",
                    "confidence": 0.7
                },
                {
                    "label": "Risk Assessment",
                    "description": "The ability to identify and evaluate potential hazards",
                    "type": "capability",
                    "confidence": 0.8
                }
            ])
            
        return mock_concepts
    
    def extract_ontology_terms_from_text(self,
                                        guideline_text: str,
                                        world_id: int,
                                        guideline_id: int,
                                        ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract ontology terms directly from guideline text.
        This finds mentions of engineering-ethics ontology terms in the text itself.
        
        Args:
            guideline_text: The full text of the guideline
            world_id: World ID for context
            guideline_id: Guideline ID for triple association
            ontology_source: Ontology to search for terms (default: 'engineering-ethics')
            
        Returns:
            Dict with extracted term triples and metadata
        """
        try:
            logger.info(f"Extracting ontology terms from guideline text")
            
            # Set default ontology source
            if not ontology_source:
                ontology_source = 'engineering-ethics'
            
            # If mock responses are enabled, return mock triples
            if self.use_mock_responses:
                logger.info("Using mock ontology term extraction")
                mock_triples = self._generate_mock_ontology_triples(guideline_text, world_id, guideline_id)
                return {
                    'success': True,
                    'triples': mock_triples,
                    'triple_count': len(mock_triples),
                    'mock': True,
                    'message': "Using mock guideline responses"
                }
            
            # Try MCP server for ontology term extraction
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Using MCP server for ontology term extraction")
                    
                    # First extract concepts from the text
                    extract_response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "extract_guideline_concepts",
                                "arguments": {
                                    "content": guideline_text[:50000],  # Limit content length
                                    "ontology_source": ontology_source
                                }
                            },
                            "id": 1
                        },
                        timeout=60
                    )
                    
                    if extract_response.status_code == 200:
                        extract_result = extract_response.json()
                        if "result" in extract_result and "concepts" in extract_result["result"]:
                            concepts = extract_result["result"]["concepts"]
                            
                            # Select all concepts (you could be more selective here)
                            selected_indices = list(range(len(concepts)))
                            
                            # Now generate triples for these concepts
                            response = requests.post(
                                f"{mcp_url}/jsonrpc",
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "call_tool",
                                    "params": {
                                        "name": "generate_concept_triples",
                                        "arguments": {
                                            "concepts": concepts,
                                            "selected_indices": selected_indices,
                                            "ontology_source": ontology_source,
                                            "namespace": f"http://proethica.org/guidelines/guideline_{guideline_id}/",
                                            "output_format": "json"
                                        }
                                    },
                                    "id": 2
                                },
                                timeout=60
                            )
                    
                            if response and response.status_code == 200:
                                result = response.json()
                                if "result" in result and "triples" in result["result"]:
                                    triples = result["result"]["triples"]
                                    logger.info(f"MCP server extracted {len(triples)} ontology term triples")
                                    return {
                                        'success': True,
                                        'triples': triples,
                                        'triple_count': len(triples)
                                    }
                                elif "error" in result:
                                    logger.error(f"MCP server error: {result['error']}")
                        else:
                            logger.warning("Failed to extract concepts from text")
                            
            except Exception as e:
                logger.warning(f"MCP server error, falling back to mock: {str(e)}")
            
            # Fall back to mock triples if MCP fails
            logger.info("Falling back to mock ontology term extraction")
            mock_triples = self._generate_mock_ontology_triples(guideline_text, world_id, guideline_id)
            return {
                'success': True,
                'triples': mock_triples,
                'triple_count': len(mock_triples),
                'fallback': True,
                'message': "MCP server unavailable, using mock data"
            }
                
        except Exception as e:
            logger.error(f"Error in extract_ontology_terms_from_text: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'triples': [],
                'triple_count': 0
            }
    
    def _generate_mock_ontology_triples(self, guideline_text: str, world_id: int, guideline_id: int) -> List[Dict[str, Any]]:
        """Generate mock ontology term triples for testing."""
        mock_triples = []
        
        namespace = "http://proethica.org/guidelines/"
        ontology_namespace = "http://proethica.org/ontology/"
        guideline_uri = f"{namespace}guideline_{guideline_id}"
        
        # Mock some common ontology terms that might be found in engineering ethics text
        mock_terms = [
            {"term": "Engineer", "category": "role", "uri": f"{ontology_namespace}Engineer"},
            {"term": "Public Safety", "category": "principle", "uri": f"{ontology_namespace}PublicSafety"},
            {"term": "Professional Competence", "category": "capability", "uri": f"{ontology_namespace}ProfessionalCompetence"},
            {"term": "Conflict of Interest", "category": "condition", "uri": f"{ontology_namespace}ConflictOfInterest"},
            {"term": "Ethical Decision", "category": "action", "uri": f"{ontology_namespace}EthicalDecision"}
        ]
        
        # Add mock triples for terms that might appear in the text
        for i, term_info in enumerate(mock_terms):
            if i >= 3:  # Limit to 3 mock terms
                break
                
            # Add mention triple
            mention_triple = {
                'subject': guideline_uri,
                'subject_label': f'Guideline {guideline_id}',
                'predicate': f"{ontology_namespace}mentionsTerm",
                'predicate_label': 'mentions term',
                'object_uri': term_info['uri'],
                'object_label': term_info['term'],
                'triple_metadata': {
                    'confidence': 0.8,
                    'text_snippet': f"...{term_info['term'].lower()}...",
                    'category': term_info['category'],
                    'mock': True
                }
            }
            mock_triples.append(mention_triple)
            
            # Add category-specific relationship
            category = term_info['category']
            if category == 'role':
                rel_triple = {
                    'subject': guideline_uri,
                    'subject_label': f'Guideline {guideline_id}',
                    'predicate': f"{ontology_namespace}definesRole",
                    'predicate_label': 'defines role',
                    'object_uri': term_info['uri'],
                    'object_label': term_info['term']
                }
                mock_triples.append(rel_triple)
            elif category == 'principle':
                rel_triple = {
                    'subject': guideline_uri,
                    'subject_label': f'Guideline {guideline_id}',
                    'predicate': f"{ontology_namespace}embodiesPrinciple",
                    'predicate_label': 'embodies principle',
                    'object_uri': term_info['uri'],
                    'object_label': term_info['term']
                }
                mock_triples.append(rel_triple)
        
        return mock_triples
    
    def generate_triples_for_concepts(self, concepts: List[Dict[str, Any]], 
                                    world_id: int, 
                                    guideline_id: Optional[int] = None,
                                    ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate RDF triples for the given saved concepts.
        Skips concept extraction and goes directly to triple generation.
        
        Args:
            concepts: List of saved concept dictionaries with 'label', 'type', 'description'
            world_id: World ID for context
            guideline_id: Guideline ID for triple association
            ontology_source: Ontology to align with (default: 'engineering-ethics')
            
        Returns:
            Dict with generated triples and metadata
        """
        try:
            logger.info(f"Generating triples for {len(concepts)} saved concepts")
            
            # Set default ontology source
            if not ontology_source:
                ontology_source = 'engineering-ethics'
            
            # Convert saved concepts to the format expected by MCP server
            mcp_concepts = []
            for i, concept in enumerate(concepts):
                mcp_concept = {
                    'id': f'concept_{i}',
                    'label': concept.get('label', 'Unknown Concept'),
                    'description': concept.get('description', ''),
                    'category': concept.get('type', 'concept').lower()
                }
                mcp_concepts.append(mcp_concept)
            
            # If mock responses are enabled, return mock triples
            if self.use_mock_responses:
                logger.info("Using mock triple generation for saved concepts")
                mock_triples = self._generate_mock_ontology_triples("", world_id, guideline_id or 0)
                return {
                    'success': True,
                    'triples': mock_triples,
                    'triple_count': len(mock_triples),
                    'mock': True,
                    'message': "Using mock guideline responses"
                }
            
            # Try MCP server for triple generation
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Using MCP server for triple generation from saved concepts")
                    
                    # Generate triples for saved concepts - select all concepts
                    selected_indices = list(range(len(mcp_concepts)))
                    
                    response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "generate_concept_triples",
                                "arguments": {
                                    "concepts": mcp_concepts,
                                    "selected_indices": selected_indices,
                                    "ontology_source": ontology_source,
                                    "namespace": f"http://proethica.org/guidelines/guideline_{guideline_id}/",
                                    "output_format": "json"
                                }
                            },
                            "id": 1
                        },
                        timeout=60
                    )
            
                    if response and response.status_code == 200:
                        result = response.json()
                        if "result" in result and "triples" in result["result"]:
                            triples = result["result"]["triples"]
                            logger.info(f"MCP server generated {len(triples)} triples from saved concepts")
                            return {
                                'success': True,
                                'triples': triples,
                                'triple_count': len(triples),
                                'term_count': len(concepts)
                            }
                        elif "error" in result:
                            logger.error(f"MCP server error: {result['error']}")
                    else:
                        logger.warning(f"MCP server returned status {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"MCP server error, falling back to mock: {str(e)}")
            
            # Fall back to mock triples if MCP fails
            logger.info("Falling back to mock triple generation for saved concepts")
            mock_triples = self._generate_mock_ontology_triples("", world_id, guideline_id or 0)
            return {
                'success': True,
                'triples': mock_triples,
                'triple_count': len(mock_triples),
                'term_count': len(concepts),
                'fallback': True,
                'message': "MCP server unavailable, using mock data"
            }
                
        except Exception as e:
            logger.error(f"Error in generate_triples_for_concepts: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'triples': [],
                'triple_count': 0
            }