"""
Precedent Citation Extractor

Extracts references to prior NSPE BOR cases from Discussion and Conclusions sections.
Precedent cases are cited by the board to establish patterns, support reasoning,
or distinguish the current case from prior decisions.

Part of Step 4 Part A-bis: Precedent Case Citations

Uses Claude to:
1. Identify precedent case citations (variable formats: "BOR Case 79-5", "Case 92-7", etc.)
2. Extract case metadata (number, title, year)
3. Determine relevance (why did the board cite this case?)
4. Link to related provisions/questions/conclusions

Stores as RDF triples in temporary_rdf_storage with:
- extraction_type: 'precedent_case_reference'
- entity_type: 'resources' (precedents are authoritative resources)
- ontology_target: 'proethica-case-{id}'
- rdf_json_ld: PrecedentCaseReference structure
"""

import logging
import re
import json
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PrecedentCitation:
    """A reference to a prior NSPE BOR case."""
    case_number: str  # e.g., "79-5", "92-7", "2005-10"
    case_title: str  # Brief description
    full_citation: str  # Complete citation text
    year_decided: Optional[int]  # Extracted year if available
    citation_context: str  # Where/how it's cited
    relevance_reasoning: str  # Why the board cited it
    related_provisions: List[str]  # NSPE Code sections mentioned with this case
    mentioned_in_section: str  # Usually "references"
    confidence: float  # 0-1, how confident we are this is a precedent case

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'caseNumber': self.case_number,
            'caseTitle': self.case_title,
            'fullCitation': self.full_citation,
            'yearDecided': self.year_decided,
            'citationContext': self.citation_context,
            'relevanceReasoning': self.relevance_reasoning,
            'relatedProvisions': self.related_provisions,
            'mentionedInSection': self.mentioned_in_section,
            'confidence': self.confidence
        }


