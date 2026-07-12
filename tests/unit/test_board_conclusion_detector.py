"""Board-disposition detector rules (semantic-audit S4 findings, 2026-07-12).

The pre-fix ordering made 'no violation' return VIOLATION (the bare-substring
check ran first; polarity inversion), and the era phrasings 'acted ethically'
/ 'has an ethical obligation to' fell through to unknown.
"""
from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer

_detect = ConclusionAnalyzer.__new__(ConclusionAnalyzer)._detect_board_conclusion_type


def test_negated_forms_win_over_bare_substrings():
    assert _detect("The Board finds no violation of the Code.") == "no_violation"
    assert _detect("This was not a violation of Section 8.") == "no_violation"
    assert _detect("Engineer A did not violate the Code.") == "no_violation"
    assert _detect("Engineer A's conduct was not unethical.") == "compliance"


def test_era_phrasings_classified():
    assert _detect("Engineers A and B acted ethically by participating.") == "compliance"
    assert _detect("Doe has an ethical obligation to report his findings.") == "recommendation"
    assert _detect("It was ethical for Firm A to seek to alter its proposal.") == "compliance"


def test_positive_forms_unchanged():
    assert _detect("Engineer A violated Section II.1.c.") == "violation"
    assert _detect("The conduct was unethical.") == "violation"
    assert _detect("The Board recommends full disclosure.") == "recommendation"
    assert _detect("Section 8 means that prior consent is required.") == "interpretation"
    assert _detect("The weather was pleasant.") == "unknown"
