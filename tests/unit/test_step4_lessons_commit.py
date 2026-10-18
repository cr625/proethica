"""Case 8 (NSPE 24-1) review, lesson L8: Step-4 analysis literals are
re-emitted with replace semantics, a stored row that differs from the graph
is not stamped committed_at, resolution patterns of one holding are checked
for contradictory conditions, and the provision linker receives the Board
conclusions, the discussion and the agent of each action, rejects links whose
reasoning names another actor, and validates a multi-code sentence once.

Hermetic: rdflib graphs in memory, no DB, no LLM.
"""
from types import SimpleNamespace

from rdflib import Graph, Literal, Namespace, RDF, RDFS
from rdflib.namespace import OWL, SKOS

from app.services.commit.analysis_literals import (
    analysis_individual_uri, expected_literals, stale_analysis_rows, strip_analysis_literals,
)
from app.services.step4_synthesis.rich_analysis import check_resolution_pattern_consistency
from app.services.step4_synthesis.case_synthesis_models import ResolutionPatternAnalysis
from app.services.provision.code_provision_linker import (
    CodeProvisionLinker, build_provision_link_context, reasoning_names_other_actor,
)
from app.services.provision.provision_group_validator import ProvisionGroupValidator, ValidatedMention

CASE = Namespace("http://proethica.org/ontology/case/8#")
CASES = Namespace("http://proethica.org/ontology/cases#")
PROETH = Namespace("http://proethica.org/ontology/intermediate#")


def _precedent_row(citation_type="distinguishing", context="The Board distinguished Case 92-6."):
    return SimpleNamespace(id=1, extraction_type="precedent_case_reference", entity_label="BER Case 92-6",
                           entity_definition=context,
                           rdf_json_ld={"citationType": citation_type, "citationContext": context})


def _graph_with_precedent(citation_type="supporting", context="Old context from a superseded run."):
    g = Graph()
    uri = analysis_individual_uri(8, _precedent_row(), {})
    g.add((uri, RDF.type, OWL.NamedIndividual))
    g.add((uri, RDF.type, CASES.PrecedentCaseReference))
    g.add((uri, RDFS.label, Literal("BER Case 92-6")))
    g.add((uri, CASES.citationType, Literal(citation_type)))
    g.add((uri, SKOS.definition, Literal(context)))
    g.add((uri, CASES.referencesCase, CASE["Other"]))        # an object edge survives the strip
    return g, uri


def test_strip_replaces_only_literals():
    g, uri = _graph_with_precedent()
    removed = strip_analysis_literals(g, uri)
    assert removed == 3                                    # label, citationType, definition
    assert (uri, CASES.referencesCase, CASE["Other"]) in g
    assert (uri, RDF.type, CASES.PrecedentCaseReference) in g
    assert not list(g.objects(uri, CASES.citationType))


def test_stale_row_detected_when_graph_carries_superseded_literals():
    g, uri = _graph_with_precedent(citation_type="supporting")
    stale = stale_analysis_rows(g, 8, [_precedent_row(citation_type="distinguishing")])
    assert len(stale) == 1
    assert "citationType" in stale[0][1] and "distinguishing" in stale[0][1]


def test_row_matching_the_graph_is_not_stale():
    row = _precedent_row()
    g, uri = _graph_with_precedent(citation_type="distinguishing", context=row.entity_definition)
    assert stale_analysis_rows(g, 8, [row]) == []


def test_absent_individual_and_non_analysis_rows():
    g = Graph()
    stale = stale_analysis_rows(g, 8, [_precedent_row(),
                                       SimpleNamespace(id=2, extraction_type="roles", entity_label="Engineer L",
                                                       entity_definition="", rdf_json_ld={})])
    assert len(stale) == 1 and "not in the committed graph" in stale[0][1]


def test_expected_literals_for_decision_points_and_conclusions():
    dp = SimpleNamespace(extraction_type="canonical_decision_point", entity_label="x", entity_definition=None)
    assert expected_literals(dp, {"focus_id": "DP1", "board_resolution": "Held ethical.", "decision_question": "q?"}) == [
        (PROETH.boardResolution, Literal("Held ethical.")), (PROETH.decisionQuestion, Literal("q?"))]
    c = SimpleNamespace(extraction_type="ethical_conclusion", entity_label="Conclusion_1", entity_definition="t")
    assert expected_literals(c, {"conclusionNumber": 1, "conclusionText": "t"}) == [(PROETH.conclusionText, Literal("t"))]
    assert analysis_individual_uri(8, c, {"conclusionNumber": 1}) == CASE["Conclusion_1"]


