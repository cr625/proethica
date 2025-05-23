#!/usr/bin/env python3
"""
Test script to verify that the experiment_run_id constraint fix worked.
This will attempt to create a prediction without experiment_run_id.
"""

import os
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['SQLALCHEMY_TRACK_MODIFICATIONS'] = "false"
os.environ['USE_MOCK_GUIDELINE_RESPONSES'] = "true"
os.environ['ENVIRONMENT'] = "development"

from app import create_app, db
from app.models.experiment import Prediction

def test_constraint_fix():
    """Test creating a prediction without experiment_run_id."""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🧪 Testing constraint fix...")
            print("=" * 50)
            
            # Attempt to create a prediction without experiment_run_id
            test_prediction = Prediction(
                document_id=252,  # Case 252: "Acknowledging Errors in Design"
                target="conclusion",
                condition="baseline",
                prediction_text="Test baseline prediction",
                reasoning="Test reasoning",
                meta_info={"test": True, "constraint_fix_test": True}
                # Note: NOT setting experiment_run_id (should be None/NULL)
            )
            
            # Add to session and commit
            db.session.add(test_prediction)
            db.session.commit()
            
            print("✅ SUCCESS: Prediction created without experiment_run_id!")
            print(f"   - Prediction ID: {test_prediction.id}")
            print(f"   - Document ID: {test_prediction.document_id}")
            print(f"   - experiment_run_id: {test_prediction.experiment_run_id}")
            print(f"   - Created at: {test_prediction.created_at}")
            
            # Clean up test data
            db.session.delete(test_prediction)
            db.session.commit()
            print("✅ Test data cleaned up successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ FAILED: {e}")
            db.session.rollback()
            return False

def check_table_schema():
    """Check the current table schema for experiment_predictions."""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("\n🔍 Checking table schema...")
            print("=" * 50)
            
            # Query table information
            result = db.session.execute(db.text("""
                SELECT column_name, is_nullable, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            row = result.fetchone()
            if row:
                print(f"Column: {row[0]}")
                print(f"Nullable: {row[1]}")
                print(f"Data Type: {row[2]}")
                
                if row[1] == 'YES':
                    print("✅ experiment_run_id is now nullable")
                    return True
                else:
                    print("❌ experiment_run_id is still NOT NULL")
                    return False
            else:
                print("❌ Could not find experiment_run_id column")
                return False
                
        except Exception as e:
            print(f"❌ Schema check failed: {e}")
            return False

if __name__ == "__main__":
    print("🔧 Testing experiment_run_id constraint fix...")
    print("=" * 60)
    
    # Check schema first
    schema_ok = check_table_schema()
    
    if schema_ok:
        # Test constraint fix
        test_ok = test_constraint_fix()
        
        print("=" * 60)
        if test_ok:
            print("🎉 CONSTRAINT FIX SUCCESSFUL!")
            print("   - experiment_run_id is now nullable")
            print("   - Standalone predictions can be created")
            print("   - Ready to test Case 252 experiment workflow")
        else:
            print("❌ CONSTRAINT FIX FAILED!")
            print("   - Need to investigate further")
    else:
        print("❌ SCHEMA ISSUE - constraint may not have been fixed")
