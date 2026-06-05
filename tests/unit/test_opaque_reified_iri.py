"""Opaque IRIs for reified temporal/causal nodes (W3C n-ary-relations convention).

A TemporalRelation (reified Allen interval relation) and a CausalChain (reified
cause/effect link) carry metadata of their own, so they are reified -- but their
IDENTITY must be opaque (case#TemporalRelation_<n> / case#CausalChain_<n>), not built
from the participant prose. The former entity_label-derived URIs concatenated the
endpoint labels (AllenRelation_<from>_<rel>_<to>, "cause -> effect" with a raw arrow),
producing 90-140 char IRIs. rdf_converter mints the opaque @id; the commit serializer
reads it via OntServeCommitService._opaque_reified_uri_local while keeping the readable
text in rdfs:label. Participants are resolved post-commit (temporal_relation_edges /
causal_edges), not encoded in the IRI.
"""
from app.services.temporal_dynamics.utils.rdf_converter import (
    convert_allen_relation_to_rdf,
    convert_causal_chain_to_rdf,
)
from app.services.ontserve_commit_service import OntServeCommitService

CANON = "http://proethica.org/ontology/case/"


def test_allen_converter_opaque_sequential_iri():
    allen = {"entity1": "Engineer A preparing the summary memo",
             "entity2": "City Administrator's request for a recommendation",
             "relation": "before", "evidence": "memo precedes request"}
    rdf = convert_allen_relation_to_rdf(allen, 14, relation_index=3)
    assert rdf["@id"] == f"{CANON}14#TemporalRelation_3"
    # readable text preserved for display; no lossy pre-computed endpoint URIs
    assert rdf["rdfs:label"].startswith("Engineer A preparing the summary memo before")
    assert "fromEntityURI" not in rdf and "toEntityURI" not in rdf
    assert not any(k.startswith("time:") for k in rdf)


def test_causal_chain_converter_opaque_sequential_iri():
    chain = {"cause": "AI Report Generation", "effect": "Report Stylistic Inconsistency",
             "causal_language": "because"}
    rdf = convert_causal_chain_to_rdf(chain, 7, chain_index=3)
    assert rdf["@id"] == f"{CANON}7#CausalChain_3"
    assert "→" not in rdf["@id"]  # no raw arrow in the IRI


def test_converters_opaque_short_without_index():
    allen = convert_allen_relation_to_rdf({"entity1": "a", "entity2": "b", "relation": "before"}, 1)
    chain = convert_causal_chain_to_rdf({"cause": "a", "effect": "b"}, 1)
    for rdf, prefix in ((allen, "TemporalRelation_"), (chain, "CausalChain_")):
        frag = rdf["@id"].split("#")[-1]
        assert frag.startswith(prefix) and len(frag) <= 25, frag


def test_commit_helper_reads_opaque_for_both_reified_types():
    h = OntServeCommitService._opaque_reified_uri_local
    assert h({"@type": "proeth:TemporalRelation", "@id": "x#TemporalRelation_5"}) == "TemporalRelation_5"
    assert h({"@type": "proeth:CausalChain", "@id": "x#CausalChain_2"}) == "CausalChain_2"


def test_commit_helper_returns_none_for_legacy_and_non_reified():
    h = OntServeCommitService._opaque_reified_uri_local
    # legacy concatenated @id -> None (caller falls back to _safe_label)
    assert h({"@type": "proeth:CausalChain", "@id": "http://proethica.org/cases/7#AI_arrow_x"}) is None
    assert h({"@type": "proeth:TemporalRelation", "@id": "x#AllenRelation_a_before_b"}) is None
    # non-reified individuals and empty input -> None
    assert h({"@type": "proeth:Action", "@id": "x#Foo"}) is None
    assert h(None) is None
    assert h({}) is None
