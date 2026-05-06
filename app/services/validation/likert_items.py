"""Likert item definitions for the validation study.

Item wording is bound to Drexel IRB Protocol 2603011709 v7 Appendix A.
Any change here must be matched in the protocol document and notified
to Drexel HRPP. The wording-parity test in
tests/unit/test_likert_items_match_protocol.py catches drift.

Each item dict has:
  - name: form field name; must equal the column in
    ViewUtilityEvaluation.
  - label: verbatim text from Appendix A.
  - reverse_coded (optional): True when the item is scored inversely.
  - attention_check (optional): True for the Overall reverse-coded
    item used as an attention check (one per case).
"""

from __future__ import annotations


NARR_ITEMS = [
    {
        "name": "narr_characters_tensions",
        "label": "The character profiles and ethical tensions helped me understand who was affected and why.",
    },
    {
        "name": "narr_relationships_clear",
        "label": "The relationship information clarified the professional dynamics in the case.",
    },
    {
        "name": "narr_ethical_significance",
        "label": "This view provided a useful overview of the ethical significance of the case.",
    },
]

TIMELINE_ITEMS = [
    {
        "name": "timeline_temporal_sequence",
        "label": "The temporal sequence of events helped me understand how the situation developed.",
    },
    {
        "name": "timeline_causal_links",
        "label": "The causal links between events clarified why certain actions raised ethical concerns.",
    },
    {
        "name": "timeline_obligation_activation",
        "label": "This view helped me identify when obligations were activated or violated.",
    },
]

QC_ITEMS = [
    {
        "name": "qc_issues_visible",
        "label": "The extracted questions helped me see the ethical issues at stake.",
    },
    {
        "name": "qc_emergence_resolution",
        "label": "The connections between questions and conclusions clarified how the board reached its findings.",
    },
    {
        "name": "qc_deliberation_needs",
        "label": "This view helped me identify what questions an ethics review would need to address.",
    },
]

DECS_ITEMS = [
    {
        "name": "decs_choices_understood",
        "label": "The decision points helped me understand the choices the professional faced.",
    },
    {
        "name": "decs_argumentative_structure",
        "label": "The arguments for and against each option helped me evaluate the choices that were made.",
    },
    {
        "name": "decs_actions_obligations",
        "label": "This view helped me trace how the professional’s actions related to their obligations.",
    },
]

PROV_ITEMS = [
    {
        "name": "prov_standards_identified",
        "label": "The code provision mapping helped me identify which professional standards apply to this case.",
    },
    {
        "name": "prov_connections_clear",
        "label": "The connections between provisions and case facts were clear.",
    },
    {
        "name": "prov_normative_foundation",
        "label": "This view helped me understand the ethical basis for evaluating the case.",
    },
]

OVERALL_ITEMS = [
    {
        "name": "overall_helped_understand",
        "label": "The structured presentation helped me understand this case.",
    },
    {
        "name": "overall_surfaced_considerations",
        "label": "I could have reached the same understanding from the case facts alone.",
        "reverse_coded": True,
        "attention_check": True,
    },
    {
        "name": "overall_useful_deliberation",
        "label": "This type of structured synthesis would be useful for professional ethics deliberation.",
    },
]


ALL_VIEW_GROUPS = [
    ("Narrative", NARR_ITEMS),
    ("Timeline", TIMELINE_ITEMS),
    ("Q&C", QC_ITEMS),
    ("Decisions", DECS_ITEMS),
    ("Provisions", PROV_ITEMS),
]

ALL_ITEMS = (
    NARR_ITEMS + TIMELINE_ITEMS + QC_ITEMS + DECS_ITEMS + PROV_ITEMS + OVERALL_ITEMS
)
