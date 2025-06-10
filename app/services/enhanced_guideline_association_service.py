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
from app.models.document import Document
from app.models.entity_triple import EntityTriple
from app.services.embedding_service import EmbeddingService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

@dataclass
class AssociationScore:
    """Container for association scoring metrics"""
    semantic_similarity: float
    keyword_overlap: float  
    contextual_relevance: float
    overall_confidence: float
    reasoning: str

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
        from app.models.document import Document
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
                for section_data in doc_structure['sections']:
                    section_type = section_data.get('type', '').lower()
                    
                    # Get clean text content
                    content = ''
                    if 'content_text' in section_data:
                        content = section_data['content_text']
                    elif 'content' in section_data:
                        content = section_data['content']
                        
                    if content and section_type:
                        sections[section_type] = content
                        
        # Fallback to legacy section format
        if not sections and 'sections' in metadata:
            legacy_sections = metadata['sections']
            for section_data in legacy_sections:
                section_type = section_data.get('type', '').lower()
                content = section_data.get('content', '')
                if content and section_type:
                    sections[section_type] = content
                    
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
        Calculate multi-dimensional association score
        
        Returns:
            AssociationScore with semantic, keyword, contextual, and overall scores
        """
        
        # Get concept text representation
        concept_text = self._get_concept_text(concept)
        
        # Calculate semantic similarity using embeddings
        semantic_similarity = self._calculate_semantic_similarity(section_content, concept_text)
        
        # Calculate keyword overlap
        keyword_overlap = self._calculate_keyword_overlap(section_content, concept_text)
        
        # Calculate contextual relevance
        contextual_relevance = self._calculate_contextual_relevance(section_content, concept)
        
        # Calculate overall confidence (weighted combination)
        overall_confidence = (
            0.5 * semantic_similarity +     # Primary: embedding similarity
            0.3 * contextual_relevance +    # Secondary: context matching
            0.2 * keyword_overlap           # Tertiary: keyword overlap
        )
        
        # Generate reasoning
        reasoning = self._generate_association_reasoning(
            semantic_similarity, keyword_overlap, contextual_relevance, concept_text
        )
        
        return AssociationScore(
            semantic_similarity=semantic_similarity,
            keyword_overlap=keyword_overlap,
            contextual_relevance=contextual_relevance,
            overall_confidence=overall_confidence,
            reasoning=reasoning
        )
    
    def _get_concept_text(self, concept: EntityTriple) -> str:
        """Extract text representation from concept entity"""
        # Try object_literal first
        if concept.object_literal:
            return concept.object_literal
            
        # Fallback to subject URI (extract readable name)
        if concept.subject:
            # Extract the fragment or last part of URI
            parts = concept.subject.split('/')
            if parts:
                name = parts[-1].replace('_', ' ').replace('-', ' ')
                return name
                
        return ""
    
    def _calculate_semantic_similarity(self, text1: str, text2: str) -> float:
        """Calculate embedding-based semantic similarity"""
        try:
            embedding1 = self.embedding_service.get_text_embedding(text1)
            embedding2 = self.embedding_service.get_text_embedding(text2)
            
            if embedding1 and embedding2:
                return self.embedding_service.calculate_similarity(embedding1, embedding2)
                
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
    
    def _generate_association_reasoning(
        self, 
        semantic: float, 
        keyword: float, 
        contextual: float, 
        concept_text: str
    ) -> str:
        """Generate human-readable reasoning for the association"""
        
        components = []
        
        if semantic >= 0.7:
            components.append(f"strong semantic similarity ({semantic:.2f})")
        elif semantic >= 0.4:
            components.append(f"moderate semantic similarity ({semantic:.2f})")
            
        if keyword >= 0.3:
            components.append(f"keyword overlap ({keyword:.2f})")
            
        if contextual >= 0.3:
            components.append(f"contextual relevance ({contextual:.2f})")
            
        if components:
            return f"Association based on {', '.join(components)} with concept '{concept_text}'"
        else:
            return f"Low-confidence association with concept '{concept_text}'"
    
    def _generate_pattern_indicators(
        self, 
        section_type: str, 
        section_content: str, 
        concept: EntityTriple, 
        score: AssociationScore
    ) -> Dict[str, Any]:
        """Generate pattern indicators for outcome prediction"""
        
        indicators = {
            'section_type': section_type,
            'confidence_level': score.overall_confidence,
            'pattern_strength': score.semantic_similarity,
            'concept_uri': concept.subject,
            'timestamp': datetime.utcnow().isoformat()
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
                # Prepare data for insert
                insert_data = {
                    'case_id': assoc.case_id,
                    'guideline_concept_id': assoc.guideline_concept_id,
                    'section_type': assoc.section_type,
                    'semantic_similarity': assoc.score.semantic_similarity,
                    'keyword_overlap': assoc.score.keyword_overlap,
                    'contextual_relevance': assoc.score.contextual_relevance,
                    'overall_confidence': assoc.score.overall_confidence,
                    'pattern_indicators': json.dumps(assoc.pattern_indicators),
                    'association_reasoning': assoc.score.reasoning,
                    'association_method': assoc.association_method
                }
                
                # Insert with ON CONFLICT handling
                insert_sql = text("""
                    INSERT INTO case_guideline_associations 
                    (case_id, guideline_concept_id, section_type, semantic_similarity, 
                     keyword_overlap, contextual_relevance, overall_confidence, 
                     pattern_indicators, association_reasoning, association_method)
                    VALUES 
                    (:case_id, :guideline_concept_id, :section_type, :semantic_similarity,
                     :keyword_overlap, :contextual_relevance, :overall_confidence,
                     :pattern_indicators, :association_reasoning, :association_method)
                    ON CONFLICT (case_id, guideline_concept_id, section_type) 
                    DO UPDATE SET
                        semantic_similarity = EXCLUDED.semantic_similarity,
                        keyword_overlap = EXCLUDED.keyword_overlap,
                        contextual_relevance = EXCLUDED.contextual_relevance,
                        overall_confidence = EXCLUDED.overall_confidence,
                        pattern_indicators = EXCLUDED.pattern_indicators,
                        association_reasoning = EXCLUDED.association_reasoning,
                        association_method = EXCLUDED.association_method,
                        updated_at = CURRENT_TIMESTAMP
                """)
                
                db.session.execute(insert_sql, insert_data)
                saved_count += 1
                
            except Exception as e:
                logger.error(f"Error saving association {assoc}: {e}")
                continue
                
        db.session.commit()
        logger.info(f"Saved {saved_count} associations to database")
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
            from app.models.document import Document
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