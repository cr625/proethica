"""Unit tests for the participant-edge family spec (edge_spec._PARTICIPANT_SPEC).

The Pass-2 'who' fields plus the actor-edge additions (citedByAgent, isPerformedBy)
are materialised by the data-driven framework; these tests lock the family DATA that
must not drift: the six predicates (Ca/Cs flip guard), their per-predicate subject
category + extraction_type (+ row shape for the temporal isPerformedBy), the
per-predicate prompt wording, the Board-fallback scoping, and that every minted
participant property is covered by the unified domain/range guard registry. The full
materialize_edge_family path is exercised by tests/unit/test_edge_spec_equivalence.py
and tests/unit/test_dead_edge_families.py under a mocked resolver.
"""
from app.services.extraction import edge_spec as es
from app.services.extraction.rpo_edges import ALL_EDGE_RANGE
from rdflib import Namespace

CORE = Namespace("http://proethica.org/ontology/core#")
CASE = Namespace("http://proethica.org/ontology/case/15#")


def _by_prop():
    return {p.prop: p for p in es._PARTICIPANT_SPEC.predicates}


def test_specs_cover_the_six_actor_edges_with_correct_categories():
    """The family must wire the four Pass-2 participant edges plus the two actor-edge
    additions (citedByAgent, isPerformedBy), and must not confuse Ca (Capabilities)
    with Cs (Constraints)."""
    by_prop = _by_prop()
    assert set(by_prop) == {"obligatedParty", "constrainedEntity", "possessedBy",
                            "invokedBy", "citedByAgent", "isPerformedBy"}
    assert by_prop["obligatedParty"].subject_category == "Obligation"
    assert by_prop["obligatedParty"].subject_extraction_type == "obligations"
    assert by_prop["constrainedEntity"].subject_category == "Constraint"
    assert by_prop["constrainedEntity"].subject_extraction_type == "constraints"
    # Ca/Cs flip guard: possessedBy is the CAPABILITY edge, constrainedEntity the CONSTRAINT one.
    assert by_prop["possessedBy"].subject_category == "Capability"
    assert by_prop["possessedBy"].subject_extraction_type == "capabilities"
    assert by_prop["invokedBy"].subject_category == "Principle"
    assert by_prop["invokedBy"].subject_extraction_type == "principles"
    assert by_prop["citedByAgent"].subject_category == "Resource"
    assert by_prop["citedByAgent"].subject_extraction_type == "resources"
    # isPerformedBy reads the Step-3 rows: Action subjects live under the TEMPORAL
    # extraction type (NOT 'actions'), with the top-level rdf_json_ld row shape.
    assert by_prop["isPerformedBy"].subject_category == "Action"
    assert by_prop["isPerformedBy"].subject_extraction_type == "temporal_dynamics_enhanced"
    assert by_prop["isPerformedBy"].row_shape == "temporal"
    assert by_prop["isPerformedBy"].row_type_filter == ("Action",)
    assert by_prop["isPerformedBy"].normalize is es._strip_role_parenthetical
    # All six target Agent.
    assert all(p.range_category == "Agent" for p in by_prop.values())
    # The Board-pattern fallback is scoped to invokedBy/citedByAgent ONLY.
    assert by_prop["invokedBy"].board_agent_fallback
    assert by_prop["citedByAgent"].board_agent_fallback
    assert not any(by_prop[p].board_agent_fallback
                   for p in ("obligatedParty", "constrainedEntity", "possessedBy",
                             "isPerformedBy"))


def test_all_participant_edges_are_guarded():
    """Every minted participant property must be in ALL_EDGE_RANGE so the unified
    domain/range guard validates its subject (range Agent is intentionally outside
    the nine disjoint categories, so the object is unconstrained)."""
    for prop in ("obligatedParty", "constrainedEntity", "possessedBy", "invokedBy",
                 "citedByAgent", "isPerformedBy"):
        sub, obj = ALL_EDGE_RANGE[CORE[prop]]
        assert obj == "Agent", (prop, obj)
    assert ALL_EDGE_RANGE[CORE.obligatedParty][0] == "Obligation"
    assert ALL_EDGE_RANGE[CORE.constrainedEntity][0] == "Constraint"
    assert ALL_EDGE_RANGE[CORE.possessedBy][0] == "Capability"
    assert ALL_EDGE_RANGE[CORE.invokedBy][0] == "Principle"
    assert ALL_EDGE_RANGE[CORE.citedByAgent][0] == "Resource"
    assert ALL_EDGE_RANGE[CORE.isPerformedBy][0] == "Action"


def _items():
    return [
        {"id": 1, "desc": "Engineer B; the public",
         "subj_label": "Engineer B Public Safety Obligation",
         "shortlist": [(CASE["Agent_Engineer_B"], "Engineer B", 0.9),
                       (CASE["Agent_Owner"], "Owner", 0.4),
                       (CASE["Agent_Engineer_A"], "Engineer A", 0.35)]},
    ]


