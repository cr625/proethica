"""Case 8 (NSPE 24-1) review, lesson L5: prompt assembly separates the Board's
record from Step-4 generated analysis, grounds the generated questions in the
facts, and validates every label the analysis names against the extracted
entities.

- DP-refine, resolution-pattern and transformation prompts: generated
  conclusions and questions are tagged and leave the Board headings.
- Emergence prompt receives the facts text.
- Implicit questions need a grounding_fact quote found in the facts.
- determinative_principles and the causal-link references are validated
  against the extracted labels (closed lists).
- Analytical-extension sentences that speak for the Board need a quoted
  discussion span.

Hermetic: sidecar templates rendered directly (no DB), LLM calls stubbed.
"""
import json
from types import SimpleNamespace
from unittest.mock import patch

import jinja2
import pytest

from app.utils.seed_step4_prompts import SIDECAR_DIR, parse_sidecar
from app.services.decision_point_synthesizer import DecisionPointSynthesizer, QCAlignmentScore
from app.services.step4_synthesis.case_synthesis_models import EntityFoundation, EntitySummary
from app.services.step4_synthesis.rich_analysis import (
    RichAnalyzer, validate_against_extracted, extracted_normative_labels,
)
from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer, quote_appears_in
from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer, attributes_to_board
from app.services.case_analysis.transformation_classifier import (
    TransformationClassifier, truncate_at_boundary,
)


def _sidecar_template(concept_type):
    _, body = parse_sidecar(SIDECAR_DIR / f'{concept_type}.md')

    class _T:
        def render(self, **variables):
            return jinja2.Template(body).render(**variables)
    return _T()


def _foundation():
    f = EntityFoundation(case_id=None)
    f.roles = [EntitySummary(uri="case-8#Engineer_L", label="Engineer L", entity_type="roles")]
    f.principles = [EntitySummary(uri="case-8#Public_Welfare", label="Public Welfare", entity_type="principles")]
    f.obligations = [EntitySummary(uri="case-8#Public_Safety_Duty", label="Public Safety Duty", entity_type="obligations"),
                     EntitySummary(uri="case-8#Faithful_Agent_Duty", label="Faithful Agent Duty", entity_type="obligations")]
    f.actions = [EntitySummary(uri="case-8#Work_Suspension_Request", label="Work Suspension Request", entity_type="actions")]
    return f


BOARD_Q = {"uri": "case-8#Question_1", "label": "Question_1", "text": "Was suspension ethical?", "number": 1}
GEN_Q = {"uri": "case-8#Question_103", "label": "Question_103", "text": "Should monitoring continue?",
         "number": 103, "question_type": "implicit"}
BOARD_C = {"uri": "case-8#Conclusion_1", "label": "Conclusion_1", "text": "Suspension was ethical.", "number": 1}
GEN_C = {"uri": "case-8#Conclusion_101", "label": "Conclusion_101", "text": "A passive-awareness duty follows.",
         "number": 101, "conclusion_type": "analytical_extension"}


# ---------------------------------------------------------------------------
# DP-refine prompt
# ---------------------------------------------------------------------------

def test_refine_prompt_puts_generated_records_under_their_own_heading():
    s = DecisionPointSynthesizer()
    cand = SimpleNamespace(focus_id="DP1", description="d", decision_question="q?",
                           grounding=SimpleNamespace(role_label="Engineer L", role_uri="case-8#Engineer_L",
                                                     obligation_label="Public Safety Duty",
                                                     obligation_uri="case-8#Public_Safety_Duty"),
                           options=[SimpleNamespace(description="Suspend", is_extracted_action=True)])
    with patch("app.services.decision_point_synthesizer.strategies.get_step4_template", _sidecar_template):
        prompt = s._build_refinement_prompt(8, [(cand, QCAlignmentScore("DP1", 0.5))],
                                            [BOARD_Q, GEN_Q], [BOARD_C, GEN_C], [], [])
    board_q_section = prompt.split("## BOARD'S QUESTIONS")[1].split("## BOARD'S CONCLUSIONS")[0]
    board_c_section = prompt.split("## BOARD'S CONCLUSIONS")[1].split("## GENERATED ANALYSIS")[0]
    generated = prompt.split("## GENERATED ANALYSIS")[1].split("## TASK")[0]
    assert "Q0:" in board_q_section and "Question_103" not in board_q_section
    assert "C0:" in board_c_section and "passive-awareness" not in board_c_section
    assert "Q1: [GENERATED implicit question, not asked by the Board]" in generated
    assert "C1: [GENERATED analytical_extension conclusion, not a Board determination]" in generated
    assert "analytical extension" in generated.lower()


