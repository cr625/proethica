"""
Document Annotation Pipeline - Core service for annotating documents with ontology concepts.
"""
import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from app.models.guideline import Guideline
from app.models import Document
from app.models.document_concept_annotation import DocumentConceptAnnotation
from models import ModelConfig
from app.services.ontserve_annotation_service import OntServeAnnotationService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

@dataclass
class AnnotationCandidate:
    """Data class for annotation candidates."""
    text_segment: str
    start_offset: int
    end_offset: int
    concept_uri: str
    concept_label: str
    concept_definition: str
    concept_type: str
    ontology_name: str
    ontology_version: str
    confidence: float
    reasoning: str

class DocumentAnnotationPipeline:
    """
    Main service for annotating documents with ontology concepts using LLM analysis.
    """
    
    def __init__(self):
        self.ontserve_service = OntServeAnnotationService()
        self.llm_service = LLMService()
        
        # Configuration
        self.min_confidence_threshold = 0.4
        self.max_annotations_per_pass = 50
        self.overlap_threshold = 5  # Characters
        
        # LLM model preference
        self.preferred_model = ModelConfig.get_claude_model("default")
    
    def annotate_document(self, document_type: str, document_id: int, 
                         world_id: int, force_refresh: bool = False) -> List[DocumentConceptAnnotation]:
        """
        Main annotation workflow - annotate a document with ontology concepts.
        
        Args:
            document_type: 'guideline' or 'case'
            document_id: ID of the document
            world_id: ID of the world (for ontology mapping)
            force_refresh: If True, re-annotate even if annotations exist
            
        Returns:
            List of created annotations
        """
        try:
            logger.info(f"Starting annotation of {document_type} {document_id} for world {world_id}")
            
            # Check if annotations already exist
            if not force_refresh:
                existing = DocumentConceptAnnotation.get_annotations_for_document(
                    document_type, document_id
                )
                if existing:
                    logger.info(f"Annotations already exist for {document_type} {document_id}")
                    return existing
            
            # Get document content
            document = self._get_document(document_type, document_id)
            if not document:
                logger.error(f"Document not found: {document_type} {document_id}")
                return []
            
            # Get ontology mapping for this world
            ontology_mapping = self.ontserve_service.get_world_ontology_mapping(world_id)
            logger.info(f"Using ontology mapping: {ontology_mapping}")
            
            # Fetch all relevant ontology concepts
            ontology_names = list(ontology_mapping.values())
            all_concepts = self.ontserve_service.get_ontology_concepts(ontology_names)
            
            # Get clean text content for analysis
            clean_content = self._extract_clean_text(document)
            
            # Perform multi-pass annotation
            all_candidates = []
            
            # Pass 1: Core concepts (highest priority)
            if 'core' in ontology_mapping:
                core_ontology = ontology_mapping['core']
                if core_ontology in all_concepts:
                    logger.info(f"Pass 1: Annotating with core concepts from {core_ontology}")
                    core_candidates = self._annotate_with_ontology(
                        clean_content, all_concepts[core_ontology], 'core', []
                    )
                    all_candidates.extend(core_candidates)
            
            # Pass 2: Intermediate concepts
            if 'intermediate' in ontology_mapping:
                intermediate_ontology = ontology_mapping['intermediate']
                if intermediate_ontology in all_concepts:
                    logger.info(f"Pass 2: Annotating with intermediate concepts from {intermediate_ontology}")
                    intermediate_candidates = self._annotate_with_ontology(
                        clean_content, all_concepts[intermediate_ontology], 'intermediate', all_candidates
                    )
                    all_candidates.extend(intermediate_candidates)
            
            # Pass 3: Domain-specific concepts
            if 'domain' in ontology_mapping:
                domain_ontology = ontology_mapping['domain']
                if domain_ontology in all_concepts:
                    logger.info(f"Pass 3: Annotating with domain concepts from {domain_ontology}")
                    domain_candidates = self._annotate_with_ontology(
                        clean_content, all_concepts[domain_ontology], 'domain', all_candidates
                    )
                    all_candidates.extend(domain_candidates)
            
            # Filter and validate candidates
            validated_candidates = self._validate_candidates(all_candidates, clean_content)
            
            # Store annotations in database
            annotations = self._store_annotations(
                document_type, document_id, world_id, validated_candidates
            )
            
            logger.info(f"Created {len(annotations)} annotations for {document_type} {document_id}")
            return annotations
            
        except Exception as e:
            logger.exception(f"Error annotating document {document_type} {document_id}: {e}")
            return []
    
    def _get_document(self, document_type: str, document_id: int):
        """Get the document object."""
        if document_type == 'guideline':
            return Guideline.query.get(document_id)
        elif document_type == 'case':
            return Document.query.get(document_id)
        return None
    
    def _extract_clean_text(self, document) -> str:
        """Extract clean text content from document."""
        if hasattr(document, 'content') and document.content:
            # Remove HTML tags
            clean_text = re.sub(r'<[^>]+>', ' ', document.content)
            # Normalize whitespace
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text
        return ""
    
    def _annotate_with_ontology(self, content: str, ontology_concepts: List[Dict], 
                               level: str, existing_annotations: List[AnnotationCandidate]) -> List[AnnotationCandidate]:
        """
        Use LLM to identify concept matches in text.
        
        Args:
            content: Document content
            ontology_concepts: List of concepts from the ontology
            level: Ontology level ('core', 'intermediate', 'domain')
            existing_annotations: Already found annotations to avoid overlap
            
        Returns:
            List of annotation candidates
        """
        try:
            # Limit concepts to avoid overwhelming the LLM
            concepts_for_prompt = ontology_concepts[:self.max_annotations_per_pass]
            
            # Build concept descriptions for LLM
            concept_descriptions = []
            for concept in concepts_for_prompt:
                desc = {
                    'uri': concept['uri'],
                    'label': concept['label'],
                    'definition': concept.get('definition', ''),
                    'type': concept['type']
                }
                concept_descriptions.append(desc)
            
            # Build existing annotations summary to avoid overlap
            existing_segments = [ann.text_segment for ann in existing_annotations]
            
            # Create LLM prompt
            prompt = self._build_annotation_prompt(
                content, concept_descriptions, level, existing_segments
            )
            
            # Call LLM
            logger.debug(f"Calling LLM for {level} level annotation")
            llm_result = self.llm_service.generate_response(prompt)
            response = llm_result.get('analysis', '') if isinstance(llm_result, dict) else str(llm_result)
            
            # Parse LLM response
            candidates = self._parse_llm_response(response, ontology_concepts, level)
            
            logger.info(f"Found {len(candidates)} candidates at {level} level")
            return candidates
            
        except Exception as e:
            logger.error(f"Error in {level} level annotation: {e}")
            return []
    
    def _build_annotation_prompt(self, content: str, concept_descriptions: List[Dict], 
                               level: str, existing_segments: List[str]) -> str:
        """Build the LLM prompt for concept annotation."""
        
        # Truncate content if too long
        max_content_length = 8000  # Adjust based on model limits
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [truncated]"
        
        prompt = f"""You are an expert in professional ethics and ontology annotation. Your task is to identify specific text segments in the document that correspond to the given ontology concepts at the {level} level.

DOCUMENT CONTENT:
{content}

AVAILABLE CONCEPTS ({level} level):
{json.dumps(concept_descriptions, indent=2)}

ALREADY ANNOTATED TEXT (avoid these segments):
{json.dumps(existing_segments, indent=2) if existing_segments else "None"}

INSTRUCTIONS:
1. Identify text segments (words or short phrases) that semantically match the given concepts
2. Focus on {level} level concepts - {"formal tuple components" if level == "core" else "specific ethical concepts" if level == "intermediate" else "domain-specific terms"}
3. Extract the EXACT text from the document (not paraphrased)
4. Avoid overlapping with already annotated segments
5. Only include matches with high confidence (>0.6)
6. Prefer precise, specific matches over general ones

For each match, provide:
- text_segment: The exact text from the document
- concept_uri: The URI of the matching concept
- concept_label: The label of the concept
- confidence: Your confidence score (0.0-1.0)
- reasoning: Brief explanation of why this text matches the concept

Return your response as a JSON array of matches:

[
    {{
        "text_segment": "exact text from document",
        "concept_uri": "http://...",
        "concept_label": "concept name",
        "confidence": 0.85,
        "reasoning": "brief explanation"
    }}
]

Focus on quality over quantity. Only include clear, unambiguous matches."""

        return prompt
    
    def _parse_llm_response(self, response: str, ontology_concepts: List[Dict], 
                          level: str) -> List[AnnotationCandidate]:
        """Parse LLM response into annotation candidates."""
        candidates = []
        
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if not json_match:
                logger.error("No JSON array found in LLM response")
                return candidates
            
            json_str = json_match.group(0)
            parsed_response = json.loads(json_str)
            
            # Create concept lookup for additional info
            concept_lookup = {c['uri']: c for c in ontology_concepts}
            
            for item in parsed_response:
                try:
                    concept_uri = item.get('concept_uri')
                    if concept_uri not in concept_lookup:
                        logger.warning(f"Concept URI not found: {concept_uri}")
                        continue
                    
                    concept = concept_lookup[concept_uri]
                    
                    # Create annotation candidate
                    candidate = AnnotationCandidate(
                        text_segment=item.get('text_segment', ''),
                        start_offset=0,  # Will be calculated later
                        end_offset=0,
                        concept_uri=concept_uri,
                        concept_label=item.get('concept_label', concept['label']),
                        concept_definition=concept.get('definition', ''),
                        concept_type=concept['type'],
                        ontology_name=concept['ontology'],
                        ontology_version=None,  # Will be set later
                        confidence=float(item.get('confidence', 0.0)),
                        reasoning=item.get('reasoning', '')
                    )
                    
                    # Basic validation
                    if candidate.confidence >= self.min_confidence_threshold and candidate.text_segment:
                        candidates.append(candidate)
                    
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning(f"Error parsing LLM response item: {e}")
                    continue
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
        
        return candidates
    
    def _validate_candidates(self, candidates: List[AnnotationCandidate], 
                           content: str) -> List[AnnotationCandidate]:
        """Validate and refine annotation candidates."""
        validated = []
        
        for candidate in candidates:
            try:
                # Find text segment position in content
                positions = self._find_text_positions(candidate.text_segment, content)
                
                if not positions:
                    logger.warning(f"Text segment not found: {candidate.text_segment}")
                    continue
                
                # Use the first occurrence for now
                start_pos, end_pos = positions[0]
                candidate.start_offset = start_pos
                candidate.end_offset = end_pos
                
                # Additional validation using OntServe service
                validation_result = self.ontserve_service.validate_annotation_candidate(
                    candidate.text_segment,
                    candidate.concept_uri,
                    candidate.ontology_name
                )
                
                if validation_result['valid']:
                    # Update confidence with validation result
                    candidate.confidence = min(candidate.confidence, validation_result['confidence'])
                    validated.append(candidate)
                else:
                    logger.debug(f"Validation failed for {candidate.text_segment}: {validation_result['reasoning']}")
                
            except Exception as e:
                logger.warning(f"Error validating candidate {candidate.text_segment}: {e}")
        
        # Remove overlapping annotations (keep higher confidence ones)
        validated = self._remove_overlaps(validated)
        
        return validated
    
    def _find_text_positions(self, text: str, content: str) -> List[Tuple[int, int]]:
        """Find all positions of text in content."""
        positions = []
        start = 0
        
        while True:
            pos = content.find(text, start)
            if pos == -1:
                break
            positions.append((pos, pos + len(text)))
            start = pos + 1
        
        return positions
    
    def _remove_overlaps(self, candidates: List[AnnotationCandidate]) -> List[AnnotationCandidate]:
        """Remove overlapping annotations, keeping higher confidence ones."""
        # Sort by confidence descending
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        result = []
        used_ranges = []
        
        for candidate in candidates:
            # Check if this candidate overlaps with any already used range
            overlaps = False
            for start, end in used_ranges:
                if (candidate.start_offset < end and candidate.end_offset > start):
                    overlaps = True
                    break
            
            if not overlaps:
                result.append(candidate)
                used_ranges.append((candidate.start_offset, candidate.end_offset))
        
        return result
    
    def _store_annotations(self, document_type: str, document_id: int, world_id: int,
                          candidates: List[AnnotationCandidate]) -> List[DocumentConceptAnnotation]:
        """Store validated candidates as annotations in the database."""
        from app.models import db
        
        annotations = []
        
        try:
            # First, mark any existing annotations as superseded
            existing_annotations = DocumentConceptAnnotation.get_annotations_for_document(
                document_type, document_id
            )
            for existing in existing_annotations:
                existing.is_current = False
            
            # Create new annotations
            for candidate in candidates:
                annotation = DocumentConceptAnnotation(
                    document_type=document_type,
                    document_id=document_id,
                    world_id=world_id,
                    text_segment=candidate.text_segment,
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                    ontology_name=candidate.ontology_name,
                    ontology_version=candidate.ontology_version,
                    concept_uri=candidate.concept_uri,
                    concept_label=candidate.concept_label,
                    concept_definition=candidate.concept_definition,
                    concept_type=candidate.concept_type,
                    confidence=candidate.confidence,
                    llm_model=self.preferred_model,
                    llm_reasoning=candidate.reasoning,
                    validation_status='pending'  # Default to pending
                )
                
                db.session.add(annotation)
                annotations.append(annotation)
            
            db.session.commit()
            logger.info(f"Stored {len(annotations)} annotations in database")
            
        except Exception as e:
            logger.error(f"Error storing annotations: {e}")
            db.session.rollback()
            annotations = []
        
        return annotations
    
    def get_annotation_summary(self, document_type: str, document_id: int) -> Dict[str, Any]:
        """Get a summary of annotations for a document."""
        annotations = DocumentConceptAnnotation.get_annotations_for_document(
            document_type, document_id
        )
        
        if not annotations:
            return {
                'total_annotations': 0,
                'by_ontology': {},
                'by_confidence': {'high': 0, 'medium': 0, 'low': 0},
                'by_status': {'pending': 0, 'approved': 0, 'rejected': 0}
            }
        
        # Group by ontology
        by_ontology = {}
        for ann in annotations:
            if ann.ontology_name not in by_ontology:
                by_ontology[ann.ontology_name] = 0
            by_ontology[ann.ontology_name] += 1
        
        # Group by confidence level
        by_confidence = {'high': 0, 'medium': 0, 'low': 0}
        for ann in annotations:
            level = ann.get_confidence_level()
            if level == 'high':
                by_confidence['high'] += 1
            elif level == 'medium':
                by_confidence['medium'] += 1
            else:
                by_confidence['low'] += 1
        
        # Group by validation status
        by_status = {'pending': 0, 'approved': 0, 'rejected': 0}
        for ann in annotations:
            by_status[ann.validation_status] += 1
        
        return {
            'total_annotations': len(annotations),
            'by_ontology': by_ontology,
            'by_confidence': by_confidence,
            'by_status': by_status,
            'created_at': max(ann.created_at for ann in annotations).isoformat()
        }
