"""Defeasibility layer re-derivation (case-8 review, L2).

add_edges_to_graph skipped a (subject, predicate, object) already in the graph
and kept the derivation node of the first run, so case 8, re-derived three
times, still carried the 2026-07-08 node content (source fields, confidences,
quotes, wasDerivedFrom) under the active 2026-07-10 extraction_prompts row, and
the commit provenance counted four edges materialized when zero triples were
written. The applier now rewrites a derivation node from the current edge,
records the extraction_prompts row as prov:wasGeneratedBy, replaces the prior
layer before re-applying (or refuses to write a layer with stale derivations),
and reports triples_added apart from edges_emitted.

DB-free: graphs are built in the tests, ExtractionPrompt.save_prompt is stubbed.
"""
import types
from unittest.mock import MagicMock

from rdflib import Graph, Literal, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import PROV

from app.services.extraction.defeasibility_pipeline import (
    PROETH, PROETH_CORE,
    add_edges_to_graph, apply_defeasibility_edges, derivation_iri, extraction_record_iri,
    layer_derivations, remove_defeasibility_layer, stale_derivations,
    verify_graph_reflects_active_record,
)
from app.services.extraction.schemas import DefeasibilityEdge

CASE = "http://proethica.org/ontology/case/8#"
SAFETY = CASE + "Engineer_L_Watershed_Safety_Duty"
FAITHFUL = CASE + "Engineer_L_Faithful_Agent_Duty"


def _edge(pred, s, o, field="casecontext", text="quote", conf=0.85, source=None):
    return DefeasibilityEdge(predicate=pred, subject_iri=s, object_iri=o, source_field=field,
                             source_text=text, confidence=conf, source_individual_iri=source)


def _case_graph():
    g = Graph()
    for iri, label in ((SAFETY, "Engineer L Watershed Safety Duty"),
                       (FAITHFUL, "Engineer L Faithful Agent Duty")):
        g.add((URIRef(iri), RDF.type, PROETH_CORE.Obligation))
        g.add((URIRef(iri), RDFS.label, Literal(label)))
        g.add((URIRef(iri), PROETH.obligationStatement, Literal(f"{label} statement")))
    return g


def test_existing_triple_refreshes_its_derivation_node():
    g = Graph()
    first = _edge("prevailsOver", SAFETY, FAITHFUL, "casecontext", "July quote", 0.85,
                  source=CASE + "Principle_P")
    stats = {}
    assert add_edges_to_graph(g, [first], 8, record_iri=extraction_record_iri(8264), stats=stats) == 1
    assert stats == {"triples_added": 1, "derivations_created": 1, "derivations_refreshed": 0}
    node = derivation_iri(8, first)
    assert (node, PROV.wasGeneratedBy, extraction_record_iri(8264)) in g
    assert (node, PROV.wasDerivedFrom, URIRef(CASE + "Principle_P")) in g

    second = _edge("prevailsOver", SAFETY, FAITHFUL, "obligationstatement", "newer quote", 0.9)
    stats = {}
    added = add_edges_to_graph(g, [second], 8, record_iri=extraction_record_iri(8570), stats=stats)
    assert added == 0
    assert stats == {"triples_added": 0, "derivations_created": 0, "derivations_refreshed": 1}
    # The node describes the CURRENT edge: quote, source field, confidence, record, endpoints.
    assert g.value(node, PROV.value) == Literal("newer quote")
    assert str(g.value(node, RDFS.comment)) == "source_field=obligationstatement; confidence=0.9"
    assert str(g.value(node, RDFS.label)) == "Defeasibility edge from obligationstatement"
    assert set(g.objects(node, PROV.wasGeneratedBy)) == {extraction_record_iri(8570)}
    assert set(g.objects(node, PROV.wasDerivedFrom)) == {URIRef(SAFETY), URIRef(FAITHFUL)}
    assert len(list(g.objects(node, PROV.generatedAtTime))) == 1
    assert (node, PROETH.resolutionKind, Literal("override")) in g
    # The object-property triple is asserted once.
    assert len(list(g.triples((URIRef(SAFETY), PROETH_CORE.prevailsOver, None)))) == 1
    assert stale_derivations(g, 8, extraction_record_iri(8570)) == []
    assert stale_derivations(g, 8, extraction_record_iri(8264)) == [node]
    assert stale_derivations(g, 8, None) == []


