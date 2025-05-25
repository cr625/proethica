#!/usr/bin/env python3
"""
Direct database fix for experiment_run_id constraint.

This script connects directly to PostgreSQL to fix the NOT NULL constraint
without using Flask app context.
"""

import os
import sys
from dotenv import load_dotenv
import sqlalchemy as sa
from sqlalchemy import create_engine, text

# Load environment variables
if os.path.exists('.env'):
    load_dotenv()

def get_database_url():
    """Get the database URL from environment."""
    return os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')

def fix_constraint_direct():
    """Fix the constraint by connecting directly to the database."""
    
    print("🔧 DIRECT DATABASE CONSTRAINT FIX")
    print("=" * 40)
    
    try:
        # Create database engine
        db_url = get_database_url()
        print(f"📡 Connecting to database...")
        
        engine = create_engine(db_url)
        
        with engine.connect() as connection:
            # Check current constraint status
            print("📊 Checking current constraint status...")
            
            result = connection.execute(text("""
                SELECT column_name, is_nullable, column_default
                FROM information_schema.columns 
                WHERE table_name = 'experiment_predictions' 
                AND column_name = 'experiment_run_id'
            """))
            
            column_info = result.fetchone()
            if column_info:
                print(f"   Column: {column_info[0]}")
                print(f"   Nullable: {column_info[1]}")
                print(f"   Default: {column_info[2] or 'NULL'}")
                
                if column_info[1] == 'YES':
                    print("   ✅ Column is already nullable!")
                    return True
            else:
                print("   ❌ Column not found!")
                return False
            
            # Drop the NOT NULL constraint
            print("🔄 Making experiment_run_id column nullable...")
            
            connection.execute(text("""
                ALTER TABLE experiment_predictions 
                ALTER COLUMN experiment_run_id DROP NOT NULL
            """))
            
            connection.commit()
            print("   ✅ Successfully removed NOT NULL constraint!")
            
            # Verify the fix
            print("🔍 Verifying the change...")
            
            result = connection.execute(text("""
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
        print(f"   ❌ Error: {str(e)}")
        return False

def test_with_direct_insert():
    """Test by attempting to insert a record with NULL experiment_run_id."""
    
    print("\n🧪 TESTING WITH DIRECT INSERT")
    print("=" * 35)
    
    try:
        db_url = get_database_url()
        engine = create_engine(db_url)
        
        with engine.connect() as connection:
            # Try to insert a test record with NULL experiment_run_id
            print("📝 Inserting test record with NULL experiment_run_id...")
            
            # First, get a document ID to use
            result = connection.execute(text("""
                SELECT id FROM documents 
                WHERE document_type IN ('case', 'case_study') 
                LIMIT 1
            """))
            
            doc_row = result.fetchone()
            if not doc_row:
                print("   ❌ No test documents found!")
                return False
            
            doc_id = doc_row[0]
            print(f"   Using document ID: {doc_id}")
            
            # Insert test record
            connection.execute(text("""
                INSERT INTO experiment_predictions 
                (experiment_run_id, document_id, condition, target, prediction_text, prompt, reasoning, created_at, meta_info)
                VALUES 
                (NULL, :doc_id, 'test', 'conclusion', 'Test prediction', 'Test prompt', 'Test reasoning', NOW(), '{"test": true}')
            """), {"doc_id": doc_id})
            
            connection.commit()
            print("   ✅ Successfully inserted test record with NULL experiment_run_id!")
            
            # Clean up test record
            connection.execute(text("""
                DELETE FROM experiment_predictions 
                WHERE condition = 'test' AND prediction_text = 'Test prediction'
            """))
            
            connection.commit()
            print("   🧹 Test record cleaned up")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Test failed: {str(e)}")
        return False

def main():
    """Main execution function."""
    
    print("🚀 Direct Database Constraint Fix")
    print("=================================")
    print(f"Database URL: {get_database_url()}")
    print()
    
    # Step 1: Fix the constraint
    constraint_fixed = fix_constraint_direct()
    
    if not constraint_fixed:
        print("\n❌ FAILED TO FIX CONSTRAINT")
        return False
    
    # Step 2: Test the fix
    test_passed = test_with_direct_insert()
    
    if not test_passed:
        print("\n❌ CONSTRAINT FIXED BUT TEST FAILED")
        return False
    
    print("\n🎉 SUCCESS!")
    print("=" * 50)
    print("✅ Database constraint fixed successfully")
    print("✅ experiment_run_id can now be NULL")
    print("✅ Quick predictions should now work")
    print()
    print("Next steps:")
    print("1. Test quick prediction in web interface")
    print("2. Try Case 252 end-to-end workflow")
    print("3. Create formal experiment run")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
