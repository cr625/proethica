"""
Dual Role Extractor - Discovers both new role classes and individual role instances

This service extracts:
1. NEW ROLE CLASSES: Novel professional roles not in existing ontology
2. INDIVIDUAL ROLE INSTANCES: Specific people fulfilling roles in cases
"""

import json
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.external_mcp_client import get_external_mcp_client
from app.services.candidate_role_validation_service import CandidateRoleValidationService
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.utils.llm_utils import extract_json_from_response
from models import ModelConfig

logger = logging.getLogger(__name__)

@dataclass
class CandidateRoleClass:
    """Represents a potentially new professional role class"""
    label: str
    definition: str
    distinguishing_features: List[str]
    professional_scope: str
    typical_qualifications: List[str]
    discovered_in_case: int
    confidence: float
    examples_from_case: List[str]
    similarity_to_existing: float = 0.0
    existing_similar_classes: List[str] = None
    source_text: Optional[str] = None  # Text snippet where this role class is identified

@dataclass
class RoleIndividual:
    """Represents a specific person fulfilling a role in a case"""
    name: str
    role_class: str  # URI of the role class they fulfill
    attributes: Dict[str, Any]
    relationships: List[Dict[str, str]]
    case_section: str
    confidence: float
    is_new_role_class: bool = False  # True if they fulfill a newly discovered role class
    source_text: Optional[str] = None  # Text snippet where this individual is mentioned
    source_context: Optional[str] = None  # Additional surrounding context

class DualRoleExtractor:
    """Extract both new role classes and individual role instances"""

    def __init__(self, llm_client=None):
        """
        Initialize the dual role extractor.

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
        self.validation_service = CandidateRoleValidationService()
        self.existing_role_classes = self._load_existing_role_classes()
        self.model_name = ModelConfig.get_claude_model("powerful")
        self.last_raw_response = None  # Store the raw LLM response
        self.last_prompt = None  # Store the prompt sent to LLM

    def extract_dual_roles(self, case_text: str, case_id: int, section_type: str) -> Tuple[List[CandidateRoleClass], List[RoleIndividual]]:
        """
        Extract both new role classes and individual role instances from case text

        Returns:
            Tuple of (candidate_role_classes, role_individuals)

        Raises:
            ExtractionError: If LLM call fails (NOT silently caught)
        """
        # Store section_type for mock client lookup
        self._current_section_type = section_type

        # 1. Generate dual extraction prompt
        prompt = self._create_dual_role_extraction_prompt(case_text, section_type)

        # 2. Call LLM for dual extraction - errors will propagate, NOT be swallowed
        extraction_result = self._call_llm_for_dual_extraction(prompt)

        # 3. Parse and validate results
        candidate_classes = self._parse_candidate_role_classes(extraction_result.get('new_role_classes', []), case_id)
        role_individuals = self._parse_role_individuals(extraction_result.get('role_individuals', []), case_id, section_type)

        # 4. Cross-reference: link individuals to new classes if applicable
        self._link_individuals_to_new_classes(role_individuals, candidate_classes)

        logger.info(f"Extracted {len(candidate_classes)} candidate role classes and {len(role_individuals)} role individuals from case {case_id} (source: {self.data_source.value})")

        # Return raw extraction results - let route handler manage storage
        return candidate_classes, role_individuals

    def _load_existing_role_classes(self) -> List[Dict[str, Any]]:
        """Load existing role classes from proethica-intermediate via MCP"""
        try:
            # Get all role entities using the correct MCP method
            existing_roles = self.mcp_client.get_all_role_entities()
            logger.info(f"Retrieved {len(existing_roles)} existing roles from external MCP for dual extraction context")
            return existing_roles

        except Exception as e:
            logger.error(f"Error loading existing role classes: {e}")
            return []

    def _create_dual_role_extraction_prompt(self, case_text: str, section_type: str) -> str:
        """Create prompt for extracting both new role classes and individual role instances"""

        existing_roles_text = self._format_existing_roles_for_prompt()

        return f"""
