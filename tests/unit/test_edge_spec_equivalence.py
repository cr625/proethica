"""Golden-output tests for the data-driven edge framework.

Phase B2 consolidated six bespoke embedding-resolved edge appliers (resource,
state-affects, participant, fluent, obligation, temporal-relation) into one
data-driven framework (``edge_spec.materialize_edge_family`` + ``EDGE_REGISTRY``).
The OLD per-family appliers were then deleted; this test pins the framework's
output instead of comparing it to the (now-gone) oracle.

For each family the test runs the framework over an in-memory case graph + fixture
under a MOCKED resolver (the LLM select step is non-deterministic, so equivalence
must be asserted deterministically), then asserts the materialised EDGE triples
(subject, predicate, object) AND the PROV-O Derivation structure exactly match a
captured golden set. The golden sets were captured from the framework at the point
the OLD appliers were removed, after the prior cross-implementation equivalence
suite confirmed the two produced byte-identical graphs.

The mock makes the resolver deterministic: ``_shortlist`` returns a fixed candidate
list, ``_llm_select_multi`` returns a fixed selection, and the per-family temp_rdf
reader is replaced with the fixture. This exercises the orchestration that actually
varies across families (subject resolution, pool building, per-predicate emission,
single vs multi, the time: extra triple).
"""
import os
import tempfile

from rdflib import Graph, Namespace, RDF, RDFS, Literal
from rdflib.namespace import TIME

from app.services.extraction import edge_resolution as er
from app.services.extraction import edge_spec as es

CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")
CASE = Namespace("http://proethica.org/ontology/case/99#")
CASE_ID = 99


# --- graph + serialization helpers -----------------------------------------

def _ind(g, iri, label, category=None, rdf_type=None):
    g.add((iri, RDF.type, __import__("rdflib").OWL.NamedIndividual))
    g.add((iri, RDFS.label, Literal(label)))
    if category:
        g.add((iri, PROETH.conceptCategory, Literal(category)))
    if rdf_type:
        g.add((iri, RDF.type, rdf_type))


def _write(g):
    fd, path = tempfile.mkstemp(suffix=".ttl")
    os.close(fd)
    g.serialize(destination=path, format="turtle")
    return path


def _edge_triples(g):
    """All non-PROV, non-structural object-property triples (the materialised edges),
    as a comparable set. The seed individuals' type/label/conceptCategory are inputs,
    not outputs, so they are excluded; the time: triple is kept (it IS a materialised
    edge)."""
    skip_pred = {RDF.type, RDFS.label, RDFS.comment, PROETH.conceptCategory,
                 PROV.wasDerivedFrom, PROV.value}
    out = set()
    for s, p, o in g:
        if p in skip_pred:
            continue
        if isinstance(o, Literal):
            continue
        out.add((s, p, o))
    return out


def _prov_structure(g):
    """{prov_node: (sorted derived-from, label, value, comment)} for every Derivation
    node, so the provenance can be compared exactly."""
    out = {}
    for prov in g.subjects(RDF.type, PROV.Derivation):
        derived = tuple(sorted(str(x) for x in g.objects(prov, PROV.wasDerivedFrom)))
        label = next((str(x) for x in g.objects(prov, RDFS.label)), None)
        value = next((str(x) for x in g.objects(prov, PROV.value)), None)
        comment = next((str(x) for x in g.objects(prov, RDFS.comment)), None)
        out[str(prov)] = (derived, label, value, comment)
    return out


# --- deterministic resolver mocks ------------------------------------------

def _install_deterministic_resolver(monkeypatch, selection_by_desc):
    """Replace the embedding + shortlist + LLM-select primitives with deterministic
    stubs. ``selection_by_desc`` maps a desc string -> list of target IRIs the LLM
    'selects'. The shortlist returns those same targets (so the embedding fallback
    would also work), each at a fixed sim. Patched on both the shared home (``er``)
    and the framework module (``es``) since the framework rebinds the names at import."""
    def fake_embedding_service():
        return object()

    def fake_embed(svc, text):
        return [1.0] if (text or "").strip() else None

    def fake_shortlist(svc, desc, pool, floor, k):
        tgts = selection_by_desc.get(desc, [])
        return [(iri, str(iri).split("#")[-1], 0.9) for iri in tgts][:k]

    def fake_llm_multi(items, client=None, model=None, prompt_builder=None, model_tier="default"):
        return {str(it["id"]): [iri for iri, _l, _s in it["shortlist"]] for it in items}

    monkeypatch.setattr(er, "_embed", fake_embed)
    for m in (er, es):
        for name, fn in (("_embedding_service", fake_embedding_service),
                         ("_shortlist", fake_shortlist),
                         ("_llm_select_multi", fake_llm_multi)):
            if hasattr(m, name):
                monkeypatch.setattr(m, name, fn, raising=False)


