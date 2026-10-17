"""Case 8 (NSPE 24-1) review, lesson L7: the phase-4 narrative orders the
timeline by the committed temporalSequence with agents from performedBy,
derives 'enables' links only from the Step-3 causal chains, and authors a
board_rationale only for a decision point a Board conclusion resolves.

Hermetic: no DB, no LLM. The committed order is injected on the extractor.
"""
from types import SimpleNamespace
from unittest.mock import patch

from app.services.narrative.narrative_element_extractor import NarrativeElementExtractor
from app.services.narrative.timeline_constructor import TimelineConstructor, load_step3_causal_chains
from app.services.narrative.scenario_seed_generator import ScenarioBranch, ScenarioOption, ScenarioSeeds
from app.services.step4_synthesis.case_synthesis_models import EntityFoundation, EntitySummary


def _foundation():
    f = EntityFoundation(case_id=None)
    # Storage order: the suspension request is stored FIRST, the contract
    # acceptance (which precedes it in the case) is stored last.
    f.actions = [
        EntitySummary(uri="case-8#Work_Suspension_Request", label="Work Suspension Request",
                      entity_type="actions", temporal_sequence=3, agent_label="Engineer L"),
        EntitySummary(uri="case-8#Risk_Notification", label="Risk Notification",
                      entity_type="actions", temporal_sequence=2, agent_label="Engineer L"),
    ]
    f.events = [
        EntitySummary(uri="case-8#Contract_Acceptance", label="Contract Acceptance",
                      entity_type="events", temporal_sequence=1),
        EntitySummary(uri="case-8#Later_Collapse", label="Later Collapse", entity_type="events"),
    ]
    return f


def test_events_follow_the_stored_temporal_sequence_not_storage_order():
    ex = NarrativeElementExtractor(use_llm=False)
    events = ex._extract_events(_foundation())
    assert [e.label for e in events] == ["Contract Acceptance", "Risk Notification",
                                         "Work Suspension Request", "Later Collapse"]
    assert [e.time_point for e in events] == [1, 2, 3, 4]
    assert events[2].agent_label == "Engineer L" and events[0].agent_label is None


def test_committed_sequence_and_performed_by_override_the_rows():
    ex = NarrativeElementExtractor(use_llm=False)
    committed = {
        "Work_Suspension_Request": {"sequence": 1, "agent_uri": "case-8#Agent_Engineer_L", "agent_label": "Engineer L"},
        "Contract_Acceptance": {"sequence": 2},
        "Risk_Notification": {"sequence": 3, "agent_uri": "case-8#Agent_Engineer_L", "agent_label": "Engineer L"},
    }
    with patch.object(ex, "_committed_temporal_order", return_value=committed):
        events = ex._extract_events(_foundation())
    assert [e.label for e in events] == ["Work Suspension Request", "Contract Acceptance",
                                         "Risk Notification", "Later Collapse"]
    assert events[0].agent_uri == "case-8#Agent_Engineer_L"


def test_committed_temporal_order_reads_sequence_and_performed_by(monkeypatch):
    from rdflib import Graph, Literal, Namespace, RDFS, XSD
    case = Namespace("http://proethica.org/ontology/case/8#")
    proeth = Namespace("http://proethica.org/ontology/intermediate#")
    g = Graph()
    g.add((case["Work_Suspension_Request"], proeth["temporalSequence"], Literal(3, datatype=XSD.nonNegativeInteger)))
    g.add((case["Work_Suspension_Request"], proeth["performedBy"], case["Agent_Engineer_L"]))
    g.add((case["Agent_Engineer_L"], RDFS.label, Literal("Engineer L")))
    import app.services.entity.committed_case_graph as ccg
    monkeypatch.setattr(ccg, "load_case_graph", lambda case_id: g)
    ex = NarrativeElementExtractor(use_llm=False)
    order = ex._committed_temporal_order(8)
    assert order == {"Work_Suspension_Request": {"sequence": 3, "agent_uri": str(case["Agent_Engineer_L"]),
                                                 "agent_label": "Engineer L"}}


