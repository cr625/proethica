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


# --- establishedBy: Constraint proeth:source -> nspe: CodeProvision -----------
# (Stage-3 dead-edge batch: the constraint's establishing provision, resolved via
# the SAME resolver as citesProvision; free-text sources need embedded-token
# extraction because proeth:source is prose, not a bare dotted code.)

from rdflib import RDF, Namespace as _Namespace

from app.services.extraction.provision_citation_resolver import (
    CORE_ESTABLISHED_BY, apply_established_by_edges, extract_provision_fragments,
)

CORE = _Namespace("http://proethica.org/ontology/core#")
CASE = _Namespace("http://proethica.org/ontology/case/99#")


def test_extract_provision_fragments_whole_and_embedded():
    # Whole-literal dotted codes (the citedProvisionN form).
    assert extract_provision_fragments("II.4.a.") == ["II_4_a"]
    assert extract_provision_fragments("II") == ["II"]
    # Embedded codes inside free-text source literals (case7_opus_run12 shapes).
    assert extract_provision_fragments("NSPE Code II.2.b") == ["II_2_b"]
    assert extract_provision_fragments("NSPE Code III.8.a; BER Case 98-3") == ["III_8_a"]
    # Non-code sources yield nothing (bare roman numerals in prose never resolve).
    assert extract_provision_fragments("NSPE Code of Ethics") == []
    assert extract_provision_fragments("State Seal Law") == []
    assert extract_provision_fragments("Local regulations") == []
    assert extract_provision_fragments("") == []


def test_resolver_resolve_all_validates_against_corpus():
    r = ProvisionCitationResolver(valid_fragments_from_codes(["II.2.b", "III.8.a"]))
    assert r.resolve_all("NSPE Code II.2.b") == [NSPE_NS + "II_2_b"]
    assert r.resolve_all("NSPE Code III.8.a; BER Case 98-3") == [NSPE_NS + "III_8_a"]
    assert r.resolve_all("NSPE Code IX.9.z") == []      # not a corpus node
    assert r.resolve_all("State Seal Law") == []


def test_apply_established_by_edges_constraint_scoped_and_idempotent():
    r = ProvisionCitationResolver(valid_fragments_from_codes(["II.2.b", "III.8.a"]))
    g = Graph()
    established = URIRef(CORE_ESTABLISHED_BY)

    # A Constraint with a resolvable code source.
    cs = CASE["Engineer_A_Seal_Authority_Boundary"]
    g.add((cs, RDF.type, CORE.Constraint))
    g.add((cs, PROETH.source, Literal("NSPE Code II.2.b")))
    # A Constraint whose source is not an NSPE code: no edge, literal untouched.
    cs2 = CASE["Seal_Law_Boundary"]
    g.add((cs2, RDF.type, CORE.Constraint))
    g.add((cs2, PROETH.source, Literal("State Seal Law")))
    # A NON-Constraint subject carrying a source literal: subject validation skips it.
    st = CASE["Some_State"]
    g.add((st, RDF.type, CORE.State))
    g.add((st, PROETH.source, Literal("NSPE Code III.8.a")))

    added = apply_established_by_edges(g, r)
    assert added == 1
    assert (cs, established, URIRef(NSPE_NS + "II_2_b")) in g
    assert not list(g.objects(cs2, established))
    assert not list(g.objects(st, established))
    # ADDITIVE: the source literals are all still present.
    assert (cs, PROETH.source, Literal("NSPE Code II.2.b")) in g
    assert (cs2, PROETH.source, Literal("State Seal Law")) in g
    # Idempotent: re-applying adds nothing new.
    assert apply_established_by_edges(g, r) == 0


def test_apply_established_by_multi_code_source():
    """A source literal citing several dotted codes yields one edge per resolvable
    provision (deduplicated)."""
    r = ProvisionCitationResolver(valid_fragments_from_codes(["II.2.b", "III.8.a"]))
    g = Graph()
    cs = CASE["Review_Boundary"]
    g.add((cs, RDF.type, CORE.Constraint))
    g.add((cs, PROETH.source, Literal("NSPE Code III.8.a and II.2.b; BER Case 98-3")))

    assert apply_established_by_edges(g, r) == 2
    established = URIRef(CORE_ESTABLISHED_BY)
    assert (cs, established, URIRef(NSPE_NS + "III_8_a")) in g
    assert (cs, established, URIRef(NSPE_NS + "II_2_b")) in g