def _run_family(monkeypatch, g, spec, reader, selection_by_desc):
    """Run the framework for ``spec`` over a copy of ``g`` with ``reader`` swapped onto
    the (frozen) spec, and return the written TTL parsed back as a Graph."""
    _install_deterministic_resolver(monkeypatch, selection_by_desc)
    path = _write(g)
    saved_reader = spec.reader
    object.__setattr__(spec, "reader", reader)
    try:
        es.materialize_edge_family(CASE_ID, path, spec, write_back=True)
    finally:
        object.__setattr__(spec, "reader", saved_reader)
    out = Graph()
    out.parse(path, format="turtle")
    os.unlink(path)
    return out


def _assert_golden(g, expected_edges, expected_prov):
    got_edges = _edge_triples(g)
    assert got_edges == expected_edges, (
        "edge triples differ\nMISSING: %s\nEXTRA: %s"
        % (expected_edges - got_edges, got_edges - expected_edges))
    got_prov = _prov_structure(g)
    assert got_prov == expected_prov, (
        "PROV-O structure differs\nMISSING: %s\nEXTRA: %s"
        % (set(expected_prov) - set(got_prov), set(got_prov) - set(expected_prov)))


def _prov(prefix, prop, subj_local, obj_local, subj_iri, obj_iri, label, value, comment):
    """Build a golden {prov_node: (...)} entry matching emit_edge_prov's IRI scheme."""
    node = str(CASE[f"{prefix}{subj_local}_{prop}_{obj_local}"])
    return {node: (tuple(sorted((str(subj_iri), str(obj_iri)))), label, value, comment)}


# ===========================================================================
# resource_edges  (Resource availableTo Agent, multi-select)
# ===========================================================================