class PrecedentCitationExtractor:
    """
    Extracts precedent case citations from case References section.

    Uses Claude Sonnet 4.5 to identify and analyze case citations, handling
    variable formats and determining relevance to current case analysis.
    """

    def __init__(self, llm_client):
        """
        Initialize extractor with LLM client.

        Args:
            llm_client: Claude client for citation extraction and analysis
        """
        self.llm_client = llm_client
        self.last_prompt = None
        self.last_response = None

    def extract_precedent_citations(
        self,
        references_text: str,
        case_context: Optional[Dict] = None
    ) -> List[PrecedentCitation]:
        """
        Extract precedent case citations from Discussion and Conclusions sections.

        Args:
            references_text: Text from Discussion and Conclusions sections
            case_context: Optional context (questions, conclusions, provisions)

        Returns:
            List of PrecedentCitation objects
        """
        if not references_text or len(references_text.strip()) < 50:
            logger.warning("[Precedent Extractor] Case text too short or empty")
            return []

        logger.info(f"[Precedent Extractor] Analyzing {len(references_text)} chars of case text")

        # Build context summary if provided
        context_summary = ""
        if case_context:
            provisions = case_context.get('provisions', [])
            questions = case_context.get('questions', [])
            conclusions = case_context.get('conclusions', [])

            if provisions:
                context_summary += f"\n\nCode Provisions Referenced:\n"
                for p in provisions[:5]:  # Limit for token efficiency
                    context_summary += f"- {p}\n"

            if questions:
                context_summary += f"\n\nEthical Questions:\n"
                for q in questions[:3]:
                    context_summary += f"- {q}\n"

        # Build LLM prompt
        prompt = self._build_extraction_prompt(references_text, context_summary)

        try:
            # Call Claude for extraction
            logger.info("[Precedent Extractor] Calling LLM for precedent citation extraction...")
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            response_text = response.content[0].text
            logger.debug(f"[Precedent Extractor] Response length: {len(response_text)} chars")

            # Store for SSE display
            self.last_prompt = prompt
            self.last_response = response_text

            # Extract JSON from response
            json_text = self._extract_json_from_response(response_text)

            # Log extracted JSON for debugging
            logger.debug(f"[Precedent Extractor] Extracted JSON: {json_text[:500]}...")

            # Parse JSON response
            citations_data = json.loads(json_text)

            # Convert to PrecedentCitation objects
            citations = []
            for cite_data in citations_data.get('precedent_citations', []):
                citation = PrecedentCitation(
                    case_number=cite_data.get('case_number', ''),
                    case_title=cite_data.get('case_title', ''),
                    full_citation=cite_data.get('full_citation', ''),
                    year_decided=cite_data.get('year_decided'),
                    citation_context=cite_data.get('citation_context', ''),
                    relevance_reasoning=cite_data.get('relevance_reasoning', ''),
                    related_provisions=cite_data.get('related_provisions', []),
                    mentioned_in_section='references',
                    confidence=cite_data.get('confidence', 0.9)
                )
                citations.append(citation)

            logger.info(f"[Precedent Extractor] Extracted {len(citations)} precedent citations")
            return citations

        except json.JSONDecodeError as e:
            logger.error(f"[Precedent Extractor] Failed to parse LLM JSON: {e}")
            return []
        except Exception as e:
            logger.error(f"[Precedent Extractor] Error extracting precedent citations: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _build_extraction_prompt(self, references_text: str, context_summary: str) -> str:
        """Build LLM prompt for precedent citation extraction."""
        return f"""You are analyzing an NSPE Board of Ethical Review case to find precedent case citations.

Your task: Extract ALL precedent case citations (references to prior BOR cases).

**Case Text (Discussion and Conclusions sections):**
{references_text}

**Case Context (for relevance analysis):**
{context_summary}

**Instructions:**

1. **Identify precedent cases**: Look for references to prior NSPE Board of Ethical Review cases in various formats:
   - "BER Case 84-5" (Board of Ethical Review)
   - "BOR Case 79-5" (Board of Review - older name)
   - "Case 92-7"
   - "NSPE Case No. 2005-10"
   - "In Case 89-3, we held that..."
   - Any reference to a numbered BER/BOR case decision

   **IMPORTANT**: Most cases use "BER" (Board of Ethical Review), not "BOR"!

2. **Extract for EACH precedent case**:
   - case_number: The case number (e.g., "79-5", "92-7")
   - case_title: Brief description/subject of the case
   - full_citation: Complete citation text as it appears
   - year_decided: Extracted year if available (from case number or text)
   - citation_context: Where/how is this case cited? (direct quote or paraphrase)
   - relevance_reasoning: WHY did the board cite this case? What does it establish/distinguish?
   - related_provisions: Any NSPE Code sections mentioned in connection with this case
   - confidence: 0-1 score for how confident you are this is a precedent case

3. **Focus on RELEVANCE**: For each case, explain:
   - Does it SUPPORT the board's reasoning?
   - Is it DISTINGUISHED (similar facts, different conclusion)?
   - Does it establish a PATTERN or PRINCIPLE?

4. **Output ONLY valid JSON** (no markdown, no explanation):

{{
  "precedent_citations": [
    {{
      "case_number": "84-5",
      "case_title": "Engineer's Obligation to Advise Client on Project Success",
      "full_citation": "BER Case 84-5",
      "year_decided": 1984,
      "citation_context": "Referenced in discussion of Code section III.1.b requirements to advise clients when a project will be unsuccessful",
      "relevance_reasoning": "Establishes that engineers must not abandon their ethical duty to the public when client raises cost concerns",
      "related_provisions": ["III.1.b", "II.1.a"],
      "confidence": 0.95
    }}
  ]
}}

**IMPORTANT**:
- Return ONLY JSON (no markdown code blocks, no explanation)
- Empty array if no precedent cases found
- Only include actual BOR case citations, not general references to codes/statutes
- Focus on NSPE Board of Ethical Review cases specifically
"""

    def _extract_json_from_response(self, response_text: str) -> str:
        """Extract JSON from LLM response, handling markdown code blocks."""
        import re

        # Try to find JSON in markdown code blocks first
        json_match = re.search(r'```json\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()

        # Try generic code block
        code_match = re.search(r'```\s*\n(.*?)\n```', response_text, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try to find JSON object directly
        json_obj_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_obj_match:
            return json_obj_match.group(0).strip()

        # If all else fails, return raw text
        logger.warning("[Precedent Extractor] Could not extract JSON from response, trying raw text")
        return response_text.strip()
