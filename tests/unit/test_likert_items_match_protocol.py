"""Asserts Likert item wording matches the deployed instrument baseline.

Wording revised 2026-05-06 (post-demo advisor feedback). Items now use
the same noun phrases as the view UI labels (e.g. "Characters" rather
than "character profiles", "Causal flow" rather than "causal links",
"Argument structure" rather than "arguments for and against each option")
so that participants rate what they read rather than translating between
view labels and item phrasings. The earlier wording was the IRB Protocol
2603011709 v7 Appendix A baseline; the protocol is exempt and item
rewording does not require an amendment.

If this test fails, items were edited in code without updating the
baseline below. Stop and reconcile before participants see drifted
wording.

The reverse-coded Overall item ("I could have reached the same
understanding from the case facts alone") is unchanged from the v7
protocol baseline; rewording it would weaken the validity safeguard
documented in chapter 4 §4.4.3 and §4.5.1.
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


DEPLOYED_BASELINE = {
    # Narrative View
    "narr_characters_tensions": "The characters and ethical tensions on this view helped me understand who was affected and why.",
    "narr_relationships_clear": "The character details on this view clarified the professional relationships in the case.",
    "narr_ethical_significance": "Reading this view helped me see the ethical significance of the case.",
    # Timeline View
    "timeline_temporal_sequence": "The sequence of actions and events on this view helped me understand how the situation developed.",
    "timeline_causal_links": "The causal flow shown on this view clarified why certain actions raised ethical concerns.",
    "timeline_obligation_activation": "This view helped me see when in the timeline ethical obligations became active.",
    # Q&C View
    "qc_issues_visible": "The board questions on this view helped me see the ethical issues at stake.",
    "qc_emergence_resolution": "Seeing each board question paired with its conclusion clarified how the board reached its findings.",
    "qc_deliberation_needs": "Reading this view helped me see what questions an ethics review of this case would need to address.",
    # Decisions View
    "decs_choices_understood": "The decision points on this view helped me understand the choices the professional faced.",
    "decs_argumentative_structure": "The argument structure shown for each decision helped me evaluate the options.",
    "decs_actions_obligations": "Reading this view helped me see how each decision connected to the professional's obligations.",
    # Provisions View
    "prov_standards_identified": "The code provisions shown on this view helped me identify which professional standards apply to this case.",
    "prov_connections_clear": "The connections between each provision and the case facts on this view were clear.",
    "prov_normative_foundation": "Reading this view helped me understand the ethical basis for evaluating the case.",
    # Overall Assessment
    "overall_helped_understand": "Across all five views, the structured presentation helped me understand this case.",
    "overall_surfaced_considerations": "I could have reached the same understanding from the case facts alone.",
    "overall_useful_deliberation": "This kind of structured presentation would be useful for ethics review committees.",
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


def test_all_item_wording_matches_deployed_baseline():
    for it in ALL_ITEMS:
        expected = DEPLOYED_BASELINE.get(it["name"])
        assert expected is not None, (
            f"Item {it['name']!r} has no baseline entry; the test fixture "
            f"is out of sync with the items module."
        )
        assert it["label"] == expected, (
            f"Wording drift on {it['name']}: baseline says {expected!r}, "
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
