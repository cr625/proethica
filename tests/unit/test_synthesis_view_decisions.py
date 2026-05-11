"""Decisions-view dedup tests.

Covers the predecessor branch behavior (commit 6199b9b on
study/fresh-eyes-fixes-2026-05-10): _dedupe_decision_points drops
near-duplicate decision points produced by Step 4 Phase 3 so the
Decisions view does not surface "unfinished analysis" duplicate cards
to the participant.

Three signals trigger a drop:
  1. Normalized 40-char prefix equality.
  2. Content-word Jaccard >= 0.55.
  3. First 6 content tokens share >= 5 (catches rephrasings whose
     trailing detail diverges).

Earliest-by-ordinal wins.
"""

from app.services.validation.synthesis_view_builder import SynthesisViewBuilder


def _dp(question, ordinal=1):
    return {
        'decision_question': question,
        'description': '',
        'ordinal': ordinal,
    }


def test_no_decisions_no_dedup():
    """Empty input returns empty list."""
    assert SynthesisViewBuilder._dedupe_decision_points([]) == []


def test_distinct_decisions_kept():
    """Genuinely distinct decision points are not deduped."""
    dps = [
        _dp('Should Engineer A use AI for the report draft?'),
        _dp('Should Client W be informed of the AI use after submission?'),
        _dp('What weight should the firm give to the missing peer review?'),
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 3


def test_dedup_on_normalized_prefix_equality():
    """Two questions whose first 40 normalized chars match dedupe to one."""
    dps = [
        _dp('Engineer A uploaded Client W confidential site data to the AI.'),
        _dp('Engineer A uploaded Client W confidential site data into ChatGPT.'),
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 1
    assert out[0]['decision_question'].endswith('to the AI.')  # earliest wins


def test_dedup_on_token_jaccard():
    """Heavy content-word overlap collapses near-duplicates."""
    dps = [
        _dp('Should Engineer A disclose the AI tool use to Client W in the report?'),
        _dp('Engineer A should disclose AI tool use to Client W during report review.'),
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 1


def test_dedup_on_first_six_tokens_overlap():
    """Rephrasings that share the first six content tokens dedupe."""
    dps = [
        _dp('Engineer A authorship integrity report submission verification responsibility extends to AI-generated text.'),
        _dp('Engineer A authorship integrity report submission verification with respect to AI tool outputs.'),
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 1


def test_dedup_preserves_first_in_ordinal_order():
    """When multiple distinct sets dedupe, the earliest representative survives."""
    dps = [
        _dp('Engineer A uploaded Client W data to AI.', ordinal=1),
        _dp('Engineer A uploaded Client W data into the model.', ordinal=2),
        _dp('Engineer A uploaded Client W data using a public API.', ordinal=3),
        _dp('Should Client W be informed of the AI use after submission?', ordinal=4),
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 2
    assert out[0]['ordinal'] == 1
    assert out[1]['ordinal'] == 4


def test_dedup_handles_missing_question_field():
    """Decision points missing 'decision_question' fall back to 'description'."""
    dps = [
        {'description': 'Engineer A uploaded confidential site data to AI tool.'},
        {'description': 'Engineer A uploaded confidential site data to AI service.'},
        {'decision_question': 'Should the firm pause AI use until policy is set?'},
    ]
    out = SynthesisViewBuilder._dedupe_decision_points(dps)
    assert len(out) == 2
