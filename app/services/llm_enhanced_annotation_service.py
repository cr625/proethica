"""
LLM-Enhanced Annotation Service

Implements intelligent term extraction and semantic matching using LLM capabilities
to dramatically improve annotation matching between text and ontology concepts.

Two-stage approach:
1. Extract key ethical/professional terms from text using LLM
2. Use LLM to semantically compare extracted terms against ontology concept definitions
"""

import logging
import json
import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from app.services.ontserve_annotation_service import OntServeAnnotationService
from app.services.unified_agent_service import UnifiedAgentService

logger = logging.getLogger(__name__)


@dataclass
class ExtractedTerm:
    """Represents a term extracted from text."""
    term: str
    context: str  # Surrounding text for context
    start_offset: int
    end_offset: int
    importance_score: float = 0.0
    term_type: str = "general"  # ethical, professional, technical, etc.


@dataclass  
class SemanticMatch:
    """Represents a semantic match between extracted term and ontology concept."""
    extracted_term: ExtractedTerm
    concept_uri: str
    concept_label: str
    concept_definition: str
    concept_ontology: str
    similarity_score: float
    reasoning: str
    confidence: str  # high, medium, low
    match_type: str  # exact, semantic, contextual


@dataclass
class EnhancedAnnotationResult:
    """Result of enhanced annotation process."""
    total_terms_extracted: int
    successful_matches: int
    failed_matches: int
    ontology_gaps: List[str]  # Terms that couldn't be matched
    matches: List[SemanticMatch]
    processing_time_ms: int
    errors: List[str] = field(default_factory=list)


