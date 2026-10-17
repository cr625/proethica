"""Outcome polarity of case_precedent_features (case 24-1 review, lesson L1).

The board conclusions decide the polarity deterministically; the conclusion-text
regex and the model prompt are fallbacks for cases without typed board
conclusions. Case 24-1 (case 8) carries one no_violation and one violation
board conclusion and is therefore mixed, where the stored row said ethical.
No database: the storage query and the model client are patched.
"""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.services.precedent.case_feature_extractor import (
    CaseFeatureExtractor,
    FEATURE_PROMPT_CONCEPT_TYPE,
    board_conclusion_types_from_rows,
    derive_outcome_from_board_conclusions,
)

CASE_8_CONCLUSION = (
    "It was not unethical for Engineer L to cease work on the project after "
    "Client M refused to accept the revised design. It would not be ethical for "
    "Engineer L to continue working on the project under the directive of Client M."
)


# =============================================================================
# derive_outcome_from_board_conclusions: the four polarity cases
# =============================================================================

class TestDeriveOutcomeFromBoardConclusions:

    def test_all_no_violation_or_compliance_is_ethical(self):
        outcome, confidence, reasoning = derive_outcome_from_board_conclusions(
            ['no_violation', 'compliance', 'no_violation'])
        assert outcome == 'ethical'
        assert confidence > 0.9
        assert 'compliance=1' in reasoning and 'no_violation=2' in reasoning

    def test_all_violation_is_unethical(self):
        outcome, _, _ = derive_outcome_from_board_conclusions(['violation', 'violation'])
        assert outcome == 'unethical'

    def test_both_kinds_is_mixed_case_24_1(self):
        # Case 8: "not unethical ... to cease work" (no_violation) and "would
        # not be ethical ... to continue" (violation).
        outcome, _, reasoning = derive_outcome_from_board_conclusions(['no_violation', 'violation'])
        assert outcome == 'mixed'
        assert 'both polarities' in reasoning

    def test_none_is_unclear(self):
        assert derive_outcome_from_board_conclusions([])[0] == 'unclear'
        assert derive_outcome_from_board_conclusions(None)[0] == 'unclear'

    def test_non_polar_values_only_is_unclear(self):
        outcome, confidence, _ = derive_outcome_from_board_conclusions(['recommendation', 'interpretation'])
        assert outcome == 'unclear'
        assert confidence == 0.0

    def test_single_mixed_value_is_mixed(self):
        # One conclusion bundling verdicts of differing polarities.
        assert derive_outcome_from_board_conclusions(['mixed'])[0] == 'mixed'

    def test_values_are_case_and_whitespace_insensitive(self):
        assert derive_outcome_from_board_conclusions([' Violation '])[0] == 'unethical'


class TestBoardConclusionTypesFromRows:

    def _row(self, conclusion_type, board_type, number):
        return SimpleNamespace(rdf_json_ld={
            'conclusionNumber': number,
            'conclusionType': conclusion_type,
            'boardConclusionType': board_type,
        })

    def test_only_board_explicit_rows_count(self):
        rows = [
            self._row('board_explicit', 'no_violation', 1),
            self._row('board_explicit', 'violation', 2),
            self._row('analytical_extension', 'violation', 101),
            self._row('question_response', 'compliance', 201),
        ]
        assert board_conclusion_types_from_rows(rows) == ['no_violation', 'violation']

    def test_rows_without_a_type_are_skipped(self):
        rows = [self._row('board_explicit', '', 1), SimpleNamespace(rdf_json_ld=None)]
        assert board_conclusion_types_from_rows(rows) == []


# =============================================================================
# The text fallback: "not unethical" is a clearance
# =============================================================================

class TestExtractOutcomeRegex:

    def setup_method(self):
        self.extractor = CaseFeatureExtractor(embedding_service=MagicMock())

    def test_not_unethical_scores_ethical(self):
        outcome, _, reasoning = self.extractor.extract_outcome(
            "It was not unethical for Engineer L to cease work on the project.")
        assert outcome == 'ethical'
        assert 'not unethical statement' in reasoning

    def test_would_not_be_unethical_scores_ethical(self):
        outcome, _, _ = self.extractor.extract_outcome(
            "It would not be unethical for Engineer A to accept the assignment.")
        assert outcome == 'ethical'

    def test_case_24_1_two_part_conclusion_is_mixed(self):
        outcome, _, reasoning = self.extractor.extract_outcome(CASE_8_CONCLUSION)
        assert outcome == 'mixed'
        assert 'not unethical statement' in reasoning
        assert 'was not ethical statement' in reasoning

    def test_bare_unethical_still_scores_unethical(self):
        outcome, _, _ = self.extractor.extract_outcome(
            "It was unethical for Engineer A to sign the plans.")
        assert outcome == 'unethical'


# =============================================================================
# extract_outcome_for_case: board conclusions first, text second
# =============================================================================

