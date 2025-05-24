#!/usr/bin/env python3
"""
Verify that the experiment_run_id constraint has been fixed.
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

from app import create_app, db
from sqlalchemy import text

def test_constraint_fix():
    """Test if experiment_run_id can now be NULL."""
    
    print("🧪 TESTING CONSTRAINT FIX")
    print("=" * 30)
    
    app = create_app()
    
    with app.app_context():
        try:
            # Check the column is nullable
            result = db.session.execute(text("""
                SELECT column_name, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"Column nullable status: {column_info[1]}")
                if column_info[1] == 'YES':
                    print("✅ Column is now nullable!")
                    
                    # Test creating a record with NULL experiment_run_id
                    from app.models.experiment import Prediction
                    from app.models.document import Document
                    
                    # Find a test document
                    test_doc = Document.query.first()
                    if test_doc:
                        # Create test prediction with NULL experiment_run_id
                        test_prediction = Prediction(
                            experiment_run_id=None,
                            document_id=test_doc.id,
                            condition='test',
                            target='conclusion',
                            prediction_text='Test prediction for constraint verification',
                            prompt='Test prompt',
                            reasoning='Test reasoning',
                            created_at=datetime.utcnow(),
                            meta_info={'test': True}
                        )
                        
                        db.session.add(test_prediction)
                        db.session.commit()
                        
                        print("✅ Successfully created prediction with NULL experiment_run_id!")
                        
                        # Clean up
                        db.session.delete(test_prediction)
                        db.session.commit()
                        print("🧹 Test prediction cleaned up")
                        
                        return True
                    else:
                        print("❌ No test document found")
                        return False
                else:
                    print("❌ Column is still NOT NULL!")
                    return False
            else:
                print("❌ Column not found!")
                return False
                
        except Exception as e:
            print(f"❌ Error: {str(e)}")
            db.session.rollback()
            return False

def main():
    print("🚀 Constraint Fix Verification")
    print("===============================")
    
    success = test_constraint_fix()
    
    if success:
        print("\n🎉 SUCCESS!")
        print("The constraint fix is working correctly.")
        print("Quick predictions should now work in the web interface.")
    else:
        print("\n❌ FAILURE!")
        print("The constraint issue is not yet resolved.")
    
    return success

if __name__ == "__main__":
    main()
