#!/usr/bin/env python3
"""
Standalone script to import base ontologies into the database.

This script does not rely on the Flask app context, making it more reliable
for database migrations.

Imports:
1. BFO ontology (if available)
2. ProEthica Intermediate ontology
3. Sets up proper import relationships between them
4. Ensures they are marked as base ontologies (non-editable)
"""

import sys
import os
import logging
import re
import traceback
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from rdflib import Graph

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()

# Database connection parameters - parse from DATABASE_URL
def get_db_connection():
    """Get database connection from DATABASE_URL in .env."""
    db_url = None
    
    # First try to get from environment
    db_url = os.environ.get("DATABASE_URL")
    
    # If not in environment, parse from .env file
    if not db_url:
        try:
            with open(os.path.join(os.path.dirname(__file__), '..', '.env'), 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
                        break
        except Exception as e:
            logger.error(f"Error reading .env file: {e}")
    
    if db_url:
        # Parse connection details from URL
        # Format: postgresql://user:password@host:port/dbname
        parts = db_url.replace('postgresql://', '').split('@')
        auth = parts[0].split(':')
        host_db = parts[1].split('/')
        host_port = host_db[0].split(':')
        
        try:
            conn = psycopg2.connect(
                dbname=host_db[1],
                user=auth[0],
                password=auth[1],
                host=host_port[0],
                port=host_port[1] if len(host_port) > 1 else '5432'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            logger.info(f"Connected to database: {host_port[0]}:{host_port[1] if len(host_port) > 1 else '5432'}/{host_db[1]}")
            return conn
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
    
    # Fallback to default connection
    try:
        logger.warning("Using fallback database connection")
        conn = psycopg2.connect(
            dbname="ai_ethical_dm",
            user="postgres",
            password="PASS",
            host="localhost",
            port="5433"
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to fallback database: {e}")
        raise

def load_file(path):
    """Load file content from path."""
    try:
        with open(path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger.error(f"Error reading file {path}: {str(e)}")
        return None

def extract_ontology_details(content, format='turtle'):
    """Extract ontology URI, label, and description from content."""
    if not content:
        return None, None, None
    
    g = Graph()
    try:
        g.parse(data=content, format=format)
    except Exception as e:
        logger.error(f"Error parsing ontology: {str(e)}")
        return None, None, None
    
    # Try to find ontology declaration
    ontology_uri = None
    ontology_label = None
    ontology_description = None
    
    # Find ontology declaration
    for s, p, o in g.triples((None, None, None)):
        # Look for owl:Ontology type declaration
        if str(p) == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' and \
           str(o) == 'http://www.w3.org/2002/07/owl#Ontology':
            ontology_uri = str(s)
            break
    
    # If found, try to get label and comment
    if ontology_uri:
        for s, p, o in g.triples((None, None, None)):
            if str(s) != ontology_uri:
                continue
                
            if str(p) == 'http://www.w3.org/2000/01/rdf-schema#label':
                ontology_label = str(o)
            elif str(p) == 'http://www.w3.org/2000/01/rdf-schema#comment':
                ontology_description = str(o)
    
    # If no ontology URI was found, try to infer from prefixes or base
    if not ontology_uri:
        # Try to find a @base directive
        base_match = re.search(r'@base\s+<([^>]+)>', content)
        if base_match:
            ontology_uri = base_match.group(1)
    
    return ontology_uri, ontology_label, ontology_description

def get_ontology_by_domain_id(conn, domain_id):
    """Get ontology record by domain_id."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, description, domain_id, content, created_at, updated_at,
               is_base, is_editable, base_uri
        FROM ontologies
        WHERE domain_id = %s
    """, (domain_id,))
    
    row = cursor.fetchone()
    cursor.close()
    
    if row:
        # Convert to dict for easier handling
        return {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'domain_id': row[3],
            'content': row[4],
            'created_at': row[5],
            'updated_at': row[6],
            'is_base': row[7],
            'is_editable': row[8],
            'base_uri': row[9]
        }
    
    return None

def update_ontology(conn, ontology_id, updates):
    """Update an ontology record."""
    cursor = conn.cursor()
    
    # Create SQL SET clause dynamically
    set_parts = []
    values = []
    
    for field, value in updates.items():
        set_parts.append(f"{field} = %s")
        values.append(value)
    
    # Add the WHERE condition value
    values.append(ontology_id)
    
    # Execute the update
    cursor.execute(f"""
        UPDATE ontologies
        SET {", ".join(set_parts)},
            updated_at = NOW()
        WHERE id = %s
    """, values)
    
    cursor.close()

def create_ontology(conn, ontology_data):
    """Create a new ontology record."""
    cursor = conn.cursor()
    
    # Create field and placeholder lists dynamically
    fields = []
    placeholders = []
    values = []
    
    for field, value in ontology_data.items():
        fields.append(field)
        placeholders.append("%s")
        values.append(value)
    
    # Execute the insert
    cursor.execute(f"""
        INSERT INTO ontologies
            ({", ".join(fields)})
        VALUES
            ({", ".join(placeholders)})
        RETURNING id
    """, values)
    
    ontology_id = cursor.fetchone()[0]
    cursor.close()
    
    return ontology_id

def get_import_relationship(conn, importing_id, imported_id):
    """Check if an import relationship already exists."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM ontology_imports
        WHERE importing_ontology_id = %s AND imported_ontology_id = %s
    """, (importing_id, imported_id))
    
    row = cursor.fetchone()
    cursor.close()
    
    return row[0] if row else None

def create_import_relationship(conn, importing_id, imported_id):
    """Create an import relationship between ontologies."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ontology_imports
            (importing_ontology_id, imported_ontology_id, created_at)
        VALUES
            (%s, %s, NOW())
        RETURNING id
    """, (importing_id, imported_id))
    
    import_id = cursor.fetchone()[0]
    cursor.close()
    
    return import_id

def import_base_ontologies():
    """Import base ontologies into the database."""
    try:
        # Connect to database
        conn = get_db_connection()
        
        # Check if BFO is available (web version or local file)
        bfo_content = None
        bfo_path = os.path.join(os.path.dirname(__file__), '..', 'mcp', 'ontology', 'bfo-core.ttl')
        
        if os.path.exists(bfo_path):
            bfo_content = load_file(bfo_path)
            logger.info(f"Loaded BFO from {bfo_path}")
        
        # Import BFO if available
        bfo_ontology_id = None
        if bfo_content:
            bfo_uri, bfo_label, bfo_desc = extract_ontology_details(bfo_content)
            
            # Look for existing BFO ontology
            existing_bfo = get_ontology_by_domain_id(conn, 'bfo')
            
            if existing_bfo:
                logger.info("BFO ontology already exists in the database")
                bfo_ontology_id = existing_bfo['id']
                
                # Update properties
                updates = {
                    'is_base': True,
                    'is_editable': False
                }
                
                if bfo_uri:
                    updates['base_uri'] = bfo_uri
                
                if bfo_label and existing_bfo['name'] != bfo_label:
                    updates['name'] = bfo_label
                
                if bfo_desc and existing_bfo['description'] != bfo_desc:
                    updates['description'] = bfo_desc
                
                if bfo_content != existing_bfo['content']:
                    updates['content'] = bfo_content
                
                # Only update if there are changes
                if updates:
                    update_ontology(conn, existing_bfo['id'], updates)
                    logger.info("Updated BFO ontology in database")
            else:
                # Create new BFO ontology
                bfo_ontology_id = create_ontology(conn, {
                    'name': bfo_label or "Basic Formal Ontology",
                    'description': bfo_desc or "Upper-level ontology for scientific data integration",
                    'domain_id': 'bfo',
                    'content': bfo_content,
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                    'is_base': True,
                    'is_editable': False,
                    'base_uri': bfo_uri or "http://purl.obolibrary.org/obo/bfo.owl"
                })
                logger.info(f"Created BFO ontology in database with ID {bfo_ontology_id}")
        
        # Load ProEthica Intermediate ontology
        intermediate_path = os.path.join(os.path.dirname(__file__), '..', 'mcp', 'ontology', 'proethica-intermediate.ttl')
        intermediate_content = load_file(intermediate_path)
        
        if not intermediate_content:
            logger.error(f"Could not load intermediate ontology from {intermediate_path}")
            return False
        
        int_uri, int_label, int_desc = extract_ontology_details(intermediate_content)
        
        # Look for existing intermediate ontology
        existing_int = get_ontology_by_domain_id(conn, 'proethica-intermediate')
        
        intermediate_ontology_id = None
        if existing_int:
            logger.info("ProEthica Intermediate ontology already exists in the database")
            intermediate_ontology_id = existing_int['id']
            
            # Update properties
            updates = {
                'is_base': True,
                'is_editable': False
            }
            
            if int_uri:
                updates['base_uri'] = int_uri
            
            if int_label and existing_int['name'] != int_label:
                updates['name'] = int_label
            
            if int_desc and existing_int['description'] != int_desc:
                updates['description'] = int_desc
            
            if intermediate_content != existing_int['content']:
                updates['content'] = intermediate_content
            
            # Only update if there are changes
            if updates:
                update_ontology(conn, existing_int['id'], updates)
                logger.info("Updated ProEthica Intermediate ontology in database")
        else:
            # Create new intermediate ontology
            intermediate_ontology_id = create_ontology(conn, {
                'name': int_label or "ProEthica Intermediate Ontology",
                'description': int_desc or "Mid-level ontology bridging BFO to domain-specific ethical frameworks",
                'domain_id': 'proethica-intermediate',
                'content': intermediate_content,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'is_base': True,
                'is_editable': False,
                'base_uri': int_uri or "http://proethica.org/ontology/intermediate"
            })
            logger.info(f"Created ProEthica Intermediate ontology in database with ID {intermediate_ontology_id}")
        
        # Set up import relationship if both ontologies exist
        if bfo_ontology_id and intermediate_ontology_id:
            # Check if import relationship already exists
            existing_import_id = get_import_relationship(conn, intermediate_ontology_id, bfo_ontology_id)
            
            if not existing_import_id:
                # Create import relationship
                import_id = create_import_relationship(conn, intermediate_ontology_id, bfo_ontology_id)
                logger.info(f"Created import relationship: intermediate ontology imports BFO (ID: {import_id})")
            else:
                logger.info(f"Import relationship already exists (ID: {existing_import_id})")
        
        # Close connection
        conn.close()
        
        logger.info("Successfully imported base ontologies")
        return True
    
    except Exception as e:
        logger.error(f"Error importing base ontologies: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if import_base_ontologies():
        logger.info("Successfully imported base ontologies")
    else:
        logger.error("Failed to import base ontologies")
        sys.exit(1)