def test_resolution_condition_consistency_check():
    same = ResolutionPatternAnalysis(conclusion_uri="case-8#Conclusion_1", conclusion_text="t",
                                     resolution_conditions="Holds when the client was notified.")
    contradicting = ResolutionPatternAnalysis(conclusion_uri="case-8#Conclusion_1", conclusion_text="t",
                                              resolution_conditions="Holds when the client was NOT notified.")
    other = ResolutionPatternAnalysis(conclusion_uri="case-8#Conclusion_2", conclusion_text="t",
                                      resolution_conditions="Holds when x.")
    conflicts = check_resolution_pattern_consistency([same, contradicting, other])
    assert len(conflicts) == 1 and "case-8#Conclusion_1" in conflicts[0]
    # Same conditions modulo whitespace/case/final period: no conflict.
    twin = ResolutionPatternAnalysis(conclusion_uri="case-8#Conclusion_1", conclusion_text="t",
                                     resolution_conditions="holds when the client was notified")
    assert check_resolution_pattern_consistency([same, twin]) == []
    # A holding key widens the grouping (generated pattern of the same holding).
    gen = {"conclusion_uri": "case-8#Conclusion_101", "resolution_conditions": "Holds when y."}
    assert check_resolution_pattern_consistency(
        [same, gen], holding_key=lambda u: "case-8#Conclusion_1") != []


def test_provision_link_context_carries_board_conclusions_and_discussion():
    sections = {"conclusion": {"text": "It was ethical for Engineer L to suspend work."},
                "discussion": {"text": "The Board first considered the contract. " * 300},
                "facts": {"text": "Facts."}}
    ctx = build_provision_link_context("Case 8: Retaining Wall", sections, discussion_limit=500)
    assert ctx.startswith("Case 8: Retaining Wall")
    assert "BOARD CONCLUSIONS:\nIt was ethical for Engineer L to suspend work." in ctx
    discussion = ctx.split("DISCUSSION:\n")[1]
    assert len(discussion) <= 500 and discussion.endswith("contract.")
    assert build_provision_link_context("Case 8: T", {}) == "Case 8: T"


def test_action_lines_show_the_agent():
    text = CodeProvisionLinker()._format_entities_for_prompt(
        [{"label": "Work Suspension Request", "definition": "d", "agent": "Engineer L"},
         {"label": "Contract Acceptance", "definition": "d"}], "Actions")
    assert "- Work Suspension Request (agent: Engineer L): d" in text
    assert "- Contract Acceptance: d" in text


def test_links_whose_reasoning_names_another_actor_are_rejected():
    linker = CodeProvisionLinker()
    entities = [{"label": "Work Suspension Request", "agent": "Engineer L"},
                {"label": "Contract Acceptance", "agent": "Client"}]
    parsed = [{"code_provision": "II.1.a", "applies_to": [
        {"entity_label": "Contract Acceptance",
         "reasoning": "Engineer L failed to hold paramount the safety of the public when the contract was accepted."},
        {"entity_label": "Work Suspension Request",
         "reasoning": "Engineer L suspended work to protect the public."},
        {"entity_label": "Contract Acceptance",
         "reasoning": "The Client accepted the contract knowing the risk."},
    ]}]
    out = linker._extract_links_from_parsed(parsed, "action", entities)
    labels = [(l["entity_label"], l["reasoning"][:12]) for l in out["II.1.a"]]
    assert labels == [("Work Suspension Request", "Engineer L s"), ("Contract Acceptance", "The Client a")]


def test_actor_mismatch_rules():
    assert reasoning_names_other_actor("Engineer L did X", "Client", {"Engineer L", "Client"}) == "Engineer L"
    assert reasoning_names_other_actor("Engineer L and the Client agreed", "Client", {"Engineer L", "Client"}) is None
    assert reasoning_names_other_actor("Engineer L did X", "Engineer L (the designer)", {"Engineer L"}) is None
    assert reasoning_names_other_actor("Nobody named", "Client", {"Engineer L", "Client"}) is None
    assert reasoning_names_other_actor("Engineer L did X", "", {"Engineer L"}) is None


def test_multi_code_sentence_is_validated_once():
    v = ProvisionGroupValidator(llm_client=object())
    calls = []

    def _fake_batch(code, text, mentions):
        calls.append((code, [m.excerpt for m in mentions]))
        return [ValidatedMention(section=m.section, excerpt=m.excerpt, citation_text=m.citation_text,
                                 is_relevant=True, confidence=0.9, reasoning="discusses it",
                                 content_type="violation") for m in mentions]
    v._validate_batch = _fake_batch
    sentence = "Engineer L violated II.1.a, II.1.b, III.1.b, II.4 and I.1 by proceeding."

    def mention(code):
        return SimpleNamespace(section="discussion", excerpt=sentence, citation_text=code)
    first = v.validate_group("II.1.a", "text a", [mention("II.1.a")])
    second = v.validate_group("II.1.b", "text b", [mention("II.1.b"),
                                                     SimpleNamespace(section="discussion", excerpt="Another sentence citing II.1.b.",
                                                                     citation_text="II.1.b")])
    assert calls == [("II.1.a", [sentence]), ("II.1.b", ["Another sentence citing II.1.b."])]
    assert len(first) == 1 and len(second) == 2
    reused = next(m for m in second if m.excerpt == sentence)
    assert reused.citation_text == "II.1.b" and reused.content_type == "violation" and reused.confidence == 0.9
