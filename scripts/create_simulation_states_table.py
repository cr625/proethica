"""
Create the simulation_states table in the database.

This script creates a new table to store simulation state data.
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the database configuration
from app.config import config

def create_simulation_states_table():
    """Create the simulation_states table directly using SQL."""
    # Get database configuration
    db_config = config['default'].SQLALCHEMY_DATABASE_URI
    
    # Parse the database URI to get connection parameters
    # Format: postgresql://username:password@host:port/dbname
    db_uri = db_config.replace('postgresql://', '')
    
    # Split the URI into parts
    if '@' in db_uri:
        auth, host_db = db_uri.split('@')
        if ':' in auth:
            username, password = auth.split(':')
        else:
            username = auth
            password = ''
        
        if '/' in host_db:
            host_port, dbname = host_db.split('/')
            if ':' in host_port:
                host, port = host_port.split(':')
            else:
                host = host_port
                port = '5432'  # Default PostgreSQL port
        else:
            host = host_db
            port = '5432'
            dbname = 'postgres'  # Default database name
    else:
        # Simplified case for local connections
        if '/' in db_uri:
            host_port, dbname = db_uri.split('/')
        else:
            host_port = db_uri
            dbname = 'postgres'
        
        if ':' in host_port:
            host, port = host_port.split(':')
        else:
            host = host_port
            port = '5432'
        
        username = ''
        password = ''
    
    # Connect to the database
    try:
        # Create connection
        conn = psycopg2.connect(
            dbname=dbname,
            user=username,
            password=password,
            host=host,
            port=port
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Create cursor
        cursor = conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'simulation_states')")
        table_exists = cursor.fetchone()[0]
        
        if not table_exists:
            print("Creating simulation_states table...")
            
            # Create the table
            cursor.execute("""
                CREATE TABLE simulation_states (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(64) UNIQUE NOT NULL,
                    scenario_id INTEGER REFERENCES scenarios(id) NOT NULL,
                    user_id INTEGER REFERENCES users(id),
                    current_event_index INTEGER DEFAULT 0,
                    decisions JSONB DEFAULT '[]'::jsonb,
                    state_data JSONB NOT NULL,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
                    expires_at TIMESTAMP WITHOUT TIME ZONE
                )
            """)
            
            # Create index on session_id for faster lookups
            cursor.execute("CREATE INDEX idx_simulation_states_session_id ON simulation_states(session_id)")
            
            # Create index on expires_at for faster cleanup
            cursor.execute("CREATE INDEX idx_simulation_states_expires_at ON simulation_states(expires_at)")
            
            print("Table created successfully.")
        else:
            print("Table simulation_states already exists.")
        
        # Close cursor and connection
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error creating table: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    create_simulation_states_table()
