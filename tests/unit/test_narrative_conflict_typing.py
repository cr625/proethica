"""Principle tensions and obligation conflicts of the narrative pass (case 24-1
review, lesson L5).

The algorithmic branch typed the DP constraint slot as a constraint even when
it held an Obligation ("Engineer L Faithful Agent Duty"), emitted duplicate
tensions for decision points sharing a pair, stored a null competing
obligation, and asserted a board_choice for a model-generated conclusion.
No database and no model: the extractor runs with use_llm=False.
"""

from types import SimpleNamespace

from app.services.narrative.narrative_element_extractor import (
    NarrativeElementExtractor,
    is_board_explicit_conclusion_uri,
)
from app.services.precedent.phase4_connector import _extract_obligation_conflicts

CASE = 'http://proethica.org/ontology/case/8#'
O_SAFETY = CASE + 'Engineer_L_Watershed_Safety_Duty'
O_AGENT = CASE + 'Engineer_L_Faithful_Agent_Duty'
C_SCOPE = CASE + 'Client_Directive_Constraint'
ROLE = CASE + 'Engineer_L'


def _entity(uri, label):
    return SimpleNamespace(uri=uri, label=label, definition='', entity_type='')


def _foundation():
    return SimpleNamespace(
        case_id=None,
        roles=[_entity(ROLE, 'Engineer L')],
        states=[], resources=[], principles=[], capabilities=[], actions=[], events=[],
        obligations=[_entity(O_SAFETY, 'Engineer L Watershed Safety Duty'),
                     _entity(O_AGENT, 'Engineer L Faithful Agent Duty')],
        constraints=[_entity(C_SCOPE, 'Client Directive Constraint')],
    )


def _dp(focus_id, obligation, constraint, aligned=None, options=None):
    return SimpleNamespace(
        focus_id=focus_id, uri=CASE + focus_id, decision_question=f'{focus_id}?', description='',
        role_uri=ROLE, role_label='Engineer L',
        obligation_uri=obligation[0] if obligation else None,
        obligation_label=obligation[1] if obligation else None,
        constraint_uri=constraint[0] if constraint else None,
        constraint_label=constraint[1] if constraint else None,
        aligned_conclusion_uri=aligned,
        options=options or [{'description': 'Cease work', 'action_uri': CASE + 'Action_1', 'is_board_choice': True},
                            {'description': 'Continue', 'action_uri': CASE + 'Action_2', 'is_board_choice': False}],
    )


SAFETY = (O_SAFETY, 'Engineer L Watershed Safety Duty')
AGENT = (O_AGENT, 'Engineer L Faithful Agent Duty')
SCOPE = (C_SCOPE, 'Client Directive Constraint')


