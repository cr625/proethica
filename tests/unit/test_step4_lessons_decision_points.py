"""Case 8 (NSPE 24-1) review, lessons L1 to L4: the decision-point parser and
the board-choice verifier read the record, not the model's slot assignment.

L1  involved_action_uris filtered by the committed Action/Event category
    (or the stored temporal rows), never by a URI naming prefix.
L2  board_resolution only from board_explicit conclusions answering the
    Board question, untruncated, empty when none.
L3  Verifier fed board_explicit conclusions only; a point aligned with a
    generated question is an analytical_extension with no board choice; a
    backing provision the case never cites is dropped.
L4  Obligation/constraint slots type-checked at parse time; a mis-slotted
    Obligation becomes a second involvesObligation; the competing pair follows
    the committed competesWith / prevailsOver edges.

Hermetic: no DB, no LLM, no app context. The committed graph is an in-memory
rdflib graph and the grounding context is injected on the synthesizer.
"""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef

from app.services.decision_point_synthesizer import DecisionPointSynthesizer
from app.services.decision_point_synthesizer.grounding import (
    DPGroundingContext, add_candidates, add_cited_provisions, add_temporal_rows,
    context_from_graph, filter_backing_provisions,
)
from app.services.decision_point_synthesizer.strategies import (
    board_resolution_for, resolve_normative_slots,
)
from app.services.step4_synthesis.qc_refs import is_board_explicit

CORE = Namespace("http://proethica.org/ontology/core#")
CASE = Namespace("http://proethica.org/ontology/case/8#")

SAFETY = "case-8#Public_Safety_Duty"
FAITHFUL = "case-8#Engineer_L_Faithful_Agent_Duty"
CONSTRAINT = "case-8#Contract_Scope_Constraint"
SUSPENSION = "case-8#Work_Suspension_Request"
NOTIFICATION = "case-8#Risk_Notification"


def _case8_graph(with_competition=True) -> Graph:
    g = Graph()

    def ind(frag, cat, label):
        u = CASE[frag]
        g.add((u, RDF.type, CORE[cat]))
        g.add((u, RDFS.label, Literal(label)))
        return u

    safety = ind("Public_Safety_Duty", "Obligation", "Public Safety Duty")
    faithful = ind("Engineer_L_Faithful_Agent_Duty", "Obligation", "Engineer L Faithful Agent Duty")
    ind("Contract_Scope_Constraint", "Constraint", "Contract Scope Constraint")
    ind("Work_Suspension_Request", "Action", "Work Suspension Request")
    ind("Risk_Notification", "Action", "Risk Notification")
    ind("Contract_Acceptance", "Event", "Contract Acceptance")
    ind("Engineer_L", "Role", "Engineer L")
    ind("Agent_Engineer_L", "Agent", "Engineer L")
    if with_competition:
        g.add((safety, URIRef(str(CORE) + "competesWith"), faithful))
        g.add((faithful, URIRef(str(CORE) + "competesWith"), safety))
        g.add((safety, URIRef(str(CORE) + "prevailsOver"), faithful))
    return g


def _questions():
    return [
        {"uri": "case-8#Question_1", "text": "Was it ethical for Engineer L to suspend work?",
         "number": 1, "question_number": 1},
        {"uri": "case-8#Question_2", "text": "Was Engineer L obligated to notify the client?",
         "number": 2, "question_number": 2},
        {"uri": "case-8#Question_103", "text": "Should Engineer L have kept monitoring?",
         "number": 103, "question_number": 103, "question_type": "implicit"},
    ]


