"""
Golden-output characterization for the synthesis-view text helpers, locking
behavior across the text_helpers extraction (plan: services-modularization.md,
Phase 2 synthesis_view_builder). _match_tokens is pure -- no DB/LLM/app context.
"""

from __future__ import annotations

from app.services.validation.synthesis_view_builder.text_helpers import _match_tokens, _CITATION_RE


def test_match_tokens_keeps_uppercase_disambiguator_letter():
    # single uppercase non-stopword letter kept (NSPE "Engineer B" disambiguator)
    assert _match_tokens("Engineer B Design") == {"engineer", "b", "design"}


def test_match_tokens_drops_stopword_letter_A():
    # 'A' -> 'a' is a stopword, so it is dropped: the disambiguator guard runs
    # AFTER the stopword filter (a quirk worth pinning).
    assert _match_tokens("Engineer A Design") == {"engineer", "design"}


def test_match_tokens_splits_hyphens_and_drops_stopwords():
    assert _match_tokens("part-time work for the firm") == {"part", "time", "work", "firm"}


def test_match_tokens_empty():
    assert _match_tokens("") == set()


def test_citation_re_matches_ber_forms():
    assert _CITATION_RE.search("Engineer A BER Case 19-3 Standards Chair")
    assert _CITATION_RE.search("Case 76-4")
    assert not _CITATION_RE.search("Engineer A Environmental Consultant")