def test_refine_prompt_without_generated_records_has_no_generated_block():
    s = DecisionPointSynthesizer()
    with patch("app.services.decision_point_synthesizer.strategies.get_step4_template", _sidecar_template):
        prompt = s._build_refinement_prompt(8, [], [BOARD_Q], [BOARD_C], [], [])
    assert "GENERATED ANALYSIS" not in prompt


# ---------------------------------------------------------------------------
# Resolution-pattern prompt and parser
# ---------------------------------------------------------------------------

def _run_resolution_batch(response_json, conclusions):
    analyzer = RichAnalyzer(llm_client=object())
    captured = {}

    def _fake_completion(client, model, max_tokens, prompt, temperature):
        captured['prompt'] = prompt
        return json.dumps(response_json)

    with patch("app.services.step4_synthesis.rich_analysis.get_step4_template", _sidecar_template), \
         patch("app.services.step4_synthesis.rich_analysis.streaming_completion", _fake_completion):
        patterns = analyzer._analyze_resolution_batch(conclusions, 0, conclusions, [BOARD_Q, GEN_Q],
                                                      [], _foundation(), [])
    return captured['prompt'], patterns


def test_resolution_prompt_separates_board_and_generated_conclusions():
    prompt, _ = _run_resolution_batch([], [BOARD_C, GEN_C])
    board_block = prompt.split("## BOARD CONCLUSIONS")[1].split("## GENERATED ANALYTICAL CONCLUSIONS")[0]
    generated_block = prompt.split("## GENERATED ANALYTICAL CONCLUSIONS")[1].split("## ETHICAL QUESTIONS")[0]
    assert "C1. Conclusion_1" in board_block and "passive-awareness" not in board_block
    assert "C2. [GENERATED analytical_extension, not a Board determination] Conclusion_101" in generated_block
    assert 'never\n"the Board"' in generated_block or 'never "the Board"' in generated_block.replace("\n", " ")
    closed = prompt.split("PRINCIPLES AND OBLIGATIONS THE ANALYSIS MAY NAME")[1]
    assert "- Public Welfare" in closed and "- Public Safety Duty" in closed


def test_resolution_prompt_board_only_batch_has_no_generated_block():
    prompt, _ = _run_resolution_batch([], [BOARD_C])
    assert "GENERATED ANALYTICAL CONCLUSIONS" not in prompt


def test_determinative_principles_validated_against_extracted_labels():
    response = [{"conclusion_index": 1, "answers_questions": [1],
                 "determinative_principles": ["Public Welfare", "Opinions Founded on Facts Obligation"],
                 "determinative_facts": ["f"], "cited_provisions": [], "weighing_process": "w",
                 "resolution_conditions": "Holds when X.", "resolution_narrative": "n", "confidence": 0.8}]
    _, patterns = _run_resolution_batch(response, [BOARD_C])
    assert patterns[0].determinative_principles == ["Public Welfare"]


def test_extracted_normative_labels_closed_list():
    assert extracted_normative_labels(_foundation().to_entity_dict()) == [
        "Public Welfare", "Public Safety Duty", "Faithful Agent Duty"]


# ---------------------------------------------------------------------------
# Causal-link references and committed-edge display
# ---------------------------------------------------------------------------

def test_causal_link_references_outside_the_extracted_labels_are_dropped():
    analyzer = RichAnalyzer(llm_client=object())
    f = _foundation()
    committed = {"work suspension request": {"fulfills": ["Public Safety Duty", "Opinions Founded on Facts Obligation"],
                                             "violates": ["Faithful Agent Duty"], "guided": ["Not Extracted Principle"],
                                             "agent": "Engineer L"}}
    links = analyzer._build_grounded_links(
        [{"action_index": 1, "reasoning": "r", "confidence": 0.9}], f.actions, committed, f.to_entity_dict())
    assert links[0].fulfills_obligations == ["case-8#Public_Safety_Duty"]
    assert links[0].violates_obligations == ["case-8#Faithful_Agent_Duty"]
    assert links[0].guided_by_principles == []
    assert links[0].reasoning == "r"


def test_committed_edges_by_label_filters_free_text_tags():
    analyzer = RichAnalyzer(llm_client=object())
    analyzer._committed_action_edges = lambda case_id: {
        "work suspension request": {"fulfills": ["Public Safety Duty", "Opinions Founded on Facts Obligation"],
                                    "violates": [], "guided": ["Public Welfare"], "agent": ""}}
    edges = analyzer._committed_edges_by_label(8, _foundation().to_entity_dict())
    assert edges == {"work suspension request": [("fulfills", ["Public Safety Duty"]),
                                                 ("guided by", ["Public Welfare"])]}
    # Without an entity_dict the former behaviour (every tag shown) is kept.
    assert analyzer._committed_edges_by_label(8)["work suspension request"][0][1] == [
        "Public Safety Duty", "Opinions Founded on Facts Obligation"]