def _conclusions():
    return [
        {"uri": "case-8#Conclusion_1", "text": "It was ethical for Engineer L to suspend work.",
         "conclusion_text": "It was ethical for Engineer L to suspend work.",
         "number": 1, "answersQuestions": [1], "cited_provisions": ["I.1", "II.1.a"]},
        {"uri": "case-8#Conclusion_2", "text": "Engineer L was obligated to notify the client.",
         "conclusion_text": "Engineer L was obligated to notify the client.",
         "number": 2, "answersQuestions": [2], "cited_provisions": ["II.1.b"]},
        {"uri": "case-8#Conclusion_101",
         "text": "The analysis finds a further duty of passive awareness. " * 30,
         "conclusion_text": "The analysis finds a further duty of passive awareness. " * 30,
         "number": 101, "conclusion_type": "analytical_extension", "answersQuestions": [1, 103]},
    ]


def _ctx(with_competition=True, cited=("I.1", "II.1.a", "II.1.b")):
    ctx = context_from_graph(_case8_graph(with_competition), 8)
    add_cited_provisions(ctx, cited, _conclusions())
    return ctx


def _synth(ctx):
    s = DecisionPointSynthesizer()
    s._dp_grounding_context = lambda case_id, candidates, conclusions: ctx
    return s


def _refinement(dp_overrides=None):
    base = {
        "focus_id": "DP1",
        "description": "Whether to suspend the work",
        "decision_question": "Should Engineer L suspend work or continue?",
        "role_label": "Engineer L",
        "role_uri": "case-8#Engineer_L",
        "obligation_label": "Public Safety Duty",
        "obligation_uri": SAFETY,
        "constraint_label": None,
        "constraint_uri": None,
        "provision_labels": ["I.1", "II.1.f"],
        "involved_action_uris": [SUSPENSION, NOTIFICATION, CONSTRAINT],
        "addresses_questions": ["Q0"],
        "board_resolution": "The model's one-sentence summary.",
        "options": [
            {"option_id": "O1", "label": "Suspend Work", "is_board_choice": True},
            {"option_id": "O2", "label": "Continue Work", "is_board_choice": False},
        ],
        "source_candidate_ids": ["DP1"],
    }
    base.update(dp_overrides or {})
    return json.dumps([base])


def _parse(s, resp, questions=None, conclusions=None):
    return s._parse_refinement_response(
        resp, top_candidates=[], questions=questions if questions is not None else _questions(),
        conclusions=conclusions if conclusions is not None else _conclusions(),
        question_emergence=[], resolution_patterns=[], case_id=8)


# ---------------------------------------------------------------------------
# L1: action slot by category, not by prefix
# ---------------------------------------------------------------------------

def test_l1_label_minted_action_uris_survive_and_non_actions_drop():
    dp = _parse(_synth(_ctx()), _refinement())[0]
    assert dp.involved_action_uris == [SUSPENSION, NOTIFICATION]  # the Constraint URI dropped


def test_l1_prefixed_uri_of_a_non_action_is_still_rejected():
    # The old '#Action_' prefix test would have kept this echoed State URI.
    dp = _parse(_synth(_ctx()), _refinement(
        {"involved_action_uris": ["case-8#Action_SupervisoryDirectionState", SUSPENSION]}))[0]
    assert dp.involved_action_uris == [SUSPENSION]


def test_l1_stored_temporal_rows_type_actions_when_no_committed_graph():
    ctx = DPGroundingContext(case_id=8)
    rows = [SimpleNamespace(rdf_json_ld={'@type': 'proeth:Action', '@id': 'http://proethica.org/cases/8#Action_Work_Suspension_Request'},
                            entity_type='actions', entity_label='Work Suspension Request', entity_uri=None),
            SimpleNamespace(rdf_json_ld={'@type': 'proeth:Event'}, entity_type='events',
                            entity_label='Contract Acceptance', entity_uri=None)]
    add_temporal_rows(ctx, rows, 8)
    assert ctx.source == 'stored_rows'
    assert ctx.is_timeline_individual(SUSPENSION)
    assert ctx.is_timeline_individual("http://proethica.org/ontology/case/8#Contract_Acceptance")
    assert not ctx.is_timeline_individual(CONSTRAINT)


