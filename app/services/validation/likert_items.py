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
        "label": "The characters and ethical tensions on this view helped me understand who was affected and why.",
    },
    {
        "name": "narr_relationships_clear",
        "label": "The character details on this view clarified the professional relationships in the case.",
    },
    {
        "name": "narr_ethical_significance",
        "label": "Reading this view helped me see the ethical significance of the case.",
    },
]

TIMELINE_ITEMS = [
    {
        "name": "timeline_temporal_sequence",
        "label": "The sequence of actions and events on this view helped me understand how the situation developed.",
    },
    {
        "name": "timeline_causal_links",
        "label": "The causal flow shown on this view clarified why certain actions raised ethical concerns.",
    },
    {
        "name": "timeline_obligation_activation",
        "label": "This view helped me see when in the timeline ethical obligations became active.",
    },
]

QC_ITEMS = [
    {
        "name": "qc_issues_visible",
        "label": "The board questions on this view helped me see the ethical issues at stake.",
    },
    {
        "name": "qc_emergence_resolution",
        "label": "Seeing each board question paired with its conclusion clarified how the board reached its findings.",
    },
    {
        "name": "qc_deliberation_needs",
        "label": "Reading this view helped me see what questions an ethics review of this case would need to address.",
    },
]

DECS_ITEMS = [
    {
        "name": "decs_choices_understood",
        "label": "The decision points on this view helped me understand the choices the professional faced.",
    },
    {
        "name": "decs_argumentative_structure",
        "label": "The argument structure shown for each decision helped me evaluate the options.",
    },
    {
        "name": "decs_actions_obligations",
        "label": "Reading this view helped me see how each decision connected to the professional's obligations.",
    },
]

PROV_ITEMS = [
    {
        "name": "prov_standards_identified",
        "label": "The code provisions shown on this view helped me identify which professional standards apply to this case.",
    },
    {
        "name": "prov_connections_clear",
        "label": "The connections between each provision and the case facts on this view were clear.",
    },
    {
        "name": "prov_normative_foundation",
        "label": "Reading this view helped me understand the ethical basis for evaluating the case.",
    },
]

OVERALL_ITEMS = [
    {
        "name": "overall_helped_understand",
        "label": "Across all five views, the structured presentation helped me understand this case.",
    },
    {
        "name": "overall_surfaced_considerations",
        "label": "I could have reached the same understanding from the case facts alone.",
        "reverse_coded": True,
        "attention_check": True,
    },
    {
        "name": "overall_useful_deliberation",
        "label": "This kind of structured presentation would be useful for ethics review committees.",
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
