"""Per-concept configuration tables and standalone prompt/context helpers.

Pure data plus free functions split out of the former unified_dual_extractor.py
(services modularization, 2026-06-19) so the extractor class, its mixins, and the
external consumers (prompt_variable_resolver, prompt_editor, ontserve_ops) all
share one definition. The public dotted import path
``app.services.extraction.unified_dual_extractor`` is preserved via the package
__init__ re-export, so callers are unchanged.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Maps the extractor's concept_type to the core D-tuple category a candidate of
# that type belongs to. Mirrors the category_map in _load_existing_classes; the
# cross-category matcher gate uses it as the candidate's category.
CONCEPT_TYPE_TO_CORE_CATEGORY: Dict[str, str] = {
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
        'max_tokens': 32000,  # discussion-pass ceiling: 16384 truncated verbose roles (case 7) + constraints (case 8); 32000 matches the edge extractors
        'classes_key': 'new_role_classes',
        'individuals_key': 'role_individuals',
        'class_ref_field': 'role_class',
    },
    'states': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 32000,
        'classes_key': 'new_state_classes',
        'individuals_key': 'state_individuals',
        'class_ref_field': 'state_class',
    },
    'resources': {
        'step': 1,
        'model_tier': 'powerful',
        'temperature': 0.3,
        'max_tokens': 32000,
        'classes_key': 'new_resource_classes',
        'individuals_key': 'resource_individuals',
        'class_ref_field': 'resource_class',
    },
    'principles': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.5,
        'max_tokens': 32000,
        'classes_key': 'new_principle_classes',
        'individuals_key': 'principle_individuals',
        'class_ref_field': 'principle_class',
    },
    'obligations': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 32000,
        'classes_key': 'new_obligation_classes',
        'individuals_key': 'obligation_individuals',
        'class_ref_field': 'obligation_class',
    },
    'constraints': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 32000,
        'classes_key': 'new_constraint_classes',
        'individuals_key': 'constraint_individuals',
        'class_ref_field': 'constraint_class',
    },
    'capabilities': {
        'step': 2,
        'model_tier': 'powerful',
        'temperature': 0.2,
        'max_tokens': 32000,
        'classes_key': 'new_capability_classes',
        'individuals_key': 'capability_individuals',
        'class_ref_field': 'capability_class',
    },
    'actions': {
        'step': 3,
        'model_tier': 'powerful',
        'temperature': 0.7,
        'max_tokens': 32000,
        'classes_key': 'new_action_classes',
        'individuals_key': 'action_individuals',
        'class_ref_field': 'action_class',
    },
    'events': {
        'step': 3,
        'model_tier': 'powerful',
        'temperature': 0.7,
        'max_tokens': 32000,
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
#   States/Actions -> Events (initiates/terminates and action-result links)

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
    'events': {
        'depends_on': ['states', 'actions'],
        'instruction': (
            'The following STATES and ACTIONS were identified. '
            'When an event initiates or terminates a state, reference '
            'these state labels; when an event results from an action, '
            'reference these action labels.'
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
        'resources': ('resourceClass', ['documentTitle', 'topic']),
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
            if dep_concept in ('actions', 'events'):
                # Step-3 rows are stored under the temporal extraction type with
                # the concept as entity_type; a bare extraction_type filter finds
                # zero rows and silently empties the section (A/E properties review).
                entities = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.case_id == case_id,
                    TemporaryRDFStorage.extraction_type == 'temporal_dynamics_enhanced',
                    TemporaryRDFStorage.entity_type == dep_concept,
                ).all()
            else:
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
            'obligation_type (disclosure | safety | competence | '
            'confidentiality | reporting | collegial | attribution | legal | ethical), '
            'derived_from_principle, text_references'
        ),
        'individual_required': (
            'identifier, obligation_class, obligated_party, '
            'obligation_statement, confidence (float 0-1), text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object.'
        ),
    },
    'constraints': {
        'class_required': (
            'label, definition (the prohibition), confidence (float 0-1), '
            'match_decision, constraint_type (legal | regulatory | resource | '
            'competence | jurisdictional | procedural | safety | confidentiality '
            '| ethical | temporal), text_references'
        ),
        'individual_required': (
            'identifier, constraint_class, constraint_statement, '
            'applicability_condition, confidence (float 0-1), severity, '
            'text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object. A constraint is '
            'a PROHIBITION; a positive "shall do" duty is an obligation, not a constraint.'
        ),
    },
    'capabilities': {
        'class_required': (
            'label (a tool/actor-neutral competence kind), definition, '
            'confidence (float 0-1), match_decision, text_references'
        ),
        'individual_required': (
            'identifier, capability_class, possessed_by, '
            'required_for_obligations (extracted obligation labels of THIS case '
            'that presuppose the capability; empty list when none), '
            'confidence (float 0-1), text_references'
        ),
        'match_decision_note': (
            'Every new class MUST include a match_decision object. Extract only a '
            'competence the agent POSSESSES or exercises; drop a lacked competence.'
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
        ('attribution', {
            'attribution', 'give credit', 'credit for engineering work',
            'citation', 'authorship', 'proprietary interests',
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
            ('confidentiality', {
            'confidential', 'privacy', 'proprietary information', 'nondisclosure',
        }),
        ('ethical', {
            'ethical boundary', 'ethics rule', 'moral boundary',
        }),
        ('temporal', {
            'deadline', 'time limit', 'expiration', 'within the period',
        }),
    ]),
    # capabilities: inference retired 2026-07-07 (the capability_category field was
    # dropped; the kind rides the class label via match_decision).
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
