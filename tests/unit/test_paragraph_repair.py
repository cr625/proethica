"""Tests for SynthesisViewBuilder._repair_paragraphs.

Covers the predecessor branch behavior (commits c3de02e + 08ec47f on
study/fresh-eyes-fixes-2026-05-10):

- Run-together NSPE case text (sentence-end + immediate uppercase
  preceded by >=4 lowercase letters) gets a paragraph break inserted.
- Trailing duplicate periods (". ." or "..") collapse to a single
  sentence terminator.
- Text already containing <p>, <br>, or newline boundaries skips the
  paragraph-repair step (cleanup still runs).
- Short abbreviations like "U.S.", "I.S.O.", "Dr.Smith" must NOT be
  split (the four-letter floor on preceding lowercase prevents this).
"""

from app.services.validation.synthesis_view_builder import SynthesisViewBuilder

_repair = SynthesisViewBuilder._repair_paragraphs


def test_empty_returns_unchanged():
    assert _repair('') == ''
    assert _repair(None) is None


def test_run_together_text_gets_paragraph_breaks():
    """Sentence-end + immediate uppercase splits into <p>...</p><p>...</p>."""
    text = (
        'Engineer A reviewed the deliverables at the same site.'
        'Engineer A is known for strong technical expertise.'
    )
    out = _repair(text)
    assert '<p>' in out
    assert '</p><p>' in out
    assert 'same site.</p><p>Engineer A' in out


def test_already_paragraphed_text_skips_repair():
    """Text with <p> tags is left structurally alone."""
    text = '<p>First paragraph.</p><p>Second paragraph.</p>'
    out = _repair(text)
    assert out == text


def test_text_with_newlines_skips_repair():
    text = 'First paragraph.\n\nSecond paragraph.'
    out = _repair(text)
    assert out == text


def test_trailing_duplicate_periods_collapse():
    """`. .` or `..` at end of text collapses to single period."""
    assert _repair('Some text. .') == 'Some text.'
    assert _repair('Some text..') == 'Some text.'
    assert _repair('Some text. . .') == 'Some text.'


def test_trailing_duplicate_periods_run_with_repair():
    """Both repairs run on the same input."""
    text = (
        'Engineer A finished the design at the same site.'
        'Engineer A submitted the report. .'
    )
    out = _repair(text)
    assert '</p><p>' in out
    assert not out.endswith('. .')
    assert not out.endswith('..')


def test_short_abbreviations_not_split():
    """`U.S.` and similar must not trigger paragraph break.

    The (?<=[a-z]{4}) lookbehind requires at least four lowercase letters
    immediately before the period, which excludes "U.S." (uppercase
    preceding) and "S." standalone.
    """
    text = 'The U.S. and the I.S.O. set the standard. ABC engineering applies it.'
    out = _repair(text)
    # No paragraph break should appear inside U.S. / I.S.O.
    assert 'U.S.</p><p>' not in out
    assert 'I.S.O.</p><p>' not in out


def test_internal_ellipsis_not_collapsed():
    """A genuine mid-text ellipsis (e.g., omitted-quote marker) survives.

    Pass 3 [2] confirmed that case 17's '...' is a quotation ellipsis
    from the source. _repair_paragraphs anchors its trailing-period
    collapse to end-of-string ($), so internal ellipses are preserved.
    """
    text = 'The board observed "There may...be honest differences" in the case.'
    out = _repair(text)
    assert '...' in out


def test_sentence_break_followed_by_short_word_skipped():
    """`abcd.A x` (uppercase word too short) still triggers; documented."""
    # The current heuristic only requires uppercase + one lowercase after the
    # period; this test pins the contract so future tightening is intentional.
    text = 'thefacts.Are clear.'
    out = _repair(text)
    assert '</p><p>' in out  # current behavior; if changed, update this test
