"""Case 24-1 review lessons L3, L4, L5, L6 (row adjust) and L8 on the data-driven
edge framework (edge_spec.py).

Each family runs over an in-memory case graph under the deterministic resolver
stubs of tests/unit/test_edge_spec_equivalence.py (fixed shortlist, fixed select,
fixture reader): no database, no embedding model, no LLM.
"""
import os
import tempfile
from types import SimpleNamespace

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS
from rdflib.namespace import TIME

from app.services.extraction import edge_resolution as er
from app.services.extraction import edge_spec as es

CASE_ID = 8
CASE = Namespace(f"http://proethica.org/ontology/case/{CASE_ID}#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _ind(g, local, label, cat=None, rdf_type=None, seq=None, extent=None, description="",
         marker=""):
    u = CASE[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDFS.label, Literal(label)))
    if cat:
        g.add((u, RDF.type, CORE[cat]))
    if rdf_type:
        g.add((u, RDF.type, rdf_type))
    if seq is not None:
        g.add((u, PROETH.temporalSequence, Literal(seq)))
    if extent:
        g.add((u, PROETH.temporalExtent, Literal(extent)))
    if description:
        g.add((u, PROETH.description, Literal(description)))
    if marker:
        g.add((u, PROETH.temporalMarker, Literal(marker)))
    return u


def _write(g):
    fd, path = tempfile.mkstemp(suffix=".ttl")
    os.close(fd)
    g.serialize(destination=path, format="turtle")
    return path


def _install_deterministic_resolver(monkeypatch, selection_by_desc):
    def fake_embedding_service():
        return object()

    def fake_embed(svc, text):
        return [1.0] if (text or "").strip() else None

    def fake_shortlist(svc, desc, pool, floor, k):
        allowed = {p[0] for p in pool}
        tgts = [t for t in selection_by_desc.get(desc, []) if t in allowed]
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


def _run_family(monkeypatch, path, spec, reader, selection_by_desc, reconstruct=False,
                **spec_overrides):
    _install_deterministic_resolver(monkeypatch, selection_by_desc)
    saved = {"reader": spec.reader}
    saved.update({k: getattr(spec, k) for k in spec_overrides})
    object.__setattr__(spec, "reader", reader)
    for k, v in spec_overrides.items():
        object.__setattr__(spec, k, v)
    try:
        if reconstruct:
            res = es.reconstruct_edge_family(CASE_ID, path, spec, write_back=True)
        else:
            res = es.materialize_edge_family(CASE_ID, path, spec, write_back=True)
    finally:
        for k, v in saved.items():
            object.__setattr__(spec, k, v)
    out = Graph()
    out.parse(path, format="turtle")
    return res, out


def _provs(g):
    return {str(p) for p in g.subjects(RDF.type, PROV.Derivation)}


# --- L3: fluent family -----------------------------------------------------------