def test_validate_against_extracted_keeps_only_resolvable_labels():
    assert validate_against_extracted(["public safety duty", "Nope", ""], _foundation().to_entity_dict()) == \
        ["public safety duty"]


# ---------------------------------------------------------------------------
# Emergence prompt: facts text
# ---------------------------------------------------------------------------

def test_emergence_prompt_carries_the_facts_text():
    analyzer = RichAnalyzer(llm_client=object())
    captured = {}

    def _fake_completion(client, model, max_tokens, prompt, temperature):
        captured['prompt'] = prompt
        return json.dumps([{"question_index": 1, "data_events": [], "data_actions": ["Work Suspension Request"],
                            "involves_roles": ["Engineer L"], "competing_warrants": [],
                            "emergence_narrative": "n", "confidence": 0.7}])

    facts = "Engineer L accepted the contract. Later Engineer L requested a suspension of the work."
    with patch("app.services.step4_synthesis.rich_analysis.get_step4_template", _sidecar_template), \
         patch("app.services.step4_synthesis.rich_analysis.streaming_completion", _fake_completion):
        out = analyzer.analyze_question_batch([BOARD_Q], _foundation(), [], 0, facts_text=facts)
    assert "## CASE FACTS" in captured['prompt'] and facts in captured['prompt']
    assert "in the order the CASE FACTS give them" in captured['prompt']
    assert out[0].data_actions == ["case-8#Work_Suspension_Request"]


def test_emergence_prompt_without_facts_omits_the_block():
    analyzer = RichAnalyzer(llm_client=object())
    captured = {}

    def _fake_completion(client, model, max_tokens, prompt, temperature):
        captured['prompt'] = prompt
        return "[]"
    with patch("app.services.step4_synthesis.rich_analysis.get_step4_template", _sidecar_template), \
         patch("app.services.step4_synthesis.rich_analysis.streaming_completion", _fake_completion):
        analyzer.analyze_question_batch([BOARD_Q], _foundation(), [], 0, facts_text='')
    assert "## CASE FACTS" not in captured['prompt']


# ---------------------------------------------------------------------------
# Implicit questions: grounding_fact
# ---------------------------------------------------------------------------

FACTS = ("Engineer L was retained by Client to design the retaining wall. Client declined the "
         "recommended inspection and accepted the contract after Engineer L's refusal.")


def test_implicit_questions_need_a_grounding_quote_found_in_the_facts():
    qa = QuestionAnalyzer()
    response = json.dumps({"implicit": [
        {"question_text": "Should Engineer L have insisted on the inspection?",
         "grounding_fact": "Client declined the recommended inspection"},
        {"question_text": "Should Engineer L have refused the unpaid monitoring?",
         "grounding_fact": "Client asked for unpaid monitoring"},        # not in the facts
        {"question_text": "Was the design adequate?"},                   # no quote
    ], "principle_tension": [
        {"question_text": "How to balance loyalty and safety?", "mentioned_entities": {}},
    ]})
    out = qa._parse_analytical_questions_response(response, {}, case_facts=FACTS)
    assert [q.question_text for q in out['implicit']] == ["Should Engineer L have insisted on the inspection?"]
    assert out['implicit'][0].question_number == 101
    assert out['implicit'][0].grounding_fact == "Client declined the recommended inspection"
    assert len(out['principle_tension']) == 1 and out['principle_tension'][0].grounding_fact is None
    assert qa._question_to_dict(out['implicit'][0])['grounding_fact'] == "Client declined the recommended inspection"


def test_implicit_question_quote_only_required_when_facts_unavailable():
    qa = QuestionAnalyzer()
    response = json.dumps({"implicit": [
        {"question_text": "A?", "grounding_fact": "anything"},
        {"question_text": "B?"},
    ]})
    out = qa._parse_analytical_questions_response(response, {}, case_facts=None)
    assert [q.question_text for q in out['implicit']] == ["A?"]


def test_quote_matching_tolerates_whitespace_and_case():
    assert quote_appears_in("client DECLINED   the recommended inspection", FACTS)
    assert not quote_appears_in("", FACTS)


def test_implicit_block_in_prompt_asks_for_grounding_fact():
    from tests.extraction import step4_qc_fixtures as fx
    variables = QuestionAnalyzer()._analytical_prompt_variables(**fx.q_analytical_variants()['batch1'])
    implicit_block = variables['categories'][0]
    assert "grounding_fact" in implicit_block['block'] and "grounding_fact" in implicit_block['example']


# ---------------------------------------------------------------------------
# Analytical extensions: Board attribution needs a quoted span
# ---------------------------------------------------------------------------

DISCUSSION = ("The Board has long held that an engineer's paramount duty is to the public. "
              "The Board noted that Engineer L notified the client of the risk promptly.")


