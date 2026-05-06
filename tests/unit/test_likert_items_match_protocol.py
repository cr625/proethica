"""Asserts Likert item wording matches Protocol 2603011709 v7 Appendix A.

If this fails, either the protocol was amended without updating
likert_items.py, or items were edited in code without an amendment.
Either way, stop and reconcile before participants see drifted wording.

Source of truth: docs-internal/irb_amendment_2026-05/ProEthica_IRB_Protocol_v7.docx
                 Appendix A (lines 66-91 in the extracted text).
"""

from app.services.validation.likert_items import (
    ALL_ITEMS,
    DECS_ITEMS,
    NARR_ITEMS,
    OVERALL_ITEMS,
    PROV_ITEMS,
    QC_ITEMS,
    TIMELINE_ITEMS,
)


PROTOCOL_APPENDIX_A = {
    # Narrative View
    "narr_characters_tensions": "The character profiles and ethical tensions helped me understand who was affected and why.",
    "narr_relationships_clear": "The relationship information clarified the professional dynamics in the case.",
    "narr_ethical_significance": "This view provided a useful overview of the ethical significance of the case.",
    # Timeline View
    "timeline_temporal_sequence": "The temporal sequence of events helped me understand how the situation developed.",
    "timeline_causal_links": "The causal links between events clarified why certain actions raised ethical concerns.",
    "timeline_obligation_activation": "This view helped me identify when obligations were activated or violated.",
    # Q&C View
    "qc_issues_visible": "The extracted questions helped me see the ethical issues at stake.",
    "qc_emergence_resolution": "The connections between questions and conclusions clarified how the board reached its findings.",
    "qc_deliberation_needs": "This view helped me identify what questions an ethics review would need to address.",
    # Decisions View
    "decs_choices_understood": "The decision points helped me understand the choices the professional faced.",
    "decs_argumentative_structure": "The arguments for and against each option helped me evaluate the choices that were made.",
    "decs_actions_obligations": "This view helped me trace how the professional’s actions related to their obligations.",
    # Provisions View
    "prov_standards_identified": "The code provision mapping helped me identify which professional standards apply to this case.",
    "prov_connections_clear": "The connections between provisions and case facts were clear.",
    "prov_normative_foundation": "This view helped me understand the ethical basis for evaluating the case.",
    # Overall Assessment
    "overall_helped_understand": "The structured presentation helped me understand this case.",
    "overall_surfaced_considerations": "I could have reached the same understanding from the case facts alone.",
    "overall_useful_deliberation": "This type of structured synthesis would be useful for professional ethics deliberation.",
}


def test_eighteen_items_total():
    assert len(ALL_ITEMS) == 18, (
        f"Protocol Appendix A specifies 18 items per case; "
        f"likert_items.py declares {len(ALL_ITEMS)}."
    )


def test_three_per_view():
    for group, expected_count in [
        (NARR_ITEMS, 3),
        (TIMELINE_ITEMS, 3),
        (QC_ITEMS, 3),
        (DECS_ITEMS, 3),
        (PROV_ITEMS, 3),
        (OVERALL_ITEMS, 3),
    ]:
        assert len(group) == expected_count


def test_all_item_wording_matches_appendix_a():
    for it in ALL_ITEMS:
        expected = PROTOCOL_APPENDIX_A.get(it["name"])
        assert expected is not None, (
            f"Item {it['name']!r} has no Appendix A entry; the test fixture "
            f"is out of sync with the items module."
        )
        assert it["label"] == expected, (
            f"Wording drift on {it['name']}: protocol says {expected!r}, "
            f"code says {it['label']!r}."
        )


def test_attention_check_is_overall_reverse_coded_item():
    attn = [it for it in OVERALL_ITEMS if it.get("attention_check")]
    assert len(attn) == 1, (
        f"Exactly one attention check expected; found {len(attn)}."
    )
    item = attn[0]
    assert item["name"] == "overall_surfaced_considerations"
    assert item.get("reverse_coded") is True


def test_form_field_names_unique():
    names = [it["name"] for it in ALL_ITEMS]
    assert len(names) == len(set(names)), (
        "Form field names must be unique across all 18 items."
    )