def test_fluent_single_label_resolves_to_at_most_one_state(monkeypatch):
    """Stormwater_Accumulation_Increase initiated both Drinking_Water_Source_Runoff_Risk
    and Unquantified_Runoff_Risk_Awareness from ONE non-conjunctive label; the
    multi-select is bounded to the entities the field names."""
    g = Graph()
    _ind(g, "Event_Accumulation", "Stormwater Accumulation Increase", "Event")
    _ind(g, "State_Runoff_Risk", "Drinking Water Source Runoff Risk", "State")
    _ind(g, "State_Awareness", "Unquantified Runoff Risk Awareness", "State")
    label = "Runoff risk to the drinking water source"
    sel = {label: [CASE["State_Runoff_Risk"], CASE["State_Awareness"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Stormwater Accumulation Increase",
                              fields={"initiates": [label], "terminates": []})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._FLUENT_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert (CASE["Event_Accumulation"], CORE.initiates, CASE["State_Runoff_Risk"]) in out
    assert (CASE["Event_Accumulation"], CORE.initiates, CASE["State_Awareness"]) not in out
    assert res["initiates"]["edges"] == 1
    assert res["initiates"]["bounded"] == 1


def test_fluent_conjunctive_label_keeps_both_states(monkeypatch):
    g = Graph()
    _ind(g, "Action_Suspend", "Work Suspension", "Action")
    _ind(g, "State_Suspended", "Work Suspension State", "State")
    _ind(g, "State_Risk", "Public Safety Risk", "State")
    label = "Work Suspension State and Public Safety Risk"
    sel = {label: [CASE["State_Suspended"], CASE["State_Risk"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Work Suspension",
                              fields={"initiates": [label], "terminates": []})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._FLUENT_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert res["initiates"]["edges"] == 2
    assert "bounded" not in res["initiates"]


def test_fluent_label_equal_to_an_event_label_is_rejected(monkeypatch):
    """Work_Resumption's initiates label "Increased Stormwater Accumulation" is the
    label of the next Event: it names a happening, not a state, and is rejected
    before resolution instead of dangling or resolving to a state."""
    g = Graph()
    _ind(g, "Action_Resumption", "Work Resumption", "Action")
    _ind(g, "Event_Accumulation", "Increased Stormwater Accumulation", "Event")
    _ind(g, "State_Runoff_Risk", "Drinking Water Source Runoff Risk", "State")
    sel = {"Increased Stormwater Accumulation": [CASE["State_Runoff_Risk"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Work Resumption",
                              fields={"initiates": ["Increased Stormwater Accumulation"],
                                      "terminates": []})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._FLUENT_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert res["initiates"]["edges"] == 0
    assert res["initiates"]["rejected_labels"] == 1
    assert not list(out.subject_objects(CORE.initiates))


# --- L5: temporal relation endpoints -------------------------------------------

def _temporal_graph():
    g = Graph()
    eng = _ind(g, "Agent_Engineer_L", "Engineer L")
    g.add((eng, RDF.type, CORE.Agent))
    client = _ind(g, "Agent_Client_X", "Client X")
    g.add((client, RDF.type, CORE.Agent))
    notif = _ind(g, "Action_Risk_Notification", "Risk Notification", "Action", seq=3)
    g.add((notif, CORE.isPerformedBy, eng))
    refusal = _ind(g, "Action_Safeguard_Refusal", "Safeguard Refusal", "Action", seq=4)
    g.add((refusal, PROETH.hasAgent, Literal("Client X (project owner)")))
    _ind(g, "Action_Nondisclosure", "Nondisclosure at Suspension", "Action", seq=6)
    g.add((CASE["Action_Nondisclosure"], CORE.isPerformedBy, eng))
    return g


def _rel(g, local, label):
    u = CASE[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, PROETH.TemporalRelation))
    g.add((u, RDFS.label, Literal(label)))
    return u


def test_temporal_endpoint_resolves_lexically_before_the_model(monkeypatch):
    g = _temporal_graph()
    rel = _rel(g, "TemporalRelation_3", "nondisclosure during suspension talks")
    from_desc = ("Engineer L's non-disclosure to Client X during communications about the "
                 "suspension")
    to_desc = "the resumption of work on the site"
    # The model would have chosen Risk Notification for the phrase; lexical wins.
    sel = {from_desc: [CASE["Action_Risk_Notification"], CASE["Action_Safeguard_Refusal"]],
           to_desc: []}

    def reader(cid, spec):
        return [es.SubjectRow(label="nondisclosure during suspension talks",
                              fields={"fromEntity": [from_desc], "toEntity": [to_desc]},
                              extra={"owlprop": "time:intervalBefore", "evidence": "",
                                     "prov_desc": None})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._TEMPORAL_RELATION_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert set(out.objects(rel, PROETH.fromEntity)) == {CASE["Action_Nondisclosure"]}
    assert res["fromEntity"]["direct"] == 1
    prov = [p for p in out.subjects(RDF.type, PROV.Derivation) if "fromEntity" in str(p)]
    assert prov and "lexical match" in str(out.value(prov[0], RDFS.comment))


def test_temporal_phrase_naming_an_agent_excludes_other_performers(monkeypatch):
    """"Client X's refusal" must not resolve to an action Engineer L performed."""
    g = _temporal_graph()
    rel = _rel(g, "TemporalRelation_10", "notification before refusal")
    from_desc = "the notification of the runoff risk"
    to_desc = "Client X's refusal"
    sel = {from_desc: [CASE["Action_Risk_Notification"]],
           to_desc: [CASE["Action_Risk_Notification"], CASE["Action_Safeguard_Refusal"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="notification before refusal",
                              fields={"fromEntity": [from_desc], "toEntity": [to_desc]},
                              extra={"owlprop": "time:intervalBefore", "evidence": "",
                                     "prov_desc": None})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._TEMPORAL_RELATION_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert set(out.objects(rel, PROETH.toEntity)) == {CASE["Action_Safeguard_Refusal"]}
    assert (rel, TIME.intervalBefore, CASE["Action_Safeguard_Refusal"]) in out
    assert res["toEntity"]["edges"] == 1


def test_temporal_single_valued_enforced_at_emit_and_reconstruct_reresolves(monkeypatch):
    """TemporalRelation_3 carried two fromEntity actions after re-runs selected
    differently. A second value is skipped at emit; reconstruct_edge_family drops
    the family and re-applies, so the new resolution replaces the old one."""
    g = _temporal_graph()
    rel = _rel(g, "TemporalRelation_3", "stale relation")
    # A previous run: fromEntity -> Risk Notification with its provenance and time triple.
    g.add((rel, PROETH.fromEntity, CASE["Action_Risk_Notification"]))
    g.add((rel, PROETH.toEntity, CASE["Action_Nondisclosure"]))
    g.add((rel, TIME.intervalBefore, CASE["Action_Nondisclosure"]))
    er.emit_edge_prov(g, CASE_ID, "temporal_relation_edge_provenance_", "fromEntity", rel,
                      CASE["Action_Risk_Notification"], "old", "l", "c")
    from_desc = "the client's refusal of safeguards"
    to_desc = "Engineer L's nondisclosure at suspension"
    sel = {from_desc: [CASE["Action_Safeguard_Refusal"]], to_desc: [CASE["Action_Nondisclosure"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="stale relation",
                              fields={"fromEntity": [from_desc], "toEntity": [to_desc]},
                              extra={"owlprop": "time:intervalBefore", "evidence": "",
                                     "prov_desc": None})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._TEMPORAL_RELATION_SPEC, reader, sel)
        assert set(out.objects(rel, PROETH.fromEntity)) == {CASE["Action_Risk_Notification"]}
        assert res["fromEntity"]["single_valued_skipped"] == 1
        assert res["fromEntity"]["edges"] == 0

        res2, out2 = _run_family(monkeypatch, path, es._TEMPORAL_RELATION_SPEC, reader, sel,
                                 reconstruct=True)
    finally:
        os.unlink(path)
    assert res2["reconstructed"]["edges_dropped"] >= 3   # fromEntity, toEntity, time triple
    assert res2["reconstructed"]["prov_dropped"] == 1
    assert set(out2.objects(rel, PROETH.fromEntity)) == {CASE["Action_Safeguard_Refusal"]}
    assert set(out2.objects(rel, PROETH.toEntity)) == {CASE["Action_Nondisclosure"]}
    assert (rel, TIME.intervalBefore, CASE["Action_Nondisclosure"]) in out2
    assert not any("Action_Risk_Notification" in p for p in _provs(out2))


# --- L4: Allen validation ------------------------------------------------------------

def _allen_graph():
    g = Graph()
    _ind(g, "Event_Rainfall", "Heavy Rainfall", "Event", seq=5, extent="interval")
    _ind(g, "Action_Resumption", "Work Resumption", "Action", seq=6, extent="instant")
    _ind(g, "Action_Study", "Runoff Risk Quantification Study", "Action", seq=3, extent="interval")
    _ind(g, "Event_Risk_Confirmed", "Runoff Risk Confirmed", "Event", seq=4, extent="instant")
    _ind(g, "Action_Report", "Professional Report Completion", "Action", seq=7, extent="instant",
         description="Per the BER's conclusion, Engineer L must not issue a report")
    chain = CASE["CausalChain_1"]
    g.add((chain, RDF.type, PROETH.CausalChain))
    g.add((chain, PROETH.cause, CASE["Action_Study"]))
    g.add((chain, PROETH.effect, CASE["Event_Risk_Confirmed"]))
    return g


def _relation_rows(specs):
    """specs: [(local, from_desc, to_desc, owlprop, evidence)] -> reader rows."""
    def reader(cid, spec):
        return [es.SubjectRow(label=local,
                              fields={"fromEntity": [f], "toEntity": [t]},
                              extra={"owlprop": owlprop, "evidence": ev, "prov_desc": ev or None})
                for local, f, t, owlprop, ev in specs]
    return reader


def test_allen_relations_are_validated_after_resolution(monkeypatch):
    g = _allen_graph()
    r6 = _rel(g, "TemporalRelation_6", "TemporalRelation_6")
    r8 = _rel(g, "TemporalRelation_8", "TemporalRelation_8")
    r12 = _rel(g, "TemporalRelation_12", "TemporalRelation_12")
    r13 = _rel(g, "TemporalRelation_13", "TemporalRelation_13")
    rok = _rel(g, "TemporalRelation_1", "TemporalRelation_1")
    sel = {"the heavy rainfall": [CASE["Event_Rainfall"]],
           "the resumption of work": [CASE["Action_Resumption"]],
           "the confirmed runoff risk": [CASE["Event_Risk_Confirmed"]],
           "the quantification study": [CASE["Action_Study"]],
           "completion of a professional report": [CASE["Action_Report"]]}
    rows = _relation_rows([
        # equals between an interval and an instant (hedge inside the quote too)
        ("TemporalRelation_6", "the heavy rainfall", "the resumption of work",
         "time:intervalEquals", "About this same time (presumably within weeks)"),
        # an interval during an instant
        ("TemporalRelation_8", "the heavy rainfall", "the resumption of work",
         "time:intervalDuring", "About this same time"),
        # the risk became fact before the study that established it
        ("TemporalRelation_12", "the confirmed runoff risk", "the quantification study",
         "time:intervalBefore", "the risk was confirmed"),
        # an endpoint that never occurred
        ("TemporalRelation_13", "the quantification study", "completion of a professional report",
         "time:intervalBefore", "the study preceded the report"),
        # a sound relation
        ("TemporalRelation_1", "the quantification study", "the confirmed runoff risk",
         "time:intervalBefore", "the study was followed by the confirmed risk"),
    ])
    case_text = ("The study was followed by the confirmed risk. About this same time, heavy "
                 "rainfall increased stormwater accumulation. The risk was confirmed.")
    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._TEMPORAL_RELATION_SPEC, rows, sel,
                               case_text_loader=lambda cid: case_text)
    finally:
        os.unlink(path)
    post = res["post_process"]
    assert post["relations_checked"] == 5
    assert post["relations_dropped"] == 4
    for rel in (r6, r8, r12, r13):
        assert not list(out.objects(rel, PROETH.fromEntity)), rel
        assert not list(out.objects(rel, PROETH.toEntity)), rel
        assert not [p for p, o in out.predicate_objects(rel) if str(p).startswith(str(TIME))], rel
    assert (rok, PROETH.fromEntity, CASE["Action_Study"]) in out
    assert (rok, PROETH.toEntity, CASE["Event_Risk_Confirmed"]) in out
    assert (rok, TIME.intervalBefore, CASE["Event_Risk_Confirmed"]) in out
    reasons = {p["relation"]: " ".join(p["problems"]) for p in post["problems"]}
    assert "needs two intervals" in reasons["TemporalRelation_6"]
    assert "verbatim" in reasons["TemporalRelation_6"]
    assert "needs two intervals" in reasons["TemporalRelation_8"]
    assert "contradicts" in reasons["TemporalRelation_12"]
    assert "did not occur" in reasons["TemporalRelation_13"]
    # Withdrawn relations leave no provenance behind.
    assert not any("TemporalRelation_12" in p or "TemporalRelation_6" in p for p in _provs(out))
    assert res["total"] == 2


# --- L8: affects pre-resolution, multi-select bound ---------------------------------

def test_affects_exact_agent_names_resolve_before_the_model(monkeypatch):
    """The affectedParties text named Engineer L first and the select omitted it on
    four states; exact agent names now resolve deterministically and only the
    remaining party text reaches the model."""
    g = Graph()
    _ind(g, "State_Risk", "Drinking Water Source Runoff Risk", "State")
    eng = _ind(g, "Agent_Engineer_L", "Engineer L")
    g.add((eng, RDF.type, CORE.Agent))
    client = _ind(g, "Agent_Client_X", "Client X")
    g.add((client, RDF.type, CORE.Agent))
    parties = ["Engineer L", "Client X", "Public (future users of the water source)"]
    # The model returns nothing for the generic public party.
    sel = {"Public (future users of the water source)": []}

    def reader(cid, spec):
        return [es.SubjectRow(label="Drinking Water Source Runoff Risk",
                              fields={"affects": parties},
                              extra={"state_label": "Drinking Water Source Runoff Risk"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._STATE_AFFECTS_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert set(out.objects(CASE["State_Risk"], CORE.affects)) == {eng, client}
    assert res["affects"]["direct"] == 2
    assert res["affects"]["edges"] == 2
    assert res["affects"]["unresolved"] == 1
    prov = [p for p in out.subjects(RDF.type, PROV.Derivation) if "Agent_Engineer_L" in str(p)]
    assert prov and str(out.value(prov[0], PROV.value)) == "Engineer L"
    assert "exact label match" in str(out.value(prov[0], RDFS.comment))


def test_requires_capability_bounded_to_the_named_obligation(monkeypatch):
    """The field named only "Safety Obligation"; the multi-select added a second
    obligation. The bound keeps the best-ranked target for the one named entity."""
    g = Graph()
    _ind(g, "Cap_Analysis", "Engineering Analysis Capability", "Capability")
    _ind(g, "Obl_Safety", "Safety Obligation", "Obligation")
    _ind(g, "Obl_Charge", "Responsible Charge Obligation", "Obligation")
    sel = {"Safety Obligation": [CASE["Obl_Safety"], CASE["Obl_Charge"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Engineering Analysis Capability",
                              fields={"requiresCapability": ["Safety Obligation"]},
                              extra={"subj_label": "Engineering Analysis Capability"})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._REQUIRES_CAPABILITY_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert (CASE["Obl_Safety"], CORE.requiresCapability, CASE["Cap_Analysis"]) in out
    assert (CASE["Obl_Charge"], CORE.requiresCapability, CASE["Cap_Analysis"]) not in out
    assert res["requiresCapability"]["edges"] == 1
    assert res["requiresCapability"]["bounded"] == 1


def test_fulfills_target_not_named_by_the_source_list_is_dropped(monkeypatch):
    g = Graph()
    _ind(g, "Action_Notification", "Risk Notification", "Action")
    _ind(g, "Obl_Disclose", "Duty to Disclose Runoff Risk", "Obligation")
    _ind(g, "Obl_Faithful", "Faithful Agent Duty", "Obligation")
    sel = {"Duty to Disclose Runoff Risk": [CASE["Obl_Disclose"], CASE["Obl_Faithful"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Risk Notification",
                              fields={"fulfillsObligation": ["Duty to Disclose Runoff Risk"],
                                      "violatesObligation": [], "raisesObligation": [],
                                      "guidedByPrinciple": []})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._OBLIGATION_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert set(out.objects(CASE["Action_Notification"], CORE.fulfillsObligation)) == {CASE["Obl_Disclose"]}
    assert res["fulfillsObligation"]["bounded"] == 1


# --- L6 (row adjust): a prescribed action fulfils nothing ----------------------------

class _StubQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter_by(self, **kw):
        return self

    def all(self):
        return self._rows


def test_prescribed_action_fulfills_move_to_raises_in_the_reader(monkeypatch):
    import app.models.temporary_rdf_storage as trs
    rows = [
        SimpleNamespace(entity_label="Refusal to Acquiesce", rdf_json_ld={
            "@type": "proeth:Action", "rdfs:label": "Refusal to Acquiesce",
            "proeth:description": "Per the BER's conclusion, Engineer L must not continue work",
            "proeth:temporalMarker": "Present, unresolved endpoint",
            "proeth:fulfillsObligation": ["Public Safety Duty"],
            "proeth:raisesObligation": ["Faithful Agent Duty"]}),
        SimpleNamespace(entity_label="Risk Notification", rdf_json_ld={
            "@type": "proeth:Action", "rdfs:label": "Risk Notification",
            "proeth:description": "Engineer L notified Client X of the runoff risk",
            "proeth:temporalMarker": "Month 2",
            "proeth:fulfillsObligation": ["Duty to Disclose Runoff Risk"]}),
    ]
    monkeypatch.setattr(trs, "TemporaryRDFStorage", SimpleNamespace(query=_StubQuery(rows)))
    out = {r.label: r.fields for r in es._read_temporal(CASE_ID, es._OBLIGATION_SPEC)}
    assert out["Refusal to Acquiesce"]["fulfillsObligation"] == []
    assert out["Refusal to Acquiesce"]["raisesObligation"] == ["Faithful Agent Duty", "Public Safety Duty"]
    assert out["Risk Notification"]["fulfillsObligation"] == ["Duty to Disclose Runoff Risk"]


def test_demote_prescribed_fulfills_is_a_no_op_for_performed_actions():
    fields = {"fulfillsObligation": ["Duty A"], "raisesObligation": []}
    es._demote_prescribed_fulfills({"proeth:description": "Engineer L notified the client"}, fields)
    assert fields == {"fulfillsObligation": ["Duty A"], "raisesObligation": []}
