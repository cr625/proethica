"""One home for the actor-marker and case/precedent-number regexes used by the text-pattern
filters in this package.

Two filters independently inspect entity/label text for the same two *notions* -- a
case-specific actor (engineer/client/firm + a letter, or the "Doe" placeholder) and a
BER/precedent case number -- but for DIFFERENT purposes and with DELIBERATELY DIFFERENT
patterns:

  * ``precedent_filter`` DROPS phantom precedent entities, so its patterns are tuned to NSPE
    precedent-citation forms ("BER Case 19-3", "Engineer A" foreign to the present case).
  * ``label_generality_judge`` SCORES a class label's generality, so its patterns are broader
    actor/case-number heuristics ("remove the named actor", "remove the case number").

The patterns are NOT interchangeable (different actor sets, different boundary and number
handling) and MUST NOT be merged or altered -- moving them here only gives the actor/case-number
notions a single, inspectable home. Each pattern is copied byte-for-byte from its original site.
"""
from __future__ import annotations

import re

# === precedent_filter patterns (drop phantom precedent entities) =========================

# Precedent-citation marker anywhere in a label/quote (BER [Case] [No.] NN-N | Case [No.] NN-N).
# Used by precedent_filter.is_precedent_reference. The former "|\bDoe\b" alternative moved to
# PLACEHOLDER_ACTOR_RE (2026-07-11, rebuild batch 1): in modern opinions Doe appears only inside
# cited precedents, but pre-1980s cases use Doe/Roe as the PRESENT case's party names (NSPE
# 76-4's protagonist IS "Engineer Doe"), so unconditional matching dropped 16 present-case
# individuals across six components. Placeholder names are now judged per case against the
# present-case sections (precedent_filter placeholder_actor rule), like the engineer-letter rule.
PRECEDENT_REF_RE = re.compile(
    r"\bBER\s+(?:Case\s+)?(?:No\.?\s+)?\d{2}-\d{1,2}\b"
    r"|\bCase\s+(?:No\.?\s+)?\d{2}-\d{1,2}\b",
    re.IGNORECASE,
)

# NSPE placeholder party surnames (Doe and its companion Roe). Contamination markers ONLY when
# the name is foreign to the present case; see precedent_filter.is_foreign_placeholder_entity.
PLACEHOLDER_ACTOR_RE = re.compile(r"\b(Doe|Roe)\b", re.IGNORECASE)

# Concept-type head nouns appended to labels by the D4 generality reinforcement; embedded into
# GENERIC_PRECEDENT_RE so a bare placeholder plus its head noun still matches.
_CONCEPT_HEAD_NOUNS = (
    r"Resource|State|Role|Principle|Obligation|Constraint|Capability|Action|Event"
)

# Whole-label generic precedent PLACEHOLDER (e.g. "BER Case Precedent", "Precedent Reference",
# "BER Case Precedent Resource"); end-anchored. Used by precedent_filter.is_precedent_reference.
GENERIC_PRECEDENT_RE = re.compile(
    r"^\s*(?:BER\s+)?(?:Case\s+)?Precedent"
    r"(?:\s+(?:Reference|Case))?"
    rf"(?:\s+(?:{_CONCEPT_HEAD_NOUNS})s?)?"
    r"\s*$",
    re.IGNORECASE,
)

# A present-case engineer letter ("Engineer A", "Engineers A"). Used by precedent_filter to
# collect present-case actor letters and to detect foreign (precedent) actors.
_ENGINEER_LETTER_RE = re.compile(r"\bEngineers?\s+([A-Z])\b")


# === label_generality_judge patterns (score a class label's generality) ==================

# Case-specific actor marker that must NOT appear in a CLASS label (broader actor set than the
# precedent filter; intentionally distinct). Used by label_generality_judge actor_marker rule.
_ACTOR_RE = re.compile(r"\b(Engineer|Client|Owner|Firm|Company|Contractor|Supplier)\s*[A-Z]\b|\bDoe\b")

# Case/precedent number marker that must NOT appear in a CLASS label (BER / Case / NN-NN / NN-N).
# Used by label_generality_judge case_number rule. Distinct from the precedent filter's number
# handling on purpose.
_CASENUM_RE = re.compile(r"\bBER\b|\bCase\b|\d{2,4}-\d{1,3}|\b\d{2}-\d\b")