def _narrative_elements(events):
    return SimpleNamespace(setting=None, events=events, conflicts=[], decision_moments=[], resolution=None,
                           summary=lambda: {})


def test_enables_links_come_only_from_step3_causal_chains():
    ex = NarrativeElementExtractor(use_llm=False)
    ne = _narrative_elements(ex._extract_events(_foundation()))
    tc = TimelineConstructor(use_llm=False)
    events = tc._build_timeline_events(ne)
    chains = [{"cause": "Risk Notification", "effect": "Work Suspension Request", "confidence": 0.9},
              {"cause": "Unknown Thing", "effect": "Later Collapse"}]
    links = tc._build_causal_links(events, ne, [], chains)
    enables = [(l.source_label, l.target_label) for l in links if l.link_type == "enables"]
    assert enables == [("Risk Notification", "Work Suspension Request")]
    assert links[0].confidence == 0.9


def test_without_chains_no_enables_links_are_invented():
    ex = NarrativeElementExtractor(use_llm=False)
    ne = _narrative_elements(ex._extract_events(_foundation()))
    tc = TimelineConstructor(use_llm=False)
    events = tc._build_timeline_events(ne)
    links = tc._build_causal_links(events, ne, [], None)
    assert not [l for l in links if l.link_type == "enables"]


def test_load_step3_causal_chains_reads_causal_chain_rows(monkeypatch):
    rows = [SimpleNamespace(rdf_json_ld={"@type": "proeth:CausalChain", "proeth:cause": "A", "proeth:effect": "B",
                                         "proeth:responsibleAgent": "Engineer L"}),
            SimpleNamespace(rdf_json_ld={"@type": "proeth:Action"})]
    import app.services.narrative.timeline_constructor as tc_mod
    monkeypatch.setattr(tc_mod, "_temporal_rows", lambda case_id: rows)
    chains = load_step3_causal_chains(8)
    assert chains == [{"cause": "A", "effect": "B", "agent": "Engineer L", "confidence": 0.8}]


def test_decision_moments_know_whether_a_board_conclusion_resolves_them():
    ex = NarrativeElementExtractor(use_llm=False)
    board_dp = SimpleNamespace(focus_id="DP1", decision_question="q", description="d", role_uri="r", role_label="R",
                               options=[{"label": "Suspend", "is_board_choice": True}],
                               obligation_label="Safety", constraint_label=None,
                               competing_obligation_label="Faithful Agent Duty",
                               aligned_conclusion_uri="case-8#Conclusion_1", synthesis_method="algorithmic+llm")
    analytical_dp = SimpleNamespace(focus_id="DP5", decision_question="q", description="d", role_uri="r", role_label="R",
                                    options=[{"label": "Monitor", "is_board_choice": True}],
                                    obligation_label="Safety", constraint_label="Scope",
                                    aligned_conclusion_uri="case-8#Conclusion_101", synthesis_method="analytical_extension")
    unaligned_dp = SimpleNamespace(focus_id="DP3", decision_question="q", description="d", role_uri="r", role_label="R",
                                   options=[], obligation_label="Safety", constraint_label=None,
                                   aligned_conclusion_uri=None, synthesis_method="llm_direct")
    moments = ex._extract_decision_moments([board_dp, analytical_dp, unaligned_dp])
    assert [m.has_board_conclusion for m in moments] == [True, False, False]
    assert moments[0].board_choice == "Suspend" and moments[0].board_conclusion_uri == "case-8#Conclusion_1"
    assert moments[1].board_choice is None
    assert moments[0].competing_obligations == ["Safety", "Faithful Agent Duty"]
    assert moments[1].competing_obligations == ["Safety", "Scope"]


