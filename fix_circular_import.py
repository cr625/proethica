#!/usr/bin/env python3
# Script to fix the circular import issue between app/__init__.py and app/models/domain.py

import os
import sys
import shutil
import time

def backup_file(file_path):
    """Create a backup of the file"""
    backup_path = f"{file_path}.bak.{time.strftime('%Y%m%d%H%M%S')}"
    shutil.copy2(file_path, backup_path)
    print(f"Created backup at {backup_path}")

# 1. Fix model files to import db from app.models, not from app directly
def fix_model_files():
    model_files = [
        "app/models/domain.py",
        "app/models/world.py",
        "app/models/role.py",
        # Add other model files that have "from app import db" here
    ]
    
    for model_path in model_files:
        backup_file(model_path)
        
        with open(model_path, 'r') as f:
            content = f.read()
        
        # Replace import statement
        new_content = content.replace("from app import db", "from app.models import db")
        
        with open(model_path, 'w') as f:
            f.write(new_content)
        
        print(f"Updated {model_path} to import db from app.models")

# 2. Fix mcp/load_from_db.py to avoid importing from app.models if needed
def fix_load_from_db_py():
    load_from_db_path = "mcp/load_from_db.py"
    backup_file(load_from_db_path)
    
    new_content = '''# Module to load ontologies from database
# This file is included by mcp/__init__.py

import os
import sys
import psycopg2
import json
from urllib.parse import urlparse

# Add the project root to Python path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def get_db_connection():
    """
    Get a database connection using environment variables or .env file
    """
    # Try to get connection info from environment
    db_url = os.environ.get("DATABASE_URL")
    
    # If not found in environment, try to read from .env file
    if not db_url:
        try:
            with open(os.path.join(os.path.dirname(__file__), "..", ".env")) as f:
                for line in f:
                    if line.startswith("DATABASE_URL="):
                        db_url = line.strip().split("=", 1)[1].strip(\'"\')
                        break
        except Exception as e:
            print(f"Warning: Could not read .env file: {e}")
    
    if not db_url:
        raise ValueError("DATABASE_URL not found in environment or .env file")
    
    # Parse the URL
    url = urlparse(db_url)
    
    # Connect to database
    return psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port or 5432
    )

def load_ontology_from_db(ontology_name):
    """
    Load an ontology from the database directly using psycopg2 to avoid circular imports.
    
    Args:
        ontology_name (str): Name of the ontology to load
        
    Returns:
        dict: Ontology data structure
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Look for the ontology in the ontologies table
        cursor.execute("SELECT id, name, description, file_path FROM ontologies WHERE name = %s", (ontology_name,))
        result = cursor.fetchone()
        
        if not result:
            print(f"Warning: Ontology \'{ontology_name}\' not found in database")
            return {"name": ontology_name, "loaded": False, "error": "Not found"}
        
        ontology_id, name, description, file_path = result
        
        # Get triples related to this ontology
        cursor.execute("""
            SELECT subject, predicate, object, is_literal 
            FROM entity_triples
            WHERE ontology_id = %s
        """, (ontology_id,))
        
        triples = []
        for triple_row in cursor.fetchall():
            subject, predicate, object_val, is_literal = triple_row
            triples.append({
                "subject": subject,
                "predicate": predicate,
                "object": object_val,
                "is_literal": is_literal
            })
        
        conn.close()
        
        return {
            "name": name,
            "description": description,
            "file_path": file_path,
            "triples": triples,
            "loaded": True,
            "source": "database"
        }
        
    except Exception as e:
        print(f"Error loading ontology from database: {e}")
        return {"name": ontology_name, "loaded": False, "error": str(e)}
'''
    
    with open(load_from_db_path, 'w') as f:
        f.write(new_content)
    
    print(f"Updated {load_from_db_path} to avoid circular imports")

if __name__ == "__main__":
    print("Fixing circular import issues...")
    fix_model_files()
    fix_load_from_db_py()
    print("Circular import fixes completed!")
