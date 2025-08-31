"""
Simple Annotation Service - Reliable keyword-based annotation without JSON parsing.
"""
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.services.ontserve_annotation_service import OntServeAnnotationService

logger = logging.getLogger(__name__)

class SimpleAnnotationService:
    """
    Simple, reliable annotation service using keyword matching instead of LLM JSON parsing.
    """
    
    def __init__(self):
        self.ontserve_service = OntServeAnnotationService()
        
        # Configuration
        self.min_confidence_threshold = 0.6
    
    def annotate_document(self, document_type: str, document_id: int, 
                         world_id: int, force_refresh: bool = False) -> List[DocumentConceptAnnotation]:
        """
        Annotate a document using simple keyword matching.
        
        Args:
            document_type: 'guideline' or 'case'
            document_id: ID of the document
            world_id: ID of the world
            force_refresh: If True, re-annotate even if annotations exist
            
        Returns:
            List of created annotations
        """
        try:
            logger.info(f"Starting simple annotation of {document_type} {document_id}")
            
            # Check if annotations already exist
            if not force_refresh:
                existing = DocumentConceptAnnotation.get_annotations_for_document(
                    document_type, document_id
                )
                if existing:
                    logger.info(f"Annotations already exist for {document_type} {document_id}")
                    return existing
            
            # Get document content
            if document_type == 'guideline':
                from app.models.guideline import Guideline
                document = Guideline.query.get(document_id)
            else:
                from app.models import Document
                document = Document.query.get(document_id)
            
            if not document:
                logger.error(f"Document not found: {document_type} {document_id}")
                return []
            
            # Get clean text
            clean_content = self._extract_clean_text(document)
            if len(clean_content) < 50:
                logger.warning(f"Document content too short for annotation: {len(clean_content)} chars")
                return []
            
            # Get ontology concepts
            ontology_mapping = self.ontserve_service.get_world_ontology_mapping(world_id)
            ontology_names = list(ontology_mapping.values())
            all_concepts = self.ontserve_service.get_ontology_concepts(ontology_names)
            
            # Perform keyword-based annotation
            annotations = []
            all_annotations = []
            
            # Process each ontology
            for ontology_name, concepts in all_concepts.items():
                if not concepts:
                    continue
                
                logger.info(f"Processing {len(concepts)} concepts from {ontology_name}")
                
                for concept in concepts:
                    # Find matches for this concept
                    matches = self._find_concept_matches(clean_content, concept)
                    all_annotations.extend(matches)
            
            # Remove overlaps and store in database
            final_annotations = self._remove_overlaps_and_store(
                all_annotations, document_type, document_id, world_id
            )
            
            logger.info(f"Created {len(final_annotations)} simple annotations")
            return final_annotations
            
        except Exception as e:
            logger.exception(f"Error in simple annotation: {e}")
            return []
    
    def _extract_clean_text(self, document) -> str:
        """Extract clean text from document."""
        if hasattr(document, 'content') and document.content:
            # Remove HTML tags
            clean_text = re.sub(r'<[^>]+>', ' ', document.content)
            # Normalize whitespace
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text
        return ""
    
    def _find_concept_matches(self, content: str, concept: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find matches for a concept using keyword matching."""
        matches = []
        content_lower = content.lower()
        
        # Get concept keywords
        label = concept.get('label', '').lower()
        definition = concept.get('definition', '').lower()
        
        if not label:
            return matches
        
        # Simple keyword matching strategies
        keywords_to_try = []
        
        # 1. Exact label match
        keywords_to_try.append((label, 1.0))
        
        # 2. Label words (if multi-word)
        if ' ' in label:
            words = [w.strip() for w in label.split() if len(w.strip()) > 2]
            for word in words:
                keywords_to_try.append((word, 0.8))
        
        # 3. Key words from definition (first few important words)
        if definition:
            def_words = re.findall(r'\b\w{4,}\b', definition)[:5]  # 4+ letter words, first 5
            for word in def_words:
                if word not in ['that', 'this', 'with', 'from', 'they', 'have', 'will', 'been', 'were']:
                    keywords_to_try.append((word.lower(), 0.6))
        
        # Find matches in content
        for keyword, base_confidence in keywords_to_try:
            if len(keyword) < 3:  # Skip very short words
                continue
                
            # Find all occurrences
            positions = []
            start = 0
            while True:
                pos = content_lower.find(keyword, start)
                if pos == -1:
                    break
                    
                # Check if it's a whole word match
                if self._is_whole_word_match(content, keyword, pos):
                    positions.append(pos)
                    
                start = pos + 1
            
            # Create annotations for matches
            for pos in positions:
                # Extract the actual case-sensitive text
                actual_text = content[pos:pos + len(keyword)]
                
                match = {
                    'text_segment': actual_text,
                    'start_offset': pos,
                    'end_offset': pos + len(keyword),
                    'concept_uri': concept['uri'],
                    'concept_label': concept['label'],
                    'concept_definition': concept.get('definition', ''),
                    'concept_type': concept.get('type', 'Unknown'),
                    'ontology_name': concept['ontology'],
                    'confidence': base_confidence,
                    'reasoning': f"Keyword match: '{actual_text}' matches concept '{concept['label']}'"
                }
                matches.append(match)
                
                # Only keep the best match per concept to avoid duplication
                if matches:
                    break
        
        return matches
    
    def _is_whole_word_match(self, content: str, keyword: str, position: int) -> bool:
        """Check if the match is a whole word (not part of another word)."""
        # Check character before
        if position > 0:
            prev_char = content[position - 1]
            if prev_char.isalnum():
                return False
        
        # Check character after
        end_pos = position + len(keyword)
        if end_pos < len(content):
            next_char = content[end_pos]
            if next_char.isalnum():
                return False
        
        return True
    
    def _remove_overlaps_and_store(self, all_matches: List[Dict[str, Any]], 
                                  document_type: str, document_id: int, world_id: int) -> List[DocumentConceptAnnotation]:
        """Remove overlaps and store in database."""
        from app.models import db
        
        # Sort by confidence descending
        all_matches.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Remove overlaps
        final_matches = []
        used_ranges = []
        
        for match in all_matches:
            start = match['start_offset']
            end = match['end_offset']
            
            # Check if this overlaps with any existing range
            overlaps = False
            for used_start, used_end in used_ranges:
                if start < used_end and end > used_start:
                    overlaps = True
                    break
            
            if not overlaps and match['confidence'] >= self.min_confidence_threshold:
                final_matches.append(match)
                used_ranges.append((start, end))
        
        # Store in database
        annotations = []
        
        try:
            # Mark existing annotations as superseded
            existing = DocumentConceptAnnotation.get_annotations_for_document(
                document_type, document_id
            )
            for existing_ann in existing:
                existing_ann.is_current = False
            
            # Create new annotations
            for match in final_matches:
                annotation = DocumentConceptAnnotation(
                    document_type=document_type,
                    document_id=document_id,
                    world_id=world_id,
                    text_segment=match['text_segment'],
                    start_offset=match['start_offset'],
                    end_offset=match['end_offset'],
                    ontology_name=match['ontology_name'],
                    concept_uri=match['concept_uri'],
                    concept_label=match['concept_label'],
                    concept_definition=match['concept_definition'],
                    concept_type=match['concept_type'],
                    confidence=match['confidence'],
                    llm_model='keyword_matching',
                    llm_reasoning=match['reasoning'],
                    validation_status='pending'
                )
                
                db.session.add(annotation)
                annotations.append(annotation)
            
            db.session.commit()
            logger.info(f"Stored {len(annotations)} simple annotations")
            
        except Exception as e:
            logger.error(f"Error storing annotations: {e}")
            db.session.rollback()
            annotations = []
        
        return annotations
