"""Fixture inputs shared by the batch-analysis golden capture and parity tests.

The golden files in tests/fixtures/step4_prompt_golden/ were captured from the
pre-migration inline prompt builders with EXACTLY these inputs (scratch capture
script, 2026-07-10, step4-template-migration batch-analysis); the parity tests
re-run the migrated builders on the same inputs and assert byte-equality.
Editing an input here invalidates its golden files.

Covers P13 step4_provision_validate, P14 step4_provision_link (two variants:
different entity type and empty case summary), P16 step4_precedents,
P17 step4_transformation (full and reduced variants), and
P18 step4_obligation_relevance.
"""

from types import SimpleNamespace


def provision_validate_inputs():
    return {
        'provision_code': 'II.4.e',
        'provision_text': (
            'Engineers shall not solicit or accept a contract from a governmental '
            'body on which a principal or officer of their organization serves as '
            'a member.'
        ),
        'mentions': [
            SimpleNamespace(
                section='discussion',
                citation_text='Code II.4.e',
                excerpt='Engineer A accepted the contract while serving on the planning board.',
            ),
            SimpleNamespace(
                section='facts',
                citation_text='Section II.4.e',
                excerpt='The RFP cited Section II.4.e of the NSPE Code without further analysis.',
            ),
        ],
    }


_LINK_PROVISIONS = [
    {
        'code_provision': 'I.1',
        'provision_text': 'Hold paramount the safety, health, and welfare of the public.',
    },
    {
        'code_provision': 'II.4.e',
        'provision_text': (
            'Engineers shall not solicit or accept a contract from a governmental '
            'body on which a principal or officer of their organization serves as '
            'a member.'
        ),
    },
]


def provision_link_inputs(variant='full'):
    if variant == 'full':
        return {
            'provisions': _LINK_PROVISIONS,
            'entity_type': 'role',
            'type_label': 'Roles',
            'entities': [
                {
                    'label': 'Engineer A',
                    'definition': 'A professional engineer serving on the municipal planning board.',
                },
                {
                    'label': 'City Engineer',
                    # Over 150 chars to exercise the builder-side truncation.
                    'definition': (
                        'The public official responsible for reviewing and approving '
                        'engineering submittals on behalf of the municipality, including '
                        'plans prepared by outside consultants under contract to the city.'
                    ),
                },
            ],
            'case_summary': 'Case 9: Engineer serving on a public board whose firm seeks municipal work.',
        }
    # Reduced variant: a different entity type (different applicability
    # sentence) and an empty case summary (default-context branch).
    return {
        'provisions': _LINK_PROVISIONS,
        'entity_type': 'obligation',
        'type_label': 'Obligations',
        'entities': [
            {
                'label': 'Duty to disclose conflict of interest',
                'definition': 'Obligation to disclose any financial interest to affected parties.',
            },
        ],
        'case_summary': '',
    }


def precedents_inputs():
    return {
        'case_text': (
            '=== FACTS ===\n'
            'Engineer A cited BER Case 94-8 in support of the delegation.\n\n'
            '=== DISCUSSION ===\n'
            'The Board discussed Cases 65-9 and 73-9 jointly, distinguishing both '
            'on their facts.'
        ),
    }


def transformation_inputs(variant='full'):
    if variant == 'full':
        return {
            'case_id': 9,
            'case_title': 'Case 24-02: AI in Engineering Practice',
            'case_facts': (
                'Engineer A used an AI system to produce design documents and sealed '
                'them without a full personal review.'
            ),
            'questions': [
                {
                    'entity_definition': 'Was it ethical for Engineer A to seal drawings produced by the AI system?',
                    'rdf_json_ld': {},
                },
                {'text': 'Did Engineer B have a duty to report the practice?', 'type': 'board'},
            ],
            'conclusions': [
                {
                    'entity_definition': 'It was not ethical to seal the drawings without full review.',
                    'rdf_json_ld': {'conclusionType': 'violation'},
                },
            ],
            'resolution_patterns': [
                {
                    'pattern_type': 'duty_reassertion',
                    'resolution_narrative': 'The Board reasserted the personal-review duty over delegation to tools.',
                },
            ],
            'all_entities': {
                'roles': [{'label': 'Engineer A'}, {'label': 'Client'}],
                'obligations': [{'label': 'Duty of competent practice'}],
                'actions': [{'label': 'Sealing the drawings'}],
                'constraints': [{'label': 'License scope'}],
            },
        }
    # Reduced variant: every optional block absent, exercising the
    # facts-unavailable fallback, the omitted entities/patterns blocks, and
    # the no-questions/no-conclusions placeholders.
    return {
        'case_id': 9,
        'case_title': 'Case 24-02: AI in Engineering Practice',
        'case_facts': '',
        'questions': [],
        'conclusions': [],
        'resolution_patterns': [],
        'all_entities': {},
    }


def obligation_relevance_inputs():
    from app.services.entity_analysis.obligation_coverage_analyzer import (
        ConstraintAnalysis,
        ObligationAnalysis,
    )

    return {
        'obligations': [
            ObligationAnalysis(
                entity_uri='urn:proethica:obligation:o1',
                entity_label='Duty to public safety',
                entity_definition=(
                    'Hold paramount the safety, health, and welfare of the public in '
                    'all professional duties.'
                ),
            ),
            ObligationAnalysis(
                entity_uri='urn:proethica:obligation:o2',
                entity_label='Duty of confidentiality',
                entity_definition=(
                    'Maintain client confidences except where public safety requires '
                    'disclosure.'
                ),
            ),
        ],
        'constraints': [
            ConstraintAnalysis(
                entity_uri='urn:proethica:constraint:c1',
                entity_label='Licensure limit',
                entity_definition='Practice only within areas of licensed competence.',
            ),
        ],
        'questions': [{'text': 'Was disclosure of the conflict required?'}],
        'conclusions': [{'text': 'Disclosure was required under II.1.a.'}],
    }
