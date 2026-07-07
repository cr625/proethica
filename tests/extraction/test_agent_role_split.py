"""Unit tests for split_agent_role (study-corrections A7/B4).

The same helper drives the live converter (A7) and the corpus backfill (B4),
so its clean-vs-composite boundary is the single source of truth for which
agent strings get split and which are deferred to the bucket-C corrective pass.
"""
import pytest

from app.services.temporal_dynamics.utils.rdf_converter import (
    split_agent_role,
    decompose_agents,
    convert_action_to_rdf,
)


@pytest.mark.parametrize("agent,name,role", [
    # Clean single "Name (role)" -> split.
    ("Engineer A (Professional Engineer, Structural)",
     "Engineer A", "Professional Engineer, Structural"),
    ("Client B (Developer)", "Client B", "Developer"),
    ("NSPE Board of Ethical Review (Professional Ethics Adjudicatory Body)",
     "NSPE Board of Ethical Review", "Professional Ethics Adjudicatory Body"),
    # Slash composite NAME but single clean role parenthetical -> still split
    # (the role context is unambiguous; the composite name is a separate
    # narrative-matching concern, not a malformed-for-split case).
    ("Company X management / Supervisor B (corporate decision-makers)",
     "Company X management / Supervisor B", "corporate decision-makers"),
    # Surrounding whitespace tolerated.
    ("  Engineer A (EIT, Mechanical Engineer)  ",
     "Engineer A", "EIT, Mechanical Engineer"),
])
def test_clean_strings_split(agent, name, role):
    assert split_agent_role(agent) == (name, role)


@pytest.mark.parametrize("agent", [
    # Multiple parenthetical groups -> conjunctive agent, leave intact.
    "Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)",
    # No parenthetical at all.
    "County A Engineering Staff",
    "Unknown",
    # Empty / falsy.
    "",
    # Empty role.
    "Engineer A ()",
    # Empty name.
    "(just a role)",
])
def test_composite_or_malformed_left_intact(agent):
    name, role = split_agent_role(agent)
    assert role is None
    assert name == agent


def test_converter_applies_split():
    """convert_action_to_rdf splits a clean agent into name + role context."""
    rdf = convert_action_to_rdf(
        {"label": "Notify authority", "agent": "Engineer A (Professional Engineer)"},
        case_id=999,
    )
    assert rdf["proeth:hasAgent"] == "Engineer A"
    assert rdf["proeth:eventRoleContext"] == "Professional Engineer"


def test_converter_decomposes_composite_agent():
    """A composite agent keeps its original hasAgent (provenance) and no single
    eventRoleContext, but is decomposed into the proeth:agents list, flattened
    to 'Name (role)' strings (the commit serializer drops dict values, so the
    earlier list-of-dicts shape never reached the committed graph)."""
    rdf = convert_action_to_rdf(
        {"label": "Joint review",
         "agent": "Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)"},
        case_id=999,
    )
    assert rdf["proeth:hasAgent"] == \
        "Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)"
    assert "proeth:eventRoleContext" not in rdf
    assert rdf["proeth:agents"] == [
        "Engineer A (Original Engineer)",
        "Engineer B (Reviewing Engineer)",
    ]
    assert rdf["proeth:agentRelation"] == "and"


@pytest.mark.parametrize("agent,expected_agents,relation", [
    ("Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)",
     [{"name": "Engineer A", "role": "Original Engineer"},
      {"name": "Engineer B", "role": "Reviewing Engineer"}], "and"),
    ("ZZZ (project owner) and Firm C (design firm)",
     [{"name": "ZZZ", "role": "project owner"},
      {"name": "Firm C", "role": "design firm"}], "and"),
    # Bare names, no roles.
    ("Engineer A and Engineer B",
     [{"name": "Engineer A", "role": None},
      {"name": "Engineer B", "role": None}], "and"),
    # CRITICAL: 'and' + comma INSIDE a role must not split the actors.
    ("Engineer A (superintendent and chief engineer, MWC) and Engineer B (Town Engineer)",
     [{"name": "Engineer A", "role": "superintendent and chief engineer, MWC"},
      {"name": "Engineer B", "role": "Town Engineer"}], "and"),
    ("Owner and/or Contractor",
     [{"name": "Owner", "role": None},
      {"name": "Contractor", "role": None}], "and/or"),
])
def test_decompose_agents_multi(agent, expected_agents, relation):
    agents, rel = decompose_agents(agent)
    assert agents == expected_agents
    assert rel == relation


@pytest.mark.parametrize("agent", [
    "Engineer A (Professional Engineer, Structural)",  # single actor, comma in role
    "Engineer A",                                       # bare single name
    "",
    "County A Engineering Staff",
])
def test_decompose_agents_single_returns_none(agent):
    assert decompose_agents(agent) is None
