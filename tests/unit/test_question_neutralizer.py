"""Tests for question_neutralizer module."""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.scenario_generation.question_neutralizer import (
    neutralize_branches,
    apply_neutralization_to_seeds,
    _parse_neutralization_response,
    _fallback_neutralization,
    _build_neutralization_prompt,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _branch(question="Did Engineer A violate the duty of candor?",
            options=None, obligations=None):
    """Build a minimal branch dict."""
    if options is None:
        options = [
            {"label": "Yes, violated", "description": "Clear violation.", "is_board_choice": True},
            {"label": "No violation", "description": "No breach.", "is_board_choice": False},
        ]
    return {
        "decision_maker_label": "Engineer A",
        "question": question,
        "options": options,
        "competing_obligation_labels": obligations or ["Duty of Candor"],
    }


# ---------------------------------------------------------------------------
# _parse_neutralization_response
# ---------------------------------------------------------------------------

class TestParseNeutralizationResponse:
    def test_valid_json(self):
        response = json.dumps({
            "neutral_question": "How should Engineer A approach disclosure?",
            "options": [
                {"original_index": 1, "label": "Maintain confidentiality",
                 "description": "Protects client trust."},
                {"original_index": 0, "label": "Disclose proactively",
                 "description": "Ensures transparency."},
            ]
        })
        branch = _branch()
        result = _parse_neutralization_response(response, branch)

        assert result["neutral_question"] == "How should Engineer A approach disclosure?"
        assert len(result["neutral_options"]) == 2
        assert result["option_order"] == [1, 0]
        assert result["neutral_options"][0]["original_index"] == 1
        assert result["neutral_options"][1]["original_index"] == 0

    def test_json_embedded_in_text(self):
        response = 'Here is the result:\n```json\n' + json.dumps({
            "neutral_question": "How should they proceed?",
            "options": [
                {"original_index": 0, "label": "Option A", "description": "Desc A."},
                {"original_index": 1, "label": "Option B", "description": "Desc B."},
            ]
        }) + '\n```'
        result = _parse_neutralization_response(response, _branch())
        assert result["neutral_question"] == "How should they proceed?"

    def test_no_json_falls_back(self):
        result = _parse_neutralization_response("No JSON here at all.", _branch())
        # Fallback should still produce a result
        assert "neutral_question" in result
        assert len(result["neutral_options"]) == 2

    def test_invalid_json_falls_back(self):
        result = _parse_neutralization_response("{bad json!!", _branch())
        assert "neutral_question" in result

    def test_missing_question_falls_back(self):
        response = json.dumps({
            "neutral_question": "",
            "options": [
                {"original_index": 0, "label": "A", "description": "D."},
                {"original_index": 1, "label": "B", "description": "D."},
            ]
        })
        result = _parse_neutralization_response(response, _branch())
        # Empty question triggers fallback
        assert "neutral_question" in result

    def test_too_few_options_falls_back(self):
        response = json.dumps({
            "neutral_question": "How should they proceed?",
            "options": [{"original_index": 0, "label": "Only one", "description": "D."}]
        })
        result = _parse_neutralization_response(response, _branch())
        # Fewer than 2 options triggers fallback
        assert len(result["neutral_options"]) == 2


# ---------------------------------------------------------------------------
# _fallback_neutralization
# ---------------------------------------------------------------------------

class TestFallbackNeutralization:
    def test_strips_did_prefix(self):
        branch = _branch(question="Did Engineer A violate the code?")
        result = _fallback_neutralization(branch)
        assert result["neutral_question"].startswith("How should ")

    def test_strips_does_prefix(self):
        branch = _branch(question="Does the firm have an obligation?")
        result = _fallback_neutralization(branch)
        assert result["neutral_question"].startswith("How should ")

    def test_preserves_non_evaluative_question(self):
        branch = _branch(question="How should the engineer proceed?")
        result = _fallback_neutralization(branch)
        assert result["neutral_question"] == "How should the engineer proceed?"

    def test_option_count_preserved(self):
        branch = _branch(options=[
            {"label": "A", "is_board_choice": True},
            {"label": "B", "is_board_choice": False},
            {"label": "C", "is_board_choice": False},
        ])
        result = _fallback_neutralization(branch)
        assert len(result["neutral_options"]) == 3
        assert len(result["option_order"]) == 3

    def test_option_order_is_permutation(self):
        branch = _branch()
        result = _fallback_neutralization(branch)
        assert sorted(result["option_order"]) == [0, 1]

    def test_original_indices_match_order(self):
        branch = _branch()
        result = _fallback_neutralization(branch)
        for i, nopt in enumerate(result["neutral_options"]):
            assert nopt["original_index"] == result["option_order"][i]


# ---------------------------------------------------------------------------
# apply_neutralization_to_seeds
# ---------------------------------------------------------------------------

class TestApplyNeutralizationToSeeds:
    def test_adds_fields_to_branches(self):
        seeds = {
            "branches": [
                {"question": "Original Q1", "options": [{"label": "A"}, {"label": "B"}]},
                {"question": "Original Q2", "options": [{"label": "C"}, {"label": "D"}]},
            ]
        }
        neutralizations = [
            {"neutral_question": "Neutral Q1", "neutral_options": [{"label": "NA"}], "option_order": [1, 0]},
            {"neutral_question": "Neutral Q2", "neutral_options": [{"label": "NC"}], "option_order": [0, 1]},
        ]
        result = apply_neutralization_to_seeds(seeds, neutralizations)
        assert result["branches"][0]["neutral_question"] == "Neutral Q1"
        assert result["branches"][1]["neutral_question"] == "Neutral Q2"
        assert result["branches"][0]["option_order"] == [1, 0]
        # Original fields preserved
        assert result["branches"][0]["question"] == "Original Q1"

    def test_fewer_neutralizations_than_branches(self):
        seeds = {
            "branches": [
                {"question": "Q1", "options": []},
                {"question": "Q2", "options": []},
                {"question": "Q3", "options": []},
            ]
        }
        neutralizations = [
            {"neutral_question": "NQ1", "neutral_options": [], "option_order": []},
        ]
        result = apply_neutralization_to_seeds(seeds, neutralizations)
        assert "neutral_question" in result["branches"][0]
        assert "neutral_question" not in result["branches"][2]

    def test_empty_branches(self):
        seeds = {"branches": []}
        result = apply_neutralization_to_seeds(seeds, [])
        assert result["branches"] == []


# ---------------------------------------------------------------------------
# _build_neutralization_prompt
# ---------------------------------------------------------------------------

class TestBuildNeutralizationPrompt:
    def test_includes_question_and_options(self):
        branch = _branch()
        prompt = _build_neutralization_prompt(branch, "An ethics case.")
        assert "Did Engineer A violate" in prompt
        assert "Yes, violated" in prompt
        assert "No violation" in prompt

    def test_marks_board_choice(self):
        branch = _branch()
        prompt = _build_neutralization_prompt(branch, "")
        assert "BOARD'S ACTUAL CHOICE" in prompt

    def test_includes_obligations(self):
        branch = _branch(obligations=["Duty of Candor", "Loyalty"])
        prompt = _build_neutralization_prompt(branch, "")
        assert "Duty of Candor" in prompt
        assert "Loyalty" in prompt


# ---------------------------------------------------------------------------
# neutralize_branches (integration with mocked LLM)
# ---------------------------------------------------------------------------

class TestNeutralizeBranches:
    @patch("app.services.scenario_generation.question_neutralizer.get_llm_client")
    def test_calls_llm_per_branch(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "neutral_question": "How should they proceed?",
            "options": [
                {"original_index": 0, "label": "Act A", "description": "D."},
                {"original_index": 1, "label": "Act B", "description": "D."},
            ]
        }))]
        mock_client.messages.create.return_value = mock_response

        branches = [_branch(), _branch()]
        results = neutralize_branches(branches, "context")

        assert len(results) == 2
        assert mock_client.messages.create.call_count == 2
        assert results[0]["neutral_question"] == "How should they proceed?"

    @patch("app.services.scenario_generation.question_neutralizer.get_llm_client")
    def test_fallback_on_llm_error(self, mock_get_client):
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        mock_client.messages.create.side_effect = RuntimeError("API down")

        results = neutralize_branches([_branch()], "context")
        assert len(results) == 1
        assert "neutral_question" in results[0]
