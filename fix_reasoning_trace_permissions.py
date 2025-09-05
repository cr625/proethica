#!/usr/bin/env python3
"""
Fix Reasoning Trace Table Permissions

Grants proper permissions to the PostgreSQL user for the reasoning_traces 
and reasoning_steps tables so scenario generation can work.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_table_permissions():
    """Grant proper permissions to postgres user for reasoning trace tables"""
    print("🔧 Fixing reasoning_traces table permissions...")
    
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
        
        # Grant all privileges on reasoning_traces table to both users
        print("Granting permissions on reasoning_traces...")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_traces TO postgres;")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_traces TO proethica_user;")
        
        # Grant all privileges on reasoning_steps table to both users
        print("Granting permissions on reasoning_steps...")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_steps TO postgres;")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_steps TO proethica_user;")
        
        # Grant usage on sequences (for auto-increment IDs) to both users
        print("Granting sequence permissions...")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_traces_id_seq TO postgres;")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_steps_id_seq TO postgres;")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_traces_id_seq TO proethica_user;")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_steps_id_seq TO proethica_user;")
        
        # Commit changes
        conn.commit()
        
        # Verify permissions
        print("Verifying permissions...")
        cursor.execute("""
            SELECT table_name, privilege_type 
            FROM information_schema.table_privileges 
            WHERE table_name IN ('reasoning_traces', 'reasoning_steps')
            AND grantee = 'postgres';
        """)
        
        permissions = cursor.fetchall()
        print("Granted permissions:")
        for table, privilege in permissions:
            print(f"  ✅ {table}: {privilege}")
        
        # Test INSERT permission
        print("Testing INSERT permission...")
        cursor.execute("""
            INSERT INTO reasoning_traces (case_id, feature_type, session_id)
            VALUES (1, 'test', 'permission_test_001')
            RETURNING id;
        """)
        test_id = cursor.fetchone()[0]
        print(f"✅ INSERT test successful: created trace {test_id}")
        
        # Clean up test data
        cursor.execute("DELETE FROM reasoning_traces WHERE id = %s;", (test_id,))
        conn.commit()
        
        print("✅ All permissions fixed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing table permissions: {e}")
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
    print("🔧 ProEthica Reasoning Trace Permissions Fix")
    print("=" * 50)
    
    success = fix_table_permissions()
    
    if success:
        print("\n✅ Table permissions fix completed successfully!")
        print("📋 postgres user now has full access to reasoning_traces tables")
        print("🔧 INSERT, UPDATE, DELETE, SELECT permissions granted")
        print("🔢 Sequence permissions granted for auto-increment IDs")
        print("\nScenario generation should now work without permission errors.")
    else:
        print("\n❌ Table permissions fix failed")
        print("You may need to run this as a database administrator")

if __name__ == "__main__":
    main()