def test_resource_edges_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["Res_NSPE_Code"], "NSPE Code", category="Resource")
    _ind(g, CASE["Agent_Engineer_B"], "Engineer B")
    g.add((CASE["Agent_Engineer_B"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    used_by = "Engineer B and Engineer A"
    sel = {used_by: [CASE["Agent_Engineer_B"], CASE["Agent_Engineer_A"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="NSPE Code", fields={"availableTo": [used_by]},
                              extra={"resource_label": "NSPE Code"})]

    out = _run_family(monkeypatch, g, es._RESOURCE_SPEC, reader, sel)

    comment = ("property=availableTo; resource used_by text resolved to the case Agent(s) "
               "by embedding shortlist + LLM multi-select")
    expected_edges = {
        (CASE["Res_NSPE_Code"], CORE.availableTo, CASE["Agent_Engineer_B"]),
        (CASE["Res_NSPE_Code"], CORE.availableTo, CASE["Agent_Engineer_A"]),
    }
    expected_prov = {}
    for obj_local, obj in (("Agent_Engineer_B", CASE["Agent_Engineer_B"]),
                           ("Agent_Engineer_A", CASE["Agent_Engineer_A"])):
        expected_prov.update(_prov(
            "resource_edge_provenance_", "availableTo", "Res_NSPE_Code", obj_local,
            CASE["Res_NSPE_Code"], obj, "Resource edge (availableTo)", used_by, comment))
    _assert_golden(out, expected_edges, expected_prov)


# ===========================================================================
# state_affects_edges  (State affects Agent, multi-select)
# ===========================================================================

def test_state_affects_edges_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["State_Risk"], "Public Safety Risk", category="State")
    _ind(g, CASE["Agent_Owner"], "Owner")
    g.add((CASE["Agent_Owner"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    parties = ["Owner", "Engineer A"]
    desc = "; ".join(parties)
    sel = {desc: [CASE["Agent_Owner"], CASE["Agent_Engineer_A"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Public Safety Risk", fields={"affects": parties},
                              extra={"state_label": "Public Safety Risk"})]

    out = _run_family(monkeypatch, g, es._STATE_AFFECTS_SPEC, reader, sel)

    comment = ("property=affects; state affectedParties text resolved to the case Agent(s) "
               "by embedding shortlist + LLM multi-select")
    expected_edges = {
        (CASE["State_Risk"], CORE.affects, CASE["Agent_Owner"]),
        (CASE["State_Risk"], CORE.affects, CASE["Agent_Engineer_A"]),
    }
    expected_prov = {}
    for obj_local, obj in (("Agent_Owner", CASE["Agent_Owner"]),
                           ("Agent_Engineer_A", CASE["Agent_Engineer_A"])):
        expected_prov.update(_prov(
            "state_affects_provenance_", "affects", "State_Risk", obj_local,
            CASE["State_Risk"], obj, "State edge (affects)", desc, comment))
    _assert_golden(out, expected_edges, expected_prov)


# ===========================================================================
# participant_edges  (per-predicate subject category, additive)
# ===========================================================================

def test_participant_edges_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["Obl_Confidentiality"], "Confidentiality Obligation", category="Obligation")
    _ind(g, CASE["Cap_Review"], "Peer Review Capability", category="Capability")
    _ind(g, CASE["Agent_Engineer_B"], "Engineer B")
    g.add((CASE["Agent_Engineer_B"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    sel = {"Engineer B": [CASE["Agent_Engineer_B"]],
           "Engineer A": [CASE["Agent_Engineer_A"]]}

    def reader(cid, spec):
        return [
            es.SubjectRow(label="Confidentiality Obligation",
                          fields={"obligatedParty": ["Engineer B"]},
                          extra={"subj_label": "Confidentiality Obligation"}),
            es.SubjectRow(label="Peer Review Capability",
                          fields={"possessedBy": ["Engineer A"]},
                          extra={"subj_label": "Peer Review Capability"}),
        ]

    out = _run_family(monkeypatch, g, es._PARTICIPANT_SPEC, reader, sel)

    expected_edges = {
        (CASE["Obl_Confidentiality"], CORE.obligatedParty, CASE["Agent_Engineer_B"]),
        (CASE["Cap_Review"], CORE.possessedBy, CASE["Agent_Engineer_A"]),
    }
    expected_prov = {}
    expected_prov.update(_prov(
        "participant_edge_provenance_", "obligatedParty", "Obl_Confidentiality",
        "Agent_Engineer_B", CASE["Obl_Confidentiality"], CASE["Agent_Engineer_B"],
        "Participant edge (obligatedParty)", "Engineer B",
        "property=obligatedParty; component party text resolved to the case Agent(s) "
        "by embedding shortlist + LLM select"))
    expected_prov.update(_prov(
        "participant_edge_provenance_", "possessedBy", "Cap_Review",
        "Agent_Engineer_A", CASE["Cap_Review"], CASE["Agent_Engineer_A"],
        "Participant edge (possessedBy)", "Engineer A",
        "property=possessedBy; component party text resolved to the case Agent(s) "
        "by embedding shortlist + LLM select"))
    _assert_golden(out, expected_edges, expected_prov)


# ===========================================================================
# fluent_edges  (union subject pool Action+Event -> State, multi-predicate)
# ===========================================================================

def test_fluent_edges_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["Action_Suspend"], "Project Suspension", category="Action")
    _ind(g, CASE["State_Suspended"], "Project Suspended", category="State")
    _ind(g, CASE["State_Risk"], "Public Safety Risk", category="State")

    sel = {"Project Suspended": [CASE["State_Suspended"]],
           "Public Safety Risk": [CASE["State_Risk"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Project Suspension",
                              fields={"initiates": ["Project Suspended"],
                                      "terminates": ["Public Safety Risk"]})]

    out = _run_family(monkeypatch, g, es._FLUENT_SPEC, reader, sel)

    expected_edges = {
        (CASE["Action_Suspend"], CORE.initiates, CASE["State_Suspended"]),
        (CASE["Action_Suspend"], CORE.terminates, CASE["State_Risk"]),
    }

    def _fluent_comment(p):
        return (f"property={p}; happening's {p} state text resolved to the case State(s) by "
                "embedding shortlist + LLM multi-select (Event Calculus fluent transition)")

    expected_prov = {}
    expected_prov.update(_prov(
        "fluent_edge_provenance_", "initiates", "Action_Suspend", "State_Suspended",
        CASE["Action_Suspend"], CASE["State_Suspended"], "Fluent edge (initiates)",
        "Project Suspended", _fluent_comment("initiates")))
    expected_prov.update(_prov(
        "fluent_edge_provenance_", "terminates", "Action_Suspend", "State_Risk",
        CASE["Action_Suspend"], CASE["State_Risk"], "Fluent edge (terminates)",
        "Public Safety Risk", _fluent_comment("terminates")))
    _assert_golden(out, expected_edges, expected_prov)


# ===========================================================================
# obligation_edges  (Action -> Obligation/Principle, mixed namespaces)
# ===========================================================================

def test_obligation_edges_golden(monkeypatch):
    g = Graph()
    _ind(g, CASE["Action_Disclose"], "Disclosure Action", category="Action")
    _ind(g, CASE["Obl_PublicSafety"], "Public Safety Obligation", category="Obligation")
    _ind(g, CASE["Prin_Honesty"], "Honesty Principle", category="Principle")

    sel = {"Public Safety Obligation": [CASE["Obl_PublicSafety"]],
           "Honesty Principle": [CASE["Prin_Honesty"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Disclosure Action",
                              fields={"fulfillsObligation": ["Public Safety Obligation"],
                                      "violatesObligation": [],
                                      "raisesObligation": [],
                                      "guidedByPrinciple": ["Honesty Principle"]})]

    out = _run_family(monkeypatch, g, es._OBLIGATION_SPEC, reader, sel)

    # fulfillsObligation is declared in CORE; guidedByPrinciple in PROETH.
    expected_edges = {
        (CASE["Action_Disclose"], CORE.fulfillsObligation, CASE["Obl_PublicSafety"]),
        (CASE["Action_Disclose"], PROETH.guidedByPrinciple, CASE["Prin_Honesty"]),
    }

    def _norm_comment(p):
        return (f"property={p}; action's {p} text resolved to the case "
                "Obligation/Principle individual(s) by embedding shortlist + LLM multi-select "
                "(obligation-engagement grounding)")

    expected_prov = {}
    expected_prov.update(_prov(
        "normative_edge_provenance_", "fulfillsObligation", "Action_Disclose",
        "Obl_PublicSafety", CASE["Action_Disclose"], CASE["Obl_PublicSafety"],
        "Normative edge (fulfillsObligation)", "Public Safety Obligation",
        _norm_comment("fulfillsObligation")))
    expected_prov.update(_prov(
        "normative_edge_provenance_", "guidedByPrinciple", "Action_Disclose",
        "Prin_Honesty", CASE["Action_Disclose"], CASE["Prin_Honesty"],
        "Normative edge (guidedByPrinciple)", "Honesty Principle",
        _norm_comment("guidedByPrinciple")))
    _assert_golden(out, expected_edges, expected_prov)


# ===========================================================================
# temporal_relation_edges  (single-valued + time: extra triple)
# ===========================================================================

def test_temporal_relation_edges_golden(monkeypatch):
    g = Graph()
    rel = CASE["TemporalRelation_1"]
    g.add((rel, RDF.type, __import__("rdflib").OWL.NamedIndividual))
    g.add((rel, RDF.type, PROETH.TemporalRelation))
    g.add((rel, RDFS.label, Literal("memo before request")))
    _ind(g, CASE["Action_Memo"], "Advisory Memo Preparation", category="Action")
    _ind(g, CASE["Event_Request"], "Recommendation Request", category="Event")

    from_desc = "Engineer A preparing the summary memo"
    to_desc = "City Administrator's request for a recommendation"
    sel = {from_desc: [CASE["Action_Memo"]], to_desc: [CASE["Event_Request"]]}
    prov_value = "the memo predates the request"

    def reader(cid, spec):
        return [es.SubjectRow(label="memo before request",
                              fields={"fromEntity": [from_desc], "toEntity": [to_desc]},
                              extra={"owlprop": "time:intervalBefore",
                                     "evidence": prov_value,
                                     "prov_desc": prov_value})]

    out = _run_family(monkeypatch, g, es._TEMPORAL_RELATION_SPEC, reader, sel)

    expected_edges = {
        (rel, PROETH.fromEntity, CASE["Action_Memo"]),
        (rel, PROETH.toEntity, CASE["Event_Request"]),
        # the OWL-Time triple lands on the relation node, pointing at the real toEntity
        (rel, TIME.intervalBefore, CASE["Event_Request"]),
    }

    def _tr_comment(p):
        return (f"property={p}; temporal relation's {p} text resolved to the case "
                "Action/Event individual by embedding shortlist + LLM select")

    expected_prov = {}
    expected_prov.update(_prov(
        "temporal_relation_edge_provenance_", "fromEntity", "TemporalRelation_1",
        "Action_Memo", rel, CASE["Action_Memo"], "Temporal relation edge (fromEntity)",
        prov_value, _tr_comment("fromEntity")))
    expected_prov.update(_prov(
        "temporal_relation_edge_provenance_", "toEntity", "TemporalRelation_1",
        "Event_Request", rel, CASE["Event_Request"], "Temporal relation edge (toEntity)",
        prov_value, _tr_comment("toEntity")))
    _assert_golden(out, expected_edges, expected_prov)
    # Explicitly assert the OWL-Time triple landed on the relation node.
    assert (rel, TIME.intervalBefore, CASE["Event_Request"]) in out
