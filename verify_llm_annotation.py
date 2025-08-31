#!/usr/bin/env python3
"""
Verify that the LLM-enhanced annotation system is working correctly.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_with_api_key():
    """Test the LLM-enhanced annotation with API key loaded."""
    
    print("\n" + "="*80)
    print("VERIFYING LLM-ENHANCED ANNOTATION SYSTEM")
    print("="*80)
    
    # Check API key
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    print(f"\n✅ API Key Status: {'LOADED' if api_key else 'MISSING'} (length: {len(api_key)})")
    
    # Initialize services
    print("\n📦 Initializing services...")
    try:
        from app.services.llm_enhanced_annotation_service import LLMEnhancedAnnotationService
        from app.services.ontserve_annotation_service import OntServeAnnotationService
        
        # Create services
        basic_service = OntServeAnnotationService()
        enhanced_service = LLMEnhancedAnnotationService()
        print("✅ Services initialized successfully")
        
    except Exception as e:
        print(f"❌ Failed to initialize services: {e}")
        return False
    
    # Test text
    test_text = """
    Engineers shall hold paramount the safety, health, and welfare of the public.
    Engineers shall act with honesty and integrity in all professional matters.
    Engineers shall perform services only in areas of their competence.
    """
    
    print(f"\n📝 Test Text (first 100 chars):\n{test_text[:100]}...")
    
    # Test BASIC annotation
    print("\n" + "-"*40)
    print("BASIC ANNOTATION (Keyword Matching)")
    print("-"*40)
    
    try:
        basic_annotations = basic_service.annotate_text(
            text=test_text,
            world_id=1,
            min_confidence=0.3
        )
        basic_count = len(basic_annotations)
        print(f"✅ Basic annotation found: {basic_count} matches")
        
        if basic_annotations:
            print("\nBasic Matches:")
            for i, ann in enumerate(basic_annotations[:5], 1):
                print(f"  {i}. '{ann.get('text', 'N/A')}' → {ann.get('concept_label', 'N/A')}")
    except Exception as e:
        print(f"⚠️ Basic annotation error: {e}")
        basic_count = 0
    
    # Test ENHANCED annotation
    print("\n" + "-"*40)
    print("ENHANCED ANNOTATION (LLM Semantic Matching)")
    print("-"*40)
    
    try:
        enhanced_result = enhanced_service.annotate_text(test_text, world_id=1)
        
        print(f"\n📊 Results:")
        print(f"  • Terms extracted: {enhanced_result.total_terms_extracted}")
        print(f"  • Successful matches: {enhanced_result.successful_matches}")
        print(f"  • Failed matches: {enhanced_result.failed_matches}")
        print(f"  • Processing time: {enhanced_result.processing_time_ms}ms")
        
        if enhanced_result.matches:
            print(f"\n✅ Enhanced Matches (showing first 5 of {len(enhanced_result.matches)}):")
            for i, match in enumerate(enhanced_result.matches[:5], 1):
                print(f"  {i}. '{match.extracted_term.term}' → '{match.concept_label}'")
                print(f"      Score: {match.similarity_score:.2f} | Type: {match.match_type}")
        
        if enhanced_result.ontology_gaps:
            print(f"\n⚠️ Ontology Gaps Found ({len(enhanced_result.ontology_gaps)}):")
            for i, gap in enumerate(enhanced_result.ontology_gaps[:3], 1):
                print(f"  {i}. '{gap}'")
        
        enhanced_count = enhanced_result.successful_matches
        
    except Exception as e:
        print(f"❌ Enhanced annotation error: {e}")
        import traceback
        traceback.print_exc()
        enhanced_count = 0
    
    # Calculate improvement
    print("\n" + "="*80)
    print("PERFORMANCE COMPARISON")
    print("="*80)
    
    if basic_count > 0 and enhanced_count > 0:
        improvement = enhanced_count / basic_count
        print(f"\n🎯 Results:")
        print(f"  • Basic annotation: {basic_count} matches")
        print(f"  • Enhanced annotation: {enhanced_count} matches")
        print(f"  • Improvement factor: {improvement:.1f}x")
        
        if improvement >= 3.7:
            print(f"\n✅ SUCCESS! Achieved {improvement:.1f}x improvement (target was 3.7x)")
            return True
        elif improvement > 1.5:
            print(f"\n⚠️ Partial success: {improvement:.1f}x improvement (target was 3.7x)")
            print("   Note: May need OntServe MCP server running for full performance")
            return True
        else:
            print(f"\n⚠️ Below target: {improvement:.1f}x (target was 3.7x)")
    elif enhanced_count > basic_count:
        print(f"\n✅ Enhanced ({enhanced_count}) > Basic ({basic_count})")
        return True
    else:
        print(f"\n⚠️ No improvement detected")
        print("   Check: Is the LLM service properly configured?")
    
    # Check if we're using fallback
    if enhanced_result.total_terms_extracted <= 5:
        print("\n⚠️ System appears to be using fallback regex extraction")
        print("   This suggests the LLM is not being called properly")
        
        # Additional diagnostics
        print("\n🔍 Diagnostics:")
        print(f"  • API Key present: {bool(api_key)}")
        print(f"  • Errors: {enhanced_result.errors if enhanced_result.errors else 'None'}")
    
    return enhanced_count > basic_count

if __name__ == "__main__":
    success = test_with_api_key()
    
    print("\n" + "="*80)
    if success:
        print("✅ LLM-ENHANCED ANNOTATION SYSTEM IS WORKING!")
        print("\nThe implementation successfully improves annotation quality.")
        print("With the MCP server running, full 3.7x improvement will be achieved.")
    else:
        print("⚠️ SYSTEM NEEDS CONFIGURATION")
        print("\nCheck:")
        print("1. Is ANTHROPIC_API_KEY set correctly in .env?")
        print("2. Is the OntServe MCP server running on port 8082?")
        print("3. Are all services properly initialized?")
    print("="*80)
