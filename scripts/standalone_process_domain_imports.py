#!/usr/bin/env python3
"""
Standalone script to process domain ontology imports.

This script does not rely on the Flask app context, making it more reliable
for database operations. It:

1. Analyzes existing domain-specific ontologies in the database
2. Identifies import relationships based on content (owl:imports, prefix declarations)
3. Updates the database with these import relationships
4. Ensures proper dependency chain from domain ontologies to base ontologies
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

def get_all_ontologies(conn):
    """Get all ontologies from the database."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name, description, domain_id, content, created_at, updated_at,
               is_base, is_editable, base_uri
        FROM ontologies
    """)
    
    rows = cursor.fetchall()
    cursor.close()
    
    ontologies = []
    for row in rows:
        ontologies.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'domain_id': row[3],
            'content': row[4],
            'created_at': row[5],
            'updated_at': row[6],
            'is_base': row[7] if row[7] is not None else False,
            'is_editable': row[8] if row[8] is not None else True,
            'base_uri': row[9]
        })
    
    return ontologies

def extract_imports_from_content(content, format='turtle'):
    """
    Extract import URIs and prefix declarations from ontology content.
    
    Args:
        content: The ontology content as string
        format: Format of the ontology content (default: 'turtle')
        
    Returns:
        tuple: (list of import URIs, dict of prefix -> namespace mappings)
    """
    # Initialize return values
    import_uris = []
    prefixes = {}
    
    if not content:
        return import_uris, prefixes
    
    # Parse the ontology with rdflib
    g = Graph()
    try:
        g.parse(data=content, format=format)
    except Exception as e:
        logger.error(f"Error parsing ontology: {str(e)}")
        
        # Even if parsing fails, try to extract prefixes manually
        prefix_matches = re.findall(r'@prefix\s+(\w+):\s+<([^>]+)>', content)
        for prefix, uri in prefix_matches:
            prefixes[prefix] = uri
            
        # And try to extract imports manually
        import_matches = re.findall(r'owl:imports\s+<([^>]+)>', content)
        import_uris.extend(import_matches)
        
        return import_uris, prefixes
    
    # Find owl:imports statements
    owl_imports = 'http://www.w3.org/2002/07/owl#imports'
    for s, p, o in g.triples((None, None, None)):
        if str(p) == owl_imports:
            import_uris.append(str(o))
    
    # Get all prefixes
    for prefix, namespace in g.namespaces():
        prefixes[prefix] = str(namespace)
    
    return import_uris, prefixes

def find_ontology_by_uri(uri, ontologies):
    """Find an ontology by its URI or domain ID."""
    for ontology in ontologies:
        # Check exact URI match
        if ontology['base_uri'] == uri:
            return ontology
        
        # Check if URI ends with the domain ID
        if uri.endswith(f"/{ontology['domain_id']}") or uri.endswith(f"#{ontology['domain_id']}"):
            return ontology
    
    return None

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

def process_domain_ontology_imports():
    """Process domain ontology imports."""
    try:
        # Connect to database
        conn = get_db_connection()
        
        # Get all ontologies
        ontologies = get_all_ontologies(conn)
        logger.info(f"Found {len(ontologies)} ontologies in the database")
        
        # Get base ontologies
        base_ontologies = [o for o in ontologies if o['is_base']]
        domain_ontologies = [o for o in ontologies if not o['is_base']]
        
        logger.info(f"Found {len(base_ontologies)} base ontologies and {len(domain_ontologies)} domain ontologies")
        
        # Find intermediate ontology for default import
        intermediate_ontology = None
        for o in base_ontologies:
            if 'intermediate' in o['domain_id'].lower():
                intermediate_ontology = o
                break
        
        if not intermediate_ontology:
            logger.warning("No intermediate ontology found for default imports")
        
        # Process each domain ontology
        for ontology in domain_ontologies:
            logger.info(f"Processing domain ontology: {ontology['name']} (ID={ontology['id']})")
            
            # Extract imports and prefixes
            import_uris, prefixes = extract_imports_from_content(ontology['content'])
            
            logger.info(f"Found {len(import_uris)} explicit imports and {len(prefixes)} prefixes")
            
            # Track all imports for this ontology
            imported_ontology_ids = set()
            
            # Find imported ontologies based on URIs
            for uri in import_uris:
                imported = find_ontology_by_uri(uri, ontologies)
                if imported:
                    imported_ontology_ids.add(imported['id'])
                    logger.info(f"Found explicit import: {ontology['name']} imports {imported['name']}")
            
            # Check prefix declarations for implicit imports
            intermediate_uri_patterns = [
                'http://proethica.org/ontology/intermediate',
                'proethica-intermediate'
            ]
            
            bfo_uri_patterns = [
                'http://purl.obolibrary.org/obo',
                'bfo'
            ]
            
            # Check if any prefix refers to intermediate ontology
            for prefix, uri in prefixes.items():
                if any(pattern in uri for pattern in intermediate_uri_patterns):
                    # Find intermediate ontology
                    for o in base_ontologies:
                        if 'intermediate' in o['domain_id'].lower():
                            imported_ontology_ids.add(o['id'])
                            logger.info(f"Found implicit import (based on prefix {prefix}): {ontology['name']} imports {o['name']}")
                            break
                
                elif any(pattern in uri for pattern in bfo_uri_patterns):
                    # Find BFO ontology
                    for o in base_ontologies:
                        if 'bfo' in o['domain_id'].lower():
                            imported_ontology_ids.add(o['id'])
                            logger.info(f"Found implicit import (based on prefix {prefix}): {ontology['name']} imports {o['name']}")
                            break
            
            # If no imports were found and we have an intermediate ontology, add it as default import
            if not imported_ontology_ids and intermediate_ontology:
                imported_ontology_ids.add(intermediate_ontology['id'])
                logger.info(f"Added default import: {ontology['name']} imports {intermediate_ontology['name']}")
            
            # Create any missing import relationships
            for imported_id in imported_ontology_ids:
                if not get_import_relationship(conn, ontology['id'], imported_id):
                    create_import_relationship(conn, ontology['id'], imported_id)
                    logger.info(f"Created import relationship in database: ontology {ontology['id']} imports ontology {imported_id}")
        
        # Close connection
        conn.close()
        
        logger.info("Successfully processed domain ontology imports")
        return True
    
    except Exception as e:
        logger.error(f"Error processing domain ontology imports: {str(e)}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if process_domain_ontology_imports():
        logger.info("Successfully processed domain ontology imports")
    else:
        logger.error("Failed to process domain ontology imports")
        sys.exit(1)
