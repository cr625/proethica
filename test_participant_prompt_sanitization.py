#!/usr/bin/env python3
"""
Test script for validating participant mapper prompt sanitization.

Run this BEFORE enabling LLM to verify prompts are clean.

Usage:
    python test_participant_prompt_sanitization.py
"""

import sys
import os
import json
import re

# Add proethica to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Document, db
from app.services.scenario_generation.participant_mapper import ParticipantMapper
from app.services.scenario_generation.data_collection import ScenarioDataCollector
from app import create_app


def test_prompt_sanitization(case_id=8):
    """
    Test prompt generation and sanitization for a specific case.

    Returns:
        bool: True if sanitization passed all checks, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"Testing Participant Prompt Sanitization for Case {case_id}")
    print(f"{'='*70}\n")

    app = create_app()

    with app.app_context():
        # Get roles from database
        collector = ScenarioDataCollector()
        data = collector.collect_all_data(case_id)

        roles = data.get_entities_by_type('Role')
        if not roles:
            roles = data.get_entities_by_type('Roles')

        print(f"✓ Loaded {len(roles)} roles from database\n")

        # Create participant mapper
        mapper = ParticipantMapper()

        # Map participants (without LLM enhancement)
        result = mapper.map_participants(roles, timeline_data=None)

        print(f"✓ Created {len(result.participants)} participant profiles\n")

        # Generate prompt using internal method
        prompt = mapper._create_enhancement_prompt(result.participants, result.relationship_map)

        print(f"{'─'*70}")
        print("PROMPT VALIDATION CHECKS")
        print(f"{'─'*70}\n")

        # Check 1: Prompt length
        print(f"1. Prompt Length Check:")
        print(f"   Length: {len(prompt):,} characters")
        print(f"   Status: {'✓ PASS' if len(prompt) > 0 else '✗ FAIL'}\n")

        # Check 2: Control characters
        print(f"2. Control Character Check:")
        control_chars = [c for c in prompt if ord(c) < 32 and c not in '\n\t\r ']
        if control_chars:
            print(f"   Found: {len(control_chars)} control characters")
            print(f"   Codes: {[ord(c) for c in control_chars[:10]]}")
            print(f"   Status: ✗ FAIL - Control characters found!\n")
            return False
        else:
            print(f"   Found: 0 control characters")
            print(f"   Status: ✓ PASS\n")

        # Check 3: JSON validation
        print(f"3. JSON Structure Check:")
        try:
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', prompt, re.DOTALL)
            if json_match:
                test_json = json.loads(json_match.group(1))
                participant_count = len(test_json.get('participants', {}))
                print(f"   Participants: {participant_count}")
                print(f"   Status: ✓ PASS - Valid JSON\n")
            else:
                print(f"   Status: ✗ FAIL - Could not extract JSON from prompt\n")
                return False
        except json.JSONDecodeError as e:
            print(f"   Error: {e}")
            print(f"   Status: ✗ FAIL - Invalid JSON\n")
            return False

        # Check 4: Character encoding
        print(f"4. Character Encoding Check:")
        try:
            prompt.encode('utf-8')
            print(f"   Encoding: UTF-8")
            print(f"   Status: ✓ PASS\n")
        except UnicodeEncodeError as e:
            print(f"   Error: {e}")
            print(f"   Status: ✗ FAIL - Encoding error\n")
            return False

        # Check 5: Newline normalization
        print(f"5. Newline Normalization Check:")
        crlf_count = prompt.count('\r\n')
        cr_count = prompt.count('\r') - crlf_count  # Don't double-count CRLF
        lf_count = prompt.count('\n') - crlf_count  # Don't double-count CRLF
        print(f"   CRLF (\\r\\n): {crlf_count}")
        print(f"   CR (\\r): {cr_count}")
        print(f"   LF (\\n): {lf_count}")
        if cr_count > 0 or crlf_count > 0:
            print(f"   Status: ⚠ WARNING - Non-LF newlines found (may cause issues)\n")
        else:
            print(f"   Status: ✓ PASS\n")

        # Save prompt to file for manual inspection
        output_file = '/tmp/participant_prompt_test.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(prompt)

        print(f"{'─'*70}")
        print(f"PROMPT SAVED FOR INSPECTION")
        print(f"{'─'*70}\n")
        print(f"File: {output_file}")
        print(f"Size: {len(prompt):,} characters\n")

        # Summary
        print(f"{'='*70}")
        print(f"SUMMARY: ✓ ALL CHECKS PASSED")
        print(f"{'='*70}\n")
        print(f"The prompt is ready for LLM submission.")
        print(f"Review the saved file to verify content quality.\n")

        return True


if __name__ == '__main__':
    success = test_prompt_sanitization()
    sys.exit(0 if success else 1)
