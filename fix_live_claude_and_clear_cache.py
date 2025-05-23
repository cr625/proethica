#!/usr/bin/env python3
"""
Fix script to enable live Claude LLM and clear cached military medical content.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_live_claude_and_clear_cache():
    """Enable live Claude LLM and clear cached military medical content."""
    
    print("=== Fixing Live Claude and Clearing Cache ===")
    
    # 1. Configure environment for live Claude
    print("1. Configuring environment for live Claude...")
    os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = 'false'  # Use real LLM
    os.environ['FORCE_MOCK_LLM'] = 'false'  # Disable mock forcing
    os.environ['ANTHROPIC_MODEL'] = 'claude-3-7-sonnet-20250219'  # Set specific model
    
    print(f"   USE_MOCK_GUIDELINE_RESPONSES: {os.environ.get('USE_MOCK_GUIDELINE_RESPONSES')}")
    print(f"   FORCE_MOCK_LLM: {os.environ.get('FORCE_MOCK_LLM')}")
    print(f"   ANTHROPIC_MODEL: {os.environ.get('ANTHROPIC_MODEL')}")
    
    # Create app context for database access
    app = create_app('config')
    
    with app.app_context():
        try:
            # 2. Check and clear stored predictions with military content
            print("\n2. Checking stored predictions for military medical content...")
            
            from app.models.experiment import Prediction
            from sqlalchemy import text
            
            # Query predictions containing military keywords
            military_keywords = ['military', 'medical', 'triage', 'patient', 'allocating', 'limited resources']
            
            military_predictions = []
            for keyword in military_keywords:
                predictions = Prediction.query.filter(
                    Prediction.prediction_text.ilike(f'%{keyword}%')
                ).all()
                for pred in predictions:
                    if pred.id not in [p.id for p in military_predictions]:
                        military_predictions.append(pred)
            
            print(f"   Found {len(military_predictions)} predictions with military content")
            
            if military_predictions:
                print("   Military predictions found:")
                for pred in military_predictions[:3]:  # Show first 3
                    print(f"     ID {pred.id}: {str(pred.prediction_text)[:100]}...")
                
                # Ask what to do
                print(f"   Total: {len(military_predictions)} predictions with military content")
                
                # For now, let's delete Case 252 predictions specifically
                case_252_predictions = [p for p in military_predictions if p.document_id == 252]
                if case_252_predictions:
                    print(f"   Deleting {len(case_252_predictions)} Case 252 predictions with military content...")
                    for pred in case_252_predictions:
                        app.db.session.delete(pred)
                    app.db.session.commit()
                    print("   ✓ Case 252 military predictions deleted")
            
            # 3. Clear application caches
            print("\n3. Clearing application caches...")
            
            # Clear URL processing cache
            try:
                from app.services.case_url_processor.case_cache import UrlProcessingCache
                cache = UrlProcessingCache()
                cache.clear_cache()
                print("   ✓ URL processing cache cleared")
            except Exception as e:
                print(f"   ⚠️  Could not clear URL cache: {e}")
            
            # Clear ontology cache
            try:
                from app.services.ontology_entity_service import OntologyEntityService
                ontology_service = OntologyEntityService()
                ontology_service.invalidate_cache()
                print("   ✓ Ontology cache cleared")
            except Exception as e:
                print(f"   ⚠️  Could not clear ontology cache: {e}")
            
            # 4. Test live Claude configuration
            print("\n4. Testing live Claude configuration...")
            
            from app.services.llm_service import LLMService
            
            # Create new LLM service with live configuration
            llm_service = LLMService()
            print(f"   LLM Type: {type(llm_service.llm)}")
            print(f"   Model Name: {llm_service.model_name}")
            
            # Test with a simple prompt
            test_prompt = "Explain the key principles of engineering ethics in one sentence."
            try:
                response = llm_service.llm.invoke(test_prompt)
                print(f"   Test response: {str(response)[:200]}...")
                
                # Check if it's mock or real
                if "I understand you're looking at an engineering ethics scenario" in str(response):
                    print("   ❌ Still using mock responses")
                elif "claude" in str(type(llm_service.llm)).lower() or len(str(response)) > 100:
                    print("   ✅ Using live Claude")
                else:
                    print("   ⚠️  Unclear if using live Claude")
                    
            except Exception as e:
                print(f"   ❌ Error testing Claude: {e}")
            
            # 5. Generate a fresh prediction for Case 252
            print("\n5. Generating fresh Case 252 prediction with live Claude...")
            
            try:
                from app.services.experiment.prediction_service import PredictionService
                prediction_service = PredictionService()
                
                result = prediction_service.generate_conclusion_prediction(document_id=252)
                
                if result.get('success'):
                    prediction = result.get('prediction', '')
                    print(f"   ✓ Fresh prediction generated")
                    print(f"   Length: {len(str(prediction))}")
                    print(f"   Preview: {str(prediction)[:200]}...")
                    
                    # Check for military content
                    military_found = any(kw.lower() in str(prediction).lower() for kw in military_keywords)
                    if military_found:
                        print("   ❌ Fresh prediction still contains military content")
                    else:
                        print("   ✅ Fresh prediction is clean (no military content)")
                        
                else:
                    print(f"   ❌ Failed to generate fresh prediction: {result.get('error')}")
                    
            except Exception as e:
                print(f"   ❌ Error generating fresh prediction: {e}")
                
        except Exception as e:
            print(f"Error in fix: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n=== Fix Complete ===")
    print("Restart your Flask application to ensure all changes take effect.")

if __name__ == "__main__":
    fix_live_claude_and_clear_cache()
