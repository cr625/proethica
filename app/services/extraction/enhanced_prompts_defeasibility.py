"""
Defeasibility edge extraction prompt builder.

Generates the LLM prompt for proethica-core v2.5.0 object properties
(competesWith, prevailsOver, defeasibleUnder) over already-extracted
Obligation and State individuals. The prompt:

  - Quotes the property axioms verbatim from proethica-core.ttl so the LLM
    cannot invent variants or misuse domain/range.
  - Passes full IRIs (not fragments) so the LLM echoes them back unchanged
    even when fragments contain non-ASCII characters (em-dashes etc.).
  - Forbids invented IRIs: subject_iri and object_iri must appear in the
    supplied entity lists.
  - Asks for one direction of competesWith only; symmetric closure is
    added in DefeasibilityEdgeExtractor.

Reference: proethica/.claude/plans/defeasibility-edge-extraction.md Phase A2.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Caller-side input dataclasses
# ---------------------------------------------------------------------------
# Decoupled from the Pydantic schemas so callers in both the live pipeline
# (Pydantic Obligation/State Individuals) and the backfill script (parsed
# rdflib graphs) can populate the same shape.

@dataclass
class ObligationContext:
    iri: str
    label: str
    statement: Optional[str] = None
    case_context: Optional[str] = None
    obligated_party: Optional[str] = None
    temporal_scope: Optional[str] = None


@dataclass
class StateContext:
    iri: str
    label: str
    state_class: Optional[str] = None
    triggering_event: Optional[str] = None
    subject: Optional[str] = None


@dataclass
class NarrativeContext:
    """Narrative datatype fragment from a related entity (Principle,
    Constraint, etc.) that may justify a defeasibility edge between
    obligations.
    """
    source_iri: str
    source_label: str
    source_field: str  # e.g. tensionresolution, balancingwith, interpretation
    text: str


# ---------------------------------------------------------------------------
# Property axioms (verbatim from proethica-core.ttl lines 241-263)
# ---------------------------------------------------------------------------

PROPERTY_AXIOMS_BLOCK = """\
proeth-core:competesWith a owl:ObjectProperty, owl:SymmetricProperty ;
    rdfs:domain proeth-core:Obligation ;
    rdfs:range proeth-core:Obligation ;
    rdfs:label "competes with"@en ;
    rdfs:comment "Relates an obligation to another obligation with which it stands in normative tension within a case. Symmetric: if O1 competes with O2 then O2 competes with O1. Does not itself specify which obligation prevails; use prevailsOver for the directed resolution."@en .

proeth-core:prevailsOver a owl:ObjectProperty ;
    rdfs:domain proeth-core:Obligation ;
    rdfs:range proeth-core:Obligation ;
    rdfs:label "prevails over"@en ;
    rdfs:comment "Relates an obligation to another obligation that it defeats under the conditions of the case. The prevailing obligation retains its force; the defeated obligation is subordinated to it. Use together with defeasibleUnder to record the State that licenses the resolution."@en .

proeth-core:defeasibleUnder a owl:ObjectProperty ;
    rdfs:domain proeth-core:Obligation ;
    rdfs:range proeth-core:State ;
    rdfs:label "defeasible under"@en ;
    rdfs:comment "Relates an obligation to a State whose obtaining renders the obligation defeasible -- that is, subject to override by a competing obligation with stronger normative support. The State specifies the context in which the obligation yields."@en .\
"""


def _load_defeasibility_template():
    """Load the editable 'defeasibility_edges' prompt template (prompt editor -> Shared prompts ->
    Ontology edges -> Defeasibility edges). A separate function so a test can inject a stub without a
    DB / app context. Raises (no fallback) if unseeded."""
    from app.models.extraction_prompt_template import ExtractionPromptTemplate
    tmpl = ExtractionPromptTemplate.get_active_template(0, 'defeasibility_edges')
    if tmpl is None:
        raise RuntimeError(
            "No 'defeasibility_edges' prompt template in extraction_prompt_templates. "
            "Seed it: docs-internal/scripts/seed_defeasibility_edges_template.py")
    return tmpl


def defeasibility_system_prompt() -> str:
    """Render the defeasibility system prompt from the editable template. The property axioms are
    injected from PROPERTY_AXIOMS_BLOCK (verbatim from proethica-core.ttl), keeping the ontology as
    the canonical source rather than baking the axioms into the editable text."""
    return _load_defeasibility_template().render_system(property_axioms_block=PROPERTY_AXIOMS_BLOCK)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _format_obligations(obligations: List[ObligationContext]) -> str:
    if not obligations:
        return "(none)"
    lines = []
    for ob in obligations:
        block = [f"- IRI: <{ob.iri}>", f"  label: {ob.label}"]
        if ob.statement:
            block.append(f"  obligationstatement: {ob.statement}")
        if ob.case_context:
            block.append(f"  casecontext: {ob.case_context}")
        if ob.obligated_party:
            block.append(f"  obligatedparty: {ob.obligated_party}")
        if ob.temporal_scope:
            block.append(f"  temporalscope: {ob.temporal_scope}")
        lines.append("\n".join(block))
    return "\n\n".join(lines)


def _format_states(states: List[StateContext]) -> str:
    if not states:
        return "(none)"
    lines = []
    for st in states:
        block = [f"- IRI: <{st.iri}>", f"  label: {st.label}"]
        if st.state_class:
            block.append(f"  stateClass: {st.state_class}")
        if st.triggering_event:
            block.append(f"  triggeringEvent: {st.triggering_event}")
        if st.subject:
            block.append(f"  subject: {st.subject}")
        lines.append("\n".join(block))
    return "\n\n".join(lines)


def _format_narratives(narratives: List[NarrativeContext]) -> str:
    if not narratives:
        return "(no additional narrative context supplied)"
    lines = []
    for n in narratives:
        lines.append(
            f"- source: <{n.source_iri}> ({n.source_label})\n"
            f"  field: {n.source_field}\n"
            f"  text: {n.text}"
        )
    return "\n\n".join(lines)


def create_defeasibility_prompt(
    obligations: List[ObligationContext],
    states: List[StateContext],
    additional_narratives: Optional[List[NarrativeContext]] = None,
    case_id: Optional[int] = None,
) -> str:
    """Render the defeasibility user prompt from the editable DB template.

    The per-entity blocks are assembled here (via _format_obligations / _format_states /
    _format_narratives) and passed as template variables; the static framing and the JSON output
    example live in the editable template. The system prompt (with the property axioms) is rendered
    separately by ``defeasibility_system_prompt()``.
    """
    case_tag = f"case {case_id}" if case_id is not None else "this case"
    additional_narratives = additional_narratives or []
    return _load_defeasibility_template().render(
        case_tag=case_tag,
        obligations_block=_format_obligations(obligations),
        states_block=_format_states(states),
        narratives_block=_format_narratives(additional_narratives),
    )
