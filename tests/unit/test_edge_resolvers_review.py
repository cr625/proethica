"""Review of the edge-resolvers lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Four defects found in the merge review, each with the scenario that broke:

1. state_edges narrowed the candidate pool across the descriptions of one class
   row. ``_collect`` restricted the pool for one obligation_activation entry (to
   the lexical candidates of a duty name, or to the obligations citing a code)
   and kept the restricted pool for the next entry of the same row, so the second
   duty a class row names was shortlisted against the candidates of the first
   duty and resolved to nothing. Class row 95600 of case 8 names three duties.

2. edge_coherence read the action description as proeth:description, but the
   commit emitter writes it as rdfs:comment (ttl_emitters._add_temporal_fields).
   On the committed graph happening_occurred saw no description, so an action
   prescribed only in its description counted as performed for the Allen
   endpoint check, and later_happening_citing_state matched labels only.

3. The modality derivation ignored the parse-time verdict. prompts-and-filters
   stores proeth:modality on each action row (happening_checks
   .classify_action_modality) and the emitter commits it as a literal; the row
   adjust of the obligation family, the engagement pass and happening_occurred
   re-derived the modality from phrases alone, so the two derivations disagreed
   whenever the Board sentence sat in the text references rather than the
   description. The stored value now wins when present; the phrase rule covers
   the rows that carry none.

4. The fluent family rejected an initiates / terminates label equal to a
   happening label even when a State carries the same label. Such a label names
   a state the pool holds, so it is no longer rejected.

The committed shapes come from the real producers (rdf_converter.convert_action_to_rdf
and the commit emitter), not from hand-built triples. Hermetic: no DB, no LLM.
"""
import os
from types import SimpleNamespace

from rdflib import Graph, Literal, RDFS

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction import edge_coherence as ec
from app.services.extraction import edge_spec as es
from app.services.extraction.obligation_engagement_apply import apply_obligation_engagement
from app.services.temporal_dynamics.utils.rdf_converter import convert_action_to_rdf
from tests.unit.test_edge_spec_case8_lessons import _ind, _run_family, _write
from tests.unit.test_state_edges_case8_lessons import CASE, CORE, PROETH, _class, _indiv, _run


# --- 1. state_edges: the pool is restricted per description, not per class row ---

def test_second_duty_name_on_one_class_row_resolves(monkeypatch):
    """Two duty names on one class row, each with its own obligation individual.
    The first name narrowed the pool to its lexical candidates and the second was
    shortlisted against that pool; both must resolve."""
    psr = _class("Public Safety Risk State",
                 obligation_activation=["Duty to Protect Public Safety", "Faithful Agent Duty"])
    individuals = [_indiv("Public Safety Risk State", state_class="Public Safety Risk State")]
    sl = {"Duty to Protect Public Safety": [CASE["Obl_Public_Safety"]],
          "Faithful Agent Duty": [CASE["Obl_Faithful_Agent"]]}
    res, out, stubs = _run(monkeypatch, [psr], individuals, sl)
    state = CASE["State_Public_Safety_Risk"]
    assert set(out.objects(state, CORE.activatesObligation)) == {
        CASE["Obl_Public_Safety"], CASE["Obl_Faithful_Agent"]}
    assert res["activatesObligation"] == 2
    assert res["unresolved"] == 0
    assert stubs.shortlist_calls == ["Duty to Protect Public Safety", "Faithful Agent Duty"]


# --- 2 and 3. the committed action record as the emitter writes it ---

def _committed_action(g, local, action, sequence=None):
    """Store a Step-3 action through the real converter and the real commit
    emitter: proeth:description lands as rdfs:comment, proeth:modality and
    proeth:temporalMarker as intermediate literals."""
    row = convert_action_to_rdf(action, 8)
    if sequence is not None:
        row["proeth:temporalSequence"] = sequence   # temporal_sequence_apply writes it
    svc = OntServeCommitService.__new__(OntServeCommitService)
    svc._base_ontology_index._objprop_cache = {"fulfillsObligation", "cause", "effect"}
    uri = CASE[local]
    svc._add_temporal_fields(g, uri, row)
    g.add((uri, RDFS.label, Literal(action["label"])))
    return uri


