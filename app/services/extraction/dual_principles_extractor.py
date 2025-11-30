"""
Dual Principles Extractor - Discovers both new principle classes and individual principle instances

This service extracts:
1. NEW PRINCIPLE CLASSES: Novel ethical principles not in existing ontology
2. PRINCIPLE INDIVIDUALS: Specific principles invoked/applied in cases

Based on Chapter 2 Section 2.2.2 literature:
- McLaren (2003): Principles require extensional definition through precedents
- Taddeo et al. (2024): Constitutional-like principles requiring interpretation
- Anderson & Anderson (2018): Principles learned from expert examples
- Hallamaa & Kalliokoski (2022): Principles mediate moral ideals into reality
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidatePrincipleClass:
    """Represents a potentially new ethical principle class"""
    label: str
    definition: str
    abstract_nature: str  # The abstract ethical ideal it represents
    extensional_examples: List[str]  # Concrete cases demonstrating the principle
    value_basis: str  # Core moral value underlying the principle
    application_context: List[str]  # Contexts where this principle applies
    operationalization: str  # How to make this principle concrete
    discovered_in_case: int
    confidence: float
    examples_from_case: List[str]
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None
    source_text: Optional[str] = None  # Text snippet where this principle is identified

@dataclass
class PrincipleIndividual:
    """Represents a specific principle invoked/applied in a case"""
    identifier: str  # e.g., "SafetyPrinciple_Case8"
    principle_class: str  # URI of the principle class it instantiates
    concrete_expression: str  # How this principle is expressed in the case
    invoked_by: List[str]  # Who invokes this principle
    applied_to: List[str]  # What situation/decision it applies to
    interpretation: str  # Context-specific interpretation
    balancing_with: List[str]  # Other principles it must be balanced against
    case_section: str
    confidence: float
    is_new_principle_class: bool = False
    source_text: Optional[str] = None  # Text snippet where this principle is mentioned

class DualPrinciplesExtractor:
    """Extract both new principle classes and individual principle instances"""

    def __init__(self, llm_client=None):
        """
        Initialize the dual principles extractor.

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
        self.mcp_client = get_external_mcp_client()
        self.existing_principle_classes = self._load_existing_principle_classes()
        self.model_name = ModelConfig.get_claude_model("powerful")
        self.last_raw_response = None  # CRITICAL for RDF conversion
        self.last_prompt = None  # Store the prompt sent to LLM

    def extract_dual_principles(self, case_text: str, case_id: int, section_type: str) -> Tuple[List[CandidatePrincipleClass], List[PrincipleIndividual]]:
        """
        Extract both new principle classes and individual principle instances from case text

        Returns:
            Tuple of (candidate_principle_classes, principle_individuals)

        Raises:
            ExtractionError: If LLM call fails (NOT silently caught)
        """
        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # 1. Generate dual extraction prompt
        prompt = self._create_dual_principle_extraction_prompt(case_text, section_type)

        # 2. Call LLM for dual extraction - errors will propagate, NOT be swallowed
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        # 3. Parse and validate results
        candidate_classes = self._parse_candidate_principle_classes(extraction_result.get('new_principle_classes', []), case_id)
        principle_individuals = self._parse_principle_individuals(extraction_result.get('principle_individuals', []), case_id, section_type)

        # 4. Cross-reference: link individuals to new classes if applicable
        self._link_individuals_to_new_classes(principle_individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate principle classes and {len(principle_individuals)} principle individuals from case {case_id} (source: {self.data_source.value})")

        return candidate_classes, principle_individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the raw LLM response for RDF conversion"""
        return self.last_raw_response

    def _load_existing_principle_classes(self) -> List[Dict[str, Any]]:
        """Load existing principle classes from proethica-intermediate via MCP"""
        try:
            # Use the correct MCP method for getting principle entities
            existing_principles = self.mcp_client.get_all_principle_entities()
            logger.info(f"Retrieved {len(existing_principles)} existing principles from MCP for dual extraction context")
            return existing_principles

        except Exception as e:
            logger.error(f"Error loading existing principle classes: {e}")
            return []

    def _create_dual_principle_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new principle classes and individual principle instances"""

        existing_principles_text = self._format_existing_principles_for_prompt()

        return f"""
DUAL PRINCIPLE EXTRACTION - Ethical Principles Analysis

THEORETICAL CONTEXT (Chapter 2.2.2):
- Principles are ABSTRACT ethical foundations requiring extensional definition through cases
- They function like constitutional principles - open-textured and requiring interpretation
- Principles mediate moral ideals into concrete reality through context-specific application
- They cannot be applied deductively but require balancing and interpretation

EXISTING PRINCIPLE CLASSES IN ONTOLOGY:
{existing_principles_text}

=== TASK ===
From the following case text ({section_type} section), extract information at TWO levels:

LEVEL 1 - NEW PRINCIPLE CLASSES: Identify ethical principles that appear to be NEW types not covered by existing classes above. Look for:
- Fundamental ethical values being invoked
- Abstract moral ideals guiding decisions
- Constitutional-like principles requiring interpretation
- Values that transcend specific rules or obligations

For each NEW principle class, provide:
- label: Clear principle name (e.g., "Environmental Stewardship", "Professional Autonomy")
- definition: What moral ideal this principle represents
- abstract_nature: The abstract ethical foundation (justice, welfare, autonomy, etc.)
- extensional_examples: Concrete cases/situations where this principle applies
- value_basis: Core moral value underlying the principle
- application_context: Professional domains or situations where relevant
- operationalization: How this abstract principle becomes concrete in practice
- balancing_requirements: What other principles it typically must be balanced against
- examples_from_case: How this principle appears in the case text

LEVEL 2 - PRINCIPLE INDIVIDUALS: Identify specific instances where principles are invoked or applied. For each instance:
- identifier: Unique identifier for this principle instance (e.g., "PublicSafety_Case8_Discussion")
- principle_class: Which principle class it instantiates (use existing classes when possible)
- concrete_expression: EXACT text showing how the principle is expressed
- invoked_by: Who invokes or appeals to this principle
- applied_to: What decision/situation/dilemma it applies to
- interpretation: How the principle is interpreted in this specific context
- balancing_with: Other principles that must be balanced against it
- tension_resolution: How conflicts between principles are resolved
- case_relevance: Why this principle matters in this specific case

IMPORTANT:
- Focus on ABSTRACT ethical foundations, not specific rules or procedures
- Principles are broader than obligations - they generate obligations in context
- Use EXACT quotes from case text where principles are expressed
- Distinguish between the abstract principle CLASS and its concrete APPLICATION

CASE TEXT:
{case_text}

Respond with valid JSON in this format:
{{
    "new_principle_classes": [
        {{
            "label": "Sustainable Development",
            "definition": "Principle that engineering solutions must balance current needs with long-term environmental and societal impacts",
            "abstract_nature": "Intergenerational justice and environmental stewardship",
            "extensional_examples": ["Green building design", "Renewable energy projects", "Resource conservation"],
            "value_basis": "Responsibility to future generations",
            "application_context": ["Infrastructure projects", "Environmental engineering", "Urban planning"],
            "operationalization": "Through environmental impact assessments, lifecycle analysis, sustainable design criteria",
            "balancing_requirements": ["Economic feasibility", "Immediate safety needs", "Client requirements"],
            "examples_from_case": ["Engineer considered long-term environmental impacts", "balanced immediate needs with sustainability"],
            "source_text": "Engineer considered long-term environmental impacts and balanced immediate needs with sustainability"
        }}
    ],
    "principle_individuals": [
        {{
            "identifier": "PublicSafety_Case8_Facts",
            "principle_class": "Public Safety",
            "concrete_expression": "the safety of the public must be held paramount",
            "invoked_by": ["Engineer L"],
            "applied_to": ["stormwater management system design"],
            "interpretation": "Safety considerations override cost savings in drainage design",
            "source_text": "the safety of the public must be held paramount",
            "balancing_with": ["Cost Efficiency", "Client Interests"],
            "tension_resolution": "Safety takes precedence even if it increases project costs",
            "case_relevance": "Critical for evaluating adequacy of proposed drainage solution"
        }}
    ]
}}
"""

    def _format_existing_principles_for_prompt(self) -> str:
        """Format existing principle classes for inclusion in prompt"""
        if not self.existing_principle_classes:
            return "No existing principle classes loaded."

        formatted_principles = []
        for principle in self.existing_principle_classes[:15]:  # Limit to avoid prompt length issues
            label = principle.get('label', 'Unknown')
            description = principle.get('description', principle.get('comment', ''))[:150]
            formatted_principles.append(f"- {label}: {description}")

        return "\n".join(formatted_principles)

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM with dual extraction prompt"""
        # Store prompt for later retrieval
        self.last_prompt = prompt

        try:
            # Use injected client if available (for testing), otherwise get default
            if self.llm_client is not None:
                # Mock client - call with extraction type for fixture lookup
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type='principles',
                    section_type=getattr(self, '_current_section_type', 'facts')
                )
                response_text = response.content if hasattr(response, 'content') else str(response)
                self.last_raw_response = response_text
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    import re
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        return json.loads(json_match.group())
                    return {"new_principle_classes": [], "principle_individuals": []}

            # Import the LLM client getter
            try:
                from app.utils.llm_utils import get_llm_client
            except ImportError:
                logger.error("Could not import get_llm_client")
                return {"new_principle_classes": [], "principle_individuals": []}

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available for dual principles extraction")
                return {"new_principle_classes": [], "principle_individuals": []}

            # Call the LLM
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Store the raw response for RDF conversion
            self.last_raw_response = response.content[0].text if response.content else ""

            # Parse JSON from response
            response_text = response.content[0].text if response.content else ""

            # Try to extract JSON from the response
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to find JSON in the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    logger.error("Could not extract JSON from LLM response")
                    return {"new_principle_classes": [], "principle_individuals": []}

            return result

        except Exception as e:
            logger.error(f"Error calling LLM for dual principles extraction: {e}")
            return {"new_principle_classes": [], "principle_individuals": []}

    def _parse_candidate_principle_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidatePrincipleClass]:
        """Parse raw principle class data into CandidatePrincipleClass objects"""
        candidates = []

        for raw_class in raw_classes:
            try:
                # Get source_text from LLM response, or fall back to first example
                source_text = raw_class.get('source_text')
                if not source_text and raw_class.get('examples_from_case'):
                    source_text = raw_class.get('examples_from_case', [''])[0]

                candidate = CandidatePrincipleClass(
                    label=raw_class.get('label', 'Unknown Principle'),
                    definition=raw_class.get('definition', ''),
                    abstract_nature=raw_class.get('abstract_nature', ''),
                    extensional_examples=raw_class.get('extensional_examples', []),
                    value_basis=raw_class.get('value_basis', ''),
                    application_context=raw_class.get('application_context', []),
                    operationalization=raw_class.get('operationalization', ''),
                    discovered_in_case=case_id,
                    confidence=raw_class.get('confidence', 0.85),
                    examples_from_case=raw_class.get('examples_from_case', []),
                    similarity_to_existing=0.0,
                    existing_similar_classes=[],
                    source_text=source_text
                )

                # Calculate similarity to existing principles
                self._calculate_similarity(candidate)

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing principle class: {e}")
                continue

        return candidates

    def _parse_principle_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[PrincipleIndividual]:
        """Parse raw principle individual data into PrincipleIndividual objects"""
        individuals = []

        for raw_ind in raw_individuals:
            try:
                individual = PrincipleIndividual(
                    identifier=raw_ind.get('identifier', f'Principle_{case_id}_{len(individuals)}'),
                    principle_class=raw_ind.get('principle_class', 'Unknown'),
                    concrete_expression=raw_ind.get('concrete_expression', ''),
                    invoked_by=raw_ind.get('invoked_by', []),
                    applied_to=raw_ind.get('applied_to', []),
                    interpretation=raw_ind.get('interpretation', ''),
                    balancing_with=raw_ind.get('balancing_with', []),
                    case_section=section_type,
                    confidence=raw_ind.get('confidence', 0.85),
                    is_new_principle_class=False,
                    source_text=raw_ind.get('source_text')
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing principle individual: {e}")
                continue

        return individuals

    def _calculate_similarity(self, candidate: CandidatePrincipleClass):
        """Calculate similarity between candidate and existing principle classes"""
        if not self.existing_principle_classes:
            return

        # Simple label-based similarity for now
        candidate_label_lower = candidate.label.lower()
        similar_classes = []

        for existing in self.existing_principle_classes:
            existing_label = existing.get('label', '').lower()
            if (candidate_label_lower in existing_label or
                existing_label in candidate_label_lower or
                any(word in existing_label for word in candidate_label_lower.split())):
                similar_classes.append(existing.get('label', 'Unknown'))

        if similar_classes:
            candidate.similarity_to_existing = 0.8  # High similarity if label matches
            candidate.existing_similar_classes = similar_classes[:3]
        else:
            candidate.similarity_to_existing = 0.0

    def _link_individuals_to_new_classes(self, individuals: List[PrincipleIndividual], candidates: List[CandidatePrincipleClass]):
        """Link principle individuals to newly discovered principle classes"""
        candidate_labels = {c.label for c in candidates}

        for individual in individuals:
            if individual.principle_class in candidate_labels:
                individual.is_new_principle_class = True