def test_prompt_wording_is_spec_specific_and_excludes_generics():
    """Each predicate's prompt names its component noun + relation verb and includes the
    party text verbatim, and instructs the model to drop generic/institutional parties
    (which is how a non-case party yields no edge)."""
    obl = _by_prop()["obligatedParty"]
    p = es._participant_prompt_factory(obl, es._PARTICIPANT_SPEC)(_items())
    assert "obligation" in p.lower()
    assert "BEARS" in p
    assert "the public" in p          # request text included verbatim
    assert "generic" in p.lower()

    inv = _by_prop()["invokedBy"]
    pi = es._participant_prompt_factory(inv, es._PARTICIPANT_SPEC)(_items())
    assert "principle" in pi.lower()
    assert "INVOKES" in pi


def test_board_agent_typed_deliberative_body_on_mint_and_reuse():
    """The Board agent is the deliberative body, not a case participant
    (cases v3.8.0, case-5 popover review): minted nodes carry the
    DeliberativeBody subclass + definition, and a REUSED extraction-minted
    Board agent (the case-5 pattern) gains both at materialization time."""
    from rdflib import Graph, Literal, RDF, RDFS, URIRef
    CASES = Namespace("http://proethica.org/ontology/cases#")
    CORE = Namespace("http://proethica.org/ontology/core#")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")

    g = Graph()
    minted = es._ensure_board_agent(g, 999)
    assert (minted, RDF.type, CASES.DeliberativeBody) in g
    assert g.value(minted, SKOS.definition) is not None
    # idempotent
    assert es._ensure_board_agent(g, 999) == minted

    g2 = Graph()
    extracted = URIRef("http://proethica.org/ontology/case/5#Agent_Board_of_Ethical_Review")
    g2.add((extracted, RDF.type, CORE.Agent))
    g2.add((extracted, RDFS.label, Literal("Board of Ethical Review")))
    reused = es._ensure_board_agent(g2, 5)
    assert reused == extracted  # no same-label duplicate minted
    assert (extracted, RDF.type, CASES.DeliberativeBody) in g2
    assert g2.value(extracted, SKOS.definition) is not None


def test_annotate_participant_agents_case_relative_definitions():
    """Participant agents get a deterministic case-relative definition from
    their own committed edges; the legacy process-description text (the
    2026-07-12 backfill putting pipeline metadata into skos:definition) is
    replaced; DeliberativeBody and hand-written definitions are untouched."""
    from rdflib import Graph, Literal, RDF, RDFS, URIRef
    from rdflib.namespace import SKOS
    CASES = Namespace("http://proethica.org/ontology/cases#")
    CORE = Namespace("http://proethica.org/ontology/core#")
    PROV = Namespace("http://www.w3.org/ns/prov#")
    NS = Namespace("http://proethica.org/ontology/case/58#")

    g = Graph()
    consultant = NS.Agent_Consultant
    g.add((consultant, RDF.type, CORE.Agent))
    g.add((consultant, RDFS.label, Literal("Consultant")))
    g.add((consultant, SKOS.definition, Literal(es._LEGACY_SCAFFOLD_DEFINITION)))
    action = NS.Site_Review
    g.add((action, RDFS.label, Literal("Site Review")))
    g.add((action, CORE.isPerformedBy, consultant))
    cap = NS.Structural_Analysis
    g.add((cap, RDFS.label, Literal("Structural Analysis")))
    g.add((cap, CORE.possessedBy, consultant))

    board = NS.Agent_Board
    g.add((board, RDF.type, CORE.Agent))
    g.add((board, RDF.type, CASES.DeliberativeBody))
    g.add((board, SKOS.definition, Literal("handcrafted board definition")))

    handmade = NS.Agent_Client
    g.add((handmade, RDF.type, CORE.Agent))
    g.add((handmade, SKOS.definition, Literal("An extracted, curated definition.")))
    g.add((NS.Duty, CORE.obligatedParty, handmade))

    edgeless = NS.Agent_Bystander
    g.add((edgeless, RDF.type, CORE.Agent))

    stats = es.annotate_participant_agents(g, 58)

    d = str(g.value(consultant, SKOS.definition))
    assert d.startswith("Participant in this case: ")
    assert "performs Site Review" in d and "possesses Structural Analysis" in d
    assert d.endswith(es._DERIVED_MARKER)
    assert str(g.value(board, SKOS.definition)) == "handcrafted board definition"
    assert str(g.value(handmade, SKOS.definition)) == "An extracted, curated definition."
    assert g.value(edgeless, SKOS.definition) is None
    assert g.value(consultant, PROV.wasAttributedTo) is not None
    # idempotent: a second run changes nothing
    before = len(g)
    stats2 = es.annotate_participant_agents(g, 58)
    assert len(g) == before and stats2["refreshed"] == 0 and stats2["defined"] == 0
