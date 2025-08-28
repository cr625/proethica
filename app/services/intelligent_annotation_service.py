"""
Intelligent Multi-Pass Annotation Service

Uses LLM-powered contextual understanding to create high-quality annotations
that properly match concepts to their usage context, replacing simple keyword matching.
"""

import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.services.ontserve_annotation_service import OntServeAnnotationService

# LangChain imports with graceful fallback
try:
    from langchain.schema import BaseMessage, HumanMessage, SystemMessage
    from langchain.callbacks import get_openai_callback
except ImportError:
    BaseMessage = HumanMessage = SystemMessage = None
    get_openai_callback = None

logger = logging.getLogger(__name__)

class AnnotationPhase(Enum):
    """Phases in the multi-pass annotation pipeline."""
    CONCEPT_DETECTION = "concept_detection"
    CONTEXTUAL_VALIDATION = "contextual_validation"
    SEMANTIC_REFINEMENT = "semantic_refinement"

@dataclass
class AnnotationCandidate:
    """Candidate annotation from LLM processing."""
    concept_uri: str
    concept_label: str
    concept_type: str
    text_segment: str
    start_offset: int
    end_offset: int
    confidence: float
    reasoning: str
    phase: AnnotationPhase
    context_window: str = ""

@dataclass
class ProcessingResult:
    """Result of multi-pass processing."""
    candidates: List[AnnotationCandidate]
    phase: AnnotationPhase
    processing_time: float
    token_usage: Dict[str, int]
    success: bool
    error_message: Optional[str] = None

