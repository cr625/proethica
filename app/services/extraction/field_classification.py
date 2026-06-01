"""Single source of truth for classifying an extracted predicate as a structural
relation vs a descriptive/assessment literal.

The review pages exist to show the extracted *structural triples* faithfully, but the
extraction emits a mixture: object-property relations (which become edges), irreducible
literal content (statements, the NESS causal analysis, descriptions), LLM judgments
(confidence, severity, compliance), literals that merely duplicate a materialized edge or
are reconstructable from the graph, and provenance bookkeeping. This module gives every
predicate one classification so the serializer, the provenance view, the temporal review,
and the synthesis hand-off all agree on which is which.

It is curated (not ontology-introspecting) on purpose: the review and provenance surfaces
read ``temporary_rdf_storage`` JSON-LD, where would-be edges are still *label strings*
(the appliers resolve them to IRIs only at commit), so object-type inspection is not
available there. The vocabulary is finite and stable (it tracks the edge appliers in
``edge_materialization.py`` + ``rpo_edges.ALL_EDGE_RANGE`` and the audit in
``docs-internal/reextraction/review-vs-synthesis-fields.md``); add a predicate here when a
new field is introduced.

Classes (see the registry for the rationale of each):
  RELATION    - a relationship to another individual; is or becomes an object-property edge.
  CONTENT     - kept literal carrying irreducible source content (not reconstructable
                from the graph; the capture-point rule). The default.
  ASSESSMENT  - kept literal that is an LLM judgment (boolean / score / category).
  DERIVED     - literal mechanically reconstructable from the graph (a count, an ordinal
                that equals a label, a literal duplicating a materialized edge).
  PROVENANCE  - extraction bookkeeping / XAI annotations.

``CONTENT`` and ``ASSESSMENT`` together are the *synthesis literals*: the kept,
non-structural values synthesis should carry forward. ``RELATION`` is the structural
triple set. ``DERIVED`` / ``PROVENANCE`` are neither (reconstructable / bookkeeping).
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Dict, Iterable, List


class FieldKind(str, Enum):
    RELATION = "relation"
    CONTENT = "content"
    ASSESSMENT = "assessment"
    DERIVED = "derived"
    PROVENANCE = "provenance"


# --- curated sets (bare local names; numbered/Text variants normalized in classify) ----

# Relationships to other individuals: object-property edges, or the temp_rdf label
# fields that the commit-time appliers resolve into such edges.
_RELATION = {
    # actor-anchored (participant + role/resource/state actor edges)
    "hasRole", "actor",
    "obligatedParty", "constrainedEntity", "possessedBy", "invokedBy", "hasCapability",
    "affects", "affectedParties", "availableTo", "usedBy",
    # R -> P -> O dependency chain
    "hasObligation", "adheresToPrinciple", "derivedFromPrinciple",
    # defeasibility
    "competesWith", "prevailsOver", "defeasibleUnder",
    # state-anchored activation/termination
    "activatesObligation", "activatesConstraint", "activatedByEvent", "terminatedByEvent",
    # Event-Calculus fluent transitions
    "initiates", "terminates",
    # action normative engagement
    "fulfillsObligation", "violatesObligation", "raisesObligation", "guidedByPrinciple",
    # provision citation
    "citesProvision",
    # causal-chain endpoints (cause/effect/responsibleAgent minted as edges; see causal_edges.py)
    "cause", "effect", "responsibleAgent", "causedByAction",
    # Step-4 argument / conclusion relations to named entities
    "answersQuestion", "claimEntity", "warrantEntity", "backingProvision",
    "qualifierConstraint", "validatesArgument", "validatesObligationRef",
}

# LLM judgments: booleans, scores, categorical ratings. Not relations.
_ASSESSMENT = {
    # situational / normative component judgments
    "confidence", "complianceStatus", "urgencyLevel", "severity", "proficiencyLevel",
    # action / causal judgments
    "withinCompetence", "responsibilityType", "withinAgentControl",
    # decision-option board choice
    "isBoardChoice",
    # Step-4 argument validation block
    "isValid", "validationScore", "validationNote", "entityValidationPassed",
    "missingEntity", "foundingValueCompliant", "foundingValueAnalysis",
    "virtueValidationPassed", "missingVirtue", "confidenceScore", "foundingGoodAnalysis",
    "argumentType", "extractionReasoning",
}

# Literals mechanically reconstructable from the graph (counts, ordinals == label,
# literals duplicating a materialized edge, derivable-from-agent-layer attributes).
_DERIVED = {
    "totalElements", "actionCount", "eventCount",          # timeline counts
    "owlTimeProperty", "fromEntityText", "toEntityText",   # Allen-relation literal duplicates
    "conclusionNumber", "questionNumber", "argumentId",    # ordinals / handles == label
    "citedProvision",                                      # duplicated by the citesProvision edge
    "requiresCapability",                                  # action competence: derivable from agent capabilities
    # State candidate-class activation lists, materialized instead as state/fluent edges
    "obligationActivation", "actionConstraints",
    "activationConditions", "terminationConditions",
}

# Extraction bookkeeping + XAI annotations (mirrors _PROV_PROP_KEYS in
# ontserve_commit_service.py plus the matcher-decision annotation props and our own marker).
_PROVENANCE = {
    "generatedAtTime", "wasAttributedTo", "wasGeneratedBy",
    "firstDiscoveredInCase", "firstDiscoveredAt", "discoveredInCase",
    "discoveredInSection", "discoveredInPass", "sourceText",
    "matchedOntologyClass", "matchedOntologyLabel", "matchConfidence",
    "matchesExisting", "matchReasoning",
    "synthesisLiteral",
}

_TRAILING_DIGITS = re.compile(r"\d+$")


def _normalize(predicate: str) -> str:
    """Reduce a JSON-LD key / IRI fragment to a bare local name for lookup.

    Strips a namespace prefix (``proeth:foo`` / ``proeth-core:foo`` / a full IRI) and a
    trailing index (``option3`` -> ``option``, ``causalStep2`` -> ``causalStep``).
    """
    if not predicate:
        return ""
    local = predicate
    if "#" in local:
        local = local.rsplit("#", 1)[-1]
    if "/" in local:
        local = local.rsplit("/", 1)[-1]
    if ":" in local:
        local = local.rsplit(":", 1)[-1]
    local = _TRAILING_DIGITS.sub("", local)
    return local


def classify(predicate: str) -> FieldKind:
    """Classify a predicate (JSON-LD key, prefixed name, or IRI) into a FieldKind.

    Precedence: PROVENANCE > ASSESSMENT > DERIVED > RELATION > CONTENT (default). A
    ``...Text`` datatype sibling of an object property (the commit-time demotion of a
    literal placed on an object property, e.g. ``fulfillsObligationText``) is the raw-text
    literal form and classifies as CONTENT, not as the RELATION it shadows.
    """
    local = _normalize(predicate)
    if not local:
        return FieldKind.CONTENT

    # A demoted "<relation>Text" literal is content, not the relation it mirrors.
    if local.endswith("Text"):
        base = local[: -len("Text")]
        if base in _RELATION:
            return FieldKind.CONTENT

    if local in _PROVENANCE:
        return FieldKind.PROVENANCE
    if local in _ASSESSMENT:
        return FieldKind.ASSESSMENT
    if local in _DERIVED:
        return FieldKind.DERIVED
    if local in _RELATION:
        return FieldKind.RELATION
    return FieldKind.CONTENT


def is_synthesis_literal(predicate: str) -> bool:
    """True if the predicate is a kept literal synthesis should carry (CONTENT or
    ASSESSMENT). Excludes relations (structural), derived (reconstructable), and
    provenance (bookkeeping)."""
    return classify(predicate) in (FieldKind.CONTENT, FieldKind.ASSESSMENT)


def synthesis_literals(predicates: Iterable[str]) -> List[str]:
    """The subset of ``predicates`` that are kept synthesis literals (CONTENT/ASSESSMENT),
    de-duplicated, order preserved. This is what the synthesisLiteral provenance marker
    enumerates and what the synthesis layer carries forward."""
    seen, out = set(), []
    for p in predicates:
        if p in seen:
            continue
        seen.add(p)
        if is_synthesis_literal(p):
            out.append(p)
    return out


def partition(predicates: Iterable[str]) -> Dict[str, List[str]]:
    """Group predicates by FieldKind value -> list of predicates (original spelling kept).
    Used by the provenance and temporal-review surfaces to render Relations vs Literal
    extractions distinctly."""
    groups: Dict[str, List[str]] = {k.value: [] for k in FieldKind}
    for p in predicates:
        groups[classify(p).value].append(p)
    return groups
