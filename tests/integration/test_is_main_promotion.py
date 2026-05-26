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
    for i, agent in enumerate(action_agents):
        iri = f"http://proethica.org/cases/{case_id}#Action_{i}"
        db.session.add(TemporaryRDFStorage(
            case_id=case_id, extraction_session_id="t", storage_type="individual",
            extraction_type="temporal_dynamics_enhanced", entity_label=f"Action_{i}",
            rdf_json_ld={"@id": iri, "@type": "proeth:Action", "rdfs:label": f"Action_{i}",
                         "proeth:hasAgent": agent}))
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
