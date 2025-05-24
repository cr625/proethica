#!/usr/bin/env python3
"""
Fix experiment_run_id constraint issue.

This script updates the database schema to allow NULL values for experiment_run_id
in the experiment_predictions table, enabling standalone quick predictions.
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Add the parent directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set database URL like other scripts do
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app import create_app, db
from sqlalchemy import text

def fix_experiment_constraint():
    """Fix the experiment_run_id constraint to allow NULL values."""
    
    print("🔧 FIXING EXPERIMENT CONSTRAINT ISSUE")
    print("=" * 50)
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        try:
            # Check current constraint
            print("📊 Checking current database schema...")
            
            result = db.session.execute(text("""
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"   Current nullable status: {column_info[1]}")
                print(f"   Current default: {column_info[2]}")
            else:
                print("   ❌ Column not found!")
                return False
            
            # If already nullable, we're done
            if column_info[1] == 'YES':
                print("   ✅ Column is already nullable!")
                return True
            
            # Make the column nullable
            print("🔄 Making experiment_run_id column nullable...")
            
            db.session.execute(text("""
                ALTER TABLE experiment_predictions 
                ALTER COLUMN experiment_run_id DROP NOT NULL
            """))
            
            db.session.commit()
            print("   ✅ Successfully made experiment_run_id nullable!")
            
            # Verify the change
            print("🔍 Verifying the fix...")
            
            result = db.session.execute(text("""
                SELECT column_name, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            column_info = result.fetchone()
            if column_info and column_info[1] == 'YES':
                print("   ✅ Verification successful - column is now nullable!")
                return True
            else:
                print("   ❌ Verification failed!")
                return False
                
        except Exception as e:
            print(f"   ❌ Error fixing constraint: {str(e)}")
            db.session.rollback()
            return False

def test_quick_prediction():
    """Test that quick predictions now work."""
    
    print("\n🧪 TESTING QUICK PREDICTION FUNCTIONALITY")
    print("=" * 50)
    
    app = create_app()
    
    with app.app_context():
        try:
            from app.models.experiment import Prediction
            from app.models.document import Document
            
            # Find a test case
            test_case = Document.query.filter(
                Document.document_type.in_(['case', 'case_study'])
            ).first()
            
            if not test_case:
                print("   ❌ No test cases found!")
                return False
            
            print(f"📝 Using test case: {test_case.title} (ID: {test_case.id})")
            
            # Create a test prediction with NULL experiment_run_id
            test_prediction = Prediction(
                experiment_run_id=None,  # This should now work
                document_id=test_case.id,
                condition='test',
                target='conclusion',
                prediction_text='Test prediction',
                prompt='Test prompt',
                reasoning='Test reasoning',
                created_at=datetime.utcnow(),
                meta_info={'test': True}
            )
            
            db.session.add(test_prediction)
            db.session.commit()
            
            print("   ✅ Successfully created prediction with NULL experiment_run_id!")
            
            # Clean up test prediction
            db.session.delete(test_prediction)
            db.session.commit()
            
            print("   🧹 Cleaned up test prediction")
            return True
            
        except Exception as e:
            print(f"   ❌ Test failed: {str(e)}")
            db.session.rollback()
            return False

def main():
    """Main execution function."""
    
    print("🚀 ProEthica Experiment Constraint Fix")
    print("=====================================")
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 1: Fix the constraint
    constraint_fixed = fix_experiment_constraint()
    
    if not constraint_fixed:
        print("\n❌ FAILED TO FIX CONSTRAINT - ABORTING")
        return False
    
    # Step 2: Test the fix
    test_passed = test_quick_prediction()
    
    if not test_passed:
        print("\n❌ CONSTRAINT FIXED BUT TEST FAILED")
        return False
    
    print("\n🎉 SUCCESS!")
    print("=" * 50)
    print("✅ Database constraint fixed successfully")
    print("✅ Quick predictions should now work")
    print("✅ Experiment system is unblocked")
    print()
    print("Next steps:")
    print("1. Test quick prediction in web interface")
    print("2. Try Case 252 end-to-end workflow")
    print("3. Create formal experiment run")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
