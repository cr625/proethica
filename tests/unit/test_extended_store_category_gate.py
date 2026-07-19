"""
The accumulate-path category gate (shadow-gate review, 2026-07-11).

When a commit re-discovers an EXISTING extended-store class, the subClassOf
reconciliation used to add parents resolved from the incoming extraction's
own category fields with no agreement check -- a re-discovery of the same
label under a different concept category would chain the class into a second
disjoint core branch, making every case that loads the extended store
Pellet-inconsistent. The gate vetoes parents whose core category disagrees
with the class's existing chain (trust the chain, not the incoming claim).
"""

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef

from app.services.commit.ontserve_commit_service import OntServeCommitService

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")


def _svc(base_map):
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc._base_ontology_index._base_cat_cache = dict(base_map)
    return svc


def test_core_category_of_iri_resolves_core_and_base():
    svc = _svc({"CompetenceSelfAssessmentCapability": "Capability"})
    assert svc._core_category_of_iri(str(CORE.Role)) == "Role"
    assert svc._core_category_of_iri(
        str(PROETH.CompetenceSelfAssessmentCapability)) == "Capability"
    assert svc._core_category_of_iri(str(PROETH.UnknownThing)) is None


def test_graph_core_category_walks_extended_chain():
    svc = _svc({})
    g = Graph()
    cls = URIRef("http://proethica.org/ontology/intermediate#SomeExtendedCapability")
    mid = URIRef("http://proethica.org/ontology/intermediate#MidLayer")
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, RDFS.subClassOf, mid))
    g.add((mid, RDFS.subClassOf, CORE.Capability))
    assert svc._graph_core_category(g, cls) == "Capability"
    # cycle-safe
    g.add((mid, RDFS.subClassOf, cls))
    assert svc._graph_core_category(g, cls) == "Capability"


def test_camelcase_normalization_import_present():
    """The class-mint branch's CamelCase label split referenced a module
    import that never existed (NameError shipped 2026-07-07, first executed
    by the shadow gate 2026-07-11: gold recommits take the accumulate path,
    so only a genuinely NEW CamelCase class label reaches it)."""
    import re
    import app.services.commit.ontserve_commit_service as ocs
    assert ocs.re is re
    disp = ocs.re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', 'DesignReviewCapability')
    assert disp == 'Design Review Capability'


def test_cross_category_parent_would_be_vetoed():
    """The gate condition itself: existing chain says Capability, incoming
    parent resolves to Principle -> disagreement detected."""
    svc = _svc({})
    g = Graph()
    cls = URIRef("http://proethica.org/ontology/intermediate#DualUseThing")
    g.add((cls, RDF.type, OWL.Class))
    g.add((cls, RDFS.subClassOf, CORE.Capability))
    existing = svc._graph_core_category(g, cls)
    incoming = svc._core_category_of_iri(str(CORE.Principle))
    assert existing == "Capability" and incoming == "Principle"
    assert existing != incoming  # the veto branch fires

    # agreement passes
    assert svc._core_category_of_iri(str(CORE.Capability)) == existing
