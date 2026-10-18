"""Review of the step4-synthesis lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Two defects found in the merge review, each with the scenario that broke, and
one verification the branch tests left to hand-built graphs:

1. The stored decision points lost their alignment and competition fields on
   reload. Both loaders (the phase-4 route helper and
   CaseSynthesizer.load_canonical_points) rebuilt a fixed subset of
   CanonicalDecisionPoint, so a phase-4 run from stored rows saw
   aligned_conclusion_uri None and competing_obligation_label None on every
   point: no Board conclusion resolved any point (no board_choice, no
   board_rationale) and the obligation pair of lesson L4 never reached the
   tensions. CanonicalDecisionPoint.from_storage restores every stored field.

2. The grounding context read the stored Step-3 rows only when no committed
   graph existed. A graph committed before the current Step-3 run, or a
   model echo of the extraction-time @id form, dropped the action again,
   the symptom lesson L1 removes. The rows are now read beside the graph.

3. The stale-row gate of lesson L8 was tested on hand-built graphs only; the
   last test runs it against the TTL the append-path emitter writes, twice.

Hermetic: no DB, no LLM.
"""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rdflib import Graph, Literal, Namespace, RDF, RDFS

from app.services.decision_point_synthesizer import CanonicalDecisionPoint, DecisionPointSynthesizer
from app.services.decision_point_synthesizer.models import ToulminStructure
from app.services.narrative.narrative_element_extractor import NarrativeElementExtractor
from app.services.step4_synthesis.case_synthesis_models import EntityFoundation

CORE = Namespace("http://proethica.org/ontology/core#")
CASE = Namespace("http://proethica.org/ontology/case/8#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")


def _point(**over):
    base = dict(
        focus_id="DP1", focus_number=1, description="Whether to suspend the work",
        decision_question="Should Engineer L suspend work?", role_uri="case-8#Engineer_L", role_label="Engineer L",
        obligation_uri="case-8#Public_Safety_Duty", obligation_label="Public Safety Duty",
        constraint_uri=None, constraint_label=None,
        additional_obligation_uris=["case-8#Engineer_L_Faithful_Agent_Duty"],
        additional_obligation_labels=["Engineer L Faithful Agent Duty"],
        competing_obligation_uri="case-8#Engineer_L_Faithful_Agent_Duty",
        competing_obligation_label="Engineer L Faithful Agent Duty",
        involved_action_uris=["case-8#Work_Suspension_Request"],
        provision_labels=["I.1"],
        toulmin=ToulminStructure(claim="Suspend", backing_provisions=["I.1"]),
        aligned_question_uri="case-8#Question_1", aligned_conclusion_uri="case-8#Conclusion_1",
        aligned_conclusion_text="It was ethical to suspend.", addresses_questions=["case-8#Question_1"],
        board_resolution="It was ethical to suspend.",
        options=[{"label": "Suspend Work", "is_board_choice": True}, {"label": "Continue", "is_board_choice": False}],
        synthesis_method="algorithmic+llm", source_candidate_ids=["DP1"],
    )
    base.update(over)
    return CanonicalDecisionPoint(**base)


def _row(dp, rid=1, label=None):
    return SimpleNamespace(id=rid, rdf_json_ld=dp.to_dict(), entity_label=label or dp.description,
                           entity_definition=dp.decision_question)


# ---------------------------------------------------------------------------
# 1. Stored decision points keep their alignment and competition fields
# ---------------------------------------------------------------------------

def test_from_storage_restores_alignment_and_competition_fields():
    dp = _point()
    back = CanonicalDecisionPoint.from_storage(dp.to_dict())
    for name in ("aligned_question_uri", "aligned_conclusion_uri", "aligned_conclusion_text",
                 "addresses_questions", "board_resolution", "synthesis_method", "competing_obligation_uri",
                 "competing_obligation_label", "additional_obligation_uris", "additional_obligation_labels",
                 "source_candidate_ids", "options", "involved_action_uris", "provision_labels", "description"):
        assert getattr(back, name) == getattr(dp, name), name
    assert back.toulmin is None          # unchanged: the stored Toulmin dict is not rehydrated
    # A stored None keeps the dataclass default, unknown keys are ignored, overrides win.
    back = CanonicalDecisionPoint.from_storage({**dp.to_dict(), "board_resolution": None, "unknown": 1},
                                               description="row label")
    assert back.board_resolution == "" and back.description == "row label"
    # A legacy payload carrying the old subset only still loads.
    legacy = CanonicalDecisionPoint.from_storage({"focus_id": "DP2", "role_uri": "r", "role_label": "R"})
    assert legacy.focus_number == 0 and legacy.synthesis_method == "algorithmic+llm" and legacy.options == []


