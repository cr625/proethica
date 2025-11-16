#!/usr/bin/env python
"""
Test script for Code Provision Pattern Matching and Validation.

Tests the new 2-stage pipeline with sample text.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.code_provision_pattern_matcher import CodeProvisionPatternMatcher
from app.services.code_provision_validator import CodeProvisionValidator


def test_pattern_matcher():
    """Test the pattern matcher with various citation formats."""
    print("=" * 80)
    print("TESTING: CodeProvisionPatternMatcher")
    print("=" * 80)

    matcher = CodeProvisionPatternMatcher()

    # Test provision
    code_provision = "II.1.e"
    provision_text = "Engineers shall not aid or abet the unlawful practice of engineering"

    # Test case sections with various citation formats
    case_sections = {
        'facts': """
            Engineer Smith was employed by ABC Corp. The project required
            compliance with Section II.1.e of the NSPE Code, which prohibits
            aiding unlawful practice. The Board noted that provision II.1.e
            was central to this case.
        """,
        'discussion': """
            The case involves Section II, paragraph 1, subparagraph e.
            This provision clearly states that engineers shall not aid
            unlawful practice. The Board also considered provision I.1.e
            regarding public safety.
        """,
        'questions': """
            Did Engineer Smith's actions violate II.1.e? The Board examined
            whether the provision II-1-e applied in this context.
        """
    }

    # Find all mentions
    candidates = matcher.find_all_mentions(
        case_sections=case_sections,
        code_provision=code_provision,
        provision_text=provision_text
    )

    print(f"\nProvision: {code_provision}")
    print(f"Found {len(candidates)} candidate mentions:\n")

    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. Section: {candidate.section}")
        print(f"   Matched: '{candidate.matched_text}'")
        print(f"   Type: {candidate.match_type}")
        print(f"   Confidence: {candidate.confidence:.2f}")
        print(f"   Excerpt: \"{candidate.excerpt[:100]}...\"")
        print()

    return candidates


def test_false_positive_detection():
    """Test that validator catches false positives (II.1.e vs I.1.e)."""
    print("=" * 80)
    print("TESTING: False Positive Detection")
    print("=" * 80)

    matcher = CodeProvisionPatternMatcher()

    # We're looking for I.1.e but text mentions II.1.e
    code_provision = "I.1.e"
    provision_text = "Engineers shall hold paramount the safety, health, and welfare"

    case_sections = {
        'discussion': """
            The Board considered Section II.1.e which prohibits aiding
            unlawful practice. However, provision I.1.e regarding public
            safety is also relevant. The engineer violated I.1.e by
            approving unsafe designs.
        """
    }

    candidates = matcher.find_all_mentions(
        case_sections=case_sections,
        code_provision=code_provision,
        provision_text=provision_text
    )

    print(f"\nLooking for: {code_provision}")
    print(f"Found {len(candidates)} candidates\n")

    # Print what was found
    for candidate in candidates:
        print(f"Found: '{candidate.matched_text}' in {candidate.section}")
        print(f"       Should this match {code_provision}? ", end="")

        # Check if it's the right provision
        if candidate.matched_text.strip().rstrip('.').upper() == code_provision.upper():
            print("✓ YES - Correct match")
        else:
            print("✗ NO - This is a false positive!")
        print()

    print("\nNOTE: The validator should mark mismatched provisions as false positives")
    print("      even if the pattern matcher found them.")

    return candidates


def test_pattern_variations():
    """Test various citation format patterns."""
    print("=" * 80)
    print("TESTING: Citation Format Variations")
    print("=" * 80)

    matcher = CodeProvisionPatternMatcher()

    test_cases = [
        ("II.1.e", "Section II.1.e requires..."),
        ("II.1.e", "Provision II.1.e states..."),
        ("II.1.e", "Code II.1.e prohibits..."),
        ("II.1.e", "The engineer violated II-1-e by..."),
        ("II.1.e", "Section II, paragraph 1, subparagraph e..."),
        ("II.1.e", "II . 1 . e applies here"),
        ("I.4", "Section I.4 of the Code"),
        ("I.4", "I-4 requires paramount safety"),
    ]

    for provision, text in test_cases:
        candidates = matcher.find_all_mentions(
            case_sections={'test': text},
            code_provision=provision,
            provision_text="Test provision"
        )

        if candidates:
            print(f"✓ Found '{provision}' in: \"{text}\"")
            print(f"  Matched as: '{candidates[0].matched_text}' ({candidates[0].match_type})")
        else:
            print(f"✗ MISSED '{provision}' in: \"{text}\"")
        print()


if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("CODE PROVISION MATCHING TEST SUITE")
    print("=" * 80 + "\n")

    # Test 1: Pattern matcher
    candidates = test_pattern_matcher()

    print("\n")

    # Test 2: False positive detection
    false_positive_candidates = test_false_positive_detection()

    print("\n")

    # Test 3: Pattern variations
    test_pattern_variations()

    print("\n" + "=" * 80)
    print("TESTING COMPLETE")
    print("=" * 80)
    print("\nTo test with LLM validation:")
    print("1. Ensure ProEthica is running with ANTHROPIC_API_KEY set")
    print("2. Navigate to http://localhost:5000/scenario_pipeline/case/8/step1e")
    print("3. Click 'Extract Code Provisions'")
    print("4. Verify:")
    print("   - No false positives (II.1.e text under I.1.e)")
    print("   - All citation formats detected")
    print("   - Confidence scores correlate with match quality")
    print()
