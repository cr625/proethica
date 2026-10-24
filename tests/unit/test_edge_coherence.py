"""Unit tests for the shared edge-coherence checks (edge_coherence.py).

The case 24-1 review (ProEthica case 8) found the commit-time resolvers never
checked a pick against the temporal order, the causal chains, the extents, the
performing agent, or the other extracted labels. These tests lock each check as a
pure function over an in-memory graph: no database, no embedding model, no LLM.
"""
from rdflib import Graph, Literal, Namespace, OWL, RDF, RDFS
from rdflib.namespace import TIME

from app.services.extraction import edge_coherence as ec
from app.services.extraction.edge_resolution import emit_edge_prov

CASE = Namespace("http://proethica.org/ontology/case/8#")
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")
PROV = Namespace("http://www.w3.org/ns/prov#")


def _ind(g, local, label, cat, seq=None, extent=None, description="", marker="", section=""):
    u = CASE[local]
    g.add((u, RDF.type, OWL.NamedIndividual))
    g.add((u, RDF.type, CORE[cat]))
    g.add((u, RDFS.label, Literal(label)))
    if seq is not None:
        g.add((u, PROETH.temporalSequence, Literal(seq)))
    if extent:
        g.add((u, PROETH.temporalExtent, Literal(extent)))
    if description:
        g.add((u, PROETH.description, Literal(description)))
    if marker:
        g.add((u, PROETH.temporalMarker, Literal(marker)))
    if section:
        g.add((u, PROETH.discoveredInSection, Literal(section)))
    return u


# --- lexical helpers ---------------------------------------------------------

def test_lexical_norm_joins_hyphens_and_strips_possessives():
    assert ec.lexical_norm("Engineer L's non-disclosure") == "engineer l nondisclosure"
    assert ec.lexical_norm("Nondisclosure at Suspension") == "nondisclosure at suspension"
    assert ec.lexical_norm("EthicalDilemmaState") == "ethical dilemma state"


def test_lexical_match_picks_the_covered_label_and_refuses_ambiguity():
    labels = {CASE["Nondisclosure_at_Suspension"]: "Nondisclosure at Suspension",
              CASE["Risk_Notification"]: "Risk Notification",
              CASE["Safeguard_Refusal"]: "Safeguard Refusal"}
    desc = "Engineer L's non-disclosure to Client X during communications about the suspension"
    assert ec.lexical_match(desc, labels) == CASE["Nondisclosure_at_Suspension"]
    # No label covered: the caller falls through to the embedding + model path.
    assert ec.lexical_match("Client X's refusal", labels) is None
    # Two labels covered equally well: ambiguous, no deterministic pick.
    amb = {CASE["Work_Suspension"]: "Work Suspension",
           CASE["Suspension_Notice"]: "Suspension Notice"}
    assert ec.lexical_match("the suspension", amb) is None
    # Inflections fold onto the same key (disclose / disclosure).
    duty = {CASE["Obl_Disclose"]: "Risk Disclosure Duty"}
    assert ec.lexical_match("Duty to disclose the risk", duty,
                            drop=ec.GENERIC_DUTY_WORDS) == CASE["Obl_Disclose"]


def test_agents_named_in_and_performer_exclusion():
    g = Graph()
    eng = _ind(g, "Agent_Engineer_L", "Engineer L", "Agent")
    client = _ind(g, "Agent_Client_X", "Client X", "Agent")
    agents = {eng: "Engineer L", client: "Client X"}
    assert ec.agents_named_in("Client X's refusal", agents) == [client]
    assert ec.agents_named_in("the client's refusal", agents) == []

    refusal = _ind(g, "Action_Safeguard_Refusal", "Safeguard Refusal", "Action")
    g.add((refusal, CORE.isPerformedBy, client))
    notification = _ind(g, "Action_Risk_Notification", "Risk Notification", "Action")
    g.add((notification, PROETH.hasAgent, Literal("Engineer L (Professional Engineer)")))
    rainfall = _ind(g, "Event_Rainfall", "Heavy Rainfall", "Event")
    assert ec.performed_by_other_agent(g, notification, "Client X")
    assert not ec.performed_by_other_agent(g, refusal, "Client X")
    # No performer information: never excluded.
    assert not ec.performed_by_other_agent(g, rainfall, "Client X")


def test_named_target_bound_counts_the_entities_the_field_names():
    assert ec.named_target_bound(["Safety Obligation"]) == 1
    assert ec.named_target_bound(["Engineer B and Engineer A"]) == 2
    assert ec.named_target_bound(["Public Safety Risk; Project Suspended", "Budget Constraint"]) == 3
    assert ec.named_target_bound([]) == 1


