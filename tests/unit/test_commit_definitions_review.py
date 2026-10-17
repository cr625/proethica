"""Review of the commit-definitions lessons (brief 2 of docs/reviews/lessons/cloud_briefs.md).

Four defects found in the merge review, each with the scenario that broke:

1. The working store typed a matched individual to the matched class at any
   confidence (storage-persistence, extraction_graph.individual_type_iri), so
   the confidence floor of lesson L4 never acted on a new row: a 0.75 "matched
   to parent with medium confidence" decision reached the commit with
   rdf_json_ld.types already naming the parent, _matched_class_override saw the
   row as already typed, and both stores named the parent in place of the
   minted specialization. The store now applies the shared match-link
   threshold, so below it the minted class stands in both stores.

2. The participant scaffold read proeth:actionModality, a literal nothing
   writes; the temporal converter stores the model's call as proeth:modality
   and the emitter copies that key. Its fallback marker list also differed from
   edge_coherence.derive_action_modality, the classifier the obligation
   engagement pass applies to the same actions, so one action could be
   performed to one pass and prescribed to the other. The scaffold now reads
   proeth:modality and shares the classifier.

3. verification_gate.match_confidence_of preferred the match_confidence
   column, which the storage writes from the match decision whether or not the
   decision linked the row; a declined decision carrying a confidence read as a
   link, and the gate left such a row unjudged. The recorded decision decides.

4. The relationship needle "duty_toward" routed every duty-toward phrase to
   owesDutyToward, so an overflow entry naming a duty toward a client minted
   the PublicInterest counterparty with the client as its alias. Only the
   property name routes there; the entry stays a staged literal.

Hermetic: no DB, no LLM.
"""
import types

from rdflib import Graph, Literal, Namespace, RDF, RDFS
from rdflib.namespace import SKOS

from app.services.commit.ontserve_commit_service import OntServeCommitService
from app.services.extraction import edge_spec as es
from app.services.extraction.edge_coherence import derive_action_modality
from app.services.extraction.extraction_graph import individual_type_iri, pydantic_to_rdf_data
from app.services.extraction.schemas import MatchDecision, ObligationIndividual
from app.services.extraction.verification_gate import match_confidence_of
from tests.mocks.commit_service_stub import make_stub_commit_service

INT_NS = "http://proethica.org/ontology/intermediate#"
CORE = Namespace("http://proethica.org/ontology/core#")
PROETH = Namespace(INT_NS)
NS = Namespace("http://proethica.org/ontology/case/8#")


# --- 1. the store and the commit apply one link threshold ---------------------

def _decision(confidence, matched="SafetyObligation", matches_existing=True):
    return MatchDecision(matches_existing=matches_existing, matched_uri=f"{INT_NS}{matched}",
                         matched_label=matched, confidence=confidence, reasoning="test")


def test_store_type_follows_the_match_only_at_the_link_threshold(monkeypatch):
    monkeypatch.delenv("PROETHICA_MATCH_LINK_THRESHOLD", raising=False)
    minted = f"{INT_NS}WatershedSafetyObligation"
    # A specialization matched to its parent with medium confidence keeps the minted class in
    # the store, the decision the honoring floor of the commit takes (L4).
    assert individual_type_iri("Watershed Safety Obligation", _decision(0.75)) == minted
    assert individual_type_iri("Watershed Safety Obligation", _decision(0.85)) == f"{INT_NS}SafetyObligation"
    assert individual_type_iri("Watershed Safety Obligation", _decision(0.95)) == f"{INT_NS}SafetyObligation"
    assert individual_type_iri("Watershed Safety Obligation", _decision(0.95, matches_existing=False)) == minted
    monkeypatch.setenv("PROETHICA_MATCH_LINK_THRESHOLD", "0.97")
    assert individual_type_iri("Watershed Safety Obligation", _decision(0.95)) == minted


def test_stored_row_and_commit_name_the_same_class_on_both_sides_of_the_floor(monkeypatch):
    """The storage row as pydantic_to_rdf_data writes it, then the commit's honoring."""
    monkeypatch.delenv("PROETHICA_MATCH_LINK_THRESHOLD", raising=False)
    svc = object.__new__(OntServeCommitService)
    svc._established_core_category = lambda local: "Obligation"

    below = ObligationIndividual(identifier="Engineer L Watershed Safety Duty",
                                 obligation_class="Watershed Safety Obligation",
                                 match_decision=_decision(0.75))
    above = ObligationIndividual(identifier="Engineer L Risk Disclosure Duty",
                                 obligation_class="Risk Disclosure Obligation",
                                 match_decision=_decision(0.9, matched="DisclosureObligation"))
    out = pydantic_to_rdf_data(classes=[], individuals=[below, above], concept_type="obligations",
                               case_id=8, section_type="facts", step_number=2)
    row_below, row_above = out["new_individuals"]

    # Below the floor the store keeps the minted class and the commit honors nothing: one class.
    assert row_below["types"] == [f"{INT_NS}WatershedSafetyObligation"]
    assert svc._matched_class_override(row_below, "Obligation", row_below["types"]) is None
    # At or above it the store already names the matched class and the commit sees it typed.
    assert row_above["types"] == [f"{INT_NS}DisclosureObligation"]
    assert svc._matched_class_override(row_above, "Obligation", row_above["types"]) is None


# --- 2. the scaffold reads the stored modality and shares the classifier ------

def _action(g, local, label, agent, comment=None, **literals):
    a = NS[local]
    g.add((a, RDF.type, CORE.Action))
    g.add((a, RDFS.label, Literal(label)))
    g.add((a, CORE.isPerformedBy, agent))
    if comment:
        # The emitter maps the converter's proeth:description to rdfs:comment.
        g.add((a, RDFS.comment, Literal(comment)))
    for pred, value in literals.items():
        g.add((a, PROETH[pred], Literal(value)))
    return a


