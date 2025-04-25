
import os
import sys
from app import db
from app.models.ontology import Ontology

# Patch for OntologyMCPServer class
def _load_ontology_from_db(self, ontology_source):
    """
    Load ontology content from database.
    Replaces _load_graph_from_file to enable database-sourced ontologies.
    
    Args:
        ontology_source: Source identifier for ontology (filename)
        
    Returns:
        RDFLib Graph object with loaded ontology
    """
    from rdflib import Graph
    
    g = Graph()
    if not ontology_source:
        print(f"Error: No ontology source specified", file=sys.stderr)
        return g

    # Handle cleanup of file extension if present
    if ontology_source.endswith('.ttl'):
        domain_id = ontology_source[:-4]  # Remove .ttl extension
    else:
        domain_id = ontology_source
        
    try:
        # Try to fetch from database
        from flask import current_app
        with current_app.app_context():
            ontology = Ontology.query.filter_by(domain_id=domain_id).first()
            if ontology:
                print(f"Loading ontology '{domain_id}' from database", file=sys.stderr)
                g.parse(data=ontology.content, format="turtle")
                print(f"Successfully loaded ontology '{domain_id}' from database", file=sys.stderr)
                return g
                
        # If not found in database, fall back to file (for backward compatibility)
        print(f"Ontology '{domain_id}' not found in database, checking filesystem", file=sys.stderr)
        ontology_path = os.path.join(ONTOLOGY_DIR, ontology_source)
        if not os.path.exists(ontology_path):
            print(f"Error: Ontology file not found: {ontology_path}", file=sys.stderr)
            return g

        g.parse(ontology_path, format="turtle")
        print(f"Successfully loaded ontology from {ontology_path}", file=sys.stderr)
    except Exception as e:
        print(f"Failed to load ontology: {str(e)}", file=sys.stderr)
    return g

# Replace the original method with our DB-aware version
OntologyMCPServer._load_graph_from_file = _load_ontology_from_db
