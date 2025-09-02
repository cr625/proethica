"""
LLM Annotation Approval Service

Handles intermediate LLM approval and validation of document concept annotations.
This service provides a second LLM pass to review, refine, and validate initial annotations
before they are presented to users for final approval.

Key Features:
- Validates semantic accuracy of annotations
- Can suggest better concept matches
- May adjust confidence levels
- Provides enhanced reasoning
- Identifies potentially problematic annotations
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.services.direct_llm_service import DirectLLMService
from app.services.ontserve_annotation_service import OntServeAnnotationService
from app.models.document_concept_annotation import DocumentConceptAnnotation

logger = logging.getLogger(__name__)


@dataclass
class ApprovalResult:
    """Result of LLM approval process for an annotation."""
    annotation_id: int
    should_approve: bool
    suggested_concept_uri: Optional[str] = None
    suggested_concept_label: Optional[str] = None
    new_confidence: Optional[float] = None
    enhanced_reasoning: Optional[str] = None
    concerns: List[str] = None
    processing_time_ms: int = 0
    error_message: Optional[str] = None

    def __post_init__(self):
        if self.concerns is None:
            self.concerns = []


class LLMAnnotationApprovalService:
    """
    Service for LLM-powered intermediate approval of document annotations.
    """

    def __init__(self):
        self.llm_service = DirectLLMService()
        self.ontserve_service = OntServeAnnotationService()

    def approve_annotations(self, annotation_ids: List[int], world_id: int = 1) -> List[ApprovalResult]:
        """
        Approve a batch of annotations using LLM validation.

        Args:
            annotation_ids: List of annotation IDs to approve
            world_id: World context for ontology access

        Returns:
            List of ApprovalResult objects
        """
        results = []
        start_time = datetime.now()

        try:
            # Get all annotations in single query
            annotations = DocumentConceptAnnotation.query \
                .filter(DocumentConceptAnnotation.id.in_(annotation_ids)) \
                .all()

            # Get ontology mapping for context
            ontology_mapping = self.ontserve_service.get_world_ontology_mapping(world_id)

            # Get concepts for potential re-matching
            all_concepts = []
            if ontology_mapping:
                for ontology_name in ontology_mapping.values():
                    concepts = self.ontserve_service.get_ontology_concepts([ontology_name])
                    all_concepts.extend([
                        {**concept, 'source_ontology': ontology_name}
                        for concept in concepts[ontology_name]
                    ])

            logger.info(f"Found {len(annotations)} annotations and {len(all_concepts)} concepts")

            # Process each annotation
            for annotation in annotations:
                result = self._approve_single_annotation(annotation, all_concepts)
                results.append(result)

                # Apply the approval result
                self._apply_approval_result(annotation, result)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Approved {len(results)} annotations successfully")
            return results

        except Exception as e:
            logger.exception(f"Error in batch approval: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Return error results for all annotations
            return [
                ApprovalResult(
                    annotation_id=aid,
                    should_approve=False,
                    error_message=str(e),
                    processing_time_ms=int(processing_time)
                )
                for aid in annotation_ids
            ]

    def _approve_single_annotation(self, annotation: DocumentConceptAnnotation,
                                  ontology_concepts: List[Dict[str, Any]]) -> ApprovalResult:
        """
        Run LLM approval validation on a single annotation.
        """
        start_time = datetime.now()

        try:
            # Create approval prompt
            prompt = self._create_approval_prompt(annotation, ontology_concepts)

            # Use the direct LLM service
            from app.services.llm_service import Conversation
            conversation = Conversation()

            response = self.llm_service.send_message_with_context(
                message=prompt,
                conversation=conversation,
                application_context="LLM Annotation Approval",
                world_id=annotation.world_id or 1,
                service="claude"
            )

            # Parse response
            approval_data = self._parse_approval_response(response.content)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            # Create result
            result = ApprovalResult(
                annotation_id=annotation.id,
                should_approve=approval_data.get('approve', True),
                suggested_concept_uri=approval_data.get('suggested_concept_uri'),
                suggested_concept_label=approval_data.get('suggested_concept_label'),
                new_confidence=approval_data.get('new_confidence'),
                enhanced_reasoning=approval_data.get('enhanced_reasoning'),
                concerns=approval_data.get('concerns', []),
                processing_time_ms=int(processing_time)
            )

            return result

        except Exception as e:
            logger.exception(f"Error approving annotation {annotation.id}: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            return ApprovalResult(
                annotation_id=annotation.id,
                should_approve=False,
                error_message=str(e),
                processing_time_ms=int(processing_time)
            )

    def _create_approval_prompt(self, annotation: DocumentConceptAnnotation,
                               ontology_concepts: List[Dict[str, Any]]) -> str:
        """
        Create a detailed LLM prompt for annotation approval evaluation.
        """

        # Get document context
        document = annotation.get_document()
        document_context = ""
        if document:
            if hasattr(document, 'content'):
                # Truncate content around annotation
                content = document.content or ""
                start_max = max(0, annotation.start_offset - 200) if annotation.start_offset else 0
                end_max = min(len(content),
                             annotation.end_offset + 200) if annotation.end_offset else len(content)
                document_context = content[start_max:end_max]

        # Format ontology concepts for LLM
        ontology_list = []
        for i, concept in enumerate(ontology_concepts[:50]):  # Limit to 50 concepts
            label = concept.get('label', 'Unknown')
            definition = concept.get('definition', 'No definition')[:200]
            ontology = concept.get('source_ontology', 'Unknown')
            uri = concept.get('uri', '')

            ontology_list.append(f"{i+1}. **{label}** ({ontology}): {definition}")

        prompt = f"""
