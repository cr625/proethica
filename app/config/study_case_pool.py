"""
Study case pool for the HT'26 user study (IRB Protocol 2603011709).

The pool consists of the 23 NSPE Board of Ethical Review opinions processed
through the pipeline with the full-text-entity-definitions-in-prompt
extraction strategy (before the later label-reference-plus-lookup refinement
was adopted). This shared extraction methodology is why the pool is locked
at these specific cases.

Selection criterion (equivalent SQL):

    SELECT id FROM documents
    WHERE document_type IN ('case','case_study')
      AND (doc_metadata->>'extraction_mode' IS NULL
           OR doc_metadata->>'extraction_mode' != 'label_only')
      AND (doc_metadata->>'year')::int >= 2021;

Publication years in the pool: 2021, 2022, 2023, 2025
(case-number years 21-9 through 24-05).

IRB Protocol §2 describes this pool as "23 NSPE Board of Ethical Review
cases, recent opinions 2017–2024." The "2017–2024" range is wider than the
actual pool; reconcile on the next protocol revision if one opens.

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
    18,   # 22-5  (2022) Professional Responsibility if Appropriate Authority Fails to Act
    19,   # 22-4  (2022) Duty to Report Misconduct
    20,   # 22-3  (2022) Review of Other Engineer's Work
    22,   # 22-2  (2022) Sharing As-Built Drawings
    56,   # 22-1  (2022) Unlicensed Practice by Nonengineers
    57,   # 21-12 (2021) Duty to Report - Material Information
    58,   # 21-11 (2021) Public Welfare at What Cost?
    59,   # 21-10 (2021) Protecting Public Health, Safety, and Welfare
    60,   # 21-9  (2021) Misrepresentation of Qualifications
]

STUDY_CASE_POOL_SIZE: int = len(STUDY_CASE_POOL_IDS)

assert STUDY_CASE_POOL_SIZE == 23, (
    f"Study pool must contain exactly 23 cases per IRB Protocol 2603011709; "
    f"got {STUDY_CASE_POOL_SIZE}"
)


def is_in_study_pool(case_id: int) -> bool:
    """True if the case is one of the 23 IRB-approved study stimuli."""
    return case_id in STUDY_CASE_POOL_IDS