def test_names_duty_detects_duty_names_not_sentences():
    assert ec.names_duty("Risk Investigation And Quantification Obligation")
    assert ec.names_duty("Duty to Protect Public Safety")
    assert not ec.names_duty("the engineer must disclose the risk to the client when asked")
    assert not ec.names_duty("Client Advisement Obligation under Code section III.1.b")
    assert not ec.names_duty("")


def test_cites_state_token_overlap():
    assert ec.cites_state("Client X proceeds under continuing budget limits",
                          "Client X Budget Constraint")
    assert not ec.cites_state("Heavy rainfall increased stormwater accumulation",
                              "Client X Budget Constraint")


# --- modality ----------------------------------------------------------------

def test_derive_action_modality():
    assert ec.derive_action_modality(
        "Per the BER's conclusion, Engineer L must not continue work on the project",
        "Present, unresolved endpoint", "discussion") == ec.MODALITY_PRESCRIBED
    assert ec.derive_action_modality(
        "Engineer L notified Client X of the runoff risk", "Month 2", "facts") == ec.MODALITY_PERFORMED
    # Discussion-section provenance plus deontic language marks a prescription.
    assert ec.derive_action_modality(
        "Engineer L should have disclosed the risk to the water authority", "",
        "discussion") == ec.MODALITY_PRESCRIBED
    # Discussion-section provenance alone does not.
    assert ec.derive_action_modality(
        "Engineer L notified the client", "", "discussion") == ec.MODALITY_PERFORMED


def test_happening_occurred_reads_the_committed_record():
    g = Graph()
    prescribed = _ind(g, "Action_Refusal_to_Acquiesce", "Refusal to Acquiesce", "Action",
                      description="Per the BER's conclusion, Engineer L must not continue work",
                      marker="Present, unresolved endpoint")
    performed = _ind(g, "Action_Risk_Notification", "Risk Notification", "Action",
                     description="Engineer L notified Client X of the runoff risk")
    event = _ind(g, "Event_Rainfall", "Heavy Rainfall", "Event", description="must not matter")
    assert not ec.happening_occurred(g, prescribed)
    assert ec.happening_occurred(g, performed)
    assert ec.happening_occurred(g, event)


# --- Allen relations -----------------------------------------------------------

CASE_TEXT = ("Engineer L notified Client X of the runoff risk. About this same time, heavy "
             "rainfall increased stormwater accumulation on the site, and work resumed.")


def test_evidence_is_verbatim_rejects_a_hedge_inside_the_quote():
    assert ec.evidence_is_verbatim(
        '"About this same time, heavy rainfall increased stormwater accumulation"', CASE_TEXT)
    assert not ec.evidence_is_verbatim(
        "About this same time (presumably within weeks), heavy rainfall increased "
        "stormwater accumulation", CASE_TEXT)
    assert not ec.evidence_is_verbatim("About this same time", "")


def test_allen_equals_and_during_need_two_intervals():
    g = Graph()
    rainfall = _ind(g, "Event_Rainfall", "Heavy Rainfall", "Event", seq=5, extent="interval")
    resumption = _ind(g, "Action_Resumption", "Work Resumption", "Action", seq=6, extent="instant")
    problems = ec.allen_relation_problems(g, "time:intervalEquals", rainfall, resumption)
    assert any("needs two intervals" in p for p in problems)
    problems = ec.allen_relation_problems(g, "time:intervalDuring", rainfall, resumption)
    assert any("needs two intervals" in p for p in problems)
    # An ordering relation between the same endpoints has no extent requirement.
    assert ec.allen_relation_problems(g, "time:intervalBefore", rainfall, resumption) == []
    # The anchor type stands in for a missing extent literal.
    g2 = Graph()
    a = _ind(g2, "Action_A", "A", "Action")
    b = _ind(g2, "Action_B", "B", "Action")
    g2.add((a, TIME.hasTime, CASE["time_Action_A"]))
    g2.add((CASE["time_Action_A"], RDF.type, TIME.Instant))
    assert ec.happening_extent(g2, a) == "instant"
    assert ec.happening_extent(g2, b) is None
    assert any("needs two intervals" in p
               for p in ec.allen_relation_problems(g2, "time:intervalStarts", a, b))


def test_allen_meets_and_overlaps_need_two_intervals():
    """OWL-Time defines meets and overlaps on proper intervals too (case 25-1 committed an
    intervalMeets whose target, a projected team reassignment, is an instant)."""
    g = Graph()
    delivery = _ind(g, "Event_Delivery", "Delivery", "Event", seq=13, extent="interval")
    reassignment = _ind(g, "Event_Reassignment", "Team Reassignment", "Event", seq=14,
                        extent="instant")
    for prop in ("time:intervalMeets", "time:intervalMetBy",
                 "time:intervalOverlaps", "time:intervalOverlappedBy"):
        assert any("needs two intervals" in p
                   for p in ec.allen_relation_problems(g, prop, delivery, reassignment)), prop


