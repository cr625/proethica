"""
Seeder for guideline extraction prompt templates.

Creates initial templates for:
- Provision Structure: Extract hierarchical provision structure
- Provision Concepts: Identify what each provision establishes
- Provision Linkage: Link provisions to ontology entities
"""

from datetime import datetime
from app.models import db
from app.models.extraction_prompt_template import ExtractionPromptTemplate


GUIDELINE_TEMPLATES = [
    {
        'extraction_type': 'guideline',
        'step_number': 0,
        'concept_type': 'provision_structure',
        'pass_type': 'all',
        'name': 'Provision Structure Extraction',
        'description': 'Extract hierarchical provision structure from ethics codes (canons, rules, sections)',
        'domain': 'engineering',
        'extractor_file': 'app/services/guideline_analysis_service.py',
        'prompt_method': 'extract_provisions',
        'variable_builders': {
            'guideline_text': {
                'description': 'Full text of the ethics code',
                'source': 'Guideline.content'
            },
            'guideline_title': {
                'description': 'Title of the ethics code',
                'source': 'Guideline.title'
            },
            'existing_provisions': {
                'description': 'Already extracted provisions (for incremental extraction)',
                'source': 'GuidelineSection.query(guideline_id)'
            }
        },
        'output_schema': {
            'provisions': {
                'type': 'array',
                'items': {
                    'provision_code': {'type': 'string', 'description': 'Section reference (e.g., "II.1.c")'},
                    'provision_text': {'type': 'string', 'description': 'Full provision text'},
                    'provision_category': {'type': 'string', 'enum': ['fundamental_canons', 'rules_of_practice', 'professional_obligations']},
                    'parent_code': {'type': 'string', 'description': 'Parent provision code if nested'},
                    'hierarchy_level': {'type': 'integer', 'description': '0=canon, 1=rule, 2=sub-rule'}
                }
            }
        },
        'template_text': """PROVISION STRUCTURE EXTRACTION

You are analyzing an ethics code document to extract its hierarchical provision structure.

ETHICS CODE TITLE:
{{ guideline_title }}

DOCUMENT TEXT:
{{ guideline_text }}

{% if existing_provisions %}
ALREADY EXTRACTED PROVISIONS (do not duplicate):
{{ existing_provisions }}
{% endif %}

=== TASK ===
Extract all provisions from this ethics code, preserving the hierarchical structure.

For each provision, identify:
1. provision_code: The official section reference (e.g., "I", "II.1", "II.1.a")
2. provision_text: The complete text of the provision
3. provision_category: One of "fundamental_canons", "rules_of_practice", or "professional_obligations"
4. parent_code: The parent provision code (if this is a sub-provision)
5. hierarchy_level: 0 for top-level canons, 1 for rules, 2 for sub-rules

Respond with valid JSON:
{
    "provisions": [
        {
            "provision_code": "I",
            "provision_text": "Hold paramount the safety, health, and welfare of the public.",
            "provision_category": "fundamental_canons",
            "parent_code": null,
            "hierarchy_level": 0
        },
        ...
    ]
}
"""
    },
    {
        'extraction_type': 'guideline',
        'step_number': 0,
        'concept_type': 'provision_concepts',
        'pass_type': 'all',
        'name': 'Provision Concept Identification',
        'description': 'Identify principles, obligations, and constraints each provision establishes',
        'domain': 'engineering',
        'extractor_file': 'app/services/guideline_concept_integration_service.py',
        'prompt_method': 'identify_concepts',
        'variable_builders': {
            'provision_code': {
                'description': 'The provision section code',
                'source': 'GuidelineSection.section_number'
            },
            'provision_text': {
                'description': 'The full text of the provision',
                'source': 'GuidelineSection.text'
            },
            'existing_principles': {
                'description': 'Existing principles in the ontology',
                'source': 'MCP get_entities_by_category(Principle)'
            },
            'existing_obligations': {
                'description': 'Existing obligations in the ontology',
                'source': 'MCP get_entities_by_category(Obligation)'
            }
        },
        'output_schema': {
            'concepts': {
                'type': 'array',
                'items': {
                    'concept_type': {'type': 'string', 'enum': ['Principle', 'Obligation', 'Constraint', 'Capability']},
                    'label': {'type': 'string', 'description': 'Short label for the concept'},
                    'definition': {'type': 'string', 'description': 'Definition derived from provision'},
                    'existing_match': {'type': 'string', 'description': 'IRI of matching existing concept, if any'}
                }
            }
        },
        'template_text': """PROVISION CONCEPT IDENTIFICATION

Analyze this provision to identify the ethical concepts it establishes.

PROVISION CODE: {{ provision_code }}
PROVISION TEXT:
{{ provision_text }}

EXISTING PRINCIPLES IN ONTOLOGY:
{{ existing_principles }}

EXISTING OBLIGATIONS IN ONTOLOGY:
{{ existing_obligations }}

=== TASK ===
Identify what ethical concepts this provision establishes. Each provision typically establishes:
- Principles: Fundamental ethical values or goals (e.g., "Public Safety", "Professional Integrity")
- Obligations: Specific duties that must be fulfilled (e.g., "Maintain Confidentiality")
- Constraints: Limitations or prohibitions (e.g., "No Conflicts of Interest")
- Capabilities: Enabled actions or permissions (e.g., "May Disclose When Required by Law")

For each concept:
1. Determine if it matches an existing ontology entity
2. If it matches, provide the existing IRI
3. If new, provide a label and definition

Respond with valid JSON:
{
    "concepts": [
        {
            "concept_type": "Obligation",
            "label": "Maintain Confidentiality",
            "definition": "Engineers shall not disclose confidential information without consent",
            "existing_match": null
        },
        {
            "concept_type": "Principle",
            "label": "Public Safety",
            "definition": "The paramount importance of protecting public safety, health, and welfare",
            "existing_match": "http://proethica.org/ontology/intermediate#PublicSafety"
        }
    ]
}
"""
    },
    {
        'extraction_type': 'guideline',
        'step_number': 0,
        'concept_type': 'provision_linkage',
        'pass_type': 'all',
        'name': 'Provision-to-Entity Linkage',
        'description': 'Create formal links between provisions and ontology entities',
        'domain': 'engineering',
        'extractor_file': 'app/services/guideline_concept_type_mapper.py',
        'prompt_method': 'create_linkages',
        'variable_builders': {
            'provision_code': {
                'description': 'The provision section code',
                'source': 'GuidelineSection.section_number'
            },
            'provision_text': {
                'description': 'The full text of the provision',
                'source': 'GuidelineSection.text'
            },
            'identified_concepts': {
                'description': 'Concepts identified from provision_concepts phase',
                'source': 'Previous extraction output'
            },
            'ontology_entities': {
                'description': 'Full list of relevant ontology entities',
                'source': 'MCP sparql_query'
            }
        },
        'output_schema': {
            'linkages': {
                'type': 'array',
                'items': {
                    'provision_uri': {'type': 'string', 'description': 'IRI of the provision'},
                    'relationship': {'type': 'string', 'enum': ['establishes', 'reinforces', 'constrains', 'enables']},
                    'entity_uri': {'type': 'string', 'description': 'IRI of the linked entity'},
                    'confidence': {'type': 'number', 'description': '0.0-1.0 confidence score'}
                }
            }
        },
        'template_text': """PROVISION-TO-ENTITY LINKAGE

Create formal ontology links between this provision and entities.

PROVISION CODE: {{ provision_code }}
PROVISION TEXT:
{{ provision_text }}

IDENTIFIED CONCEPTS (from previous analysis):
{{ identified_concepts }}

ONTOLOGY ENTITIES:
{{ ontology_entities }}

=== TASK ===
Create formal linkages between the provision and ontology entities.

Relationship types:
- establishes: This provision creates/defines this concept (primary relationship)
- reinforces: This provision strengthens an existing concept
- constrains: This provision limits or qualifies a concept
- enables: This provision grants permission or capability

For each linkage, provide:
1. The provision URI (will be generated from code)
2. The relationship type
3. The target entity URI
4. A confidence score (0.0-1.0)

Respond with valid JSON:
{
    "linkages": [
        {
            "provision_uri": "http://proethica.org/ontology/provisions#NSPE_II_1_c",
            "relationship": "establishes",
            "entity_uri": "http://proethica.org/ontology/intermediate#Confidentiality",
            "confidence": 0.95
        },
        {
            "provision_uri": "http://proethica.org/ontology/provisions#NSPE_II_1_c",
            "relationship": "constrains",
            "entity_uri": "http://proethica.org/ontology/intermediate#ClientRelationship",
            "confidence": 0.8
        }
    ]
}
"""
    }
]


def seed_guideline_templates():
    """Create initial guideline extraction templates."""
    created = 0
    updated = 0

    for template_data in GUIDELINE_TEMPLATES:
        # Check if template already exists
        existing = ExtractionPromptTemplate.query.filter_by(
            extraction_type=template_data['extraction_type'],
            step_number=template_data['step_number'],
            concept_type=template_data['concept_type'],
            domain=template_data.get('domain', 'engineering')
        ).first()

        if existing:
            # Update existing template
            for key, value in template_data.items():
                if key != 'template_text' or not existing.template_text:
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            updated += 1
        else:
            # Create new template
            template = ExtractionPromptTemplate(
                **template_data,
                version=1,
                is_active=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                created_by='system_seeder'
            )
            db.session.add(template)
            created += 1

    db.session.commit()
    return {'created': created, 'updated': updated}


if __name__ == '__main__':
    # Allow running as standalone script
    import sys
    sys.path.insert(0, '/home/chris/onto/proethica')

    from app import create_app
    app = create_app()

    with app.app_context():
        result = seed_guideline_templates()
        print(f"Seeded guideline templates: {result['created']} created, {result['updated']} updated")
