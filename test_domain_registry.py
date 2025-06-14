#!/usr/bin/env python3
"""Test script for the domain registry functionality."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.domain_registry import domain_registry
from app.models.domain_config import DomainConfig


def test_domain_registry():
    """Test the domain registry functionality."""
    print("=" * 60)
    print("Domain Registry Test")
    print("=" * 60)
    
    # Test 1: List domains
    print("\n1. Listing all domains:")
    domains = domain_registry.list_domains()
    print(f"   Found {len(domains)} domain(s): {', '.join(domains)}")
    
    # Test 2: Get all domain details
    print("\n2. Domain configurations:")
    all_domains = domain_registry.get_all_domains()
    
    for name, config in all_domains.items():
        print(f"\n   Domain: {name}")
        print(f"   - Display Name: {config.display_name}")
        print(f"   - Description: {config.description}")
        print(f"   - Adapter Class: {config.adapter_class_name}")
        print(f"   - Guideline Sections: {', '.join(config.guideline_sections)}")
        print(f"   - Case Sections: {len(config.case_sections)} sections")
        print(f"   - Extraction Patterns: {list(config.extraction_patterns.keys())}")
        print(f"   - Ontology Namespace: {config.ontology_namespace}")
    
    # Test 3: Get specific domain
    print("\n3. Getting specific domain (engineering):")
    eng_domain = domain_registry.get_domain("engineering")
    if eng_domain:
        print(f"   ✓ Successfully retrieved engineering domain")
        print(f"   - Has {len(eng_domain.ontology_concepts)} ontology concepts")
    else:
        print("   ✗ Engineering domain not found")
    
    # Test 4: Create adapter
    print("\n4. Creating adapter for engineering domain:")
    try:
        adapter = domain_registry.create_adapter("engineering")
        print(f"   ✓ Successfully created adapter: {adapter.__class__.__name__}")
        
        # Test adapter methods exist
        methods = ["extract_stakeholders", "extract_decision_points", "extract_reasoning_chains", "deconstruct"]
        for method in methods:
            if hasattr(adapter, method):
                print(f"   ✓ Adapter has method: {method}")
            else:
                print(f"   ✗ Adapter missing method: {method}")
    except Exception as e:
        print(f"   ✗ Error creating adapter: {e}")
    
    # Test 5: Validate configuration
    print("\n5. Validating domain configuration:")
    if eng_domain:
        errors = eng_domain.validate()
        if errors:
            print(f"   ✗ Validation errors: {errors}")
        else:
            print("   ✓ Domain configuration is valid")
    
    # Test 6: Test domain configuration serialization
    print("\n6. Testing serialization:")
    if eng_domain:
        try:
            dict_repr = eng_domain.to_dict()
            print(f"   ✓ Successfully serialized to dict with {len(dict_repr)} keys")
            
            # Test deserialization
            restored = DomainConfig.from_dict(dict_repr)
            print(f"   ✓ Successfully deserialized back to DomainConfig")
            print(f"   - Names match: {restored.name == eng_domain.name}")
        except Exception as e:
            print(f"   ✗ Serialization error: {e}")
    
    print("\n" + "=" * 60)
    print("Domain Registry Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    test_domain_registry()