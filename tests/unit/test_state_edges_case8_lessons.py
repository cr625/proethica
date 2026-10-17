"""Case 24-1 review lessons L1, L2 and L7 on the state-edge applier (state_edges.py).

apply_state_edges is driven end to end over an in-memory case graph with the
temp_rdf reader, the embedding service, the shortlist, the select and the
diagnostics saver replaced by deterministic stubs: no database, no model.
"""
import os
import tempfile

from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS

from app.services.extraction import edge_resolution as er
from app.services.extraction import state_edges as se

CASE_ID = 8
CASE = Namespace(f"http://proethica.org/ontology/case/{CASE_ID}#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")


# --- fixture graph (case-8 shapes) -------------------------------------------

def _ind(g, local, label, cat, seq=None, description="", **lits):
    u = CASE[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, CORE[cat]))
    g.add((u, RDFS.label, Literal(label)))
    if seq is not None:
        g.add((u, PROETH.temporalSequence, Literal(seq)))
    if description:
        g.add((u, PROETH.description, Literal(description)))
    for k, v in lits.items():
        for val in (v if isinstance(v, list) else [v]):
            g.add((u, PROETH[k], Literal(val)))
    return u


def _case_graph():
    g = Graph()
    _ind(g, "Event_Client_Financial_Setback", "Client Financial Setback", "Event", seq=1)
    _ind(g, "Action_Risk_Notification", "Risk Notification", "Action", seq=3,
         description="Engineer L notified Client X of the runoff risk")
    _ind(g, "Action_Safeguard_Refusal", "Safeguard Refusal", "Action", seq=4,
         description="Client X insists on proceeding without added safeguards")
    _ind(g, "Event_Stormwater_Accumulation", "Increased Stormwater Accumulation", "Event", seq=5)
    _ind(g, "Event_Client_Financial_Recovery", "Client Financial Recovery", "Event", seq=6)
    _ind(g, "Event_Budget_Reaffirmed", "Budget Reaffirmed", "Event", seq=7,
         description="Client X proceeds under continuing budget limits")
    _ind(g, "State_Confirmed_Runoff_Risk_Finding", "Confirmed Runoff Risk Finding", "State")
    _ind(g, "State_Public_Safety_Risk", "Public Safety Risk State", "State")
    _ind(g, "State_Budget_Constraint", "Client X Budget Constraint", "State")
    _ind(g, "Obl_Faithful_Agent", "Faithful Agent Duty", "Obligation",
         textReferences=["Engineers shall advise their clients or employers when they believe "
                         "a project will not be successful (Code III.1.b)."])
    _ind(g, "Obl_Disclose", "Duty to Disclose Runoff Risk", "Obligation",
         textReferences=["Engineer L notified Client X of the runoff risk"])
    _ind(g, "Obl_Public_Safety", "Duty to Protect Public Safety", "Obligation")
    return g


def _write(g):
    fd, path = tempfile.mkstemp(suffix=".ttl")
    os.close(fd)
    g.serialize(destination=path, format="turtle")
    return path


def _class(label, uri="", **fields):
    c = {"label": label, "uri": uri, "definition": f"{label} definition",
         "obligation_activation": [], "action_constraints": [], "activation_conditions": [],
         "termination_conditions": [], "principle_transformation": ""}
    c.update(fields)
    return c


def _indiv(label, state_class="", matched="", trigger="", terminated=""):
    return {"label": label, "definition": f"{label} definition", "state_class": state_class,
            "matched_ontology_uri": matched, "triggering_event": trigger,
            "terminated_by": terminated}


class _Stubs:
    """Deterministic resolver: the shortlist maps a description to pool members, the
    select takes the first shortlisted candidate (or the configured answer)."""

    def __init__(self, monkeypatch, shortlist_by_desc, select_none=()):
        self.shortlist_calls = []
        self.saved = []
        monkeypatch.setattr(er, "_embed", lambda svc, t: [1.0] if (t or "").strip() else None)
        monkeypatch.setattr(se, "_embedding_service", lambda: object())

        def fake_shortlist(svc, desc, pool, floor, k):
            self.shortlist_calls.append(desc)
            allowed = {p[0] for p in pool}
            return [(iri, str(iri).rsplit("#", 1)[-1], 0.9)
                    for iri in shortlist_by_desc.get(desc, []) if iri in allowed]

        def fake_select(items, client=None, model=None, diag=None):
            if diag is not None:
                diag["prompt"] = "SELECT PROMPT"
                diag["model"] = "stub"
                diag["raws"] = ["{}"]
            return {str(it["id"]): (None if it["desc"] in select_none
                                    else (it["shortlist"][0][0] if it["shortlist"] else None))
                    for it in items}

        monkeypatch.setattr(se, "_shortlist", fake_shortlist)
        monkeypatch.setattr(se, "_llm_select", fake_select)

    def saver(self, **kw):
        self.saved.append(kw)


