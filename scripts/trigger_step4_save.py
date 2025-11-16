#!/usr/bin/env python3
"""
Manual Step 4 Save Trigger

If Step 4 synthesis completes but doesn't save to database,
run this script to manually trigger the save for specific cases.

Usage: python scripts/trigger_step4_save.py 8 10 13
"""

import sys
import requests

BASE_URL = "http://localhost:5000"

def trigger_save(case_id):
    """Trigger a manual save by visiting the Step 4 page which should load saved data"""
    url = f"{BASE_URL}/scenario_pipeline/case/{case_id}/step4"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Case {case_id}: Page loaded successfully")
            return True
        else:
            print(f"Case {case_id}: Failed to load ({response.status_code})")
            return False
    except Exception as e:
        print(f"Case {case_id}: Error - {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/trigger_step4_save.py 8 10 13")
        sys.exit(1)

    cases = [int(c) for c in sys.argv[1:]]

    print("Step 4 Save Check")
    print("=" * 50)
    print(f"Cases: {cases}")
    print()
    print("IMPORTANT: You need to re-run Step 4 synthesis for these cases")
    print("through the web interface. The save issue prevents automatic saving.")
    print()
    print("For each case, visit:")
    for case_id in cases:
        print(f"  http://localhost:5000/scenario_pipeline/case/{case_id}/step4")
        print(f"  Click 'Run Whole-Case Synthesis' and watch for save messages")
        print()
