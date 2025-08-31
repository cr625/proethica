"""
Enhanced Guideline Association Service

This service generates outcome-aware associations between cases and guideline concepts
using semantic similarity, keyword overlap, and contextual relevance measures.

Author: Claude Code
Date: June 9, 2025
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

from sqlalchemy import text
from app import db
from app.models.scenario import Scenario
from app.models import Document
from app.models.entity_triple import EntityTriple
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

@dataclass
class AssociationScore:
    """Container for association scoring metrics"""
    # Embedding-based scores
    embedding_similarity: float
    keyword_overlap: float  
    contextual_relevance: float
    
    # LLM-based scores
    llm_semantic_score: float
    llm_reasoning_quality: float
    
    # Combined scores
    overall_confidence: float
    
    # Explanations
    embedding_reasoning: str
    llm_reasoning: str
    combined_reasoning: str

@dataclass  
class GuidelineAssociation:
    """Container for guideline association data"""
    case_id: int
    guideline_concept_id: int
    section_type: str
    score: AssociationScore
    pattern_indicators: Dict[str, Any]
    association_method: str = 'semantic_similarity'

class EnhancedGuidelineAssociationService:
    """
    Service for generating enhanced guideline associations with outcome prediction capabilities
    """
    
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.llm_service = LLMService()
        self.min_confidence_threshold = 0.3
        self.max_associations_per_section = 10
        
    def generate_associations_for_case(self, case_id: int) -> List[GuidelineAssociation]:
        """
        Generate all guideline associations for a specific case
        
        Args:
            case_id: Database ID of the case (scenario)
            
        Returns:
            List of GuidelineAssociation objects
        """
        logger.info(f"Generating associations for case {case_id}")
        
        # Get case data (could be Document or Scenario)
        from app.models import Document
        case = Document.query.get(case_id)
        if not case:
            case = Scenario.query.get(case_id)
            if not case:
                raise ValueError(f"Case {case_id} not found in either documents or scenarios")
            
        # Get case sections from metadata
        sections = self._extract_case_sections(case)
        if not sections:
            logger.warning(f"No sections found for case {case_id}")
            return []
            
        # Get all guideline concepts
        guideline_concepts = self._get_guideline_concepts()
        if not guideline_concepts:
            logger.warning("No guideline concepts found")
            return []
            
        # Generate associations for each section
        all_associations = []
        
        for section_type, section_content in sections.items():
            if not section_content or not section_content.strip():
                continue
                
            section_associations = self._generate_section_associations(
                case_id, section_type, section_content, guideline_concepts
            )
            all_associations.extend(section_associations)
            
        logger.info(f"Generated {len(all_associations)} associations for case {case_id}")
        return all_associations
    
    def _extract_case_sections(self, case) -> Dict[str, str]:
        """Extract sections from case metadata (works with both Document and Scenario)"""
        sections = {}
        
        # Get metadata from the appropriate field
        metadata = None
        if hasattr(case, 'scenario_metadata') and case.scenario_metadata:
            metadata = case.scenario_metadata
        elif hasattr(case, 'doc_metadata') and case.doc_metadata:
            metadata = case.doc_metadata
        
        if not metadata:
            return sections
            
        # Check for document structure format
        if 'document_structure' in metadata:
            doc_structure = metadata['document_structure']
            if 'sections' in doc_structure:
                sections_data = doc_structure['sections']
                logger.info(f"Sections data type: {type(sections_data)}, length: {len(sections_data) if hasattr(sections_data, '__len__') else 'N/A'}")
                
                # Handle different section formats
                if isinstance(sections_data, list):
                    for i, section_data in enumerate(sections_data):
                        if i < 3:  # Log first 3 items for debugging
                            logger.info(f"Section {i}: type={type(section_data)}, value={str(section_data)[:100]}...")
                        
                        # Skip if section_data is a string or not a dict
                        if not isinstance(section_data, dict):
                            logger.warning(f"Skipping non-dict section data: {type(section_data)}")
                            continue
                            
                        section_type = section_data.get('type', '').lower()
                        
                        # Get clean text content
                        content = ''
                        if 'content_text' in section_data:
                            content = section_data['content_text']
                        elif 'content' in section_data:
                            content = section_data['content']
                            
                        if content and section_type:
                            sections[section_type] = content
                elif isinstance(sections_data, dict):
                    # Handle case where sections is a dict of section_type: content
                    for section_type, content in sections_data.items():
                        if isinstance(content, str) and content:
                            sections[section_type.lower()] = content
                        
        # Fallback to legacy section format
        if not sections and 'sections' in metadata:
            legacy_sections = metadata['sections']
            if isinstance(legacy_sections, list):
                for section_data in legacy_sections:
                    # Skip if section_data is not a dict
                    if not isinstance(section_data, dict):
                        logger.warning(f"Skipping non-dict legacy section data: {type(section_data)}")
                        continue
                        
                    section_type = section_data.get('type', '').lower()
                    content = section_data.get('content', '')
                    if content and section_type:
                        sections[section_type] = content
            elif isinstance(legacy_sections, dict):
                # Handle case where sections is a dict
                for section_type, content in legacy_sections.items():
                    if isinstance(content, str) and content:
                        sections[section_type.lower()] = content
                    
        return sections
    
    def _get_guideline_concepts(self) -> List[EntityTriple]:
        """Get all guideline concept entities"""
        return EntityTriple.query.filter(
            EntityTriple.entity_type == 'guideline_concept',
            EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        ).all()
    
    def _generate_section_associations(
        self, 
        case_id: int, 
        section_type: str, 
        section_content: str, 
        guideline_concepts: List[EntityTriple]
    ) -> List[GuidelineAssociation]:
        """Generate associations for a specific case section"""
        
        associations = []
        
        for concept in guideline_concepts:
            # Calculate association score
            score = self._calculate_association_score(section_content, concept)
            
            # Skip low-confidence associations
            if score.overall_confidence < self.min_confidence_threshold:
                continue
                
            # Generate pattern indicators
            pattern_indicators = self._generate_pattern_indicators(
                section_type, section_content, concept, score
            )
            
            association = GuidelineAssociation(
                case_id=case_id,
                guideline_concept_id=concept.id,
                section_type=section_type,
                score=score,
                pattern_indicators=pattern_indicators
            )
            
            associations.append(association)
            
        # Sort by confidence and limit results
        associations.sort(key=lambda a: a.score.overall_confidence, reverse=True)
        return associations[:self.max_associations_per_section]
    
    def _calculate_association_score(self, section_content: str, concept: EntityTriple) -> AssociationScore:
        """
        Calculate hybrid multi-dimensional association score using both embeddings and LLM
        
        Returns:
            AssociationScore with separate embedding and LLM scores plus combined overall score
        """
        
        # Get concept text representation
        concept_text = self._get_concept_text(concept)
        
        # === EMBEDDING-BASED SCORING ===
        embedding_similarity = self._calculate_embedding_similarity(section_content, concept_text)
        keyword_overlap = self._calculate_keyword_overlap(section_content, concept_text)
        contextual_relevance = self._calculate_contextual_relevance(section_content, concept)
        
        # Generate embedding-based reasoning
        embedding_reasoning = self._generate_embedding_reasoning(
            embedding_similarity, keyword_overlap, contextual_relevance, concept_text
        )
        
        # === LLM-BASED SCORING ===
        llm_scores = self._calculate_llm_scores(section_content, concept_text, concept)
        llm_semantic_score = llm_scores.get('semantic_score', 0.0)
        llm_reasoning_quality = llm_scores.get('reasoning_quality', 0.0)
        llm_reasoning = llm_scores.get('reasoning', 'LLM analysis unavailable')
        
        # === HYBRID COMBINATION ===
        # Weight the scores: embeddings (reliable, fast) + LLM (nuanced, context-aware)
        overall_confidence = (
            0.35 * embedding_similarity +    # Fast, reliable semantic matching
            0.25 * llm_semantic_score +      # Nuanced LLM semantic analysis
            0.20 * contextual_relevance +    # Context pattern matching
            0.15 * llm_reasoning_quality +   # LLM reasoning coherence
            0.05 * keyword_overlap           # Simple keyword matching
        )
        
        # Generate combined reasoning explaining both methods
        combined_reasoning = self._generate_combined_reasoning(
            embedding_similarity, llm_semantic_score, embedding_reasoning, llm_reasoning, concept_text
        )
        
        return AssociationScore(
            # Embedding scores
            embedding_similarity=embedding_similarity,
            keyword_overlap=keyword_overlap,
            contextual_relevance=contextual_relevance,
            
            # LLM scores  
            llm_semantic_score=llm_semantic_score,
            llm_reasoning_quality=llm_reasoning_quality,
            
            # Combined
            overall_confidence=overall_confidence,
            
            # Reasonings
            embedding_reasoning=embedding_reasoning,
            llm_reasoning=llm_reasoning,
            combined_reasoning=combined_reasoning
        )
    
    def _get_concept_text(self, concept: EntityTriple) -> str:
        """Extract text representation from concept entity"""
        # Handle case where concept might be a dict-like object
        if hasattr(concept, 'get'):
            object_literal = concept.get('object_literal')
            subject = concept.get('subject')
        else:
            object_literal = getattr(concept, 'object_literal', None)
            subject = getattr(concept, 'subject', None)
            
        # Try object_literal first
        if object_literal:
            return object_literal
            
        # Fallback to subject URI (extract readable name)
        if subject:
            # Extract the fragment or last part of URI
            parts = subject.split('/')
            if parts:
                name = parts[-1].replace('_', ' ').replace('-', ' ')
                return name
                
        return ""
    
    def _calculate_embedding_similarity(self, text1: str, text2: str) -> float:
        """Calculate embedding-based semantic similarity"""
        try:
            embedding1 = self.embedding_service.get_embedding(text1)
            embedding2 = self.embedding_service.get_embedding(text2)
            
            if embedding1 and embedding2:
                # Calculate cosine similarity
                import numpy as np
                
                # Convert to numpy arrays
                vec1 = np.array(embedding1)
                vec2 = np.array(embedding2)
                
                # Calculate cosine similarity
                dot_product = np.dot(vec1, vec2)
                norm1 = np.linalg.norm(vec1)
                norm2 = np.linalg.norm(vec2)
                
                if norm1 > 0 and norm2 > 0:
                    similarity = dot_product / (norm1 * norm2)
                    # Ensure the result is between 0 and 1
                    return max(0.0, min(1.0, (similarity + 1) / 2))
                
        except Exception as e:
            logger.warning(f"Error calculating semantic similarity: {e}")
            
        return 0.0
    
    def _calculate_keyword_overlap(self, text1: str, text2: str) -> float:
        """Calculate keyword overlap score"""
        
        # Simple tokenization and normalization
        def normalize_tokens(text):
            tokens = text.lower().split()
            # Remove common stop words
            stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'}
            return set(token.strip('.,!?:;') for token in tokens if token not in stop_words and len(token) > 2)
        
        tokens1 = normalize_tokens(text1)
        tokens2 = normalize_tokens(text2)
        
        if not tokens1 or not tokens2:
            return 0.0
            
        # Calculate Jaccard similarity
        intersection = len(tokens1.intersection(tokens2))
        union = len(tokens1.union(tokens2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_contextual_relevance(self, section_content: str, concept: EntityTriple) -> float:
        """Calculate contextual relevance score"""
        
        # Simple heuristic based on concept URI and section content
        concept_uri = concept.subject.lower() if concept.subject else ""
        content_lower = section_content.lower()
        
        relevance_score = 0.0
        
        # Check for direct concept mentions
        concept_keywords = self._extract_concept_keywords(concept_uri)
        for keyword in concept_keywords:
            if keyword in content_lower:
                relevance_score += 0.3
                
        # Cap at 1.0
        return min(relevance_score, 1.0)
    
    def _extract_concept_keywords(self, concept_uri: str) -> List[str]:
        """Extract keywords from concept URI"""
        keywords = []
        
        # Extract from URI fragments
        if '/' in concept_uri:
            fragment = concept_uri.split('/')[-1]
            # Split on common separators
            for separator in ['_', '-', '.']:
                fragment = fragment.replace(separator, ' ')
            keywords.extend(fragment.split())
            
        # Clean and filter keywords
        return [kw.lower() for kw in keywords if len(kw) > 2]
    
    def _calculate_llm_scores(self, section_content: str, concept_text: str, concept: EntityTriple) -> Dict[str, Any]:
        """
        Calculate LLM-based scores for semantic similarity and reasoning quality
        
        Returns:
            Dictionary with semantic_score, reasoning_quality, and reasoning text
        """
        try:
            # Construct prompt for LLM analysis
            prompt = f"""You are an expert in engineering ethics. Analyze the semantic relationship between this case section and ethical concept.

