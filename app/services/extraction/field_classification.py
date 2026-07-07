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

from app.services.extraction.rules import Rule, RuleSet


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
    "affects", "affectedParties", "availableTo", "usedBy", "citedBy",
    # generic per-individual relationship list (a temp_rdf field the serializer resolves into
    # peer / symmetric-property edges); structural, not a kept synthesis literal.
    "relationships", "relatedTo",
    # the attributes dict is a structural EXPANSION: the serializer flattens it to one
    # proeth:<key> datatype triple per key (license/specialty/...), so there is no single
    # proeth:attributes literal to mark. Classifying it as a kept literal made the
    # synthesisLiteral marker point at a predicate that does not exist in the graph.
    "attributes",
    # R -> P -> O dependency chain
    "hasObligation", "adheresToPrinciple", "derivedFromPrinciple",
    # obligation-capability presupposition: the capability rows' requiredForObligations
    # labels resolve (inverted) to Obligation requiresCapability Capability edges;
    # the bare requiresCapability is that edge. The Action-level requiresCapability
    # literal is demoted to requiresCapabilityText at commit (registered in _DERIVED).
    "requiresCapability", "requiredForObligations",
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
    # provisionCodes is NOT here (CONTENT, 2026-07-07 Rs properties review): only designations
    # that resolve against the NSPE registry gain containsProvision edges; unresolvable ones
    # (Canons, external-standard paragraphs -- 8 of 55 in the gold corpus) survive only as the
    # literal, so the field is not reconstructable from the graph.
    "requiresCapabilityText",                              # the committed literal (commit-time demotion of the
                                                           # Action requiresCapability field); derivable from
                                                           # agent capabilities. The bare name is the edge.
    # State candidate-class activation lists, materialized instead as the state-anchored activation/termination edges (state_edges)
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

# Kept raw-text literals that shadow a materialized edge under a DIFFERENT property name
# (no '<relation>Text' spelling): state_edges resolves these free-text event descriptions
# into the activatedByEvent / terminatedByEvent edges, while the committed literal keeps
# the verbatim description (the intermediate ontology declares both as datatype properties
# intended on State). They take the demoted-text treatment: content, not the edge.
_DEMOTED_LITERALS = {"triggeringEvent", "terminatedBy"}


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


# The classification as a coherent, inspectable rule set over the bare local name (see
# app.services.extraction.rules). Order IS the precedence: PROVENANCE > ASSESSMENT > DERIVED
# > RELATION, with the demoted "<relation>Text" rule first (a literal shadow of an object
# property is content, not the relation it mirrors). The demoted rule also covers the
# irregularly named shadows in _DEMOTED_LITERALS, and defers to an explicit _DERIVED
# registration (requiresCapabilityText derives from the graph rather than carrying kept
# content). CONTENT is the default when none match.
FIELD_RULES: RuleSet[str] = RuleSet("field_classification", [
    Rule("demoted_text",
         "a literal shadow of an object property ('<relation>Text' or an irregularly "
         "named shadow) is kept content",
         lambda local: local in _DEMOTED_LITERALS
         or (local.endswith("Text") and local not in _DERIVED
             and local[: -len("Text")] in _RELATION),
         payload=FieldKind.CONTENT),
    Rule("provenance", "extraction bookkeeping / XAI annotation",
         lambda local: local in _PROVENANCE, payload=FieldKind.PROVENANCE),
    Rule("assessment", "an LLM judgment (boolean / score / category)",
         lambda local: local in _ASSESSMENT, payload=FieldKind.ASSESSMENT),
    Rule("derived", "mechanically reconstructable from the graph",
         lambda local: local in _DERIVED, payload=FieldKind.DERIVED),
    Rule("relation", "a relationship to another individual (object-property edge)",
         lambda local: local in _RELATION, payload=FieldKind.RELATION),
])


def classify(predicate: str) -> FieldKind:
    """Classify a predicate (JSON-LD key, prefixed name, or IRI) into a FieldKind.

    Precedence: PROVENANCE > ASSESSMENT > DERIVED > RELATION > CONTENT (default). A
    ``...Text`` datatype sibling of an object property (the commit-time demotion of a
    literal placed on an object property, e.g. ``fulfillsObligationText``) is the raw-text
    literal form and classifies as CONTENT, not as the RELATION it shadows; so do the
    irregularly named state shadows (``triggeringEvent`` / ``terminatedBy``). A Text
    sibling explicitly registered in _DERIVED (``requiresCapabilityText``) stays DERIVED.
    Backed by FIELD_RULES so the vocabulary is one inspectable registry."""
    local = _normalize(predicate)
    if not local:
        return FieldKind.CONTENT
    return FIELD_RULES.classify(local, default=FieldKind.CONTENT)


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


# JSON-LD framing / identity keys that are not extracted predicates.
_STRUCTURAL_KEYS = frozenset({
    "@context", "@id", "@type", "rdfs:label", "rdfs:comment", "label", "id", "uri",
    "type", "name", "identifier", "definition", "rdf_turtle", "section_sources",
})


def group_properties(rdf_json_ld: dict) -> Dict[str, List[tuple]]:
    """Extract ``(predicate, value)`` pairs from a temporary_rdf_storage JSON-LD record and
    group them by FieldKind value. Handles both storage shapes: the pass-1/2 ``properties``
    wrapper and the temporal / step-4 top-level keys. Skips JSON-LD framing/identity keys
    and empty values. The review and provenance surfaces use this to render Relations vs
    Literal extractions (and to label each literal by kind) without bespoke per-field code."""
    groups: Dict[str, List[tuple]] = {k.value: [] for k in FieldKind}
    if not isinstance(rdf_json_ld, dict):
        return groups

    def _add(pred, val):
        if val in (None, "", [], {}):
            return
        groups[classify(pred).value].append((pred, val))

    for k, v in rdf_json_ld.items():
        if k in _STRUCTURAL_KEYS:
            continue
        if k == "properties" and isinstance(v, dict):
            for pk, pv in v.items():
                _add(pk, pv)
            continue
        _add(k, v)
    return groups
