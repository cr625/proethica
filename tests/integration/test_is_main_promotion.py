"""Integration tests for the A9 is_main >=2-action promotion (study-corrections).

A character is promoted to "main" when it is the agent of >=2 timeline actions,
even if the opening_context narration does not name it (case 15's "Owner" is the
motivating fixture). The rule only promotes characters the extractor already
surfaced; composite/conjunctive agents are excluded.
"""
import json

import pytest

from app import db
from app.models.world import World
from app.models.document import Document
from app.models.extraction_prompt import ExtractionPrompt
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder


def _seed(case_id, characters, opening_context, action_agents):
    world = World.query.first() or World(name="Test World")
    if world.id is None:
        db.session.add(world)
        db.session.flush()
    if not Document.query.get(case_id):
        db.session.add(Document(id=case_id, title=f"Case {case_id}",
                                document_type="case", world_id=world.id))
    db.session.add(ExtractionPrompt(
        case_id=case_id, concept_type="phase4_narrative", section_type="discussion",
        step_number=4, prompt_text="p",
        raw_response=json.dumps({
            "narrative_elements": {"characters": characters, "conflicts": []},
            "scenario_seeds": {"opening_context": opening_context},
        })))
    for i, spec in enumerate(action_agents):
        # spec is either a bare agent string or a (agent, eventRoleContext) tuple.
        agent, context = (spec, "") if isinstance(spec, str) else spec
        iri = f"http://proethica.org/cases/{case_id}#Action_{i}"
        rdf = {"@id": iri, "@type": "proeth:Action", "rdfs:label": f"Action_{i}",
               "proeth:hasAgent": agent}
        if context:
            rdf["proeth:eventRoleContext"] = context
        db.session.add(TemporaryRDFStorage(
            case_id=case_id, extraction_session_id="t", storage_type="individual",
            extraction_type="temporal_dynamics_enhanced", entity_label=f"Action_{i}",
            rdf_json_ld=rdf))
    db.session.commit()


def test_agent_count_helper_skips_composites(app_context):
    case_id = 9501
    _seed(case_id, [{"label": "Owner X"}], "irrelevant",
          ["Owner X", "Owner X", "Firm P (lead) and Firm Q (sub)",
           "Firm P (lead) and Firm Q (sub)", "Unknown"])
    counts = SynthesisViewBuilder()._timeline_agent_action_counts(case_id)
    assert counts.get("owner x") == 2
    assert all("firm p" not in k for k in counts)  # composite skipped
    assert "unknown" not in counts


def test_owner_promoted_by_two_actions(app_context):
    case_id = 9502
    # Engineer A is named in opening_context; Owner X is not but acts twice;
    # Clerk Y acts once and is not named -> stays additional.
    _seed(
        case_id,
        characters=[{"label": "Engineer A"}, {"label": "Owner X"}, {"label": "Clerk Y"}],
        opening_context="Engineer A reviewed the design and signed off.",
        action_agents=["Owner X", "Owner X", "Clerk Y", "Engineer A"],
    )
    view = SynthesisViewBuilder().get_narrative_view(case_id)
    main = {g["short_name"] for g in view["grouped_main_characters"]}
    other = {g["short_name"] for g in view["grouped_other_characters"]}

    assert "Engineer A" in main          # named in opening_context
    assert "Owner X" in main             # promoted by >=2 actions
    assert "Clerk Y" in other            # only 1 action, not named
    assert "Clerk Y" not in main


def test_single_action_not_promoted(app_context):
    case_id = 9503
    _seed(case_id, [{"label": "Owner X"}], "Nobody relevant named here.",
          action_agents=["Owner X"])  # only one action
    view = SynthesisViewBuilder().get_narrative_view(case_id)
    main = {g["short_name"] for g in view["grouped_main_characters"]}
    assert "Owner X" not in main


