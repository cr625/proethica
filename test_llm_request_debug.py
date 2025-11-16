#!/usr/bin/env python3
"""
LLM Request Debugging Test Script

Tests Anthropic API connection with progressively complex requests
to isolate the source of APIConnectionError.

Usage:
    python test_llm_request_debug.py
"""

import os
import sys
import json
import logging
from pathlib import Path

# Add proethica to path
sys.path.insert(0, str(Path(__file__).parent))

# Enable debug logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Enable httpx debug logging
import httpx
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.DEBUG)

logger = logging.getLogger(__name__)

def test_minimal_request():
    """Test 1: Absolute minimal request."""
    print("\n" + "="*70)
    print("TEST 1: Minimal Request (1 sentence)")
    print("="*70)

    try:
        import anthropic
        from httpx import Timeout

        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not set")
            return False

        client = anthropic.Anthropic(
            api_key=api_key,
            timeout=Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
        )

        prompt = "Say hello in one word."

        logger.info(f"Request: {len(prompt)} chars")

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=10,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        print(f"✓ SUCCESS: {result}")
        return True

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


def test_json_request():
    """Test 2: Request with JSON data."""
    print("\n" + "="*70)
    print("TEST 2: JSON Request")
    print("="*70)

    try:
        import anthropic
        from httpx import Timeout

        api_key = os.getenv('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(
            api_key=api_key,
            timeout=Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
        )

        prompt = """Enhance this participant:
[
  {
    "id": "p0",
    "name": "Test Engineer",
    "background": "Professional engineer",
    "motivations": ["Fulfill responsibilities"]
  }
]

Respond with JSON: {"participants": {"p0": {"enhanced_arc": "..."}}}"""

        logger.info(f"Request: {len(prompt)} chars")

        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=100,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        print(f"✓ SUCCESS: {len(result)} chars returned")
        return True

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        return False


def test_actual_prompt():
    """Test 3: Actual saved prompt from /tmp."""
    print("\n" + "="*70)
    print("TEST 3: Actual Saved Prompt")
    print("="*70)

    try:
        import anthropic
        from httpx import Timeout

        # Load saved prompt
        prompt_file = '/tmp/proethica_participant_prompt_debug.txt'
        if not os.path.exists(prompt_file):
            print(f"ERROR: Prompt file not found: {prompt_file}")
            print("Run Step 5 scenario generation first to create this file")
            return False

        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt = f.read()

        logger.info(f"Loaded prompt: {len(prompt)} chars")

        # Check for problematic characters
        control_chars = [c for c in prompt if ord(c) < 32 and c not in '\n\t\r']
        zero_width = [c for c in prompt if c in '\u200b\u200c\u200d\ufeff']
        non_printable = [c for c in prompt if not c.isprintable() and c not in '\n\t\r']

        print(f"  - Control chars: {len(control_chars)}")
        print(f"  - Zero-width: {len(zero_width)}")
        print(f"  - Non-printable: {len(non_printable)}")

        if control_chars or zero_width or non_printable:
            print("  WARNING: Problematic characters found!")

        api_key = os.getenv('ANTHROPIC_API_KEY')
        client = anthropic.Anthropic(
            api_key=api_key,
            timeout=Timeout(connect=10.0, read=60.0, write=60.0, pool=60.0)
        )

        print("  Calling API...")
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.content[0].text
        print(f"✓ SUCCESS: {len(result)} chars returned")

        # Save response
        response_file = '/tmp/proethica_test_response.txt'
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"  Response saved to: {response_file}")

        return True

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_raw_httpx():
    """Test 4: Raw httpx request (bypass Anthropic SDK)."""
    print("\n" + "="*70)
    print("TEST 4: Raw httpx Request (bypass SDK)")
    print("="*70)

    try:
        # Load saved prompt
        prompt_file = '/tmp/proethica_participant_prompt_debug.txt'
        if not os.path.exists(prompt_file):
            print(f"ERROR: Prompt file not found: {prompt_file}")
            return False

        with open(prompt_file, 'r', encoding='utf-8') as f:
            prompt = f.read()

        api_key = os.getenv('ANTHROPIC_API_KEY')

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 3000,
            "messages": [{"role": "user", "content": prompt}]
        }

        logger.info(f"Request size: {len(json.dumps(payload))} chars")

        print("  Calling API with raw httpx...")
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, headers=headers, json=payload)

        print(f"  Status: {response.status_code}")
        print(f"  Response: {len(response.text)} chars")

        if response.status_code == 200:
            print(f"✓ SUCCESS")
            return True
        else:
            print(f"✗ FAILED: {response.status_code}")
            print(f"  {response.text[:200]}")
            return False

    except Exception as e:
        print(f"✗ FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False


def generate_curl_command():
    """Generate curl command for testing."""
    print("\n" + "="*70)
    print("CURL TEST COMMAND")
    print("="*70)

    payload_file = '/tmp/proethica_request_payload.json'
    if not os.path.exists(payload_file):
        print(f"ERROR: Payload file not found: {payload_file}")
        print("Run Step 5 scenario generation first to create this file")
        return

    print(f"\nRun this command to test with curl:\n")
    print(f"curl https://api.anthropic.com/v1/messages \\")
    print(f"  -H 'content-type: application/json' \\")
    print(f"  -H 'x-api-key: $ANTHROPIC_API_KEY' \\")
    print(f"  -H 'anthropic-version: 2023-06-01' \\")
    print(f"  -d @{payload_file} \\")
    print(f"  -v")
    print(f"\nIf curl succeeds but Python fails, it's an SDK issue.")
    print(f"If curl also fails, it's a request format or network issue.\n")


def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("LLM REQUEST DEBUGGING TEST SUITE")
    print("="*70)

    results = {
        "Test 1 (Minimal)": test_minimal_request(),
        "Test 2 (JSON)": test_json_request(),
        "Test 3 (Actual Prompt)": test_actual_prompt(),
        "Test 4 (Raw httpx)": test_raw_httpx(),
    }

    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    generate_curl_command()

    # Analyze results
    print("\n" + "="*70)
    print("ANALYSIS")
    print("="*70)

    if all(results.values()):
        print("✓ All tests passed! LLM API is working correctly.")
        print("  The issue may be intermittent or environment-specific.")

    elif results["Test 1 (Minimal)"]:
        print("✓ Basic API connection works.")
        if not results["Test 2 (JSON)"]:
            print("✗ JSON formatting issue - check JSON structure")
        if not results["Test 3 (Actual Prompt)"]:
            print("✗ Issue with actual prompt - check for special characters")
        if not results["Test 4 (Raw httpx)"]:
            print("✗ SDK issue - try using raw httpx instead")
    else:
        print("✗ Cannot connect to Anthropic API at all.")
        print("  Check: API key, network connection, firewall rules")


if __name__ == '__main__':
    main()