def _run(monkeypatch, classes, individuals, shortlist_by_desc, select_none=(),
         provision_texts=None):
    stubs = _Stubs(monkeypatch, shortlist_by_desc, select_none)
    monkeypatch.setattr(se, "_state_linkage_from_db", lambda cid: (classes, individuals))
    path = _write(_case_graph())
    try:
        res = se.apply_state_edges(
            CASE_ID, path, write_back=True, diagnostics_saver=stubs.saver,
            provision_text_loader=lambda frags: provision_texts or {})
        out = Graph()
        out.parse(path, format="turtle")
    finally:
        os.unlink(path)
    return res, out, stubs


# --- L1: class row lookup never falls back to an embedding -------------------

def test_best_class_uses_literal_then_matched_uri_then_nothing():
    psr = _class("Public Safety Risk State", uri="http://proethica.org/ontology/intermediate#PublicSafetyRiskState")
    crr = _class("Confirmed Runoff Risk Finding", uri="http://proethica.org/ontology/intermediate#ConfirmedRunoffRiskFinding")
    classes = [psr, crr]
    assert se._best_class(_indiv("x", state_class="ConfirmedRunoffRiskFinding"), classes) is crr
    assert se._best_class(_indiv("x", matched=crr["uri"]), classes) is crr
    # Fragment of the matched uri against the class label (class row uri missing).
    crr_no_uri = _class("Confirmed Runoff Risk Finding")
    assert se._best_class(_indiv("x", matched="http://x#ConfirmedRunoffRiskFinding"),
                          [psr, crr_no_uri]) is crr_no_uri
    # The named class row is gone (auto merge): None, never the neighbour.
    assert se._best_class(_indiv("x", state_class="Confirmed Runoff Risk Finding",
                                 matched=crr["uri"]), [psr]) is None
    # No evidence at all and a single class row: that row.
    assert se._best_class(_indiv("x"), [psr]) is psr
    assert se._best_class(_indiv("x"), [psr, crr]) is None


def test_deleted_class_row_inherits_no_linkage_but_keeps_its_trigger(monkeypatch):
    """Case 8: the class row of Confirmed Runoff Risk Finding was deleted; the
    embedding fallback copied Public Safety Risk State's principleTransformation and
    activation edges onto it. Now the individual carries nothing from the other
    class and its own trigger still resolves."""
    psr = _class("Public Safety Risk State",
                 obligation_activation=["Duty to protect public safety"],
                 activation_conditions=["Stormwater accumulates on the site"],
                 principle_transformation="Public safety paramount becomes a duty to act")
    individuals = [
        _indiv("Confirmed Runoff Risk Finding", state_class="Confirmed Runoff Risk Finding",
               matched="http://proethica.org/ontology/intermediate#ConfirmedRunoffRiskFinding",
               trigger="Stormwater accumulation increases on the site"),
        _indiv("Public Safety Risk State", state_class="Public Safety Risk State",
               trigger="Stormwater accumulation increases on the site"),
    ]
    sl = {"Duty to protect public safety": [CASE["Obl_Public_Safety"]],
          "Stormwater accumulates on the site": [CASE["Event_Stormwater_Accumulation"]],
          "Stormwater accumulation increases on the site": [CASE["Event_Stormwater_Accumulation"]]}
    res, out, _ = _run(monkeypatch, [psr], individuals, sl)

    crr, psr_state = CASE["State_Confirmed_Runoff_Risk_Finding"], CASE["State_Public_Safety_Risk"]
    assert res["class_unresolved"] == 1
    assert (crr, PROETH.principleTransformation, None) not in out
    assert not list(out.objects(crr, CORE.activatesObligation))
    assert (crr, CORE.activatedByEvent, CASE["Event_Stormwater_Accumulation"]) in out
    # The individual that does own the class row gets the class linkage.
    assert (psr_state, PROETH.principleTransformation, None) in out
    assert (psr_state, CORE.activatesObligation, CASE["Obl_Public_Safety"]) in out
    assert res["principleTransformation"] == 1


