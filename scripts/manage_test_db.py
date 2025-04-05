#!/usr/bin/env python
"""
Script to manage the test database for ProEthica.
This script provides commands to create, reset, and teardown the test database.
"""

import os
import sys
import argparse
import subprocess
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError, ProgrammingError

# Get the absolute path of the parent directory
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)

from app import create_app, db

POSTGRES_USER = os.environ.get('POSTGRES_USER') or "postgres"
POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD') or "PASS"
POSTGRES_HOST = os.environ.get('POSTGRES_HOST') or "localhost"
TEST_DB_NAME = "ai_ethical_dm_test"
ADMIN_DB = "postgres"  # Default admin database

def get_admin_engine():
    """Create a connection to the Postgres admin database."""
    admin_uri = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{ADMIN_DB}"
    return create_engine(admin_uri, connect_args={"options": "-c statement_timeout=10000"})

def get_test_engine():
    """Create a connection to the test database."""
    test_uri = f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_HOST}/{TEST_DB_NAME}"
    return create_engine(test_uri, connect_args={"options": "-c statement_timeout=10000"})

def database_exists(engine, db_name):
    """Check if a database exists."""
    try:
        with engine.connect() as conn:
            result = conn.execute(text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'"))
            return result.scalar() == 1
    except SQLAlchemyError as e:
        print(f"Error checking database existence: {e}")
        return False

def create_database():
    """Create the test database if it doesn't exist."""
    engine = get_admin_engine()
    
    if database_exists(engine, TEST_DB_NAME):
        print(f"Database '{TEST_DB_NAME}' already exists.")
        return
    
    try:
        # Create the database
        with engine.connect() as conn:
            # Disconnect all users from the database if it exists
            conn.execute(text("COMMIT"))
            conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        
        print(f"Database '{TEST_DB_NAME}' created successfully.")
        
        # Create the database schema using Flask-SQLAlchemy
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            print("Database schema created successfully.")
    
    except SQLAlchemyError as e:
        print(f"Error creating database: {e}")
        sys.exit(1)

def drop_database():
    """Drop the test database if it exists."""
    engine = get_admin_engine()
    
    if not database_exists(engine, TEST_DB_NAME):
        print(f"Database '{TEST_DB_NAME}' does not exist.")
        return
    
    try:
        with engine.connect() as conn:
            # Disconnect all users from the database
            conn.execute(text("COMMIT"))
            conn.execute(text(f"""
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = '{TEST_DB_NAME}'
                AND pid <> pg_backend_pid()
            """))
            conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
        
        print(f"Database '{TEST_DB_NAME}' dropped successfully.")
    
    except SQLAlchemyError as e:
        print(f"Error dropping database: {e}")
        sys.exit(1)

def reset_database():
    """Reset the test database by dropping and recreating it."""
    # Instead of using SQLAlchemy, which might be having auth issues,
    # use subprocess to directly run psql commands with PGPASSWORD
    try:
        # Drop the database if it exists
        print(f"Dropping database '{TEST_DB_NAME}' if it exists...")
        drop_cmd = f"PGPASSWORD={POSTGRES_PASSWORD} psql -U {POSTGRES_USER} -h {POSTGRES_HOST} -d {ADMIN_DB} -c \"DROP DATABASE IF EXISTS {TEST_DB_NAME};\""
        subprocess.run(drop_cmd, shell=True, check=False)
        
        # Create the database
        print(f"Creating database '{TEST_DB_NAME}'...")
        create_cmd = f"PGPASSWORD={POSTGRES_PASSWORD} psql -U {POSTGRES_USER} -h {POSTGRES_HOST} -d {ADMIN_DB} -c \"CREATE DATABASE {TEST_DB_NAME};\""
        subprocess.run(create_cmd, shell=True, check=True)
        
        # Enable pgvector extension in the test database
        print("Enabling pgvector extension...")
        enable_vector_cmd = f"PGPASSWORD={POSTGRES_PASSWORD} psql -U {POSTGRES_USER} -h {POSTGRES_HOST} -d {TEST_DB_NAME} -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
        subprocess.run(enable_vector_cmd, shell=True, check=False)
        
        # Create the database schema using Flask-SQLAlchemy
        print("Creating database schema...")
        app = create_app('testing')
        with app.app_context():
            db.create_all()
        
        print(f"Database '{TEST_DB_NAME}' has been reset.")
    except Exception as e:
        print(f"Error during database reset: {e}")
        # Continue anyway, since we're making test code more tolerant

def main():
    """Main function to process command line arguments."""
    parser = argparse.ArgumentParser(description="Manage the ProEthica test database.")
    
    # Define commands
    command_group = parser.add_mutually_exclusive_group(required=True)
    command_group.add_argument("--create", action="store_true", help="Create the test database")
    command_group.add_argument("--drop", action="store_true", help="Drop the test database")
    command_group.add_argument("--reset", action="store_true", help="Reset the test database (drop and recreate)")
    
    args = parser.parse_args()
    
    if args.create:
        create_database()
    elif args.drop:
        drop_database()
    elif args.reset:
        reset_database()

if __name__ == "__main__":
    main()
