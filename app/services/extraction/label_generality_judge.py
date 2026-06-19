"""Class-label generality judge (F3 rubric, "Balanced" style).

Deterministic 0-1 scorer + feedback for an ontology CLASS label, codifying
docs-internal/reextraction/label-generality-rubric.md. A balanced class label is
[concept] + [at most ONE distinguishing qualifier] + [component-type head noun], typically
3-5 words; case-specific detail (named actors, case/precedent numbers, multi-clause scenario
chains, "vs." pile-ups, more than one qualifier) belongs on the INDIVIDUAL, not the class.

Reused by the D4 DSPy offline prompt optimizer (as the metric) and the Tier-1 semantic repair
(as the judge with feedback). Deterministic so it needs no LLM and is stable across runs.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple

from app.services.extraction.rules import Rule, RuleSet

COMPONENT_HEADS = {
    "Obligation", "Principle", "State", "Constraint", "Capability",
    "Role", "Resource", "Action", "Event",
}

# Case-specific markers that must NOT appear in a class label.
_ACTOR_RE = re.compile(r"\b(Engineer|Client|Owner|Firm|Company|Contractor|Supplier)\s*[A-Z]\b|\bDoe\b")
_CASENUM_RE = re.compile(r"\bBER\b|\bCase\b|\d{2,4}-\d{1,3}|\b\d{2}-\d\b")
_CONNECTOR_RE = re.compile(r"\bvs\.?\b|\band\b|\bfor\b|\bof\b", re.I)


def split_camel(label: str) -> List[str]:
    """Split a CamelCase / mixed class label into words.

    Handles "ConfidentialityObligationvs.ImminentPublicDanger..." by breaking at case
    transitions, digits, and punctuation ('.', '-', 'vs').
    """
    if not label:
        return []
    s = re.sub(r"[._/]+", " ", label)
    s = s.replace("vs", " vs ")
    # break camelCase / PascalCase boundaries
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return [w for w in re.split(r"\s+", s.strip()) if w]


@dataclass(frozen=True)
class _LabelCtx:
    label: str
    words: Tuple[str, ...]
    joined: str


# The generality rubric as a coherent scoring rule set (see app.services.extraction.rules).
# Each rule's payload is ``ctx -> (penalty_weight, feedback)``; score_label sums the penalties
# of all matching rules from 1.0 and gathers their feedback. Declaration order is the feedback
# order. The actor/case-number patterns are the same notions precedent_filter checks -- a future
# step in this consolidation lifts them into one shared pattern module both draw from.
GENERALITY_RULES: RuleSet[_LabelCtx] = RuleSet("label_generality", [
    Rule("too_long", "more than 5 words: a scenario baked into the class label",
         lambda c: len(c.words) > 5,
         payload=lambda c: (0.12 * (len(c.words) - 5),
                            f"too long ({len(c.words)} words; aim 3-5): drop the scenario, keep one qualifier")),
    Rule("too_short", "fewer than 2 words",
         lambda c: len(c.words) < 2,
         payload=lambda c: (0.15, "too short: include the component-type head noun")),
    Rule("no_head_noun", "last word is not a component-type head noun (no category anchor)",
         lambda c: (c.words[-1] if c.words else "") not in COMPONENT_HEADS,
         payload=lambda c: (0.25, f"should end in a component type ({'/'.join(sorted(COMPONENT_HEADS))})")),
    Rule("actor_marker", "names a case-specific actor (belongs on the individual)",
         lambda c: bool(_ACTOR_RE.search(c.label) or _ACTOR_RE.search(c.joined)),
         payload=lambda c: (0.4, "remove the named actor (case-specific; put it on the individual)")),
    Rule("case_number", "contains a case/precedent number (BER / NN-N / Case NN)",
         lambda c: bool(_CASENUM_RE.search(c.label) or _CASENUM_RE.search(c.joined)),
         payload=lambda c: (0.4, "remove the case/precedent number (BER / NN-N / Case NN)")),
    Rule("connector_pileup", "more than one connector (vs / and / for / of): multi-clause pile-up",
         lambda c: len(_CONNECTOR_RE.findall(c.joined)) > 1,
         payload=lambda c: (0.1 * (len(_CONNECTOR_RE.findall(c.joined)) - 1),
                            "collapse multi-clause / 'vs.' pile-up to at most one contrast")),
])


def score_label(label: str, component_type: str | None = None) -> Tuple[float, List[str]]:
    """Return (score in [0,1], feedback list). 1.0 == ideally balanced.

    Starts at 1.0 and subtracts the penalty of every matching GENERALITY_RULES rule:
      - word count: ideal 2-5; -0.12 per word beyond 5 (long compound = scenario baked in).
      - head noun: -0.25 if the last word is not a component type (no category anchor).
      - actor markers (Engineer A, Doe, ...): -0.4 (case-specific, belongs on the individual).
      - case/precedent numbers (BER, 84-5, Case NN): -0.4.
      - more than one connector (vs / and / for / of): -0.1 per extra (multi-clause / pile-up).
    """
    words = split_camel(label)
    ctx = _LabelCtx(label=label, words=tuple(words), joined=" ".join(words))
    score = 1.0
    feedback: List[str] = []
    for rule in GENERALITY_RULES.collect(ctx):
        weight, message = rule.payload(ctx)
        score -= weight
        feedback.append(message)
    return max(0.0, min(1.0, score)), feedback