def test_allen_relation_with_an_unresolved_source_is_judged_through_its_target():
    g = Graph()
    completion = _ind(g, "Event_Completion", "Project Deliverable Completion", "Event", seq=13,
                      extent="instant")
    problems = ec.allen_relation_problems(g, "time:intervalFinishes", None, completion)
    assert problems == ["intervalFinishes needs two intervals but Event_Completion is an instant"]
    # An ordering relation needs both endpoints for the order check, so one end is not judged.
    assert ec.allen_relation_problems(g, "time:intervalBefore", None, completion) == []


def test_allen_order_against_sequence_and_causal_chain():
    g = Graph()
    study = _ind(g, "Action_Study", "Runoff Risk Quantification Study", "Action", seq=3)
    risk = _ind(g, "Event_Risk_Confirmed", "Runoff Risk Confirmed", "Event", seq=5)
    chain = CASE["CausalChain_1"]
    g.add((chain, RDF.type, PROETH.CausalChain))
    g.add((chain, PROETH.cause, study))
    g.add((chain, PROETH.effect, risk))
    adj = ec.precedence_graph(g)
    assert ec.reaches(adj, study, risk)
    assert not ec.reaches(adj, risk, study)
    # "risk before study" contradicts both the sequence and the chain.
    problems = ec.allen_relation_problems(g, "time:intervalBefore", risk, study, adj=adj)
    assert any("contradicts" in p for p in problems)
    # The consistent direction is fine.
    assert ec.allen_relation_problems(g, "time:intervalBefore", study, risk, adj=adj) == []
    # The causal chain alone (no sequence literals) still orders the endpoints.
    g2 = Graph()
    s2 = _ind(g2, "Action_Study", "Study", "Action")
    r2 = _ind(g2, "Event_Risk", "Risk", "Event")
    g2.add((chain, RDF.type, PROETH.CausalChain))
    g2.add((chain, PROETH.cause, s2))
    g2.add((chain, PROETH.effect, r2))
    assert any("contradicts" in p for p in ec.allen_relation_problems(
        g2, "time:intervalAfter", s2, r2, adj=ec.precedence_graph(g2)))


def test_allen_endpoint_must_have_occurred():
    g = Graph()
    report = _ind(g, "Action_Report", "Professional Report Completion", "Action", seq=4,
                  description="Engineer L must not issue the report without the study")
    study = _ind(g, "Action_Study", "Runoff Risk Quantification Study", "Action", seq=3)
    problems = ec.allen_relation_problems(g, "time:intervalBefore", study, report)
    assert any("did not occur" in p for p in problems)


# --- state transitions -----------------------------------------------------------

def _prov(g, prefix, prop, s, o):
    emit_edge_prov(g, 8, prefix, prop, s, o, "d", "l", "c")


def test_drop_fluent_reinitiation_and_double_termination():
    g = Graph()
    state = _ind(g, "State_Runoff_Risk", "Drinking Water Source Runoff Risk", "State")
    h1 = _ind(g, "Event_Accumulation", "Stormwater Accumulation Increase", "Event", seq=1)
    h2 = _ind(g, "Event_Nondisclosure", "Nondisclosure at Suspension", "Event", seq=3)
    h3 = _ind(g, "Action_Mitigation", "Safeguard Installation", "Action", seq=5)
    h4 = _ind(g, "Action_Resumption", "Work Resumption", "Action", seq=7)
    for h in (h1, h2):
        g.add((h, CORE.initiates, state))
        _prov(g, ec.FLUENT_PROV_PREFIX, "initiates", h, state)
    for h in (h3, h4):
        g.add((h, CORE.terminates, state))
        _prov(g, ec.FLUENT_PROV_PREFIX, "terminates", h, state)
    # The same start asserted in both vocabularies by one happening counts once.
    g.add((state, CORE.activatedByEvent, h1))
    _prov(g, ec.STATE_PROV_PREFIX, "activatedByEvent", state, h1)

    dropped = ec.drop_fluent_reinitiation(g, 8)
    assert dropped == 2
    assert (h1, CORE.initiates, state) in g
    assert (state, CORE.activatedByEvent, h1) in g
    assert (h2, CORE.initiates, state) not in g          # re-initiation of a holding state
    assert (h3, CORE.terminates, state) in g
    assert (h4, CORE.terminates, state) not in g         # terminated twice
    provs = {str(p) for p in g.subjects(RDF.type, PROV.Derivation)}
    assert not any("Event_Nondisclosure_initiates" in p for p in provs)
    assert not any("Action_Resumption_terminates" in p for p in provs)
    assert any("Event_Accumulation_initiates" in p for p in provs)


