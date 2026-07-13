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
    # 'not unethical' re-routed to no_violation 2026-07-13 (negated-violation convention)
    assert _detect("Engineer A's conduct was not unethical.") == "no_violation"


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


def test_batch3_era_phrasings():
    """Batch-3 semantic audit round: violation-by-omission and negated-ethical
    wordings fell through to unknown; 'not unethical' routes to no_violation
    (negated-violation convention), affirmative-ethical stays compliance."""
    assert _detect("Engineer A did not fulfill her ethical obligations by informing only the administrator.") == "violation"
    assert _detect("It would not be ethical for Engineer A to be retained by the contractor.") == "violation"
    assert _detect("Engineer Z's conduct was not unethical.") == "no_violation"
    assert _detect("It was not unethical for Engineer Z to continue the representation.") == "no_violation"
    assert _detect("Engineers A and B acted ethically.") == "compliance"


def test_batch5_round3_forms():
    """Batch-5 semantic audit round: multi-situation bundles segment and
    aggregate (uniform -> that type, differing -> mixed); '(not) consistent
    with the Code' maps per polarity; a past-tense duty affirmation is a
    breach finding; a prescriptive-opening conclusion whose only 'violation'
    tokens describe a third party's legal violation stays a recommendation."""
    assert _detect(
        "Situation 1. Engineer A's actions were not consistent with the NSPE Code of Ethics."
        "Situation 2. Engineer A's actions were consistent with the NSPE Code of Ethics."
        "Situation 3. Engineer A's actions were consistent with the NSPE Code of Ethics."
    ) == "mixed"
    assert _detect(
        "Situation 1. Engineer A's actions were consistent with the NSPE Code. "
        "Situation 2. Engineer B's actions were consistent with the NSPE Code."
    ) == "no_violation"
    assert _detect(
        "Engineer F had an ethical obligation to report on the employment "
        "application the revocation of his contractor's license.") == "violation"
    assert _detect(
        "Engineer A should contact the client and point out the action is a "
        "violation of the law and that steps need to be taken to remedy the "
        "violation. If appropriate steps are not taken, Engineer A has an "
        "obligation to bring this matter to the attention of the authorities."
    ) == "recommendation"
    assert _detect(
        "Engineer A should have disclosed the defect; his failure to do so "
        "violated the Code.") == "violation"
    assert _detect(
        "It would be ethical for Engineer X or his firm to accept the "
        "contract under the stated circumstances.") == "compliance"
    assert _detect(
        "It would not be ethical for Engineer X to accept the contract."
    ) == "violation"
