"""
Unified Dual Extractor for all 9 D-Tuple concepts.

Replaces the 7 near-identical dual_*_extractor.py files with a single
parameterized class. Loads prompts from DB templates, validates LLM output
against Pydantic schemas from schemas.py, and uses PromptVariableResolver
for MCP entity context.

Usage:
    extractor = UnifiedDualExtractor('obligations')
    classes, individuals = extractor.extract(case_text, case_id, 'discussion')
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from app.services.prompt_variable_resolver import format_existing_entities

from app.utils.llm_utils import extract_json_from_response

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-concept configuration
# ---------------------------------------------------------------------------
# Derived from the 7 existing dual extractors. Each entry captures the
# concept-specific settings that were previously hardcoded.

CONCEPT_CONFIG: Dict[str, Dict[str, Any]] = {
    'roles': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 8192,
        'classes_key': 'new_role_classes',
        'individuals_key': 'role_individuals',
        'class_ref_field': 'role_class',
    },
    'states': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 8192,
        'classes_key': 'new_state_classes',
        'individuals_key': 'state_individuals',
        'class_ref_field': 'state_class',
    },
    'resources': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 8192,
        'classes_key': 'new_resource_classes',
        'individuals_key': 'resource_individuals',
        'class_ref_field': 'resource_class',
    },
    'principles': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.5,
        'max_tokens': 8192,
        'classes_key': 'new_principle_classes',
        'individuals_key': 'principle_individuals',
        'class_ref_field': 'principle_class',
    },
    'obligations': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_obligation_classes',
        'individuals_key': 'obligation_individuals',
        'class_ref_field': 'obligation_class',
    },
    'constraints': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_constraint_classes',
        'individuals_key': 'constraint_individuals',
        'class_ref_field': 'constraint_class',
    },
    'capabilities': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 8192,
        'classes_key': 'new_capability_classes',
        'individuals_key': 'capability_individuals',
        'class_ref_field': 'capability_class',
    },
    'actions': {
        'step': 3,
        'model_tier': 'default',
        'temperature': 0.7,
        'max_tokens': 8192,
        'classes_key': 'new_action_classes',
        'individuals_key': 'action_individuals',
        'class_ref_field': 'action_class',
    },
    'events': {
        'step': 3,
        'model_tier': 'default',
        'temperature': 0.7,
        'max_tokens': 8192,
        'classes_key': 'new_event_classes',
        'individuals_key': 'event_individuals',
        'class_ref_field': 'event_class',
    },
}


# ---------------------------------------------------------------------------
# Cross-concept dependency map
# ---------------------------------------------------------------------------
# Defines which prior concept extractions should be injected into the prompt
# for each concept. Reflects the methodology's dependency chain:
#   Roles -> Principles -> Obligations -> Constraints/Capabilities

CROSS_CONCEPT_DEPS: Dict[str, Dict[str, Any]] = {
    'principles': {
        'depends_on': ['roles'],
        'instruction': (
            'The following ROLES were identified in this case. '
            'Consider which ethical principles apply to each role\'s '
            'professional responsibilities.'
        ),
    },
    'obligations': {
        'depends_on': ['principles', 'roles'],
        'instruction': (
            'The following PRINCIPLES and ROLES were identified. '
            'Derive specific obligations from these principles for each role.'
        ),
    },
    'constraints': {
        'depends_on': ['obligations', 'states', 'resources'],
        'instruction': (
            'The following OBLIGATIONS, STATES, and RESOURCES were identified. '
            'Identify constraints that limit or affect the fulfillment of these '
            'obligations within the given states and available resources.'
        ),
    },
    'capabilities': {
        'depends_on': ['obligations', 'roles'],
        'instruction': (
            'The following OBLIGATIONS and ROLES were identified. '
            'Identify capabilities needed by each role to fulfill '
            'these obligations.'
        ),
    },
}


def _summarize_individual(rdf_json_ld: dict, concept_type: str) -> str:
    """
    Build a one-line summary of an individual from its rdf_json_ld data.

    Each concept type has a different "descriptor" field that best captures
    how the individual manifests in the case. The class reference field
    (e.g. principleClass, obligationClass) identifies what kind of entity
    this individual is, and the descriptor provides case-specific detail.
    """
    if not rdf_json_ld:
        return ''

    props = rdf_json_ld.get('properties', {})

    # Concept-specific descriptor fields (camelCase as stored in rdf_json_ld).
    # Each entry: (class_ref_key, [descriptor_keys in priority order])
    _INDIVIDUAL_SUMMARY_FIELDS = {
        'roles': ('roleClass', ['caseInvolvement']),
        'states': ('stateClass', ['subject', 'triggeringEvent']),
        'resources': ('resourceClass', ['usedInContext', 'documentTitle']),
        'principles': ('principleClass', ['concreteExpression', 'interpretation']),
        'obligations': ('obligationClass', ['obligationStatement', 'obligatedParty']),
        'constraints': ('constraintClass', ['constraintStatement', 'constrainedEntity']),
        'capabilities': ('capabilityClass', ['capabilityStatement', 'possessedBy']),
    }

    config = _INDIVIDUAL_SUMMARY_FIELDS.get(concept_type, (None, []))
    class_key, descriptor_keys = config

    parts = []

    # Class reference (what kind of entity)
    if class_key:
        class_val = props.get(class_key, [])
        if class_val:
            val = class_val[0] if isinstance(class_val, list) else class_val
            parts.append(val)

    # First available descriptor (how it manifests in this case)
    for key in descriptor_keys:
        val = props.get(key, [])
        if val:
            text = val[0] if isinstance(val, list) else val
            if text and len(text) > 150:
                text = text[:147] + '...'
            parts.append(text)
            break

    return ' -- '.join(parts) if parts else ''


def format_cross_concept_context(concept_type: str, case_id: int) -> str:
    """
    Load entities extracted for dependency concepts and format as prompt context.

    Queries TemporaryRDFStorage for classes and individuals of each dependency
    concept type. Returns a formatted text block the LLM can use to inform its
    extraction, or an empty string if no dependencies or no prior extractions.

    For classes, the definition from entity_definition is shown. For individuals,
    richer data is pulled from rdf_json_ld including the class reference and a
    concept-specific descriptor field (e.g. concrete_expression for principles,
    obligation_statement for obligations). This enables the methodological
    dependency chain: Roles -> Principles -> Obligations -> Constraints/Capabilities.

    Shared function so both UnifiedDualExtractor._build_prompt() and
    PromptVariableResolver.resolve_variables() produce identical prompts.
    """
    deps = CROSS_CONCEPT_DEPS.get(concept_type)
    if not deps:
        return ''

    try:
        from app.models.temporary_rdf_storage import TemporaryRDFStorage

        sections = []
        for dep_concept in deps['depends_on']:
            entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == dep_concept,
            ).all()

            if not entities:
                continue

            classes = [e for e in entities if e.storage_type == 'class']
            individuals = [e for e in entities if e.storage_type == 'individual']

            lines = [f'\n--- {dep_concept.upper()} (from prior extraction) ---']
            if classes:
                lines.append(f'Classes ({len(classes)}):')
                for cls in classes:
                    defn = cls.entity_definition or ''
                    if defn and len(defn) > 120:
                        defn = defn[:117] + '...'
                    lines.append(f'  - {cls.entity_label}: {defn}')
            if individuals:
                lines.append(f'Individuals ({len(individuals)}):')
                for ind in individuals:
                    summary = _summarize_individual(
                        ind.rdf_json_ld, dep_concept
                    )
                    if summary:
                        lines.append(f'  - {ind.entity_label}: {summary}')
                    else:
                        # Fallback to entity_definition
                        defn = ind.entity_definition or ''
                        if defn and len(defn) > 120:
                            defn = defn[:117] + '...'
                        lines.append(f'  - {ind.entity_label}: {defn}')

            sections.append('\n'.join(lines))

        if not sections:
            return ''

        header = (
            f'\n\n=== CROSS-CONCEPT CONTEXT ===\n'
            f'{deps["instruction"]}\n'
        )
        return header + '\n'.join(sections)

    except Exception as e:
        logger.warning(f"Could not load cross-concept context: {e}")
        return ''


def build_json_wrapper_suffix(concept_type: str) -> str:
    """
    Build the JSON wrapper instruction appended after the rendered template.

    Kept as a shared function (not in the template text) so that:
    - The keys always match CONCEPT_CONFIG and can't be accidentally edited.
    - Both the extractor and the prompt editor preview use the same logic.
    - Field-level requirements reinforce schema compliance at the end of the
      prompt where the LLM pays most attention.
    """
    config = CONCEPT_CONFIG.get(concept_type, {})
    classes_key = config.get('classes_key', f'new_{concept_type}_classes')
    individuals_key = config.get('individuals_key', f'{concept_type}_individuals')
    class_ref_field = config.get('class_ref_field', f'{concept_type}_class')

    base = (
        f'\n\nIMPORTANT: Wrap your response as a JSON object with exactly '
        f'two keys:\n'
        f'{{"{classes_key}": [...], "{individuals_key}": [...]}}\n'
        f'If there are no individuals to report, use an empty array for '
        f'"{individuals_key}".'
    )

    # Concept-specific field reinforcement at the very end of the prompt.
    # The LLM attends most to the final instructions.
    field_reqs = _FIELD_REQUIREMENTS.get(concept_type)
    if field_reqs:
        base += (
            f'\n\nREQUIRED FIELDS on every class: '
            f'{field_reqs["class_required"]}\n'
            f'REQUIRED FIELDS on every individual: '
            f'{field_reqs["individual_required"]}'
        )
        if field_reqs.get('match_decision_note'):
            base += f'\n{field_reqs["match_decision_note"]}'

    return base


# Per-concept required-field reminders appended by build_json_wrapper_suffix().
# Keep concise -- this is the last thing the LLM sees before generating JSON.
_FIELD_REQUIREMENTS: Dict[str, Dict[str, str]] = {
    'principles': {
        'class_required': (
            'label, definition, confidence (float 0-1), match_decision '
            '(object with matches_existing, matched_label, confidence, '
            'reasoning), principle_category (fundamental_ethical | '
            'professional_virtue | relational | domain_specific), '
            'text_references (list of direct quotes)'
        ),
        'individual_required': (
            'identifier, principle_class, confidence (float 0-1), '
            'text_references (list of direct quotes)'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object. '
            'If the class matches an existing ontology class, set '
            'matches_existing=true and matched_label to the existing label.'
        ),
    },
    'obligations': {
        'class_required': (
            'label, definition, confidence (float 0-1), match_decision, '
            'obligation_type, enforcement_level, text_references'
        ),
        'individual_required': (
            'identifier, obligation_class, confidence (float 0-1), '
            'text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object.'
        ),
    },
    'constraints': {
        'class_required': (
            'label, definition, confidence (float 0-1), match_decision, '
            'constraint_type, flexibility, text_references'
        ),
        'individual_required': (
            'identifier, constraint_class, confidence (float 0-1), '
            'severity, text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object.'
        ),
    },
    'capabilities': {
        'class_required': (
            'label, definition, confidence (float 0-1), match_decision, '
            'capability_category, skill_level, text_references'
        ),
        'individual_required': (
            'identifier, capability_class, confidence (float 0-1), '
            'text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object.'
        ),
    },
}


# Per-concept category enum inference when LLM omits the category field.
# Maps concept_type -> (field_name, [(enum_value, {keywords...}), ...]).
# Order within each list matters: checked top-to-bottom, first match wins.
# Text fields checked: label, definition, value_basis (shared across concepts).
_CATEGORY_INFERENCE: Dict[str, Tuple[str, list]] = {
    'principles': ('principle_category', [
        ('fundamental_ethical', {
            'public welfare', 'public safety', 'paramount', 'fundamental',
            'universal', 'human dignity', 'justice', 'beneficence',
            'respect for persons', 'welfare of the public',
        }),
        ('professional_virtue', {
            'integrity', 'competence', 'honesty', 'accountability',
            'virtue', 'character', 'professional excellence', 'courage',
            'responsibility', 'diligence',
        }),
        ('relational', {
            'confidentiality', 'loyalty', 'transparency', 'trust',
            'fairness', 'collegial', 'respect', 'communication',
            'disclosure', 'notification', 'consent',
        }),
        ('domain_specific', {
            'engineering', 'medical', 'legal', 'environmental',
            'stewardship', 'patient', 'domain', 'technological',
        }),
    ]),
    'obligations': ('obligation_type', [
        ('disclosure', {
            'disclose', 'disclosure', 'inform stakeholder', 'notify client',
            'report to', 'transparency',
        }),
        ('safety', {
            'safety', 'protect the public', 'harm', 'danger', 'risk',
            'public welfare', 'paramount',
        }),
        ('competence', {
            'competence', 'qualified', 'expertise', 'training requirement',
            'skill', 'proficiency',
        }),
        ('confidentiality', {
            'confidential', 'privacy', 'secret', 'non-disclosure',
            'privileged information',
        }),
        ('reporting', {
            'report violation', 'notify authorities', 'whistleblow',
            'alert regulatory', 'report to board',
        }),
        ('collegial', {
            'collegial', 'peer', 'colleague', 'fellow engineer',
            'professional relationship', 'mutual respect',
        }),
        ('legal', {
            'law', 'statute', 'regulation', 'legal requirement',
            'compliance', 'statutory',
        }),
    ]),
    'constraints': ('constraint_type', [
        ('legal', {
            'law', 'statute', 'legislation', 'legal requirement',
            'court order', 'legal prohibition',
        }),
        ('regulatory', {
            'regulation', 'code requirement', 'standard', 'building code',
            'compliance requirement', 'regulatory body',
        }),
        ('resource', {
            'budget', 'funding', 'time constraint', 'personnel',
            'limited resource', 'financial',
        }),
        ('competence', {
            'qualification', 'expertise limitation', 'training',
            'certification', 'outside competence',
        }),
        ('jurisdictional', {
            'jurisdiction', 'authority', 'boundary of practice',
            'scope of license', 'geographic',
        }),
        ('procedural', {
            'procedure', 'process requirement', 'protocol',
            'workflow', 'due process', 'notification requirement',
        }),
        ('safety', {
            'safety constraint', 'hazard', 'risk limit',
            'danger threshold', 'safety factor',
        }),
    ]),
    'capabilities': ('capability_category', [
        ('norm_management', {
            'norm', 'rule management', 'obligation tracking',
            'compliance management', 'policy',
        }),
        ('awareness', {
            'awareness', 'recognize', 'perceive', 'identify risk',
            'detect', 'situational awareness',
        }),
        ('learning', {
            'learn', 'adapt', 'update knowledge', 'improve',
            'experience', 'continuing education',
        }),
        ('reasoning', {
            'reason', 'analyze', 'evaluate', 'judge', 'assess',
            'deliberate', 'weigh', 'ethical reasoning',
        }),
        ('communication', {
            'communicate', 'inform', 'report', 'disclose',
            'articulate', 'explain', 'present',
        }),
        ('domain_specific', {
            'engineering', 'technical', 'domain knowledge',
            'specialized', 'professional expertise',
        }),
        ('retrieval', {
            'retrieve', 'access', 'reference', 'recall',
            'look up', 'precedent', 'case law',
        }),
    ]),
}


def _infer_category_enum(
    concept_type: str, item: Dict[str, Any],
) -> Optional[str]:
    """Infer a missing category enum value from item text fields.

    Works for any concept type registered in _CATEGORY_INFERENCE.
    Returns the enum value string or None if no match.
    """
    spec = _CATEGORY_INFERENCE.get(concept_type)
    if not spec:
        return None
    field_name, keyword_rules = spec
    if item.get(field_name):
        return None  # already set
    text = ' '.join(
        str(item.get(f, '')) for f in ('label', 'definition', 'value_basis')
    ).lower()
    if not text.strip():
        return None
    for enum_value, keywords in keyword_rules:
        if any(kw in text for kw in keywords):
            return enum_value
    return None


class UnifiedDualExtractor:
    """
    Parameterized extractor for any of the 9 D-Tuple concepts.

    Consolidates the shared flow:
        prompt template (DB) -> variable resolution (MCP) -> LLM call ->
        Pydantic validation -> ontology matching -> linking
    """

    def __init__(
        self,
        concept_type: str,
        llm_client: Any = None,
        model: Optional[str] = None,
    ):
        if concept_type not in CONCEPT_CONFIG:
            raise ValueError(
                f"Unknown concept_type '{concept_type}'. "
                f"Valid: {list(CONCEPT_CONFIG.keys())}"
            )

        self.concept_type = concept_type
        self.config = CONCEPT_CONFIG[concept_type]

        # -- Mock / real LLM client --
        from app.services.extraction.mock_llm_provider import (
            get_llm_client_for_extraction,
            get_current_data_source,
        )
        self.llm_client = get_llm_client_for_extraction(llm_client)
        self.data_source = get_current_data_source()

        # -- Model selection --
        from models import ModelConfig
        if model:
            self.model_name = model
        else:
            self.model_name = ModelConfig.get_claude_model(
                self.config['model_tier']
            )

        # -- MCP existing entities --
        self.existing_classes: List[Dict[str, Any]] = []
        self.mcp_client = None
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            self.mcp_client = get_external_mcp_client()
            self.existing_classes = self._load_existing_classes()
            logger.info(
                f"Loaded {len(self.existing_classes)} existing "
                f"{concept_type} classes from MCP"
            )
        except Exception as e:
            logger.warning(f"MCP client unavailable for {concept_type}: {e}")

        # -- DB prompt template --
        self.template = self._load_template()

        # -- Pydantic schemas --
        from app.services.extraction.schemas import CONCEPT_SCHEMAS, CONCEPT_MODELS
        self.result_schema = CONCEPT_SCHEMAS[concept_type]
        self.class_model, self.individual_model = CONCEPT_MODELS[concept_type]

        # -- Response caching for RDF conversion --
        self.last_raw_response: Optional[str] = None
        self.last_prompt: Optional[str] = None

        logger.info(
            f"UnifiedDualExtractor({concept_type}) initialized: "
            f"model={self.model_name}, "
            f"template={'DB' if self.template else 'NONE'}, "
            f"existing_classes={len(self.existing_classes)}"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        case_text: str,
        case_id: int,
        section_type: str = 'discussion',
    ) -> Tuple[List[BaseModel], List[BaseModel]]:
        """
        Extract candidate classes and individuals for this concept.

        Returns:
            (candidate_classes, individuals) -- both are lists of Pydantic
            model instances from schemas.py.
        """
        start = time.time()
        logger.info(
            f"Extracting {self.concept_type} for case {case_id}, "
            f"section={section_type}"
        )
        self._current_section_type = section_type

        # 1. Build prompt
        prompt = self._build_prompt(case_text, section_type, case_id=case_id)
        self.last_prompt = prompt

        # 2. Call LLM
        raw_json = self._call_llm(prompt)
        if not raw_json:
            logger.warning(f"No LLM result for {self.concept_type}")
            return [], []

        # 3. Parse + validate
        classes, individuals = self._parse_and_validate(raw_json, case_id)

        # 4. Match against existing ontology classes
        self._check_existing_matches(classes)

        # 5. Collect ontology definitions for matched entities
        self.ontology_definitions = self._collect_ontology_definitions(classes)

        # 6. Link individuals to classes
        self._link_individuals_to_classes(individuals, classes)

        elapsed = time.time() - start
        logger.info(
            f"Extracted {len(classes)} classes, {len(individuals)} individuals "
            f"for {self.concept_type} in {elapsed:.1f}s"
        )

        return classes, individuals

    def get_last_raw_response(self) -> Optional[str]:
        """Return the last raw LLM response for RDF conversion."""
        return self.last_raw_response

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _load_template(self):
        """Load the active DB prompt template for this concept."""
        try:
            from app.models.extraction_prompt_template import (
                ExtractionPromptTemplate,
            )
            template = ExtractionPromptTemplate.get_active_template(
                step_number=self.config['step'],
                concept_type=self.concept_type,
            )
            if template:
                logger.info(
                    f"Loaded DB template for {self.concept_type} "
                    f"(v{template.version})"
                )
            else:
                logger.warning(
                    f"No active DB template for step={self.config['step']}, "
                    f"concept={self.concept_type}"
                )
            return template
        except Exception as e:
            logger.error(f"Failed to load DB template: {e}")
            return None

    def _build_prompt(
        self, case_text: str, section_type: str, case_id: int = None,
    ) -> str:
        """
        Build the extraction prompt.

        Uses the DB template with PromptVariableResolver for variable
        resolution (case text + existing MCP entities).

        When section_type is not 'facts', classes already extracted from
        earlier sections (e.g. facts) are appended to the existing-entities
        list so the LLM can reference them rather than re-extracting.
        """
        if not self.template:
            raise RuntimeError(
                f"No prompt template available for {self.concept_type}. "
                f"Check extraction_prompt_templates table."
            )

        # Format existing entities for the template
        existing_text = self._format_existing_entities()

        # For non-facts sections, include classes extracted from prior sections
        if section_type != 'facts' and case_id is not None:
            prior_text = self._format_prior_section_classes(case_id, section_type)
            if prior_text:
                existing_text += prior_text

        # Load cross-concept context (e.g., roles for principles, etc.)
        cross_context = ''
        if case_id is not None:
            cross_context = format_cross_concept_context(
                self.concept_type, case_id
            )

        # Handle dict input from _format_section_for_llm()
        if isinstance(case_text, dict):
            case_text = case_text.get('llm_text') or case_text.get('html', '')
            logger.warning("case_text was a dict, extracted llm_text")

        # Strip non-printable control characters (except newline, tab, CR)
        # that may be present in source documents from PDF extraction.
        import re
        case_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', case_text)

        # Build variable dict matching the template's Jinja2 variables
        variables = {
            'case_text': case_text,
            'section_type': section_type,
            f'existing_{self.concept_type}_text': existing_text,
            'existing_entities_text': existing_text,
            'cross_concept_context': cross_context,
        }

        rendered = self.template.render(**variables)

        # Append JSON wrapper instruction so the LLM returns a dict with
        # both keys rather than a bare list.  Kept in code (not in the
        # editable template) so the keys always match CONCEPT_CONFIG.
        rendered += build_json_wrapper_suffix(self.concept_type)
        return rendered

    def _format_existing_entities(self) -> str:
        """Format existing ontology entities for prompt inclusion."""
        return format_existing_entities(self.existing_classes, self.concept_type)

    def _format_prior_section_classes(
        self, case_id: int, current_section: str,
    ) -> str:
        """
        Format classes extracted from earlier sections for this case.

        When extracting from discussion, the facts-extracted classes are
        included so the LLM can reference them instead of re-extracting.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.extraction_prompt import ExtractionPrompt

            # Determine which prior sections to include
            section_order = ['facts', 'discussion', 'questions', 'conclusions']
            current_idx = section_order.index(current_section) if current_section in section_order else 0
            prior_sections = section_order[:current_idx]

            if not prior_sections:
                return ''

            # Find extraction sessions for prior sections
            prior_sessions = [
                p.extraction_session_id
                for p in ExtractionPrompt.query.filter_by(
                    case_id=case_id,
                    concept_type=self.concept_type,
                    is_active=True,
                ).all()
                if p.extraction_session_id and p.section_type in prior_sections
            ]

            if not prior_sessions:
                return ''

            # Query classes from those sessions
            prior_classes = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == self.concept_type,
                TemporaryRDFStorage.storage_type == 'class',
                TemporaryRDFStorage.extraction_session_id.in_(prior_sessions),
            ).all()

            if not prior_classes:
                return ''

            # Format as text block with multi-source definitions
            lines = [
                f'\n\n--- {self.concept_type.upper()} CLASSES ALREADY EXTRACTED FROM PRIOR SECTIONS ---',
                'These classes were found in earlier sections of this case.',
                'Reference them via match_decision if the same concept appears here.',
                'Do NOT re-create them as new classes.\n',
            ]
            for cls in prior_classes:
                json_ld = cls.rdf_json_ld or {}
                definitions = json_ld.get('definitions', [])
                if definitions and len(definitions) > 1:
                    # Show each definition with source tag
                    lines.append(f'- {cls.entity_label}')
                    for defn_entry in definitions:
                        source_tag = defn_entry.get('source_section') or defn_entry.get('source_type', 'unknown')
                        text = defn_entry.get('text', '')
                        if text:
                            lines.append(f'  [{source_tag}] {text}')
                else:
                    defn = cls.entity_definition or ''
                    lines.append(f'- {cls.entity_label}: {defn}')

            logger.info(
                f"Added {len(prior_classes)} prior-section {self.concept_type} "
                f"classes to prompt for case {case_id}"
            )
            return '\n'.join(lines)

        except Exception as e:
            logger.warning(f"Could not load prior-section classes: {e}")
            return ''

    # ------------------------------------------------------------------
    # MCP entity loading
    # ------------------------------------------------------------------

    def _load_existing_classes(self) -> List[Dict[str, Any]]:
        """Load existing classes from MCP for ontology awareness."""
        if not self.mcp_client:
            return []

        try:
            # The PromptVariableResolver has the concept->MCP method mapping.
            # For simplicity, use get_entities_by_category which works for all.
            category_map = {
                'roles': 'Role',
                'states': 'State',
                'resources': 'Resource',
                'principles': 'Principle',
                'obligations': 'Obligation',
                'constraints': 'Constraint',
                'capabilities': 'Capability',
                'actions': 'Action',
                'events': 'Event',
            }
            category = category_map[self.concept_type]

            # Some concepts have dedicated methods on the MCP client
            method_name = f'get_all_{self.concept_type[:-1] if self.concept_type.endswith("s") else self.concept_type}_entities'
            # e.g. get_all_obligation_entities, get_all_role_entities

            if hasattr(self.mcp_client, method_name):
                entities = getattr(self.mcp_client, method_name)()
                if isinstance(entities, list):
                    return entities

            # Fallback: generic category query
            result = self.mcp_client.get_entities_by_category(category)
            if result.get('success') and result.get('result'):
                return result['result'].get('entities', [])

            return []

        except Exception as e:
            logger.error(
                f"Failed to load existing {self.concept_type} classes: {e}"
            )
            return []

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Call the LLM and parse JSON from the response."""
        try:
            # Mock client path (testing)
            if self.llm_client is not None:
                response = self.llm_client.call(
                    prompt=prompt,
                    extraction_type=self.concept_type,
                    section_type=getattr(
                        self, '_current_section_type', 'facts'
                    ),
                )
                response_text = (
                    response.content
                    if hasattr(response, 'content')
                    else str(response)
                )
                self.last_raw_response = response_text
                return extract_json_from_response(response_text)

            # Real LLM path
            from app.utils.llm_utils import get_llm_client

            client = get_llm_client()
            if not client:
                logger.error("No LLM client available")
                return {}

            logger.info(
                f"_call_llm: sending {len(prompt)} chars, "
                f"type={type(prompt).__name__}, "
                f"model={self.model_name}, "
                f"max_tokens={self.config['max_tokens']}"
            )

            # Use streaming to avoid server-side timeout on long responses.
            # Non-streaming requests fail with APIConnectionError when
            # generation exceeds ~180s (e.g., discussion principles at 7K+
            # output tokens).
            chunks = []
            with client.messages.stream(
                model=self.model_name,
                max_tokens=self.config['max_tokens'],
                temperature=self.config['temperature'],
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    chunks.append(text)

            response_text = "".join(chunks)
            self.last_raw_response = response_text

            final_msg = stream.get_final_message()
            stop_reason = final_msg.stop_reason
            logger.info(
                f"LLM stream complete: {final_msg.usage.input_tokens} in / "
                f"{final_msg.usage.output_tokens} out, stop={stop_reason}"
            )

            if stop_reason == 'max_tokens':
                logger.warning(
                    f"Response truncated at {self.config['max_tokens']} "
                    f"tokens for {self.concept_type}"
                )
                # Try to repair truncated JSON
                response_text = self._repair_truncated_json(response_text)

            logger.debug(f"LLM response ({len(response_text)} chars)")

            return extract_json_from_response(response_text)

        except Exception as e:
            logger.error(
                f"LLM call failed for {self.concept_type}: "
                f"{type(e).__name__}: {e}"
            )
            # Log full chain for connection errors
            if hasattr(e, '__cause__') and e.__cause__:
                logger.error(f"  Caused by: {type(e.__cause__).__name__}: {e.__cause__}")
            if hasattr(e, 'status_code'):
                logger.error(f"  Status code: {e.status_code}")
            if hasattr(e, 'response'):
                logger.error(f"  Response: {e.response}")
            import traceback
            logger.error(f"  Traceback: {traceback.format_exc()}")
            return {}

    # ------------------------------------------------------------------
    # Parsing + validation
    # ------------------------------------------------------------------

    def _parse_and_validate(
        self,
        raw_json: Any,
        case_id: int,
    ) -> Tuple[List[BaseModel], List[BaseModel]]:
        """
        Parse LLM JSON output into Pydantic models.

        Handles multiple response shapes:
        - Dict with classes_key and individuals_key (ideal)
        - Raw list of items (DB template format -- classes only)
        - Partial dict (only one key present)

        Tries full ExtractionResult validation first. Falls back to
        parsing classes and individuals separately if that fails.
        """
        classes_key = self.config['classes_key']
        individuals_key = self.config['individuals_key']

        # Normalize: if the LLM returned a bare list, wrap it
        if isinstance(raw_json, list):
            logger.info(
                f"LLM returned a list of {len(raw_json)} items, "
                f"wrapping as {classes_key}"
            )
            raw_json = {classes_key: raw_json}

        if not isinstance(raw_json, dict):
            logger.error(
                f"Unexpected LLM response type: {type(raw_json).__name__}"
            )
            return [], []

        # Remap legacy flat keys to the expected dual-array keys.
        # Older DB templates used a single array (e.g. "resources" instead of
        # "new_resource_classes" + "resource_individuals"). If neither expected
        # key is present but a legacy key is, treat the flat list as classes.
        if classes_key not in raw_json and individuals_key not in raw_json:
            legacy_key = self.concept_type  # e.g. 'resources', 'roles'
            if legacy_key in raw_json and isinstance(raw_json[legacy_key], list):
                logger.info(
                    f"Remapping legacy '{legacy_key}' key "
                    f"({len(raw_json[legacy_key])} items) to '{classes_key}'"
                )
                raw_json[classes_key] = raw_json.pop(legacy_key)

        # Normalize all items BEFORE validation so the primary path
        # handles enum hyphens, label->identifier, and source_text
        # fallback -- not just the fallback per-item path.
        for key in (classes_key, individuals_key):
            items = raw_json.get(key, [])
            if isinstance(items, list):
                raw_json[key] = [
                    self._normalize_field_names(item)
                    for item in items
                    if isinstance(item, dict)
                ]

        # Try validating the full ExtractionResult
        try:
            result = self.result_schema.model_validate(raw_json)
            classes = getattr(result, classes_key, [])
            individuals = getattr(result, individuals_key, [])
            logger.info(
                f"Pydantic validation OK: {len(classes)} classes, "
                f"{len(individuals)} individuals"
            )
            return classes, individuals
        except ValidationError as e:
            logger.warning(
                f"Full schema validation failed for {self.concept_type}, "
                f"falling back to per-item parsing: {e.error_count()} errors"
            )
            logger.debug(f"Keys in LLM response: {list(raw_json.keys())}")
            for err in e.errors()[:5]:
                logger.debug(f"  Validation error: {err['loc']} - {err['msg']}")

        # Fallback: parse each item individually, skipping invalid ones.
        # Items are already normalized above, but _parse_items calls
        # _normalize_field_names again (idempotent).
        classes = self._parse_items(
            raw_json.get(classes_key, []),
            self.class_model,
            'class',
            case_id,
        )
        individuals = self._parse_items(
            raw_json.get(individuals_key, []),
            self.individual_model,
            'individual',
            case_id,
        )

        return classes, individuals

    def _parse_items(
        self,
        items: List[Dict],
        model_class: type,
        item_type: str,
        case_id: int,
    ) -> List[BaseModel]:
        """Parse a list of raw dicts into Pydantic model instances."""
        parsed = []
        for i, item in enumerate(items):
            try:
                item = self._normalize_field_names(item)
                obj = model_class.model_validate(item)
                parsed.append(obj)
            except ValidationError as e:
                label = item.get('label', item.get('identifier', f'#{i}'))
                logger.warning(
                    f"Skipping invalid {self.concept_type} {item_type} "
                    f"'{label}': {e.error_count()} validation errors"
                )
                for err in e.errors():
                    logger.debug(f"  {err['loc']}: {err['msg']}")
        return parsed

    def _normalize_field_names(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize LLM field names to match Pydantic schema field names.

        DB templates and hardcoded prompts may use different field names
        for the same concept. This maps common aliases. Uses
        self.concept_type for concept-aware category inference.
        """
        # definition/description: handled by Pydantic AliasChoices on BaseCandidate
        # text_references/examples_from_case: handled by Pydantic AliasChoices

        # Bidirectional fallback between source_text and text_references
        refs = item.get('text_references') or item.get('examples_from_case')
        if not item.get('source_text') and refs:
            item['source_text'] = refs[0]
        elif item.get('source_text') and not refs:
            item['text_references'] = [item['source_text']]

        # name/label -> identifier (for individuals)
        if 'identifier' not in item:
            if 'name' in item:
                item['identifier'] = item['name']
            elif 'label' in item:
                item['identifier'] = item['label']

        # --- Remap commonly hallucinated class fields ---
        # LLM returns "balancing_requirements" instead of "potential_conflicts"
        if 'balancing_requirements' in item and 'potential_conflicts' not in item:
            item['potential_conflicts'] = item.pop('balancing_requirements')
        # LLM returns "application_context" -- no direct match, drop it
        # (this data is partially captured by extensional_examples)
        item.pop('application_context', None)
        # LLM returns "case_relevance" on individuals -- not a schema field
        item.pop('case_relevance', None)

        # NOTE: examples_from_case is NOT dropped here. Pydantic AliasChoices
        # on BaseCandidate.text_references handles it:
        #   AliasChoices('text_references', 'examples_from_case')
        # Dropping it would lose data when text_references is absent.

        # --- Default confidence when LLM omits it ---
        if 'confidence' not in item:
            item['confidence'] = 0.75

        # --- Ensure match_decision has required subfields ---
        md = item.get('match_decision')
        if isinstance(md, dict):
            md.setdefault('matches_existing', False)
            md.setdefault('confidence', 0.5)
            if not md.get('reasoning'):
                md['reasoning'] = 'No reasoning provided by LLM'
            # Remap LLM variants of matched_label
            if not md.get('matched_label'):
                for alt_key in ('matched_class', 'matched_name', 'match_label'):
                    if alt_key in md:
                        md['matched_label'] = md.pop(alt_key)
                        break
        # If LLM omits match_decision entirely on a class (has "label" key),
        # add a default so Pydantic populates the field
        if 'match_decision' not in item and 'label' in item:
            item['match_decision'] = {
                'matches_existing': False,
                'confidence': 0.5,
                'reasoning': 'match_decision omitted by LLM; post-hoc matching will resolve',
            }

        # --- Infer missing category enum from item text ---
        inferred = _infer_category_enum(self.concept_type, item)
        if inferred:
            spec = _CATEGORY_INFERENCE[self.concept_type]
            item.setdefault(spec[0], inferred)

        # Normalize hyphenated enum values to underscores
        # LLMs sometimes return "non-inertial" instead of "non_inertial"
        for enum_field in (
            'persistence_type', 'state_category', 'urgency_level',
            'role_category', 'resource_category', 'resource_type',
            'principle_category', 'obligation_type', 'enforcement_level',
            'compliance_status', 'constraint_type', 'flexibility', 'severity',
            'capability_category', 'skill_level', 'proficiency_level',
        ):
            if enum_field in item and isinstance(item[enum_field], str):
                item[enum_field] = item[enum_field].replace('-', '_')

        # Normalize compliance_status to valid ComplianceStatus enum values.
        # LLMs produce semantically equivalent but syntactically invalid values
        # (e.g. "potentially_violated", "met_after_objection"). Two-stage:
        # 1. Exact synonym map for known variants
        # 2. Keyword fallback for any novel LLM invention
        _COMPLIANCE_VALID = {'met', 'unmet', 'partial', 'unclear'}
        _COMPLIANCE_STATUS_MAP = {
            'not_met': 'unmet',
            'unknown': 'unclear',
            'partially_met': 'partial',
            'in_progress': 'partial',
            'pending': 'unclear',
            'violated': 'unmet',
            'fulfilled': 'met',
            'compliant': 'met',
            'non_compliant': 'unmet',
            'potentially_violated': 'partial',
            'met_after_objection': 'met',
        }
        cs = item.get('compliance_status')
        if cs and isinstance(cs, str) and cs not in _COMPLIANCE_VALID:
            if cs in _COMPLIANCE_STATUS_MAP:
                item['compliance_status'] = _COMPLIANCE_STATUS_MAP[cs]
            else:
                # Keyword fallback for novel LLM values.
                # Split on underscores to get word tokens, avoiding
                # substring false positives (e.g. "so_met_hing").
                tokens = set(cs.lower().replace('-', '_').split('_'))
                if tokens & {'violated', 'violation', 'breached', 'breach'}:
                    item['compliance_status'] = 'unmet'
                elif tokens & {'partial', 'partially', 'progress'}:
                    item['compliance_status'] = 'partial'
                elif tokens & {'unclear', 'unknown', 'undetermined', 'indeterminate'}:
                    item['compliance_status'] = 'unclear'
                elif tokens & {'met', 'fulfilled', 'satisfied', 'complied'}:
                    item['compliance_status'] = 'met'
                else:
                    item['compliance_status'] = 'unclear'

        return item

    # ------------------------------------------------------------------
    # Ontology matching
    # ------------------------------------------------------------------

    def _check_existing_matches(self, classes: List[BaseModel]) -> None:
        """
        Check candidate classes against existing ontology classes.

        Updates the match_decision field on each candidate.

        For classes where the LLM already set matches_existing=True but
        provided a label (not a full URI) in matched_uri, resolves the
        proper URI from self.existing_classes.
        """
        if not self.existing_classes:
            return

        # Build label -> existing entity lookup for URI resolution
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for candidate in classes:
            if candidate.match_decision.matches_existing:
                # LLM already identified a match -- resolve URI if missing
                # or invalid (LLM only sees labels, not full URIs)
                uri = candidate.match_decision.matched_uri or ''
                if not uri.startswith('http'):
                    resolve_label = (
                        candidate.match_decision.matched_label
                        or candidate.match_decision.matched_uri
                        or ''
                    )
                    norm = resolve_label.lower().replace(
                        '_', ' '
                    ).replace('-', ' ').strip()
                    resolved = existing_by_label.get(norm)
                    if resolved:
                        candidate.match_decision.matched_uri = resolved.get('uri')
                        candidate.match_decision.matched_label = (
                            resolved.get('label')
                        )
                        logger.debug(
                            f"Resolved URI for LLM-matched class "
                            f"'{candidate.label}': {resolved.get('uri')}"
                        )
                continue

            for existing in self.existing_classes:
                existing_label = existing.get('label', '')
                if self._labels_match(candidate.label, existing_label):
                    candidate.match_decision.matches_existing = True
                    candidate.match_decision.matched_uri = existing.get('uri')
                    candidate.match_decision.matched_label = existing_label
                    candidate.match_decision.confidence = 0.9
                    candidate.match_decision.reasoning = (
                        'Label match with existing ontology class'
                    )
                    break

        # Cleanup: zero out ALL orphaned match data where no URI was resolved.
        # The LLM sometimes matches against sibling extractions (from prior
        # sections) rather than the ontology list.  Those siblings have no
        # OntServe URI, so the match is invalid.  Clear everything so the DB
        # columns stay strictly "matched to an OntServe ontology entity."
        for candidate in classes:
            if not candidate.match_decision.matched_uri:
                candidate.match_decision.confidence = 0.0
                candidate.match_decision.matches_existing = False
                candidate.match_decision.matched_label = None
                candidate.match_decision.reasoning = None

    def _collect_ontology_definitions(
        self, classes: List[BaseModel],
    ) -> Dict[str, Dict[str, str]]:
        """Collect definitions from matched ontology entities.

        For each candidate class that matched an existing ontology class,
        look up the ontology entity's comment (rdfs:comment) and return it
        keyed by label.

        Returns:
            Dict mapping label -> {text, source_uri, source_ontology}
        """
        result = {}
        if not self.existing_classes:
            return result

        # Build lookup: URI -> existing entity dict
        existing_by_uri = {}
        existing_by_label = {}
        for ent in self.existing_classes:
            uri = ent.get('uri', '')
            label = ent.get('label', '')
            if uri:
                existing_by_uri[uri] = ent
            if label:
                norm = label.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = ent

        for candidate in classes:
            md = candidate.match_decision
            if not md.matches_existing:
                continue

            # Find the ontology entity via matched_uri or matched_label
            ont_entity = None
            if md.matched_uri:
                ont_entity = existing_by_uri.get(md.matched_uri)
            if not ont_entity and md.matched_label:
                norm = md.matched_label.lower().replace('_', ' ').replace('-', ' ').strip()
                ont_entity = existing_by_label.get(norm)

            ont_def = (
                ont_entity.get('description')
                or ont_entity.get('comment', '')
            ) if ont_entity else ''
            if ont_def:
                result[candidate.label] = {
                    'text': ont_def,
                    'source_uri': ont_entity.get('uri', ''),
                    'source_ontology': (
                        ont_entity.get('ontology_name')
                        or ont_entity.get('source')
                        or (ont_entity.get('metadata', {}) or {}).get('ontology', '')
                    ),
                }

        return result

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Case-insensitive exact label matching with normalization.

        Only matches when labels are identical after normalization.
        Substring containment is intentionally excluded -- the LLM
        already sees the full existing class list and makes deliberate
        match decisions.  Overriding with substring matching collapses
        legitimate specializations (e.g. 'Design Engineer Role' would
        falsely match 'Engineer Role').
        """
        norm1 = label1.lower().replace('_', ' ').replace('-', ' ').strip()
        norm2 = label2.lower().replace('_', ' ').replace('-', ' ').strip()
        return norm1 == norm2

    # ------------------------------------------------------------------
    # Individual-to-class linking
    # ------------------------------------------------------------------

    def _link_individuals_to_classes(
        self,
        individuals: List[BaseModel],
        classes: List[BaseModel],
    ) -> None:
        """
        Propagate ontology match info from classes to their individuals.

        When an individual's class reference (e.g. role_class) points to a
        newly extracted class that matched an existing ontology class, the
        individual inherits that match decision. When the reference points
        directly to an existing ontology class label, the individual gets
        a match decision linking it there.
        """
        class_ref_field = self.config['class_ref_field']

        # Build lookup: normalized label -> candidate class
        candidate_by_label = {}
        for c in classes:
            norm = c.label.lower().replace('_', ' ').replace('-', ' ').strip()
            candidate_by_label[norm] = c

        # Build lookup: normalized label -> existing ontology class dict
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for individual in individuals:
            ref_value = getattr(individual, class_ref_field, None)
            if not ref_value:
                continue

            ref_norm = ref_value.lower().replace('_', ' ').replace('-', ' ').strip()

            # Case 1: individual references a new candidate class
            matched_candidate = candidate_by_label.get(ref_norm)
            if matched_candidate:
                md = matched_candidate.match_decision
                if md.matches_existing:
                    # Cascade: class matched existing -> individual inherits
                    individual.match_decision.matches_existing = True
                    individual.match_decision.matched_uri = md.matched_uri
                    individual.match_decision.matched_label = md.matched_label
                    individual.match_decision.confidence = md.confidence
                    individual.match_decision.reasoning = (
                        f"Via class '{matched_candidate.label}': "
                        f"{md.reasoning or ''}"
                    )
                    logger.debug(
                        f"Individual '{individual.identifier}' linked to "
                        f"existing '{md.matched_label}' via class "
                        f"'{matched_candidate.label}'"
                    )
                continue

            # Case 2: individual references an existing ontology class directly
            matched_existing = existing_by_label.get(ref_norm)
            if matched_existing:
                individual.match_decision.matches_existing = True
                individual.match_decision.matched_uri = matched_existing.get('uri')
                individual.match_decision.matched_label = matched_existing.get('label')
                individual.match_decision.confidence = 0.95
                individual.match_decision.reasoning = (
                    f"Individual typed as existing ontology class "
                    f"'{matched_existing.get('label')}'"
                )
                logger.debug(
                    f"Individual '{individual.identifier}' directly references "
                    f"existing class '{matched_existing.get('label')}'"
                )

    # ------------------------------------------------------------------
    # JSON repair
    # ------------------------------------------------------------------

    @staticmethod
    def _repair_truncated_json(text: str) -> str:
        """
        Attempt to repair JSON that was truncated by max_tokens.

        Strategy: strip markdown fences, find the last complete object
        in the array, close the array.
        """
        import json
        import re

        # Strip markdown code fences
        cleaned = re.sub(r'^```(?:json)?\s*', '', text.strip())
        cleaned = re.sub(r'\s*```$', '', cleaned)

        # Try parsing as-is first
        try:
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            pass

        # Find the last complete object by tracking brace depth
        depth = 0
        last_complete_end = -1
        in_string = False
        escape_next = False

        for i, ch in enumerate(cleaned):
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    last_complete_end = i

        if last_complete_end > 0:
            repaired = cleaned[:last_complete_end + 1]
            # Close any open array
            if repaired.lstrip().startswith('['):
                repaired = repaired.rstrip().rstrip(',') + '\n]'
            try:
                json.loads(repaired)
                logger.info(
                    f"Repaired truncated JSON: kept "
                    f"{last_complete_end + 1}/{len(cleaned)} chars"
                )
                return repaired
            except json.JSONDecodeError:
                pass

        logger.warning("Could not repair truncated JSON")
        return text
