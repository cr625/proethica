"""
Simplified LLM Annotation Service

A simpler, more effective approach that gives the LLM full context 
and includes a validation/refinement step.
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class AnnotationMatch:
    """Represents a match between text and ontology concept."""
    text_snippet: str
    start_offset: int
    end_offset: int
    concept_uri: str
    concept_label: str
    concept_definition: str
    confidence: float
    reasoning: str
    

@dataclass
class SimplifiedAnnotationResult:
    """Result of simplified annotation process."""
    initial_matches: List[Dict]
    refined_matches: List[Dict] 
    processing_time_ms: int
    validation_performed: bool = True
    validation_summary: str = ""
    errors: List[str] = None


class SimplifiedLLMAnnotationService:
    """
    Simplified annotation service that gives LLM full context at once
    and includes validation/refinement.
    """
    
    def __init__(self):
        from app.services.direct_llm_service import DirectLLMService
        self.llm_service = DirectLLMService()
    
    def annotate_text(self, text: str, world_id: int, target_ontologies: Optional[List[str]] = None) -> SimplifiedAnnotationResult:
        """
        Main annotation method expected by the route.
        """
        start_time = datetime.now()
        
        try:
            # Get ontology concepts
            from app.services.ontserve_annotation_service import OntServeAnnotationService
            ontserve = OntServeAnnotationService()
            
            if target_ontologies:
                concepts_dict = ontserve.get_ontology_concepts(target_ontologies)
            else:
                # Get all concepts for world
                ontology_mapping = ontserve.get_world_ontology_mapping(world_id)
                if ontology_mapping and all(isinstance(v, dict) for v in ontology_mapping.values()):
                    target_ontologies = list(set([v['name'] for v in ontology_mapping.values()]))
                else:
                    target_ontologies = list(set(ontology_mapping.values()))
                concepts_dict = ontserve.get_ontology_concepts(target_ontologies)
            
            # Flatten concepts
            flattened_concepts = []
            for ontology_name, concepts in concepts_dict.items():
                for concept in concepts:
                    concept['source_ontology'] = ontology_name
                    flattened_concepts.append(concept)
                    
            # Perform annotation
            initial_matches_data = self._annotate_with_full_context(text, flattened_concepts)
            refined_matches_data, validation_notes = self._validate_and_refine_dict_format(text, initial_matches_data, flattened_concepts)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SimplifiedAnnotationResult(
                initial_matches=[self._match_to_dict(m) for m in initial_matches_data],
                refined_matches=refined_matches_data,
                processing_time_ms=int(processing_time),
                validation_performed=True,
                validation_summary=validation_notes,
                errors=[]
            )
            
        except Exception as e:
            logger.exception(f"Error in annotate_text: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            return SimplifiedAnnotationResult(
                initial_matches=[],
                refined_matches=[],
                processing_time_ms=int(processing_time),
                validation_performed=False,
                validation_summary=f"Error: {str(e)}",
                errors=[str(e)]
            )
        
    def annotate_with_validation(self, text: str, ontology_concepts: List[Dict]) -> SimplifiedAnnotationResult:
        """
        Annotate text with ontology concepts using a simpler, more effective approach.
        
        1. Give LLM everything at once for initial annotation
        2. Validate and refine the annotations
        3. Return final refined results
        """
        start_time = datetime.now()
        
        # Step 1: Initial annotation with FULL context
        initial_matches = self._annotate_with_full_context(text, ontology_concepts)
        
        # Step 2: Validation and refinement
        refined_matches, validation_notes = self._validate_and_refine(text, initial_matches, ontology_concepts)
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        return SimplifiedAnnotationResult(
            matches=refined_matches,
            refinements_applied=len(refined_matches) - len(initial_matches) if refined_matches else 0,
            processing_time_ms=int(processing_time),
            validation_notes=validation_notes
        )
    
    def _annotate_with_full_context(self, text: str, concepts: List[Dict]) -> List[AnnotationMatch]:
        """
        Give the LLM everything at once - much simpler and more effective.
        """
        # Prepare concept list for the prompt
        concept_list = []
        for i, concept in enumerate(concepts[:50], 1):  # Limit to 50 for prompt size
            label = concept.get('label', 'Unknown')
            definition = concept.get('definition', 'No definition')[:150]
            uri = concept.get('uri', f'concept_{i}')
            concept_list.append(f"{i}. **{label}**: {definition}")
        
        # Single comprehensive prompt with ALL context
        annotation_prompt = f"""
