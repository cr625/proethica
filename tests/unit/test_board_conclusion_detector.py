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


def test_batch6_fulfilled_duty_forms():
    """Batch-6 audit round: a fulfilled/discharged duty is a compliance
    verdict; negated fulfillment stays a violation."""
    assert _detect(
        "Engineer A has fulfilled his ethical obligation by taking prudent "
        "action in notifying the town supervisor. However, Engineer A should "
        "also notify the new owner in writing.") == "compliance"
    assert _detect(
        "Engineer A had not fulfilled his ethical obligation to notify the "
        "owner.") == "violation"
    assert _detect(
        "Engineer A is free to pursue employment with Company Y provided "
        "Engineer A does not disclose any confidential design information."
    ) == "recommendation"


def test_batch7_exoneration_forms():
    """Batch-7 audit round: negated-deception and no-conflict clearances are
    no-violation findings even when 'should' appears in the sentence."""
    assert _detect(
        "Engineer A is certainly free to disclose his autism if he so "
        "chooses. However, the NSPE Code of Ethics does not compel "
        "disclosure nor does a failure to disclose somehow constitutes a "
        "“deception.”") == "no_violation"
    assert _detect(
        "Engineer A’s role as a private forensic engineering expert "
        "should not present any clear or apparent conflict of interest. "
        "Engineer A has an obligation to (1) fully disclose to Attorney X "
        "his role on the committee.") == "no_violation"


def test_batch8_round5_forms():
    """Batch-8 audit round: duty-scope holdings are interpretations; the
    adverb form 'not ethically <verb>' never reads as a verdict; fulfilled
    duty without a possessive; 'did not act ethically'; misconduct bundled
    with a report duty -> mixed."""
    assert _detect(
        "Clear reporting of unresolved public health and safety risks to "
        "appropriate authorities satisfies Engineer B's obligation to "
        "protect public health, safety and welfare.") == "interpretation"
    assert _detect(
        "Any additional steps taken beyond the notification of appropriate "
        "authorities are not an obligation of Engineer B but rather a "
        "personal choice as a citizen, and should be taken with due "
        "consideration.") == "interpretation"
    assert _detect(
        "Owner and Engineer B are not required to obtain Engineer A's "
        "consent to the peer review. Engineer A may not ethically object "
        "to the peer review.") == "recommendation"
    assert _detect(
        "Engineer B is ethically required to make certain that Engineer A "
        "is advised of the planned peer review.") == "recommendation"
    assert _detect(
        "Engineer R fulfilled ethical obligations regarding environmental "
        "concerns at the site of the truck stop through public testimony."
    ) == "compliance"
    assert _detect(
        "Engineer H did not act ethically by failing to address the "
        "potential for leaking fuel.") == "violation"
    assert _detect(
        "Engineer B's proposal and marketing practices would constitute "
        "professional misconduct per licensure law in State Z, and "
        "Engineer A has a clear obligation to report to the engineering "
        "licensing board in State Z.") == "mixed"
    assert _detect(
        "Engineer A's use of AI in report writing was partly ethical, and "
        "partly unethical.") == "mixed"
    assert _detect(
        "Since the City D Engineer indicated they have no plans to change "
        "the contract arrangement with Firm Z, Engineer A is obligated to "
        "take appropriate action.") == "recommendation"
    assert _detect(
        "The use of AI-assisted drafting tools by Engineer A was not "
        "unethical per se. However, Engineer A's misuse of the tool, by "
        "failing to maintain Responsible Charge, was unethical.") == "mixed"
    assert _detect(
        "Engineer A does not have an obligation to report Engineer B's "
        "practices to the engineering licensing board in State Q."
    ) == "no_violation"
    assert _detect(
        "Engineer A has no professional or ethical obligation to disclose "
        "AI use to Client W. However, engineers integrating AI should "
        "adopt rigorous verification processes.") == "mixed"


def test_gold_audit_round5b_forms():
    """Gold-audit round: the board's own 'the answer is mixed'; past-duty
    breach bundled with a permissibility clearance; conditional duty-trigger
    holdings are interpretations."""
    assert _detect(
        "As to whether it would be ethical for Engineer D to be immediately, "
        "directly involved with AE&R's projects with the City, the answer is "
        "mixed as multiple considerations and details will affect the "
        "outcome.") == "mixed"
    assert _detect(
        "Engineer A was obligated to report Engineer B to the proper "
        "authority, in this case the State Board. As Engineer B's friend and "
        "with Engineer B's approval, once the matter was reported to the "
        "Board, it would have been permissible for Engineer A to help "
        "cooperatively identify a temporary practice management alternative."
    ) == "mixed"
    assert _detect(
        "If Engineer A reasonably believes that the probability of property "
        "damage is high and that the probable amount of property damage is "
        "significant, Engineer A has a duty to advise the Owner/Client of "
        "the risk.") == "interpretation"