def test_scaffold_reads_the_stored_modality_literal():
    g = Graph()
    agent = NS.Agent_Engineer_L
    g.add((agent, RDF.type, CORE.Agent))
    g.add((agent, RDFS.label, Literal("Engineer L")))
    # proeth:modality is the key rdf_converter stores and _add_temporal_fields copies.
    _action(g, "Withdrawal", "Withdrawal from Project", agent,
            comment="Engineer L withdraws from the project.", modality="prescribed")
    _action(g, "Notification", "Risk Notification", agent,
            comment="Engineer L notifies Client X of the increased risk.", modality="performed")
    assert es._action_modality(g, NS.Withdrawal) == "prescribed"
    assert es._action_modality(g, NS.Notification) == "performed"
    es.annotate_participant_agents(g, 8)
    d = str(g.value(agent, SKOS.definition))
    assert "performs Risk Notification;" in d
    assert "is prescribed to perform Withdrawal from Project" in d


def test_scaffold_fallback_agrees_with_the_engagement_classifier():
    g = Graph()
    agent = NS.Agent_Engineer_L
    g.add((agent, RDF.type, CORE.Agent))
    g.add((agent, RDFS.label, Literal("Engineer L")))
    cases = {
        # A prescription phrase the engagement classifier knows and the former scaffold list lacked.
        "Continuation": ("Engineer L is not permitted to continue the work without safeguards.", "", "discussion"),
        # A deontic sentence discovered in the discussion: prescribed to the engagement pass.
        "Report": ("Engineer L should report the risk to the authorities.", "", "discussion"),
        # The same sentence from the facts narrates an occurrence.
        "Facts_Report": ("Engineer L should report the risk to the authorities.", "", "facts"),
        "Notification": ("Engineer L notifies Client X.", "After the studies", "facts"),
        "Refusal": ("Engineer L cannot ethically acquiesce.", "Present, unresolved endpoint", "discussion"),
    }
    for local, (comment, marker, section) in cases.items():
        literals = {"discoveredInSection": section}
        if marker:
            literals["temporalMarker"] = marker
        _action(g, local, local.replace("_", " "), agent, comment=comment, **literals)
    for local, (comment, marker, section) in cases.items():
        assert es._action_modality(g, NS[local]) == derive_action_modality(comment, marker, section), local
    assert es._action_modality(g, NS.Continuation) == "prescribed"
    assert es._action_modality(g, NS.Report) == "prescribed"
    assert es._action_modality(g, NS.Facts_Report) == "performed"
    assert es._action_modality(g, NS.Notification) == "performed"
    assert es._action_modality(g, NS.Refusal) == "prescribed"


# --- 3. the gate's link confidence follows the recorded decision ---------------

def test_gate_link_confidence_follows_the_recorded_decision():
    # The column carries the decision's confidence even when the decision declined the match.
    declined = {"match_decision": {"matches_existing": False, "matched_uri": "Disclosure Obligation",
                                   "confidence": 0.95, "reasoning": "related but distinct"}}
    assert match_confidence_of(declined, 0.95) is None
    assert match_confidence_of(declined) is None
    linked = {"match_decision": {"matches_existing": True, "matched_uri": f"{INT_NS}DisclosureObligation",
                                 "confidence": 0.92}}
    assert match_confidence_of(linked, 0.92) == 0.92
    assert match_confidence_of(linked) == 0.92
    # A row without a recorded decision reads the column as before.
    assert match_confidence_of({}, 0.9) == 0.9
    assert match_confidence_of({"properties": {}}, None) is None


# --- 4. a duty toward a named party is not the public duty ---------------------

def _service(tmp_path, monkeypatch):
    return make_stub_commit_service(
        tmp_path, monkeypatch,
        chain_resolver=lambda local: "Role" if local in ("DesignEngineerRole", "ClientRole") else None,
        header_fields={"title": "Mock Case", "case_number": None, "decade": None})


def _role(label, props, types_=("DesignEngineerRole",)):
    entity = types.SimpleNamespace(
        extraction_type="roles", entity_type="roles", entity_label=label, entity_definition="A role.",
        iao_document_uri=None, iao_document_label=None, cited_by_role=None, available_to_role=None,
        extraction_model=None)
    return entity, {"properties": props, "types": [f"{INT_NS}{t}" for t in types_]}


def test_a_duty_toward_a_client_stays_a_staged_literal(tmp_path, monkeypatch):
    svc = _service(tmp_path, monkeypatch)
    assert svc._rel_property_for("owesDutyToward") == ("owesDutyToward", False)
    assert svc._rel_property_for("owes duty toward") == ("owesDutyToward", False)
    assert svc._rel_property_for("has fiduciary duty toward") == ("relatedTo", False)
    engineer = _role("Engineer L Design Engineer", {
        "actor": ["Engineer L"],
        "additionalRelationships": [
            "{'type': 'has fiduciary duty toward', 'target': 'Client X', 'quote': 'faithful agents or trustees'}"],
    })
    client = _role("Client X Developer", {"actor": ["Client X"]}, types_=("ClientRole",))
    result = svc._commit_individuals_to_case_ontology(8, [engineer, client])
    assert result.get("error") is None, result
    g = Graph()
    g.parse(result["file"], format="turtle")
    facet = NS["Engineer_L_Design_Engineer"]
    assert (facet, PROETH.otherAttribute, Literal("rel:has fiduciary duty toward -> Client X")) in g
    assert not list(g.objects(facet, PROETH.owesDutyToward))
    assert (NS.PublicInterest, RDF.type, PROETH.PublicInterest) not in g
    assert (facet, RDF.type, PROETH.PublicResponsibilityRole) not in g