# --- L2: happenings as candidates, termination from the individual only -------

def test_action_candidate_is_emitted_in_the_event_calculus_direction(monkeypatch):
    """"Client insists on proceeding without added safeguards" names the Action
    Safeguard_Refusal. It is now a candidate, and because activatedByEvent ranges
    over Event the transition lands as Action initiates State under the fluent
    family's provenance."""
    psr = _class("Public Safety Risk State")
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State",
                          trigger="Client insists on proceeding without added safeguards")]
    sl = {"Client insists on proceeding without added safeguards":
          [CASE["Action_Safeguard_Refusal"], CASE["Event_Client_Financial_Setback"]]}
    res, out, _ = _run(monkeypatch, [psr], individuals, sl)
    state = CASE["State_Public_Safety_Risk"]
    assert (CASE["Action_Safeguard_Refusal"], CORE.initiates, state) in out
    assert not list(out.objects(state, CORE.activatedByEvent))
    assert res["initiates"] == 1 and res["activatedByEvent"] == 0
    provs = {str(p) for p in out.subjects(RDF.type, PROV.Derivation)}
    assert any("fluent_edge_provenance_Action_Safeguard_Refusal_initiates" in p for p in provs)


def test_not_terminated_literal_short_circuits_and_class_conditions_do_not_feed(monkeypatch):
    budget = _class("Budget Constraint State",
                    termination_conditions=["Client's financial recovery"])
    individuals = [_indiv("Client X Budget Constraint", state_class="Budget Constraint State",
                          terminated="Not fully terminated; continuing budget limitations remain")]
    sl = {"Client's financial recovery": [CASE["Event_Client_Financial_Recovery"]],
          "Not fully terminated; continuing budget limitations remain":
          [CASE["Event_Client_Financial_Recovery"]]}
    res, out, stubs = _run(monkeypatch, [budget], individuals, sl)
    assert res["not_terminated"] == 1
    assert res["terminatedByEvent"] == 0
    assert not list(out.objects(CASE["State_Budget_Constraint"], CORE.terminatedByEvent))
    # Neither the class condition nor the persisting literal reached the resolver.
    assert "Client's financial recovery" not in stubs.shortlist_calls
    assert not any(c.startswith("Not fully") for c in stubs.shortlist_calls)


def test_activation_preceding_the_trigger_is_dropped(monkeypatch):
    """A class-level activation condition resolved to Client_Financial_Setback (seq 1)
    while the state's own trigger is the stormwater accumulation (seq 5): the
    earlier activation is incoherent and withdrawn."""
    psr = _class("Public Safety Risk State",
                 activation_conditions=["Client suffers a financial setback"])
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State",
                          trigger="Stormwater accumulation increases on the site")]
    sl = {"Client suffers a financial setback": [CASE["Event_Client_Financial_Setback"]],
          "Stormwater accumulation increases on the site": [CASE["Event_Stormwater_Accumulation"]]}
    res, out, _ = _run(monkeypatch, [psr], individuals, sl)
    state = CASE["State_Public_Safety_Risk"]
    assert set(out.objects(state, CORE.activatedByEvent)) == {CASE["Event_Stormwater_Accumulation"]}
    assert res["incoherent_dropped"] == 1
    assert res["activatedByEvent"] == 1
    provs = {str(p) for p in out.subjects(RDF.type, PROV.Derivation)}
    assert not any("Event_Client_Financial_Setback" in p for p in provs)


def test_termination_contradicted_by_a_later_citing_happening_is_dropped(monkeypatch):
    budget = _class("Budget Constraint State")
    individuals = [_indiv("Client X Budget Constraint", state_class="Budget Constraint State",
                          terminated="Client's finances recover")]
    sl = {"Client's finances recover": [CASE["Event_Client_Financial_Recovery"]]}
    res, out, _ = _run(monkeypatch, [budget], individuals, sl)
    # Budget_Reaffirmed (seq 7) cites the budget limits after the recovery (seq 6).
    assert not list(out.objects(CASE["State_Budget_Constraint"], CORE.terminatedByEvent))
    assert res["incoherent_dropped"] == 1
    assert res["terminatedByEvent"] == 0


# --- L7: provision match, duty names, diagnostics ----------------------------

