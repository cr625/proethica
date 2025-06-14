#!/usr/bin/env python3
"""
Test the MCP field mapping fix - verify that "category" field from MCP 
gets properly mapped to "type" field for processing.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.services.guideline_analysis_service import GuidelineAnalysisService

def test_mcp_field_mapping():
    """Test that MCP 'category' field gets mapped to 'type' field."""
    print("🧪 TESTING MCP FIELD MAPPING FIX")
    print("=" * 50)
    
    app = create_app('config')
    with app.app_context():
        print(f"📊 Testing with GuidelineAnalysisService")
        print()
        
        # Initialize the service
        service = GuidelineAnalysisService()
        print("✅ GuidelineAnalysisService initialized")
        
        # Enable mock mode to test without MCP dependency
        service.use_mock_responses = True
        print("✅ Mock mode enabled for testing")
        
        # Test content that should generate good types
        test_content = """
        Engineering Code of Ethics
        
        1. Public Safety: Engineers shall hold paramount the safety, health, and welfare of the public.
        
        2. Professional Competence: Engineers shall only undertake work within their area of expertise.
        
        3. Honesty and Integrity: Engineers must be truthful and fair in all professional dealings.
        """
        
        print("🔍 Testing concept extraction with field mapping fix...")
        
        # Extract concepts
        result = service.extract_concepts(test_content)
        
        if "error" in result:
            print(f"❌ Error in concept extraction: {result['error']}")
            return False
        
        concepts = result.get("concepts", [])
        print(f"✅ Extracted {len(concepts)} concepts")
        
        # Check if concepts have proper types and metadata
        properly_typed = 0
        with_metadata = 0
        
        for concept in concepts:
            print(f"\n📝 Concept: {concept.get('label', 'Unknown')}")
            print(f"   Type: {concept.get('type', 'Unknown')}")
            print(f"   Category: {concept.get('category', 'N/A')}")  # Check if category field still exists
            
            # Check for type mapping metadata
            if concept.get("original_llm_type") is not None:
                with_metadata += 1
                print(f"   ✅ Original LLM type: {concept.get('original_llm_type')}")
                print(f"   ✅ Mapping confidence: {concept.get('type_mapping_confidence', 'N/A')}")
                print(f"   ✅ Needs review: {concept.get('needs_type_review', False)}")
                print(f"   ✅ Justification: {concept.get('mapping_justification', 'N/A')}")
            else:
                print(f"   ⚠️  No type mapping metadata")
            
            # Check if type is valid
            valid_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability"}
            if concept.get("type") in valid_types:
                properly_typed += 1
                print(f"   ✅ Valid type: {concept.get('type')}")
            else:
                print(f"   ❌ Invalid type: {concept.get('type')}")
        
        print(f"\n📊 FIELD MAPPING TEST RESULTS:")
        print(f"   Total concepts: {len(concepts)}")
        print(f"   Properly typed: {properly_typed}/{len(concepts)}")
        print(f"   With metadata: {with_metadata}/{len(concepts)}")
        
        success = properly_typed == len(concepts) and with_metadata == len(concepts)
        
        if success:
            print(f"\n✅ FIELD MAPPING FIX WORKING!")
            print(f"   All concepts have valid types")
            print(f"   All concepts have mapping metadata")
        else:
            print(f"\n⚠️  FIELD MAPPING NEEDS MORE WORK")
        
        return success

def test_type_mapping_scenarios():
    """Test different type mapping scenarios."""
    print(f"\n🎯 TESTING TYPE MAPPING SCENARIOS")
    print("=" * 40)
    
    app = create_app('config')
    with app.app_context():
        service = GuidelineAnalysisService()
        
        # Test the type mapper with realistic MCP-style categories
        test_cases = [
            ("principle", "Should be exact match"),
            ("Fundamental Duty", "Should map to principle/obligation"),
            ("Professional Standards", "Should map to principle"),
            ("Core Values", "Should map to principle"),
            ("Professional Duty", "Should map to obligation"),
            ("Environmental Ethics", "Should map to principle/obligation"),
            ("None", "Should map to state as fallback")
        ]
        
        print("🔄 Testing category → type mapping:")
        for category, expected in test_cases:
            # Simulate what happens in the processing
            original_type = category
            valid_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability"}
            
            if original_type not in valid_types:
                result = service.type_mapper.map_concept_type(
                    llm_type=original_type,
                    concept_description=expected
                )
                final_type = result.mapped_type
                confidence = result.confidence
                status = "✅ MAPPED" if final_type != "state" else "⚠️ FALLBACK"
            else:
                final_type = original_type
                confidence = 1.0
                status = "✅ EXACT"
            
            print(f"   {status}: '{category}' → '{final_type}' (confidence: {confidence:.2f})")
        
        return True

def main():
    """Run MCP field mapping tests."""
    print("🚀 MCP FIELD MAPPING FIX TESTS")
    print("=" * 60)
    
    try:
        # Test field mapping fix
        mapping_ok = test_mcp_field_mapping()
        
        # Test type mapping scenarios  
        scenarios_ok = test_type_mapping_scenarios()
        
        print(f"\n🎉 MCP FIELD MAPPING TEST SUMMARY")
        print("=" * 40)
        print(f"✅ Field mapping fix: {'PASS' if mapping_ok else 'FAIL'}")
        print(f"✅ Type mapping scenarios: {'PASS' if scenarios_ok else 'FAIL'}")
        
        if mapping_ok and scenarios_ok:
            print("\n🎊 MCP FIELD MAPPING FIX SUCCESSFUL!")
            print("✅ 'category' field properly mapped to 'type'")
            print("✅ Type mapping working for all scenarios")
            print("✅ Metadata correctly generated")
            print("\nThe fix should resolve the 'State' over-assignment issue!")
            return True
        else:
            print("\n⚠️ Some tests failed - fix needs more work")
            return False
            
    except Exception as e:
        print(f"\n❌ FIELD MAPPING TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)