def test_board_attributed_extension_needs_a_quote_from_the_discussion():
    ca = ConclusionAnalyzer()
    response = json.dumps({"analytical_extension": [
        {"conclusion_text": "The Board indicated that unpaid monitoring is required."},          # no quote
        {"conclusion_text": "The Board noted the prompt notification, which also satisfies II.1.a.",
         "discussion_quote": "The Board noted that Engineer L notified the client of the risk promptly."},
        {"conclusion_text": "The Board reasons from the contract alone.",
         "discussion_quote": "a span the discussion does not contain"},
        {"conclusion_text": "Beyond the holding, the notification also protected the contractor."},
    ]})
    out = ca._parse_analytical_conclusions_response(response, None, board_source=DISCUSSION)
    texts = [c.conclusion_text for c in out['analytical_extension']]
    assert texts == ["The Board noted the prompt notification, which also satisfies II.1.a.",
                     "Beyond the holding, the notification also protected the contractor."]
    assert [c.conclusion_number for c in out['analytical_extension']] == [101, 102]
    assert out['analytical_extension'][0].discussion_quote.startswith("The Board noted")
    assert ca._conclusion_to_dict(out['analytical_extension'][0])['discussion_quote']


def test_attribution_check_applies_to_the_opening_words_only():
    assert attributes_to_board("The Board reasons that ...")
    assert attributes_to_board('"The board" concluded')
    assert not attributes_to_board("Beyond the Board's finding, ...")


def test_extension_block_in_prompt_asks_for_discussion_quote():
    from tests.extraction import step4_qc_fixtures as fx
    variables = ConclusionAnalyzer()._analytical_prompt_variables(**fx.c_analytical_variants()['single'])
    block = variables['categories'][0]
    assert "discussion_quote" in block['block'] and "discussion_quote" in block['example']


# ---------------------------------------------------------------------------
# Transformation prompt
# ---------------------------------------------------------------------------

def _classify_prompt(questions, conclusions, facts):
    classifier = TransformationClassifier(llm_client=object())

    def _no_llm(*args, **kwargs):
        raise RuntimeError("no LLM in tests")
    import app.utils.llm_utils as llm_utils
    import app.services.step4_synthesis.template_loader as template_loader
    with patch.object(llm_utils, 'streaming_completion', _no_llm), \
         patch.object(template_loader, 'get_step4_template', _sidecar_template), \
         pytest.raises(RuntimeError):
        classifier._llm_classification(8, questions, conclusions, [], case_title="Case 8",
                                       case_facts=facts, all_entities={})
    return classifier.last_prompt


def test_transformation_prompt_tags_generated_records_and_keeps_board_headings_clean():
    questions = [{"question_number": 1, "question_text": "Was suspension ethical?", "question_type": "board_explicit"},
                 {"question_number": 103, "question_text": "Should monitoring continue?", "question_type": "implicit"}]
    conclusions = [{"conclusion_number": 1, "conclusion_text": "Suspension was ethical.", "conclusion_type": "board_explicit"},
                   {"conclusion_number": 101, "conclusion_text": "A passive-awareness duty follows.",
                    "conclusion_type": "analytical_extension"}]
    prompt = _classify_prompt(questions, conclusions, "Short facts.")
    board_q = prompt.split("ETHICAL QUESTIONS POSED TO THE BOARD:")[1].split("BOARD'S CONCLUSIONS:")[0]
    board_c = prompt.split("BOARD'S CONCLUSIONS:")[1].split("GENERATED ANALYSIS")[0]
    generated = prompt.split("GENERATED ANALYSIS")[1].split("ANALYSIS TASK:")[0]
    assert "Q1: Was suspension ethical?" in board_q and "monitoring" not in board_q
    assert "C1: Suspension was ethical." in board_c and "passive-awareness" not in board_c
    assert "Q2: [GENERATED implicit question, not posed to the Board]" in generated
    assert "C2: [GENERATED analytical_extension conclusion, not a Board determination]" in generated
    assert "context only" in generated


def test_transformation_prompt_facts_are_cut_at_a_boundary():
    facts = ("The retaining wall was designed in spring. " * 60).strip()   # > 2000 chars
    prompt = _classify_prompt([], [], facts)
    facts_block = prompt.split("CASE FACTS:\n")[1].split("\n\n")[0]
    assert len(facts_block) <= 2000
    assert facts_block.endswith("spring.")
    assert "GENERATED ANALYSIS" not in prompt


def test_truncate_at_boundary_rules():
    assert truncate_at_boundary("short", 10) == "short"
    assert truncate_at_boundary("one two three four", 9) == "one two"
    assert truncate_at_boundary("First sentence. Second sentence here.", 25) == "First sentence."
    assert truncate_at_boundary("", 10) == ""
