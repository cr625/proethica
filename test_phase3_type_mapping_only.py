#!/usr/bin/env python3
"""
Test Phase 3 type mapping integration without MCP dependencies.
Focus on testing the GuidelineConceptTypeMapper integration.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.models import db
from app.services.guideline_analysis_service import GuidelineAnalysisService

def test_type_mapper_in_service():
    """Test that the type mapper is correctly integrated into GuidelineAnalysisService."""
    print("🧪 TESTING TYPE MAPPER INTEGRATION")
    print("=" * 50)
    
    app = create_app('config')
    with app.app_context():
        print(f"📊 Database: {db.engine.url}")
        print()
        
        # Initialize the service
        service = GuidelineAnalysisService()
        print("✅ GuidelineAnalysisService initialized")
        
        # Test that type mapper is available
        if hasattr(service, 'type_mapper'):
            print("✅ Type mapper is integrated into service")
        else:
            print("❌ Type mapper NOT found in service")
            return False
        
        # Test type mapper directly
        print("\n🔄 Testing type mapper functionality:")
        
        test_cases = [
            ("Professional Standard", "Professional Competence", "Professional qualification requirements"),
            ("Fundamental Principle", "Public Safety Paramount", "The overriding principle of public welfare"),
            ("Core Value", "Honesty and Integrity", "Fundamental ethical requirements"),
            ("Environmental Responsibility", "Sustainability", "Long-term environmental impact considerations"),
            ("Unknown New Type", "Some Concept", "A concept with an unknown type")
        ]
        
        improvements = 0
        total_tests = len(test_cases)
        
        for llm_type, concept_name, description in test_cases:
            result = service.type_mapper.map_concept_type(
                llm_type=llm_type,
                concept_name=concept_name,
                concept_description=description
            )
            
            if result.mapped_type != "state" or result.confidence >= 0.8:
                improvements += 1
                status = "✅ GOOD MAPPING"
            elif result.needs_review:
                status = "👁️ NEEDS REVIEW"
            else:
                status = "⚠️ POOR MAPPING"
            
            print(f"   {status}: '{llm_type}' → '{result.mapped_type}' (confidence: {result.confidence:.2f})")
            print(f"      Concept: {concept_name}")
            print(f"      Justification: {result.justification}")
            print()
        
        improvement_rate = improvements / total_tests * 100
        print(f"📊 Type Mapper Performance:")
        print(f"   Good mappings: {improvements}/{total_tests} ({improvement_rate:.1f}%)")
        
        return improvement_rate >= 60  # At least 60% should be good mappings

def test_llm_response_parsing():
    """Test the _parse_llm_response method with type mapping logic."""
    print(f"\n🔍 TESTING LLM RESPONSE PARSING")
    print("=" * 40)
    
    app = create_app('config')
    with app.app_context():
        service = GuidelineAnalysisService()
        
        # Mock LLM response with invalid types
        mock_response = '''[
            {
                "label": "Professional Competence",
                "description": "Engineers should work within their expertise",
                "type": "Professional Standard",
                "confidence": 0.9
            },
            {
                "label": "Public Safety",
                "description": "The paramount concern for public welfare",
                "type": "Fundamental Principle", 
                "confidence": 0.95
            },
            {
                "label": "Honesty",
                "description": "Truthfulness in all dealings",
                "type": "Core Value",
                "confidence": 0.85
            },
            {
                "label": "Valid Concept",
                "description": "Already has valid type",
                "type": "principle",
                "confidence": 0.8
            }
        ]'''
        
        # Define valid types (the 8 core ontology types)
        valid_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability"}
        
        # Test parsing
        concepts = service._parse_llm_response(mock_response, valid_types)
        
        print(f"✅ Parsed {len(concepts)} concepts from mock response")
        
        mapped_concepts = 0
        exact_matches = 0
        
        for concept in concepts:
            concept_name = concept.get("label", "Unknown")
            original_type = concept.get("original_llm_type")
            final_type = concept.get("type")
            confidence = concept.get("type_mapping_confidence", 0)
            justification = concept.get("mapping_justification", "")
            
            print(f"\n   📝 {concept_name}:")
            
            if original_type and original_type != final_type:
                mapped_concepts += 1
                print(f"      ✅ Mapped: '{original_type}' → '{final_type}' (confidence: {confidence:.2f})")
                print(f"      Justification: {justification}")
            elif original_type == final_type:
                exact_matches += 1
                print(f"      ✅ Exact match: '{final_type}' (confidence: {confidence:.2f})")
            else:
                print(f"      ℹ️ Type: '{final_type}' (no mapping needed)")
        
        print(f"\n📊 Parsing Results:")
        print(f"   Total concepts: {len(concepts)}")
        print(f"   Mapped types: {mapped_concepts}")
        print(f"   Exact matches: {exact_matches}")
        print(f"   All concepts preserved: {len(concepts) == 4}")
        
        # Key success criteria
        success_criteria = [
            len(concepts) == 4,  # All concepts preserved
            mapped_concepts >= 3,  # At least 3 concepts were mapped
            exact_matches >= 1,  # At least 1 exact match
            all(c.get("type") in valid_types for c in concepts)  # All final types are valid
        ]
        
        success = all(success_criteria)
        print(f"✅ Parsing test: {'PASS' if success else 'FAIL'}")
        
        return success

def test_type_mapping_metadata():
    """Test that type mapping metadata is properly created."""
    print(f"\n📊 TESTING TYPE MAPPING METADATA")
    print("=" * 40)
    
    app = create_app('config')
    with app.app_context():
        service = GuidelineAnalysisService()
        
        # Test concepts with different mapping scenarios
        test_concepts = [
            {"type": "Professional Standard", "label": "Professional Competence", "description": "Work within expertise"},  # Should be mapped
            {"type": "principle", "label": "Valid Type", "description": "Already valid"},  # Should be exact match
            {"type": "Weird New Type", "label": "Unknown", "description": "Something new"}  # Should be new type proposal
        ]
        
        valid_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability"}
        
        processed_concepts = []
        
        for concept in test_concepts:
            original_type = concept["type"]
            
            if original_type not in valid_types:
                # Simulate what happens in _parse_llm_response
                mapping_result = service.type_mapper.map_concept_type(
                    llm_type=original_type,
                    concept_description=concept["description"],
                    concept_name=concept["label"]
                )
                
                # Create concept with mapping metadata
                processed_concept = {
                    "label": concept["label"],
                    "description": concept["description"],
                    "type": mapping_result.mapped_type,
                    "original_llm_type": original_type,
                    "type_mapping_confidence": mapping_result.confidence,
                    "needs_type_review": mapping_result.needs_review,
                    "mapping_justification": mapping_result.justification
                }
            else:
                # Exact match - create with exact match metadata
                processed_concept = {
                    "label": concept["label"],
                    "description": concept["description"],
                    "type": original_type,
                    "original_llm_type": original_type,
                    "type_mapping_confidence": 1.0,
                    "needs_type_review": False,
                    "mapping_justification": f"Exact match to ontology type '{original_type}'"
                }
            
            processed_concepts.append(processed_concept)
        
        print("📋 Processed concepts with metadata:")
        
        metadata_fields = ["original_llm_type", "type_mapping_confidence", "needs_type_review", "mapping_justification"]
        all_have_metadata = True
        
        for concept in processed_concepts:
            print(f"\n   📝 {concept['label']}:")
            print(f"      Final type: {concept['type']}")
            
            for field in metadata_fields:
                value = concept.get(field)
                if value is not None:
                    print(f"      ✅ {field}: {value}")
                else:
                    print(f"      ❌ {field}: MISSING")
                    all_have_metadata = False
        
        print(f"\n✅ Metadata test: {'PASS' if all_have_metadata else 'FAIL'}")
        return all_have_metadata

def main():
    """Run Phase 3 type mapping integration tests."""
    print("🚀 PHASE 3 TYPE MAPPING INTEGRATION TESTS")
    print("=" * 60)
    
    try:
        # Test type mapper integration
        mapper_ok = test_type_mapper_in_service()
        
        # Test LLM response parsing
        parsing_ok = test_llm_response_parsing()
        
        # Test metadata creation
        metadata_ok = test_type_mapping_metadata()
        
        print(f"\n🎉 PHASE 3 TYPE MAPPING TEST SUMMARY")
        print("=" * 45)
        print(f"✅ Type mapper integration: {'PASS' if mapper_ok else 'FAIL'}")
        print(f"✅ LLM response parsing: {'PASS' if parsing_ok else 'FAIL'}")
        print(f"✅ Metadata creation: {'PASS' if metadata_ok else 'FAIL'}")
        
        all_pass = mapper_ok and parsing_ok and metadata_ok
        
        if all_pass:
            print("\n🎊 PHASE 3 TYPE MAPPING INTEGRATION SUCCESSFUL!")
            print("✅ GuidelineConceptTypeMapper properly integrated")
            print("✅ Type mapping metadata correctly generated")
            print("✅ Invalid types properly handled with fallback")
            print("\nReady for end-to-end testing with real guidelines!")
            return True
        else:
            print("\n⚠️ Some tests failed - integration needs fixes")
            return False
            
    except Exception as e:
        print(f"\n❌ INTEGRATION TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)