"""
Test Part D with REAL Case 8 data (outside synthesis pipeline)
"""

import sys
import os
import time
sys.path.insert(0, '/home/chris/onto/proethica')
os.chdir('/home/chris/onto/proethica')

# Set environment
os.environ.setdefault('FLASK_ENV', 'development')

from app import create_app
from app.models import TemporaryRDFStorage
from sqlalchemy import func

app = create_app()

with app.app_context():
    case_id = 8

    print("=" * 80)
    print(f"TESTING PART D WITH REAL CASE {case_id} DATA")
    print("=" * 80)

    # Fetch real entities
    print("\n[1] Fetching REAL entities from database...")
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
    print("\n[2] Initializing InstitutionalRuleAnalyzer...")
    from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer

    analyzer = InstitutionalRuleAnalyzer()

    print(f"    Analyzer initialized")
    print(f"    LLM client type: {type(analyzer.llm_client)}")
    print(f"    LLM client timeout: {analyzer.llm_client.timeout}")

    # Build prompt
    print("\n[3] Building prompt with REAL data...")
    prompt = analyzer._build_analysis_prompt(principles, obligations, constraints, None)

    print(f"    Prompt size: {len(prompt)} characters")
    print(f"    Prompt size: {len(prompt.encode('utf-8'))} bytes")

    # Try API call
    print("\n[4] Making API call...")
    print(f"    Start time: {time.strftime('%H:%M:%S')}")

    start_time = time.time()

    try:
        analysis = analyzer.analyze_case(
            case_id=case_id,
            principles=principles,
            obligations=obligations,
            constraints=constraints,
            case_context=None
        )

        elapsed = time.time() - start_time

        print(f"\n[5] ✓ SUCCESS!")
        print(f"    Elapsed: {elapsed:.2f} seconds")
        print(f"    Principle tensions: {len(analysis.principle_tensions)}")
        print(f"    Obligation conflicts: {len(analysis.obligation_conflicts)}")
        print(f"    Constraining factors: {len(analysis.constraining_factors)}")

        sys.exit(0)

    except Exception as e:
        elapsed = time.time() - start_time

        print(f"\n[5] ✗ FAILED!")
        print(f"    Elapsed: {elapsed:.2f} seconds")
        print(f"    Error: {e}")

        import traceback
        print(f"\n    Full traceback:")
        traceback.print_exc()

        # Save prompt to file for inspection
        print(f"\n[6] Saving prompt to file for inspection...")
        with open('/tmp/part_d_prompt.txt', 'w') as f:
            f.write(prompt)
        print(f"    Saved to: /tmp/part_d_prompt.txt")

        sys.exit(1)
