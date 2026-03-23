"""Tests for refactored InteractiveScenarioService (pure data reader)."""
import json
import pytest
from unittest.mock import patch, MagicMock
from app.services.interactive_scenario_service import InteractiveScenarioService


@pytest.fixture
def service():
    return InteractiveScenarioService()


@pytest.fixture
def sample_phase4_data():
    """Phase 4 narrative data with consequence fields populated."""
    return {
        "scenario_seeds": {
            "opening_context": "You are an engineer.",
            "branches": [
                {
                    "branch_id": "branch_0",
                    "decision_maker_label": "Engineer",
                    "question": "Disclose or not?",
                    "context": "A conflict exists.",
                    "decision_point_uri": "dp_0",
                    "decision_maker_uri": "uri:eng",
                    "involved_obligation_uris": ["uri:obl1"],
                    "competing_obligation_labels": ["Duty of Candor", "Loyalty"],
                    "board_rationale": "Candor is paramount.",
                    "options": [
                        {
                            "option_id": "opt_0_0",
                            "label": "Disclose",
                            "description": "",
                            "is_board_choice": True,
                            "action_uris": [],
                            "consequence_narrative": "Disclosure leads to resolution.",
                            "consequence_obligations": ["Duty of Candor"],
                            "consequence_fluent_changes": {"initiated": ["Transparent"], "terminated": []},
                        },
                        {
                            "option_id": "opt_0_1",
                            "label": "Stay silent",
                            "description": "",
                            "is_board_choice": False,
                            "action_uris": [],
                            "consequence_narrative": "Silence risks discovery.",
                            "consequence_obligations": ["Loyalty"],
                            "consequence_fluent_changes": {"initiated": ["Hidden_Conflict"], "terminated": []},
                        },
                    ],
                },
            ],
            "canonical_path": ["Disclose"],
        },
        "narrative_elements": {
            "resolution": {
                "resolution_type": "violation",
                "summary": "Board found a violation.",
                "conclusions": [{"uri": "c1", "text": "Engineer should have disclosed."}],
            },
        },
    }


def test_get_analysis_data_builds_comparison(service, sample_phase4_data):
    """get_analysis_data builds a comparison of user choices vs board choices."""
    mock_session = MagicMock()
    mock_session.case_id = 1
    mock_session.session_uuid = "test-uuid"
    mock_session.choices = [
        MagicMock(
            decision_point_index=0,
            chosen_option_index=1,  # User chose "Stay silent" (not board choice)
            chosen_option_label="Stay silent",
            board_choice_index=0,
            board_choice_label="Disclose",
            matches_board_choice=False,
            time_spent_seconds=30,
        ),
    ]

    curated_dps = [{'original_branch_index': 0, 'question': 'Disclose or not?'}]
    with patch.object(service, '_load_phase4_data', return_value=sample_phase4_data), \
         patch.object(service, '_load_decision_points', return_value=curated_dps):
        analysis = service.get_analysis_data(mock_session)

    assert analysis["total_decisions"] == 1
    assert analysis["matches_with_board"] == 0
    assert len(analysis["decisions"]) == 1

    decision = analysis["decisions"][0]
    assert decision["user_choice"]["label"] == "Stay silent"
    assert decision["user_choice"]["consequence_narrative"] == "Silence risks discovery."
    assert decision["board_choice"]["label"] == "Disclose"
    assert decision["board_choice"]["consequence_narrative"] == "Disclosure leads to resolution."
    assert decision["board_rationale"] == "Candor is paramount."
    assert decision["matched"] is False
    assert len(decision["alternatives"]) == 0  # User chose one, board chose the other, no remaining

    assert analysis["resolution"]["summary"] == "Board found a violation."


# ---------------------------------------------------------------------------
# Neutral framing in get_current_decision
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_neutralized_decision_points():
    """Decision points with neutral_question and neutral_options (reordered)."""
    return [
        {
            "uri": "dp_0",
            "label": "DP-0",
            "decision_maker_label": "Engineer",
            "question": "Did Engineer violate the duty?",
            "context": "A conflict exists.",
            "competing_obligation_labels": ["Duty of Candor", "Loyalty"],
            "neutral_question": "How should the engineer approach disclosure?",
            "neutral_options": [
                {"label": "Maintain confidentiality", "description": "Protects trust.",
                 "original_index": 1},
                {"label": "Disclose proactively", "description": "Ensures transparency.",
                 "original_index": 0},
            ],
            "option_order": [1, 0],
            "options": [
                {"option_id": "opt_0_0", "label": "Disclose", "is_board_choice": True,
                 "consequence_narrative": "Disclosed."},
                {"option_id": "opt_0_1", "label": "Stay silent", "is_board_choice": False,
                 "consequence_narrative": "Stayed silent."},
            ],
        },
    ]


