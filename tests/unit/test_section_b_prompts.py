"""Section-B prompt/extractor finalization tests (ROADMAP).

Covers three changes authored 2026-05-26 (corpus effect deferred to Section C):

- B5: defeasible/conditional language in the resolution-pattern prompt + a new
  ``resolution_conditions`` field threaded through model/parser/persist/load.
- B3: missing-present-case-character rescan in the Phase-4 character pass.
- HO-006: Action/Event Pydantic models conformed to the emitted JSON-LD vocabulary.

All tests are hermetic (no DB, no live LLM); the LLM client and facts loader are
mocked where needed.
"""

from unittest.mock import patch

import pytest

from app.services.step4_synthesis.case_synthesis_models import EntityFoundation, EntitySummary, ResolutionPatternAnalysis
from app.services.step4_synthesis.rich_analysis import RichAnalyzer
from app.services.narrative.narrative_element_extractor import (
    NarrativeElementExtractor,
    NarrativeCharacter,
)
from app.services.extraction.schemas import ActionIndividual, EventIndividual


# ---------------------------------------------------------------------------
# B5 - resolution-pattern conditional language
# ---------------------------------------------------------------------------

class TestB5ResolutionConditions:
    def test_model_carries_resolution_conditions(self):
        rp = ResolutionPatternAnalysis(
            conclusion_uri="case-1#C1",
            conclusion_text="...",
            resolution_conditions="Holds when X; would not hold unless Y",
        )
        assert rp.resolution_conditions.startswith("Holds when")
        assert "resolution_conditions" in rp.to_dict()

    def test_parser_maps_resolution_conditions(self):
        analyzer = RichAnalyzer(llm_client=object())
        patterns_data = [{
            "conclusion_index": 1,
            "answers_questions": [],
            "determinative_principles": [],
            "determinative_facts": [],
            "cited_provisions": [],
            "weighing_process": "balanced",
            "resolution_conditions": "Holds when disclosure was made; not unless concealed",
            "resolution_narrative": "Given X, the board concluded Y",
            "confidence": 0.8,
        }]
        batch_conclusions = [{"uri": "case-1#C1", "text": "conclusion text"}]
        results = analyzer._resolve_resolution_patterns(
            patterns_data, batch_conclusions, questions=[], provisions=[], entity_dict={}
        )
        assert len(results) == 1
        assert results[0].resolution_conditions == "Holds when disclosure was made; not unless concealed"

    def test_parser_defaults_blank_when_absent(self):
        """Legacy patterns without the field must still parse."""
        analyzer = RichAnalyzer(llm_client=object())
        patterns_data = [{"conclusion_index": 1, "resolution_narrative": "..."}]
        batch_conclusions = [{"uri": "case-1#C1", "text": "t"}]
        results = analyzer._resolve_resolution_patterns(
            patterns_data, batch_conclusions, questions=[], provisions=[], entity_dict={}
        )
        assert results[0].resolution_conditions == ""


# ---------------------------------------------------------------------------
# B3 - missing-present-case-character rescan
# ---------------------------------------------------------------------------

def _foundation_with_one_role():
    f = EntityFoundation()
    f.roles = [EntitySummary(uri="http://proethica.org/cases/60#EngineerA",
                             label="Engineer A", definition="Primary engineer")]
    f.obligations = []
    return f