def test_remove_defeasibility_layer_clears_trio_and_nodes_only():
    g = _case_graph()
    pair = [_edge("competesWith", SAFETY, FAITHFUL), _edge("competesWith", FAITHFUL, SAFETY)]
    add_edges_to_graph(g, pair, 8, record_iri=extraction_record_iri(8264))
    unrelated = URIRef(CASE + "rpo_edge_provenance_x")
    g.add((unrelated, RDF.type, PROV.Derivation))
    before = len(g)
    removed = remove_defeasibility_layer(g, 8)
    assert removed == {"triples_removed": 2, "derivations_removed": 2}
    assert layer_derivations(g, 8) == []
    assert (unrelated, RDF.type, PROV.Derivation) in g
    assert (URIRef(SAFETY), RDFS.label, None) in g
    assert len(g) < before


class _StubExtractor:
    def __init__(self, edges):
        self._edges = edges
        self.last_raw_response = '{"edges": [...]}'
        self.last_prompt = "STUB PROMPT"

    def extract(self, **_kw):
        return self._edges

    def _resolve_model(self):
        return "claude-stub-model"


def _stub_record(monkeypatch, record_id):
    calls = []

    def _save(_cls, **kw):
        calls.append(kw)
        return types.SimpleNamespace(id=record_id)

    monkeypatch.setattr("app.models.extraction_prompt.ExtractionPrompt.save_prompt",
                        classmethod(_save))
    return calls


def _prior_layer_ttl(tmp_path):
    """A case TTL carrying a competesWith pair from an earlier record (8264)."""
    g = _case_graph()
    add_edges_to_graph(g, [_edge("competesWith", SAFETY, FAITHFUL, text="old"),
                           _edge("competesWith", FAITHFUL, SAFETY, text="old")],
                       8, record_iri=extraction_record_iri(8264))
    ttl = tmp_path / "proethica-case-8.ttl"
    g.serialize(destination=str(ttl), format="turtle")
    return ttl


def test_apply_replaces_prior_layer_and_stamps_the_new_record(tmp_path, monkeypatch):
    ttl = _prior_layer_ttl(tmp_path)
    _stub_record(monkeypatch, 8570)
    new_edge = _edge("prevailsOver", SAFETY, FAITHFUL, "obligationstatement", "new quote", 0.9)

    res = apply_defeasibility_edges(8, ttl, extractor=_StubExtractor([new_edge]), write_back=True)

    assert res["status"] == "ok"
    assert res["edges_emitted"] == 1 and res["triples_added"] == 1
    assert res["derivations_created"] == 1 and res["derivations_refreshed"] == 0
    assert res["prior_layer_removed"] == {"triples_removed": 2, "derivations_removed": 2}
    assert res["extraction_record_id"] == 8570 and res["reflects_active_record"] is True
    assert res["pre_counts"]["competesWith"] == 2
    assert res["post_counts"] == {"competesWith": 0, "prevailsOver": 1, "defeasibleUnder": 0}

    g = Graph()
    g.parse(str(ttl), format="turtle")
    nodes = layer_derivations(g, 8)
    assert nodes == [derivation_iri(8, new_edge)]
    assert (nodes[0], PROV.wasGeneratedBy, extraction_record_iri(8570)) in g
    assert (URIRef(SAFETY), PROETH_CORE.competesWith, URIRef(FAITHFUL)) not in g
    check = verify_graph_reflects_active_record(g, 8, active_record_id=8570)
    assert check["reflects_active_record"] is True and check["stale_derivations"] == []
    stale = verify_graph_reflects_active_record(g, 8, active_record_id=8264)
    assert stale["reflects_active_record"] is False and len(stale["stale_derivations"]) == 1
    assert verify_graph_reflects_active_record(g, 8, active_record_id=None)["checked"] is False


