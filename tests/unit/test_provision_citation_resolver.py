"""Tests for NSPE provision citation -> nspe: IRI resolution and edge materialization."""

from rdflib import Graph, Literal, URIRef, Namespace

from app.services.extraction.provision_citation_resolver import (
    ProvisionCitationResolver, apply_cites_provision_edges, normalize_citation,
    valid_fragments_from_codes, NSPE_NS, CORE_CITES_PROVISION,
)

PROETH = Namespace("http://proethica.org/ontology/intermediate#")


def test_normalize_dotted_codes():
    assert normalize_citation("II.4.a.") == "II_4_a"
    assert normalize_citation("I.6.") == "I_6"
    assert normalize_citation("II.1") == "II_1"
    assert normalize_citation("  III.9.d  ") == "III_9_d"
    assert normalize_citation("I") == "I"


def test_normalize_rejects_non_dotted():
    assert normalize_citation("NSPE Code of Ethics Section 2") is None
    assert normalize_citation("NSPE Code of Ethics Section 2(c)") is None
    assert normalize_citation("BER Case 63-6") is None
    assert normalize_citation("Model-Law-Section-2d-Definition") is None
    assert normalize_citation("") is None
    assert normalize_citation(None) is None


def test_valid_fragments_from_codes_includes_ancestors():
    frags = valid_fragments_from_codes(["II.1.a", "I.1", "III.9.d"])
    assert {"II", "II_1", "II_1_a", "I", "I_1", "III", "III_9", "III_9_d"} <= frags


def test_resolver_maps_only_existing_nodes():
    r = ProvisionCitationResolver(valid_fragments_from_codes(["II.1.a", "I.6"]))
    assert r.resolve("II.1.a.") == NSPE_NS + "II_1_a"
    assert r.resolve("II.1") == NSPE_NS + "II_1"      # ancestor node exists
    assert r.resolve("I.6.") == NSPE_NS + "I_6"
    assert r.resolve("IV.9.z") is None                 # not in the corpus structure
    assert r.resolve("BER Case 63-6") is None


def test_apply_edges_adds_and_is_idempotent():
    r = ProvisionCitationResolver(valid_fragments_from_codes(["II.4.a", "I.6"]))
    g = Graph()
    concl = URIRef("http://example.org/case#Conclusion_1")
    g.add((concl, PROETH.citedProvision1, Literal("II.4.a.")))
    g.add((concl, PROETH.citedProvision2, Literal("I.6.")))
    g.add((concl, PROETH.citedProvision3, Literal("BER Case 99-1")))  # skipped

    added = apply_cites_provision_edges(g, r)
    assert added == 2
    cites = URIRef(CORE_CITES_PROVISION)
    assert (concl, cites, URIRef(NSPE_NS + "II_4_a")) in g
    assert (concl, cites, URIRef(NSPE_NS + "I_6")) in g

    # Idempotent: re-applying adds nothing new
    assert apply_cites_provision_edges(g, r) == 0