class LLMEnhancedAnnotationService:
    """
    Enhanced annotation service using LLM for intelligent term extraction
    and semantic matching against ontology definitions.
    """
    
    def __init__(self):
        self.ontserve_service = OntServeAnnotationService()
        self.llm_service = UnifiedAgentService()
        self.cache = {}
        
    def annotate_text(self, text: str, world_id: int = 1, 
                     target_ontologies: Optional[List[str]] = None) -> EnhancedAnnotationResult:
        """
        Perform enhanced annotation on text using LLM-powered semantic matching.
        
        Args:
            text: Text to annotate
            world_id: World ID for ontology mapping
            target_ontologies: Specific ontologies to use (if None, uses world mapping)
            
        Returns:
            EnhancedAnnotationResult with matches and analysis
        """
        start_time = datetime.now()
        
        try:
            # Stage 1: Extract key terms from text
            logger.info("Stage 1: Extracting key terms from text")
            extracted_terms = self._extract_key_terms(text)
            logger.info(f"Extracted {len(extracted_terms)} key terms")
            
            # Get ontology concepts
            if target_ontologies is None:
                ontology_mapping = self.ontserve_service.get_world_ontology_mapping(world_id)
                target_ontologies = list(set(ontology_mapping.values()))  # Remove duplicates
            
            logger.info(f"Using ontologies: {target_ontologies}")
            all_concepts = self.ontserve_service.get_ontology_concepts(target_ontologies)
            
            # Flatten concepts from all ontologies
            flattened_concepts = []
            for ontology_name, concepts in all_concepts.items():
                for concept in concepts:
                    concept['source_ontology'] = ontology_name
                    flattened_concepts.append(concept)
            
            logger.info(f"Loaded {len(flattened_concepts)} concepts from ontologies")
            
            # Stage 2: LLM semantic matching
            logger.info("Stage 2: Performing LLM semantic matching")
            matches = []
            ontology_gaps = []
            
            for term in extracted_terms:
                match = self._find_semantic_match(term, flattened_concepts)
                if match:
                    matches.append(match)
                else:
                    ontology_gaps.append(term.term)
                    
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            result = EnhancedAnnotationResult(
                total_terms_extracted=len(extracted_terms),
                successful_matches=len(matches),
                failed_matches=len(ontology_gaps),
                ontology_gaps=ontology_gaps,
                matches=matches,
                processing_time_ms=int(processing_time)
            )
            
            logger.info(f"Enhanced annotation complete: {len(matches)} matches, {len(ontology_gaps)} gaps")
            return result
            
        except Exception as e:
            logger.exception(f"Error in enhanced annotation: {e}")
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            return EnhancedAnnotationResult(
                total_terms_extracted=0,
                successful_matches=0, 
                failed_matches=0,
                ontology_gaps=[],
                matches=[],
                processing_time_ms=int(processing_time),
                errors=[str(e)]
            )
    
    def _extract_key_terms(self, text: str) -> List[ExtractedTerm]:
        """
        Use LLM to extract key ethical, professional, and technical terms from text.
        """
        extraction_prompt = f"""
You are analyzing text from professional engineering ethics guidelines. Extract key terms that represent:

1. **Ethical principles** (e.g., honesty, integrity, fairness)
2. **Professional obligations** (e.g., competence, confidentiality, public safety)
3. **Stakeholder concepts** (e.g., public, client, employer)
4. **Professional capabilities** (e.g., technical competence, judgment)
5. **Important concepts** (e.g., standards, regulations, responsibility)

Text to analyze:
```
{text[:2000]}  # Limit to first 2000 chars for efficiency
```

Extract 15-25 key terms as a JSON array. For each term, provide:
- "term": the exact term or short phrase (2-4 words max)
- "context": brief surrounding context (10-15 words)
- "start_offset": approximate character position in text
- "importance": score 0.1-1.0 (higher = more central to ethics)
- "type": category (ethical, professional, stakeholder, capability, concept)

Focus on terms that would appear in professional codes of ethics. Avoid generic words.

Return only valid JSON array format.
"""
        
        try:
            response = self.llm_service.process_request(
                extraction_prompt,
                context_type="term_extraction",
                domain="engineering-ethics"
            )
            
            # Parse JSON response
            if isinstance(response, dict) and 'extracted_content' in response:
                content = response['extracted_content']
            else:
                content = str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', content, re.DOTALL)
            if json_match:
                terms_data = json.loads(json_match.group())
                
                extracted_terms = []
                for term_data in terms_data:
                    try:
                        term = ExtractedTerm(
                            term=term_data.get('term', ''),
                            context=term_data.get('context', ''),
                            start_offset=term_data.get('start_offset', 0),
                            end_offset=term_data.get('start_offset', 0) + len(term_data.get('term', '')),
                            importance_score=float(term_data.get('importance', 0.5)),
                            term_type=term_data.get('type', 'general')
                        )
                        extracted_terms.append(term)
                    except Exception as e:
                        logger.warning(f"Error parsing term data: {e}")
                        continue
                        
                return extracted_terms
                
        except Exception as e:
            logger.exception(f"Error in LLM term extraction: {e}")
        
        # Fallback: basic term extraction
        return self._fallback_term_extraction(text)
    
    def _fallback_term_extraction(self, text: str) -> List[ExtractedTerm]:
        """
        Fallback term extraction if LLM fails - uses predefined patterns.
        """
        # Common professional ethics terms
        ethics_patterns = [
            r'\b(public\s+(?:safety|health|welfare|interest))\b',
            r'\b(professional\s+(?:competence|integrity|responsibility|conduct))\b', 
            r'\b(technical\s+(?:competence|expertise|knowledge))\b',
            r'\b(ethical?\s+(?:standards|principles|obligations|conduct))\b',
            r'\b(honesty|integrity|truthfulness|objectivity|impartiality)\b',
            r'\b(confidentiality|conflicts?\s+of\s+interest|disclosure)\b',
            r'\b(client|employer|colleague|profession)\b',
            r'\b(safety|quality|environment|sustainability)\b',
            r'\b(standards?|regulations?|codes?\s+of\s+ethics?)\b'
        ]
        
        extracted_terms = []
        text_lower = text.lower()
        
        for pattern in ethics_patterns:
            for match in re.finditer(pattern, text_lower, re.IGNORECASE):
                term = match.group(1) if match.groups() else match.group(0)
                start_pos = match.start()
                end_pos = match.end()
                
                # Get context (20 chars before and after)
                context_start = max(0, start_pos - 20)
                context_end = min(len(text), end_pos + 20)
                context = text[context_start:context_end].strip()
                
                extracted_term = ExtractedTerm(
                    term=term,
                    context=context,
                    start_offset=start_pos,
                    end_offset=end_pos,
                    importance_score=0.7,  # Default importance
                    term_type="professional"
                )
                extracted_terms.append(extracted_term)
        
        # Remove duplicates
        seen_terms = set()
        unique_terms = []
        for term in extracted_terms:
            if term.term.lower() not in seen_terms:
                seen_terms.add(term.term.lower())
                unique_terms.append(term)
                
        return unique_terms[:20]  # Limit to 20 terms
    
    def _find_semantic_match(self, extracted_term: ExtractedTerm, 
                           concepts: List[Dict[str, Any]]) -> Optional[SemanticMatch]:
        """
        Use LLM to find the best semantic match between extracted term and ontology concepts.
        """
        # Filter concepts that have definitions for better matching
        concepts_with_definitions = [
            c for c in concepts 
            if c.get('definition', '').strip()
        ]
        
        # If no concepts with definitions, use all concepts
        if not concepts_with_definitions:
            concepts_with_definitions = concepts
            
        # Limit to top concepts to avoid overwhelming the LLM
        concepts_to_check = concepts_with_definitions[:15]  # Top 15 concepts
        
        # Build concept descriptions for LLM
        concept_descriptions = []
        for i, concept in enumerate(concepts_to_check):
            label = concept.get('label', 'Unknown')
            definition = concept.get('definition', 'No definition available')
            ontology = concept.get('source_ontology', 'Unknown')
            
            concept_descriptions.append(
                f"{i+1}. **{label}** ({ontology}): {definition[:200]}"
            )
        
        matching_prompt = f"""
You are matching professional ethics terms to ontology concepts. 

**Term to match**: "{extracted_term.term}"
**Context**: "{extracted_term.context}"

**Available ontology concepts**:
{chr(10).join(concept_descriptions)}

Task: Find the BEST semantic match (if any) between the term and the concepts.

Consider:
- Semantic similarity (synonyms, related concepts)
- Professional ethics context
- Definition alignment
- Conceptual relationships

Respond with JSON:
{{
    "best_match": {{
        "concept_number": <number 1-{len(concepts_to_check)} or null>,
        "similarity_score": <0.0-1.0>,
        "confidence": "<high|medium|low>",
        "reasoning": "<brief explanation of why this matches or doesn't match>",
        "match_type": "<exact|semantic|contextual>"
    }}
}}

If similarity_score < 0.4, set concept_number to null (no good match found).
"""
        
        try:
            response = self.llm_service.process_request(
                matching_prompt,
                context_type="semantic_matching", 
                domain="engineering-ethics"
            )
            
            # Parse JSON response
            if isinstance(response, dict) and 'extracted_content' in response:
                content = response['extracted_content']
            else:
                content = str(response)
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                match_data = json.loads(json_match.group())
                best_match = match_data.get('best_match', {})
                
                concept_number = best_match.get('concept_number')
                if concept_number is not None and 1 <= concept_number <= len(concepts_to_check):
                    matched_concept = concepts_to_check[concept_number - 1]
                    
                    return SemanticMatch(
                        extracted_term=extracted_term,
                        concept_uri=matched_concept.get('uri', ''),
                        concept_label=matched_concept.get('label', ''),
                        concept_definition=matched_concept.get('definition', ''),
                        concept_ontology=matched_concept.get('source_ontology', ''),
                        similarity_score=float(best_match.get('similarity_score', 0.0)),
                        reasoning=best_match.get('reasoning', ''),
                        confidence=best_match.get('confidence', 'low'),
                        match_type=best_match.get('match_type', 'semantic')
                    )
                    
        except Exception as e:
            logger.exception(f"Error in LLM semantic matching for term '{extracted_term.term}': {e}")
        
        return None  # No match found
    
    def generate_annotation_report(self, result: EnhancedAnnotationResult) -> str:
        """
        Generate a human-readable report of annotation results.
        """
        report_lines = [
            f"# Enhanced Annotation Report",
            f"",
            f"**Processing Summary:**",
            f"- Terms extracted: {result.total_terms_extracted}",
            f"- Successful matches: {result.successful_matches}",
            f"- Failed matches: {result.failed_matches}",
            f"- Processing time: {result.processing_time_ms:.0f}ms",
            f"",
            f"**Success Rate: {(result.successful_matches/result.total_terms_extracted*100):.1f}%**" if result.total_terms_extracted > 0 else "**Success Rate: 0%**",
            f""
        ]
        
        if result.matches:
            report_lines.extend([
                f"## Successful Matches ({len(result.matches)})",
                f""
            ])
            
            for i, match in enumerate(result.matches, 1):
                report_lines.extend([
                    f"### {i}. \"{match.extracted_term.term}\" → **{match.concept_label}**",
                    f"- **Ontology**: {match.concept_ontology}",
                    f"- **Similarity**: {match.similarity_score:.2f} ({match.confidence} confidence)",
                    f"- **Match Type**: {match.match_type}",
                    f"- **Definition**: {match.concept_definition[:150]}{'...' if len(match.concept_definition) > 150 else ''}",
                    f"- **Reasoning**: {match.reasoning}",
                    f""
                ])
        
        if result.ontology_gaps:
            report_lines.extend([
                f"## Ontology Gaps - Terms Not Matched ({len(result.ontology_gaps)})",
                f"",
                f"These terms were extracted but no good semantic match was found in the ontologies:",
                f""
            ])
            
            for i, gap in enumerate(result.ontology_gaps, 1):
                report_lines.append(f"{i}. \"{gap}\"")
                
            report_lines.extend([
                f"",
                f"*Consider adding these concepts to improve coverage.*"
            ])
        
        return "\n".join(report_lines)