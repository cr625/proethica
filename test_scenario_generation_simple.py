#!/usr/bin/env python3
"""
Simple test for Scenario Generation Stage 1 (Data Collection).

Tests basic functionality without full app context.
"""

import sys
import os

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ''))

# Test imports
print("Testing imports...")
try:
    from app.services.scenario_generation import ScenarioDataCollector
    from app.services.scenario_generation.models import (
        ScenarioSourceData,
        RDFEntity,
        EligibilityReport
    )
    print("✓ All imports successful!")
    print()
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test model instantiation
print("Testing model instantiation...")
try:
    entity = RDFEntity(
        uri="http://example.org/test",
        label="Test Entity",
        entity_type="Role",
        source="temporary",
        definition="A test entity"
    )
    print(f"✓ Created RDFEntity: {entity.label} ({entity.entity_type})")
    print(f"  URI: {entity.uri}")
    print(f"  Source: {entity.source}")
    print()
except Exception as e:
    print(f"✗ Model instantiation error: {e}")
    sys.exit(1)

# Test collector instantiation
print("Testing ScenarioDataCollector instantiation...")
try:
    collector = ScenarioDataCollector()
    print("✓ ScenarioDataCollector instantiated successfully!")
    print()
except Exception as e:
    print(f"✗ Collector instantiation error: {e}")
    sys.exit(1)

print("=" * 80)
print("BASIC TESTS PASSED")
print("=" * 80)
print()
print("Next steps:")
print("1. Start ProEthica server: python run.py")
print("2. Run full test: python test_scenario_generation_stage1.py")
print()
print("Note: Full testing requires database access and completed case data.")
