#!/usr/bin/env python3
"""
Automated Demo Cases Analysis Script

Runs complete extraction workflow (Passes 1-3 + Step 4) for specified cases
to prepare them for production deployment.

Usage:
    python scripts/analyze_demo_cases.py 8 10 13
    python scripts/analyze_demo_cases.py --all  # Analyzes cases 8, 10, 13
"""

import sys
import time
import json
import requests
from typing import List

# ProEthica base URL
BASE_URL = "http://localhost:5000"

# Default demo cases
DEFAULT_CASES = [8, 10, 13]


def analyze_case(case_id: int) -> bool:
    """
    Run complete extraction workflow for a single case.

    Steps:
    1. Pass 1: Roles, States, Resources (Facts + Discussion)
    2. Pass 2: Principles, Obligations, Constraints, Capabilities (Facts + Discussion)
    3. Pass 3: Actions, Events (Facts + Discussion)
    4. Step 4: Whole-Case Synthesis (Questions, Conclusions, Code Provisions)

    Returns True if all passes succeeded, False otherwise.
    """
    print(f"\n{'='*80}")
    print(f"Analyzing Case {case_id}")
    print(f"{'='*80}\n")

    # Step 1: Pass 1 - Contextual Framework (Roles, States, Resources)
    print(f"[Case {case_id}] Pass 1: Extracting Roles, States, Resources...")
    success = run_pass(case_id, "step1", "Contextual Framework")
    if not success:
        print(f"[Case {case_id}] ✗ Pass 1 failed!")
        return False
    print(f"[Case {case_id}] ✓ Pass 1 complete\n")

    # Step 2: Pass 2 - Normative Requirements
    print(f"[Case {case_id}] Pass 2: Extracting Principles, Obligations, Constraints, Capabilities...")
    success = run_pass(case_id, "step2", "Normative Requirements")
    if not success:
        print(f"[Case {case_id}] ✗ Pass 2 failed!")
        return False
    print(f"[Case {case_id}] ✓ Pass 2 complete\n")

    # Step 3: Pass 3 - Temporal Dynamics
    print(f"[Case {case_id}] Pass 3: Extracting Actions, Events...")
    success = run_pass(case_id, "step3", "Temporal Dynamics")
    if not success:
        print(f"[Case {case_id}] ✗ Pass 3 failed!")
        return False
    print(f"[Case {case_id}] ✓ Pass 3 complete\n")

    # Step 4: Whole-Case Synthesis
    print(f"[Case {case_id}] Step 4: Running Whole-Case Synthesis...")
    success = run_step4_synthesis(case_id)
    if not success:
        print(f"[Case {case_id}] ✗ Step 4 failed!")
        return False
    print(f"[Case {case_id}] ✓ Step 4 complete\n")

    print(f"[Case {case_id}] ✓ COMPLETE - All passes finished successfully!\n")
    return True


