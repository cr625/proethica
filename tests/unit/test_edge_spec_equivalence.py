"""Behaviour-preserving equivalence tests for the data-driven edge framework.

Phase B2 consolidated six bespoke embedding-resolved edge appliers (resource,
state-affects, participant, fluent, obligation, temporal-relation) into one
data-driven framework (``edge_spec.materialize_edge_family`` + ``EDGE_REGISTRY``).
The LLM select step is non-deterministic, so equivalence is asserted under a MOCKED
LLM (and mocked embedding shortlist + DB read): for each family this test runs BOTH
the OLD applier and the NEW framework over the same in-memory case graph + fixture,
and asserts the emitted edge triples (subject, predicate, object) AND the PROV-O
Derivation structure are byte-identical.

The mock makes the resolver deterministic: ``_shortlist`` returns a fixed candidate
list, ``_llm_select_multi`` / ``_llm_select`` return a fixed selection, and the
per-family temp_rdf reader is replaced with the fixture. Both implementations share
the same ``edge_resolution`` primitives, so the test exercises the orchestration that
actually differs (subject resolution, pool building, per-predicate emission, single
vs multi, the time: extra triple, the additive literal).
"""
import os
import tempfile

from rdflib import Graph, Namespace, RDF, RDFS, Literal, URIRef
from rdflib.namespace import TIME

from app.services.extraction import edge_resolution as er
from app.services.extraction import edge_spec as es
from app.services.extraction import resource_edges as resource_mod
from app.services.extraction import state_affects_edges as affects_mod
from app.services.extraction import participant_edges as participant_mod
from app.services.extraction import fluent_edges as fluent_mod
from app.services.extraction import obligation_edges as obligation_mod
from app.services.extraction import temporal_relation_edges as temporal_mod

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
    as a comparable set."""
    skip_pred = {RDF.type, RDFS.label, RDFS.comment, PROETH.conceptCategory,
                 PROV.wasDerivedFrom, PROV.value}
    out = set()
    for s, p, o in g:
        if p in skip_pred:
            continue
        if isinstance(o, Literal) and p not in (TIME.intervalBefore,):
            # keep object-property edges + the time: triple; drop datatype literals
            # except none here are edges
            continue
        out.add((s, p, o))
    return out


def _prov_structure(g):
    """{prov_node_local: (sorted derived-from, label, value, comment)} for every
    Derivation node, so two graphs' provenance can be compared exactly."""
    out = {}
    for prov in g.subjects(RDF.type, PROV.Derivation):
        derived = tuple(sorted(str(x) for x in g.objects(prov, PROV.wasDerivedFrom)))
        label = next((str(x) for x in g.objects(prov, RDFS.label)), None)
        value = next((str(x) for x in g.objects(prov, PROV.value)), None)
        comment = next((str(x) for x in g.objects(prov, RDFS.comment)), None)
        out[str(prov)] = (derived, label, value, comment)
    return out


def _assert_equivalent(old_path, new_path):
    go, gn = Graph(), Graph()
    go.parse(old_path, format="turtle")
    gn.parse(new_path, format="turtle")
    assert _edge_triples(go) == _edge_triples(gn), (
        "edge triples differ\nOLD-NEW: %s\nNEW-OLD: %s"
        % (_edge_triples(go) - _edge_triples(gn), _edge_triples(gn) - _edge_triples(go)))
    assert _prov_structure(go) == _prov_structure(gn), "PROV-O structure differs"
    # Also assert FULL triple-set identity (the strongest check).
    assert set(go) == set(gn), (
        "full graph differs\nOLD-NEW: %s\nNEW-OLD: %s"
        % (set(go) - set(gn), set(gn) - set(go)))


# --- deterministic resolver mocks ------------------------------------------

def _install_deterministic_resolver(monkeypatch, modules, selection_by_desc):
    """Replace the embedding + shortlist + LLM-select primitives with deterministic
    stubs across all modules that reference them. ``selection_by_desc`` maps a desc
    string -> list of target IRIs the LLM 'selects'. The shortlist returns those same
    targets (so the embedding fallback would also work), each at a fixed sim."""
    def fake_embedding_service():
        return object()

    def fake_embed(svc, text):
        # Non-empty so _candidate_pool / _agent_pool build a pool without the real model;
        # fake_shortlist ignores the vectors and keys off the desc string.
        return [1.0] if (text or "").strip() else None

    def fake_shortlist(svc, desc, pool, floor, k):
        tgts = selection_by_desc.get(desc, [])
        return [(iri, str(iri).split("#")[-1], 0.9) for iri in tgts][:k]

    def fake_llm_multi(items, client=None, model=None, prompt_builder=None, model_tier="default"):
        out = {}
        for it in items:
            out[str(it["id"])] = [iri for iri, _l, _s in it["shortlist"]]
        return out

    def fake_llm_single(items, prompt_builder=None, client=None, model=None, model_tier="fast"):
        out = {}
        for it in items:
            out[str(it["id"])] = it["shortlist"][0][0] if it["shortlist"] else None
        return out

    # Patch the shared home AND every module-local re-export binding (OLD appliers, the
    # framework module es, and edge_resolution). _embed is patched only on er because the
    # pool builders read er._embed regardless of which module calls them.
    monkeypatch.setattr(er, "_embed", fake_embed)
    for m in [er, es] + list(modules):
        for name, fn in (("_embedding_service", fake_embedding_service),
                         ("_shortlist", fake_shortlist),
                         ("_llm_select_multi", fake_llm_multi),
                         ("_llm_select", fake_llm_single)):
            if hasattr(m, name):
                monkeypatch.setattr(m, name, fn, raising=False)