class TestExtractOutcomeForCase:

    def setup_method(self):
        self.extractor = CaseFeatureExtractor(embedding_service=MagicMock())

    def test_board_conclusions_win_over_the_text(self):
        with patch('app.services.precedent.case_feature_extractor.board_outcome_for_case',
                   return_value=('mixed', 0.95, 'Board conclusions of both polarities')):
            outcome, confidence, reasoning = self.extractor.extract_outcome_for_case(
                8, "It was ethical for Engineer L to cease work.")
        assert (outcome, confidence) == ('mixed', 0.95)
        assert 'Board conclusions' in reasoning

    def test_text_fallback_without_board_conclusions(self):
        with patch('app.services.precedent.case_feature_extractor.board_outcome_for_case',
                   return_value=None):
            outcome, _, _ = self.extractor.extract_outcome_for_case(8, CASE_8_CONCLUSION)
        assert outcome == 'mixed'

    def test_storage_failure_falls_back_to_the_text(self):
        with patch('app.services.precedent.case_feature_extractor.board_outcome_for_case',
                   side_effect=RuntimeError('no app context')):
            outcome, _, _ = self.extractor.extract_outcome_for_case(
                8, "It was unethical for Engineer A to sign the plans.")
        assert outcome == 'unethical'


# =============================================================================
# The model path: fallback only, with its prompt and response stored
# =============================================================================

class TestLlmExtractFeaturesProvenance:

    def _run(self, model_json, board_outcome):
        extractor = CaseFeatureExtractor(embedding_service=MagicMock())
        llm = MagicMock()
        llm.complete.return_value = SimpleNamespace(text=json.dumps(model_json))
        llm_manager = MagicMock(return_value=llm)
        prompt_model = MagicMock()
        with patch('app.services.llm.manager.LLMManager', llm_manager), \
             patch('app.services.precedent.case_feature_extractor.board_outcome_for_case',
                   return_value=board_outcome), \
             patch('app.models.ExtractionPrompt', prompt_model):
            result = extractor.llm_extract_features(
                "Engineer L raised the stormwater risk.", CASE_8_CONCLUSION, case_id=8)
        return result, llm, prompt_model

    def test_board_conclusions_override_the_model_outcome(self):
        model_json = {
            'provisions_cited': ['II.1.a', 'I.1'],
            'outcome_type': 'ethical',
            'outcome_reasoning': 'The Board found the conduct ethical.',
            'subject_tags': [],
        }
        result, _, _ = self._run(model_json, ('mixed', 0.95, 'Board conclusions of both polarities'))
        assert result['outcome_type'] == 'mixed'
        assert result['outcome_reasoning'] == 'Board conclusions of both polarities'

    def test_model_outcome_stands_without_board_conclusions(self):
        model_json = {'provisions_cited': [], 'outcome_type': 'ethical',
                      'outcome_reasoning': 'r', 'subject_tags': []}
        result, _, _ = self._run(model_json, None)
        assert result['outcome_type'] == 'ethical'

    def test_prompt_and_response_are_stored_as_an_extraction_prompt(self):
        model_json = {'provisions_cited': ['II.1.a', 'iii.4', 'I.1.', 'Canon 15'],
                      'outcome_type': 'unethical', 'outcome_reasoning': 'r', 'subject_tags': []}
        result, llm, prompt_model = self._run(model_json, None)

        prompt_model.save_prompt.assert_called_once()
        kwargs = prompt_model.save_prompt.call_args.kwargs
        assert kwargs['case_id'] == 8
        assert kwargs['concept_type'] == FEATURE_PROMPT_CONCEPT_TYPE
        assert kwargs['step_number'] == 0
        assert kwargs['raw_response'] == json.dumps(model_json)
        # The stored prompt carries the system prompt and the user message.
        sent_system = llm.complete.call_args.kwargs['system']
        sent_user = llm.complete.call_args.kwargs['messages'][0]['content']
        assert sent_system in kwargs['prompt_text']
        assert sent_user in kwargs['prompt_text']
        assert kwargs['results_summary'] == result
        # The validator accepts either letter case and stores the canonical form.
        assert result['provisions_cited'] == ['I.1', 'II.1.A', 'III.4']

    def test_no_prompt_row_without_a_case_id(self):
        extractor = CaseFeatureExtractor(embedding_service=MagicMock())
        llm = MagicMock()
        llm.complete.return_value = SimpleNamespace(text=json.dumps(
            {'provisions_cited': [], 'outcome_type': 'ethical', 'outcome_reasoning': 'r', 'subject_tags': []}))
        prompt_model = MagicMock()
        with patch('app.services.llm.manager.LLMManager', MagicMock(return_value=llm)), \
             patch('app.models.ExtractionPrompt', prompt_model):
            extractor.llm_extract_features("discussion", "conclusion")
        prompt_model.save_prompt.assert_not_called()
