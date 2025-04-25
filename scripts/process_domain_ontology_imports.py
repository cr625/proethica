#!/usr/bin/env python3
"""
Process domain ontology imports.

This script:
1. Analyzes existing domain-specific ontologies in the database
2. Identifies import relationships based on content (owl:imports, prefix declarations)
3. Updates the database with these import relationships
4. Ensures proper dependency chain from domain ontologies to base ontologies
"""

import sys
import os
import logging
import re
from rdflib import Graph

# Add the parent directory to the path so we can import app correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.models.ontology import Ontology
from app.models.ontology_import import OntologyImport

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        if ontology.base_uri == uri:
            return ontology
        
        # Check if URI ends with the domain ID
        if uri.endswith(f"/{ontology.domain_id}") or uri.endswith(f"#{ontology.domain_id}"):
            return ontology
    
    return None

def process_domain_ontology_imports():
    """
    Process domain ontology imports.
    """
    try:
        app = create_app()
        with app.app_context():
            # Load all ontologies
            ontologies = Ontology.query.all()
            logger.info(f"Found {len(ontologies)} ontologies in the database")
            
            # Get base ontologies
            base_ontologies = [o for o in ontologies if o.is_base]
            domain_ontologies = [o for o in ontologies if not o.is_base]
            
            logger.info(f"Found {len(base_ontologies)} base ontologies and {len(domain_ontologies)} domain ontologies")
            
            # Process each domain ontology
            for ontology in domain_ontologies:
                logger.info(f"Processing domain ontology: {ontology.name} (ID={ontology.id})")
                
                # Extract imports and prefixes
                import_uris, prefixes = extract_imports_from_content(ontology.content)
                
                logger.info(f"Found {len(import_uris)} explicit imports and {len(prefixes)} prefixes")
                
                # Find imported ontologies based on URIs
                for uri in import_uris:
                    imported = find_ontology_by_uri(uri, ontologies)
                    if imported:
                        # Add import relationship
                        ontology.add_import(imported)
                        logger.info(f"Added import relationship: {ontology.name} imports {imported.name}")
                
                # Check prefix declarations for implicit imports
                implicit_imports = []
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
                        intermediate = next((o for o in base_ontologies if 'intermediate' in o.domain_id.lower()), None)
                        if intermediate:
                            implicit_imports.append(intermediate)
                    
                    elif any(pattern in uri for pattern in bfo_uri_patterns):
                        # Find BFO ontology  
                        bfo = next((o for o in base_ontologies if 'bfo' in o.domain_id.lower()), None)
                        if bfo:
                            implicit_imports.append(bfo)
                
                # Add implicit imports
                for imported in implicit_imports:
                    ontology.add_import(imported)
                    logger.info(f"Added implicit import: {ontology.name} imports {imported.name} (based on prefix)")
                
                # If no imports were found but we have base ontologies, 
                # add intermediate ontology as implicit import
                if not ontology.imports.count() and base_ontologies:
                    # Find intermediate ontology
                    intermediate = next((o for o in base_ontologies if 'intermediate' in o.domain_id.lower()), None)
                    if intermediate:
                        ontology.add_import(intermediate)
                        logger.info(f"Added default import: {ontology.name} imports {intermediate.name}")
            
            # Commit changes
            db.session.commit()
            logger.info("Successfully processed domain ontology imports")
            return True
    except Exception as e:
        logger.error(f"Error processing domain ontology imports: {str(e)}")
        if 'db' in locals() and 'session' in dir(db):
            db.session.rollback()
        return False

if __name__ == '__main__':
    if process_domain_ontology_imports():
        logger.info("Successfully processed domain ontology imports")
    else:
        logger.error("Failed to process domain ontology imports")
        sys.exit(1)
