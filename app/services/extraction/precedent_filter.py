"""Shared filter for precedent-case contamination in extracted entities.

NSPE Board opinions discuss prior BER cases by number ("BER Case 19-3", "Case
04-11"). The LLM extractors readily pull the *actors* and entities described inside
those cited precedents (e.g. "Defendant Attorney BER Case 19-3", "BER Case 04-11
Situation 1 Engineer") into the present case as first-class roles/states/etc. Those
are phantom entities: they belong to the precedent, not the case under analysis.

This centralizes the detection so every extractor (Step-1 roles, the case-pipeline
UnifiedDualExtractor, Step-3 storage, the Step-4 narrative character pass, and any future
use) applies the same rule. Matches the NSPE precedent-citation forms anywhere in a label:

  * ``BER Case 19-3`` / ``Case 04-11``  (the "Case NN-N" form)
  * ``BER 07-6`` / ``BER 84-5``         (the bare "BER NN-N" form, no "Case" keyword)
  * ``Doe`` as a standalone word         (the placeholder party name -- in NSPE opinions
                                          "Engineer Doe"/"John Doe" appear only inside cited
                                          precedents; present-case actors are "Engineer A/B/L")

The "BER NN-N" and "Doe" forms were added 2026-05-28 after the case-8 Stage-1 re-extraction
pilot showed the original "Case NN-N"-only pattern leaving ~24 phantom precedent entities
(see docs-internal/reextraction/Stage1_Pilot_Case8_Results_2026-05-28.md, Finding 1). A bare
"BER" with no following number is deliberately NOT matched, to preserve legitimate present-case
entities that merely reference precedent practice (e.g. "Engineer L BER Precedent Synthesis").
"""
from __future__ import annotations

import re

from typing import Callable, List, Tuple, TypeVar

# Actor/case-number patterns now live in one shared home (app.services.extraction.text_patterns);
# imported here under the same names so the rest of this module is unchanged. Their rationale:
#   PRECEDENT_REF_RE    - citation marker anywhere in a label/quote (BER [Case] [No.] NN-N |
#                         Case [No.] NN-N | Doe). The optional "No." token was added 2026-06-18
#                         after a clean-labeled phantom ("Public Works Director", attested only by
#                         "BER Case No. 00-5 centered on ...") slipped the "Case NN-N"-only pattern
#                         under the since-retired clean-label quote rule (the broadened pattern
#                         still serves the label-marker rule).
#   GENERIC_PRECEDENT_RE - whole-label generic precedent PLACEHOLDER ("BER Case Precedent",
#                         "Precedent Reference"). End-anchored so it does NOT touch present-case
#                         entities that merely mention precedent (e.g. "Engineer L BER Precedent
#                         Synthesis"); tolerates a trailing concept-type head noun that the D4
#                         generality reinforcement appends ("BER Case Precedent Resource").
#   _ENGINEER_LETTER_RE - a present-case engineer letter ("Engineer A"); used for the foreign-actor
#                         rule below.
from app.services.extraction.text_patterns import (
    PRECEDENT_REF_RE,
    GENERIC_PRECEDENT_RE,
    _ENGINEER_LETTER_RE,
)

T = TypeVar("T")


def is_precedent_reference(label: str | None) -> bool:
    """True if the label/quote names/derives from a cited precedent case, OR is a generic
    precedent-placeholder label with no present-case content."""
    return bool(label and (PRECEDENT_REF_RE.search(label) or GENERIC_PRECEDENT_RE.match(label)))


# Concept types for which a cited precedent is legitimate CONTENT, not contamination. The Resources
# component captures a cited BER opinion AS a case_precedent resource (the precedent IS the resource),
# so a precedent-reference label or quote is the entity itself, not a phantom pulled from inside a
# precedent. These types are exempt from the precedent-marker rule; the foreign-actor rule still
# applies (a resource carrying a foreign engineer letter is still a phantom).
# Added 2026-06-28 after the case-7 pilot dropped BER Case 90-6 and 98-3, the two precedents the
# case's entire analysis rests on.
PRECEDENT_AS_CONTENT_TYPES = frozenset({"resources"})

# The former is_precedent_entity/_all_quotes_are_precedent pair (the clean-label quote-provenance
# rule, with a NORM_CONCEPT_TYPES exemption) was removed 2026-07-04: the rule itself was retired
# from PRECEDENT_RULES on 2026-06-28 (498d316, see the RuleSet note below), leaving the pair dead
# and asserting a policy the live filter no longer enforces.


# Present-case actor consistency (added 2026-06-18, case-8 Section-C pilot, Finding B). NSPE
# opinions recap prior BER cases in the DISCUSSION section, naming their engineers by letter
# ("Engineer A"). When the present case's engineer is a different letter (case 8 = Engineer L),
# that precedent engineer and everything attributed to it are phantoms the rules above MISS: the
# recap quotes paraphrase the precedent without a case NUMBER, and "Engineer A" reads as a
# present-case actor. The reliable, per-case discriminator is structural -- an engineer letter
# that never appears in the present-case sections (facts/question/conclusion; the discussion is
# the only precedent-bearing section) is foreign. This applies to EVERY concept type including
# norms: an actor-specific precedent obligation ("Engineer A Bird Species Written Report") is a
# phantom, not a transferable abstract norm (which carries no actor letter and is untouched here).
# _ENGINEER_LETTER_RE is imported from text_patterns (see the header import block).


def present_case_actor_letters(text: str | None) -> frozenset:
    """The set of engineer letters named in present-case text (pass facts+question+conclusion,
    NOT discussion). Empty when the text is empty -- callers then skip the actor check."""
    if not text:
        return frozenset()
    return frozenset(m.group(1) for m in _ENGINEER_LETTER_RE.finditer(text))


