"""Deterministic S-checks of the semantic QC audit (per-batch rebuild gate)."""
from rdflib import Graph, Literal, Namespace, RDF, RDFS

from app.services.qc import semantic_audit as sa

CORE = Namespace("http://proethica.org/ontology/core#")
CASES = Namespace("http://proethica.org/ontology/cases#")
NS = Namespace("http://proethica.org/ontology/case/999#")


def _graph_with_precedent(num):
    g = Graph()
    p = NS[f"BER_Case_{num.replace('-', '_')}"]
    g.add((p, RDF.type, CASES.PrecedentCaseReference))
    g.add((p, RDFS.label, Literal(f"BER Case {num}")))
    return g


def test_s1_flags_hallucinated_and_lost_designators(monkeypatch):
    class _Doc:
        doc_metadata = {"case_number": "79-2"}

    class _Sess:
        @staticmethod
        def get(model, cid):
            return _Doc()
    import app
    monkeypatch.setattr(app, "db", type("D", (), {"session": _Sess}))
    sections = {"discussion": "The board cited BER Case 62-7 and Case 63-5. This is 79-2."}
    g = _graph_with_precedent("62-7")
    r = sa.s1_precedent_designators(999, g, sections)
    assert r["status"] == "warning"          # 63-5 cited in text, absent from graph
    assert r["detail"]["in_text_only"] == ["63-5"]
    assert "79-2" not in r["detail"]["in_text_only"]  # own number never counts

    g2 = _graph_with_precedent("55-11")       # never appears in the text
    r2 = sa.s1_precedent_designators(999, g2, sections)
    assert r2["status"] == "critical"
    assert r2["detail"]["in_graph_only_HALLUCINATION"] == ["55-11"]


def test_s2_flags_ungrounded_agent_skips_board():
    g = Graph()
    ghost = NS.Agent_Ghost_Contractor
    g.add((ghost, RDF.type, CORE.Agent))
    g.add((ghost, RDFS.label, Literal("Ghost Contractor")))
    board = NS.Agent_Board
    g.add((board, RDF.type, CORE.Agent))
    g.add((board, RDF.type, CASES.DeliberativeBody))
    g.add((board, RDFS.label, Literal("NSPE Board of Ethical Review")))
    real = NS.Agent_City
    g.add((real, RDF.type, CORE.Agent))
    g.add((real, RDFS.label, Literal("City")))
    sections = {"facts": "The city retained an engineer."}
    r = sa.s2_agent_grounding(999, g, sections)
    assert r["detail"]["ungrounded_agents"] == ["Ghost Contractor"]
