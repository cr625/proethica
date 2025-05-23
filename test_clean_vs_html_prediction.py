#!/usr/bin/env python3
"""
Test clean text vs HTML prediction service for Case 252.
Demonstrates the improvement in prompt quality and LLM response.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set up environment
os.environ.setdefault('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', 'false')
os.environ.setdefault('ENVIRONMENT', 'development')

from app import create_app
from app.services.experiment.prediction_service import PredictionService
from app.services.experiment.prediction_service_clean import CleanPredictionService

def test_clean_vs_html():
    """Test clean text vs HTML content in prediction service."""
    app = create_app('config')
    
    with app.app_context():
        print("🧪 TESTING CLEAN vs HTML PREDICTION SERVICE")
        print("="*60)
        
        # Initialize services
        html_service = PredictionService()
        clean_service = CleanPredictionService()
        
        # Test document ID (Case 252)
        document_id = 252
        
        print(f"\n🔍 TESTING DOCUMENT {document_id}: Acknowledging Errors in Design")
        print("="*50)
        
        # Test 1: Compare section extraction
        print(f"\n📄 SECTION EXTRACTION COMPARISON:")
        print("-"*40)
        
        # Get sections from both services
        html_sections = html_service.get_document_sections(document_id)
        clean_sections = clean_service.get_document_sections(document_id)
        
        print(f"HTML Service sections: {list(html_sections.keys())}")
        print(f"Clean Service sections: {list(clean_sections.keys())}")
        
        # Compare key sections
        sections_to_compare = ['facts', 'references', 'discussion']
        
        for section_name in sections_to_compare:
            if section_name in html_sections and section_name in clean_sections:
                html_content = html_sections[section_name]
                clean_content = clean_sections[section_name]
                
                html_tags = html_content.count('<') + html_content.count('>')
                clean_tags = clean_content.count('<') + clean_content.count('>')
                
                print(f"\n📋 {section_name.upper()} section:")
                print(f"   HTML version: {len(html_content)} chars, {html_tags} HTML tags")
                print(f"   Clean version: {len(clean_content)} chars, {clean_tags} HTML tags")
                
                if clean_tags < html_tags:
                    improvement = html_tags - clean_tags
                    print(f"   🎯 IMPROVEMENT: Removed {improvement} HTML tags!")
                elif clean_tags == html_tags:
                    print(f"   ⚖️  Same content quality")
                
                # Show content samples for highly improved sections
                if section_name == 'references' and clean_tags < html_tags:
                    print(f"\n   📝 HTML Sample: {html_content[:150]}...")
                    print(f"   ✨ Clean Sample: {clean_content[:150]}...")
        
        # Test 2: Generate predictions (if desired)
        print(f"\n🚀 PREDICTION GENERATION TEST:")
        print("-"*40)
        
        # Generate with clean service (safer test)
        print(f"Generating prediction with CLEAN service...")
        clean_result = clean_service.generate_conclusion_prediction(document_id)
        
        if clean_result['success']:
            print(f"✅ Clean prediction generated successfully!")
            print(f"   Length: {len(clean_result['prediction'])} characters")
            print(f"   Condition: {clean_result['condition']}")
            print(f"   Content cleaned: {clean_result['metadata']['content_cleaned']}")
            print(f"   Sections used: {clean_result['metadata']['sections_included']}")
            
            # Show prompt sample
            prompt = clean_result['prompt']
            print(f"\n📄 Clean Prompt Sample (first 300 chars):")
            print(f"   {prompt[:300]}...")
            
            # Check for HTML in prompt
            html_in_prompt = prompt.count('<') + prompt.count('>')
            print(f"   HTML tags in prompt: {html_in_prompt}")
            
            if html_in_prompt == 0:
                print(f"   🎯 SUCCESS: Clean prompt with no HTML tags!")
            else:
                print(f"   ⚠️  Still has {html_in_prompt} HTML tags")
                
        else:
            print(f"❌ Clean prediction failed: {clean_result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    test_clean_vs_html()