You are annotating an engineering ethics text with ontology concepts. 

**TEXT TO ANNOTATE:**
```
{text[:8000]}
```

**AVAILABLE ONTOLOGY CONCEPTS:**
{chr(10).join(concept_list)}

**TASK:**
Find ALL meaningful matches between the text and the ontology concepts. For each match:
1. Identify the specific text snippet that relates to the concept
2. Explain why it matches
3. Rate your confidence (0.0-1.0)

**IMPORTANT:**
- Match based on SEMANTIC MEANING, not just word overlap
- A text about "keeping the public safe" should match "Public Safety Principle"
- Don't force matches - only match when there's real semantic relationship
- Multiple text snippets can match the same concept
- The same text can match multiple concepts if relevant

Return a JSON array of matches:
[
  {{
    "text_snippet": "exact text from the document",
    "concept_number": 1-{len(concept_list)},
    "confidence": 0.0-1.0,
    "reasoning": "why this matches"
  }}
]

Be thorough - find ALL good matches. Quality over quantity, but don't miss obvious connections.
"""
        
        try:
            from app.services.llm_service import Conversation
            conversation = Conversation()
            
            response = self.llm_service.send_message_with_context(
                message=annotation_prompt,
                conversation=conversation,
                application_context="Simplified LLM Annotation",
                world_id=1,
                service="claude"
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON array
            json_match = re.search(r'\[[\s\S]*?\]', content, re.DOTALL)
            if json_match:
                matches_data = json.loads(json_match.group())
                
                annotation_matches = []
                for match_data in matches_data:
                    concept_num = match_data.get('concept_number')
                    if concept_num and 1 <= concept_num <= len(concepts):
                        concept = concepts[concept_num - 1]
                        
                        # Find text position (approximate)
                        text_snippet = match_data.get('text_snippet', '')
                        start_offset = text.lower().find(text_snippet.lower())
                        if start_offset == -1:
                            start_offset = 0
                        
                        annotation_matches.append(AnnotationMatch(
                            text_snippet=text_snippet,
                            start_offset=start_offset,
                            end_offset=start_offset + len(text_snippet),
                            concept_uri=concept.get('uri', ''),
                            concept_label=concept.get('label', ''),
                            concept_definition=concept.get('definition', ''),
                            confidence=float(match_data.get('confidence', 0.5)),
                            reasoning=match_data.get('reasoning', '')
                        ))
                
                return annotation_matches
                
        except Exception as e:
            logger.exception(f"Error in annotation: {e}")
            
        return []
    
    def _validate_and_refine(self, text: str, initial_matches: List[AnnotationMatch], 
                            concepts: List[Dict]) -> tuple[List[AnnotationMatch], str]:
        """
        Validation step - ask LLM to review and refine the annotations.
        """
        if not initial_matches:
            return [], "No initial matches to validate"
        
        # Prepare matches for validation
        matches_description = []
        for i, match in enumerate(initial_matches, 1):
            matches_description.append(
                f"{i}. \"{match.text_snippet[:50]}...\" → {match.concept_label} "
                f"(confidence: {match.confidence:.2f})"
            )
        
        validation_prompt = f"""
Review these ontology annotations. Keep the good ones, remove poor matches.

ANNOTATIONS TO REVIEW:
{chr(10).join(matches_description)}

Return simple JSON with annotation numbers to keep:
{{
  "keep": [1, 2, 3],
  "notes": "validation summary"
}}

