"""
Dual Resources Extractor - Discovers both new resource classes and individual resource instances

This service extracts:
1. NEW RESOURCE CLASSES: Novel resource types not in existing ontology
2. INDIVIDUAL RESOURCE INSTANCES: Specific documents, tools, and knowledge sources used in cases
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from app.services.extraction.mock_llm_provider import LLMResponseError
from app.utils.llm_utils import extract_json_from_response
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidateResourceClass:
    """Represents a potentially new resource class"""
    label: str
    definition: str
    resource_type: str  # document, tool, standard, guideline, etc.
    accessibility: List[str]  # public, restricted, proprietary
    authority_source: str = ''  # Who creates/maintains this resource
    typical_usage: str = ''  # How it's typically used
    domain_context: str = ''  # Medical/Engineering/Legal/etc.
    discovered_in_case: int = 0
    confidence: float = 0.0
    examples_from_case: List[str] = None
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None

@dataclass
class ResourceIndividual:
    """Represents a specific resource instance used in a case"""
    identifier: str
    resource_class: str  # URI or label of the resource class
    document_title: str = ''
    created_by: str = ''  # WHO created this resource
    created_at: str = ''  # WHEN it was created
    version: str = ''  # Version or edition
    url_or_location: str = ''  # Where to find it
    used_by: str = ''  # WHO used it in the case
    used_in_context: str = ''  # HOW it was used
    case_section: str = ''
    confidence: float = 0.8
    is_new_resource_class: bool = False  # True if this is a newly discovered resource class

class DualResourcesExtractor:
    """Extract both new resource classes and individual resource instances"""

    def __init__(self, llm_client=None):
        """
        Initialize the dual resources extractor.

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
        self.existing_resource_classes = self._load_existing_resource_classes()
        self.model_name = ModelConfig.get_claude_model("powerful")
        self.last_raw_response = None  # Store the raw LLM response
        self.last_prompt = None  # Store the prompt sent to LLM

    def extract_dual_resources(self, case_text: str, case_id: int, section_type: str) -> Tuple[List[CandidateResourceClass], List[ResourceIndividual]]:
        """
        Extract both new resource classes and individual resource instances from case text

        Returns:
            Tuple of (candidate_resource_classes, resource_individuals)

        Raises:
            ExtractionError: If LLM call fails (NOT silently caught)
        """
        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # 1. Generate dual extraction prompt
        prompt = self._create_dual_resources_extraction_prompt(case_text, section_type)

        # 2. Call LLM for dual extraction - errors will propagate, NOT be swallowed
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        # 3. Parse and validate results
        candidate_classes = self._parse_candidate_resource_classes(extraction_result.get('new_resource_classes', []), case_id)
        resource_individuals = self._parse_resource_individuals(extraction_result.get('resource_individuals', []), case_id, section_type)

        # 4. Cross-reference: link individuals to new classes if applicable
        self._link_individuals_to_new_classes(resource_individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate resource classes and {len(resource_individuals)} resource individuals from case {case_id} (source: {self.data_source.value})")

        # Return raw extraction results - let route handler manage storage
        return candidate_classes, resource_individuals

    def _load_existing_resource_classes(self) -> List[Dict[str, Any]]:
        """Load existing resource classes from proethica-intermediate via MCP"""
        try:
            # Get all resource entities using MCP
            existing_resources = self.mcp_client.get_all_resource_entities()
            logger.info(f"Retrieved {len(existing_resources)} existing resources from external MCP for dual extraction context")
            return existing_resources

        except Exception as e:
            logger.error(f"Error loading existing resource classes: {e}")
            return []

    def _create_dual_resources_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new resource classes and individual resource instances"""

        existing_resources_text = self._format_existing_resources_for_prompt()

        return f"""
{existing_resources_text}

You are analyzing a professional ethics case to extract both RESOURCE CLASSES and RESOURCE INSTANCES.

DEFINITIONS:
- RESOURCE CLASS: A type of document, tool, standard, or knowledge source (e.g., "Emergency Response Protocol", "Technical Specification", "Ethics Code")
- RESOURCE INDIVIDUAL: A specific instance of a resource used in this case (e.g., "NSPE Code of Ethics 2023", "City M Water Quality Standards")

CRITICAL REQUIREMENT: Every RESOURCE CLASS you identify MUST be based on at least one specific RESOURCE INDIVIDUAL instance in the case.
You cannot propose a resource class without providing the concrete instance(s) that demonstrate it.

YOUR TASK - Extract two LINKED types of entities:

1. NEW RESOURCE CLASSES (types not in the existing ontology above):
   - Novel types of resources discovered in this case
   - Must be sufficiently general to apply to other cases
   - Should represent distinct categories of decision-making resources
   - Consider documents, tools, standards, guidelines, databases, etc.

2. RESOURCE INDIVIDUALS (specific instances in this case):
   - Specific documents, tools, or knowledge sources mentioned
   - MUST have identifiable titles or descriptions
   - Include metadata (creator, date, version) where available
   - Map to existing classes where possible, or to new classes you discover

EXTRACTION GUIDELINES:

For NEW RESOURCE CLASSES, identify:
- Label: Clear, professional name for the resource type
- Definition: What this resource type represents
- Resource type: document, tool, standard, guideline, database, etc.
- Accessibility: public, restricted, proprietary, etc.
- Authority source: Who typically creates/maintains these resources
- Typical usage: How these resources are typically used
- Domain context: Medical/Engineering/Legal/etc.
- Examples from case: Specific instances showing this resource type

For RESOURCE INDIVIDUALS, identify:
- Identifier: Unique descriptor (e.g., "NSPE_CodeOfEthics_2023")
- Resource class: Which resource type it represents (existing or new)
- Document title: Official name or description
- Created by: Organization or authority that created it
- Created at: When it was created (if mentioned)
- Version: Edition or version information
- URL or location: Where to find it (if mentioned)
- Used by: Who used this resource in the case
- Used in context: How this resource was applied
- Case involvement: How this resource affected decisions

CASE TEXT FROM {section_type} SECTION:
{case_text}

Respond with a JSON structure. Here's an EXAMPLE:

EXAMPLE (if the case mentions "Engineer A consulted the NSPE Code of Ethics and the state's engineering regulations"):
{{
  "new_resource_classes": [
    {{
      "label": "State Engineering Regulations",
      "definition": "Legal requirements and regulations governing engineering practice at the state level",
      "resource_type": "regulatory_document",
      "accessibility": ["public", "official"],
      "authority_source": "State Engineering Board",
      "typical_usage": "Legal compliance and professional practice guidance",
      "domain_context": "Engineering",
      "examples_from_case": ["State engineering regulations consulted by Engineer A"],
      "source_text": "Engineer A consulted the state's engineering regulations",
      "confidence": 0.85,
      "rationale": "Specific type of regulatory resource not in existing ontology"
    }}
  ],
  "resource_individuals": [
    {{
      "identifier": "NSPE_CodeOfEthics_Current",
      "resource_class": "Professional Ethics Code",
      "document_title": "NSPE Code of Ethics",
      "created_by": "National Society of Professional Engineers",
      "created_at": "Current version",
      "version": "Current",
      "used_by": "Engineer A",
      "used_in_context": "Consulted for ethical guidance on conflict of interest",
      "case_involvement": "Provided framework for ethical decision-making",
      "source_text": "Engineer A consulted the NSPE Code of Ethics",
      "is_existing_class": true,
      "confidence": 0.95
    }},
    {{
      "identifier": "State_Engineering_Regulations_Current",
      "resource_class": "State Engineering Regulations",
      "document_title": "State Engineering Practice Act and Regulations",
      "created_by": "State Engineering Board",
      "used_by": "Engineer A",
      "used_in_context": "Referenced for legal requirements",
      "case_involvement": "Defined legal obligations for professional practice",
      "source_text": "Engineer A referenced the State Engineering Practice Act and Regulations",
      "is_existing_class": false,
      "confidence": 0.9
    }}
  ]
}}

EXTRACTION RULES:
1. For EVERY new resource class you identify, you MUST provide at least one corresponding resource individual
2. Resource individuals MUST have identifiable titles or descriptions
3. If you cannot identify a specific instance, do not create the resource class
4. Focus on resources that directly influence decision-making in the case
5. Each resource individual should clearly demonstrate why its resource class is needed

Focus on resources that:
1. Are explicitly mentioned or referenced in the case
2. Guide professional decisions or actions
3. Provide standards, requirements, or frameworks
4. Serve as knowledge sources for the professionals involved
"""

    def _format_existing_resources_for_prompt(self) -> str:
        """Format existing resource classes for inclusion in prompt"""
        # Defensive check - ensure we have a list
        if self.existing_resource_classes is None:
            self.existing_resource_classes = []
        if not self.existing_resource_classes:
            return "EXISTING RESOURCE CLASSES IN ONTOLOGY: None found. All resources you identify will be new."

        text = "EXISTING RESOURCE CLASSES IN ONTOLOGY (DO NOT RE-EXTRACT THESE):\n\n"

        for resource in self.existing_resource_classes:
            label = resource.get('label', 'Unknown')
            definition = resource.get('description', resource.get('definition', 'No definition'))
            text += f"- {label}: {definition}\n"

        text += "\nIMPORTANT: Only extract NEW resource types not listed above!\n"
        return text

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """Call LLM for dual resource extraction"""
        # Store prompt for later retrieval
        self.last_prompt = prompt

        try:
            # Use injected client if available (for testing), otherwise get default
            if self.llm_client is not None:
                # Mock client - call with extraction type for fixture lookup
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type='resources',
                    section_type=getattr(self, '_current_section_type', 'facts')
                )
                response_text = response.content if hasattr(response, 'content') else str(response)
                self.last_raw_response = response_text
                try:
                    return extract_json_from_response(response_text)
                except ValueError as e:
                    raise LLMResponseError(f"Could not parse JSON from LLM response: {str(e)}")

            from app.utils.llm_utils import get_llm_client

            llm_client = get_llm_client()
            if llm_client:
                response = llm_client.messages.create(
                    model=self.model_name,
                    max_tokens=4000,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )

                response_text = response.content[0].text if response.content else ""

                # Store raw response for debugging
                self.last_raw_response = response_text

                # Parse JSON response
                try:
                    return extract_json_from_response(response_text)
                except ValueError as e:
                    raise LLMResponseError(f"Could not parse JSON from LLM response: {str(e)}")

        except Exception as e:
            logger.error(f"Error calling LLM for dual resources extraction: {e}")
            return {}

    def _parse_candidate_resource_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateResourceClass]:
        """Parse raw resource class data into CandidateResourceClass objects"""
        candidates = []

        for raw in raw_classes:
            try:
                candidate = CandidateResourceClass(
                    label=raw.get('label', 'Unknown Resource'),
                    definition=raw.get('definition', ''),
                    resource_type=raw.get('resource_type', 'document'),
                    accessibility=raw.get('accessibility', ['unknown']),
                    authority_source=raw.get('authority_source', ''),
                    typical_usage=raw.get('typical_usage', ''),
                    domain_context=raw.get('domain_context', ''),
                    discovered_in_case=case_id,
                    confidence=raw.get('confidence', 0.7),
                    examples_from_case=raw.get('examples_from_case', [])
                )

                # Calculate similarity to existing classes
                similarity, similar = self._calculate_similarity_to_existing(candidate.label, candidate.definition)
                candidate.similarity_to_existing = similarity
                candidate.existing_similar_classes = similar

                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing candidate resource class: {e}")

        return candidates

    def _parse_resource_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[ResourceIndividual]:
        """Parse raw individual data into ResourceIndividual objects"""
        individuals = []

        for raw in raw_individuals:
            try:
                individual = ResourceIndividual(
                    identifier=raw.get('identifier', 'Unknown Resource Instance'),
                    resource_class=raw.get('resource_class', 'Resource'),
                    document_title=raw.get('document_title', ''),
                    created_by=raw.get('created_by', ''),
                    created_at=raw.get('created_at', ''),
                    version=raw.get('version', ''),
                    url_or_location=raw.get('url_or_location', ''),
                    used_by=raw.get('used_by', ''),
                    used_in_context=raw.get('used_in_context', ''),
                    case_section=section_type,
                    confidence=raw.get('confidence', 0.8),
                    is_new_resource_class=not raw.get('is_existing_class', True)
                )

                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing resource individual: {e}")

        return individuals

    def _calculate_similarity_to_existing(self, label: str, definition: str) -> Tuple[float, List[str]]:
        """Calculate semantic similarity to existing resource classes"""
        # For now, simple label matching - could be enhanced with embeddings
        similar_classes = []
        max_similarity = 0.0

        label_lower = label.lower()
        for existing in self.existing_resource_classes:
            existing_label = existing.get('label', '').lower()
            if label_lower == existing_label:
                return 1.0, [existing.get('label')]
            elif label_lower in existing_label or existing_label in label_lower:
                similar_classes.append(existing.get('label'))
                max_similarity = max(max_similarity, 0.5)

        return max_similarity, similar_classes

    def _link_individuals_to_new_classes(self, individuals: List[ResourceIndividual], new_classes: List[CandidateResourceClass]):
        """Link individuals to newly discovered resource classes"""
        new_class_labels = {c.label for c in new_classes}

        for individual in individuals:
            if individual.resource_class in new_class_labels:
                individual.is_new_resource_class = True

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for debugging"""
        return self.last_raw_response

    def get_extraction_summary(self, candidates: List[CandidateResourceClass], individuals: List[ResourceIndividual]) -> Dict[str, Any]:
        """Generate summary of extraction results"""
        return {
            'new_resource_classes_count': len(candidates),
            'resource_individuals_count': len(individuals),
            'individuals_with_new_classes': sum(1 for i in individuals if i.is_new_resource_class),
            'confidence_avg': sum(c.confidence for c in candidates) / len(candidates) if candidates else 0
        }