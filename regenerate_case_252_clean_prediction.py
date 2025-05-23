#!/usr/bin/env python3
"""
Regenerate Case 252 prediction with enhanced clean text approach.

This script:
1. Clears existing Case 252 predictions from database
2. Regenerates using our optimized PredictionService with clean text
3. Validates the result shows HTML-free prompts
"""

import os
import sys
import logging
from datetime import datetime

# Set environment
os.environ['FLASK_APP'] = 'run.py'
os.environ['FLASK_ENV'] = 'development'

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to regenerate Case 252 prediction."""
    
    print("🔄 REGENERATING CASE 252 PREDICTION WITH CLEAN TEXT APPROACH")
    print("=" * 70)
    
    try:
        # Import application using run.py like other test scripts
        from run import app
        from app import db
        from app.models.experiment import Prediction
        from app.models.document import Document
        from app.services.experiment.prediction_service import PredictionService
        
        with app.app_context():
            print("1. 🗑️  Clearing existing Case 252 predictions...")
            
            # Find existing predictions for Case 252
            existing_predictions = Prediction.query.filter_by(
                document_id=252,
                target='conclusion'
            ).all()
            
            if existing_predictions:
                print(f"   Found {len(existing_predictions)} existing predictions")
                for prediction in existing_predictions:
                    print(f"   Deleting prediction ID {prediction.id} (condition: {prediction.condition})")
                    db.session.delete(prediction)
                
                db.session.commit()
                print("   ✅ Existing predictions cleared")
            else:
                print("   No existing predictions found")
            
            print("\n2. 🧬 Regenerating with enhanced clean text approach...")
            
            # Verify Case 252 exists
            document = Document.query.get(252)
            if not document:
                print("   ❌ ERROR: Case 252 not found in database")
                return
                
            print(f"   Document: {document.title}")
            
            # Initialize enhanced prediction service
            prediction_service = PredictionService()
            
            # Generate clean prediction
            print("   Generating conclusion prediction...")
            result = prediction_service.generate_conclusion_prediction(document_id=252)
            
            if result.get('success'):
                print("   ✅ Prediction generated successfully!")
                
                # Extract text from AIMessage if needed
                full_response = result.get('full_response', '')
                if hasattr(full_response, 'content'):
                    reasoning_text = full_response.content
                else:
                    reasoning_text = str(full_response)
                
                # Store the prediction
                prediction = Prediction(
                    experiment_run_id=None,  # Standalone prediction
                    document_id=252,
                    condition='proethica',
                    target='conclusion',
                    prediction_text=result.get('prediction', ''),
                    prompt=result.get('prompt', ''),
                    reasoning=reasoning_text,
                    created_at=datetime.utcnow(),
                    meta_info=result.get('metadata', {})
                )
                
                db.session.add(prediction)
                db.session.commit()
                
                print(f"   ✅ Prediction stored with ID {prediction.id}")
                
                # Validate the prompt is clean
                prompt = result.get('prompt', '')
                html_indicators = ['<div', '<span', '<p>', '</div>', '</span>', '</p>']
                html_found = any(indicator in prompt for indicator in html_indicators)
                
                print(f"\n3. 🧪 Validation Results:")
                print(f"   Prompt length: {len(prompt)} characters")
                print(f"   HTML detected: {'❌ YES' if html_found else '✅ NO'}")
                
                if html_found:
                    print("   ⚠️  WARNING: HTML still detected in prompt")
                    # Show first occurrence
                    for indicator in html_indicators:
                        if indicator in prompt:
                            idx = prompt.find(indicator)
                            snippet = prompt[max(0, idx-50):idx+100]
                            print(f"   First HTML found: ...{snippet}...")
                            break
                else:
                    print("   🎉 SUCCESS: Prompt is completely HTML-free!")
                
                print(f"\n4. 📊 Metadata Summary:")
                metadata = result.get('metadata', {})
                sections = metadata.get('sections_included', [])
                entities = metadata.get('ontology_entities', {})
                
                print(f"   Sections included: {len(sections)} - {sections}")
                print(f"   Ontology entities: {entities.get('total', 0)} total")
                
                # Sample the prompt
                print(f"\n5. 📄 Prompt Preview (first 500 chars):")
                print(f"   {prompt[:500]}...")
                
                print(f"\n🎯 REGENERATION COMPLETE!")
                print(f"   Case 252 now has a clean prediction ready for web interface")
                print(f"   Visit: http://localhost:3333/experiment/case_comparison/252")
                
            else:
                print(f"   ❌ ERROR: {result.get('error', 'Unknown error')}")
                
    except Exception as e:
        logger.exception(f"Error regenerating Case 252 prediction: {str(e)}")
        print(f"❌ FATAL ERROR: {str(e)}")

if __name__ == "__main__":
    main()
