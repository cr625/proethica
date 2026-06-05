"""Unit tests for the temporal (Allen) relation endpoint resolver.

Validates that apply_temporal_relation_edges resolves the reified TemporalRelation's
free-text fromEntity/toEntity timeline phrasings to the committed Action/Event
individuals (fixing the historically-dangling time:* endpoints), leaves state-like
endpoints unwired (the declared range is union(Action, Event)), and that the unified
domain/range guard drops any fromEntity/toEntity edge mis-resolved to a State.

Embeddings + the LLM select are stubbed so the test is deterministic and needs no GPU
or API. The end-to-end embedding quality is exercised by the staged re-extraction
verification, not here.
"""
import tempfile
import os

import pytest
from rdflib import Graph, Namespace, Literal, RDF, RDFS, OWL

import app.services.extraction.temporal_relation_edges as TR
from app.services.extraction.rpo_edges import drop_domain_range_violations, ALL_EDGE_RANGE

CASE = 999
NS = Namespace(f"http://proethica.org/ontology/case/{CASE}#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
CORE = Namespace("http://proethica.org/ontology/core#")
TIME = Namespace("http://www.w3.org/2006/time#")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _ind(g, local, label, cat, core):
    u = NS[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, core))
    g.add((u, RDFS.label, Literal(label)))
    g.add((u, PROETH.conceptCategory, Literal(cat)))
    return u


def _rel(g, local, label):
    u = NS[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, PROETH.TemporalRelation))
    g.add((u, RDFS.label, Literal(label)))
    return u


def _stub_resolution(monkeypatch, rows):
    """Stub the DB read + embedding pool/shortlist + LLM select so resolution is
    deterministic word-overlap over the real Action+Event individuals in the graph."""
    monkeypatch.setattr(TR, "_temporal_relations_from_db", lambda case_id: rows)
    monkeypatch.setattr(TR, "_embedding_service", lambda: object())

    def fake_pool(graph, svc, category, extra):
        return [(s, str(next(graph.objects(s, RDFS.label))), [1.0])
                for s, _, _ in graph.triples((None, PROETH.conceptCategory, Literal(category)))]

    def fake_shortlist(svc, desc, pool, floor, k):
        dwords = set(desc.lower().split())
        scored = sorted(((iri, lbl, len(dwords & set(lbl.lower().split()))) for iri, lbl, ev in pool),
                        key=lambda x: -x[2])
        return [(iri, lbl, sim) for iri, lbl, sim in scored[:k] if sim > 0]

    def fake_llm(items, client=None, model=None, prompt_builder=None):
        # mirror the real _llm_select_multi: return the chosen IRI (best candidate)
        return {str(it["id"]): [it["shortlist"][0][0]] for it in items if it["shortlist"]}

    monkeypatch.setattr(TR, "_candidate_pool", fake_pool)
    monkeypatch.setattr(TR, "_shortlist", fake_shortlist)
    monkeypatch.setattr(TR, "_llm_select_multi", fake_llm)


def test_resolves_endpoints_and_owl_time_triple(monkeypatch):
    g = Graph()
    a1 = _ind(g, "Advisory_Memo_Preparation", "Advisory Memo Preparation", "Action", CORE.Action)
    a2 = _ind(g, "Biased_Method_Recommendation", "Biased Method Recommendation", "Event", CORE.Event)
    rel = _rel(g, "TemporalRelation_1",
               "Engineer A preparing the summary memo before Engineer A recommending the method")
    tf = tempfile.NamedTemporaryFile(suffix=".ttl", delete=False)
    g.serialize(destination=tf.name, format="turtle")
    try:
        _stub_resolution(monkeypatch, [{
            "label": "Engineer A preparing the summary memo before Engineer A recommending the method",
            "fromEntity": "Engineer A preparing the summary memo",
            "toEntity": "Engineer A recommending the method method",
            "owlprop": "time:intervalBefore", "evidence": "memo precedes recommendation",
        }])
        res = TR.apply_temporal_relation_edges(CASE, tf.name, write_back=True, use_llm=True)
        assert res["total"] == 2, res

        g2 = Graph()
        g2.parse(tf.name, format="turtle")
        assert a1 in set(g2.objects(rel, PROETH.fromEntity))
        assert a2 in set(g2.objects(rel, PROETH.toEntity))
        # the OWL-Time triple now points at a real committed individual (not a dangling frag)
        assert a2 in set(g2.objects(rel, TIME.intervalBefore))
        # PROV-O provenance is emitted for the resolved edges
        assert len(list(g2.subjects(RDF.type, PROV.Derivation))) == 2
    finally:
        os.unlink(tf.name)


def test_state_like_endpoints_left_unwired(monkeypatch):
    """fromEntity/toEntity range is union(Action, Event); a state/condition phrasing
    with no Action/Event match must resolve to nothing rather than to a State."""
    g = Graph()
    _ind(g, "Advisory_Memo_Preparation", "Advisory Memo Preparation", "Action", CORE.Action)
    _ind(g, "No_Contract_State", "No contractual relationship", "State", CORE.State)
    rel = _rel(g, "TemporalRelation_1",
               "Engineer A having no contractual relationship during the request")
    tf = tempfile.NamedTemporaryFile(suffix=".ttl", delete=False)
    g.serialize(destination=tf.name, format="turtle")
    try:
        _stub_resolution(monkeypatch, [{
            "label": "Engineer A having no contractual relationship during the request",
            "fromEntity": "zzz unrelated phrasing aaa",
            "toEntity": "qqq unrelated phrasing bbb",
            "owlprop": "time:intervalDuring", "evidence": "no contract",
        }])
        TR.apply_temporal_relation_edges(CASE, tf.name, write_back=True, use_llm=True)
        g2 = Graph()
        g2.parse(tf.name, format="turtle")
        assert not list(g2.objects(rel, PROETH.fromEntity))
        assert not list(g2.objects(rel, PROETH.toEntity))
    finally:
        os.unlink(tf.name)


def test_unified_guard_drops_state_range_violation():
    """Belt-and-suspenders: even if an endpoint were mis-resolved to a State, the
    unified guard (fromEntity/toEntity registered in ALL_EDGE_RANGE) drops it so the
    case stays OWL-DL consistent; a valid Action endpoint survives."""
    g = Graph()
    st = _ind(g, "SomeState", "Some State", "State", CORE.State)
    act = _ind(g, "SomeAction", "Some Action", "Action", CORE.Action)
    rel = _rel(g, "TemporalRelation_1", "x before y")
    g.add((rel, PROETH.fromEntity, st))   # range violation
    g.add((rel, PROETH.toEntity, act))    # valid
    dropped = drop_domain_range_violations(g, CASE, edge_range=ALL_EDGE_RANGE)
    assert dropped == 1
    assert not list(g.objects(rel, PROETH.fromEntity))
    assert act in set(g.objects(rel, PROETH.toEntity))