def is_foreign_actor_entity(label: str | None, present_letters) -> bool:
    """True iff the label names one or more engineer letters and EVERY one is absent from the
    present-case set. No-op when present_letters is empty (cannot judge -> keep) or the label
    names no engineer letter (abstract entities and present-case actors are untouched). A label
    mentioning both a present and a foreign letter is kept (it involves a present-case actor)."""
    if not label or not present_letters:
        return False
    letters = {m.group(1) for m in _ENGINEER_LETTER_RE.finditer(label)}
    if not letters:
        return False
    return letters.isdisjoint(present_letters)


# --- Contamination rule set --------------------------------------------------------------------
# The three precedent-contamination checks above, declared as one coherent, inspectable RuleSet
# (see app.services.extraction.rules). Each entity-producing site (Step 1-2 extraction, Step-3
# temporal, Step-4 narrative) applies the SAME set via one call. Adding a future text-pattern
# filter is one Rule entry here, not a new scattered function + call site.
from dataclasses import dataclass

from app.services.extraction.rules import Rule, RuleSet


@dataclass(frozen=True)
class EntityContext:
    """What a precedent-contamination rule may inspect about an extracted entity."""
    label: str | None
    quotes: List[str] | None = None
    concept_type: str | None = None
    present_letters: frozenset = frozenset()


PRECEDENT_RULES: RuleSet[EntityContext] = RuleSet(
    name="precedent_contamination",
    rules=[
        Rule("precedent_marker",
             "citation marker in the label, dropped for every concept type EXCEPT those where a "
             "precedent is legitimate content (a case_precedent resource), e.g. 'Defendant BER Case 19-3'",
             lambda c: c.concept_type not in PRECEDENT_AS_CONTENT_TYPES
             and is_precedent_reference(c.label)),
        # clean_label_precedent was RETIRED 2026-06-28 (unsound; A/B audit). It dropped a fact
        # concept whenever EVERY supporting quote sat in cited-precedent context, conflating "the
        # quote CITES a precedent" with "the entity BELONGS to a precedent". A legitimate present-case
        # entity whose evidence happens to cite a prior BER case (e.g. case-7 "Precedent Reasoning
        # Capability") was discarded on both models, with zero genuine precedent contamination in the
        # case. Present-case scoping is now handled by the discussion-pass scoping prompt directive
        # (_DISCUSSION_PRESENT_CASE_DIRECTIVE in prompt_variable_resolver.py), which instructs the
        # extractor not to mint the prior case's actors/facts/reasoning as present-case entities. The
        # high-precision label-marker and foreign-actor rules below remain.
        Rule("foreign_actor",
             "an engineer letter absent from the present case (a precedent actor)",
             lambda c: is_foreign_actor_entity(c.label, c.present_letters)),
    ],
)


def is_contaminated_entity(
    label: str | None,
    quotes: List[str] | None = None,
    concept_type: str | None = None,
    present_letters=None,
) -> bool:
    """True if the entity matches any PRECEDENT_RULES rule (a citation marker in the label, or
    a foreign present-case actor). Pass present_letters (from present_case_actor_letters over
    the facts/question/conclusion sections) to enable the actor rule; omit it where the case
    context is unavailable -- the label rule still applies. quotes is accepted (EntityContext
    carries it for future rules) but no live rule currently inspects it."""
    return PRECEDENT_RULES.matches(EntityContext(
        label=label, quotes=quotes, concept_type=concept_type,
        present_letters=present_letters or frozenset()))


def drop_contaminated_entities(
    items: List[T],
    get_label: Callable[[T], str | None],
    get_quotes: Callable[[T], List[str] | None] | None = None,
    concept_type: str | None = None,
    present_letters=None,
) -> Tuple[List[T], List[str]]:
    """Partition items into (kept, dropped_labels) by the PRECEDENT_RULES set. The single
    list-level entry point for precedent-case contamination; use it at every extraction, temporal,
    and narrative site instead of stacking rule-specific passes."""
    def to_ctx(it: T) -> EntityContext:
        return EntityContext(
            label=get_label(it),
            quotes=get_quotes(it) if get_quotes else None,
            concept_type=concept_type,
            present_letters=present_letters or frozenset())

    kept, hits = PRECEDENT_RULES.partition(items, to_ctx, get_label)
    return kept, [h.label for h in hits]


_PRECEDENT_NARRATIVE_AGENT = re.compile(
    r'\bin\s+(?:BER\s+)?Case\s+\d{2}-\d{1,2}\b', re.IGNORECASE)


def is_precedent_narrative_temporal(
    label: str | None = None,
    description: str | None = None,
    agent: str | None = None,
    present_letters=None,
) -> bool:
    """True when a temporal happening (Action/Event) narrates a CITED
    precedent case rather than this case: its label is contaminated per
    is_contaminated_entity, its description opens as precedent narration
    ("In precedent BER Case 94-8, Engineer B accepted ..."), or its agent
    is qualified into another case ("Engineer B in Case 94-8").

    The 2026-07-09 Timeline audit found stage 7's label-only contamination
    check let such entries through (cases 57 and 121: eight precedent
    happenings interleaved into the case timelines) because the
    precedent-ness lives in the description/agent, not the label. Single
    source for stage-7 dropping, the timeline view's legacy-row fallback,
    and the gold backfill.
    """
    if is_contaminated_entity(label, present_letters=present_letters):
        return True
    d = (description or '').lstrip().lower()
    if d.startswith('in precedent') or 'precedent ber case' in d:
        return True
    return bool(_PRECEDENT_NARRATIVE_AGENT.search(agent or ''))
