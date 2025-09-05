#!/usr/bin/env python3
"""
Fix Database User Password

Updates the proethica_user password in PostgreSQL to match the .env file configuration.
This ensures consistency between the application configuration and database authentication.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_database_user_password():
    """Update proethica_user password to 'PASS' to match .env configuration"""
    print("🔧 Fixing database user password...")
    
    # Connect as postgres admin user
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
        
        # Check if proethica_user exists
        cursor.execute("""
            SELECT usename FROM pg_user WHERE usename = 'proethica_user';
        """)
        
        user_exists = cursor.fetchone()
        
        if user_exists:
            print("Found existing proethica_user, updating password...")
            cursor.execute("ALTER USER proethica_user WITH PASSWORD 'PASS';")
        else:
            print("proethica_user does not exist, creating user...")
            cursor.execute("CREATE USER proethica_user WITH PASSWORD 'PASS';")
            
            # Grant database access
            cursor.execute("GRANT CONNECT ON DATABASE ai_ethical_dm TO proethica_user;")
            cursor.execute("GRANT USAGE ON SCHEMA public TO proethica_user;")
            cursor.execute("GRANT CREATE ON SCHEMA public TO proethica_user;")
            
            # Grant permissions on existing tables (basic permissions)
            cursor.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO proethica_user;")
            cursor.execute("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO proethica_user;")
            
            print("✅ Created proethica_user with full database access")
        
        # Specifically ensure reasoning trace permissions
        print("Ensuring reasoning trace table permissions...")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_traces TO proethica_user;")
        cursor.execute("GRANT ALL PRIVILEGES ON TABLE reasoning_steps TO proethica_user;")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_traces_id_seq TO proethica_user;")
        cursor.execute("GRANT USAGE, SELECT ON SEQUENCE reasoning_steps_id_seq TO proethica_user;")
        
        # Commit changes
        conn.commit()
        
        # Verify by attempting to connect as proethica_user
        print("Testing connection as proethica_user...")
        test_conn_params = {
            'host': 'localhost',
            'port': 5432,
            'database': 'ai_ethical_dm',
            'user': 'proethica_user',
            'password': 'PASS'
        }
        
        test_conn = psycopg2.connect(**test_conn_params)
        test_cursor = test_conn.cursor()
        
        # Test basic operations
        test_cursor.execute("SELECT 1 as test;")
        result = test_cursor.fetchone()
        assert result[0] == 1, "Basic query should work"
        
        # Test INSERT on reasoning_traces
        test_cursor.execute("""
            INSERT INTO reasoning_traces (case_id, feature_type, session_id)
            VALUES (1, 'test', 'password_test_001')
            RETURNING id;
        """)
        test_id = test_cursor.fetchone()[0]
        print(f"✅ INSERT test as proethica_user successful: created trace {test_id}")
        
        # Clean up test data
        test_cursor.execute("DELETE FROM reasoning_traces WHERE id = %s;", (test_id,))
        test_conn.commit()
        
        test_cursor.close()
        test_conn.close()
        
        print("✅ proethica_user authentication and permissions working!")
        return True
        
    except Exception as e:
        print(f"❌ Error fixing database user password: {e}")
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
    print("🔧 ProEthica Database User Password Fix")
    print("=" * 50)
    
    success = fix_database_user_password()
    
    if success:
        print("\n✅ Database user password fix completed successfully!")
        print("👤 proethica_user password updated to 'PASS'")
        print("🔗 Password now matches .env configuration")
        print("🔧 Full database permissions granted")
        print("\nApplication should now connect properly with .env credentials.")
    else:
        print("\n❌ Database user password fix failed")
        print("You may need to check PostgreSQL user management")

if __name__ == "__main__":
    main()
