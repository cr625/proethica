"""
Dual Obligations Extractor for ProEthica
Discovers NEW OBLIGATION CLASSES and extracts OBLIGATION INDIVIDUALS from case texts.
Based on Chapter 2.2.3 literature and NSPE framework.
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import json
import re
from datetime import datetime
from dataclasses import dataclass, field

from models import ModelConfig

logger = logging.getLogger(__name__)


@dataclass
class CandidateObligationClass:
    """Represents a potentially new obligation class not in the ontology"""
    label: str
    definition: str
    derived_from_principle: Optional[str] = None  # Which principle this operationalizes
    duty_type: Optional[str] = None  # 'professional', 'legal', 'ethical', 'societal'
    enforcement_mechanism: Optional[str] = None  # How the obligation is enforced
    violation_consequences: Optional[str] = None  # What happens if violated
    examples_from_case: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    is_existing_class: bool = False
    existing_class_uri: Optional[str] = None
    source_text: Optional[str] = None  # Text snippet where this obligation is identified


@dataclass
class ObligationIndividual:
    """Represents a specific obligation instance in the case"""
    identifier: str  # Unique identifier for this obligation instance
    obligation_class: str  # The obligation class this belongs to
    obligated_party: str  # Who has this obligation (role or specific person)
    obligation_statement: str  # The specific duty statement
    case_context: str  # How this obligation manifests in the case
    derived_from: Optional[str] = None  # Principle or law this comes from
    enforcement_context: Optional[str] = None  # How it's enforced in this case
    temporal_scope: Optional[str] = None  # When the obligation applies
    compliance_status: Optional[str] = None  # Met, unmet, unclear
    is_existing_class: bool = False
    confidence: float = 0.0
    source_text: Optional[str] = None  # Text snippet where this obligation is mentioned


class DualObligationsExtractor:
    """
    Discovers new obligation classes and extracts obligation individuals from case texts.
    Based on professional ethics literature emphasizing concrete duties derived from principles.
    """

    def __init__(self, llm_client=None):
        """
        Initialize with MCP client for existing ontology awareness.

        Args:
            llm_client: Optional LLM client for dependency injection (used in testing).
                       If None and MOCK_LLM_ENABLED=true, uses mock client.
                       Otherwise uses the default LLM client from llm_utils.
        """
        # Use mock provider to get appropriate client (mock if enabled, None otherwise)
        from app.services.extraction.mock_llm_provider import (
            get_llm_client_for_extraction,
            get_current_data_source,
            DataSource
        )
        self.llm_client = get_llm_client_for_extraction(llm_client)
        self.data_source = get_current_data_source()
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            self.mcp_client = get_external_mcp_client()
            self.existing_obligation_classes = self._load_existing_obligation_classes()
            logger.info(f"Loaded {len(self.existing_obligation_classes)} existing obligation classes from MCP")
        except Exception as e:
            logger.warning(f"Could not initialize MCP client: {e}")
            self.mcp_client = None
            self.existing_obligation_classes = []

        # Set model name
        self.model_name = ModelConfig.get_claude_model("powerful")
        logger.info(f"Will use model: {self.model_name}")

        # Store last raw response for RDF conversion
        self.last_raw_response = None
        self.last_prompt = None  # Store the prompt sent to LLM

    def _load_existing_obligation_classes(self) -> List[Dict[str, Any]]:
        """Load existing obligation classes from the ontology"""
        if not self.mcp_client:
            return []

        try:
            obligations = self.mcp_client.get_all_obligation_entities()
            logger.info(f"Retrieved {len(obligations)} obligation entities from ontology")
            return obligations
        except Exception as e:
            logger.error(f"Failed to load obligation classes: {e}")
            return []

    def extract_dual_obligations(self, case_text: str, case_id: int, section_type: str = 'discussion') -> Tuple[List[CandidateObligationClass], List[ObligationIndividual]]:
        """
        Extract both new obligation classes and obligation individuals from case text.

        Args:
            case_text: The case text to analyze
            case_id: The case identifier
            section_type: The section being analyzed (e.g., 'questions', 'discussion')

        Returns:
            Tuple of (candidate_obligation_classes, obligation_individuals)
        """
        logger.info(f"Starting dual obligations extraction for case {case_id}, section {section_type}")

        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # Create the dual extraction prompt
        prompt = self._create_dual_obligations_extraction_prompt(case_text, section_type)

        # Call LLM for extraction
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        if not extraction_result:
            logger.warning("No extraction result from LLM")
            return [], []

        # Parse the extracted obligations
        candidate_classes = self._parse_candidate_obligation_classes(extraction_result.get('new_obligation_classes', []), case_id)
        individuals = self._parse_obligation_individuals(extraction_result.get('obligation_individuals', []), case_id, section_type)

        # Link individuals to their classes
        self._link_individuals_to_classes(individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate obligation classes and {len(individuals)} obligation individuals")

        return candidate_classes, individuals

    def _create_dual_obligations_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for dual obligation extraction"""

        # Format existing obligations for context
        existing_obligations_text = ""
        if self.existing_obligation_classes:
            existing_obligations_text = "\n".join([
                f"- {obs['label']}: {obs.get('description', obs.get('definition', ''))}"
                for obs in self.existing_obligation_classes[:20]  # Limit to avoid token overflow
            ])
            existing_obligations_text = f"""
EXISTING OBLIGATIONS IN ONTOLOGY (check if your identified obligations match these before creating new classes):
{existing_obligations_text}
"""

        prompt = f"""You are an expert in professional ethics analyzing a case for obligations (professional duties and requirements).

Based on the literature:
- Obligations are CONCRETE PROFESSIONAL DUTIES derived from abstract principles (Hallamaa & Kalliokoski 2022)
- They specify what professionals MUST, SHOULD, or MUST NOT do (Dennis et al. 2016)
- Obligations have deontic force and are enforceable (Wooldridge & Jennings 1995)
- They operationalize principles in specific contexts (Kong et al. 2020)

Your task is to:
1. Identify NEW OBLIGATION CLASSES not in the existing ontology
2. Extract SPECIFIC OBLIGATION INDIVIDUALS from the case

{existing_obligations_text}

Analyze this {section_type} section:

{case_text}

Extract obligations following this JSON structure:

{{
  "new_obligation_classes": [
    {{
      "label": "Clear, specific obligation class name",
      "definition": "What this type of obligation requires professionals to do",
      "derived_from_principle": "Which principle this operationalizes (e.g., 'Public Safety', 'Honesty')",
      "duty_type": "professional|legal|ethical|societal",
      "enforcement_mechanism": "How this obligation is typically enforced",
      "violation_consequences": "What happens when this obligation is violated",
      "examples_from_case": ["Example 1 from the case", "Example 2"],
      "source_text": "EXACT text snippet from case where this obligation is identified (max 200 characters)",
      "confidence": 0.0-1.0,
      "reasoning": "Why this is a new class not in existing ontology"
    }}
  ],
  "obligation_individuals": [
    {{
      "identifier": "Unique name for this specific obligation instance",
      "obligation_class": "Name of the obligation class (new or existing)",
      "obligated_party": "Who has this obligation (e.g., 'Engineer L', 'All Licensed PEs')",
      "obligation_statement": "The specific duty statement (e.g., 'Report safety risks to authorities')",
      "derived_from": "Source principle or law (e.g., 'NSPE Code', 'State Law')",
      "enforcement_context": "How enforced in this case",
      "temporal_scope": "When this obligation applies",
      "compliance_status": "met|unmet|unclear|pending",
      "case_context": "How this obligation manifests in the specific case",
      "source_text": "EXACT text snippet from case where this obligation is mentioned (max 200 characters)",
      "is_existing_class": true/false,
      "confidence": 0.0-1.0
    }}
  ]
}}

Focus on:
1. NEW obligation types that represent novel professional duties
2. Specific obligation instances showing how duties apply in this case
3. The relationship between obligations and the principles they operationalize
4. Enforcement mechanisms and compliance status

Return ONLY the JSON structure, no additional text."""

        return prompt

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM and parse the dual extraction response"""
        # Store prompt for later retrieval
        self.last_prompt = prompt

        try:
            # Use injected client if available (for testing), otherwise get default
            if self.llm_client is not None:
                # Mock client - call with extraction type for fixture lookup
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type='obligations',
                    section_type=getattr(self, '_current_section_type', 'facts')
                )
                response_text = response.content if hasattr(response, 'content') else str(response)
                self.last_raw_response = response_text
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        return json.loads(json_match.group())
                    return {"new_obligation_classes": [], "obligation_individuals": []}

            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError:
                logger.error("Could not import get_llm_client")
                return {"new_obligation_classes": [], "obligation_individuals": []}

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available for dual obligations extraction")
                return {"new_obligation_classes": [], "obligation_individuals": []}

            # Call the LLM
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text if response.content else ""

            # Store raw response for RDF conversion
            self.last_raw_response = response_text

            logger.debug(f"LLM Response: {response_text[:500]}...")

            # Parse JSON from response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from mixed text
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.error("Could not parse JSON from LLM response")
                    return {}

            return result

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return {}

    def _parse_candidate_obligation_classes(self, obligation_classes: List[Dict], case_id: int) -> List[CandidateObligationClass]:
        """Parse candidate obligation classes from extraction results"""
        candidates = []

        for obl_class in obligation_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = obl_class.get('source_text')
                if not source_text and obl_class.get('examples_from_case'):
                    source_text = obl_class.get('examples_from_case', [''])[0]

                candidate = CandidateObligationClass(
                    label=obl_class.get('label', 'Unknown Obligation'),
                    definition=obl_class.get('definition', ''),
                    derived_from_principle=obl_class.get('derived_from_principle'),
                    duty_type=obl_class.get('duty_type', 'professional'),
                    enforcement_mechanism=obl_class.get('enforcement_mechanism'),
                    violation_consequences=obl_class.get('violation_consequences'),
                    examples_from_case=obl_class.get('examples_from_case', []),
                    confidence=float(obl_class.get('confidence', 0.8)),
                    reasoning=obl_class.get('reasoning', ''),
                    is_existing_class=False,
                    source_text=source_text
                )

                # Check if this matches an existing class
                for existing in self.existing_obligation_classes:
                    if self._obligations_match(candidate.label, existing['label']):
                        candidate.is_existing_class = True
                        candidate.existing_class_uri = existing.get('uri')
                        break

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Failed to parse obligation class: {e}")
                continue

        return candidates

    def _parse_obligation_individuals(self, individuals: List[Dict], case_id: int, section_type: str) -> List[ObligationIndividual]:
        """Parse obligation individuals from extraction results"""
        parsed_individuals = []

        for indiv in individuals:
            try:
                individual = ObligationIndividual(
                    identifier=indiv.get('identifier', f"Obligation_{case_id}_{len(parsed_individuals)}"),
                    obligation_class=indiv.get('obligation_class', 'Obligation'),
                    obligated_party=indiv.get('obligated_party', 'Unknown'),
                    obligation_statement=indiv.get('obligation_statement', ''),
                    derived_from=indiv.get('derived_from'),
                    enforcement_context=indiv.get('enforcement_context'),
                    temporal_scope=indiv.get('temporal_scope'),
                    compliance_status=indiv.get('compliance_status', 'unclear'),
                    case_context=indiv.get('case_context', f"From {section_type} section"),
                    is_existing_class=indiv.get('is_existing_class', False),
                    confidence=float(indiv.get('confidence', 0.85)),
                    source_text=indiv.get('source_text')
                )

                parsed_individuals.append(individual)

            except Exception as e:
                logger.error(f"Failed to parse obligation individual: {e}")
                continue

        return parsed_individuals

    def _obligations_match(self, label1: str, label2: str) -> bool:
        """Check if two obligation labels match (case-insensitive, ignoring minor differences)"""
        # Normalize for comparison
        norm1 = label1.lower().replace('_', ' ').replace('-', ' ')
        norm2 = label2.lower().replace('_', ' ').replace('-', ' ')

        # Exact match
        if norm1 == norm2:
            return True

        # Check if one contains the other (for hierarchical matches)
        if norm1 in norm2 or norm2 in norm1:
            return True

        return False

    def _link_individuals_to_classes(self, individuals: List[ObligationIndividual], candidate_classes: List[CandidateObligationClass]):
        """Link obligation individuals to their appropriate classes"""
        for individual in individuals:
            # First check if it links to a new candidate class
            for candidate in candidate_classes:
                if self._obligations_match(individual.obligation_class, candidate.label):
                    individual.is_existing_class = False
                    break
            else:
                # Check if it links to an existing class
                for existing in self.existing_obligation_classes:
                    if self._obligations_match(individual.obligation_class, existing['label']):
                        individual.is_existing_class = True
                        break

    def get_last_raw_response(self) -> Optional[str]:
        """Get the last raw LLM response for RDF conversion"""
        return self.last_raw_response