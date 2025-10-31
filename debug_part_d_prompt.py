"""
Debug script to see actual Part D prompt with real Case 8 data
"""

import sys
import os
sys.path.insert(0, '/home/chris/onto/proethica')
os.chdir('/home/chris/onto/proethica')

from app import create_app
from app.models import TemporaryRDFStorage
from sqlalchemy import func
from app.services.case_analysis.institutional_rule_analyzer import InstitutionalRuleAnalyzer

app = create_app()

with app.app_context():
    case_id = 8

    print("=" * 80)
    print(f"DEBUGGING PART D PROMPT FOR CASE {case_id}")
    print("=" * 80)

    # Fetch entities
    print("\n[1] Fetching entities...")
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

    # Check first entity of each type
    print("\n[2] Inspecting first entity of each type...")
    if principles:
        p = principles[0]
        print(f"\n    PRINCIPLE:")
        print(f"      entity_label: {repr(getattr(p, 'entity_label', 'NOT FOUND'))}")
        print(f"      entity_definition: {repr(getattr(p, 'entity_definition', 'NOT FOUND'))}")
        print(f"      entity_uri: {repr(getattr(p, 'entity_uri', 'NOT FOUND'))}")
        print(f"      rdf_json_ld type: {type(getattr(p, 'rdf_json_ld', None))}")

    if obligations:
        o = obligations[0]
        print(f"\n    OBLIGATION:")
        print(f"      entity_label: {repr(getattr(o, 'entity_label', 'NOT FOUND'))}")
        print(f"      entity_definition: {repr(getattr(o, 'entity_definition', 'NOT FOUND'))}")
        print(f"      entity_uri: {repr(getattr(o, 'entity_uri', 'NOT FOUND'))}")
        rdf = getattr(o, 'rdf_json_ld', {}) or {}
        print(f"      rdf_json_ld keys: {list(rdf.keys()) if isinstance(rdf, dict) else 'NOT A DICT'}")
        if isinstance(rdf, dict):
            props = rdf.get('properties', {})
            print(f"      rdf properties keys: {list(props.keys())}")

    # Initialize analyzer (will fail on LLM, but that's ok)
    print("\n[3] Building prompt...")
    try:
        analyzer = InstitutionalRuleAnalyzer()
    except Exception as e:
        print(f"    Note: LLM client init failed (expected): {e}")
        # Create minimal analyzer for prompt building
        class MinimalAnalyzer:
            def _format_principles(self, p):
                return InstitutionalRuleAnalyzer._format_principles(self, p)
            def _format_obligations(self, o):
                return InstitutionalRuleAnalyzer._format_obligations(self, o)
            def _format_constraints(self, c):
                return InstitutionalRuleAnalyzer._format_constraints(self, c)
            def _build_analysis_prompt(self, p, o, c, ctx):
                return InstitutionalRuleAnalyzer._build_analysis_prompt(self, p, o, c, ctx)

        analyzer = MinimalAnalyzer()

    prompt = analyzer._build_analysis_prompt(principles, obligations, constraints, None)

    print(f"\n[4] Prompt Analysis:")
    print(f"    Total size: {len(prompt)} characters")
    print(f"    Total size: {len(prompt.encode('utf-8'))} bytes")

    # Check for potential issues
    print(f"\n[5] Checking for potential issues...")
    if len(prompt) > 100000:
        print(f"    ⚠ WARNING: Prompt is very large ({len(prompt)} chars)")

    # Check for null bytes or other binary data
    if '\x00' in prompt:
        print(f"    ⚠ WARNING: Prompt contains null bytes!")

    # Check for extremely long lines
    lines = prompt.split('\n')
    max_line_len = max(len(line) for line in lines)
    print(f"    Max line length: {max_line_len} characters")
    if max_line_len > 10000:
        print(f"    ⚠ WARNING: Very long line detected")

    # Show sections of prompt
    print(f"\n[6] Prompt Structure:")
    print(f"    First 1000 characters:")
    print("-" * 80)
    print(prompt[:1000])
    print("-" * 80)

    print(f"\n    Middle section (around Obligations):")
    obligations_pos = prompt.find("**Available Obligations**")
    if obligations_pos > 0:
        print("-" * 80)
        print(prompt[obligations_pos:obligations_pos+1000])
        print("-" * 80)

    print(f"\n    Last 500 characters:")
    print("-" * 80)
    print(prompt[-500:])
    print("-" * 80)

    print("\n" + "=" * 80)
    print("PROMPT INSPECTION COMPLETE")
    print("=" * 80)
