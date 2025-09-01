"""
Definition-Based Annotation Service

A simplified approach that loads ontology definitions first, then asks the LLM
which definitions apply to the guideline text in context.

This is more accurate than trying to extract terms first without knowing what's
in the ontology.
"""

import logging
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from app.services.ontserve_annotation_service import OntServeAnnotationService

logger = logging.getLogger(__name__)


@dataclass
class DefinitionMatch:
    """Represents a match between an ontology definition and text."""
    concept_uri: str
    concept_label: str
    concept_definition: str
    concept_ontology: str
    text_passage: str
    start_offset: int
    end_offset: int
    reasoning: str
    confidence: float


@dataclass
class DefinitionBasedResult:
    """Result of definition-based annotation."""
    matches: List[DefinitionMatch]
    unmatched_concepts: List[str]  # Concepts that didn't match
    processing_time_ms: int
    total_concepts_checked: int
    batch_count: int
    errors: List[str] = None


class DefinitionBasedAnnotationService:
    """
    Simplified annotation service that:
    1. Loads ontology concepts with definitions
    2. Batches them to avoid token limits
    3. Asks LLM which definitions apply to the text
    4. Returns clear matches with context
    """
    
    def __init__(self, batch_size: int = 20):
        self.ontserve_service = OntServeAnnotationService()
        self.batch_size = batch_size
        
        # Use DirectLLMService to avoid mock responses
        from app.services.direct_llm_service import DirectLLMService
        self.llm_service = DirectLLMService()
    
    def annotate_text(self, text: str, world_id: int = 1,
                     target_ontologies: Optional[List[str]] = None) -> DefinitionBasedResult:
        """
        Perform definition-based annotation on text.
        
        Args:
            text: Text to annotate
            world_id: World ID for ontology mapping
            target_ontologies: Specific ontologies to use (if None, uses world mapping)
            
        Returns:
            DefinitionBasedResult with matches
        """
        start_time = datetime.now()
        all_matches = []
        all_unmatched = []
        errors = []
        
        try:
            # Get ontology concepts with definitions
            logger.info("Loading ontology concepts with definitions")
            concepts = self._load_concepts_with_definitions(world_id, target_ontologies)
            total_concepts = len(concepts)
            logger.info(f"Loaded {total_concepts} concepts with definitions")
            
            # Filter to only concepts that have definitions
            concepts_with_defs = [c for c in concepts if c.get('definition')]
            logger.info(f"Filtered to {len(concepts_with_defs)} concepts with non-empty definitions")
            
            if not concepts_with_defs:
                logger.warning("No concepts with definitions found")
                processing_time = (datetime.now() - start_time).total_seconds() * 1000
                return DefinitionBasedResult(
                    matches=[],
                    unmatched_concepts=[],
                    processing_time_ms=int(processing_time),
                    total_concepts_checked=0,
                    batch_count=0,
                    errors=["No concepts with definitions found"]
                )
            
            # Process in batches
            batches = self._create_batches(concepts_with_defs, self.batch_size)
            batch_count = len(batches)
            logger.info(f"Processing {batch_count} batches of up to {self.batch_size} concepts each")
            
            for i, batch in enumerate(batches, 1):
                logger.info(f"Processing batch {i}/{batch_count} with {len(batch)} concepts")
                try:
                    batch_matches, batch_unmatched = self._process_batch(text, batch)
                    all_matches.extend(batch_matches)
                    all_unmatched.extend(batch_unmatched)
                except Exception as e:
                    error_msg = f"Error processing batch {i}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Definition-based annotation complete: {len(all_matches)} matches found")
            
            return DefinitionBasedResult(
                matches=all_matches,
                unmatched_concepts=all_unmatched,
                processing_time_ms=int(processing_time),
                total_concepts_checked=len(concepts_with_defs),
                batch_count=batch_count,
                errors=errors if errors else None
            )
            
        except Exception as e:
            logger.exception(f"Error in definition-based annotation: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return DefinitionBasedResult(
                matches=[],
                unmatched_concepts=[],
                processing_time_ms=int(processing_time),
                total_concepts_checked=0,
                batch_count=0,
                errors=[str(e)]
            )
    
    def _load_concepts_with_definitions(self, world_id: int, 
                                       target_ontologies: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Load ontology concepts with their definitions."""
        
        # Get target ontologies
        if target_ontologies is None:
            ontology_mapping = self.ontserve_service.get_world_ontology_mapping(world_id)
            # Handle both dict and string formats
            if ontology_mapping and all(isinstance(v, dict) for v in ontology_mapping.values()):
                target_ontologies = list(set([v['name'] for v in ontology_mapping.values()]))
            else:
                target_ontologies = list(set(ontology_mapping.values()))
        
        logger.info(f"Using ontologies: {target_ontologies}")
        
        # Get concepts from ontologies
        all_concepts_dict = self.ontserve_service.get_ontology_concepts(target_ontologies)
        
        # Flatten concepts from all ontologies
        flattened_concepts = []
        for ontology_name, concepts in all_concepts_dict.items():
            for concept in concepts:
                concept['source_ontology'] = ontology_name
                flattened_concepts.append(concept)
        
        return flattened_concepts
    
    def _create_batches(self, concepts: List[Dict[str, Any]], batch_size: int) -> List[List[Dict[str, Any]]]:
        """Create batches of concepts to avoid token limits."""
        batches = []
        for i in range(0, len(concepts), batch_size):
            batches.append(concepts[i:i + batch_size])
        return batches
    
    def _process_batch(self, text: str, batch: List[Dict[str, Any]]) -> Tuple[List[DefinitionMatch], List[str]]:
        """Process a batch of concepts against the text."""
        
        # Format concepts for the prompt
        concepts_text = self._format_concepts_for_prompt(batch)
        
        # Create the prompt
        prompt = f"""You are analyzing a professional ethics guideline to identify which ontology concepts apply.

Here are ontology concepts with their definitions:

{concepts_text}

For the following guideline text, identify which of the above concepts apply.

For each match, provide:
1. concept_label: The exact concept name from above
2. text_passage: The exact passage from the guideline where this concept applies (quote it exactly)
3. start_offset: Approximate character position where the passage starts
4. end_offset: Approximate character position where the passage ends
5. reasoning: A brief explanation of why this definition matches the context (1-2 sentences)
6. confidence: Your confidence in this match (0.0-1.0)

IMPORTANT:
- Only match concepts where the definition truly applies to the context
- Quote the exact text passage, don't paraphrase
- A concept may match multiple passages - include all relevant matches
- If a concept doesn't clearly apply, don't force a match

Guideline text to analyze:
```
{text[:3000]}  # Limit text length for token management
```

Return your response as a JSON object with this structure:
{{
    "matches": [
        {{
            "concept_label": "Concept Name",
            "text_passage": "exact quote from guideline",
            "start_offset": 0,
            "end_offset": 100,
            "reasoning": "This matches because...",
            "confidence": 0.85
        }}
    ],
    "unmatched_concepts": ["List of concept labels that didn't match anything"]
}}
"""
        
        try:
            # Call LLM
            from app.services.llm_service import Conversation
            conversation = Conversation()
            
            response = self.llm_service.send_message_with_context(
                message=prompt,
                conversation=conversation,
                application_context="Definition-Based Annotation",
                world_id=1,
                service="claude"
            )
            
            # Parse response
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Extract JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', content, re.DOTALL)
            if json_match:
                result_data = json.loads(json_match.group())
                
                # Process matches
                matches = []
                for match_data in result_data.get('matches', []):
                    # Find the concept in our batch
                    concept = self._find_concept_by_label(batch, match_data.get('concept_label', ''))
                    if concept:
                        match = DefinitionMatch(
                            concept_uri=concept.get('uri', ''),
                            concept_label=concept.get('label', ''),
                            concept_definition=concept.get('definition', ''),
                            concept_ontology=concept.get('source_ontology', ''),
                            text_passage=match_data.get('text_passage', ''),
                            start_offset=match_data.get('start_offset', 0),
                            end_offset=match_data.get('end_offset', 0),
                            reasoning=match_data.get('reasoning', ''),
                            confidence=float(match_data.get('confidence', 0.5))
                        )
                        matches.append(match)
                
                unmatched = result_data.get('unmatched_concepts', [])
                
                return matches, unmatched
            else:
                logger.warning("Could not extract JSON from LLM response")
                return [], [c['label'] for c in batch]
                
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            # Return empty matches, all concepts as unmatched
            return [], [c['label'] for c in batch]
    
    def _format_concepts_for_prompt(self, concepts: List[Dict[str, Any]]) -> str:
        """Format concepts nicely for the LLM prompt."""
        lines = []
        for i, concept in enumerate(concepts, 1):
            label = concept.get('label', 'Unknown')
            definition = concept.get('definition', 'No definition')
            ontology = concept.get('source_ontology', 'Unknown')
            
            # Truncate very long definitions
            if len(definition) > 300:
                definition = definition[:297] + "..."
            
            lines.append(f"{i}. **{label}** (from {ontology})")
            lines.append(f"   Definition: {definition}")
            lines.append("")  # Empty line for readability
        
        return "\n".join(lines)
    
    def _find_concept_by_label(self, concepts: List[Dict[str, Any]], label: str) -> Optional[Dict[str, Any]]:
        """Find a concept in the list by its label."""
        label_lower = label.lower().strip()
        for concept in concepts:
            if concept.get('label', '').lower().strip() == label_lower:
                return concept
        return None
    
    def generate_annotation_report(self, result: DefinitionBasedResult) -> str:
        """Generate a human-readable report of annotation results."""
        report_lines = [
            "# Definition-Based Annotation Report",
            "",
            "## Summary",
            f"- Total concepts checked: {result.total_concepts_checked}",
            f"- Concepts matched: {len(result.matches)}",
            f"- Concepts unmatched: {len(result.unmatched_concepts)}",
            f"- Processing time: {result.processing_time_ms}ms",
            f"- Batches processed: {result.batch_count}",
            ""
        ]
        
        if result.matches:
            report_lines.extend([
                f"## Matched Concepts ({len(result.matches)})",
                ""
            ])
            
            # Group matches by concept
            matches_by_concept = {}
            for match in result.matches:
                key = match.concept_label
                if key not in matches_by_concept:
                    matches_by_concept[key] = []
                matches_by_concept[key].append(match)
            
            for concept_label, concept_matches in matches_by_concept.items():
                report_lines.append(f"### {concept_label}")
                
                # Show definition once
                if concept_matches:
                    first_match = concept_matches[0]
                    report_lines.append(f"**Definition:** {first_match.concept_definition}")
                    report_lines.append(f"**Ontology:** {first_match.concept_ontology}")
                    report_lines.append("")
                
                # Show each match
                for i, match in enumerate(concept_matches, 1):
                    report_lines.extend([
                        f"**Match {i}:**",
                        f"- Text: \"{match.text_passage}\"",
                        f"- Reasoning: {match.reasoning}",
                        f"- Confidence: {match.confidence:.2f}",
                        ""
                    ])
        
        if result.unmatched_concepts:
            report_lines.extend([
                f"## Unmatched Concepts ({len(result.unmatched_concepts)})",
                "",
                "These concepts were checked but did not match any text:",
                ""
            ])
            for concept in result.unmatched_concepts:
                report_lines.append(f"- {concept}")
        
        if result.errors:
            report_lines.extend([
                "",
                "## Errors",
                ""
            ])
            for error in result.errors:
                report_lines.append(f"- {error}")
        
        return "\n".join(report_lines)