def test_descriptive_labels_resolved_via_role_context(app_context):
    """Case-103 regression: Step-3 emits clean generic agents ("City Council",
    "Professional Engineer") while Phase-4 characters carry descriptive
    role-derived labels that share no prefix with the agents. The token-overlap
    fallback bridged by eventRoleContext must still promote the right
    characters, where a raw label match promotes nothing."""
    case_id = 9504
    characters = [
        {"label": "Engineer Dual Capacity City Advisory Design",
         "role_type": "stakeholder",
         "professional_position": "A private-practice engineer treating his part-time "
                                  "municipal role as a client engagement."},
        {"label": "City Municipal Government Client",
         "role_type": "stakeholder",
         "professional_position": "A small community whose city council retains a single "
                                  "part-time engineer for advisory guidance."},
        {"label": "Part-Time City Engineer Advisory Design",
         "role_type": "protagonist",
         "professional_position": "A professional engineer in private practice retained "
                                  "part-time by a small community as city engineer."},
    ]
    _seed(
        case_id, characters,
        opening_context="You are Engineer, serving part-time as city engineer.",
        action_agents=[
            ("City Council", "municipal decision-making body"),
            ("City Council", "municipal decision-making body"),
            ("City Council", "municipal decision-making body"),
            ("Professional Engineer", "part-time city engineer and private practitioner"),
            ("Professional Engineer", "part-time city engineer and private practitioner"),
        ],
    )
    view = SynthesisViewBuilder().get_narrative_view(case_id)
    main_labels = {c["label"] for c in view["characters"] if c.get("is_main")}
    # City Council (x3) -> the municipal-client character; Professional Engineer
    # (x2) -> the protagonist engineer. Neither resolves by a raw label prefix.
    assert "City Municipal Government Client" in main_labels
    assert "Part-Time City Engineer Advisory Design" in main_labels
    # The cautionary/secondary engineer is not the best match for either agent.
    assert "Engineer Dual Capacity City Advisory Design" not in main_labels


def test_cited_case_actors_filtered_and_excluded_from_promotion(app_context):
    """Case-60 regression: actors pulled from cited BER opinions must not appear
    as characters (filter catches "BER Case NN-N" anywhere in the label), and a
    cited-precedent timeline agent must not drive promotion."""
    case_id = 9505
    characters = [
        {"label": "Engineer A Forensic Expert State M", "role_type": "protagonist",
         "professional_position": "Licensed PE serving as a forensic expert witness."},
        {"label": "BER Case 04-11 Engineer State E Business Card", "role_type": "stakeholder",
         "professional_position": "Actor from a cited opinion."},
        {"label": "Engineer A BER Case 19-3 Standards Chair", "role_type": "decision-maker",
         "professional_position": "Actor from a cited opinion."},
        {"label": "Engineer Intern BER Case 20-1", "role_type": "stakeholder",
         "professional_position": "Actor from a cited opinion."},
    ]
    _seed(
        case_id, characters,
        opening_context="You are Engineer A, a licensed Professional Engineer.",
        action_agents=[
            ("Engineer A", "Licensed Professional Engineer"),
            ("Engineer A", "Licensed Professional Engineer"),
            ("Engineer A", "Licensed Professional Engineer"),
            ("Engineer A in BER Case 19-3", "Forensic mechanical engineer; cited opinion"),
        ],
    )
    view = SynthesisViewBuilder().get_narrative_view(case_id)
    labels = {c["label"] for c in view["characters"]}
    # All three cited-case actors are filtered out of the character set.
    assert "BER Case 04-11 Engineer State E Business Card" not in labels
    assert "Engineer A BER Case 19-3 Standards Chair" not in labels
    assert "Engineer Intern BER Case 20-1" not in labels
    # The present-case protagonist remains and is promoted (3 clean actions).
    main_labels = {c["label"] for c in view["characters"] if c.get("is_main")}
    assert "Engineer A Forensic Expert State M" in main_labels


def test_widened_citation_regex_matches_ber_anywhere():
    """The module-level citation pattern catches prefix, suffix, and mid-label
    BER references, and the NN-N (single trailing digit) form."""
    from app.services.validation.synthesis_view_builder import _CITATION_RE
    assert _CITATION_RE.search("BER Case 04-11 Engineer State E Business Card")
    assert _CITATION_RE.search("Engineer A BER Case 19-3 Standards Chair")
    assert _CITATION_RE.search("Engineer Intern BER Case 20-1")
    assert _CITATION_RE.search("Case 76-4")
    # A present-case person label must not match.
    assert not _CITATION_RE.search("Engineer A Forensic Expert State M")
    assert not _CITATION_RE.search("City Municipal Government Client")