def _run_old_new(monkeypatch, g, old_apply, new_spec, old_reader_patch, new_reader,
                 selection_by_desc, modules):
    """Run OLD applier and NEW framework over copies of the same graph + fixture and
    return their written TTL paths. ``new_reader`` is the fixture reader swapped onto
    the (frozen) spec for the duration of the run."""
    _install_deterministic_resolver(monkeypatch, modules, selection_by_desc)
    old_path = _write(g)
    new_path = _write(g)
    old_reader_patch()
    old_res = old_apply(case_id=CASE_ID, ttl_path=old_path, write_back=True)
    saved_reader = new_spec.reader
    object.__setattr__(new_spec, "reader", new_reader)
    try:
        new_res = es.materialize_edge_family(CASE_ID, new_path, new_spec, write_back=True)
    finally:
        object.__setattr__(new_spec, "reader", saved_reader)
    return old_path, new_path, old_res, new_res


# ===========================================================================
# resource_edges
# ===========================================================================

def test_resource_edges_equivalence(monkeypatch):
    g = Graph()
    _ind(g, CASE["Res_NSPE_Code"], "NSPE Code", category="Resource")
    _ind(g, CASE["Agent_Engineer_B"], "Engineer B")
    g.add((CASE["Agent_Engineer_B"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    used_by = "Engineer B and Engineer A"
    sel = {used_by: [CASE["Agent_Engineer_B"], CASE["Agent_Engineer_A"]]}

    db_rows = [{"label": "NSPE Code", "used_by": used_by, "definition": ""}]

    def old_patch():
        monkeypatch.setattr(resource_mod, "_resource_usage_from_db", lambda cid: db_rows)

    def new_reader(cid, spec):
        return [es.SubjectRow(label="NSPE Code", fields={"availableTo": [used_by]},
                              extra={"resource_label": "NSPE Code"})]

    op, np_, *_ = _run_old_new(monkeypatch, g, resource_mod.apply_resource_edges,
                               es._RESOURCE_SPEC, old_patch, new_reader, sel,
                               [resource_mod, er])
    _assert_equivalent(op, np_)


# ===========================================================================
# state_affects_edges
# ===========================================================================

def test_state_affects_edges_equivalence(monkeypatch):
    g = Graph()
    _ind(g, CASE["State_Risk"], "Public Safety Risk", category="State")
    _ind(g, CASE["Agent_Owner"], "Owner")
    g.add((CASE["Agent_Owner"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    parties = ["Owner", "Engineer A"]
    desc = "; ".join(parties)
    sel = {desc: [CASE["Agent_Owner"], CASE["Agent_Engineer_A"]]}

    def old_patch():
        monkeypatch.setattr(affects_mod, "_affected_from_db",
                            lambda cid: [{"label": "Public Safety Risk", "parties": parties, "desc": desc}])

    def new_reader(cid, spec):
        return [es.SubjectRow(label="Public Safety Risk", fields={"affects": parties},
                              extra={"state_label": "Public Safety Risk"})]

    op, np_, *_ = _run_old_new(monkeypatch, g, affects_mod.apply_state_affects_edges,
                               es._STATE_AFFECTS_SPEC, old_patch, new_reader, sel,
                               [affects_mod, er])
    _assert_equivalent(op, np_)


# ===========================================================================
# participant_edges (multi-predicate, per-predicate subject category, additive)
# ===========================================================================

def test_participant_edges_equivalence(monkeypatch):
    g = Graph()
    _ind(g, CASE["Obl_Confidentiality"], "Confidentiality Obligation", category="Obligation")
    _ind(g, CASE["Cap_Review"], "Peer Review Capability", category="Capability")
    _ind(g, CASE["Agent_Engineer_B"], "Engineer B")
    g.add((CASE["Agent_Engineer_B"], RDF.type, CORE.Agent))
    _ind(g, CASE["Agent_Engineer_A"], "Engineer A")
    g.add((CASE["Agent_Engineer_A"], RDF.type, CORE.Agent))

    sel = {"Engineer B": [CASE["Agent_Engineer_B"]],
           "Engineer A": [CASE["Agent_Engineer_A"]]}

    # OLD reads per-spec via _parties_from_db(case_id, spec).
    def old_db(cid, spec):
        if spec.prop == "obligatedParty":
            return [{"label": "Confidentiality Obligation", "desc": "Engineer B"}]
        if spec.prop == "possessedBy":
            return [{"label": "Peer Review Capability", "desc": "Engineer A"}]
        return []

    def old_patch():
        monkeypatch.setattr(participant_mod, "_parties_from_db", old_db)

    def new_rows(cid, spec):
        return [
            es.SubjectRow(label="Confidentiality Obligation",
                          fields={"obligatedParty": ["Engineer B"]},
                          extra={"subj_label": "Confidentiality Obligation"}),
            es.SubjectRow(label="Peer Review Capability",
                          fields={"possessedBy": ["Engineer A"]},
                          extra={"subj_label": "Peer Review Capability"}),
        ]


    op, np_, *_ = _run_old_new(monkeypatch, g, participant_mod.apply_participant_edges,
                               es._PARTICIPANT_SPEC, old_patch, new_rows, sel,
                               [participant_mod, er])
    _assert_equivalent(op, np_)


# ===========================================================================
# fluent_edges (union subject pool Action+Event -> State, multi-predicate)
# ===========================================================================

def test_fluent_edges_equivalence(monkeypatch):
    g = Graph()
    _ind(g, CASE["Action_Suspend"], "Project Suspension", category="Action")
    _ind(g, CASE["State_Suspended"], "Project Suspended", category="State")
    _ind(g, CASE["State_Risk"], "Public Safety Risk", category="State")

    init_desc = "Project Suspended"
    term_desc = "Public Safety Risk"
    sel = {init_desc: [CASE["State_Suspended"]], term_desc: [CASE["State_Risk"]]}

    happenings = [{"label": "Project Suspension",
                   "initiates": ["Project Suspended"],
                   "terminates": ["Public Safety Risk"]}]

    def old_patch():
        monkeypatch.setattr(fluent_mod, "_happenings_from_db", lambda cid: happenings)

    def new_rows(cid, spec):
        return [es.SubjectRow(label="Project Suspension",
                              fields={"initiates": ["Project Suspended"],
                                      "terminates": ["Public Safety Risk"]})]


    op, np_, *_ = _run_old_new(monkeypatch, g, fluent_mod.apply_fluent_edges,
                               es._FLUENT_SPEC, old_patch, new_rows, sel,
                               [fluent_mod, er])
    _assert_equivalent(op, np_)


# ===========================================================================
# obligation_edges (Action -> Obligation/Principle, mixed namespaces)
# ===========================================================================

def test_obligation_edges_equivalence(monkeypatch):
    g = Graph()
    _ind(g, CASE["Action_Disclose"], "Disclosure Action", category="Action")
    _ind(g, CASE["Obl_PublicSafety"], "Public Safety Obligation", category="Obligation")
    _ind(g, CASE["Prin_Honesty"], "Honesty Principle", category="Principle")

    ful_desc = "Public Safety Obligation"
    gp_desc = "Honesty Principle"
    sel = {ful_desc: [CASE["Obl_PublicSafety"]], gp_desc: [CASE["Prin_Honesty"]]}

    actions = [{"label": "Disclosure Action",
                "fulfillsObligation": ["Public Safety Obligation"],
                "violatesObligation": [],
                "raisesObligation": [],
                "guidedByPrinciple": ["Honesty Principle"]}]

    def old_patch():
        monkeypatch.setattr(obligation_mod, "_actions_from_db", lambda cid: actions)

    def new_rows(cid, spec):
        return [es.SubjectRow(label="Disclosure Action",
                              fields={"fulfillsObligation": ["Public Safety Obligation"],
                                      "violatesObligation": [],
                                      "raisesObligation": [],
                                      "guidedByPrinciple": ["Honesty Principle"]})]


    op, np_, *_ = _run_old_new(monkeypatch, g, obligation_mod.apply_obligation_edges,
                               es._OBLIGATION_SPEC, old_patch, new_rows, sel,
                               [obligation_mod, er])
    _assert_equivalent(op, np_)


# ===========================================================================
# temporal_relation_edges (single-valued + time: extra triple)
# ===========================================================================

def test_temporal_relation_edges_equivalence(monkeypatch):
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

    rels = [{"label": "memo before request", "fromEntity": from_desc, "toEntity": to_desc,
             "owlprop": "time:intervalBefore", "evidence": "the memo predates the request"}]

    def old_patch():
        monkeypatch.setattr(temporal_mod, "_temporal_relations_from_db", lambda cid: rels)

    def new_rows(cid, spec):
        return [es.SubjectRow(label="memo before request",
                              fields={"fromEntity": [from_desc], "toEntity": [to_desc]},
                              extra={"owlprop": "time:intervalBefore",
                                     "evidence": "the memo predates the request",
                                     "prov_desc": "the memo predates the request"})]


    op, np_, *_ = _run_old_new(monkeypatch, g, temporal_mod.apply_temporal_relation_edges,
                               es._TEMPORAL_RELATION_SPEC, old_patch, new_rows, sel,
                               [temporal_mod, er])
    _assert_equivalent(op, np_)
    # Explicitly assert the OWL-Time triple landed on the relation node in BOTH.
    gn = Graph(); gn.parse(np_, format="turtle")
    assert (rel, TIME.intervalBefore, CASE["Event_Request"]) in gn