@pytest.fixture
def sample_non_neutral_decision_points():
    """Decision points without neutralization fields."""
    return [
        {
            "uri": "dp_0",
            "label": "DP-0",
            "decision_maker_label": "Engineer",
            "question": "Did Engineer violate the duty?",
            "context": "A conflict exists.",
            "competing_obligation_labels": ["Duty of Candor"],
            "options": [
                {"option_id": "opt_0_0", "label": "Disclose", "is_board_choice": True},
                {"option_id": "opt_0_1", "label": "Stay silent", "is_board_choice": False},
            ],
        },
    ]


def test_get_current_decision_uses_neutral_framing(service, sample_neutralized_decision_points):
    """When neutral_question exists, get_current_decision uses it."""
    mock_session = MagicMock()
    mock_session.case_id = 1
    mock_session.current_decision_index = 0

    phase4_data = {"scenario_seeds": {"opening_context": "Context."}}

    with patch.object(service, '_load_decision_points', return_value=sample_neutralized_decision_points), \
         patch.object(service, '_load_phase4_data', return_value=phase4_data):
        result = service.get_current_decision(mock_session)

    assert result["decision_point"]["question"] == "How should the engineer approach disclosure?"
    assert result["options"][0]["label"] == "Maintain confidentiality"
    assert result["options"][1]["label"] == "Disclose proactively"
    assert result["option_order"] == [1, 0]
    # original_index tracks back to the original options list
    assert result["options"][0]["original_index"] == 1
    assert result["options"][1]["original_index"] == 0


def test_get_current_decision_falls_back_without_neutral(service, sample_non_neutral_decision_points):
    """Without neutral_question, get_current_decision uses original question and options."""
    mock_session = MagicMock()
    mock_session.case_id = 1
    mock_session.current_decision_index = 0

    phase4_data = {"scenario_seeds": {"opening_context": "Context."}}

    with patch.object(service, '_load_decision_points', return_value=sample_non_neutral_decision_points), \
         patch.object(service, '_load_phase4_data', return_value=phase4_data):
        result = service.get_current_decision(mock_session)

    assert result["decision_point"]["question"] == "Did Engineer violate the duty?"
    assert result["options"][0]["label"] == "Disclose"
    assert result["options"][0]["option_id"] == "opt_0_0"
    assert result["option_order"] == [0, 1]


def test_process_choice_remaps_neutral_display_index(service, sample_neutralized_decision_points):
    """process_choice maps display index through neutral_options to original index."""
    mock_session = MagicMock()
    mock_session.id = 1
    mock_session.case_id = 1
    mock_session.current_decision_index = 0

    with patch.object(service, '_load_decision_points', return_value=sample_neutralized_decision_points), \
         patch('app.services.interactive_scenario_service.ScenarioExplorationChoice') as MockChoice, \
         patch('app.services.interactive_scenario_service.db') as mock_db:
        MockChoice.query.filter_by.return_value.first.return_value = None
        result = service.process_choice(mock_session, chosen_display_index=0, time_spent_seconds=15)

    # Display index 0 = "Maintain confidentiality" which has original_index=1
    call_kwargs = MockChoice.call_args[1]
    assert call_kwargs["chosen_option_index"] == 1
    assert call_kwargs["chosen_option_label"] == "Maintain confidentiality"
    assert call_kwargs["matches_board_choice"] is False  # Board chose index 0


def test_process_choice_board_match_via_neutral(service, sample_neutralized_decision_points):
    """Choosing the board option via neutral display position correctly records a match."""
    mock_session = MagicMock()
    mock_session.id = 1
    mock_session.case_id = 1
    mock_session.current_decision_index = 0

    with patch.object(service, '_load_decision_points', return_value=sample_neutralized_decision_points), \
         patch('app.services.interactive_scenario_service.ScenarioExplorationChoice') as MockChoice, \
         patch('app.services.interactive_scenario_service.db') as mock_db:
        MockChoice.query.filter_by.return_value.first.return_value = None
        # Display index 1 = "Disclose proactively" which has original_index=0 (the board choice)
        result = service.process_choice(mock_session, chosen_display_index=1, time_spent_seconds=20)

    call_kwargs = MockChoice.call_args[1]
    assert call_kwargs["chosen_option_index"] == 0
    assert call_kwargs["matches_board_choice"] is True