def test_drop_fluent_reinitiation_keeps_a_restart_after_an_end():
    g = Graph()
    state = _ind(g, "State_Suspended", "Work Suspension State", "State")
    h1 = _ind(g, "Action_Suspend", "Work Suspension", "Action", seq=1)
    h2 = _ind(g, "Action_Resume", "Work Resumption", "Action", seq=3)
    h3 = _ind(g, "Action_Suspend_Again", "Second Suspension", "Action", seq=5)
    g.add((h1, CORE.initiates, state))
    g.add((h2, CORE.terminates, state))
    g.add((h3, CORE.initiates, state))
    assert ec.drop_fluent_reinitiation(g, 8) == 0
    assert (h3, CORE.initiates, state) in g


def test_activation_precedes_trigger_and_later_citing_happening():
    g = Graph()
    state = _ind(g, "State_Budget", "Client X Budget Constraint", "State")
    setback = _ind(g, "Event_Setback", "Client Financial Setback", "Event", seq=1)
    trigger = _ind(g, "Event_Budget_Cut", "Budget Reduction Notice", "Event", seq=4)
    recovery = _ind(g, "Event_Recovery", "Client Financial Recovery", "Event", seq=6)
    later = _ind(g, "Event_Reaffirmed", "Budget Reaffirmed", "Event", seq=7,
                 description="Client X proceeds under continuing budget limits")
    assert ec.activation_precedes_trigger(g, setback, trigger)
    assert not ec.activation_precedes_trigger(g, trigger, setback)
    assert ec.later_happening_citing_state(g, state, recovery) == later
    # Nothing after the terminator cites the state: no contradiction.
    g.remove((later, PROETH.description, None))
    assert ec.later_happening_citing_state(g, state, recovery) is None


# --- cross-family guards -----------------------------------------------------

def test_drop_activation_defeasibility_conflicts():
    g = Graph()
    s = _ind(g, "State_Conflict", "Client Instruction Conflict State", "State")
    o = _ind(g, "Obl_Faithful", "Faithful Agent Duty", "Obligation")
    o2 = _ind(g, "Obl_Safety", "Public Safety Duty", "Obligation")
    g.add((s, CORE.activatesObligation, o))
    _prov(g, ec.STATE_PROV_PREFIX, "activatesObligation", s, o)
    g.add((o, CORE.defeasibleUnder, s))
    g.add((s, CORE.activatesObligation, o2))
    _prov(g, ec.STATE_PROV_PREFIX, "activatesObligation", s, o2)

    assert ec.drop_activation_defeasibility_conflicts(g, 8) == 1
    assert (s, CORE.activatesObligation, o) not in g
    assert (o, CORE.defeasibleUnder, s) in g
    assert (s, CORE.activatesObligation, o2) in g
    provs = {str(p) for p in g.subjects(RDF.type, PROV.Derivation)}
    assert not any("Obl_Faithful" in p for p in provs)
    assert any("Obl_Safety" in p for p in provs)


def test_drop_scope_postdating_activations():
    g = Graph()
    s = _ind(g, "State_Phase_One", "Preliminary Design Phase State", "State")
    end = _ind(g, "Event_Phase_End", "Preliminary Phase Closed", "Event", seq=2)
    g.add((s, CORE.terminatedByEvent, end))
    study = _ind(g, "Action_Study", "Runoff Risk Quantification Study", "Action", seq=4)
    late = _ind(g, "Obl_Disclose", "Duty to Disclose Runoff Risk", "Obligation")
    g.add((late, PROETH.temporalScope, Literal("After the quantification of the runoff risk")))
    early = _ind(g, "Obl_Competence", "Duty of Competent Practice", "Obligation")
    g.add((early, PROETH.temporalScope, Literal("From the start of the engagement")))
    g.add((s, CORE.activatesObligation, late))
    _prov(g, ec.STATE_PROV_PREFIX, "activatesObligation", s, late)
    g.add((s, CORE.activatesObligation, early))

    assert ec.scope_start_sequence(g, late) == 4
    assert ec.scope_start_sequence(g, early) is None
    assert ec.state_active_end(g, s) == 2
    assert ec.drop_scope_postdating_activations(g, 8) == 1
    assert (s, CORE.activatesObligation, late) not in g
    assert (s, CORE.activatesObligation, early) in g
    assert study is not None
    # A state with no sequenced terminator is never judged.
    s2 = _ind(g, "State_Open", "Ongoing Risk State", "State")
    g.add((s2, CORE.activatesObligation, late))
    assert ec.drop_scope_postdating_activations(g, 8) == 0
