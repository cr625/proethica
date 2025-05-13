"""
Migration script to create database tables for guidelines and related entity triples.
This script creates:
- The guidelines table for storing guideline documents
- Adds support for guideline_id in entity_triples table
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

# Add parent directory to path to import from app
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Load environment variables
load_dotenv()

# Get database connection parameters from environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5433')  # Updated to match docker-compose port mapping
DB_NAME = os.getenv('DB_NAME', 'ai_ethical_dm')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'PASS')  # Updated to match docker-compose password

def create_connection():
    """Create a database connection to the PostgreSQL database."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        print(f"Error connecting to the database: {e}")
    return conn

def create_guidelines_table(conn):
    """Create the guidelines table if it doesn't exist."""
    cur = conn.cursor()
    try:
        # Check if the guidelines table already exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'guidelines'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("Creating guidelines table...")
            cur.execute("""
                CREATE TABLE guidelines (
                    id SERIAL PRIMARY KEY,
                    world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
                    title VARCHAR(255) NOT NULL,
                    content TEXT,
                    source_url VARCHAR(1024),
                    file_path VARCHAR(1024),
                    file_type VARCHAR(50),
                    embedding FLOAT[],
                    guideline_metadata JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Create index on world_id for faster lookups
                CREATE INDEX idx_guidelines_world_id ON guidelines(world_id);
                
                -- Create index on created_at for sorting
                CREATE INDEX idx_guidelines_created_at ON guidelines(created_at);
            """)
            print("Guidelines table created successfully")
        else:
            print("Guidelines table already exists")
    except Exception as e:
        print(f"Error creating guidelines table: {e}")
    finally:
        cur.close()

def update_entity_triples_table(conn):
    """Update the entity_triples table to add guideline_id column if needed."""
    cur = conn.cursor()
    try:
        # Check if guideline_id column already exists in entity_triples
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_schema = 'public'
                AND table_name = 'entity_triples'
                AND column_name = 'guideline_id'
            );
        """)
        column_exists = cur.fetchone()[0]
        
        if not column_exists:
            print("Adding guideline_id column to entity_triples table...")
            cur.execute("""
                ALTER TABLE entity_triples
                ADD COLUMN guideline_id INTEGER REFERENCES guidelines(id) ON DELETE CASCADE;
                
                -- Create index on guideline_id for faster lookups
                CREATE INDEX idx_entity_triples_guideline_id ON entity_triples(guideline_id);
            """)
            print("Updated entity_triples table successfully")
        else:
            print("guideline_id column already exists in entity_triples table")
    except Exception as e:
        print(f"Error updating entity_triples table: {e}")
    finally:
        cur.close()

def add_guideline_relationship_to_worlds(conn):
    """Ensure that worlds table has guideline relationship defined (if needed)."""
    # This is handled in the ORM model, but we'll perform a check to make sure
    # the worlds table exists since guidelines depend on it
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'worlds'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            print("Error: worlds table does not exist. Please create it first.")
        else:
            print("Verified worlds table exists")
    except Exception as e:
        print(f"Error checking worlds table: {e}")
    finally:
        cur.close()

def update_db_version(conn, version_info):
    """Update database version information in the db_version table."""
    cur = conn.cursor()
    try:
        # Check if db_version table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name = 'db_version'
            );
        """)
        table_exists = cur.fetchone()[0]
        
        if not table_exists:
            # Create db_version table if it doesn't exist
            cur.execute("""
                CREATE TABLE db_version (
                    id SERIAL PRIMARY KEY,
                    version VARCHAR(50) NOT NULL,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("Created db_version table")
        
        # Insert new version record
        cur.execute("""
            INSERT INTO db_version (version, description)
            VALUES (%s, %s);
        """, (version_info["version"], version_info["description"]))
        print(f"Updated database version to {version_info['version']}")
    except Exception as e:
        print(f"Error updating database version: {e}")
    finally:
        cur.close()

def main():
    """Main function to run the migration."""
    print("Starting database migration for guidelines...")
    
    # Establish database connection
    conn = create_connection()
    if conn is None:
        return
    
    try:
        # Perform migrations
        add_guideline_relationship_to_worlds(conn)
        create_guidelines_table(conn)
        update_entity_triples_table(conn)
        
        # Update database version
        version_info = {
            "version": "1.5.0",
            "description": "Added guidelines tables and entity_triples relationship"
        }
        update_db_version(conn, version_info)
        
        print("Migration completed successfully")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