You are a professional ethics expert reviewing AI-generated ontology concept annotations for engineering ethics guidelines.

**ANNOTATION TO REVIEW:**
- Text: "{annotation.text_segment}"
- Current Concept: "{annotation.concept_label}"
- Current Confidence: {annotation.confidence or 'N/A'}
- Current Reasoning: "{annotation.llm_reasoning or 'N/A'}"

**DOCUMENT CONTEXT:**
{document_context}

**VERIFICATION QUESTIONS TO ANSWER:**

1. **Semantic Accuracy**: Does this annotation accurately represent an ethical/professional engineering concept?
2. **Term Specificity**: Is this term specific enough, or is it too generic/ambiguous?
3. **Concept Fit**: Does the matched concept actually align with the meaning in context?
4. **Ontology Coverage**: If the match is poor, is there a better concept available?

**AVAILABLE ONTOLOGY CONCEPTS:**
{chr(10).join(ontology_list)}

**TASK:**
Review the annotation and provide a JSON response with your assessment.

**IMPORTANT:**
- Be conservative: only reject if there's a clear problem
- If confidence is very low (<0.4), suggest reconsideration
- If the term is too generic ("standards", "safety" without context), rate lower
- If there's a better concept match available, suggest it
- Always provide enhanced reasoning

**RESPONSE FORMAT (JSON ONLY):**
{
    "approve": true/false,
    "suggested_concept_uri": "URI_of_better_match_or_null",
    "suggested_concept_label": "Label_of_better_match_or_null",
    "new_confidence": 0.0-1.0,
    "enhanced_reasoning": "Your improved explanation of this annotation",
    "concerns": ["List any specific concerns", "or empty array if none"]
}

Only output valid JSON. Be professional and precise.
"""

        return prompt

    def _parse_approval_response(self, response: str) -> Dict[str, Any]:
        """
        Parse LLM approval response into structured data.
        """
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

            # Fallback: look for JSON in code blocks
            import re
            json_match = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))

        except Exception as e:
            logger.warning(f"Error parsing LLM approval response: {e}")

        # Fallback defaults
        return {
            'approve': True,
            'suggested_concept_uri': None,
            'suggested_concept_label': None,
            'new_confidence': None,  # Don't change if not specified
            'enhanced_reasoning': response[:500] if response else 'Could not parse LLM response',
            'concerns': ['Could not parse LLM response format']
        }

    def _apply_approval_result(self, annotation: DocumentConceptAnnotation,
                              result: ApprovalResult):
        """
        Apply the LLM approval result to the annotation.
        """
        try:
            # Create new version with approval changes
            updates = {
                'approval_stage': 'llm_approved'
            }

            if result.enhanced_reasoning:
                updates['llm_reasoning'] = result.enhanced_reasoning

            if result.new_confidence is not None:
                updates['confidence'] = result.new_confidence

            if result.suggested_concept_uri:
                # Find the concept details
                suggested_concept = next(
                    (c for c in [] if c.get('uri') == result.suggested_concept_uri),
                    None
                )
                if suggested_concept:
                    updates.update({
                        'concept_uri': result.suggested_concept_uri,
                        'concept_label': result.suggested_concept_label or suggested_concept.get('label'),
                        'concept_definition': suggested_concept.get('definition'),
                    })

            # Create new version
            new_version = annotation.create_new_version(
                updates=updates,
                approval_stage='llm_approved'
            )

            # Save to database
            db.session.add(new_version)
            db.session.commit()

            logger.info(f"Applied LLM approval to annotation {annotation.id} (new version: {new_version.id})")

        except Exception as e:
            logger.exception(f"Error applying approval result for annotation {annotation.id}: {e}")
            # Mark as failed but don't throw exception
            annotation.approval_stage = 'llm_approved'  # At least mark the stage
            db.session.commit()

    def get_approval_statistics(self, world_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get statistics about LLM approval performance.
        """
        query = DocumentConceptAnnotation.query.filter(
            DocumentConceptAnnotation.approval_stage.in_(['llm_extracted', 'llm_approved'])
        )

        if world_id:
            query = query.filter_by(world_id=world_id)

        total_annotations = query.count()
        approved = query.filter_by(approval_stage='llm_approved').count()
        pending = query.filter_by(approval_stage='llm_extracted').count()

        # Get confidence changes
        confidence_changes = db.session.query(
            DocumentConceptAnnotation.id,
            DocumentConceptAnnotation.confidence.label('current_confidence'),
            DocumentConceptAnnotation.parent_annotation.confidence.label('original_confidence')
        ).filter(
            DocumentConceptAnnotation.approval_stage == 'llm_approved',
            DocumentConceptAnnotation.parent_annotation_id.isnot(None)
        ).all()

        confidence_improvements = sum(
            1 for c in confidence_changes
            if c.current_confidence and c.original_confidence and
            c.current_confidence > c.original_confidence
        )

        return {
            'total_annotations': total_annotations,
            'approved_by_llm': approved,
            'pending_llm_approval': pending,
            'confidence_improvements': confidence_improvements,
            'approval_rate': (approved / total_annotations * 100) if total_annotations > 0 else 0
        }


# Dependency injection
from app.models import db
