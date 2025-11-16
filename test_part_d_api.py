"""
Test script for Part D (Institutional Rule Analyzer) API call
Isolates the API request to debug timeout issues
"""

import sys
import os
import time
from anthropic import Anthropic

# Set up Flask app context
sys.path.insert(0, '/home/chris/onto/proethica')
os.chdir('/home/chris/onto/proethica')

from app import create_app
from app.models import TemporaryRDFStorage
from sqlalchemy import func
from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer

def test_part_d_api():
    """Test Part D API call with actual Case 8 data"""
    app = create_app()

    with app.app_context():
        case_id = 8

        print("=" * 80)
        print("TESTING PART D: INSTITUTIONAL RULE ANALYZER API CALL")
        print("=" * 80)

        # Fetch P/O/Cs entities from database
        print(f"\n[1] Fetching entities for Case {case_id}...")

        principles = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            func.lower(TemporaryRDFStorage.entity_type) == 'principles',
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        obligations = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            func.lower(TemporaryRDFStorage.entity_type) == 'obligations',
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        constraints = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            func.lower(TemporaryRDFStorage.entity_type) == 'constraints',
            TemporaryRDFStorage.storage_type == 'individual'
        ).all()

        print(f"    Principles: {len(principles)}")
        print(f"    Obligations: {len(obligations)}")
        print(f"    Constraints: {len(constraints)}")

        # Initialize analyzer
        print(f"\n[2] Initializing InstitutionalRuleAnalyzer...")
        analyzer = InstitutionalRuleAnalyzer()

        # Build prompt
        print(f"\n[3] Building LLM prompt...")
        prompt = analyzer._build_analysis_prompt(principles, obligations, constraints, None)

        print(f"    Prompt size: {len(prompt)} characters")
        print(f"    Prompt size: {len(prompt.encode('utf-8'))} bytes")

        # Show first/last of prompt
        print(f"\n[4] Prompt preview:")
        print(f"    First 300 chars: {prompt[:300]}")
        print(f"    Last 200 chars: {prompt[-200:]}")

        # Get API key
        print(f"\n[5] Checking Anthropic API configuration...")
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            print("    ERROR: ANTHROPIC_API_KEY not set in environment!")
            return False

        print(f"    API key found: {api_key[:10]}...{api_key[-4:]}")

        # Create client directly
        print(f"\n[6] Creating Anthropic client...")
        client = Anthropic(api_key=api_key)
        print(f"    Client base URL: {client.base_url}")
        print(f"    Client timeout: {client.timeout}")
        print(f"    Client max retries: {client.max_retries}")

        # Make API call with timing
        print(f"\n[7] Making API call to /v1/messages...")
        print(f"    Model: claude-sonnet-4-5-20250929")
        print(f"    Max tokens: 4000")

        start_time = time.time()

        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            elapsed = time.time() - start_time

            print(f"\n[8] ✓ API call successful!")
            print(f"    Time elapsed: {elapsed:.2f} seconds")
            print(f"    Response ID: {response.id}")
            print(f"    Response model: {response.model}")
            print(f"    Stop reason: {response.stop_reason}")
            print(f"    Usage - Input tokens: {response.usage.input_tokens}")
            print(f"    Usage - Output tokens: {response.usage.output_tokens}")

            response_text = response.content[0].text
            print(f"    Response length: {len(response_text)} characters")
            print(f"\n    Response preview (first 500 chars):")
            print(f"    {response_text[:500]}")

            return True

        except Exception as e:
            elapsed = time.time() - start_time

            print(f"\n[8] ✗ API call FAILED!")
            print(f"    Time elapsed: {elapsed:.2f} seconds")
            print(f"    Error type: {type(e).__name__}")
            print(f"    Error message: {str(e)}")

            import traceback
            print(f"\n    Full traceback:")
            traceback.print_exc()

            return False

if __name__ == '__main__':
    success = test_part_d_api()

    print("\n" + "=" * 80)
    if success:
        print("TEST PASSED ✓")
    else:
        print("TEST FAILED ✗")
    print("=" * 80)

    sys.exit(0 if success else 1)
