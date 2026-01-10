"""
Dual Extractor Template Seeder

Seeds extraction prompt templates from the dual_*_extractor.py files,
converting Python f-strings to Jinja2 templates.
"""

import logging
from app.models import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate

logger = logging.getLogger(__name__)


# Dual extractor template definitions
# These are extracted from the dual_*_extractor.py files and converted to Jinja2 syntax
DUAL_EXTRACTOR_TEMPLATES = [
    {
        'concept_type': 'roles',
        'step_number': 1,
        'name': 'Dual Role Extraction',
        'description': 'Extract new role classes and role individuals from case text using Kong et al. (2020) framework',
        'extractor_file': 'app/services/extraction/dual_role_extractor.py',
        'prompt_method': '_create_dual_role_extraction_prompt',
        'variable_builders': {
            'existing_roles_text': {
                'description': 'Formatted list of existing role classes from ontology',
                'builder_method': '_format_existing_roles_for_prompt',
                'source': 'MCP get_all_role_entities()'
            },
            'section_type': {
                'description': 'Section type being analyzed',
                'values': ['facts', 'discussion']
            },
            'case_text': {
                'description': 'The case text to analyze',
                'source': 'Document content'
            }
        },
        'output_schema': {
            'new_role_classes': {
                'type': 'array',
                'dataclass': 'CandidateRoleClass',
                'fields': {
                    'label': {'type': 'str', 'required': True},
                    'definition': {'type': 'str', 'required': True},
                    'distinguishing_features': {'type': 'List[str]', 'required': True},
                    'professional_scope': {'type': 'str', 'required': True},
                    'typical_qualifications': {'type': 'List[str]', 'required': True},
                    'generated_obligations': {'type': 'List[str]', 'required': False},
                    'associated_virtues': {'type': 'List[str]', 'required': False},
                    'relationship_type': {'type': 'str', 'required': False},
                    'domain_context': {'type': 'str', 'required': False},
                    'examples_from_case': {'type': 'List[str]', 'required': True},
                    'source_text': {'type': 'str', 'required': False}
                }
            },
            'role_individuals': {
                'type': 'array',
                'dataclass': 'RoleIndividual',
                'fields': {
                    'name': {'type': 'str', 'required': True},
                    'role_classification': {'type': 'str', 'required': True},
                    'attributes': {'type': 'Dict[str, Any]', 'required': True},
                    'relationships': {'type': 'List[Dict]', 'required': True},
                    'case_involvement': {'type': 'str', 'required': False},
                    'source_text': {'type': 'str', 'required': False}
                }
            }
        },
        'template_text': '''DUAL ROLE EXTRACTION - Professional Roles Analysis

EXISTING ROLE CLASSES IN ONTOLOGY:
{{ existing_roles_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract information at TWO levels:

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
{{ case_text }}

Respond with valid JSON in this format:
{
    "new_role_classes": [
        {
            "label": "Environmental Compliance Specialist",
            "definition": "Professional responsible for ensuring projects meet environmental regulations and standards",
            "distinguishing_features": ["Environmental regulation expertise", "Compliance assessment capabilities", "EPA standards knowledge"],
            "professional_scope": "Environmental impact assessment, regulatory compliance review, permit coordination",
            "typical_qualifications": ["Environmental engineering degree", "Regulatory compliance experience", "Knowledge of EPA standards"],
            "generated_obligations": ["Ensure regulatory compliance", "Report violations", "Maintain environmental standards"],
            "associated_virtues": ["Environmental stewardship", "Regulatory integrity", "Technical competence"],
            "relationship_type": "Provider-Client",
            "domain_context": "Engineering",
            "examples_from_case": ["Engineer A was retained to prepare environmental assessment"],
            "source_text": "Engineer A was retained to prepare environmental assessment"
        }
    ],
    "role_individuals": [
        {
            "name": "Engineer A",
            "role_classification": "Environmental Compliance Specialist",
            "attributes": {
                "title": "Engineer",
                "license": "professional engineering license",
                "specialization": "environmental engineer",
                "experience": "several years of experience"
            },
            "relationships": [
                {"type": "retained_by", "target": "Client W"}
            ],
            "case_involvement": "Retained to prepare comprehensive report addressing organic compound characteristics",
            "source_text": "Engineer A, a professional engineer with several years of experience, was retained by Client W"
        }
    ]
}'''
    },

    {
        'concept_type': 'states',
        'step_number': 1,
        'name': 'Dual States Extraction',
        'description': 'Extract new state classes and state individuals (fluents) from case text',
        'extractor_file': 'app/services/extraction/dual_states_extractor.py',
        'prompt_method': '_create_dual_states_extraction_prompt',
        'variable_builders': {
            'existing_states_text': {
                'description': 'Formatted list of existing state classes from ontology',
                'builder_method': '_format_existing_states_for_prompt',
                'source': 'MCP get_entities_by_category(State)'
            },
            'section_type': {
                'description': 'Section type being analyzed',
                'values': ['facts', 'discussion']
            },
            'case_text': {
                'description': 'The case text to analyze',
                'source': 'Document content'
            }
        },
        'output_schema': {
            'new_state_classes': {
                'type': 'array',
                'dataclass': 'CandidateStateClass',
                'fields': {
                    'label': {'type': 'str', 'required': True},
                    'definition': {'type': 'str', 'required': True},
                    'activation_conditions': {'type': 'List[str]', 'required': True},
                    'termination_conditions': {'type': 'List[str]', 'required': True},
                    'persistence_type': {'type': 'str', 'required': True},
                    'affected_obligations': {'type': 'List[str]', 'required': False}
                }
            },
            'state_individuals': {
                'type': 'array',
                'dataclass': 'StateIndividual',
                'fields': {
                    'identifier': {'type': 'str', 'required': True},
                    'state_class': {'type': 'str', 'required': True},
                    'subject': {'type': 'str', 'required': True},
                    'active_period': {'type': 'str', 'required': False}
                }
            }
        },
        'template_text': '''DUAL STATES EXTRACTION - Professional States (Fluents) Analysis

EXISTING STATE CLASSES IN ONTOLOGY:
{{ existing_states_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract information at TWO levels:

LEVEL 1 - NEW STATE CLASSES: Identify professional states that appear to be NEW types not covered by existing classes above.
States are time-varying properties (fluents) that:
- Persist until explicitly changed by events or actions
- Enable or disable certain actions
- Activate or deactivate obligations

For each NEW state class, provide:
- label: Clear state name (e.g., "Conflict of Interest State", "Emergency Condition")
- definition: Description of what this state represents
- activation_conditions: What causes this state to become active
- termination_conditions: What causes this state to end
- persistence_type: "inertial" (persists until changed) or "momentary" (instant)
- affected_obligations: Which obligations are activated/deactivated by this state
- source_text: EXACT text snippet where this state is identified

LEVEL 2 - STATE INDIVIDUALS: Identify specific state instances in the case.
- identifier: Descriptive identifier (e.g., "Engineer_A_Conflict_State_1")
- state_class: Which state class this is an instance of
- subject: Who/what is in this state
- active_period: When this state is active
- triggering_event: What event initiated this state
- source_text: EXACT text snippet

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_state_classes": [...],
    "state_individuals": [...]
}'''
    },

    {
        'concept_type': 'resources',
        'step_number': 1,
        'name': 'Dual Resources Extraction',
        'description': 'Extract new resource classes and resource individuals from case text',
        'extractor_file': 'app/services/extraction/dual_resources_extractor.py',
        'prompt_method': '_create_dual_resources_extraction_prompt',
        'variable_builders': {
            'existing_resources_text': {
                'description': 'Formatted list of existing resource classes from ontology',
                'builder_method': '_format_existing_resources_for_prompt',
                'source': 'MCP get_entities_by_category(Resource)'
            },
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze', 'source': 'Document content'}
        },
        'output_schema': {
            'new_resource_classes': {'type': 'array', 'dataclass': 'CandidateResourceClass'},
            'resource_individuals': {'type': 'array', 'dataclass': 'ResourceIndividual'}
        },
        'template_text': '''DUAL RESOURCES EXTRACTION - Professional Resources Analysis

EXISTING RESOURCE CLASSES IN ONTOLOGY:
{{ existing_resources_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract resources at TWO levels:

LEVEL 1 - NEW RESOURCE CLASSES: Professional codes, standards, guidelines, precedents
LEVEL 2 - RESOURCE INDIVIDUALS: Specific documents, sections, citations

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_resource_classes": [...],
    "resource_individuals": [...]
}'''
    },

    {
        'concept_type': 'principles',
        'step_number': 2,
        'name': 'Dual Principles Extraction',
        'description': 'Extract new principle classes and principle instances from case text',
        'extractor_file': 'app/services/extraction/dual_principles_extractor.py',
        'prompt_method': '_create_dual_principle_extraction_prompt',
        'variable_builders': {
            'existing_principles_text': {
                'description': 'Formatted list of existing principles from ontology',
                'builder_method': '_format_existing_principles_for_prompt'
            },
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_principle_classes': {'type': 'array', 'dataclass': 'CandidatePrincipleClass'},
            'principle_individuals': {'type': 'array', 'dataclass': 'PrincipleIndividual'}
        },
        'template_text': '''DUAL PRINCIPLES EXTRACTION - Ethical Principles Analysis

EXISTING PRINCIPLES IN ONTOLOGY:
{{ existing_principles_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract principles at TWO levels:

LEVEL 1 - NEW PRINCIPLE CLASSES: Abstract ethical commitments that guide professional behavior
LEVEL 2 - PRINCIPLE INDIVIDUALS: Specific applications/invocations of principles in this case

For principles, focus on:
- Fundamental ethical commitments (public safety, integrity)
- Professional virtue principles (honesty, competence)
- Operationalization: how abstract principles become concrete duties

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_principle_classes": [...],
    "principle_individuals": [...]
}'''
    },

    {
        'concept_type': 'obligations',
        'step_number': 2,
        'name': 'Dual Obligations Extraction',
        'description': 'Extract new obligation classes and obligation instances from case text',
        'extractor_file': 'app/services/extraction/dual_obligations_extractor.py',
        'prompt_method': '_create_dual_obligations_extraction_prompt',
        'variable_builders': {
            'existing_obligations_text': {'description': 'Existing obligations from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_obligation_classes': {'type': 'array', 'dataclass': 'CandidateObligationClass'},
            'obligation_individuals': {'type': 'array', 'dataclass': 'ObligationIndividual'}
        },
        'template_text': '''DUAL OBLIGATIONS EXTRACTION - Professional Obligations Analysis

EXISTING OBLIGATIONS IN ONTOLOGY:
{{ existing_obligations_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract obligations at TWO levels:

LEVEL 1 - NEW OBLIGATION CLASSES: Normative requirements that bind professionals
LEVEL 2 - OBLIGATION INDIVIDUALS: Specific duties being fulfilled/violated in this case

Obligations are:
- Derived from principles (operationalized ethical commitments)
- Bound to specific roles
- Can conflict with each other

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_obligation_classes": [...],
    "obligation_individuals": [...]
}'''
    },

    {
        'concept_type': 'constraints',
        'step_number': 2,
        'name': 'Dual Constraints Extraction',
        'description': 'Extract new constraint classes and constraint instances from case text',
        'extractor_file': 'app/services/extraction/dual_constraints_extractor.py',
        'prompt_method': '_create_dual_constraints_extraction_prompt',
        'variable_builders': {
            'existing_constraints_text': {'description': 'Existing constraints from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_constraint_classes': {'type': 'array', 'dataclass': 'CandidateConstraintClass'},
            'constraint_individuals': {'type': 'array', 'dataclass': 'ConstraintIndividual'}
        },
        'template_text': '''DUAL CONSTRAINTS EXTRACTION - Professional Constraints Analysis

EXISTING CONSTRAINTS IN ONTOLOGY:
{{ existing_constraints_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract constraints at TWO levels:

LEVEL 1 - NEW CONSTRAINT CLASSES: Prohibitions or limitations on professional action
LEVEL 2 - CONSTRAINT INDIVIDUALS: Specific constraints active in this case

Constraints are:
- Legal, regulatory, resource, or competence-based limitations
- May be defeasible (overridable in exceptional circumstances)
- Complement obligations (what must NOT be done)

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_constraint_classes": [...],
    "constraint_individuals": [...]
}'''
    },

    {
        'concept_type': 'capabilities',
        'step_number': 2,
        'name': 'Dual Capabilities Extraction',
        'description': 'Extract new capability classes and capability instances from case text',
        'extractor_file': 'app/services/extraction/dual_capabilities_extractor.py',
        'prompt_method': '_create_dual_capabilities_extraction_prompt',
        'variable_builders': {
            'existing_capabilities_text': {'description': 'Existing capabilities from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_capability_classes': {'type': 'array', 'dataclass': 'CandidateCapabilityClass'},
            'capability_individuals': {'type': 'array', 'dataclass': 'CapabilityIndividual'}
        },
        'template_text': '''DUAL CAPABILITIES EXTRACTION - Professional Capabilities Analysis

EXISTING CAPABILITIES IN ONTOLOGY:
{{ existing_capabilities_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract capabilities at TWO levels:

LEVEL 1 - NEW CAPABILITY CLASSES: Competencies required to fulfill obligations
LEVEL 2 - CAPABILITY INDIVIDUALS: Specific capabilities possessed/needed in this case

Capabilities include:
- Technical capabilities (domain expertise)
- Ethical reasoning capabilities (moral judgment)
- Meta-capabilities (knowing limits of own capabilities)

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_capability_classes": [...],
    "capability_individuals": [...]
}'''
    },

    {
        'concept_type': 'actions',
        'step_number': 3,
        'name': 'Dual Actions Extraction',
        'description': 'Extract new action classes and action instances from case text',
        'extractor_file': 'app/services/extraction/dual_actions_extractor.py',
        'prompt_method': '_create_dual_actions_extraction_prompt',
        'variable_builders': {
            'existing_actions_text': {'description': 'Existing actions from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_action_classes': {'type': 'array', 'dataclass': 'CandidateActionClass'},
            'action_individuals': {'type': 'array', 'dataclass': 'ActionIndividual'}
        },
        'template_text': '''DUAL ACTIONS EXTRACTION - Professional Actions Analysis

EXISTING ACTIONS IN ONTOLOGY:
{{ existing_actions_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract actions at TWO levels:

LEVEL 1 - NEW ACTION CLASSES: Volitional professional activities
LEVEL 2 - ACTION INDIVIDUALS: Specific actions taken in this case

CRITICAL DISTINCTION:
- ACTIONS = Volitional choices BY agents (engineer decides to report)
- EVENTS = Occurrences that happen (discovery is made, deadline arrives)

Actions fulfill obligations, require capabilities, and may cause events.

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_action_classes": [...],
    "action_individuals": [...]
}'''
    },

    {
        'concept_type': 'events',
        'step_number': 3,
        'name': 'Dual Events Extraction',
        'description': 'Extract new event classes and event instances from case text',
        'extractor_file': 'app/services/extraction/dual_events_extractor.py',
        'prompt_method': '_create_dual_events_extraction_prompt',
        'variable_builders': {
            'existing_events_text': {'description': 'Existing events from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_event_classes': {'type': 'array', 'dataclass': 'CandidateEventClass'},
            'event_individuals': {'type': 'array', 'dataclass': 'EventIndividual'}
        },
        'template_text': '''DUAL EVENTS EXTRACTION - Professional Events Analysis

EXISTING EVENTS IN ONTOLOGY:
{{ existing_events_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract events at TWO levels:

LEVEL 1 - NEW EVENT CLASSES: Temporal occurrences that trigger ethical considerations
LEVEL 2 - EVENT INDIVIDUALS: Specific events that occurred in this case

CRITICAL DISTINCTION:
- EVENTS = Occurrences (discovery happens, deadline arrives, failure occurs)
- ACTIONS = Volitional choices BY agents (engineer decides, manager orders)

Events trigger obligations, change states, and may be caused by actions.

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_event_classes": [...],
    "event_individuals": [...]
}'''
    },

    {
        'concept_type': 'actions_events',
        'step_number': 3,
        'name': 'Combined Actions & Events Extraction',
        'description': 'Extract both actions and events together for temporal coherence',
        'extractor_file': 'app/services/extraction/dual_actions_events_extractor.py',
        'prompt_method': '_create_dual_temporal_extraction_prompt',
        'variable_builders': {
            'existing_actions_text': {'description': 'Existing actions from ontology'},
            'existing_events_text': {'description': 'Existing events from ontology'},
            'section_type': {'description': 'Section type', 'values': ['facts', 'discussion']},
            'case_text': {'description': 'Case text to analyze'}
        },
        'output_schema': {
            'new_action_classes': {'type': 'array', 'dataclass': 'CandidateActionClass'},
            'action_individuals': {'type': 'array', 'dataclass': 'ActionIndividual'},
            'new_event_classes': {'type': 'array', 'dataclass': 'CandidateEventClass'},
            'event_individuals': {'type': 'array', 'dataclass': 'EventIndividual'}
        },
        'template_text': '''COMBINED TEMPORAL EXTRACTION - Actions & Events Analysis

EXISTING ACTIONS IN ONTOLOGY:
{{ existing_actions_text }}

EXISTING EVENTS IN ONTOLOGY:
{{ existing_events_text }}

=== TASK ===
From the following case text ({{ section_type }} section), extract BOTH actions and events.

ACTIONS (volitional):
- Choices made by agents
- Fulfill or violate obligations
- Require capabilities

EVENTS (occurrences):
- Happen at points in time
- May be caused by actions or external
- Trigger obligations, change states

CASE TEXT:
{{ case_text }}

Respond with valid JSON:
{
    "new_action_classes": [...],
    "action_individuals": [...],
    "new_event_classes": [...],
    "event_individuals": [...]
}'''
    }
]


def seed_dual_extractor_templates(replace_existing: bool = False):
    """Seed dual extractor templates into the database.

    Args:
        replace_existing: If True, deactivate existing templates and create new ones.
                         If False, skip concepts that already have active templates.
    """
    logger.info("Seeding dual extractor templates...")

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for template_data in DUAL_EXTRACTOR_TEMPLATES:
        concept_type = template_data['concept_type']

        # Check if template already exists
        existing = ExtractionPromptTemplate.query.filter_by(
            concept_type=concept_type,
            is_active=True
        ).first()

        if existing:
            if replace_existing:
                # Update existing template in place rather than creating new one
                existing.name = template_data['name']
                existing.description = template_data['description']
                existing.template_text = template_data['template_text']
                existing.variables_schema = template_data['variable_builders']
                existing.source_file = template_data['extractor_file']
                existing.extractor_file = template_data['extractor_file']
                existing.prompt_method = template_data['prompt_method']
                existing.variable_builders = template_data['variable_builders']
                existing.output_schema = template_data['output_schema']
                existing.domain = 'engineering'
                existing.version += 1
                logger.info(f"Updated existing template for {concept_type} to v{existing.version}")
                updated_count += 1
                continue
            else:
                logger.info(f"Template for {concept_type} already exists, skipping")
                skipped_count += 1
                continue

        # Create new template
        template = ExtractionPromptTemplate(
            step_number=template_data['step_number'],
            concept_type=concept_type,
            pass_type='all',
            name=template_data['name'],
            description=template_data['description'],
            template_text=template_data['template_text'],
            variables_schema=template_data['variable_builders'],
            source_file=template_data['extractor_file'],
            extractor_file=template_data['extractor_file'],
            prompt_method=template_data['prompt_method'],
            variable_builders=template_data['variable_builders'],
            output_schema=template_data['output_schema'],
            domain='engineering',
            created_by='dual_extractor_seeder',
            is_active=True,
            version=1
        )

        db.session.add(template)
        created_count += 1
        logger.info(f"Created template for {concept_type} (step {template_data['step_number']})")

    db.session.commit()

    logger.info(f"Seeding complete: {created_count} created, {updated_count} updated, {skipped_count} skipped")
    return created_count, updated_count, skipped_count


def run_seeder(replace_existing: bool = False):
    """Run the seeder from Flask shell or command line."""
    from flask import current_app
    with current_app.app_context():
        return seed_dual_extractor_templates(replace_existing)


if __name__ == '__main__':
    import sys
    sys.path.insert(0, '/home/chris/onto/proethica')
    from app import create_app
    app = create_app()
    with app.app_context():
        replace = '--replace' in sys.argv
        seed_dual_extractor_templates(replace_existing=replace)
