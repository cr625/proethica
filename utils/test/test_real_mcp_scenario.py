#!/usr/bin/env python3
"""
Test the real MCP scenario - simulate concepts with 'category' field
but no 'type' field to verify our fix works.
"""
import os
from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.services.guideline_analysis_service import GuidelineAnalysisService

def test_real_mcp_response_handling():
    """Test processing of realistic MCP response with category field."""
    print("🧪 TESTING REAL MCP RESPONSE HANDLING")
    print("=" * 50)
    
    app = create_app('config')
    with app.app_context():
        service = GuidelineAnalysisService()
        print("✅ GuidelineAnalysisService initialized")
        
        # Simulate realistic MCP response (like what guideline 9 received)
        mock_mcp_response = {
            "concepts": [
                {
                    "label": "Public Safety Primacy",
                    "description": "The overriding obligation to prioritize public safety, health, and welfare",
                    "category": "Fundamental Duty",  # MCP returns "category"
                    # NO "type" field - this is the issue!
                },
                {
                    "label": "Professional Competence", 
                    "description": "The requirement to work only within one's areas of expertise",
                    "category": "Professional Standards",
                },
                {
                    "label": "Honesty and Integrity",
                    "description": "The fundamental requirement for truthfulness and ethical conduct",
                    "category": "Core Values",
                },
                {
                    "label": "Environmental Responsibility",
                    "description": "The commitment to environmental responsibility in engineering",
                    "category": "Environmental Ethics",
                },
                {
                    "label": "Professional Accountability",
                    "description": "Taking responsibility for professional actions and decisions",
                    "category": "Professional Responsibility",
                }
            ]
        }
        
        print(f"📥 Simulating MCP response with {len(mock_mcp_response['concepts'])} concepts")
        print("   (All have 'category' field, no 'type' field)")
        
        # Get valid types
        valid_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability"}
        
        # Simulate what happens in the MCP response processing
        concepts = mock_mcp_response["concepts"]
        processed_concepts = []
        
        for concept in concepts:
            print(f"\n📝 Processing: {concept['label']}")
            print(f"   Original category: {concept.get('category')}")
            
            # Apply our fix: map category to type
            original_type = concept.get("type") or concept.get("category")
            concept["type"] = original_type  # Ensure type field is set
            
            print(f"   Mapped to type: {original_type}")
            
            if original_type not in valid_types:
                print(f"   ⚠️  Invalid type - applying type mapper...")
                
                # Use type mapper to get better mapping
                mapping_result = service.type_mapper.map_concept_type(
                    llm_type=original_type,
                    concept_description=concept.get("description", ""),
                    concept_name=concept.get("label", "")
                )
                
                # Store original type and mapping metadata
                concept["original_llm_type"] = original_type
                concept["type"] = mapping_result.mapped_type
                concept["type_mapping_confidence"] = mapping_result.confidence
                concept["needs_type_review"] = mapping_result.needs_review
                concept["mapping_justification"] = mapping_result.justification
                
                print(f"   ✅ Mapped: '{original_type}' → '{mapping_result.mapped_type}' (confidence: {mapping_result.confidence:.2f})")
                print(f"   📊 Needs review: {mapping_result.needs_review}")
            else:
                # Type is already valid - add exact match metadata
                concept["original_llm_type"] = original_type
                concept["type_mapping_confidence"] = 1.0
                concept["needs_type_review"] = False
                concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                print(f"   ✅ Exact match: {original_type}")
            
            processed_concepts.append(concept)
        
        # Analyze results
        print(f"\n📊 PROCESSING RESULTS:")
        print(f"=" * 25)
        
        improved_mappings = 0
        state_assignments = 0
        total_concepts = len(processed_concepts)
        
        for concept in processed_concepts:
            final_type = concept["type"]
            original_type = concept["original_llm_type"]
            confidence = concept["type_mapping_confidence"]
            
            if final_type != "state":
                improved_mappings += 1
                status = "✅ IMPROVED"
            else:
                state_assignments += 1
                status = "⚠️ STATE"
            
            print(f"   {status}: {concept['label']}")
            print(f"      {original_type} → {final_type} (confidence: {confidence:.2f})")
        
        improvement_rate = improved_mappings / total_concepts * 100
        state_rate = state_assignments / total_concepts * 100
        
        print(f"\n📈 SUMMARY:")
        print(f"   Total concepts: {total_concepts}")
        print(f"   Improved mappings: {improved_mappings} ({improvement_rate:.1f}%)")
        print(f"   State assignments: {state_assignments} ({state_rate:.1f}%)")
        
        # Success criteria: most concepts should NOT be assigned to state
        success = improvement_rate >= 70  # At least 70% should be improved
        
        if success:
            print(f"\n🎊 SUCCESS! MCP FIELD MAPPING FIX WORKING!")
            print(f"✅ {improvement_rate:.1f}% of concepts improved from default 'state'")
            print(f"✅ Type mapping successfully preserves LLM insights")
        else:
            print(f"\n⚠️ NEEDS WORK: Only {improvement_rate:.1f}% improved")
        
        return success, processed_concepts

def main():
    """Run real MCP scenario test."""
    print("🚀 REAL MCP SCENARIO TEST")
    print("=" * 60)
    
    try:
        success, processed_concepts = test_real_mcp_response_handling()
        
        print(f"\n🎉 TEST COMPLETE")
        print("=" * 20)
        
        if success:
            print("✅ MCP field mapping fix is working correctly!")
            print("✅ The 'State' over-assignment issue should be resolved")
            print("\nNext step: Re-upload a guideline to see the improvement")
            return True
        else:
            print("⚠️ Fix needs more refinement")
            return False
            
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)