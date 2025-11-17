"""
Dual Capabilities Extractor for ProEthica
Discovers NEW CAPABILITY CLASSES and extracts CAPABILITY INDIVIDUALS from case texts.
Based on Chapter 2 literature emphasizing norm competence and professional competencies.
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
class CandidateCapabilityClass:
    """Represents a potentially new capability class not in the ontology"""
    label: str
    definition: str
    capability_type: Optional[str] = None  # 'technical', 'ethical', 'communicative', 'analytical'
    norm_competence_related: Optional[str] = None  # Which obligations this enables
    skill_level: Optional[str] = None  # 'basic', 'intermediate', 'advanced', 'expert'
    acquisition_method: Optional[str] = None  # How this capability is typically acquired
    examples_from_case: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    is_existing_class: bool = False
    existing_class_uri: Optional[str] = None
    source_text: Optional[str] = None  # Text snippet where this capability is identified


@dataclass
class CapabilityIndividual:
    """Represents a specific capability instance in the case"""
    identifier: str  # Unique identifier for this capability instance
    capability_class: str  # The capability class this belongs to
    possessed_by: str  # Who has this capability (role or specific person)
    capability_statement: str  # The specific competency statement
    case_context: str  # How this capability manifests in the case
    demonstrated_through: Optional[str] = None  # How capability is demonstrated
    proficiency_level: Optional[str] = None  # Level of proficiency shown
    enables_obligations: Optional[str] = None  # Which obligations this capability enables
    temporal_aspect: Optional[str] = None  # When this capability is relevant
    is_existing_class: bool = False
    confidence: float = 0.0
    source_text: Optional[str] = None  # Text snippet where this capability is mentioned


class DualCapabilitiesExtractor:
    """
    Discovers new capability classes and extracts capability individuals from case texts.
    Based on professional ethics literature emphasizing norm competence and professional skills.
    """

    def __init__(self):
        """Initialize with MCP client for existing ontology awareness"""
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            self.mcp_client = get_external_mcp_client()
            self.existing_capability_classes = self._load_existing_capability_classes()
            logger.info(f"Loaded {len(self.existing_capability_classes)} existing capability classes from MCP")
        except Exception as e:
            logger.warning(f"Could not initialize MCP client: {e}")
            self.mcp_client = None
            self.existing_capability_classes = []

        # Set model name
        self.model_name = ModelConfig.get_claude_model("powerful")
        logger.info(f"Will use model: {self.model_name}")

        # Store last raw response for RDF conversion
        self.last_raw_response = None

    def _load_existing_capability_classes(self) -> List[Dict[str, Any]]:
        """Load existing capability classes from the ontology"""
        if not self.mcp_client:
            return []

        try:
            capabilities = self.mcp_client.get_all_capability_entities()
            logger.info(f"Retrieved {len(capabilities)} capability entities from ontology")
            return capabilities
        except Exception as e:
            logger.error(f"Failed to load capability classes: {e}")
            return []

    def extract_dual_capabilities(self, case_text: str, case_id: int, section_type: str = 'discussion') -> Tuple[List[CandidateCapabilityClass], List[CapabilityIndividual]]:
        """
        Extract both new capability classes and capability individuals from case text.

        Args:
            case_text: The case text to analyze
            case_id: The case identifier
            section_type: The section being analyzed (e.g., 'facts', 'discussion')

        Returns:
            Tuple of (candidate_capability_classes, capability_individuals)
        """
        logger.info(f"Starting dual capabilities extraction for case {case_id}, section {section_type}")

        # Create the dual extraction prompt
        prompt = self._create_dual_capabilities_extraction_prompt(case_text, section_type)

        # Call LLM for extraction
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        if not extraction_result:
            logger.warning("No extraction result from LLM")
            return [], []

        # Parse the extracted capabilities
        candidate_classes = self._parse_candidate_capability_classes(extraction_result.get('new_capability_classes', []), case_id)
        individuals = self._parse_capability_individuals(extraction_result.get('capability_individuals', []), case_id, section_type)

        # Link individuals to their classes
        self._link_individuals_to_classes(individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate capability classes and {len(individuals)} capability individuals")

        return candidate_classes, individuals

    def _create_dual_capabilities_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for dual capability extraction"""

        # Format existing capabilities for context
        existing_capabilities_text = ""
        if self.existing_capability_classes:
            existing_capabilities_text = "\n".join([
                f"- {cap['label']}: {cap.get('description', cap.get('definition', ''))}"
                for cap in self.existing_capability_classes[:15]  # Limit to avoid token overflow
            ])
            existing_capabilities_text = f"""
EXISTING CAPABILITIES IN ONTOLOGY (check if your identified capabilities match these before creating new classes):
{existing_capabilities_text}
"""

        prompt = f"""You are an expert in professional ethics analyzing a case for capabilities (competencies and skills required for professional practice).

Based on the literature:
- Capabilities are COMPETENCIES that enable norm compliance (Hallamaa & Kalliokoski 2022)
- They represent the skills needed to fulfill professional obligations (Dennis et al. 2016)
- Capabilities include technical, ethical, communicative, and analytical competencies
- They constitute "norm competence" - the ability to act ethically (Kong et al. 2020)

Your task is to:
1. Identify NEW CAPABILITY CLASSES not in the existing ontology
2. Extract SPECIFIC CAPABILITY INDIVIDUALS from the case

{existing_capabilities_text}

Analyze this {section_type} section:

{case_text}

Extract capabilities following this JSON structure:

{{
  "new_capability_classes": [
    {{
      "label": "Clear, specific capability class name",
      "definition": "What competency or skill this capability represents",
      "capability_type": "technical|ethical|communicative|analytical",
      "norm_competence_related": "Which professional obligations this capability enables",
      "skill_level": "basic|intermediate|advanced|expert",
      "acquisition_method": "How this capability is typically acquired (education, training, experience)",
      "examples_from_case": ["Example 1 from the case", "Example 2"],
      "source_text": "EXACT text snippet from case where this capability is identified (max 200 characters)",
      "confidence": 0.0-1.0,
      "reasoning": "Why this is a new class not in existing ontology"
    }}
  ],
  "capability_individuals": [
    {{
      "identifier": "Unique name for this specific capability instance",
      "capability_class": "Name of the capability class (new or existing)",
      "possessed_by": "Who has this capability (e.g., 'Engineer L', 'All Licensed PEs')",
      "capability_statement": "The specific competency (e.g., 'Design stormwater systems')",
      "demonstrated_through": "How shown in the case (e.g., 'Years of experience', 'Professional license')",
      "proficiency_level": "basic|intermediate|advanced|expert",
      "enables_obligations": "Which obligations this capability enables",
      "temporal_aspect": "When this capability is relevant",
      "case_context": "How this capability manifests in the specific case",
      "source_text": "EXACT text snippet from case where this capability is mentioned (max 200 characters)",
      "is_existing_class": true/false,
      "confidence": 0.0-1.0
    }}
  ]
}}

Focus on:
1. NEW capability types that represent novel competencies
2. Specific capability instances showing professional competencies in this case
3. The relationship between capabilities and norm competence
4. How capabilities enable fulfillment of professional obligations

Return ONLY the JSON structure, no additional text."""

        return prompt

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM and parse the dual extraction response"""
        try:
            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError:
                logger.error("Could not import get_llm_client")
                return {"new_capability_classes": [], "capability_individuals": []}

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available for dual capabilities extraction")
                return {"new_capability_classes": [], "capability_individuals": []}

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

    def _parse_candidate_capability_classes(self, capability_classes: List[Dict], case_id: int) -> List[CandidateCapabilityClass]:
        """Parse candidate capability classes from extraction results"""
        candidates = []

        for cap_class in capability_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = cap_class.get('source_text')
                if not source_text and cap_class.get('examples_from_case'):
                    source_text = cap_class.get('examples_from_case', [''])[0]

                candidate = CandidateCapabilityClass(
                    label=cap_class.get('label', 'Unknown Capability'),
                    definition=cap_class.get('definition', ''),
                    capability_type=cap_class.get('capability_type', 'technical'),
                    norm_competence_related=cap_class.get('norm_competence_related'),
                    skill_level=cap_class.get('skill_level', 'intermediate'),
                    acquisition_method=cap_class.get('acquisition_method'),
                    examples_from_case=cap_class.get('examples_from_case', []),
                    confidence=float(cap_class.get('confidence', 0.8)),
                    reasoning=cap_class.get('reasoning', ''),
                    is_existing_class=False,
                    source_text=source_text
                )

                # Check if this matches an existing class
                for existing in self.existing_capability_classes:
                    if self._capabilities_match(candidate.label, existing['label']):
                        candidate.is_existing_class = True
                        candidate.existing_class_uri = existing.get('uri')
                        break

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Failed to parse capability class: {e}")
                continue

        return candidates

    def _parse_capability_individuals(self, individuals: List[Dict], case_id: int, section_type: str) -> List[CapabilityIndividual]:
        """Parse capability individuals from extraction results"""
        parsed_individuals = []

        for indiv in individuals:
            try:
                individual = CapabilityIndividual(
                    identifier=indiv.get('identifier', f"Capability_{case_id}_{len(parsed_individuals)}"),
                    capability_class=indiv.get('capability_class', 'Capability'),
                    possessed_by=indiv.get('possessed_by', 'Unknown'),
                    capability_statement=indiv.get('capability_statement', ''),
                    case_context=indiv.get('case_context', f"From {section_type} section"),
                    demonstrated_through=indiv.get('demonstrated_through'),
                    proficiency_level=indiv.get('proficiency_level', 'intermediate'),
                    enables_obligations=indiv.get('enables_obligations'),
                    temporal_aspect=indiv.get('temporal_aspect'),
                    is_existing_class=indiv.get('is_existing_class', False),
                    confidence=float(indiv.get('confidence', 0.85)),
                    source_text=indiv.get('source_text')
                )

                parsed_individuals.append(individual)

            except Exception as e:
                logger.error(f"Failed to parse capability individual: {e}")
                continue

        return parsed_individuals

    def _capabilities_match(self, label1: str, label2: str) -> bool:
        """Check if two capability labels match (case-insensitive, ignoring minor differences)"""
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

    def _link_individuals_to_classes(self, individuals: List[CapabilityIndividual], candidate_classes: List[CandidateCapabilityClass]):
        """Link capability individuals to their appropriate classes"""
        for individual in individuals:
            # First check if it links to a new candidate class
            for candidate in candidate_classes:
                if self._capabilities_match(individual.capability_class, candidate.label):
                    individual.is_existing_class = False
                    break
            else:
                # Check if it links to an existing class
                for existing in self.existing_capability_classes:
                    if self._capabilities_match(individual.capability_class, existing['label']):
                        individual.is_existing_class = True
                        break

    def get_last_raw_response(self) -> Optional[str]:
        """Get the last raw LLM response for RDF conversion"""
        return self.last_raw_response