class TestConflictEndpointTyping:

    def setup_method(self):
        self.extractor = NarrativeElementExtractor(use_llm=False)

    def test_obligation_in_the_constraint_slot_is_typed_obligation(self):
        conflicts = self.extractor._extract_conflicts(_foundation(), [_dp('DP1', SAFETY, AGENT)])
        assert len(conflicts) == 1
        c = conflicts[0]
        assert (c.entity1_type, c.entity2_type) == ('obligation', 'obligation')
        assert c.conflict_type == 'obligation_vs_obligation'
        assert c.entity2_label == 'Engineer L Faithful Agent Duty'

    def test_constraint_in_the_constraint_slot_stays_a_constraint(self):
        conflicts = self.extractor._extract_conflicts(_foundation(), [_dp('DP1', SAFETY, SCOPE)])
        assert (conflicts[0].entity1_type, conflicts[0].entity2_type) == ('obligation', 'constraint')
        assert conflicts[0].conflict_type == 'obligation_vs_constraint'

    def test_unresolved_uris_keep_the_slot_types(self):
        unknown = ('http://example.org/unknown#X', 'Unknown Thing')
        conflicts = self.extractor._extract_conflicts(_foundation(), [_dp('DP1', SAFETY, unknown)])
        assert conflicts[0].entity2_type == 'constraint'

    def test_decision_points_sharing_a_pair_yield_one_tension(self):
        # Case 24-1: DP2 and DP3 shared a pair and produced exact duplicates.
        points = [_dp('DP1', SAFETY, SCOPE), _dp('DP2', SAFETY, AGENT), _dp('DP3', SAFETY, AGENT),
                  _dp('DP4', AGENT, SAFETY)]  # reversed order is the same unordered pair
        conflicts = self.extractor._extract_conflicts(_foundation(), points)
        pairs = [tuple(sorted((c.entity1_uri, c.entity2_uri))) for c in conflicts]
        assert len(conflicts) == 2
        assert len(set(pairs)) == 2
        assert [c.conflict_id for c in conflicts] == ['conflict_1', 'conflict_2']

    def test_heuristic_branch_does_not_repeat_a_decision_point_pair(self):
        foundation = _foundation()
        foundation.obligations = [_entity(O_SAFETY, 'Protect the public'),
                                  _entity(O_AGENT, 'Inform the client')]
        # 'protect' / 'inform' is a heuristic conflict pair; the DP already covers it.
        conflicts = self.extractor._extract_conflicts(
            foundation, [_dp('DP1', (O_SAFETY, 'Protect the public'), (O_AGENT, 'Inform the client'))])
        assert len(conflicts) == 1


class TestDecisionMoments:

    def setup_method(self):
        self.extractor = NarrativeElementExtractor(use_llm=False)

    def test_competing_obligations_drop_empty_slots(self):
        moments = self.extractor._extract_decision_moments([_dp('DP4', SAFETY, None)])
        assert moments[0].competing_obligations == ['Engineer L Watershed Safety Duty']

    def test_board_choice_only_for_a_board_explicit_conclusion(self):
        board = _dp('DP1', SAFETY, SCOPE, aligned=CASE + 'Conclusion_2')
        analytical = _dp('DP5', SAFETY, SCOPE, aligned=CASE + 'Conclusion_102')
        unaligned = _dp('DP6', SAFETY, SCOPE, aligned=None)
        moments = self.extractor._extract_decision_moments([board, analytical, unaligned])
        assert moments[0].board_choice == 'Cease work'
        assert moments[1].board_choice is None
        assert moments[2].board_choice is None
        # The option flag itself is kept for every decision point.
        assert moments[1].options[0]['is_board_choice'] is True


class TestBoardExplicitConclusionUri:

    def test_board_numbers_below_100(self):
        assert is_board_explicit_conclusion_uri('case-8#Conclusion_1')
        assert is_board_explicit_conclusion_uri(CASE + 'Conclusion_99')

    def test_analytical_offsets_positional_keys_and_none_are_not_board(self):
        assert not is_board_explicit_conclusion_uri(CASE + 'Conclusion_101')
        assert not is_board_explicit_conclusion_uri('case-8#C2')
        assert not is_board_explicit_conclusion_uri(None)
        assert not is_board_explicit_conclusion_uri('')


class TestConnectorObligationConflicts:

    def test_null_competing_obligations_are_dropped(self):
        moment = SimpleNamespace(
            decision_id='DP4', uri=CASE + 'DP4', question='Q?', decision_maker_label='Engineer L',
            decision_maker_uri=ROLE, competing_obligations=['Engineer L Watershed Safety Duty', None, ''],
            board_choice=None, options=[{'label': 'a'}])
        conflicts = _extract_obligation_conflicts([moment, {
            'decision_id': 'DP7', 'uri': '', 'question': '', 'decision_maker_label': '',
            'decision_maker_uri': '', 'competing_obligations': [None, 'Duty B'], 'board_choice': None,
            'options': []}])
        assert conflicts[0]['competing_obligations'] == ['Engineer L Watershed Safety Duty']
        assert conflicts[1]['competing_obligations'] == ['Duty B']
