"""Tests for consequence-extended dataclasses."""
import pytest
from app.services.narrative.scenario_seed_generator import (
    ScenarioOption, ScenarioBranch, ScenarioSeeds
)


def test_scenario_option_consequence_fields_default_empty():
    """New consequence fields default to empty values."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test Option",
        description="A test",
    )
    assert opt.consequence_narrative == ""
    assert opt.consequence_obligations == []
    assert opt.consequence_fluent_changes == {}


def test_scenario_option_consequence_fields_populated():
    """Consequence fields serialize correctly when populated."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Resign First",
        description="Leave before signing",
        action_uris=["case-1#Resign"],
        is_board_choice=True,
        consequence_narrative="By resigning first, the engineer avoids conflict.",
        consequence_obligations=["Duty of Loyalty"],
        consequence_fluent_changes={
            "initiated": ["Clean_Separation"],
            "terminated": ["Active_Employment"]
        },
    )
    from dataclasses import asdict
    d = asdict(opt)
    assert d["consequence_narrative"] == "By resigning first, the engineer avoids conflict."
    assert d["consequence_obligations"] == ["Duty of Loyalty"]
    assert d["consequence_fluent_changes"]["initiated"] == ["Clean_Separation"]


def test_scenario_branch_consequence_fields_default_empty():
    """Branch-level consequence fields default to empty."""
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="Test context",
        question="What should happen?",
        decision_point_uri="dp_1",
        decision_maker_uri="uri:maker",
        decision_maker_label="Engineers",
    )
    assert branch.board_rationale == ""
    assert branch.competing_obligation_labels == []


def test_scenario_branch_to_dict_includes_consequence_fields():
    """to_dict() includes the new consequence fields."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test",
        description="",
        consequence_narrative="Consequence text",
    )
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="Context",
        question="Question?",
        decision_point_uri="dp_1",
        decision_maker_uri="uri:maker",
        decision_maker_label="Engineers",
        options=[opt],
        board_rationale="The board chose this because...",
        competing_obligation_labels=["Duty of Loyalty", "Right to Mobility"],
    )
    d = branch.to_dict()
    assert d["board_rationale"] == "The board chose this because..."
    assert d["competing_obligation_labels"] == ["Duty of Loyalty", "Right to Mobility"]
    assert d["options"][0]["consequence_narrative"] == "Consequence text"


def test_phase4_result_includes_consequence_data():
    """Verify that ScenarioSeeds.to_dict() includes consequence fields
    when they are populated."""
    opt = ScenarioOption(
        option_id="opt_0_0",
        label="Test",
        description="",
        consequence_narrative="Test consequence",
        consequence_obligations=["Duty X"],
        consequence_fluent_changes={"initiated": ["A"], "terminated": ["B"]},
    )
    branch = ScenarioBranch(
        branch_id="branch_0",
        context="",
        question="Q?",
        decision_point_uri="dp",
        decision_maker_uri="uri",
        decision_maker_label="Engineer",
        options=[opt],
        board_rationale="Board chose because...",
        competing_obligation_labels=["Duty X", "Duty Y"],
    )
    seeds = ScenarioSeeds(
        case_id=1,
        opening_context="",
        initial_state_description="",
        protagonist_uri="",
        protagonist_label="",
        branches=[branch],
    )

    d = seeds.to_dict()
    assert d["branches"][0]["board_rationale"] == "Board chose because..."
    assert d["branches"][0]["competing_obligation_labels"] == ["Duty X", "Duty Y"]
    assert d["branches"][0]["options"][0]["consequence_narrative"] == "Test consequence"
