"""Tests for the consequence generator module."""
import json
import pytest
from unittest.mock import MagicMock, patch
from app.services.narrative.scenario_seed_generator import (
    ScenarioOption, ScenarioBranch, ScenarioSeeds
)
from app.services.scenario_generation.consequence_generator import (
    generate_consequences_for_seeds,
    _build_consequence_prompt,
    _parse_consequence_response,
)


@pytest.fixture
def sample_seeds():
    """Minimal ScenarioSeeds with one branch and two options."""
    return ScenarioSeeds(
        case_id=1,
        opening_context="You are an engineer facing a decision.",
        initial_state_description="Active employment.",
        protagonist_uri="uri:engineer",
        protagonist_label="Engineer",
        branches=[
            ScenarioBranch(
                branch_id="branch_0",
                context="The engineer discovers a conflict.",
                question="Should the engineer disclose or stay silent?",
                decision_point_uri="dp_0",
                decision_maker_uri="uri:engineer",
                decision_maker_label="Engineer",
                involved_obligation_uris=[
                    "uri:obligation-duty-of-candor",
                    "uri:obligation-loyalty-to-employer",
                ],
                options=[
                    ScenarioOption(
                        option_id="opt_0_0",
                        label="Disclose the conflict",
                        description="",
                        action_uris=["case-1#Disclose"],
                        is_board_choice=True,
                    ),
                    ScenarioOption(
                        option_id="opt_0_1",
                        label="Stay silent",
                        description="",
                        action_uris=["case-1#Stay_Silent"],
                        is_board_choice=False,
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_resolution():
    return {
        "resolution_type": "violation",
        "summary": "The Board found the engineer violated the duty of candor.",
        "conclusions": [
            {"uri": "c1", "text": "The engineer should have disclosed."}
        ],
    }


@pytest.fixture
def sample_causal_links():
    return [
        {
            "source_uri": "case-1#Disclose",
            "source_label": "Disclose",
            "target_uri": "uri:obligation-duty-of-candor",
            "target_label": "Duty of Candor",
            "link_type": "fulfills",
        },
        {
            "source_uri": "case-1#Stay_Silent",
            "source_label": "Stay Silent",
            "target_uri": "uri:obligation-duty-of-candor",
            "target_label": "Duty of Candor",
            "link_type": "violates",
        },
    ]


@pytest.fixture
def sample_entity_lookup():
    return {
        "uri:obligation-duty-of-candor": {"label": "Duty of Candor"},
        "uri:obligation-loyalty-to-employer": {"label": "Loyalty to Employer"},
    }


def test_build_consequence_prompt(sample_seeds, sample_causal_links, sample_resolution):
    """Prompt includes branch question, all options, causal links, and resolution."""
    prompt = _build_consequence_prompt(
        branch=sample_seeds.branches[0],
        causal_links=sample_causal_links,
        resolution=sample_resolution,
    )
    assert "Disclose the conflict" in prompt
    assert "Stay silent" in prompt
    assert "Duty of Candor" in prompt
    assert "The Board found" in prompt


def test_parse_consequence_response_valid():
    """Parse a well-formed LLM response into consequence data."""
    llm_response = json.dumps({
        "options": [
            {
                "option_id": "opt_0_0",
                "consequence_narrative": "Disclosure leads to transparency.",
                "consequence_obligations": ["Duty of Candor"],
                "consequence_fluent_changes": {
                    "initiated": ["Transparency_Active"],
                    "terminated": ["Conflict_Hidden"],
                },
            },
            {
                "option_id": "opt_0_1",
                "consequence_narrative": "Silence preserves the status quo but risks discovery.",
                "consequence_obligations": ["Loyalty to Employer"],
                "consequence_fluent_changes": {
                    "initiated": ["Undisclosed_Conflict"],
                    "terminated": [],
                },
            },
        ],
        "board_rationale": "The Board emphasized candor as a core obligation.",
    })
    result = _parse_consequence_response(llm_response, num_options=2)
    assert len(result["options"]) == 2
    assert result["options"][0]["consequence_narrative"] == "Disclosure leads to transparency."
    assert result["board_rationale"] == "The Board emphasized candor as a core obligation."


def test_parse_consequence_response_malformed():
    """Malformed response returns empty defaults."""
    result = _parse_consequence_response("not json at all", num_options=2)
    assert len(result["options"]) == 2
    assert result["options"][0]["consequence_narrative"] == ""
    assert result["board_rationale"] == ""


@patch("app.services.scenario_generation.consequence_generator.get_llm_client")
def test_generate_consequences_populates_fields(
    mock_get_client, sample_seeds, sample_causal_links, sample_resolution, sample_entity_lookup
):
    """generate_consequences_for_seeds populates consequence fields on the ScenarioSeeds object."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps({
            "options": [
                {
                    "option_id": "opt_0_0",
                    "consequence_narrative": "Disclosure works.",
                    "consequence_obligations": ["Duty of Candor"],
                    "consequence_fluent_changes": {"initiated": ["Transparent"], "terminated": []},
                },
                {
                    "option_id": "opt_0_1",
                    "consequence_narrative": "Silence fails.",
                    "consequence_obligations": ["Loyalty to Employer"],
                    "consequence_fluent_changes": {"initiated": [], "terminated": []},
                },
            ],
            "board_rationale": "Candor is required.",
        }))]
    )

    generate_consequences_for_seeds(
        seeds=sample_seeds,
        causal_links=sample_causal_links,
        resolution=sample_resolution,
        entity_lookup=sample_entity_lookup,
    )

    # Verify options were populated
    branch = sample_seeds.branches[0]
    assert branch.options[0].consequence_narrative == "Disclosure works."
    assert branch.options[1].consequence_narrative == "Silence fails."
    assert branch.board_rationale == "Candor is required."
    assert branch.competing_obligation_labels == ["Duty of Candor", "Loyalty to Employer"]

    # Verify LLM was called once (one branch = one call)
    assert mock_client.messages.create.call_count == 1