def test_code_section_resolves_by_provision_match_before_the_model(monkeypatch):
    psr = _class("Client Advisement State",
                 obligation_activation=["Client Advisement Obligation under Code section III.1.b"])
    individuals = [_indiv("Public Safety Risk State", state_class="Client Advisement State")]
    # The model would have picked the wrong duty; it is never asked.
    sl = {"Client Advisement Obligation under Code section III.1.b": [CASE["Obl_Disclose"]]}
    res, out, stubs = _run(monkeypatch, [psr], individuals, sl)
    state = CASE["State_Public_Safety_Risk"]
    assert set(out.objects(state, CORE.activatesObligation)) == {CASE["Obl_Faithful_Agent"]}
    assert res["provision_matched"] == 1
    assert "Client Advisement Obligation under Code section III.1.b" not in stubs.shortlist_calls
    provs = [p for p in out.subjects(RDF.type, PROV.Derivation) if "Obl_Faithful_Agent" in str(p)]
    assert provs and "provision match" in str(out.value(provs[0], RDFS.comment))


def test_provision_sentence_in_text_references_matches_through_the_provision_text(monkeypatch):
    """The obligation quotes the III.1.b sentence without the code; the provision
    text supplied by the loader joins them."""
    g_text = ("Engineers shall advise their clients or employers when they believe a project "
              "will not be successful")
    psr = _class("Client Advisement State",
                 obligation_activation=["Duty to advise the client under III.1.b"])
    individuals = [_indiv("Public Safety Risk State", state_class="Client Advisement State")]
    res, out, stubs = _run(monkeypatch, [psr], individuals, {},
                           provision_texts={"III_1_b": g_text})
    assert set(out.objects(CASE["State_Public_Safety_Risk"], CORE.activatesObligation)) == {
        CASE["Obl_Faithful_Agent"]}
    assert res["provision_matched"] == 1


def test_duty_name_with_no_individual_yields_no_edge_and_is_persisted(monkeypatch):
    psr = _class("Public Safety Risk State",
                 obligation_activation=["Risk Investigation And Quantification Obligation",
                                        "Duty to Protect Public Safety"])
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State")]
    # The nearest duty the embedding would offer for the phantom name.
    sl = {"Risk Investigation And Quantification Obligation": [CASE["Obl_Disclose"]],
          "Duty to Protect Public Safety": [CASE["Obl_Public_Safety"]]}
    res, out, stubs = _run(monkeypatch, [psr], individuals, sl)
    state = CASE["State_Public_Safety_Risk"]
    assert set(out.objects(state, CORE.activatesObligation)) == {CASE["Obl_Public_Safety"]}
    assert res["unresolved"] == 1
    assert "Risk Investigation And Quantification Obligation" not in stubs.shortlist_calls
    # Diagnostics are persisted although the family resolved an edge.
    assert res["diagnostics_persisted"] is True
    assert len(stubs.saved) == 1
    summary = stubs.saved[0]["results_summary"]
    assert summary["unresolved_requests"][0]["reason"] == "names a duty with no extracted individual"
    assert summary["counts"]["activatesObligation"] == 1


def test_select_none_is_persisted_per_request(monkeypatch):
    psr = _class("Public Safety Risk State",
                 activation_conditions=["Heavy rainfall saturates the site",
                                        "Stormwater accumulation increases on the site"])
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State")]
    sl = {"Heavy rainfall saturates the site": [CASE["Event_Stormwater_Accumulation"]],
          "Stormwater accumulation increases on the site": [CASE["Event_Stormwater_Accumulation"]]}
    res, out, stubs = _run(monkeypatch, [psr], individuals, sl,
                           select_none=("Heavy rainfall saturates the site",))
    assert res["activatedByEvent"] == 1
    assert res["unresolved"] == 1
    assert len(stubs.saved) == 1
    kw = stubs.saved[0]
    assert kw["concept_type"] == "state_edges_select"
    assert kw["prompt_text"] == "SELECT PROMPT"
    reqs = kw["results_summary"]["unresolved_requests"]
    assert reqs[0]["desc"] == "Heavy rainfall saturates the site"
    assert "select answered none" in reqs[0]["reason"]
    assert reqs[0]["shortlist"] == ["Event_Stormwater_Accumulation"]


def test_nothing_unresolved_persists_nothing(monkeypatch):
    psr = _class("Public Safety Risk State",
                 activation_conditions=["Stormwater accumulation increases on the site"])
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State")]
    sl = {"Stormwater accumulation increases on the site": [CASE["Event_Stormwater_Accumulation"]]}
    res, _out, stubs = _run(monkeypatch, [psr], individuals, sl)
    assert res["unresolved"] == 0
    assert res["diagnostics_persisted"] is False
    assert stubs.saved == []