def run_pass(case_id: int, step: str, pass_name: str) -> bool:
    """
    Run a single pass extraction (Step 1, 2, or 3).

    Uses the extract_individual endpoint which handles Facts + Discussion sections.
    """
    url = f"{BASE_URL}/scenario_pipeline/case/{case_id}/{step}/extract_individual"

    try:
        # POST request with section_type (defaults to 'facts' then 'discussion')
        print(f"  → Calling {step}/extract_individual...")
        response = requests.post(
            url,
            json={"section_type": "facts"},  # Start with facts section
            timeout=300  # 5 minute timeout for LLM calls
        )

        if response.status_code == 200:
            result = response.json()
            print(f"  → Facts section: {result.get('message', 'Done')}")

            # Also extract from discussion section
            response = requests.post(
                url,
                json={"section_type": "discussion"},
                timeout=300
            )

            if response.status_code == 200:
                result = response.json()
                print(f"  → Discussion section: {result.get('message', 'Done')}")
                return True
            else:
                print(f"  ✗ Discussion extraction failed: {response.status_code}")
                print(f"     {response.text}")
                return False
        else:
            print(f"  ✗ Facts extraction failed: {response.status_code}")
            print(f"     {response.text}")
            return False

    except requests.exceptions.Timeout:
        print(f"  ✗ Extraction timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"  ✗ Error during extraction: {str(e)}")
        return False


def run_step4_synthesis(case_id: int) -> bool:
    """
    Run Step 4 Whole-Case Synthesis.

    This is a streaming endpoint, so we need to handle Server-Sent Events.
    For simplicity, we'll use a synchronous call and wait for completion.
    """
    url = f"{BASE_URL}/scenario_pipeline/case/{case_id}/synthesize_streaming"

    try:
        print(f"  → Starting synthesis...")

        # Use GET request with stream=True to handle SSE
        response = requests.get(url, stream=True, timeout=600)  # 10 minute timeout

        if response.status_code != 200:
            print(f"  ✗ Synthesis failed to start: {response.status_code}")
            return False

        # Process SSE stream
        for line in response.iter_lines():
            if line:
                line_str = line.decode('utf-8')
                if line_str.startswith('data: '):
                    data_json = line_str[6:]  # Remove 'data: ' prefix
                    try:
                        data = json.loads(data_json)

                        # Show progress
                        if 'stage' in data:
                            print(f"  → {data['stage']}")

                        # Check for completion
                        if data.get('complete'):
                            summary = data.get('summary', {})
                            print(f"  ✓ Synthesis complete:")
                            print(f"     Provisions: {summary.get('provisions_count', 0)}")
                            print(f"     Questions: {summary.get('questions_count', 0)}")
                            print(f"     Conclusions: {summary.get('conclusions_count', 0)}")
                            return True

                        # Check for errors
                        if data.get('error'):
                            print(f"  ✗ Synthesis error: {data.get('error')}")
                            return False

                    except json.JSONDecodeError:
                        pass  # Skip malformed JSON

        print(f"  ✗ Synthesis stream ended without completion")
        return False

    except requests.exceptions.Timeout:
        print(f"  ✗ Synthesis timed out after 10 minutes")
        return False
    except Exception as e:
        print(f"  ✗ Error during synthesis: {str(e)}")
        return False


def verify_server() -> bool:
    """Verify ProEthica server is running."""
    try:
        response = requests.get(f"{BASE_URL}/", timeout=5)
        if response.status_code in [200, 302]:
            print("✓ ProEthica server is running\n")
            return True
        else:
            print(f"✗ ProEthica server responded with unexpected status: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"✗ Cannot connect to ProEthica at {BASE_URL}")
        print("  Make sure ProEthica is running: python run.py")
        return False
    except Exception as e:
        print(f"✗ Error checking server: {str(e)}")
        return False


def main():
    """Main entry point."""
    print("ProEthica Demo Cases Automated Analysis")
    print("=" * 80)
    print()

    # Parse arguments
    if len(sys.argv) > 1:
        if '--all' in sys.argv:
            cases = DEFAULT_CASES
        else:
            try:
                cases = [int(arg) for arg in sys.argv[1:] if arg.isdigit()]
            except ValueError:
                print("Error: Invalid case ID(s)")
                print("Usage: python scripts/analyze_demo_cases.py 8 10 13")
                print("       python scripts/analyze_demo_cases.py --all")
                sys.exit(1)
    else:
        print("No cases specified. Using default demo cases: 8, 10, 13")
        print("To specify cases: python scripts/analyze_demo_cases.py 8 10 13")
        print()
        cases = DEFAULT_CASES

    if not cases:
        print("Error: No valid case IDs provided")
        sys.exit(1)

    print(f"Cases to analyze: {', '.join(map(str, cases))}")
    print()

    # Verify server is running
    if not verify_server():
        sys.exit(1)

    # Analyze each case
    start_time = time.time()
    results = {}

    for case_id in cases:
        success = analyze_case(case_id)
        results[case_id] = success

        if not success:
            print(f"\nCase {case_id} analysis failed. Continue with remaining cases? (y/n): ", end='')
            response = input().strip().lower()
            if response != 'y':
                break

    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total time: {elapsed/60:.1f} minutes\n")

    for case_id, success in results.items():
        status = "✓ SUCCESS" if success else "✗ FAILED"
        print(f"Case {case_id}: {status}")

    successful_cases = [case_id for case_id, success in results.items() if success]

    if len(successful_cases) == len(cases):
        print(f"\n✓ All {len(cases)} cases analyzed successfully!")
        print("\nNext steps:")
        print("  1. Verify results in web interface:")
        for case_id in successful_cases:
            print(f"     http://localhost:5000/scenario_pipeline/case/{case_id}/step4")
        print("  2. Create database backup: ./scripts/backup_demo_database.sh")
        print("  3. Deploy to production (see docs/DEPLOYMENT_CHECKLIST.md)")
        sys.exit(0)
    elif successful_cases:
        print(f"\n⚠ {len(successful_cases)}/{len(cases)} cases completed successfully")
        sys.exit(1)
    else:
        print("\n✗ All cases failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
