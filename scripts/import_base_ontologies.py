#!/usr/bin/env python3
"""
Import base ontologies into the database.

This script:
1. Imports BFO ontology (if available)
2. Imports ProEthica Intermediate ontology
3. Sets up proper import relationships between them
4. Ensures they are marked as base ontologies (non-editable)

These base ontologies serve as the foundation for domain-specific ontologies
and provide the core entity types used across the system.
"""

import sys
import os
import logging
import re
from rdflib import Graph
from datetime import datetime

# Add the parent directory to the path so we can import app correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import os
from dotenv import load_dotenv
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import traceback

# Load .env file
load_dotenv()

# Parse DATABASE_URL from .env file or environment
def get_db_connection():
    """Get database connection parameters from .env."""
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        # Fallback to parsing from .env file
        try:
            with open(os.path.join(os.path.dirname(__file__), '..', '.env'), 'r') as f:
                for line in f:
                    if line.startswith('DATABASE_URL='):
                        db_url = line.strip().split('=', 1)[1]
        except:
            pass
    
    if db_url:
        # Format: postgresql://user:password@host:port/dbname
        parts = db_url.replace('postgresql://', '').split('@')
        auth = parts[0].split(':')
        host_db = parts[1].split('/')
        host_port = host_db[0].split(':')
        
        # Create connection
        conn = psycopg2.connect(
            dbname=host_db[1],
            user=auth[0],
            password=auth[1],
            host=host_port[0],
            port=host_port[1] if len(host_port) > 1 else '5432'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    
    # Fallback to default connection
    return psycopg2.connect(
        dbname="ai_ethical_dm",
        user="postgres",
        password="PASS",
        host="localhost",
        port="5433"
    )
from app.models.ontology import Ontology
from app.models.ontology_import import OntologyImport

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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

def import_base_ontologies():
    """
    Import base ontologies into the database.
    """
    try:
        app = create_app()
        with app.app_context():
            # Check if BFO is available (web version or local file)
            bfo_content = None
            bfo_path = os.path.join(os.path.dirname(__file__), '..', 'mcp', 'ontology', 'bfo-core.ttl')
            
            if os.path.exists(bfo_path):
                bfo_content = load_file(bfo_path)
                logger.info(f"Loaded BFO from {bfo_path}")
            
            # Import BFO if available
            bfo_ontology = None
            if bfo_content:
                bfo_uri, bfo_label, bfo_desc = extract_ontology_details(bfo_content)
                
                # Look for existing BFO ontology
                existing_bfo = Ontology.query.filter_by(domain_id='bfo').first()
                
                if existing_bfo:
                    logger.info("BFO ontology already exists in the database")
                    bfo_ontology = existing_bfo
                    
                    # Update properties
                    existing_bfo.is_base = True
                    existing_bfo.is_editable = False
                    existing_bfo.base_uri = bfo_uri
                    
                    if bfo_label and not existing_bfo.name == bfo_label:
                        existing_bfo.name = bfo_label
                    if bfo_desc and not existing_bfo.description == bfo_desc:
                        existing_bfo.description = bfo_desc
                    if bfo_content != existing_bfo.content:
                        existing_bfo.content = bfo_content
                        existing_bfo.updated_at = datetime.utcnow()
                        
                else:
                    # Create new BFO ontology
                    bfo_ontology = Ontology(
                        name=bfo_label or "Basic Formal Ontology",
                        description=bfo_desc or "Upper-level ontology for scientific data integration",
                        domain_id='bfo',
                        content=bfo_content,
                        is_base=True,
                        is_editable=False,
                        base_uri=bfo_uri or "http://purl.obolibrary.org/obo/bfo.owl"
                    )
                    db.session.add(bfo_ontology)
                    logger.info("Created BFO ontology in database")
            
            # Load ProEthica Intermediate ontology
            intermediate_path = os.path.join(os.path.dirname(__file__), '..', 'mcp', 'ontology', 'proethica-intermediate.ttl')
            intermediate_content = load_file(intermediate_path)
            
            if not intermediate_content:
                logger.error(f"Could not load intermediate ontology from {intermediate_path}")
                return False
            
            int_uri, int_label, int_desc = extract_ontology_details(intermediate_content)
            
            # Look for existing intermediate ontology
            existing_int = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
            
            if existing_int:
                logger.info("ProEthica Intermediate ontology already exists in the database")
                intermediate_ontology = existing_int
                
                # Update properties
                existing_int.is_base = True
                existing_int.is_editable = False
                existing_int.base_uri = int_uri
                
                if int_label and not existing_int.name == int_label:
                    existing_int.name = int_label
                if int_desc and not existing_int.description == int_desc:
                    existing_int.description = int_desc
                if intermediate_content != existing_int.content:
                    existing_int.content = intermediate_content
                    existing_int.updated_at = datetime.utcnow()
            else:
                # Create new intermediate ontology
                intermediate_ontology = Ontology(
                    name=int_label or "ProEthica Intermediate Ontology",
                    description=int_desc or "Mid-level ontology bridging BFO to domain-specific ethical frameworks",
                    domain_id='proethica-intermediate',
                    content=intermediate_content,
                    is_base=True,
                    is_editable=False,
                    base_uri=int_uri or "http://proethica.org/ontology/intermediate"
                )
                db.session.add(intermediate_ontology)
                logger.info("Created ProEthica Intermediate ontology in database")
            
            # Set up import relationship if both ontologies exist
            if bfo_ontology and intermediate_ontology:
                # Check if import relationship already exists
                existing_import = OntologyImport.query.filter_by(
                    importing_ontology_id=intermediate_ontology.id,
                    imported_ontology_id=bfo_ontology.id
                ).first()
                
                if not existing_import:
                    # Create import relationship
                    import_rel = OntologyImport(
                        importing_ontology=intermediate_ontology,
                        imported_ontology=bfo_ontology
                    )
                    db.session.add(import_rel)
                    logger.info("Created import relationship: intermediate ontology imports BFO")
            
            # Commit changes
            db.session.commit()
            logger.info("Successfully imported base ontologies")
            return True
    except Exception as e:
        logger.error(f"Error importing base ontologies: {str(e)}")
        if 'db' in locals() and 'session' in dir(db):
            db.session.rollback()
        return False

if __name__ == '__main__':
    if import_base_ontologies():
        logger.info("Successfully imported base ontologies")
    else:
        logger.error("Failed to import base ontologies")
        sys.exit(1)