def test_l1_candidate_option_actions_are_an_allowlist():
    ctx = DPGroundingContext(case_id=8)
    cand = SimpleNamespace(grounding=SimpleNamespace(role_uri='case-8#Engineer_L', role_label='Engineer L',
                                                     obligation_uri=SAFETY, obligation_label='Public Safety Duty',
                                                     constraint_uri=None, constraint_label=None),
                           options=[SimpleNamespace(action_uri=NOTIFICATION, action_label='Risk Notification')])
    add_candidates(ctx, [(cand, None)])
    assert ctx.is_timeline_individual(NOTIFICATION)
    assert ctx.category_for(SAFETY) == 'Obligation'


# ---------------------------------------------------------------------------
# L2: board_resolution from the Board only, untruncated, empty when none
# ---------------------------------------------------------------------------

def test_l2_board_resolution_excludes_generated_conclusions_and_is_untruncated():
    long_board = "The Board concluded that suspension was ethical. " * 40  # > 800 chars
    conclusions = _conclusions()
    conclusions[0]["text"] = conclusions[0]["conclusion_text"] = long_board
    dp = _parse(_synth(_ctx()), _refinement(), conclusions=conclusions)[0]
    assert dp.board_resolution == long_board.strip()
    assert len(dp.board_resolution) > 800
    assert "passive awareness" not in dp.board_resolution     # Conclusion_101 never joins
    assert dp.aligned_conclusion_uri == "case-8#Conclusion_1"


def test_l2_board_resolution_empty_when_no_board_conclusion_answers():
    # Q2 is addressed but only Conclusion_101 (generated) claims to answer it.
    conclusions = _conclusions()
    conclusions[1]["answersQuestions"] = []
    conclusions[2]["answersQuestions"] = [2]
    dp = _parse(_synth(_ctx()), _refinement({"addresses_questions": ["Q1"]}), conclusions=conclusions)[0]
    assert dp.board_resolution == ""          # the model's summary is never used
    assert dp.aligned_conclusion_uri is None


def test_l2_helper_joins_several_board_conclusions_and_accepts_both_key_forms():
    conclusions = [
        {"uri": "c#Conclusion_1", "text": "First holding.", "number": 1, "answers_questions": [1]},
        {"uri": "c#Conclusion_2", "text": "Second holding.", "number": 2, "answersQuestions": ["1"]},
        {"uri": "c#Conclusion_201", "text": "Generated.", "number": 201, "answersQuestions": [1]},
    ]
    aligned, text = board_resolution_for(["q#Question_1"], [{"uri": "q#Question_1", "number": 1}], conclusions)
    assert aligned["uri"] == "c#Conclusion_1"
    assert text == "First holding.\n\nSecond holding."


def test_l2_causal_link_parser_follows_the_same_rule():
    s = _synth(_ctx())
    s._build_entity_uri_lookup = lambda case_id: {}
    resp = json.dumps([{"focus_id": "DP1", "description": "d", "decision_question": "q",
                        "role_label": "Engineer L", "addresses_questions": ["Q1"],
                        "board_resolution": "model text",
                        "options": [{"label": "A", "is_board_choice": True}]}])
    qs = [{"uri": "case-8#Question_1", "question_text": "Q?", "question_number": 1}]
    cs = [{"uri": "case-8#Conclusion_1", "conclusion_text": "Board text.", "number": 1, "answersQuestions": [1]},
          {"uri": "case-8#Conclusion_101", "conclusion_text": "Generated text.", "number": 101, "answersQuestions": [1]}]
    dp = s._parse_causal_link_response(resp, 8, qs, cs)[0]
    assert dp.board_resolution == "Board text."
    assert dp.synthesis_method == "llm_fallback"


# ---------------------------------------------------------------------------
# L3: analytical extension, verifier input, cited provisions
# ---------------------------------------------------------------------------

