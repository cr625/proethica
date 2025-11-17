#!/usr/bin/env python
"""
Test the new mention-first approach for code provision extraction.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.universal_provision_detector import UniversalProvisionDetector
from app.services.provision_grouper import ProvisionGrouper


def test_case_10_scenario():
    """Test with the actual Case 10 scenario that was failing."""

    print("=" * 80)
    print("TEST: Case 10 Scenario - II.4.e vs I.4")
    print("=" * 80)

    # Simulated text from Case 10
    case_sections = {
        'discussion': """
        Because Engineer A was an officer or principal of his engineering firm,
        according to NSPE Code of Ethics Section II.4.e, Engineer A was not eligible
        to provide engineering services to Smithtown for the local road project.

        This conclusion is based upon the language of Code Section II.4.e and is
        irrespective of whether the town's procurement laws were scrupulously followed.

        Additionally, Section I.4 requires engineers to act as faithful agents or
        trustees for each employer or client.
        """
    }

    # Board provisions (from HTML)
    board_provisions = [
        {'code_provision': 'I.4', 'provision_text': 'Act for each employer or client as faithful agents or trustees.'},
        {'code_provision': 'II.4.e', 'provision_text': 'Engineers shall not solicit or accept a contract from a governmental body on which a principal or officer of their organization serves as a member.'}
    ]

    print("\n1. DETECT ALL MENTIONS")
    print("-" * 80)

    detector = UniversalProvisionDetector()
    all_mentions = detector.detect_all_provisions(case_sections)

    print(f"Found {len(all_mentions)} total mentions:\n")
    for mention in all_mentions:
        print(f"  • {mention.mentioned_provision} in {mention.section}")
        print(f"    Citation: '{mention.citation_text}'")
        print(f"    Excerpt: \"{mention.excerpt[:80]}...\"")
        print()

    print("\n2. GROUP BY BOARD PROVISION")
    print("-" * 80)

    grouper = ProvisionGrouper()
    grouped = grouper.group_mentions_by_provision(all_mentions, board_provisions)

    for provision_code, mentions in grouped.items():
        print(f"\n  {provision_code}: {len(mentions)} mentions")
        for mention in mentions:
            print(f"    - {mention.section}: '{mention.citation_text}'")

    print("\n" + "=" * 80)
    print("RESULT")
    print("=" * 80)

    # Check the key test: Are II.4.e excerpts in I.4 box?
    i4_mentions = grouped.get('I.4', [])
    ii4e_mentions = grouped.get('II.4.e', [])

    print(f"\nI.4 box: {len(i4_mentions)} mentions")
    for m in i4_mentions:
        if 'II.4.e' in m.excerpt:
            print(f"  ❌ WRONG: Contains 'II.4.e' text!")
        else:
            print(f"  ✓ Correct: Discusses I.4")

    print(f"\nII.4.e box: {len(ii4e_mentions)} mentions")
    for m in ii4e_mentions:
        if 'II.4.e' in m.excerpt:
            print(f"  ✓ Correct: Contains 'II.4.e'")

    # Final verdict
    print("\n" + "=" * 80)
    i4_has_ii4e_text = any('II.4.e' in m.excerpt for m in i4_mentions)

    if i4_has_ii4e_text:
        print("❌ FAILED: II.4.e text still appearing in I.4 box!")
    else:
        print("✅ SUCCESS: Excerpts are in correct boxes!")
    print("=" * 80)


if __name__ == '__main__':
    test_case_10_scenario()