def test_route_loader_carries_every_stored_field():
    import app.routes.scenario_pipeline.step4.helpers as helpers
    query = MagicMock()
    query.filter_by.return_value.all.return_value = [_row(_point())]
    with patch.object(helpers, "TemporaryRDFStorage", SimpleNamespace(query=query)):
        points = helpers.load_canonical_points_for_phase4(8)
    assert len(points) == 1
    assert points[0].aligned_conclusion_uri == "case-8#Conclusion_1"
    assert points[0].competing_obligation_label == "Engineer L Faithful Agent Duty"
    assert points[0].additional_obligation_uris == ["case-8#Engineer_L_Faithful_Agent_Duty"]
    assert points[0].synthesis_method == "algorithmic+llm"
    assert points[0].board_resolution == "It was ethical to suspend."


def test_service_loader_carries_every_stored_field_and_keeps_the_row_label():
    import app.services.case_synthesizer.synthesizer as syn
    query = MagicMock()
    query.filter_by.return_value.order_by.return_value.all.return_value = [_row(_point(), label="DP1 row")]
    with patch.object(syn, "TemporaryRDFStorage", SimpleNamespace(query=query, id="id")):
        points = syn.CaseSynthesizer.load_canonical_points(object.__new__(syn.CaseSynthesizer), 8)
    assert len(points) == 1
    assert points[0].description == "DP1 row"
    assert points[0].aligned_conclusion_uri == "case-8#Conclusion_1"
    assert points[0].competing_obligation_uri == "case-8#Engineer_L_Faithful_Agent_Duty"
    assert points[0].synthesis_method == "algorithmic+llm"


def test_reloaded_points_drive_the_narrative_board_flags_and_tensions():
    """The scenario that broke: phase 4 run from the stored rows. The Board-resolved
    point keeps its Board conclusion and choice, the analytical extension has none,
    and the competing obligation pair reaches the tensions."""
    board = _point()
    analytical = _point(focus_id="DP5", aligned_question_uri="case-8#Question_103", aligned_conclusion_uri=None,
                        aligned_conclusion_text=None, board_resolution="", synthesis_method="analytical_extension",
                        options=[{"label": "Monitor", "is_board_choice": False}],
                        competing_obligation_uri=None, competing_obligation_label=None,
                        additional_obligation_uris=[], additional_obligation_labels=[],
                        constraint_uri="case-8#Contract_Scope_Constraint", constraint_label="Contract Scope Constraint")
    reloaded = [CanonicalDecisionPoint.from_storage(p.to_dict()) for p in (board, analytical)]
    ex = NarrativeElementExtractor(use_llm=False)
    moments = ex._extract_decision_moments(reloaded)
    assert [m.has_board_conclusion for m in moments] == [True, False]
    assert moments[0].board_choice == "Suspend Work"
    assert moments[0].board_conclusion_uri == "case-8#Conclusion_1"
    assert moments[0].competing_obligations == ["Public Safety Duty", "Engineer L Faithful Agent Duty"]
    assert moments[1].board_choice is None
    conflicts = ex._extract_conflicts(EntityFoundation(case_id=None), reloaded)
    assert conflicts[0].conflict_type == "obligation_vs_obligation"
    assert conflicts[0].entity2_label == "Engineer L Faithful Agent Duty"
    assert conflicts[1].conflict_type == "obligation_vs_constraint"


# ---------------------------------------------------------------------------
# 2. The grounding context reads the stored Step-3 rows beside the graph
# ---------------------------------------------------------------------------

