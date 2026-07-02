"""Stage-2 audit guardrails on the live Step-3 temporal prompts (WP2).

Locks four live-path repairs:
  1. Both live prompt builders (action phase-1, event) render the shared {{ pass_directive }}
     block (no-fabrication + actor-scope + quote-fidelity); A/E were the only components whose
     live prompts lacked every shared directive.
  2. The event contract converges on the seeded events template: text_references (verbatim
     grounding) + confidence are requested, and the raw case text is included so the quotes
     can be verbatim.
  3. The guiding_principles referent rule is stated and the worked example no longer teaches
     the motive-word anti-pattern ("Efficiency").
  4. The terminates-coherence rule (a happening must not terminate a state it initiates) is
     stated on both prompts and in the seeded bodies.
  5. Stage-3 action grounding parity: the action phase-1 prompt requests verbatim
     text_references (mirroring the event convergence of item 2), and the seeded actions
     body documents the same contract.

DB/LLM-free: the builders only read the ontology TTL / SHACL files via concept_ontology_slots.
"""
from pathlib import Path

from jinja2 import Template

from app.services.prompt_variable_resolver import concept_ontology_slots
from app.services.temporal_dynamics.extractors.action_extractor import _build_phase1_prompt
from app.services.temporal_dynamics.extractors.event_extractor import (
    _build_event_extraction_prompt,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "app" / "utils" / "prompts"

_NARRATIVE = {
    "unified_timeline_summary": "Engineer A assigned the analysis; a flaw was later found.",
    "decision_points": ["Assign the analysis"],
    "competing_priorities_mentioned": [],
}
_MARKERS = {"absolute": [], "relative": []}
_ACTIONS = [{"label": "Task Assignment Decision", "agent": "Engineer A (Senior Engineer)"}]

# Distinctive openings of the three all-pass shared directives (prompt_variable_resolver).
_SHARED_MARKS = ("DO NOT FABRICATE CONCEPTS", "SCOPE A DUTY TO ITS ACTOR",
                 "QUOTE VERBATIM, MATCH THE MODALITY")


def _action_prompt():
    return _build_phase1_prompt(_NARRATIVE, _MARKERS,
                                facts_text="The engineer sealed the report.",
                                discussion_text="The Board found the seal improper.")


def _event_prompt():
    return _build_event_extraction_prompt(_NARRATIVE, _MARKERS, _ACTIONS,
                                          facts_text="The engineer sealed the report.",
                                          discussion_text="The Board found the seal improper.")


# ---------------------------------------------------------------------------
# 1. shared pass directives on both live prompts
# ---------------------------------------------------------------------------

def test_action_prompt_carries_shared_directives():
    prompt = _action_prompt()
    for mark in _SHARED_MARKS:
        assert mark in prompt, f"action phase-1 prompt missing shared directive: {mark}"


def test_event_prompt_carries_shared_directives():
    prompt = _event_prompt()
    for mark in _SHARED_MARKS:
        assert mark in prompt, f"event prompt missing shared directive: {mark}"


def test_pass_directive_slot_resolves_for_actions_and_events():
    for concept in ("actions", "events"):
        slots = concept_ontology_slots(concept, "all")
        directive = slots.get("pass_directive") or ""
        for mark in _SHARED_MARKS:
            assert mark in directive, f"{concept} pass_directive missing: {mark}"


# ---------------------------------------------------------------------------
# 2. event contract convergence: verbatim grounding + confidence + case text
# ---------------------------------------------------------------------------

def test_event_prompt_requests_grounding_fields():
    prompt = _event_prompt()
    assert "text_references" in prompt
    assert "confidence" in prompt
    assert "EXACT contiguous span" in prompt
    # The raw case text is included so quotes can actually be verbatim.
    assert "CASE FACTS:" in prompt
    assert "The engineer sealed the report." in prompt
    assert "CASE DISCUSSION:" in prompt
    # The worked example shows both fields.
    assert '"text_references"' in prompt
    assert '"confidence"' in prompt


def test_event_prompt_keeps_origin_triage_and_tie_break():
    prompt = _event_prompt()
    assert "ORIGIN CLASSIFICATION" in prompt
    assert "Origin tie-break" in prompt
    assert "AutomaticEvent" in prompt
    assert "caused_by_action" in prompt


def test_action_prompt_requests_grounding_fields():
    """Stage-3 action grounding parity: the phase-1 prompt requests verbatim
    text_references (mirroring the Stage-2 event convergence), the raw case text is
    included so the quotes can be verbatim, and the worked example carries the field
    (consistent with the verbatim rule, no paraphrase)."""
    prompt = _action_prompt()
    assert "text_references" in prompt
    assert "EXACT contiguous span" in prompt
    assert "never paraphrase" in prompt
    # The raw case text is included so quotes can actually be verbatim.
    assert "CASE FACTS:" in prompt
    assert "The engineer sealed the report." in prompt
    assert "CASE DISCUSSION:" in prompt
    # The worked example shows the field.
    assert '"text_references"' in prompt


# ---------------------------------------------------------------------------
# 3. guiding_principles referent rule + example fix
# ---------------------------------------------------------------------------

def test_action_prompt_guiding_principles_referent_rule():
    prompt = _action_prompt()
    assert "must name a Principle extracted for this case" in prompt
    # Empty is the exception, not the norm (the R2 regression fix: the [] worked example
    # plus "an empty list is correct" wording taught emptiness and zeroed guidedByPrinciple).
    assert "use an empty list only when no extracted principle applies" in prompt
    assert "an empty list is correct when no extracted principle guided the action" not in prompt
    # The worked example must not teach the motive-word anti-pattern, and must not teach
    # emptiness: it names a realistic extracted-principle label consistent with its scenario.
    assert '"guiding_principles": ["Efficiency"]' not in prompt
    assert '"guiding_principles": []' not in prompt
    assert '"guiding_principles": ["Loyalty Principle"]' in prompt


# ---------------------------------------------------------------------------
# 4. terminates coherence rule on both prompts and both seeded bodies
# ---------------------------------------------------------------------------

_TERMINATES_RULE = "must not terminate a state it initiates"


def test_terminates_coherence_rule_everywhere():
    assert _TERMINATES_RULE in _action_prompt()
    assert _TERMINATES_RULE in _event_prompt()
    for body in ("actions.md", "events.md"):
        assert _TERMINATES_RULE in (_PROMPTS_DIR / body).read_text(), body


# ---------------------------------------------------------------------------
# seeded actions body: ONT-4-deprecated content purged, slots wired
# ---------------------------------------------------------------------------

def test_actions_body_purged_and_wired():
    body = (_PROMPTS_DIR / "actions.md").read_text()
    # ONT-4-deprecated content gone.
    assert "action_type" not in body
    assert "Every Action becomes an Event" not in body
    assert "becomes_event" not in body
    assert "ethics guideline" not in body
    # Stage-3 grounding parity: the documented contract carries text_references with
    # the verbatim rule (single source with the live phase-1 prompt).
    assert "text_references" in body
    assert "EXACT contiguous span" in body
    # Slots wired; mints-no-classes prominent.
    for slot in ("{{ action_definition }}", "{{ action_boundary }}",
                 "{{ action_individuation }}", "{{ pass_directive }}", "{{ case_text }}"):
        assert slot in body, f"actions.md missing {slot}"
    assert "mints NO action classes" in body
    # The body renders cleanly with the live slots.
    rendered = Template(body).render(case_text="TEXT",
                                     **concept_ontology_slots("actions", "all"))
    assert "=== ACTION (ontology definition) ===" in rendered
    for mark in _SHARED_MARKS:
        assert mark in rendered