Only include annotation numbers that are good semantic matches. Remove forced or incorrect matches.
"""
        
        try:
            from app.services.llm_service import Conversation
            conversation = Conversation()
            
            response = self.llm_service.send_message_with_context(
                message=validation_prompt,
                conversation=conversation,
                application_context="Annotation Validation",
                world_id=1,
                service="claude"
            )
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON - try multiple approaches for robust parsing
            validation_data = None
            
            # Try to find JSON block first
            json_match = re.search(r'\{[\s\S]*?\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                try:
                    validation_data = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parsing failed: {e}")
                    # Try to extract just the essentials with regex
                    keep_match = re.search(r'"keep":\s*\[([^\]]*)\]', content)
                    remove_match = re.search(r'"remove":\s*\[([^\]]*)\]', content)
                    
                    if keep_match:
                        try:
                            keep_nums = [int(x.strip()) for x in keep_match.group(1).split(',') if x.strip().isdigit()]
                            validation_data = {'keep': keep_nums, 'remove': [], 'missing': [], 'notes': 'Partial validation due to JSON parse error'}
                        except:
                            pass
            
            if validation_data:
                
                # Apply refinements
                refined_matches = []
                
                # Keep the good ones
                keep_indices = validation_data.get('keep', [])
                for idx in keep_indices:
                    if 1 <= idx <= len(initial_matches):
                        refined_matches.append(initial_matches[idx - 1])
                
                # If no keeps specified, keep all
                if not keep_indices:
                    refined_matches = initial_matches
                
                notes = validation_data.get('notes', 'Validation complete')
                
                return refined_matches, f"{notes} - kept {len(refined_matches)}/{len(initial_matches)} matches"
                
        except Exception as e:
            logger.exception(f"Error in validation: {e}")
            
        # If validation fails, return original matches
        logger.info("Validation failed, returning original matches without validation")
        return initial_matches, f"Validation skipped due to error, using {len(initial_matches)} original matches"
    
    def _match_to_dict(self, match: AnnotationMatch) -> Dict:
        """Convert AnnotationMatch to dictionary format expected by route."""
        return {
            'text_segment': match.text_snippet,
            'concept_uri': match.concept_uri,
            'concept_label': match.concept_label,
            'concept_definition': match.concept_definition,
            'reasoning': match.reasoning,
            'confidence': match.confidence,
            'start_offset': match.start_offset,
            'end_offset': match.end_offset
        }
    
    def _validate_and_refine_dict_format(self, text: str, initial_matches: List[AnnotationMatch], 
                                        concepts: List[Dict]) -> tuple[List[Dict], str]:
        """Validation method that returns dictionary format expected by route."""
        refined_matches, validation_notes = self._validate_and_refine(text, initial_matches, concepts)
        
        # Convert to dictionary format
        refined_dict_matches = []
        for match in refined_matches:
            refined_dict_matches.append({
                'text_segment': match.text_snippet,
                'concept_uri': match.concept_uri,
                'concept_label': match.concept_label,
                'concept_definition': match.concept_definition,
                'reasoning': match.reasoning,
                'quality_score': match.confidence,
                'validation_reasoning': f"Validated: {match.reasoning}",
                'ontology': getattr(match, 'ontology', 'proethica-intermediate')
            })
        
        return refined_dict_matches, validation_notes


def create_simplified_annotation_endpoint():
    """
    Create a simplified endpoint that uses this better approach.
    """
    from flask import Blueprint, request, jsonify
    from app.services.ontserve_annotation_service import OntServeAnnotationService
    
    simplified_bp = Blueprint('simplified_annotations', __name__)
    
    @simplified_bp.route('/api/annotate/simplified', methods=['POST'])
    def simplified_annotate():
        """
        Simplified annotation endpoint with validation.
        """
        data = request.json
        text = data.get('text', '')
        world_id = data.get('world_id', 1)
        
        if not text:
            return jsonify({'error': 'No text provided'}), 400
        
        try:
            # Get ontology concepts
            ontserve = OntServeAnnotationService()
            ontology_mapping = ontserve.get_world_ontology_mapping(world_id)
            
            # Get target ontologies
            if ontology_mapping and all(isinstance(v, dict) for v in ontology_mapping.values()):
                target_ontologies = list(set([v['name'] for v in ontology_mapping.values()]))
            else:
                target_ontologies = list(set(ontology_mapping.values()))
            
            all_concepts = ontserve.get_ontology_concepts(target_ontologies)
            
            # Flatten concepts
            flattened_concepts = []
            for ontology_name, concepts in all_concepts.items():
                for concept in concepts:
                    concept['source_ontology'] = ontology_name
                    flattened_concepts.append(concept)
            
            # Use simplified service
            service = SimplifiedLLMAnnotationService()
            result = service.annotate_with_validation(text, flattened_concepts)
            
            # Format response
            annotations = []
            for match in result.matches:
                annotations.append({
                    'text': match.text_snippet,
                    'start': match.start_offset,
                    'end': match.end_offset,
                    'concept': {
                        'uri': match.concept_uri,
                        'label': match.concept_label,
                        'definition': match.concept_definition
                    },
                    'confidence': match.confidence,
                    'reasoning': match.reasoning
                })
            
            return jsonify({
                'success': True,
                'annotations': annotations,
                'validation_notes': result.validation_notes,
                'processing_time_ms': result.processing_time_ms,
                'total_annotations': len(annotations)
            })
            
        except Exception as e:
            logger.exception(f"Error in simplified annotation: {e}")
            return jsonify({'error': str(e)}), 500
    
    return simplified_bp
