#!/usr/bin/env python3
"""
Script to update an existing world's ontology source in PostgreSQL.
"""

import os
import sys
import json
import argparse
import psycopg2
from psycopg2.extras import DictCursor
from configparser import ConfigParser

def get_db_connection():
    """Get a PostgreSQL database connection using app config."""
    # Try to get connection details from config.py
    try:
        # Add the parent directory to sys.path so we can import app modules
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sys.path.insert(0, parent_dir)
        
        # Try to import DATABASE_URI from app.config
        from app.config import DATABASE_URI
        
        # Parse the URI to get connection parameters
        # Format: postgresql://username:password@host:port/database
        conn_parts = DATABASE_URI.replace('postgresql://', '').split('@')
        user_pass = conn_parts[0].split(':')
        host_db = conn_parts[1].split('/')
        
        user = user_pass[0]
        password = user_pass[1] if len(user_pass) > 1 else ''
        host_port = host_db[0].split(':')
        host = host_port[0]
        port = host_port[1] if len(host_port) > 1 else '5432'
        dbname = host_db[1]
        
        print(f"Connecting to database: {dbname} on {host}:{port}")
        
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            dbname=dbname,
            user=user,
            password=password,
            host=host,
            port=port
        )
        
        return conn
    
    except ImportError:
        # If we can't import from app.config, try environment variables
        print("Couldn't import config, trying environment variables...")
        
        # Check for DATABASE_URL environment variable
        database_url = os.environ.get('DATABASE_URL')
        if database_url:
            if database_url.startswith('postgresql://'):
                # Parse the URL
                conn_parts = database_url.replace('postgresql://', '').split('@')
                user_pass = conn_parts[0].split(':')
                host_db = conn_parts[1].split('/')
                
                user = user_pass[0]
                password = user_pass[1] if len(user_pass) > 1 else ''
                host_port = host_db[0].split(':')
                host = host_port[0]
                port = host_port[1] if len(host_port) > 1 else '5432'
                dbname = host_db[1]
                
                print(f"Connecting to database from URL: {dbname} on {host}:{port}")
                
                # Connect to PostgreSQL
                conn = psycopg2.connect(
                    dbname=dbname,
                    user=user,
                    password=password,
                    host=host,
                    port=port
                )
                
                return conn
        
        # If we don't have a DATABASE_URL, try individual environment variables
        dbname = os.environ.get('DB_NAME', 'ai_ethical_dm')
        user = os.environ.get('DB_USER', 'postgres')
        password = os.environ.get('DB_PASSWORD', '')
        host = os.environ.get('DB_HOST', 'localhost')
        port = os.environ.get('DB_PORT', '5432')
        
        print(f"Connecting using environment variables: {dbname} on {host}:{port}")
        
        try:
            # Connect to PostgreSQL
            conn = psycopg2.connect(
                dbname=dbname,
                user=user,
                password=password,
                host=host,
                port=port
            )
            
            return conn
        except Exception as e:
            print(f"Error connecting to database: {str(e)}")
            print("\nPlease provide PostgreSQL connection details when running the script:")
            print("python scripts/update_world_ontology_postgres.py --host localhost --dbname ai_ethical_dm --user postgres --password yourpassword 12 engineering-ethics.ttl")
            sys.exit(1)

def update_world_ontology(world_id, ontology_source, conn=None, **kwargs):
    """
    Update a world's ontology source in the database.
    
    Args:
        world_id (int): The ID of the world to update
        ontology_source (str): The ontology source to set
        conn: Optional database connection
        **kwargs: Additional connection parameters if conn is None
    """
    # Connect to the database if no connection was provided
    if conn is None:
        try:
            # If kwargs are provided, use them to connect
            if kwargs:
                conn = psycopg2.connect(**kwargs)
            else:
                conn = get_db_connection()
        except Exception as e:
            print(f"Error connecting to database: {str(e)}")
            return False
    
    cursor = conn.cursor(cursor_factory=DictCursor)
    
    try:
        # Check if the world exists
        cursor.execute("SELECT id, name FROM worlds WHERE id = %s", (world_id,))
        world = cursor.fetchone()
        
        if not world:
            print(f"Error: World with ID {world_id} not found")
            return False
        
        print(f"Found world: {world['name']} (ID: {world['id']})")
        
        # Update the ontology source
        cursor.execute(
            "UPDATE worlds SET ontology_source = %s WHERE id = %s",
            (ontology_source, world_id)
        )
        
        # Commit the changes
        conn.commit()
        
        print(f"Successfully updated world {world['name']} (ID: {world['id']}) with ontology source: {ontology_source}")
        return True
        
    except Exception as e:
        print(f"Error updating world: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def main():
    """Parse arguments and update the world."""
    parser = argparse.ArgumentParser(description="Update a world's ontology source in PostgreSQL")
    parser.add_argument("world_id", type=int, help="The ID of the world to update")
    parser.add_argument("ontology_source", help="The ontology source to set")
    
    # Optional PostgreSQL connection parameters
    parser.add_argument("--host", help="PostgreSQL host")
    parser.add_argument("--port", help="PostgreSQL port")
    parser.add_argument("--dbname", help="PostgreSQL database name")
    parser.add_argument("--user", help="PostgreSQL user")
    parser.add_argument("--password", help="PostgreSQL password")
    
    args = parser.parse_args()
    
    # Extract PostgreSQL connection parameters if provided
    conn_params = {}
    if args.host:
        conn_params['host'] = args.host
    if args.port:
        conn_params['port'] = args.port
    if args.dbname:
        conn_params['dbname'] = args.dbname
    if args.user:
        conn_params['user'] = args.user
    if args.password:
        conn_params['password'] = args.password
    
    success = update_world_ontology(args.world_id, args.ontology_source, **conn_params)
    
    if success:
        print("\nNext steps:")
        print("1. Restart the MCP server if it's running")
        print("2. Refresh the world details page in the browser")
        print("3. Use test_ontology_extraction.py to verify entity extraction is working")
        print("\nCommand to test extraction:")
        print(f"python scripts/test_ontology_extraction.py {args.ontology_source}")
        
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
