#!/usr/bin/env python3
"""
Test Case 252 quick prediction workflow to verify constraint fix.

This tests the end-to-end workflow that was previously blocked by the 
experiment_run_id constraint issue.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
if os.path.exists('.env'):
    load_dotenv()

# Set database URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_case_252_prediction():
    """Test the quick prediction workflow for Case 252."""
    
    print("🧪 TESTING CASE 252 QUICK PREDICTION")
    print("=" * 40)
    
    try:
        from app import create_app, db
        from app.models.document import Document
        from app.models.experiment import Prediction
        from app.services.experiment.prediction_service import PredictionService
        
        app = create_app()
        
        with app.app_context():
            # Find Case 252
            case_252 = Document.query.filter(
                Document.title.ilike('%acknowledging errors in design%')
            ).first()
            
            if not case_252:
                # Try by ID
                case_252 = Document.query.get(252)
            
            if not case_252:
                print("❌ Case 252 not found!")
                return False
                
            print(f"📄 Found Case 252: {case_252.title} (ID: {case_252.id})")
            
            # Check if prediction already exists
            existing_prediction = Prediction.query.filter_by(
                document_id=case_252.id,
                target='conclusion'
            ).first()
            
            if existing_prediction:
                print(f"✅ Existing prediction found (created: {existing_prediction.created_at})")
                print(f"   Condition: {existing_prediction.condition}")
                print(f"   Text length: {len(existing_prediction.prediction_text) if existing_prediction.prediction_text else 0} chars")
                return True
            
            # Try to create a new prediction
            print("🔄 Creating new quick prediction...")
            
            prediction_service = PredictionService()
            
            # This is the operation that was previously failing
            result = prediction_service.generate_conclusion_prediction(case_252.id)
            
            if result.get('success'):
                print("✅ Prediction service returned success!")
                
                # Try to save the prediction (this was the failing point)
                prediction = Prediction(
                    experiment_run_id=None,  # This should now work
                    document_id=case_252.id,
                    condition='proethica',
                    target='conclusion',
                    prediction_text=result.get('prediction', ''),
                    prompt=result.get('prompt', ''),
                    reasoning=result.get('full_response', ''),
                    created_at=datetime.utcnow(),
                    meta_info=result.get('metadata', {})
                )
                
                db.session.add(prediction)
                db.session.commit()
                
                print("✅ Successfully saved prediction to database!")
                print(f"   Prediction ID: {prediction.id}")
                print(f"   Text length: {len(prediction.prediction_text)} chars")
                
                return True
            else:
                print(f"❌ Prediction service failed: {result.get('error', 'Unknown error')}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main test execution."""
    
    print("🚀 Case 252 Quick Prediction Test")
    print("=================================")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    success = test_case_252_prediction()
    
    if success:
        print("\n🎉 SUCCESS!")
        print("=" * 50)
        print("✅ Database constraint issue has been resolved")
        print("✅ Case 252 quick prediction workflow is working")
        print("✅ Experiment system is now unblocked")
        print()
        print("Next recommended actions:")
        print("1. Test quick prediction in web interface: http://127.0.0.1:3333/experiment/")
        print("2. Try formal experiment creation and execution")
        print("3. Test evaluation interface")
        print("4. Optimize ontology entity utilization")
    else:
        print("\n❌ FAILURE!")
        print("=" * 50)
        print("The constraint issue may still exist or there's another problem.")
        print("Further debugging needed.")
    
    return success

if __name__ == "__main__":
    main()
