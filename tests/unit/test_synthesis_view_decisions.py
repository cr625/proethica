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


# ---------------------------------------------------------------------------
# Evaluative-question reorder: stable partition that demotes "Was it ethical..."
# DPs so the visible top-five default opens with a forward-looking decision.
# Resolves baseline-audit Priority #2 (cases 6, 8, 13).
# ---------------------------------------------------------------------------


def test_reorder_no_decisions_passthrough():
    """Empty input returns empty list."""
    assert SynthesisViewBuilder._reorder_evaluative_decisions([]) == []


def test_reorder_no_evaluative_unchanged():
    """All-forward-looking input preserves order exactly."""
    dps = [
        _dp('Should Engineer A use AI for the report draft?', ordinal=1),
        _dp('What weight should the firm give to peer review?', ordinal=2),
        _dp('May the firm disclose the AI use to Client W?', ordinal=3),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [1, 2, 3]


def test_reorder_demotes_single_evaluative_lead():
    """Case 6 / case 8 shape: DP 1 opens 'Was it ethical for X to...'; demote."""
    dps = [
        _dp('Was it ethical for Engineer B to report suspected violations?', ordinal=1),
        _dp('Should Engineer A exhaust internal escalation channels first?', ordinal=2),
        _dp('What weight should the firm give to client confidentiality?', ordinal=3),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [2, 3, 1]


def test_reorder_demotes_consecutive_evaluative_leads():
    """Case 13 shape: DPs 1 and 2 both 'Was it ethical...'; both demoted, order preserved."""
    dps = [
        _dp('Was it ethical for Engineer Jaylani to accept the design task?', ordinal=1),
        _dp('Was it ethical for Engineer Intern Wasser to refuse?', ordinal=2),
        _dp('Should Engineer Jaylani independently evaluate the hydrogeological study?', ordinal=3),
        _dp('Should Engineer Wasser treat the design as conditionally permissible?', ordinal=4),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [3, 4, 1, 2]


def test_reorder_is_stable_within_groups():
    """Relative order within both forward and evaluative groups is preserved."""
    dps = [
        _dp('Was it ethical for X to act?', ordinal=1),
        _dp('Should A proceed?', ordinal=2),
        _dp('Was it ethical for Y to refuse?', ordinal=3),
        _dp('Should B disclose?', ordinal=4),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [2, 4, 1, 3]


def test_reorder_pattern_is_case_insensitive_and_tolerates_whitespace():
    """Regex anchored at start with optional whitespace; case-insensitive."""
    dps = [
        _dp('  Was It Ethical for X to act?', ordinal=1),
        _dp('Should A proceed?', ordinal=2),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [2, 1]


def test_reorder_matches_was_x_ethically_active_voice():
    """Broader pattern: 'Was Engineer A ethically obligated...' is also demoted.

    Case 6 has DP 1 ('Was it ethical for Engineer B...') AND DP 2 ('Was
    Engineer A ethically obligated...'); both are retrospective ethics-
    judgment phrasings and both should be demoted so the first visible
    card is forward-looking.
    """
    dps = [
        _dp('Was Engineer A ethically obligated to investigate?', ordinal=1),
        _dp('Was it ethical for Engineer B to report the violation?', ordinal=2),
        _dp('Should the firm escalate to the City Manager?', ordinal=3),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [3, 1, 2]


def test_reorder_does_not_match_was_x_obligated_without_ethical():
    """Pattern requires 'ethical' or 'ethically': 'Was X obligated' is NOT demoted.

    Case 4 DP 'Was Engineer K obligated to explore a hybrid design...' is
    retrospective in framing but does not invoke ethics directly; the audit
    did not flag it and the broader regex intentionally excludes it. Also
    excludes other plain past-tense openers that are not ethics judgments.
    """
    dps = [
        _dp('Was Engineer K obligated to explore a hybrid design solution?', ordinal=1),
        _dp('Was the firm contractually required to deliver by Q3?', ordinal=2),
        _dp('Should the firm escalate?', ordinal=3),
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [1, 2, 3]


def test_reorder_falls_back_to_description():
    """DPs missing 'decision_question' classify against 'description'."""
    dps = [
        {'description': 'Was it ethical for X to act?', 'ordinal': 1},
        {'decision_question': 'Should A proceed?', 'ordinal': 2},
    ]
    out = SynthesisViewBuilder._reorder_evaluative_decisions(dps)
    assert [d['ordinal'] for d in out] == [2, 1]