CASE SECTION:
{section_content[:500]}...

ETHICAL CONCEPT: {concept_text}
CONCEPT URI: {concept.subject}

TASK: Provide scores and reasoning for how this ethical concept relates to the case section.

1. Semantic Similarity Score (0.0-1.0): How semantically related is the section to this concept?
2. Reasoning Quality Score (0.0-1.0): How well does this concept help understand the ethical issues?
3. Detailed Reasoning: Explain the relationship, focusing on ethical principles and patterns.

IMPORTANT: Respond ONLY with valid JSON in this exact format:
{{
    "semantic_score": 0.85,
    "reasoning_quality": 0.75,
    "reasoning": "Detailed explanation of the ethical relationship..."
}}

Do not include any text before or after the JSON."""
            
            # Get LLM response
            llm_response = self.llm_service.send_message(prompt)
            
            if llm_response and hasattr(llm_response, 'content'):
                logger.info(f"LLM response content: '{llm_response.content}' (type: {type(llm_response.content)})")
                
                try:
                    # Parse JSON response
                    import json
                    
                    # Handle empty or whitespace-only content
                    if not llm_response.content or not llm_response.content.strip():
                        logger.warning("LLM returned empty content")
                        raise ValueError("Empty LLM response")
                    
                    # Try to extract JSON from the response if it's wrapped in other text
                    content = llm_response.content.strip()
                    
                    # Look for JSON block if response has extra text
                    if content.startswith('```json'):
                        # Extract JSON from code block
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start != -1 and json_end != 0:
                            content = content[json_start:json_end]
                    elif not content.startswith('{'):
                        # Look for the first { and last } in the response
                        json_start = content.find('{')
                        json_end = content.rfind('}') + 1
                        if json_start != -1 and json_end != 0:
                            content = content[json_start:json_end]
                        else:
                            logger.warning(f"No JSON found in LLM response: {content[:200]}...")
                            raise ValueError("No JSON in LLM response")
                    
                    result = json.loads(content)
                    
                    # Validate and normalize scores
                    semantic_score = max(0.0, min(1.0, float(result.get('semantic_score', 0.0))))
                    reasoning_quality = max(0.0, min(1.0, float(result.get('reasoning_quality', 0.0))))
                    reasoning = result.get('reasoning', 'LLM provided incomplete reasoning')
                    
                    logger.info(f"Parsed LLM scores: semantic={semantic_score}, quality={reasoning_quality}")
                    
                    return {
                        'semantic_score': semantic_score,
                        'reasoning_quality': reasoning_quality,
                        'reasoning': reasoning
                    }
                    
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse LLM response: {e}")
                    
        except Exception as e:
            logger.warning(f"LLM scoring failed: {e}")
            
        # Fallback scores when LLM unavailable
        return {
            'semantic_score': 0.0,
            'reasoning_quality': 0.0, 
            'reasoning': 'LLM analysis unavailable - using embedding-based analysis only'
        }
    
    def _generate_embedding_reasoning(
        self, 
        embedding_sim: float, 
        keyword: float, 
        contextual: float, 
        concept_text: str
    ) -> str:
        """Generate human-readable reasoning for embedding-based scoring"""
        
        components = []
        
        if embedding_sim >= 0.7:
            components.append(f"strong vector similarity ({embedding_sim:.2f})")
        elif embedding_sim >= 0.4:
            components.append(f"moderate vector similarity ({embedding_sim:.2f})")
            
        if keyword >= 0.3:
            components.append(f"keyword overlap ({keyword:.2f})")
            
        if contextual >= 0.3:
            components.append(f"contextual patterns ({contextual:.2f})")
            
        if components:
            return f"Embedding analysis: {', '.join(components)} → '{concept_text}'"
        else:
            return f"Embedding analysis: Low confidence → '{concept_text}'"
    
    def _generate_combined_reasoning(
        self,
        embedding_sim: float,
        llm_semantic: float, 
        embedding_reasoning: str,
        llm_reasoning: str,
        concept_text: str
    ) -> str:
        """Generate combined reasoning explaining both embedding and LLM contributions"""
        
        # Determine primary driver
        if embedding_sim > llm_semantic + 0.2:
            primary = "vector-driven"
        elif llm_semantic > embedding_sim + 0.2:
            primary = "LLM-driven"
        else:
            primary = "hybrid"
            
        # Create summary
        summary = f"{primary} association (embedding: {embedding_sim:.2f}, LLM: {llm_semantic:.2f}) → '{concept_text}'"
        
        return summary
    
    def _generate_pattern_indicators(
        self, 
        section_type: str, 
        section_content: str, 
        concept: EntityTriple, 
        score: AssociationScore
    ) -> Dict[str, Any]:
        """Generate pattern indicators for outcome prediction"""
        
        # Helper function to convert numpy types
        def ensure_python_type(value):
            if hasattr(value, 'item'):  # numpy scalar
                return value.item()
            return value
        
        indicators = {
            'section_type': section_type,
            'confidence_level': ensure_python_type(score.overall_confidence),
            'pattern_strength': ensure_python_type(score.embedding_similarity),
            'concept_uri': concept.subject
        }
        
        # Add section-specific indicators
        content_lower = section_content.lower()
        
        if section_type == 'facts':
            indicators.update({
                'safety_mentioned': any(word in content_lower for word in ['safety', 'danger', 'risk', 'hazard']),
                'competence_involved': any(word in content_lower for word in ['competence', 'expertise', 'qualification']),
                'economic_pressure': any(word in content_lower for word in ['cost', 'budget', 'economic', 'financial']),
                'stakeholder_conflict': any(word in content_lower for word in ['conflict', 'competing', 'opposing'])
            })
        elif section_type == 'discussion':
            indicators.update({
                'nspe_code_referenced': 'nspe' in content_lower or 'code' in content_lower,
                'multiple_perspectives': any(word in content_lower for word in ['however', 'alternatively', 'consider']),
                'public_welfare_prioritized': any(word in content_lower for word in ['public', 'welfare', 'society']),
                'professional_standards': any(word in content_lower for word in ['standard', 'professional', 'ethical'])
            })
        elif section_type == 'conclusion':
            indicators.update({
                'action_recommended': any(word in content_lower for word in ['should', 'must', 'recommend', 'action']),
                'ethical_reasoning': any(word in content_lower for word in ['ethical', 'moral', 'right', 'wrong']),
                'public_interest': any(word in content_lower for word in ['public', 'interest', 'society', 'welfare'])
            })
            
        return indicators
    
    def save_associations_to_database(self, associations: List[GuidelineAssociation]) -> int:
        """
        Save associations to the database
        
        Returns:
            Number of associations saved
        """
        saved_count = 0
        
        for assoc in associations:
            try:
                # Prepare data for insert - convert numpy types to Python types
                def convert_numpy(value):
                    """Convert numpy types to Python types"""
                    if hasattr(value, 'item'):  # numpy scalar
                        return value.item()
                    return value
                
                insert_data = {
                    'case_id': assoc.case_id,
                    'guideline_concept_id': assoc.guideline_concept_id,
                    'section_type': assoc.section_type,
                    'semantic_similarity': convert_numpy(assoc.score.embedding_similarity),
                    'keyword_overlap': convert_numpy(assoc.score.keyword_overlap),
                    'contextual_relevance': convert_numpy(assoc.score.contextual_relevance),
                    'overall_confidence': convert_numpy(assoc.score.overall_confidence),
                    'llm_semantic_score': convert_numpy(assoc.score.llm_semantic_score),
                    'llm_reasoning_quality': convert_numpy(assoc.score.llm_reasoning_quality),
                    'pattern_indicators': json.dumps(assoc.pattern_indicators, default=convert_numpy),
                    'association_reasoning': assoc.score.combined_reasoning,
                    'embedding_reasoning': assoc.score.embedding_reasoning,
                    'llm_reasoning': assoc.score.llm_reasoning,
                    'scoring_method': 'hybrid',
                    'association_method': assoc.association_method
                }
                
                # Insert with ON CONFLICT handling
                insert_sql = text("""
                    INSERT INTO case_guideline_associations 
                    (case_id, guideline_concept_id, section_type, semantic_similarity, 
                     keyword_overlap, contextual_relevance, overall_confidence,
                     llm_semantic_score, llm_reasoning_quality, 
                     pattern_indicators, association_reasoning, embedding_reasoning, 
                     llm_reasoning, scoring_method, association_method)
                    VALUES 
                    (:case_id, :guideline_concept_id, :section_type, :semantic_similarity,
                     :keyword_overlap, :contextual_relevance, :overall_confidence,
                     :llm_semantic_score, :llm_reasoning_quality,
                     :pattern_indicators, :association_reasoning, :embedding_reasoning,
                     :llm_reasoning, :scoring_method, :association_method)
                    ON CONFLICT (case_id, guideline_concept_id, section_type) 
                    DO UPDATE SET
                        semantic_similarity = EXCLUDED.semantic_similarity,
                        keyword_overlap = EXCLUDED.keyword_overlap,
                        contextual_relevance = EXCLUDED.contextual_relevance,
                        overall_confidence = EXCLUDED.overall_confidence,
                        llm_semantic_score = EXCLUDED.llm_semantic_score,
                        llm_reasoning_quality = EXCLUDED.llm_reasoning_quality,
                        pattern_indicators = EXCLUDED.pattern_indicators,
                        association_reasoning = EXCLUDED.association_reasoning,
                        embedding_reasoning = EXCLUDED.embedding_reasoning,
                        llm_reasoning = EXCLUDED.llm_reasoning,
                        scoring_method = EXCLUDED.scoring_method,
                        association_method = EXCLUDED.association_method,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                db.session.execute(insert_sql, insert_data)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving association {assoc}: {e}")
                # Rollback the current transaction to recover from the error
                db.session.rollback()
                continue
                
        try:
            db.session.commit()
            logger.info(f"Saved {saved_count} associations to database")
        except Exception as e:
            logger.error(f"Error committing associations: {e}")
            db.session.rollback()
            
        return saved_count
    
    def generate_and_save_associations_for_case(self, case_id: int) -> int:
        """
        Generate and save associations for a specific case
        
        Returns:
            Number of associations created
        """
        associations = self.generate_associations_for_case(case_id)
        return self.save_associations_to_database(associations)
    
    def batch_generate_associations(self, case_ids: Optional[List[int]] = None) -> Dict[str, int]:
        """
        Generate associations for multiple cases
        
        Args:
            case_ids: List of case IDs, or None for all cases
            
        Returns:
            Summary statistics
        """
        if case_ids is None:
            # Get all case IDs (documents and scenarios with metadata)
            from app.models import Document
            doc_ids = [case.id for case in Document.query.filter(Document.doc_metadata.isnot(None)).all()]
            scenario_ids = [case.id for case in Scenario.query.filter(Scenario.scenario_metadata.isnot(None)).all()]
            case_ids = doc_ids + scenario_ids
            
        total_associations = 0
        successful_cases = 0
        failed_cases = 0
        
        for case_id in case_ids:
            try:
                count = self.generate_and_save_associations_for_case(case_id)
                total_associations += count
                successful_cases += 1
                logger.info(f"Generated {count} associations for case {case_id}")
                
            except Exception as e:
                logger.error(f"Failed to generate associations for case {case_id}: {e}")
                failed_cases += 1
                
        return {
            'total_associations': total_associations,
            'successful_cases': successful_cases,
            'failed_cases': failed_cases,
            'total_cases': len(case_ids)
        }