#!/usr/bin/env python
"""Test Step 3 Actions & Events extraction endpoint"""

import requests
import json

def test_step3_extraction():
    """Test the Step 3 actions and events extraction"""

    # Get a session to maintain CSRF token
    session = requests.Session()

    # First, get the page to obtain CSRF token
    response = session.get('http://localhost:5000/scenario_pipeline/case/8/step3')
    if response.status_code != 200:
        print(f"Failed to get Step 3 page: {response.status_code}")
        return

    # Extract CSRF token from the page
    import re
    csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', response.text)
    if not csrf_match:
        # Try alternate pattern
        csrf_match = re.search(r'csrfToken:\s*["\']([^"\']+)["\']', response.text)

    if csrf_match:
        csrf_token = csrf_match.group(1)
        print(f"Found CSRF token: {csrf_token[:20]}...")
    else:
        print("Warning: Could not find CSRF token, proceeding without it")
        csrf_token = None

    # Test data - Case 8 stormwater management scenario
    test_data = {
        'concept_type': 'actions_events',
        'section_text': """Engineer L, a professional engineer, was initially engaged by Client X to develop a stormwater control study. After discovering potential risks to downstream properties, L suspended work due to financial setbacks from Client X. When financial conditions improved, work resumed. Following significant rainfall events that increased risks, Engineer L conducted further studies and strongly recommended additional flood protection, but Client X refused the recommendations."""
    }

    # Make the extraction request
    headers = {'Content-Type': 'application/json'}
    if csrf_token:
        headers['X-CSRFToken'] = csrf_token

    response = session.post(
        'http://localhost:5000/scenario_pipeline/case/8/step3/extract_individual',
        json=test_data,
        headers=headers
    )

    print(f"\nResponse Status: {response.status_code}")

    if response.status_code == 200:
        result = response.json()
        print("\n=== EXTRACTION SUCCESSFUL ===\n")

        if result.get('success'):
            # Display metadata
            metadata = result.get('metadata', {})
            print(f"Extraction Method: {metadata.get('extraction_method')}")
            print(f"Model Used: {metadata.get('model_used')}")
            print(f"Session ID: {metadata.get('session_id')}")

            # Display concept counts
            counts = metadata.get('concept_counts', {})
            print(f"\nConcept Counts:")
            print(f"  Action Classes: {counts.get('action_classes', 0)}")
            print(f"  Action Individuals: {counts.get('action_individuals', 0)}")
            print(f"  Event Classes: {counts.get('event_classes', 0)}")
            print(f"  Event Individuals: {counts.get('event_individuals', 0)}")
            print(f"  Total: {counts.get('total', 0)}")

            # Display extracted concepts
            concepts = result.get('concepts', [])
            print(f"\n=== EXTRACTED CONCEPTS ({len(concepts)} total) ===\n")

            # Separate by type
            action_classes = [c for c in concepts if c['type'] == 'action_class']
            action_individuals = [c for c in concepts if c['type'] == 'action_individual']
            event_classes = [c for c in concepts if c['type'] == 'event_class']
            event_individuals = [c for c in concepts if c['type'] == 'event_individual']

            if action_classes:
                print("ACTION CLASSES:")
                for ac in action_classes:
                    print(f"  - {ac['label']}: {ac.get('description', '')[:80]}...")
                    print(f"    Type: {ac.get('action_type', 'N/A')}, Confidence: {ac.get('confidence', 0):.2f}")

            if action_individuals:
                print("\nACTION INDIVIDUALS:")
                for ai in action_individuals:
                    print(f"  - {ai['label']} ({ai.get('action_class', 'Unknown')})")
                    print(f"    By: {ai.get('performed_by', 'Unknown')}")
                    print(f"    Statement: {ai.get('action_statement', '')[:80]}...")

            if event_classes:
                print("\nEVENT CLASSES:")
                for ec in event_classes:
                    print(f"  - {ec['label']}: {ec.get('description', '')[:80]}...")
                    print(f"    Type: {ec.get('event_type', 'N/A')}, Confidence: {ec.get('confidence', 0):.2f}")

            if event_individuals:
                print("\nEVENT INDIVIDUALS:")
                for ei in event_individuals:
                    print(f"  - {ei['label']} ({ei.get('event_class', 'Unknown')})")
                    print(f"    Description: {ei.get('event_description', '')[:80]}...")

            # Show if prompt was generated
            if result.get('prompt'):
                print(f"\n=== PROMPT PREVIEW ===")
                print(result['prompt'][:500] + "..." if len(result['prompt']) > 500 else result['prompt'])

            # Show if raw response available
            if result.get('raw_response'):
                print(f"\n=== RAW RESPONSE PREVIEW ===")
                print(result['raw_response'][:500] + "..." if len(result['raw_response']) > 500 else result['raw_response'])
        else:
            print(f"Extraction failed: {result.get('error', 'Unknown error')}")
    else:
        print(f"Request failed: {response.text[:500]}")

if __name__ == "__main__":
    test_step3_extraction()