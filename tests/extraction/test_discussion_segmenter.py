"""Tests for the discussion segmenter (present-case vs precedent-recap)."""
from app.services.extraction.discussion_segmenter import segment_discussion

_LINK = ('<a href="https://www.nspe.org/resources/ethics/ethics-resources/'
         'board-ethical-review-cases/x" target="_blank">BER Case 19-3</a>')


def test_deterministic_recap_then_present():
    # Two precedent recaps (each with a citation link), then a present-case cue paragraph.
    html = (
        f"<p>For example, in {_LINK}, Engineer A chairs a boiler committee while Engineer B is "
        f"retained by the plaintiff.</p>"
        f"<p>In the second situation, Engineer's business card omits the address.</p>"
        f"<p>Turning to the facts of the present situation, Engineer L signed the report without "
        f"disclosing licensure.</p>"
    )
    r = segment_discussion(html)
    assert r.method == "deterministic"
    labels = [p.label for p in r.paragraphs]
    assert labels == ["recap", "recap", "present"]
    # the precedent's boiler/Engineer A/B scenario is excluded from the present-case text
    assert "boiler" not in r.present_case_text.lower()
    assert "Engineer L" in r.present_case_text
    assert len(r.precedent_recaps) == 2


def test_no_precedent_links_is_inert():
    html = ("<p>Engineer L was retained to evaluate the design.</p>"
            "<p>Engineer L signed the report.</p>")
    r = segment_discussion(html)
    assert r.method == "none"
    assert "Engineer L was retained" in r.present_case_text
    assert r.precedent_recaps == []
    assert all(p.label == "present" for p in r.paragraphs)


def test_empty_discussion():
    r = segment_discussion("")
    assert r.method == "none" and r.present_case_text == ""


def test_link_after_cue_is_not_deterministic(monkeypatch):
    # A present-case paragraph that cites a precedent (link after the cue) is ambiguous, so the
    # deterministic path declines; with the LLM stubbed unavailable we fail safe to full text.
    import app.services.extraction.discussion_segmenter as seg
    monkeypatch.setattr(seg, "_llm_labels", lambda paras: None)
    html = (
        f"<p>Turning to the facts of the present situation, Engineer L acted.</p>"
        f"<p>This is consistent with {_LINK}, which the board applied.</p>"
    )
    r = segment_discussion(html)
    assert r.method == "fallback_full"
    # nothing dropped: present-case content is never lost when the structure is ambiguous
    assert "Engineer L acted" in r.present_case_text
