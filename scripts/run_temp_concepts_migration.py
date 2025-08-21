#!/usr/bin/env python3
"""
Script to run the temporary concepts table migration.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_migration():
    """Run the temporary concepts migration."""
    
    # Get database connection details from environment or config
    db_url = os.environ.get('DATABASE_URL') or os.environ.get('SQLALCHEMY_DATABASE_URI')
    
    if not db_url:
        # Try to load from config file
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.py')
            if os.path.exists(config_path):
                import importlib.util
                spec = importlib.util.spec_from_file_location("config", config_path)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                db_url = getattr(config_module, 'SQLALCHEMY_DATABASE_URI', None)
        except Exception as e:
            print(f"Warning: Could not load config: {e}")
    
    if not db_url:
        print("Error: No database URL found in environment or config")
        return False
    
    # Parse database URL
    # Format: postgresql://user:password@host:port/database
    if db_url.startswith('postgresql://'):
        db_url = db_url[13:]  # Remove postgresql://
    
    parts = db_url.split('@')
    if len(parts) != 2:
        print(f"Error: Invalid database URL format")
        return False
    
    user_pass = parts[0].split(':')
    host_db = parts[1].split('/')
    host_port = host_db[0].split(':')
    
    db_config = {
        'user': user_pass[0],
        'password': user_pass[1] if len(user_pass) > 1 else '',
        'host': host_port[0],
        'port': host_port[1] if len(host_port) > 1 else '5432',
        'database': host_db[1] if len(host_db) > 1 else 'postgres'
    }
    
    # Read migration SQL
    migration_path = os.path.join(
        os.path.dirname(__file__),
        'database_migrations',
        'add_temporary_concepts_table.sql'
    )
    
    with open(migration_path, 'r') as f:
        migration_sql = f.read()
    
    # Connect and run migration
    try:
        print(f"Connecting to database {db_config['database']} at {db_config['host']}:{db_config['port']}")
        conn = psycopg2.connect(**db_config)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("Running migration...")
        cursor.execute(migration_sql)
        
        # Verify table was created
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_name = 'temporary_concepts'
        """)
        result = cursor.fetchone()
        
        if result and result[0] > 0:
            print("✅ Migration successful! Table 'temporary_concepts' created.")
            
            # Show table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = 'temporary_concepts'
                ORDER BY ordinal_position
            """)
            
            print("\nTable structure:")
            for col in cursor.fetchall():
                nullable = "" if col[2] == "NO" else " (nullable)"
                print(f"  - {col[0]}: {col[1]}{nullable}")
        else:
            print("❌ Migration may have failed - table not found")
            return False
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error running migration: {e}")
        return False


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)