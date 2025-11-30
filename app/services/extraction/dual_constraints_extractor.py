"""
Dual Constraints Extractor for ProEthica
Discovers NEW CONSTRAINT CLASSES and extracts CONSTRAINT INDIVIDUALS from case texts.
Based on Chapter 2 literature and professional ethics framework.
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
class CandidateConstraintClass:
    """Represents a potentially new constraint class not in the ontology"""
    label: str
    definition: str
    constraint_type: Optional[str] = None  # 'legal', 'physical', 'resource', 'temporal', 'procedural'
    flexibility: Optional[str] = None  # 'hard', 'soft', 'negotiable'
    violation_impact: Optional[str] = None  # Impact if constraint is violated
    mitigation_possible: Optional[str] = None  # Whether mitigation is possible
    examples_from_case: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    is_existing_class: bool = False
    existing_class_uri: Optional[str] = None
    source_text: Optional[str] = None  # Text snippet where this constraint is identified


@dataclass
class ConstraintIndividual:
    """Represents a specific constraint instance in the case"""
    identifier: str  # Unique identifier for this constraint instance
    constraint_class: str  # The constraint class this belongs to
    constrained_entity: str  # What/who is constrained (e.g., 'Engineer L', 'Development Project')
    constraint_statement: str  # The specific limitation or restriction
    case_context: str  # How this constraint manifests in the case
    source: Optional[str] = None  # Source of constraint (e.g., 'Budget', 'Regulations', 'Physics')
    enforcement_mechanism: Optional[str] = None  # How constraint is enforced
    temporal_scope: Optional[str] = None  # When the constraint applies
    severity: Optional[str] = None  # 'critical', 'major', 'minor'
    is_existing_class: bool = False
    confidence: float = 0.0
    source_text: Optional[str] = None  # Text snippet where this constraint is mentioned


class DualConstraintsExtractor:
    """
    Discovers new constraint classes and extracts constraint individuals from case texts.
    Based on professional ethics literature emphasizing boundaries and limitations.
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
            self.existing_constraint_classes = self._load_existing_constraint_classes()
            logger.info(f"Loaded {len(self.existing_constraint_classes)} existing constraint classes from MCP")
        except Exception as e:
            logger.warning(f"Could not initialize MCP client: {e}")
            self.mcp_client = None
            self.existing_constraint_classes = []

        # Set model name
        self.model_name = ModelConfig.get_claude_model("powerful")
        logger.info(f"Will use model: {self.model_name}")

        # Store last raw response for RDF conversion
        self.last_raw_response = None
        self.last_prompt = None  # Store the prompt sent to LLM

    def _load_existing_constraint_classes(self) -> List[Dict[str, Any]]:
        """Load existing constraint classes from the ontology"""
        if not self.mcp_client:
            return []

        try:
            constraints = self.mcp_client.get_all_constraint_entities()
            logger.info(f"Retrieved {len(constraints)} constraint entities from ontology")
            return constraints
        except Exception as e:
            logger.error(f"Failed to load constraint classes: {e}")
            return []

    def extract_dual_constraints(self, case_text: str, case_id: int, section_type: str = 'discussion') -> Tuple[List[CandidateConstraintClass], List[ConstraintIndividual]]:
        """
        Extract both new constraint classes and constraint individuals from case text.

        Args:
            case_text: The case text to analyze
            case_id: The case identifier
            section_type: The section being analyzed (e.g., 'facts', 'discussion')

        Returns:
            Tuple of (candidate_constraint_classes, constraint_individuals)
        """
        logger.info(f"Starting dual constraints extraction for case {case_id}, section {section_type}")

        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # Create the dual extraction prompt
        prompt = self._create_dual_constraints_extraction_prompt(case_text, section_type)

        # Call LLM for extraction
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        if not extraction_result:
            logger.warning("No extraction result from LLM")
            return [], []

        # Parse the extracted constraints
        candidate_classes = self._parse_candidate_constraint_classes(extraction_result.get('new_constraint_classes', []), case_id)
        individuals = self._parse_constraint_individuals(extraction_result.get('constraint_individuals', []), case_id, section_type)

        # Link individuals to their classes
        self._link_individuals_to_classes(individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate constraint classes and {len(individuals)} constraint individuals")

        return candidate_classes, individuals

    def _create_dual_constraints_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for dual constraint extraction"""

        # Format existing constraints for context
        existing_constraints_text = ""
        if self.existing_constraint_classes:
            existing_constraints_text = "\n".join([
                f"- {cons['label']}: {cons.get('description', cons.get('definition', ''))}"
                for cons in self.existing_constraint_classes[:15]  # Limit to avoid token overflow
            ])
            existing_constraints_text = f"""
EXISTING CONSTRAINTS IN ONTOLOGY (check if your identified constraints match these before creating new classes):
{existing_constraints_text}
"""

        prompt = f"""You are an expert in professional ethics analyzing a case for constraints (boundaries, limitations, and restrictions).

Based on the literature:
- Constraints are INVIOLABLE BOUNDARIES that limit acceptable actions (Dennis et al. 2016)
- They differ from obligations by being restrictions rather than requirements
- Constraints can be legal, physical, resource-based, or procedural
- They define the space within which ethical decisions must be made

Your task is to:
1. Identify NEW CONSTRAINT CLASSES not in the existing ontology
2. Extract SPECIFIC CONSTRAINT INDIVIDUALS from the case

{existing_constraints_text}

Analyze this {section_type} section:

{case_text}

Extract constraints following this JSON structure:

{{
  "new_constraint_classes": [
    {{
      "label": "Clear, specific constraint class name",
      "definition": "What this type of constraint limits or restricts",
      "constraint_type": "legal|physical|resource|temporal|procedural",
      "flexibility": "hard|soft|negotiable",
      "violation_impact": "What happens if this constraint is violated",
      "mitigation_possible": "Whether and how this constraint can be mitigated",
      "examples_from_case": ["Example 1 from the case", "Example 2"],
      "source_text": "EXACT text snippet from case where this constraint is identified (max 200 characters)",
      "confidence": 0.0-1.0,
      "reasoning": "Why this is a new class not in existing ontology"
    }}
  ],
  "constraint_individuals": [
    {{
      "identifier": "Unique name for this specific constraint instance",
      "constraint_class": "Name of the constraint class (new or existing)",
      "constrained_entity": "What or who is constrained (e.g., 'Engineer L', 'Project')",
      "constraint_statement": "The specific limitation (e.g., 'Cannot exceed budget of $X')",
      "source": "Origin of constraint (e.g., 'Client budget', 'Environmental law')",
      "enforcement_mechanism": "How this constraint is enforced",
      "temporal_scope": "When this constraint applies",
      "severity": "critical|major|minor",
      "case_context": "How this constraint manifests in the specific case",
      "source_text": "EXACT text snippet from case where this constraint is mentioned (max 200 characters)",
      "is_existing_class": true/false,
      "confidence": 0.0-1.0
    }}
  ]
}}

Focus on:
1. NEW constraint types that represent novel limitations or boundaries
2. Specific constraint instances showing how limitations apply in this case
3. The difference between constraints (boundaries) and obligations (duties)
4. Impact and severity of constraints on decision-making

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
                    extraction_type='constraints',
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
                    return {"new_constraint_classes": [], "constraint_individuals": []}

            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError:
                logger.error("Could not import get_llm_client")
                return {"new_constraint_classes": [], "constraint_individuals": []}

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available for dual constraints extraction")
                return {"new_constraint_classes": [], "constraint_individuals": []}

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

    def _parse_candidate_constraint_classes(self, constraint_classes: List[Dict], case_id: int) -> List[CandidateConstraintClass]:
        """Parse candidate constraint classes from extraction results"""
        candidates = []

        for cons_class in constraint_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = cons_class.get('source_text')
                if not source_text and cons_class.get('examples_from_case'):
                    source_text = cons_class.get('examples_from_case', [''])[0]

                candidate = CandidateConstraintClass(
                    label=cons_class.get('label', 'Unknown Constraint'),
                    definition=cons_class.get('definition', ''),
                    constraint_type=cons_class.get('constraint_type', 'resource'),
                    flexibility=cons_class.get('flexibility', 'hard'),
                    violation_impact=cons_class.get('violation_impact'),
                    mitigation_possible=cons_class.get('mitigation_possible'),
                    examples_from_case=cons_class.get('examples_from_case', []),
                    confidence=float(cons_class.get('confidence', 0.8)),
                    reasoning=cons_class.get('reasoning', ''),
                    is_existing_class=False,
                    source_text=source_text
                )

                # Check if this matches an existing class
                for existing in self.existing_constraint_classes:
                    if self._constraints_match(candidate.label, existing['label']):
                        candidate.is_existing_class = True
                        candidate.existing_class_uri = existing.get('uri')
                        break

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Failed to parse constraint class: {e}")
                continue

        return candidates

    def _parse_constraint_individuals(self, individuals: List[Dict], case_id: int, section_type: str) -> List[ConstraintIndividual]:
        """Parse constraint individuals from extraction results"""
        parsed_individuals = []

        for indiv in individuals:
            try:
                individual = ConstraintIndividual(
                    identifier=indiv.get('identifier', f"Constraint_{case_id}_{len(parsed_individuals)}"),
                    constraint_class=indiv.get('constraint_class', 'Constraint'),
                    constrained_entity=indiv.get('constrained_entity', 'Unknown'),
                    constraint_statement=indiv.get('constraint_statement', ''),
                    source=indiv.get('source'),
                    enforcement_mechanism=indiv.get('enforcement_mechanism'),
                    temporal_scope=indiv.get('temporal_scope'),
                    severity=indiv.get('severity', 'major'),
                    case_context=indiv.get('case_context', f"From {section_type} section"),
                    is_existing_class=indiv.get('is_existing_class', False),
                    confidence=float(indiv.get('confidence', 0.85)),
                    source_text=indiv.get('source_text')
                )

                parsed_individuals.append(individual)

            except Exception as e:
                logger.error(f"Failed to parse constraint individual: {e}")
                continue

        return parsed_individuals

    def _constraints_match(self, label1: str, label2: str) -> bool:
        """Check if two constraint labels match (case-insensitive, ignoring minor differences)"""
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

    def _link_individuals_to_classes(self, individuals: List[ConstraintIndividual], candidate_classes: List[CandidateConstraintClass]):
        """Link constraint individuals to their appropriate classes"""
        for individual in individuals:
            # First check if it links to a new candidate class
            for candidate in candidate_classes:
                if self._constraints_match(individual.constraint_class, candidate.label):
                    individual.is_existing_class = False
                    break
            else:
                # Check if it links to an existing class
                for existing in self.existing_constraint_classes:
                    if self._constraints_match(individual.constraint_class, existing['label']):
                        individual.is_existing_class = True
                        break

    def get_last_raw_response(self) -> Optional[str]:
        """Get the last raw LLM response for RDF conversion"""
        return self.last_raw_response