def test_refresh_only_mode_refuses_a_layer_with_stale_derivations(tmp_path, monkeypatch):
    ttl = _prior_layer_ttl(tmp_path)
    before = ttl.read_text(encoding="utf-8")
    _stub_record(monkeypatch, 8570)
    new_edge = _edge("prevailsOver", SAFETY, FAITHFUL, "obligationstatement", "new quote", 0.9)

    res = apply_defeasibility_edges(8, ttl, extractor=_StubExtractor([new_edge]),
                                    write_back=True, replace_prior=False)

    assert res["status"] == "stale_derivations"
    assert res["edges_emitted"] == 1 and res["triples_added"] == 1
    assert len(res["stale_derivations"]) == 2
    # Nothing was persisted: the active record 8570 does not describe the stale pair.
    assert ttl.read_text(encoding="utf-8") == before


def test_refresh_only_mode_accepts_a_fully_rederived_layer(tmp_path, monkeypatch):
    ttl = _prior_layer_ttl(tmp_path)
    _stub_record(monkeypatch, 8570)
    rederived = [_edge("competesWith", SAFETY, FAITHFUL, text="new"),
                 _edge("competesWith", FAITHFUL, SAFETY, text="new")]

    res = apply_defeasibility_edges(8, ttl, extractor=_StubExtractor(rederived),
                                    write_back=True, replace_prior=False)

    assert res["status"] == "ok"
    assert res["triples_added"] == 0 and res["derivations_refreshed"] == 2
    g = Graph()
    g.parse(str(ttl), format="turtle")
    for node in layer_derivations(g, 8):
        assert set(g.objects(node, PROV.wasGeneratedBy)) == {extraction_record_iri(8570)}
        assert g.value(node, PROV.value) == Literal("new")


def test_zero_edge_run_reports_the_unreflected_prior_layer(tmp_path, monkeypatch):
    ttl = _prior_layer_ttl(tmp_path)
    _stub_record(monkeypatch, 8570)
    res = apply_defeasibility_edges(8, ttl, extractor=_StubExtractor([]), write_back=True)
    assert res["status"] == "no_edges"
    assert res["prior_layer_derivations"] == 2
    assert res["reflects_active_record"] is False
    assert res["extraction_record_id"] == 8570


def test_edge_provenance_counts_materialized_triples_not_emitted_edges(monkeypatch):
    """_record_edge_provenance._count read edges_emitted before triples_added and
    recorded four edges materialized when zero triples were written."""
    from app.services.commit.ontserve_commit_service import OntServeCommitService
    import app.services.provenance_service as prov_mod

    recorder = MagicMock()
    monkeypatch.setattr(prov_mod, "get_provenance_service", lambda: recorder)
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc._record_edge_provenance(8, {
        "defeasibility": {"status": "ok", "edges_emitted": 4, "triples_added": 0},
        "rpo": {"status": "ok", "edges_emitted": 3, "triples_added": 3, "triples_dropped": 0},
        "cites_provision": {"edges_added": 2},
        "participant_edges": {"status": "ok", "total": 5},
        "unified_guard": {"triples_dropped": 0},
    })
    materialization = [c for c in recorder.track_pass.call_args_list
                       if c.kwargs.get("activity_name") == "edge_materialization"][0]
    result = materialization.kwargs["result"]
    assert result["total_edges"] == 10
    assert result["by_family"]["defeasibility"] == {
        "edges": 0, "unresolved": None, "edges_emitted": 4, "triples_added": 0}
    assert result["by_family"]["rpo"]["edges"] == 3
    assert result["by_family"]["cites_provision"]["edges"] == 2
    assert result["by_family"]["participant_edges"]["edges"] == 5
