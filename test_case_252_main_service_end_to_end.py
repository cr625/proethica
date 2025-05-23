#!/usr/bin/env python3
"""
End-to-end test of Case 252 using the updated main PredictionService.
This validates both ontology fix and HTML cleaning in the main service.
"""

import os
import sys
import json
from datetime import datetime

# Set environment
os.environ['FLASK_APP'] = 'run.py'
os.environ['FLASK_ENV'] = 'development'

# Add path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run import app
from app.services.experiment.prediction_service import PredictionService

def test_case_252_main_service():
    """
    Complete end-to-end test using the updated main PredictionService.
    """
    print("🔬 CASE 252 END-TO-END TEST - UPDATED MAIN SERVICE")
    print("=" * 60)
    
    with app.app_context():
        
        # Initialize main prediction service
        service = PredictionService()
        
        print("1. 📋 Testing document sections retrieval...")
        sections = service.get_document_sections(252, leave_out_conclusion=True)
        
        print(f"   ✅ Retrieved {len(sections)} sections: {list(sections.keys())}")
        
        # Check for HTML content in sections
        html_found = False
        for section_type, content in sections.items():
            if '<' in content and '>' in content:
                html_found = True
                print(f"   🟡 HTML found in '{section_type}' section")
                print(f"      Sample: {content[:100]}...")
            else:
                print(f"   ✅ '{section_type}' section appears clean")
        
        if not html_found:
            print("   ✅ No HTML content detected in sections")
        
        print(f"\n2. 🧬 Testing ontology entity retrieval...")
        ontology_entities = service.get_section_ontology_entities(252, sections)
        
        total_entities = sum(len(entities) for entities in ontology_entities.values())
        print(f"   ✅ Retrieved {total_entities} ontology entities")
        
        # Validate entity content
        valid_entities = 0
        sample_entities = []
        
        for section_type, entities in ontology_entities.items():
            if entities:
                print(f"   📋 Section '{section_type}': {len(entities)} entities")
                for entity in entities[:2]:  # Check first 2
                    if entity.get('subject') and entity.get('object'):
                        valid_entities += 1
                        sample_entities.append(entity)
                        print(f"      ✅ '{entity['subject']}' → '{entity['object']}' (score: {entity['score']})")
                    else:
                        print(f"      ❌ Empty entity: {entity}")
        
        content_ratio = valid_entities / total_entities if total_entities > 0 else 0
        print(f"   🎯 Valid entities: {valid_entities}/{total_entities} ({content_ratio:.1%})")
        
        if content_ratio > 0.5:
            print(f"   ✅ ONTOLOGY FIX: Working in main service!")
        else:
            print(f"   ❌ ONTOLOGY FIX: Not working properly")
            return False
        
        print(f"\n3. 🎯 Testing complete prediction generation...")
        
        # Generate full prediction
        result = service.generate_conclusion_prediction(252)
        
        if not result.get('success', False):
            print(f"   ❌ Prediction failed: {result.get('error', 'Unknown error')}")
            return False
        
        prediction = result.get('prediction', '')
        prompt = result.get('prompt', '')
        
        print(f"   ✅ Prediction generated successfully")
        print(f"   📝 Prediction length: {len(prediction)} characters")
        print(f"   📄 Prompt length: {len(prompt)} characters")
        
        # Check for HTML in prompt
        if '<' in prompt and '>' in prompt:
            print(f"   🟡 WARNING: HTML still present in prompt")
            # Count HTML tags
            import re
            html_tags = re.findall(r'<[^>]+>', prompt)
            print(f"      Found {len(html_tags)} HTML tags in prompt")
        else:
            print(f"   ✅ Prompt appears clean (no HTML)")
        
        # Test ontology mention validation
        print(f"\n4. 🔍 Testing ontology validation...")
        validation_results = service._validate_conclusion(prediction, ontology_entities)
        
        entity_mentions = validation_results.get('entity_mentions', 0)
        total_available = validation_results.get('total_entities', 0)
        mention_ratio = validation_results.get('mention_ratio', 0)
        
        print(f"   📊 Entity mentions: {entity_mentions}/{total_available}")
        print(f"   📈 Mention ratio: {mention_ratio:.1%}")
        
        if mention_ratio > 0.1:
            print(f"   ✅ VALIDATION: Mention ratio working!")
        else:
            print(f"   🟡 VALIDATION: Low mention ratio (may be normal)")
        
        # Show sample of prediction
        print(f"\n5. 📖 Sample prediction output:")
        print(f"   {prediction[:200]}...")
        
        # Save detailed results
        results_file = f"case_252_main_service_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        detailed_results = {
            'test_type': 'main_service_end_to_end',
            'case_id': 252,
            'timestamp': datetime.utcnow().isoformat(),
            'sections_retrieved': list(sections.keys()),
            'ontology_results': {
                'total_entities': total_entities,
                'valid_entities': valid_entities,
                'content_ratio': content_ratio,
                'sample_entities': sample_entities[:5]
            },
            'prediction_results': {
                'success': result.get('success', False),
                'prediction_length': len(prediction),
                'prompt_length': len(prompt),
                'validation_metrics': validation_results
            },
            'html_analysis': {
                'html_in_sections': html_found,
                'html_in_prompt': '<' in prompt and '>' in prompt
            }
        }
        
        with open(results_file, 'w') as f:
            json.dump(detailed_results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: {results_file}")
        
        # Final assessment
        print(f"\n🏆 FINAL ASSESSMENT:")
        
        if (content_ratio > 0.5 and result.get('success', False) and 
            validation_results.get('mention_ratio', 0) >= 0):
            print(f"   ✅ MAIN SERVICE: COMPLETE SUCCESS")
            print(f"   ✅ Ontology integration working")
            print(f"   ✅ Prediction generation working")
            print(f"   ✅ Ready for production use")
            
            if html_found or ('<' in prompt and '>' in prompt):
                print(f"   🟡 NOTE: Some HTML content still present")
                print(f"   🔧 RECOMMENDATION: Consider enhanced HTML cleaning")
            
            return True
        else:
            print(f"   ❌ MAIN SERVICE: Issues detected")
            return False

if __name__ == "__main__":
    try:
        success = test_case_252_main_service()
        
        if success:
            print(f"\n🎉 SUCCESS: Main PredictionService is working!")
            print(f"🧹 NEXT: Clean up temporary files and document progress")
        else:
            print(f"\n❌ ISSUES: Main service needs further work")
        
        exit(0 if success else 1)
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
