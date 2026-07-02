"""Stage-1 definition-wire tests: _component_definition_block + the {{ <comp>_definition }} slot.

The block generalizes the Role pattern (_role_definition_block) to the eight non-Role components:
iao:0000115 (the served class definition) + the operational sentences of iao:0000116 ("Extraction
framing"), read from proethica-core.ttl and trimmed deterministically at injection (inline
parenthetical author-year citations stripped; trailing "This is the X component..." sentence
dropped from the 116 when the 115 carries one; skos:scopeNote never included -- it has its own
{{ <comp>_individuation }} slot).

DB/LLM-free: the block and concept_ontology_slots read only the ontology TTL / SHACL files.
"""
import re
from pathlib import Path

import pytest
from jinja2 import Template

from app.services.prompt_variable_resolver import (
    _component_definition_block,
    concept_ontology_slots,
)

_PROMPTS_DIR = Path(__file__).resolve().parents[2] / "app" / "utils" / "prompts"

# The eight non-Role components (Role keeps its bespoke _role_definition_block; Stage 4).
_COMPONENTS = ["Principle", "Obligation", "State", "Resource",
               "Capability", "Constraint", "Action", "Event"]

# concept_type -> (component class, slot name)
_SLOT_BY_CONCEPT = {
    "principles": ("Principle", "principle_definition"),
    "obligations": ("Obligation", "obligation_definition"),
    "states": ("State", "state_definition"),
    "resources": ("Resource", "resource_definition"),
    "capabilities": ("Capability", "capability_definition"),
    "constraints": ("Constraint", "constraint_definition"),
    "actions": ("Action", "action_definition"),
    "events": ("Event", "event_definition"),
}

# Any parenthetical carrying a 1900-2099 year = an author-year citation remnant.
_CITATION_RE = re.compile(r"\(([^()]*\b(?:19|20)\d{2}\b[^()]*)\)")


# ---------------------------------------------------------------------------
# (a) the block resolves non-empty for all 8 components, with both sections
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("component", _COMPONENTS)
def test_block_resolves_non_empty(component):
    block = _component_definition_block(component)
    assert block.startswith(f"=== {component.upper()} (ontology definition) ===")
    header, rest = block.split("===\n", 1)
    definition, framing = rest.split("Extraction framing:", 1)
    assert definition.strip(), f"{component}: empty 115 definition paragraph"
    assert framing.strip(), f"{component}: empty 116 extraction-framing section"


@pytest.mark.parametrize("concept_type", sorted(_SLOT_BY_CONCEPT))
def test_slot_registered_in_concept_ontology_slots(concept_type):
    component, slot = _SLOT_BY_CONCEPT[concept_type]
    slots = concept_ontology_slots(concept_type, "facts")
    assert slots.get(slot), f"{slot} missing/empty in concept_ontology_slots({concept_type!r})"
    assert slots[slot] == _component_definition_block(component)


# ---------------------------------------------------------------------------
# (b) the 115 genus opening survives for the deontic trio + Event
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("component,genus", [
    ("Principle", "A directive information entity (IAO) that expresses an ethical value"),
    ("Obligation", "A directive information entity (IAO) that specifies a required action or duty"),
    ("Constraint", "A directive information entity (IAO) that prescribes a boundary on professional conduct"),
    ("Event", "A process (BFO) that occurs within a professional case timeline"),
])
def test_block_contains_genus_opening(component, genus):
    assert genus in _component_definition_block(component)


# ---------------------------------------------------------------------------
# (c) no parenthetical author-year citation survives the trim
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("component", _COMPONENTS)
def test_no_citation_survives_trim(component):
    block = _component_definition_block(component)
    m = _CITATION_RE.search(block)
    assert m is None, f"{component}: citation survived the trim: ({m.group(1)})"


def test_scope_note_not_included():
    # The scopeNote has its own {{ <comp>_individuation }} slot; the definition block must not
    # duplicate it. Spot-check with a scopeNote-distinctive phrase per component.
    assert "attach to the case individuals and edges, not to the class" \
        not in _component_definition_block("Principle")
    assert "The obligation TYPE is defined by the duty it specifies" \
        not in _component_definition_block("Obligation")


# ---------------------------------------------------------------------------
# (d) the seeded bodies wire the slot; rendered P/O templates carry the new
#     directive lines and no hand-written "WHAT A ..." header remains
# ---------------------------------------------------------------------------

def _render(concept_type: str) -> str:
    body = (_PROMPTS_DIR / f"{concept_type}.md").read_text()
    return Template(body).render(**concept_ontology_slots(concept_type, "facts"))


@pytest.mark.parametrize("concept_type", sorted(_SLOT_BY_CONCEPT))
def test_body_wires_definition_slot_and_drops_header(concept_type):
    _component, slot = _SLOT_BY_CONCEPT[concept_type]
    body = (_PROMPTS_DIR / f"{concept_type}.md").read_text()
    assert f"{{{{ {slot} }}}}" in body, f"{concept_type}.md does not render {{{{ {slot} }}}}"
    assert "WHAT A" not in body, f"{concept_type}.md still carries a hand-written WHAT A header"
    assert "iao:0000033" not in body, f"{concept_type}.md still carries the BFO iao:0000033 mislabel"


def test_rendered_principles_template():
    rendered = _render("principles")
    assert "WHAT A" not in rendered
    # The injected ontology definition replaces the hand-written header.
    assert "=== PRINCIPLE (ontology definition) ===" in rendered
    assert "individuated by the value it expresses" in rendered
    # The per-value granularity directive (canonical Principle 116 sentence).
    assert ("a case yields at most one principle individual per distinct value, and distinct "
            "values remain separate individuals") in rendered
    # OUTPUT FORMAT rewritten to the per-value rule (no more "specific invocations").
    assert "specific invocations" not in rendered
    assert "at most one individual per distinct value" in rendered


def test_rendered_obligations_template():
    rendered = _render("obligations")
    assert "WHAT A" not in rendered
    assert "=== OBLIGATION (ontology definition) ===" in rendered
    # The firmness + prohibition + compliance directive lines (canonical Obligation 116 sentences).
    assert "A must-not or shall-not statement is a Constraint, not an Obligation." in rendered
    assert ("Required-ness is the differentia: guidance the source treats as recommended best "
            "practice is not an Obligation and routes to the Principle pass.") in rendered
    assert ("A duty to comply with named requirements is a positive duty and is an Obligation "
            "even when the requirements themselves are Constraints.") in rendered
    # The header fix rode the header deletion: no "action or restraint" paraphrase remains.
    assert "action or restraint" not in rendered


def test_rendered_constraints_states_events_directives():
    constraints = _render("constraints")
    assert ("a provision the code states negatively (shall not X) is extracted once, as a "
            "Constraint") in constraints
    states = _render("states")
    assert "Stative-label rule: a state is named for the condition that holds" in states
    assert "A case yields one state individual per distinct condition" in states
    events = _render("events")
    assert ("Origin tie-break: when the proximate producer of a happening is a system executing "
            "set rules, type it AutomaticEvent") in events