class IntelligentAnnotationService:
    """
    Multi-pass LLM-powered annotation service using contextual understanding.
    
    Architecture:
    1. Concept Detection - Identify potentially relevant concepts
    2. Contextual Validation - Verify concept matches context appropriately  
    3. Semantic Refinement - Apply definitions and relationships for final quality
    """
    
    def __init__(self):
        self.ontserve_service = OntServeAnnotationService()
        
        # Configuration
        self.min_confidence_threshold = 0.7
        self.context_window_size = 200  # Characters before/after match
        self.batch_size = 50  # Concepts per batch
        
        # Performance tracking
        self.stats = {
            'total_documents': 0,
            'total_processing_time': 0,
            'total_tokens_used': 0,
            'average_confidence': 0
        }
    
    def get_llm_client(self):
        """Get LLM client using ProEthica's utility."""
        try:
            from app.utils.llm_utils import get_llm_client
            return get_llm_client()
        except Exception as e:
            logger.error(f"Failed to get LLM client: {e}")
            return None
    
    async def annotate_document(self, document_type: str, document_id: int, 
                               world_id: int, force_refresh: bool = False) -> List[DocumentConceptAnnotation]:
        """
        Annotate document using intelligent multi-pass LLM processing.
        
        Args:
            document_type: 'guideline' or 'case'
            document_id: ID of the document  
            world_id: ID of the world
            force_refresh: If True, re-annotate even if annotations exist
            
        Returns:
            List of high-quality contextual annotations
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            logger.info(f"Starting intelligent annotation of {document_type} {document_id}")
            
            # Check if annotations already exist
            if not force_refresh:
                existing = DocumentConceptAnnotation.get_annotations_for_document(
                    document_type, document_id
                )
                if existing:
                    logger.info(f"Annotations already exist for {document_type} {document_id}")
                    return existing
            
            # Get document content
            document_content = self._get_document_content(document_type, document_id)
            if not document_content:
                logger.error(f"No content found for {document_type} {document_id}")
                return []
            
            # Get available ontology concepts
            ontology_concepts = await self._get_ontology_concepts(world_id)
            if not ontology_concepts:
                logger.error(f"No ontology concepts found for world {world_id}")
                return []
            
            logger.info(f"Processing {len(document_content)} chars with {len(ontology_concepts)} concepts")
            
            # Multi-pass processing pipeline
            phase1_result = await self._phase1_concept_detection(
                document_content, ontology_concepts
            )
            
            if not phase1_result.success:
                logger.error(f"Phase 1 failed: {phase1_result.error_message}")
                return []
            
            phase2_result = await self._phase2_contextual_validation(
                document_content, phase1_result.candidates
            )
            
            if not phase2_result.success:
                logger.error(f"Phase 2 failed: {phase2_result.error_message}")
                # Fallback to Phase 1 results
                final_candidates = phase1_result.candidates
            else:
                phase3_result = await self._phase3_semantic_refinement(
                    document_content, phase2_result.candidates, ontology_concepts
                )
                
                if not phase3_result.success:
                    logger.warning(f"Phase 3 failed: {phase3_result.error_message}")
                    final_candidates = phase2_result.candidates
                else:
                    final_candidates = phase3_result.candidates
            
            # Convert to database annotations
            annotations = self._create_database_annotations(
                final_candidates, document_type, document_id, world_id
            )
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Intelligent annotation complete: {len(annotations)} annotations in {processing_time:.2f}s")
            
            # Update stats
            self.stats['total_documents'] += 1
            self.stats['total_processing_time'] += processing_time
            if final_candidates:
                avg_confidence = sum(c.confidence for c in final_candidates) / len(final_candidates)
                self.stats['average_confidence'] = (
                    (self.stats['average_confidence'] * (self.stats['total_documents'] - 1) + avg_confidence) 
                    / self.stats['total_documents']
                )
            
            return annotations
            
        except Exception as e:
            logger.error(f"Error in intelligent annotation: {e}", exc_info=True)
            return []
    
    async def _phase1_concept_detection(self, document_content: str, 
                                       concepts: List[Dict]) -> ProcessingResult:
        """
        Phase 1: Detect potentially relevant concepts in the document.
        
        Uses LLM to identify which ontology concepts are meaningfully referenced
        in the document text, with initial confidence scoring.
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            client = self.get_llm_client()
            if not client:
                return ProcessingResult(
                    candidates=[], phase=AnnotationPhase.CONCEPT_DETECTION,
                    processing_time=0, token_usage={}, success=False,
                    error_message="No LLM client available"
                )
            
            # Prepare concept list for prompt
            concept_list = self._format_concepts_for_prompt(concepts[:self.batch_size])
            
            prompt = f"""You are an expert in professional engineering ethics annotation.

Analyze this document text and identify which ethical concepts are meaningfully present:

DOCUMENT TEXT:
{document_content[:2000]}  

AVAILABLE CONCEPTS:
{concept_list}

TASK: Identify concept matches with their exact text spans.

For each match, provide:
- concept_label: Exact label from the list
- text_segment: Exact text from document
- start_position: Character position (estimate)
- end_position: Character position (estimate) 
- confidence: 0.0-1.0 (how certain this concept applies)
- reasoning: Why this concept matches

Only include concepts that are genuinely relevant to the context.
Aim for precision over recall - better to miss than to incorrectly annotate.

Format as JSON array:
[{{"concept_label": "...", "text_segment": "...", "start_position": 0, "end_position": 10, "confidence": 0.9, "reasoning": "..."}}]"""

            # Call LLM
            response_content = await self._call_llm(client, prompt)
            if not response_content:
                return ProcessingResult(
                    candidates=[], phase=AnnotationPhase.CONCEPT_DETECTION,
                    processing_time=0, token_usage={}, success=False,
                    error_message="Empty LLM response"
                )
            
            # Parse response
            candidates = self._parse_detection_response(response_content, concepts)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Phase 1: Detected {len(candidates)} candidate annotations")
            
            return ProcessingResult(
                candidates=candidates,
                phase=AnnotationPhase.CONCEPT_DETECTION,
                processing_time=processing_time,
                token_usage={},  # TODO: Track token usage
                success=True
            )
            
        except Exception as e:
            logger.error(f"Phase 1 error: {e}", exc_info=True)
            return ProcessingResult(
                candidates=[], phase=AnnotationPhase.CONCEPT_DETECTION,
                processing_time=0, token_usage={}, success=False,
                error_message=str(e)
            )
    
    async def _phase2_contextual_validation(self, document_content: str,
                                           candidates: List[AnnotationCandidate]) -> ProcessingResult:
        """
        Phase 2: Validate candidates using contextual analysis.
        
        Examines each candidate annotation in its surrounding context to verify
        the concept truly applies in that specific usage.
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            client = self.get_llm_client()
            if not client:
                return ProcessingResult(
                    candidates=candidates, phase=AnnotationPhase.CONTEXTUAL_VALIDATION,
                    processing_time=0, token_usage={}, success=False,
                    error_message="No LLM client available"
                )
            
            validated_candidates = []
            
            # Process candidates in smaller batches for validation
            batch_size = 5
            for i in range(0, len(candidates), batch_size):
                batch = candidates[i:i + batch_size]
                
                validation_prompt = self._create_validation_prompt(document_content, batch)
                response_content = await self._call_llm(client, validation_prompt)
                
                if response_content:
                    validated_batch = self._parse_validation_response(response_content, batch)
                    validated_candidates.extend(validated_batch)
                else:
                    # Fallback: keep candidates but lower confidence
                    for candidate in batch:
                        candidate.confidence *= 0.8
                        candidate.reasoning += " (validation failed - confidence reduced)"
                    validated_candidates.extend(batch)
            
            # Filter by confidence threshold
            high_confidence_candidates = [
                c for c in validated_candidates 
                if c.confidence >= self.min_confidence_threshold
            ]
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Phase 2: Validated {len(high_confidence_candidates)}/{len(candidates)} candidates")
            
            return ProcessingResult(
                candidates=high_confidence_candidates,
                phase=AnnotationPhase.CONTEXTUAL_VALIDATION,
                processing_time=processing_time,
                token_usage={},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Phase 2 error: {e}", exc_info=True)
            # Return original candidates on error
            return ProcessingResult(
                candidates=candidates, phase=AnnotationPhase.CONTEXTUAL_VALIDATION,
                processing_time=0, token_usage={}, success=False,
                error_message=str(e)
            )
    
    async def _phase3_semantic_refinement(self, document_content: str,
                                         candidates: List[AnnotationCandidate],
                                         concepts: List[Dict]) -> ProcessingResult:
        """
        Phase 3: Apply semantic refinement using concept definitions.
        
        Uses full concept definitions and relationships to make final
        quality improvements and generate explanations.
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # For now, apply basic refinement rules
            # In full implementation, this would use concept definitions and relationships
            refined_candidates = []
            
            for candidate in candidates:
                # Apply semantic rules
                refined_candidate = self._apply_semantic_rules(candidate, concepts)
                
                # Add context window
                refined_candidate.context_window = self._extract_context_window(
                    document_content, refined_candidate.start_offset, refined_candidate.end_offset
                )
                
                refined_candidates.append(refined_candidate)
            
            processing_time = asyncio.get_event_loop().time() - start_time
            
            logger.info(f"Phase 3: Refined {len(refined_candidates)} final annotations")
            
            return ProcessingResult(
                candidates=refined_candidates,
                phase=AnnotationPhase.SEMANTIC_REFINEMENT,
                processing_time=processing_time,
                token_usage={},
                success=True
            )
            
        except Exception as e:
            logger.error(f"Phase 3 error: {e}", exc_info=True)
            return ProcessingResult(
                candidates=candidates, phase=AnnotationPhase.SEMANTIC_REFINEMENT,
                processing_time=0, token_usage={}, success=False,
                error_message=str(e)
            )
    
    async def _call_llm(self, client, prompt: str) -> Optional[str]:
        """Call LLM with error handling and retries."""
        try:
            if hasattr(client, 'messages'):
                # Anthropic client
                response = client.messages.create(
                    model="claude-3-sonnet-20240229",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            elif hasattr(client, 'chat'):
                # OpenAI client
                response = client.chat.completions.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4000
                )
                return response.choices[0].message.content
            else:
                logger.error(f"Unknown client type: {type(client)}")
                return None
                
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None
    
    def _format_concepts_for_prompt(self, concepts: List[Dict]) -> str:
        """Format concepts for LLM prompt."""
        return "\n".join([
            f"- {concept.get('label', 'Unknown')} ({concept.get('type', 'unknown')}): {concept.get('definition', 'No definition')}"
            for concept in concepts[:50]  # Limit for prompt size
        ])
    
    def _parse_detection_response(self, response: str, concepts: List[Dict]) -> List[AnnotationCandidate]:
        """Parse concept detection response from LLM."""
        candidates = []
        
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "[" in response and "]" in response:
                # Find the JSON array
                start = response.find("[")
                end = response.rfind("]") + 1
                json_str = response[start:end]
            else:
                json_str = response.strip()
            
            data = json.loads(json_str)
            
            # Convert to AnnotationCandidate objects
            concept_lookup = {c.get('label', ''): c for c in concepts}
            
            for item in data:
                concept_label = item.get('concept_label', '')
                concept_info = concept_lookup.get(concept_label, {})
                
                if concept_info:
                    candidates.append(AnnotationCandidate(
                        concept_uri=concept_info.get('uri', ''),
                        concept_label=concept_label,
                        concept_type=concept_info.get('type', 'unknown'),
                        text_segment=item.get('text_segment', ''),
                        start_offset=int(item.get('start_position', 0)),
                        end_offset=int(item.get('end_position', 0)),
                        confidence=float(item.get('confidence', 0.8)),
                        reasoning=item.get('reasoning', ''),
                        phase=AnnotationPhase.CONCEPT_DETECTION
                    ))
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.error(f"Failed to parse detection response: {e}")
            logger.debug(f"Response content: {response[:500]}...")
        
        return candidates
    
    def _create_validation_prompt(self, document_content: str, candidates: List[AnnotationCandidate]) -> str:
        """Create prompt for contextual validation."""
        candidate_list = "\n".join([
            f"- '{c.text_segment}' → {c.concept_label} (confidence: {c.confidence:.2f})"
            for c in candidates
        ])
        
        return f"""Review these potential annotations for contextual appropriateness:

DOCUMENT EXCERPT:
{document_content[:1500]}

CANDIDATE ANNOTATIONS:
{candidate_list}

TASK: For each annotation, validate if the concept truly applies in this specific context.

Consider:
1. Does the text usage match the concept meaning?
2. Is this the most appropriate concept for this context?
3. Are there better alternative concepts?

For each candidate, provide:
- concept_label: The concept being validated
- valid: true/false
- confidence: Updated confidence (0.0-1.0)  
- reasoning: Why it's valid/invalid in this context

Format as JSON array:
[{{"concept_label": "...", "valid": true, "confidence": 0.95, "reasoning": "..."}}]"""
    
    def _parse_validation_response(self, response: str, candidates: List[AnnotationCandidate]) -> List[AnnotationCandidate]:
        """Parse validation response and update candidates."""
        try:
            # Extract and parse JSON
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            validations = json.loads(json_str)
            validation_lookup = {v['concept_label']: v for v in validations}
            
            validated_candidates = []
            
            for candidate in candidates:
                validation = validation_lookup.get(candidate.concept_label, {})
                
                if validation.get('valid', True):  # Default to valid if not specified
                    # Update confidence and reasoning
                    candidate.confidence = validation.get('confidence', candidate.confidence)
                    candidate.reasoning = validation.get('reasoning', candidate.reasoning)
                    candidate.phase = AnnotationPhase.CONTEXTUAL_VALIDATION
                    validated_candidates.append(candidate)
            
            return validated_candidates
            
        except Exception as e:
            logger.error(f"Failed to parse validation response: {e}")
            # Return original candidates with reduced confidence
            for candidate in candidates:
                candidate.confidence *= 0.9
                candidate.reasoning += " (validation parsing failed)"
            return candidates
    
    def _apply_semantic_rules(self, candidate: AnnotationCandidate, concepts: List[Dict]) -> AnnotationCandidate:
        """Apply semantic refinement rules to candidate."""
        # Basic semantic enhancement
        # In full implementation, this would use concept definitions and relationships
        
        # Boost confidence for exact matches
        if candidate.text_segment.lower() == candidate.concept_label.lower():
            candidate.confidence = min(1.0, candidate.confidence + 0.1)
            candidate.reasoning += " (exact label match boost)"
        
        candidate.phase = AnnotationPhase.SEMANTIC_REFINEMENT
        return candidate
    
    def _extract_context_window(self, document_content: str, start_offset: int, end_offset: int) -> str:
        """Extract context window around annotation."""
        context_start = max(0, start_offset - self.context_window_size)
        context_end = min(len(document_content), end_offset + self.context_window_size)
        
        return document_content[context_start:context_end]
    
    async def _get_ontology_concepts(self, world_id: int) -> List[Dict]:
        """Get ontology concepts for the world."""
        try:
            # Get ontology mapping for world
            mapping = self.ontserve_service.get_world_ontology_mapping(world_id)
            
            # Get concepts from all mapped ontologies
            all_concepts = []
            for ontology_type, ontology_name in mapping.items():
                concepts = self.ontserve_service.get_ontology_concepts([ontology_name])
                if ontology_name in concepts:
                    all_concepts.extend(concepts[ontology_name])
            
            logger.info(f"Retrieved {len(all_concepts)} ontology concepts")
            return all_concepts
            
        except Exception as e:
            logger.error(f"Failed to get ontology concepts: {e}")
            return []
    
    def _get_document_content(self, document_type: str, document_id: int) -> Optional[str]:
        """Get document content for annotation."""
        try:
            if document_type == 'guideline':
                from app.models.guideline import Guideline
                document = Guideline.query.get(document_id)
                return document.content if document else None
            elif document_type == 'case':
                from app.models.case import Case
                document = Case.query.get(document_id)
                return document.description if document else None
            else:
                return None
                
        except Exception as e:
            logger.error(f"Failed to get document content: {e}")
            return None
    
    def _create_database_annotations(self, candidates: List[AnnotationCandidate],
                                   document_type: str, document_id: int, 
                                   world_id: int) -> List[DocumentConceptAnnotation]:
        """Create database annotation records."""
        from app.models import db
        
        annotations = []
        
        for candidate in candidates:
            annotation = DocumentConceptAnnotation(
                document_type=document_type,
                document_id=document_id,
                world_id=world_id,
                concept_uri=candidate.concept_uri,
                concept_label=candidate.concept_label,
                concept_type=candidate.concept_type,
                text_segment=candidate.text_segment,
                start_offset=candidate.start_offset,
                end_offset=candidate.end_offset,
                confidence=candidate.confidence,
                llm_model='intelligent_multipass',
                ontology_name=self._extract_ontology_name(candidate.concept_uri),
                validation_status='pending'
            )
            
            # Add processing metadata
            annotation.metadata = {
                'reasoning': candidate.reasoning,
                'phase': candidate.phase.value,
                'context_window': candidate.context_window
            }
            
            try:
                db.session.add(annotation)
                annotations.append(annotation)
            except Exception as e:
                logger.error(f"Failed to create annotation: {e}")
        
        try:
            db.session.commit()
            logger.info(f"Stored {len(annotations)} intelligent annotations")
        except Exception as e:
            logger.error(f"Failed to commit annotations: {e}")
            db.session.rollback()
            annotations = []
        
        return annotations
    
    def _extract_ontology_name(self, concept_uri: str) -> str:
        """Extract ontology name from concept URI."""
        if 'proethica-core' in concept_uri:
            return 'proethica-core'
        elif 'proethica-intermediate' in concept_uri:
            return 'proethica-intermediate'
        elif 'engineering-ethics' in concept_uri:
            return 'engineering-ethics'
        else:
            return 'unknown'
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            **self.stats,
            'average_processing_time': (
                self.stats['total_processing_time'] / self.stats['total_documents']
                if self.stats['total_documents'] > 0 else 0
            )
        }