#!/usr/bin/env python3
"""
Fix Reasoning Trace Foreign Key Issue

Removes the foreign key constraint from reasoning_traces table that's causing
SQLAlchemy initialization errors with the Document model.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_foreign_key_constraint():
    """Remove foreign key constraint from reasoning_traces table"""
    print("🔧 Fixing reasoning_traces foreign key constraint...")
    
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ai_ethical_dm',
        'user': 'postgres',
        'password': 'PASS'
    }
    
    try:
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        # Check if constraint exists
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'reasoning_traces' 
            AND constraint_type = 'FOREIGN KEY';
        """)
        
        constraints = [row[0] for row in cursor.fetchall()]
        print(f"Found foreign key constraints: {constraints}")
        
        # Remove foreign key constraints
        for constraint_name in constraints:
            print(f"Dropping constraint: {constraint_name}")
            cursor.execute(f"ALTER TABLE reasoning_traces DROP CONSTRAINT {constraint_name};")
        
        # Commit changes
        conn.commit()
        
        # Verify constraint was removed
        cursor.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'reasoning_traces' 
            AND constraint_type = 'FOREIGN KEY';
        """)
        
        remaining_constraints = cursor.fetchall()
        
        if remaining_constraints:
            print(f"⚠️  Still have constraints: {remaining_constraints}")
            return False
        else:
            print("✅ All foreign key constraints removed successfully")
            return True
        
    except Exception as e:
        print(f"❌ Error fixing foreign key constraint: {e}")
        if 'conn' in locals():
            conn.rollback()
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def main():
    """Main function"""
    print("🔧 ProEthica Reasoning Trace Foreign Key Fix")
    print("=" * 50)
    
    success = fix_foreign_key_constraint()
    
    if success:
        print("\n✅ Foreign key constraint fix completed successfully!")
        print("📋 reasoning_traces table no longer has foreign key to document")
        print("🔗 Relationship handled via @property method in model")
        print("\nThe case list should now load without SQLAlchemy errors.")
    else:
        print("\n❌ Foreign key constraint fix failed")
        print("You may need to manually remove constraints or recreate the table")

if __name__ == "__main__":
    main()
