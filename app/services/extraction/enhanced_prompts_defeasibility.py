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

import json
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


SYSTEM_PROMPT = (
    "You are a defeasibility-edge extractor for the ProEthica D-tuple model. "
    "Your task is to emit object-property triples that link previously extracted "
    "Obligation and State individuals using the three proethica-core v2.5.0 "
    "properties below. "
    "You must NOT invent classes, individuals, IRIs, or property names. "
    "Output STRICT JSON only -- no prose, no markdown fences. "
    "Property axioms (verbatim from proethica-core.ttl):\n\n"
    f"{PROPERTY_AXIOMS_BLOCK}\n\n"
    "Hard constraints:\n"
    "  1. predicate must be exactly one of: competesWith, prevailsOver, defeasibleUnder.\n"
    "  2. subject_iri and object_iri must each appear verbatim in the supplied "
    "OBLIGATIONS or STATES lists. Copy them character-for-character (including "
    "non-ASCII characters such as em-dashes).\n"
    "  3. competesWith: subject and object are both Obligations; emit ONE direction "
    "only (the inverse will be added automatically).\n"
    "  4. prevailsOver: subject is the prevailing Obligation, object is the "
    "defeated Obligation.\n"
    "  5. defeasibleUnder: subject is an Obligation, object is a State.\n"
    "  6. Every edge must be supported by a verbatim source_text drawn from one "
    "of the narrative datatype fields supplied. Set source_field to the field "
    "name (e.g. tensionresolution) and source_individual_iri to the IRI of the "
    "individual whose field supplied the quote."
)


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
            block.append(f"  stateclass: {st.state_class}")
        if st.triggering_event:
            block.append(f"  triggeringevent: {st.triggering_event}")
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
    """Build the user-side prompt for defeasibility edge extraction.

    The system prompt (`SYSTEM_PROMPT`) carries the property axioms and the
    hard constraints; this user prompt supplies the case-specific entities
    and narrative context.
    """
    case_tag = f"case {case_id}" if case_id is not None else "this case"
    additional_narratives = additional_narratives or []

    output_schema_example = {
        "edges": [
            {
                "predicate": "competesWith",
                "subject_iri": "http://proethica.org/ontology/case/72#Doe_Faithful_Agent_Obligation_Fulfilled_XYZ_Corporation_Verbal_Disclosure",
                "object_iri": "http://proethica.org/ontology/case/72#Doe_Public_Welfare_Safety_Escalation_XYZ_Discharge_Regulatory_Authority",
                "source_field": "tensionresolution",
                "source_text": "the subsequent instruction to suppress the report and the client's presentation of contradictory data at the public hearing activated the overriding public welfare obligation",
                "source_individual_iri": "http://proethica.org/ontology/case/72#Faithful_Agent_Obligation_Fulfilled_Then_Superseded_By_Ethical_Limits",
                "confidence": 0.9,
            }
        ]
    }

    return (
        f"Extract proethica-core v2.5.0 defeasibility edges from {case_tag}.\n\n"
        "OBLIGATIONS (eligible for subject_iri and object_iri on competesWith / "
        "prevailsOver, and subject_iri on defeasibleUnder):\n"
        f"{_format_obligations(obligations)}\n\n"
        "STATES (eligible for object_iri on defeasibleUnder):\n"
        f"{_format_states(states)}\n\n"
        "ADDITIONAL NARRATIVE CONTEXT (datatype fields from related entities -- "
        "Principles, Constraints, etc. -- that may justify edges between the "
        "obligations above):\n"
        f"{_format_narratives(additional_narratives)}\n\n"
        "TASK:\n"
        "Identify defeasibility edges supported by the narrative material above. "
        "Emit one competesWith direction per pair (the symmetric inverse is "
        "added automatically). When prevailsOver applies, emit the directed "
        "edge from winner to loser. When an Obligation yields under a State, "
        "emit defeasibleUnder. If no edges are warranted, return an empty "
        "edges array.\n\n"
        "OUTPUT FORMAT (strict JSON, no markdown fences):\n"
        f"{json.dumps(output_schema_example, indent=2)}\n\n"
        "Reminder: subject_iri and object_iri MUST be copied verbatim from the "
        "lists above -- do not reformat or normalize them. If you cannot find "
        "an exact IRI match for an entity you would like to reference, omit "
        "that edge."
    )


# ---------------------------------------------------------------------------
# Lightweight axiom citation for tests / debugging
# ---------------------------------------------------------------------------

DEFEASIBILITY_LITERATURE = {
    "Ganascia2007": "Defeasible logic foundations for normative reasoning",
    "GovindarajuluBringsjord2017": (
        "Obligation presupposes capacity -- defeasibleUnder grounds the "
        "yielding-state pattern"
    ),
    "KI2026Fig1": "Worked-example competition pattern (Case 72)",
}