def test_happening_occurred_reads_the_committed_description():
    g = Graph()
    refusal = _committed_action(g, "Refusal_to_Acquiesce", {
        "label": "Refusal to Acquiesce",
        "description": "Per the BER's conclusion, Engineer L must not continue work on the project",
        "agent": "Engineer L (Professional Engineer)", "temporal_marker": "Present"})
    notification = _committed_action(g, "Risk_Notification", {
        "label": "Risk Notification",
        "description": "Engineer L notified Client X of the runoff risk",
        "agent": "Engineer L (Professional Engineer)", "temporal_marker": "Month 2"})
    # The shape the emitter writes: the description is rdfs:comment, never proeth:description.
    assert (refusal, RDFS.comment, None) in g
    assert (refusal, PROETH.description, None) not in g
    assert not ec.happening_occurred(g, refusal)
    assert ec.happening_occurred(g, notification)
    # The Allen endpoint check sees the prescription too.
    problems = ec.allen_relation_problems(g, "time:intervalBefore", notification, refusal)
    assert any("did not occur" in p for p in problems)


def test_later_happening_citing_state_reads_the_committed_description():
    g = Graph()
    state = _ind(g, "State_Budget", "Client X Budget Constraint", "State")
    recovery = _ind(g, "Event_Recovery", "Client Financial Recovery", "Event", seq=6)
    later = _committed_action(g, "Design_Phase_Continuation", {
        "label": "Design Phase Continuation",
        "description": "Client X proceeds under continuing budget limits",
        "agent": "Client X", "temporal_marker": "Month 9"}, sequence=7)
    assert ec.later_happening_citing_state(g, state, recovery) == later


def test_stored_modality_wins_over_the_phrase_rule():
    # The explicit verdict (happening_checks.classify_action_modality) is taken as is.
    assert ec.derive_action_modality(
        "Engineer L declines to continue the design work", "", "",
        explicit="prescribed") == ec.MODALITY_PRESCRIBED
    assert ec.derive_action_modality(
        "Engineer L notified Client X, as the Code would require", "", "discussion",
        explicit="performed") == ec.MODALITY_PERFORMED
    # A value outside the vocabulary falls back to the phrase rule.
    assert ec.derive_action_modality(
        "Engineer L must not continue", "", "", explicit="maybe") == ec.MODALITY_PRESCRIBED
    assert ec.derive_action_modality(
        "Engineer L notified the client", "", "", explicit="") == ec.MODALITY_PERFORMED


def test_committed_modality_literal_decides_happening_occurred():
    g = Graph()
    refusal = _committed_action(g, "Refusal_to_Acquiesce", {
        "label": "Refusal to Acquiesce",
        "description": "Engineer L declines to continue the design work",
        "agent": "Engineer L", "temporal_marker": "Present", "modality": "prescribed"})
    assert (refusal, PROETH.modality, Literal("prescribed")) in g
    assert not ec.happening_occurred(g, refusal)
    notified = _committed_action(g, "Risk_Notification", {
        "label": "Risk Notification",
        "description": "Engineer L notified Client X, as the Code would require",
        "agent": "Engineer L", "temporal_marker": "Month 2", "modality": "performed",
        "source_section": "discussion"})
    assert ec.happening_occurred(g, notified)


def test_row_adjust_honours_the_stored_modality():
    fields = {"fulfillsObligation": ["Public Safety Duty"], "raisesObligation": []}
    es._demote_prescribed_fulfills(
        {"rdfs:label": "Refusal to Acquiesce", "proeth:modality": "prescribed",
         "proeth:description": "Engineer L declines to continue the design work"}, fields)
    assert fields == {"fulfillsObligation": [], "raisesObligation": ["Public Safety Duty"]}
    fields = {"fulfillsObligation": ["Duty to Disclose Runoff Risk"], "raisesObligation": []}
    es._demote_prescribed_fulfills(
        {"rdfs:label": "Risk Notification", "proeth:modality": "performed",
         "proeth:description": "Engineer L notified Client X, as the Code would require",
         "proeth:discoveredInSection": "discussion"}, fields)
    assert fields == {"fulfillsObligation": ["Duty to Disclose Runoff Risk"], "raisesObligation": []}


class _StubQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter_by(self, **kw):
        return self

    def order_by(self, *a):
        return self

    def all(self):
        return self._rows


class _StubExtractor:
    """Keeps every action's buckets as given and records the contexts it was shown."""

    def __init__(self):
        self.seen = None
        self.obligation_statuses = []

    def extract(self, case_id, case_title, actions, discussion_excerpt="", strict=True):
        from app.services.extraction.obligation_engagement import ObligationEngagementResult
        from app.services.extraction.schemas import PerActionEngagement
        self.seen = list(actions)
        return ObligationEngagementResult(
            actions=[PerActionEngagement(action_iri=a.iri, fulfills=list(a.fulfills),
                                         violates=list(a.violates), raises=list(a.raises))
                     for a in actions],
            rationale=None)


