"""
Study case pool for the HT'26 user study (IRB Protocol 2603011709).

The pool consists of 19 NSPE Board of Ethical Review opinions selected from
the 23-case extraction batch on two criteria:

  1. Processed through the pipeline with the full-text-entity-definitions-
     in-prompt extraction strategy (before the later label-reference-plus-
     lookup refinement was adopted).
  2. Character-tension attribution rate >=75% in the narrative view's
     character-grouped tension display (i.e., at least three-quarters of
     extracted ethical tensions map cleanly to a specific character so the
     role-tension chain reads as designed; see
     synthesis_view_builder.get_narrative_view).

Cases removed by criterion 2 (low character-tension attribution): 18 (38%),
56 (70%), 57 (62%), 59 (70%). These cases would have presented participants
with a heavy "Other tensions" section that visually contradicts the chapter's
claim that structured presentation reveals who is implicated by which
obligation conflicts. Power-wise, the cut is well-cushioned: at the chapter's
expected n=42 completers x 3.5 cases/completer = 147 rating slots,
19 cases yield 7.7 raters/case avg vs the chapter's 5-rater floor.

Publication years in the pool: 2021, 2022, 2023, 2025
(case-number years 21-9 through 24-05).

IRB Protocol §2 describes this pool as "23 NSPE Board of Ethical Review
cases, recent opinions 2017-2024." The chapter's §4.4.4 "Case Selection
Strategy" needs a small revision to reflect the data-quality cut to 19
cases. The range "2017-2024" is wider than the actual pool; reconcile on
the next protocol revision if one opens.

Do not expand this list without an IRB amendment.
"""

from __future__ import annotations

STUDY_CASE_POOL_IDS: list[int] = [
    4,    # 24-05 (2025) Sustainable Development and Resilient Infrastructure
    5,    # 24-04 (2025) Community Engagement for Infrastructure Projects
    6,    # 24-03 (2025) Public Contracting Practices
    7,    # 24-02 (2025) Use of Artificial Intelligence in Engineering Practice
    8,    # 24-01 (2025) Balancing Client Directives and Public Welfare
    9,    # 23-4  (2023) Acknowledging Errors in Design
    10,   # 23-3  (2023) Post-Public Employment - City Engineer Transitioning
    11,   # 23-2  (2023) Excess Stormwater Runoff
    12,   # 23-1  (2023) Competence in Design Services
    13,   # 22-10 (2022) Sustainability - Lawn Irrigation Design
    14,   # 22-9  (2022) Providing Incomplete, Self-Serving Advice
    15,   # 22-8  (2022) Independence of Peer Reviewer
    16,   # 22-7  (2022) Impaired Engineering
    17,   # 22-6  (2022) Siting a Truck Stop
    # 18 removed 2026-05-08: 38% character-tension attribution (5 of 8 tensions unassigned)
    19,   # 22-4  (2022) Duty to Report Misconduct
    20,   # 22-3  (2022) Review of Other Engineer's Work
    22,   # 22-2  (2022) Sharing As-Built Drawings
    # 56 removed 2026-05-08: 70% character-tension attribution
    # 57 removed 2026-05-08: 62% character-tension attribution
    58,   # 21-11 (2021) Public Welfare at What Cost?
    # 59 removed 2026-05-08: 70% character-tension attribution
    60,   # 21-9  (2021) Misrepresentation of Qualifications
]

STUDY_CASE_POOL_SIZE: int = len(STUDY_CASE_POOL_IDS)

assert STUDY_CASE_POOL_SIZE == 19, (
    f"Study pool must contain exactly 19 cases (cut from 23 by data-quality "
    f"threshold; see module docstring); got {STUDY_CASE_POOL_SIZE}"
)


def is_in_study_pool(case_id: int) -> bool:
    """True if the case is one of the 23 IRB-approved study stimuli."""
    return case_id in STUDY_CASE_POOL_IDS