def test_grounding_context_reads_the_stored_rows_beside_a_committed_graph(monkeypatch):
    g = Graph()
    g.add((CASE["Engineer_L"], RDF.type, CORE["Role"]))
    g.add((CASE["Engineer_L"], RDFS.label, Literal("Engineer L")))
    g.add((CASE["Public_Safety_Duty"], RDF.type, CORE["Obligation"]))
    # The graph predates the Step-3 run: it knows no Action.
    import app.services.entity.committed_case_graph as ccg
    monkeypatch.setattr(ccg, "load_case_graph", lambda case_id: g)
    s = DecisionPointSynthesizer()
    row = SimpleNamespace(
        rdf_json_ld={"@type": "proeth:Action",
                     "@id": "http://proethica.org/cases/8#Action_Work_Suspension_Request"},
        entity_type="actions", entity_label="Work Suspension Request", entity_uri=None)
    s._load_temporal_rows = lambda case_id: [row]
    s._load_cited_provision_codes = lambda case_id: []
    ctx = s._dp_grounding_context(8, [], [])
    assert ctx.source == "committed_graph"
    assert ctx.category_for(str(CASE["Public_Safety_Duty"])) == "Obligation"        # the graph still decides
    assert ctx.is_timeline_individual("case-8#Work_Suspension_Request")               # the label-minted form
    assert ctx.is_timeline_individual("http://proethica.org/cases/8#Action_Work_Suspension_Request")  # the @id form
    assert not ctx.is_timeline_individual("case-8#Public_Safety_Duty")


# ---------------------------------------------------------------------------
# 3. The stale-row gate against the TTL the append-path emitter writes
# ---------------------------------------------------------------------------

def _golden_individuals():
    from tests.unit.test_commit_service_golden import _fixture_individuals, _entity
    individuals = _fixture_individuals()
    for i, (ent, rdf) in enumerate(individuals, 1):
        ent.id = i
        ent.rdf_json_ld = rdf

    def row(extraction_type, label, definition, rdf, rid):
        e = _entity(extraction_type, label, entity_definition=definition)
        e.id = rid
        e.rdf_json_ld = rdf
        return e, rdf

    individuals.append(row('precedent_case_reference', 'BER Case 92-6', 'The Board distinguished Case 92-6.',
                           {'citationType': 'distinguishing',
                            'citationContext': 'The Board distinguished Case 92-6.'}, 901))
    individuals.append(row('resolution_pattern', 'ResolutionPattern_1', 'Holds when the client was notified.',
                           {'conclusion_uri': 'case-501#Conclusion_1', 'resolution_conditions': 'x'}, 902))
    individuals.append(row('code_provision_reference', 'II.1.a', 'Engineers shall hold paramount the safety.',
                           {'codeProvision': 'II.1.a', 'appliesTo': []}, 903))
    return individuals


def test_stale_gate_accepts_what_the_emitter_wrote_and_sees_replaced_literals(tmp_path, monkeypatch):
    from tests.unit.test_commit_service_golden import _stub_service
    from app.services.commit.analysis_literals import analysis_individual_uri, stale_analysis_rows
    svc = _stub_service(tmp_path, monkeypatch)
    individuals = _golden_individuals()
    svc._commit_individuals_to_case_ontology(501, individuals)
    g = Graph()
    g.parse(str(tmp_path / 'proethica-case-501.ttl'), format='turtle')
    entities = [e for e, _ in individuals]
    assert stale_analysis_rows(g, 501, entities) == []

    # A second append with a changed board resolution replaces the literal (lesson L8)
    # and the gate still accepts every row.
    dp = next(e for e in entities if e.extraction_type == 'canonical_decision_point')
    dp.rdf_json_ld['board_resolution'] = 'A new holding text.'
    svc._commit_individuals_to_case_ontology(501, individuals)
    g = Graph()
    g.parse(str(tmp_path / 'proethica-case-501.ttl'), format='turtle')
    assert stale_analysis_rows(g, 501, entities) == []
    uri = analysis_individual_uri(501, dp, dp.rdf_json_ld)
    assert list(g.objects(uri, PROETH.boardResolution)) == [Literal('A new holding text.')]
    # A row whose literal the graph does not carry is reported.
    dp.rdf_json_ld['board_resolution'] = 'Text the graph never received.'
    stale = stale_analysis_rows(g, 501, entities)
    assert [e.id for e, _ in stale] == [dp.id]
