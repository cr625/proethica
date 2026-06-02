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
from typing import List, Tuple

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


def score_label(label: str, component_type: str | None = None) -> Tuple[float, List[str]]:
    """Return (score in [0,1], feedback list). 1.0 == ideally balanced.

    Scoring (start at 1.0, subtract penalties):
      - word count: ideal 2-5; -0.12 per word beyond 5 (long compound = scenario baked in).
      - head noun: -0.25 if the last word is not a component type (no category anchor).
      - actor markers (Engineer A, Doe, ...): -0.4 (case-specific, belongs on the individual).
      - case/precedent numbers (BER, 84-5, Case NN): -0.4.
      - more than one connector (vs / and / for / of): -0.1 per extra (multi-clause / pile-up).
    """
    words = split_camel(label)
    n = len(words)
    feedback: List[str] = []
    score = 1.0

    if n > 5:
        over = n - 5
        score -= 0.12 * over
        feedback.append(f"too long ({n} words; aim 3-5): drop the scenario, keep one qualifier")
    elif n < 2:
        score -= 0.15
        feedback.append("too short: include the component-type head noun")

    last = words[-1] if words else ""
    if last not in COMPONENT_HEADS:
        score -= 0.25
        feedback.append(f"should end in a component type ({'/'.join(sorted(COMPONENT_HEADS))})")

    if _ACTOR_RE.search(label) or _ACTOR_RE.search(" ".join(words)):
        score -= 0.4
        feedback.append("remove the named actor (case-specific; put it on the individual)")
    if _CASENUM_RE.search(label) or _CASENUM_RE.search(" ".join(words)):
        score -= 0.4
        feedback.append("remove the case/precedent number (BER / NN-N / Case NN)")

    connectors = len(_CONNECTOR_RE.findall(" ".join(words)))
    if connectors > 1:
        score -= 0.1 * (connectors - 1)
        feedback.append("collapse multi-clause / 'vs.' pile-up to at most one contrast")

    return max(0.0, min(1.0, score)), feedback