def test_conflicts_use_the_competing_obligation_pair():
    ex = NarrativeElementExtractor(use_llm=False)
    dp = SimpleNamespace(obligation_label="Public Safety Duty", obligation_uri="case-8#Public_Safety_Duty",
                         competing_obligation_label="Faithful Agent Duty",
                         competing_obligation_uri="case-8#Faithful_Agent_Duty",
                         constraint_label=None, constraint_uri=None, role_uri="case-8#Engineer_L")
    f = EntityFoundation(case_id=None)
    conflicts = ex._extract_conflicts(f, [dp])
    assert conflicts[0].conflict_type == "obligation_vs_obligation"
    assert conflicts[0].entity2_type == "obligation" and conflicts[0].entity2_label == "Faithful Agent Duty"


def _seeds(has_board_conclusion):
    return ScenarioSeeds(
        case_id=8, opening_context="ctx", initial_state_description="init",
        protagonist_uri="case-8#Engineer_L", protagonist_label="Engineer L",
        branches=[ScenarioBranch(
            branch_id="branch_0", context="c", question="q", decision_point_uri="dp",
            decision_maker_uri="case-8#Engineer_L", decision_maker_label="Engineer L",
            involved_obligation_uris=["case-8#Public_Safety_Duty"],
            options=[ScenarioOption(option_id="opt_0_0", label="Monitor", description="", action_uris=[],
                                    is_board_choice=True)],
            has_board_conclusion=has_board_conclusion)])


def _fake_provider(payload):
    """A provider double for the consequence generator: every completion returns ``payload``."""
    return SimpleNamespace(model="test-model", complete=lambda **kw: SimpleNamespace(text=payload))


def test_board_rationale_authored_only_with_a_board_conclusion():
    import app.services.scenario_generation.consequence_generator as cg
    payload = ('{"options": [{"option_id": "opt_0_0", "consequence_narrative": "n", '
               '"consequence_obligations": [], "consequence_fluent_changes": {}}], '
               '"board_rationale": "The Board chose monitoring."}')
    prompts = []

    def _build(branch, causal_links, resolution, request_board_rationale=True):
        prompts.append(request_board_rationale)
        return "prompt"

    with patch.object(cg, "get_tier_provider", lambda *a, **kw: _fake_provider(payload)), \
         patch.object(cg, "_build_consequence_prompt", _build):
        seeds = _seeds(False)
        cg.generate_consequences_for_seeds(seeds, [], {}, {})
        assert seeds.branches[0].board_rationale == ""
        assert seeds.branches[0].options[0].consequence_narrative == "n"
        seeds = _seeds(True)
        cg.generate_consequences_for_seeds(seeds, [], {}, {})
        assert seeds.branches[0].board_rationale == "The Board chose monitoring."
    assert prompts == [False, True]


def test_consequence_prompt_omits_the_rationale_request_for_analytical_points():
    from app.services.scenario_generation.consequence_generator import _build_consequence_prompt
    branch = _seeds(False).branches[0]
    prompt = _build_consequence_prompt(branch, [], {}, request_board_rationale=False)
    assert '"board_rationale": "..."' not in prompt           # not requested in the JSON contract
    assert "Do NOT generate a board_rationale" in prompt
    assert "did not rule on this decision point" in prompt
    assert "[BOARD'S CHOICE]" not in prompt
    with_rationale = _build_consequence_prompt(branch, [], {}, request_board_rationale=True)
    assert '"board_rationale": "..."' in with_rationale and "[BOARD'S CHOICE]" in with_rationale


def test_scenario_branch_carries_the_flag_from_the_decision_moment():
    from app.services.narrative.scenario_seed_generator import ScenarioSeedGenerator
    gen = ScenarioSeedGenerator(use_llm=False)
    moment = SimpleNamespace(description="d", question="q", competing_obligations=["a", "b"],
                             options=[{"label": "Monitor", "description": "", "action_uris": [], "is_board_choice": False}],
                             uri="dp", decision_maker_uri="u", decision_maker_label="L",
                             has_board_conclusion=False)
    branches = gen._build_branches([moment], [])
    assert branches[0].has_board_conclusion is False