class TestB3CharacterRescan:
    def test_rescan_appends_omitted_actor(self):
        extractor = NarrativeElementExtractor(use_llm=False)
        extractor.llm_client = object()  # truthy so the LLM branch runs
        characters = [NarrativeCharacter(uri="http://proethica.org/cases/60#EngineerA",
                                         label="Engineer A", role_type="protagonist")]
        foundation = _foundation_with_one_role()

        llm_payload = {
            "enhancements": [],
            "missing_characters": [
                {"label": "Engineer B", "role_type": "stakeholder",
                 "description": "Reviewing engineer", "motivation": "Wants accurate plans"}
            ],
        }
        with patch("app.utils.llm_utils.streaming_completion", return_value="ignored"), \
             patch("app.utils.llm_json_utils.parse_json_response", return_value=llm_payload), \
             patch.object(extractor, "_load_case_facts", return_value="Engineer B reviewed the plans."):
            result, trace = extractor._enhance_characters_with_llm(characters, foundation, case_id=60)

        labels = [c.label for c in result]
        assert "Engineer B" in labels
        eng_b = next(c for c in result if c.label == "Engineer B")
        assert eng_b.role_type == "stakeholder"
        assert eng_b.llm_enhanced is True
        assert "#" in eng_b.uri and eng_b.uri.startswith("http://proethica.org/cases/60")

    def test_rescan_skips_duplicates_and_meta_authority(self):
        extractor = NarrativeElementExtractor(use_llm=False)
        extractor.llm_client = object()
        characters = [NarrativeCharacter(uri="http://proethica.org/cases/60#EngineerA",
                                         label="Engineer A", role_type="protagonist")]
        foundation = _foundation_with_one_role()

        llm_payload = {
            "enhancements": [],
            "missing_characters": [
                {"label": "Engineer A"},                       # duplicate
                {"label": "Board of Ethical Review"},          # meta-authority
                {"label": ""},                                  # empty
            ],
        }
        with patch("app.utils.llm_utils.streaming_completion", return_value="ignored"), \
             patch("app.utils.llm_json_utils.parse_json_response", return_value=llm_payload), \
             patch.object(extractor, "_load_case_facts", return_value="facts"):
            result, _ = extractor._enhance_characters_with_llm(characters, foundation, case_id=60)

        assert len(result) == 1  # nothing appended

    def test_legacy_bare_array_response_still_parses(self):
        """An old-shape response (bare enhancement array) must not crash."""
        extractor = NarrativeElementExtractor(use_llm=False)
        extractor.llm_client = object()
        characters = [NarrativeCharacter(uri="http://proethica.org/cases/60#EngineerA",
                                         label="Engineer A", role_type="protagonist")]
        foundation = _foundation_with_one_role()

        legacy = [{"role": "Engineer A", "description": "desc", "motivation": "mot"}]
        with patch("app.utils.llm_utils.streaming_completion", return_value="ignored"), \
             patch("app.utils.llm_json_utils.parse_json_response", return_value=legacy), \
             patch.object(extractor, "_load_case_facts", return_value="facts"):
            result, _ = extractor._enhance_characters_with_llm(characters, foundation, case_id=60)

        assert len(result) == 1
        assert result[0].professional_position == "desc"

    def test_prompt_includes_rescan_and_facts(self):
        extractor = NarrativeElementExtractor(use_llm=False)
        extractor.llm_client = object()
        characters = [NarrativeCharacter(uri="http://proethica.org/cases/60#EngineerA",
                                         label="Engineer A", role_type="protagonist")]
        foundation = _foundation_with_one_role()

        captured = {}

        def _capture(client, **kwargs):
            captured["prompt"] = kwargs.get("prompt", "")
            return "ignored"

        with patch("app.utils.llm_utils.streaming_completion", side_effect=_capture), \
             patch("app.utils.llm_json_utils.parse_json_response", return_value={"enhancements": [], "missing_characters": []}), \
             patch.object(extractor, "_load_case_facts", return_value="Engineer B inspected the site."):
            extractor._enhance_characters_with_llm(characters, foundation, case_id=60)

        prompt = captured["prompt"]
        assert "MISSING-CHARACTER RESCAN" in prompt
        assert "CASE FACTS" in prompt
        assert "Engineer B inspected the site." in prompt


# ---------------------------------------------------------------------------
# HO-006 - Action/Event models conformed to emitted vocabulary
# ---------------------------------------------------------------------------

class TestHO006ConformedModels:
    def test_action_loads_emitted_jsonld(self):
        emitted = {
            "@id": "http://proethica.org/cases/103#Action_X",
            "@type": "proeth:Action",
            "rdfs:label": "Advising the city",
            "proeth:description": "desc",
            "proeth:hasAgent": "Professional Engineer",
            "proeth:eventRoleContext": "City Engineer",
            "proeth:temporalMarker": "Recurring",
            "proeth:fulfillsObligation": ["Rule 13"],
            "proeth:hasCompetingPriorities": {"@type": "proeth:CompetingPriorities",
                                              "proeth:priorityConflict": "a vs b"},
            "proeth:withinCompetence": True,
            "proeth-scenario:isDecisionPoint": True,
            "proeth-scenario:alternativeActions": ["recuse"],
            "proeth:raisesObligation": [],
            "proeth:temporalSequence": 8,
        }
        a = ActionIndividual.model_validate(emitted)
        assert a.has_agent == "Professional Engineer"
        assert a.event_role_context == "City Engineer"
        assert a.temporal_sequence == 8
        # is_decision_point + has_competing_priorities were dropped from the Step-3 Action schema
        # (HO-006 unify / D22): the decision-point concept now lives in the separate
        # canonical_decision_point extraction, and competing priorities are not a Step-3 field.
        # round-trips back to the exact emitted keys
        dumped = a.model_dump(by_alias=True, exclude_none=True)
        assert dumped["proeth:hasAgent"] == "Professional Engineer"
        assert dumped["proeth-scenario:alternativeActions"] == ["recuse"]

    def test_event_loads_emitted_jsonld(self):
        emitted = {
            "@id": "http://proethica.org/cases/103#Event_Y",
            "@type": "proeth:Event",
            "rdfs:label": "Conflict recognized",
            "proeth:description": "desc",
            "proeth:eventType": "outcome",
            "proeth:emergencyStatus": "low",
            "proeth:urgencyLevel": "low",
            "proeth:createsObligation": ["Maintain vigilance"],
            "proeth:causedByAction": "http://proethica.org/cases/103#Action_X",
            "proeth-scenario:crisisIdentification": False,
            "proeth:temporalSequence": 10,
        }
        e = EventIndividual.model_validate(emitted)
        assert e.event_type == "outcome"
        # creates_obligation and crisis_identification were dropped from the Event schema (D22 /
        # HO-006 unify): an event does not create an obligation directly (the Event-Calculus path
        # -- event initiates a State, the State activates the obligation -- carries that now), and
        # crisis_identification is no longer a Step-3 Event field.
        assert e.temporal_sequence == 10

    def test_obsolete_snakecase_fields_removed(self):
        """The old aspirational fields that never matched emission are gone."""
        assert "performed_by" not in ActionIndividual.model_fields
        assert "temporal_interval" not in ActionIndividual.model_fields
        assert "sequence_order" not in ActionIndividual.model_fields
        assert "occurred_to" not in EventIndividual.model_fields
        assert "obligations_triggered" not in EventIndividual.model_fields
