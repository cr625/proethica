"""Fixture inputs shared by the batch-narrative golden capture and parity tests.

The golden files in tests/fixtures/step4_prompt_golden/ were captured from the
pre-migration inline prompt builders with EXACTLY these inputs (scratch capture
script, 2026-07-10, step4-template-migration batch-narrative); the parity tests
re-run the migrated builders on the same inputs and assert byte-equality.
Editing an input here invalidates its golden files.

Covers P19 step4_narrative_characters, P20 step4_narrative_tensions (full and
empty-tensions variants), P21 step4_narrative_timeline, P22
step4_narrative_option_label, P23 step4_narrative_option_set, P24
step4_narrative_opening, P25 step4_narrative_insights, P26 step4_case_summary,
and P27 step4_timeline_phases (P26/P27 goldens carry the documented
STYLE_FORMATTING_LINE addition).
"""

from types import SimpleNamespace

CASE_ID = 9

BASE = 'http://proethica.org/cases/case-9'

FACTS = (
    'Engineer A, a licensed professional engineer, performed a structural '
    'inspection of a parking garage owned by Client W. The inspection found '
    'deteriorated support columns that Engineer A judged to present a risk to '
    'public safety. Client W directed Engineer A to keep the findings '
    'confidential while repair negotiations proceeded.'
)

QUESTION = (
    'Should Engineer A disclose the structural deficiencies to the local '
    'building authority despite the confidentiality directive from Client W?'
)

COMPETING_OBLIGATIONS = [
    'Hold paramount the safety of the public',
    'Maintain client confidentiality',
]

TRANSFORMATION_TYPE = 'transfer'


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def foundation():
    return _ns(
        roles=[
            _ns(uri=f'{BASE}#EngineerA_Role_1', label='Engineer A'),
            _ns(uri=f'{BASE}#ClientW_Role_1', label='Client W'),
        ],
        obligations=[
            _ns(uri=f'{BASE}#Obligation_public_safety',
                label='Hold paramount the safety of the public'),
            _ns(uri=f'{BASE}#Obligation_client_confidentiality',
                label='Maintain client confidentiality'),
        ],
        constraints=[
            _ns(uri=f'{BASE}#Constraint_contract_terms',
                label='Contractual confidentiality clause'),
        ],
        states=[
            _ns(uri=f'{BASE}#State_deficiency_identified',
                label='Structural deficiency identified'),
        ],
        actions=[
            _ns(uri=f'{BASE}#Action_structural_inspection',
                label='Conduct structural inspection'),
        ],
        events=[
            _ns(uri=f'{BASE}#Event_confidentiality_directive',
                label='Client issues confidentiality directive'),
        ],
    )


def characters():
    from app.services.narrative.narrative_element_extractor import NarrativeCharacter
    return [
        NarrativeCharacter(
            uri=f'{BASE}#EngineerA_Role_1', label='Engineer A',
            professional_position='Licensed structural engineer'),
        NarrativeCharacter(
            uri=f'{BASE}#ClientW_Role_1', label='Client W',
            professional_position=''),
    ]


def tensions():
    from app.services.narrative.narrative_element_extractor import NarrativeConflict
    return [
        NarrativeConflict(
            conflict_id='tension_1',
            description='Public safety duty conflicts with the confidentiality directive',
            conflict_type='obligation_vs_obligation',
            entity1_uri=f'{BASE}#Obligation_public_safety',
            entity1_label='Hold paramount the safety of the public',
            entity1_type='obligation',
            entity2_uri=f'{BASE}#Obligation_client_confidentiality',
            entity2_label='Maintain client confidentiality',
            entity2_type='obligation'),
        NarrativeConflict(
            conflict_id='tension_2',
            description='',
            conflict_type='obligation_vs_constraint',
            entity1_uri=f'{BASE}#Obligation_public_safety',
            entity1_label='Hold paramount the safety of the public',
            entity1_type='obligation',
            entity2_uri=f'{BASE}#Constraint_contract_terms',
            entity2_label='Contractual confidentiality clause',
            entity2_type='constraint'),
    ]


def timeline_events():
    from app.services.narrative.timeline_constructor import TimelineEvent, TimelinePhase
    return [
        TimelineEvent(
            sequence=1, phase=TimelinePhase.INITIAL, phase_label='Initial Situation',
            event_uri=f'{BASE}#Action_structural_inspection',
            event_label='Structural inspection',
            description=('Engineer A inspects the parking garage for Client W and '
                         'documents deteriorated support columns in the north '
                         'stairwell that may endanger the public'),
            event_type='action'),
        TimelineEvent(
            sequence=2, phase=TimelinePhase.CONFLICT, phase_label='Conflict Emerges',
            event_uri=f'{BASE}#Event_confidentiality_directive',
            event_label='Confidentiality directive',
            description='Client W directs Engineer A to keep the findings confidential',
            event_type='event'),
    ]


def branches():
    return [
        _ns(decision_maker_label='Engineer A', question=QUESTION),
        _ns(decision_maker_label='Engineer A',
            question=('Should Engineer A continue the engagement while repairs '
                      'are negotiated?')),
    ]


def narrative_elements_for_opening():
    return _ns(
        setting=_ns(description=('Commercial parking garage assessment for a '
                                 'private client')),
        characters=[],
    )


def narrative_elements_for_insights():
    return _ns(
        conflicts=[
            _ns(description=('Public safety duty conflicts with the '
                             'confidentiality directive')),
            _ns(description=('Duty of loyalty to the client conflicts with the '
                             'duty to report hazards')),
        ],
        resolution=_ns(summary=('The Board concluded that Engineer A must notify '
                                'the responsible authorities because public safety '
                                'takes precedence over client confidentiality')),
    )


def principles():
    return [
        _ns(principle_label='Public Safety Paramountcy',
            how_applied=('Overrode the confidentiality directive once a danger to '
                         'the public was identified')),
        _ns(principle_label='Truthfulness in Professional Reporting',
            how_applied='Required accurate reporting of the inspection findings'),
    ]


def case_document():
    return _ns(
        title='Case 24-2: Structural Deficiencies and Client Confidentiality',
        doc_metadata={'sections_dual': {'facts': {'text': FACTS}}},
    )


def canonical_points():
    return [
        _ns(focus_id='DP1',
            description='Disclosure decision for the identified structural deficiencies',
            role_uri=f'{BASE}#EngineerA_Role_1',
            involved_action_uris=[],
            role_label='Engineer A',
            obligation_label='Hold paramount the safety of the public',
            constraint_label='Contractual confidentiality clause',
            decision_question=QUESTION),
    ]


def conclusions():
    return [
        {'uri': f'{BASE}#Conclusion_1', 'label': 'Disclosure required',
         'text': ('Engineer A has an obligation to report the deteriorated support '
                  'columns to the appropriate building authority.')},
        {'uri': f'{BASE}#Conclusion_2', 'label': 'Confidentiality yields',
         'text': ('The duty of client confidentiality yields when the public '
                  'safety obligation is engaged.')},
    ]


class FakeMessages:
    """Stub for anthropic client.messages: records prompts, replays responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.prompts = []

    def create(self, **kwargs):
        self.prompts.append(kwargs['messages'][0]['content'])
        return SimpleNamespace(
            content=[SimpleNamespace(type='text', text=self._responses.pop(0))]
        )


class FakeAnthropicClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


def make_fake_streaming(response_text, captured):
    """streaming_completion stand-in that records the prompt into `captured`."""

    def fake_streaming_completion(client, model, max_tokens, prompt, temperature=0.1):
        captured['prompt'] = prompt
        return response_text

    return fake_streaming_completion