def test_l3_point_aligned_with_generated_question_is_analytical_extension():
    dp = _parse(_synth(_ctx()), _refinement({"addresses_questions": ["Q2"]}))[0]   # Q2 = Question_103
    assert dp.synthesis_method == "analytical_extension"
    assert dp.board_resolution == ""
    assert not any(o["is_board_choice"] for o in dp.options)
    assert dp.aligned_question_uri == "case-8#Question_103"


def test_l3_foreign_backing_provisions_are_dropped():
    dp = _parse(_synth(_ctx()), _refinement())[0]
    assert dp.provision_labels == ["I.1"]                # II.1.f is not cited by case 8
    assert dp.toulmin.backing_provisions == ["I.1"]


def test_l3_backing_filter_is_disabled_without_a_cited_set():
    ctx = DPGroundingContext()
    assert filter_backing_provisions(["II.1.f", "I.1"], ctx) == ["II.1.f", "I.1"]


def test_l3_verifier_sees_board_conclusions_only_and_skips_analytical_points(monkeypatch):
    import app.services.decision_point_synthesizer.board_choice_verifier as mod
    captured = {}

    class _T:
        def render(self, **kw):
            captured.update(kw)
            return "prompt"
    monkeypatch.setattr(mod, 'get_step4_template', lambda name: _T())
    resp = MagicMock(); resp.stop_reason = "end_turn"
    block = MagicMock(); block.type = "text"
    block.text = json.dumps({"picks": [{"id": "DP1", "board_option_label": "Suspend Work", "reason": "held ethical"}]})
    resp.content = [block]
    client = MagicMock(); client.messages.create.return_value = resp

    board_dp = SimpleNamespace(focus_id="DP1", decision_question="Suspend?", synthesis_method="algorithmic+llm",
                               options=[{"label": "Suspend Work", "is_board_choice": False},
                                        {"label": "Continue Work", "is_board_choice": True}])
    analytical_dp = SimpleNamespace(focus_id="DP5", decision_question="Monitor?", synthesis_method="analytical_extension",
                                    options=[{"label": "Maintain Passive Awareness Without Unpaid Work", "is_board_choice": True},
                                             {"label": "Monitor Actively", "is_board_choice": False}])
    summary = mod.verify_board_choices(8, [board_dp, analytical_dp], _conclusions(), llm_client=client)

    assert "passive awareness" not in captured["concl_text"]      # generated conclusion not shown
    assert "suspend work" in captured["concl_text"].lower()
    assert json.loads(captured["payload_json"]) == [{"id": "DP1", "question": "Suspend?",
                                                     "options": ["Suspend Work", "Continue Work"]}]
    assert summary["analytical_skipped"] == 1 and summary["overridden"] == 1
    assert not any(o["is_board_choice"] for o in analytical_dp.options)
    assert [o["is_board_choice"] for o in board_dp.options] == [True, False]


def test_l3_verifier_skips_when_only_generated_conclusions_exist(monkeypatch):
    import app.services.decision_point_synthesizer.board_choice_verifier as mod
    monkeypatch.setattr(mod, 'get_step4_template', lambda name: (_ for _ in ()).throw(AssertionError("no call")))
    dp = SimpleNamespace(focus_id="DP1", decision_question="?", synthesis_method="llm_direct",
                         options=[{"label": "A", "is_board_choice": True}])
    summary = mod.verify_board_choices(8, [dp], [_conclusions()[2]], llm_client=MagicMock())
    assert summary["checked"] == 0
    assert dp.options[0]["is_board_choice"] is True        # unchanged, no checker call


def test_is_board_explicit_rules():
    assert is_board_explicit({"conclusion_type": "board_explicit", "number": 150}, 'C')
    assert not is_board_explicit({"conclusion_type": "analytical_extension", "number": 1}, 'C')
    assert is_board_explicit({"number": 2}, 'C')
    assert not is_board_explicit({"questionNumber": 101}, 'Q')
    assert is_board_explicit({"questionType": "unknown", "questionNumber": 1}, 'Q')
    assert not is_board_explicit({"uri": "x"}, 'Q')          # unattributed is never the Board's