def test_engagement_pass_honours_the_stored_modality(monkeypatch):
    """The refusal carries proeth:modality prescribed with a neutral description; the
    notification carries performed with a discussion-section description that says
    "would". The phrase rule alone read both the other way round."""
    import sqlalchemy.orm.attributes as sa_attrs
    import app.models as models
    import app.models.temporary_rdf_storage as trs
    rows = [
        SimpleNamespace(entity_label="Refusal to Acquiesce", rdf_json_ld={
            "@id": str(CASE["Action_Refusal_to_Acquiesce"]), "@type": "proeth:Action",
            "rdfs:label": "Refusal to Acquiesce", "proeth:modality": "prescribed",
            "proeth:description": "Engineer L declines to continue the design work",
            "proeth:temporalMarker": "Present", "proeth:temporalSequence": 8,
            "proeth:fulfillsObligation": ["Public Safety Duty"]}),
        SimpleNamespace(entity_label="Risk Notification", rdf_json_ld={
            "@id": str(CASE["Action_Risk_Notification"]), "@type": "proeth:Action",
            "rdfs:label": "Risk Notification", "proeth:modality": "performed",
            "proeth:description": "Engineer L notified Client X, as the Code would require",
            "proeth:discoveredInSection": "discussion", "proeth:temporalSequence": 3,
            "proeth:fulfillsObligation": ["Duty to Disclose Runoff Risk"]}),
    ]
    monkeypatch.setattr(trs, "TemporaryRDFStorage", SimpleNamespace(query=_StubQuery(rows), id=None))
    monkeypatch.setattr(models, "db", SimpleNamespace(session=SimpleNamespace(commit=lambda: None)))
    monkeypatch.setattr(sa_attrs, "flag_modified", lambda *a, **k: None)
    import app.services.extraction.obligation_engagement_apply as apply_mod
    monkeypatch.setattr(apply_mod, "_load_case_title", lambda cid: "Case 24-1")
    monkeypatch.setattr(apply_mod, "_load_discussion", lambda cid: "")
    ext = _StubExtractor()
    res = apply_obligation_engagement(8, extractor=ext)
    assert res["status"] == "ok"
    assert {a.label: a.modality for a in ext.seen} == {
        "Refusal to Acquiesce": "prescribed", "Risk Notification": "performed"}
    assert res["prescribed_fulfills_demoted"] == 1
    assert rows[0].rdf_json_ld["proeth:fulfillsObligation"] == []
    assert rows[0].rdf_json_ld["proeth:raisesObligation"] == ["Public Safety Duty"]
    assert rows[1].rdf_json_ld["proeth:fulfillsObligation"] == ["Duty to Disclose Runoff Risk"]
    assert rows[1].rdf_json_ld["proeth:raisesObligation"] == []


# --- 4. fluent family: a label a State carries is never a rejected happening label ---

def test_fluent_label_shared_by_a_state_and_a_happening_resolves_to_the_state(monkeypatch):
    g = Graph()
    _ind(g, "Action_Suspend", "Work Suspension", "Action")
    _ind(g, "Action_Notice", "Suspension Notice", "Action")
    _ind(g, "State_Suspension", "Work Suspension", "State")
    sel = {"Work Suspension": [CASE["State_Suspension"]]}

    def reader(cid, spec):
        return [es.SubjectRow(label="Suspension Notice",
                              fields={"initiates": ["Work Suspension"], "terminates": []})]

    path = _write(g)
    try:
        res, out = _run_family(monkeypatch, path, es._FLUENT_SPEC, reader, sel)
    finally:
        os.unlink(path)
    assert (CASE["Action_Notice"], CORE.initiates, CASE["State_Suspension"]) in out
    assert res["initiates"]["edges"] == 1
    assert "rejected_labels" not in res["initiates"]
    # A label no State carries is still rejected.
    g2 = Graph()
    _ind(g2, "Action_Resumption", "Work Resumption", "Action")
    _ind(g2, "Event_Accumulation", "Increased Stormwater Accumulation", "Event")
    _ind(g2, "State_Runoff_Risk", "Drinking Water Source Runoff Risk", "State")

    def reader2(cid, spec):
        return [es.SubjectRow(label="Work Resumption",
                              fields={"initiates": ["Increased Stormwater Accumulation"],
                                      "terminates": []})]

    path2 = _write(g2)
    try:
        res2, out2 = _run_family(monkeypatch, path2, es._FLUENT_SPEC, reader2,
                                 {"Increased Stormwater Accumulation": [CASE["State_Runoff_Risk"]]})
    finally:
        os.unlink(path2)
    assert res2["initiates"]["rejected_labels"] == 1
    assert not list(out2.subject_objects(CORE.initiates))
