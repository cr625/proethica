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

    with patch.object(service, '_load_phase4_data', return_value=sample_phase4_data):
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