# ---------------------------------------------------------------------------
# L4: slot type-check and the competing pair
# ---------------------------------------------------------------------------

def test_l4_obligation_in_constraint_slot_moves_to_the_obligation_list():
    dp = _parse(_synth(_ctx(with_competition=False)), _refinement(
        {"constraint_label": "Engineer L Faithful Agent Duty", "constraint_uri": FAITHFUL}))[0]
    assert dp.constraint_uri is None and dp.constraint_label is None
    assert dp.additional_obligation_uris == [str(CASE["Engineer_L_Faithful_Agent_Duty"])]
    assert dp.additional_obligation_labels == ["Engineer L Faithful Agent Duty"]
    assert dp.competing_obligation_label == "Engineer L Faithful Agent Duty"


def test_l4_committed_competition_edges_decide_the_competing_pair():
    # DP2 of case 8 named the safety duty against a Constraint individual while the
    # committed edges resolve it against the Faithful Agent Duty: the edges win.
    dp = _parse(_synth(_ctx()), _refinement(
        {"constraint_label": "Contract Scope Constraint", "constraint_uri": CONSTRAINT}))[0]
    assert dp.constraint_uri == str(CASE["Contract_Scope_Constraint"])   # a real Constraint stays
    assert dp.competing_obligation_uri == str(CASE["Engineer_L_Faithful_Agent_Duty"])
    assert dp.competing_obligation_label == "Engineer L Faithful Agent Duty"
    assert str(CASE["Engineer_L_Faithful_Agent_Duty"]) in dp.additional_obligation_uris


def test_l4_constraint_in_obligation_slot_moves_over():
    slots = resolve_normative_slots(_ctx(), obligation_label="Contract Scope Constraint",
                                    obligation_uri=CONSTRAINT, constraint_label=None, constraint_uri=None)
    assert slots["obligation_uri"] == ""
    assert slots["constraint_uri"] == str(CASE["Contract_Scope_Constraint"])
    assert slots["constraint_label"] == "Contract Scope Constraint"


def test_l4_analysis_edges_emit_a_second_involves_obligation(monkeypatch):
    import app.services.extraction.analysis_edges as ae
    g = _case8_graph()
    dp_uri = CASE["DP1"]
    g.add((dp_uri, RDF.type, ae.CASES.DecisionPoint))
    g.add((dp_uri, ae.PROETH.decisionPointId, Literal("DP1")))
    row = SimpleNamespace(rdf_json_ld={
        "focus_id": "DP1", "obligation_uri": SAFETY,
        "additional_obligation_uris": [FAITHFUL], "competing_obligation_uri": FAITHFUL,
        "constraint_uri": None, "role_uri": "case-8#Engineer_L",
        "involved_action_uris": [SUSPENSION],
    }, entity_label="DP1")
    monkeypatch.setattr(ae, "_rows", lambda case_id, etype: [row] if etype == "canonical_decision_point" else [])
    edges, misses = ae.build_expectations(8, g)
    preds = {(p, str(o).rsplit('#', 1)[-1]) for _, p, o, _ in edges}
    assert ("involvesObligation", "Public_Safety_Duty") in preds
    assert ("involvesObligation", "Engineer_L_Faithful_Agent_Duty") in preds
    assert ("involvesAction", "Work_Suspension_Request") in preds
    assert not [m for m in misses if "involvesConstraint" in m]


def test_existing_refinement_contract_is_preserved_for_board_points():
    dp = _parse(_synth(_ctx()), _refinement())[0]
    assert dp.synthesis_method == "algorithmic+llm"
    assert dp.role_uri == str(CASE["Engineer_L"])
    assert dp.obligation_uri == str(CASE["Public_Safety_Duty"])
    assert dp.options[0]["is_board_choice"] is True
    assert dp.aligned_question_uri == "case-8#Question_1"