DUAL ROLE EXTRACTION - Professional Roles Analysis

EXISTING ROLE CLASSES IN ONTOLOGY:
{existing_roles_text}

=== TASK ===
From the following case text ({section_type} section), extract information at TWO levels:

LEVEL 1 - NEW ROLE CLASSES: Identify professional roles that appear to be NEW types not covered by existing classes above. Look for:
- Specialized professional functions
- Emerging role types in engineering/technology
- Domain-specific professional positions
- Roles with unique qualifications or responsibilities

For each NEW role class, provide:
- label: Clear professional role name
- definition: Detailed description of role function and scope
- distinguishing_features: What makes this role unique/different
- professional_scope: Areas of responsibility and authority
- typical_qualifications: Required education, licensing, experience
- generated_obligations: What specific duties does this role create?
- associated_virtues: What virtues/qualities are expected (integrity, competence, etc.)?
- relationship_type: Provider-Client, Professional Peer, Employer, Public Responsibility
- domain_context: Engineering/Medical/Legal/etc.
- examples_from_case: How this role appears in the case text
- source_text: EXACT text snippet from the case where this role class is first identified or described (max 200 characters)

LEVEL 2 - ROLE INDIVIDUALS: Identify specific people mentioned who fulfill professional roles. For each person:
- name: EXACT name or identifier as it appears in the text (e.g., "Engineer A", "Client B", "Dr. Smith")
- role_classification: Which role class they fulfill (use existing classes when possible, or new class label if discovered)
- attributes: Specific qualifications, experience, titles, licenses mentioned in the text
- relationships: Employment, reporting, collaboration relationships explicitly stated
  - Each relationship should specify: type (employs, reports_to, collaborates_with, serves_client, etc.) and target (person/org name)
- active_obligations: What specific duties is this person fulfilling in the case?
- ethical_tensions: Any conflicts between role obligations and personal/other obligations?
- case_involvement: How they participate in this case
- source_text: EXACT text snippet from the case where this individual is first mentioned or described (max 200 characters)

IMPORTANT: Use ONLY the actual names/identifiers found in the case text. DO NOT create realistic names or make up details not explicitly stated.

CASE TEXT:
{case_text}

Respond with valid JSON in this format:
{{
    "new_role_classes": [
        {{
            "label": "Environmental Compliance Specialist",
            "definition": "Professional responsible for ensuring projects meet environmental regulations and standards",
            "distinguishing_features": ["Environmental regulation expertise", "Compliance assessment capabilities", "EPA standards knowledge"],
            "professional_scope": "Environmental impact assessment, regulatory compliance review, permit coordination",
            "typical_qualifications": ["Environmental engineering degree", "Regulatory compliance experience", "Knowledge of EPA standards"],
            "generated_obligations": ["Ensure regulatory compliance", "Report violations", "Maintain environmental standards"],
            "associated_virtues": ["Environmental stewardship", "Regulatory integrity", "Technical competence"],
            "relationship_type": "Provider-Client",
            "domain_context": "Engineering",
            "examples_from_case": ["Engineer A was retained to prepare environmental assessment", "specialist reviewed compliance requirements"],
            "source_text": "Engineer A was retained to prepare environmental assessment"
        }}
    ],
    "role_individuals": [
        {{
            "name": "Engineer A",
            "role_classification": "Environmental Compliance Specialist",
            "attributes": {{
                "title": "Engineer",
                "license": "professional engineering license",
                "specialization": "environmental engineer",
                "experience": "several years of experience"
            }},
            "relationships": [
                {{"type": "retained_by", "target": "Client W"}}
            ],
            "case_involvement": "Retained to prepare comprehensive report addressing organic compound characteristics",
            "source_text": "Engineer A, a professional engineer with several years of experience, was retained by Client W"
        }}
    ]
}}
"""

    def _format_existing_roles_for_prompt(self) -> str:
        """Format existing role classes for inclusion in prompt"""
        # Defensive check - ensure we have a list
        if self.existing_role_classes is None:
            self.existing_role_classes = []
        if not self.existing_role_classes:
            return "No existing role classes loaded."

        formatted_roles = []
        for role in self.existing_role_classes[:20]:  # Limit to avoid prompt length issues
            label = role.get('label', 'Unknown')
            # Handle None values from OntServe entities
            description = role.get('description') or role.get('comment') or ''
            description = description[:100] if description else ''
            formatted_roles.append(f"- {label}: {description}")

        return "\n".join(formatted_roles)

    def _call_llm_for_dual_extraction(self, prompt: str) -> Dict[str, Any]:
        """
        Call LLM with dual extraction prompt.

        Raises:
            LLMConnectionError: If LLM client unavailable or connection fails
            LLMResponseError: If LLM returns unparseable response
        """
        from app.services.extraction.mock_llm_provider import (
            LLMConnectionError, LLMResponseError, DataSource
        )

        # Store prompt for later retrieval
        self.last_prompt = prompt

        # Use injected client if available (for testing/mock), otherwise get default
        if self.llm_client is not None:
            # Mock or injected client - call with extraction type for fixture lookup
            response = self.llm_client.call(
                prompt=prompt,
                extraction_type='roles',
                section_type=getattr(self, '_current_section_type', 'facts')
            )
            response_text = response.content if hasattr(response, 'content') else str(response)
            self.last_raw_response = response_text
            try:
                return extract_json_from_response(response_text)
            except ValueError as e:
                raise LLMResponseError(f"Could not parse JSON from response (source: {self.data_source.value}): {str(e)}")

        # Real LLM mode - errors must propagate, not be silently converted to empty results
        try:
            from app.utils.llm_utils import get_llm_client
        except ImportError as e:
            raise LLMConnectionError(f"Could not import get_llm_client: {e}")

        client = get_llm_client()
        if client is None:
            raise LLMConnectionError("No LLM client available - check API key configuration")

        # Try Anthropic messages API
        if not (hasattr(client, 'messages') and hasattr(client.messages, 'create')):
            raise LLMConnectionError("LLM client does not support messages.create API")

        try:
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.3,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
        except Exception as e:
            raise LLMConnectionError(f"LLM API call failed: {e}")

        # Handle response content
        content = getattr(response, 'content', None)
        if content and isinstance(content, list) and len(content) > 0:
            response_text = getattr(content[0], 'text', None) or str(content[0])
        else:
            response_text = str(response)

        response_text = response_text.strip()

        # Store raw response for debugging
        self.last_raw_response = response_text

        # Parse JSON response using utility that handles markdown code blocks
        try:
            return extract_json_from_response(response_text)
        except ValueError as e:
            raise LLMResponseError(f"Could not parse JSON from LLM response: {str(e)}")

    def _parse_candidate_role_classes(self, raw_classes: List[Dict], case_id: int) -> List[CandidateRoleClass]:
        """Parse and validate candidate role classes from LLM response"""
        candidates = []

        for raw_class in raw_classes:
            try:
                # Calculate similarity to existing classes
                similarity, similar_classes = self._calculate_class_similarity(raw_class['label'])

                # Get source_text from LLM response, or fall back to first example
                source_text = raw_class.get('source_text')
                if not source_text and raw_class.get('examples_from_case'):
                    source_text = raw_class.get('examples_from_case', [''])[0]

                candidate = CandidateRoleClass(
                    label=raw_class.get('label', ''),
                    definition=raw_class.get('definition', ''),
                    distinguishing_features=raw_class.get('distinguishing_features', []),
                    professional_scope=raw_class.get('professional_scope', ''),
                    typical_qualifications=raw_class.get('typical_qualifications', []),
                    discovered_in_case=case_id,
                    confidence=0.8,  # Initial confidence, can be refined
                    examples_from_case=raw_class.get('examples_from_case', []),
                    similarity_to_existing=similarity,
                    existing_similar_classes=similar_classes,
                    source_text=source_text
                )
                candidates.append(candidate)

            except Exception as e:
                logger.error(f"Error parsing candidate role class: {e}")
                continue

        return candidates

    def _parse_role_individuals(self, raw_individuals: List[Dict], case_id: int, section_type: str) -> List[RoleIndividual]:
        """Parse and validate role individuals from LLM response"""
        individuals = []

        for raw_individual in raw_individuals:
            try:
                individual = RoleIndividual(
                    name=raw_individual.get('name', ''),
                    role_class=raw_individual.get('role_classification', ''),
                    attributes=raw_individual.get('attributes', {}),
                    relationships=raw_individual.get('relationships', []),
                    case_section=section_type,
                    confidence=0.9,  # High confidence for named individuals
                    is_new_role_class=False,  # Will be updated in linking step
                    source_text=raw_individual.get('source_text'),  # Capture source text snippet
                    source_context=raw_individual.get('case_involvement')  # Use case_involvement as context
                )
                individuals.append(individual)

            except Exception as e:
                logger.error(f"Error parsing role individual: {e}")
                continue

        return individuals

    def _calculate_class_similarity(self, new_label: str) -> Tuple[float, List[str]]:
        """Calculate similarity between new class and existing classes"""
        max_similarity = 0.0
        similar_classes = []

        for existing_class in self.existing_role_classes:
            existing_label = existing_class.get('label', '')

            # Simple similarity check (could be enhanced with semantic embeddings)
            words_new = set(new_label.lower().split())
            words_existing = set(existing_label.lower().split())

            if words_new and words_existing:
                intersection = words_new.intersection(words_existing)
                union = words_new.union(words_existing)
                similarity = len(intersection) / len(union)

                if similarity > max_similarity:
                    max_similarity = similarity

                if similarity > 0.3:  # Somewhat similar
                    similar_classes.append(existing_label)

        return max_similarity, similar_classes[:3]  # Top 3 similar classes

    def _link_individuals_to_new_classes(self, individuals: List[RoleIndividual], candidates: List[CandidateRoleClass]):
        """Link role individuals to newly discovered role classes"""
        candidate_labels = {candidate.label for candidate in candidates}

        for individual in individuals:
            if individual.role_class in candidate_labels:
                individual.is_new_role_class = True

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for debugging"""
        return self.last_raw_response

    def get_extraction_summary(self, candidates, individuals: List[RoleIndividual]) -> Dict[str, Any]:
        """Generate summary of extraction results"""
        return {
            "candidate_classes_count": len(candidates),
            "individuals_count": len(individuals),
            "new_class_individuals_count": sum(1 for ind in individuals if ind.is_new_role_class),
            "existing_class_individuals_count": sum(1 for ind in individuals if not ind.is_new_role_class),
            "candidate_classes": [
                {
                    "label": c.label if hasattr(c, 'discovery_confidence') else c.label,
                    "confidence": c.discovery_confidence if hasattr(c, 'discovery_confidence') else getattr(c, 'confidence', 0.8),
                    "similarity": c.similarity_to_existing if hasattr(c, 'similarity_to_existing') else 0.0
                }
                for c in candidates
            ],
            "individuals_by_role": self._group_individuals_by_role(individuals)
        }

    def _group_individuals_by_role(self, individuals: List[RoleIndividual]) -> Dict[str, List[str]]:
        """Group individuals by their role classifications"""
        groups = {}
        for individual in individuals:
            role = individual.role_class
            if role not in groups:
                groups[role] = []
            groups[role].append(individual.name)
        return groups

    def _store_candidates_for_validation(self,
                                       candidates: List[CandidateRoleClass],
                                       individuals: List[RoleIndividual],
                                       case_id: int,
                                       section_type: str) -> List:
        """Store discovered candidates in the validation system"""
        from app.models.candidate_role_class import CandidateRoleClass as StoredCandidate

        stored_candidates = []

        for candidate in candidates:
            try:
                # Prepare candidate data for storage
                candidate_data = {
                    'label': candidate.label,
                    'definition': candidate.definition,
                    'confidence': candidate.confidence,
                    'distinguishing_features': candidate.distinguishing_features,
                    'professional_scope': candidate.professional_scope,
                    'typical_qualifications': candidate.typical_qualifications,
                    'examples_from_case': candidate.examples_from_case,
                    'similarity_to_existing': candidate.similarity_to_existing,
                    'existing_similar_classes': candidate.existing_similar_classes or [],
                    'extraction_metadata': {
                        'model_used': self.model_name,
                        'extraction_method': 'dual_role_extractor',
                        'discovered_in_case': candidate.discovered_in_case
                    }
                }

                # Store candidate in validation system
                stored_candidate = self.validation_service.store_candidate_role_class(
                    candidate_data=candidate_data,
                    case_id=case_id,
                    section_type=section_type
                )

                # Store associated individuals
                for individual in individuals:
                    if individual.is_new_role_class and individual.role_class == candidate.label:
                        individual_data = {
                            'name': individual.name,
                            'attributes': individual.attributes
                        }
                        self.validation_service.store_candidate_role_individual(
                            individual_data=individual_data,
                            candidate_role_class=stored_candidate,
                            case_id=case_id
                        )

                stored_candidates.append(stored_candidate)
                logger.info(f"Stored candidate '{candidate.label}' for validation")

            except Exception as e:
                logger.error(f"Error storing candidate '{candidate.label}': {e}")
                continue

        # ALSO store in temporary storage system for review interface integration
        self._store_in_temporary_storage(candidates, individuals, case_id, section_type)

        return stored_candidates

    def _store_in_temporary_storage(self, candidates: List[CandidateRoleClass], individuals: List[RoleIndividual], case_id: int, section_type: str):
        """Store candidate role classes and individuals in temporary storage for review interface"""
        try:
            entities_to_store = []

            # Convert candidate role classes to temporary storage format
            for candidate in candidates:
                entity_data = {
                    'label': candidate.label,
                    'description': candidate.definition,
                    'category': 'Role',  # This maps to the TemporaryConcept.category field
                    'type': 'role_class',  # This goes in the concept_data JSON
                    'confidence': candidate.confidence,
                    'is_new': True,
                    'is_novel': candidate.similarity_to_existing < 0.3,
                    'distinguishing_features': candidate.distinguishing_features,
                    'professional_scope': candidate.professional_scope,
                    'typical_qualifications': candidate.typical_qualifications,
                    'examples_from_case': candidate.examples_from_case,
                    'similarity_to_existing': candidate.similarity_to_existing,
                    'existing_similar_classes': candidate.existing_similar_classes or []
                }
                entities_to_store.append(entity_data)

            # Convert individuals to temporary storage format
            for individual in individuals:
                entity_data = {
                    'label': individual.name,
                    'description': f"Individual fulfilling role: {individual.role_class}",
                    'category': 'Individual',  # This maps to the TemporaryConcept.category field
                    'type': 'role_individual',  # This goes in the concept_data JSON
                    'confidence': individual.confidence,
                    'is_new': True,
                    'role_class': individual.role_class,
                    'is_new_role_class': individual.is_new_role_class,
                    'attributes': individual.attributes,
                    'relationships': individual.relationships,
                    'case_involvement': getattr(individual, 'case_involvement', '')
                }
                entities_to_store.append(entity_data)

            if entities_to_store:
                # Store in temporary storage
                session_id, stored_concepts = CaseEntityStorageService.store_extracted_entities(
                    entities=entities_to_store,
                    case_id=case_id,
                    section_type=section_type,
                    extraction_metadata={
                        'extraction_method': 'dual_role_extraction',
                        'model_used': self.model_name,
                        'extraction_pass': 'contextual_framework',
                        'entity_types': ['role_class', 'role_individual']
                    },
                    provenance_activity=None  # Avoid session issues with provenance objects
                )

                logger.info(f"Stored {len(entities_to_store)} dual extraction entities in temporary storage (session: {session_id})")

        except Exception as e:
            logger.error(f"Error storing dual extraction entities in temporary storage: {e}")
            # Don't let temporary storage errors break the main extraction flow