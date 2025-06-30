#!/usr/bin/env python3
"""
Sync Ontology to Database Script

This script synchronizes TTL ontology files with the database, ensuring the database
contains the latest ontology definitions. It's designed to be run when the TTL files
have been updated outside of the application.

Usage:
    python sync_ontology_to_database.py [--domain DOMAIN_ID] [--ttl-path PATH]
    
    Without arguments, syncs the default proethica-intermediate ontology.
"""

import os
import sys
import argparse
from datetime import datetime, timezone
from pathlib import Path

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables from .env file if it exists
from dotenv import load_dotenv
if os.path.exists('.env'):
    load_dotenv()

# Set database URL
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app import create_app, db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, Namespace, RDF, RDFS, OWL
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default ontology configurations
DEFAULT_ONTOLOGIES = {
    'proethica-intermediate': {
        'path': 'ontologies/proethica-intermediate.ttl',
        'name': 'ProEthica Intermediate Ontology',
        'description': 'Intermediate ontology extending BFO for professional ethics modeling',
        'base_uri': 'http://www.semanticweb.org/proethica/proethica-intermediate#',
        'is_base': True,
        'is_editable': True
    },
    'bfo': {
        'path': 'ontologies/bfo.ttl',
        'name': 'Basic Formal Ontology (BFO)',
        'description': 'Upper-level ontology for information integration',
        'base_uri': 'http://purl.obolibrary.org/obo/bfo.owl#',
        'is_base': True,
        'is_editable': False
    },
    'engineering-ethics': {
        'path': 'ontologies/engineering-ethics.ttl',
        'name': 'Engineering Ethics Ontology',
        'description': 'Domain-specific ontology for engineering ethics',
        'base_uri': 'http://www.semanticweb.org/proethica/engineering-ethics#',
        'is_base': False,
        'is_editable': True
    }
}

def extract_ontology_metadata(graph, ttl_path):
    """
    Extract metadata from the ontology graph.
    
    Args:
        graph: RDFLib Graph object
        ttl_path: Path to the TTL file
        
    Returns:
        dict: Metadata including name, description, base_uri
    """
    metadata = {}
    
    # Try to find the main ontology IRI
    ontology_iris = list(graph.subjects(RDF.type, OWL.Ontology))
    if ontology_iris:
        ontology_iri = ontology_iris[0]
        metadata['base_uri'] = str(ontology_iri)
        
        # Try to extract label and comment
        labels = list(graph.objects(ontology_iri, RDFS.label))
        if labels:
            metadata['name'] = str(labels[0])
            
        comments = list(graph.objects(ontology_iri, RDFS.comment))
        if comments:
            metadata['description'] = str(comments[0])
    
    # Use filename as fallback name
    if 'name' not in metadata:
        metadata['name'] = Path(ttl_path).stem.replace('-', ' ').title()
    
    return metadata

def load_ttl_file(ttl_path):
    """
    Load and parse a TTL file.
    
    Args:
        ttl_path: Path to the TTL file
        
    Returns:
        tuple: (content_str, rdflib.Graph, metadata_dict)
    """
    if not os.path.exists(ttl_path):
        raise FileNotFoundError(f"TTL file not found: {ttl_path}")
    
    logger.info(f"Loading TTL file: {ttl_path}")
    
    # Read the file content
    with open(ttl_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Parse with RDFLib to validate and extract metadata
    graph = Graph()
    try:
        graph.parse(data=content, format='turtle')
        logger.info(f"Successfully parsed {len(graph)} triples from {ttl_path}")
    except Exception as e:
        logger.error(f"Failed to parse TTL file: {e}")
        raise
    
    # Extract metadata
    metadata = extract_ontology_metadata(graph, ttl_path)
    
    return content, graph, metadata

def get_next_version_number(ontology_id):
    """
    Get the next version number for an ontology.
    
    Args:
        ontology_id: ID of the ontology
        
    Returns:
        int: Next version number
    """
    latest_version = OntologyVersion.query.filter_by(
        ontology_id=ontology_id
    ).order_by(OntologyVersion.version_number.desc()).first()
    
    return (latest_version.version_number + 1) if latest_version else 1

def sync_ontology(domain_id, ttl_path, config=None):
    """
    Sync a TTL file to the database.
    
    Args:
        domain_id: Unique domain identifier for the ontology
        ttl_path: Path to the TTL file
        config: Optional configuration dict with metadata overrides
        
    Returns:
        Ontology: The created or updated ontology object
    """
    # Load the TTL file
    content, graph, metadata = load_ttl_file(ttl_path)
    
    # Apply configuration overrides if provided
    if config:
        metadata.update(config)
    
    # Check if ontology already exists
    ontology = Ontology.query.filter_by(domain_id=domain_id).first()
    
    if ontology:
        logger.info(f"Updating existing ontology: {domain_id}")
        
        # Check if content has changed
        if ontology.content == content:
            logger.info("Ontology content unchanged, skipping update")
            return ontology
        
        # Create a version backup before updating
        version_number = get_next_version_number(ontology.id)
        version = OntologyVersion(
            ontology_id=ontology.id,
            version_number=version_number,
            content=ontology.content,  # Save the OLD content
            commit_message=f"Backup before sync from {ttl_path}"
        )
        db.session.add(version)
        
        # Update the ontology
        ontology.content = content
        ontology.updated_at = datetime.now(timezone.utc)
        
        # Update metadata if provided
        if 'name' in metadata:
            ontology.name = metadata['name']
        if 'description' in metadata:
            ontology.description = metadata['description']
        if 'base_uri' in metadata:
            ontology.base_uri = metadata['base_uri']
        
        logger.info(f"Created version {version_number} and updated ontology content")
        
    else:
        logger.info(f"Creating new ontology: {domain_id}")
        
        # Create new ontology
        ontology = Ontology(
            domain_id=domain_id,
            name=metadata.get('name', domain_id),
            description=metadata.get('description', ''),
            content=content,
            is_base=metadata.get('is_base', False),
            is_editable=metadata.get('is_editable', True),
            base_uri=metadata.get('base_uri', '')
        )
        db.session.add(ontology)
        db.session.flush()  # Get the ID
        
        # Create initial version
        version = OntologyVersion(
            ontology_id=ontology.id,
            version_number=1,
            content=content,
            commit_message=f"Initial import from {ttl_path}"
        )
        db.session.add(version)
    
    # Commit all changes
    db.session.commit()
    logger.info(f"Successfully synced ontology: {domain_id}")
    
    return ontology

def verify_sync(domain_id):
    """
    Verify that the sync was successful.
    
    Args:
        domain_id: Domain ID of the ontology to verify
        
    Returns:
        bool: True if verification passed
    """
    ontology = Ontology.query.filter_by(domain_id=domain_id).first()
    
    if not ontology:
        logger.error(f"Ontology not found in database: {domain_id}")
        return False
    
    # Try to parse the stored content
    try:
        graph = Graph()
        graph.parse(data=ontology.content, format='turtle')
        logger.info(f"Verification passed: {len(graph)} triples in database for {domain_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to parse stored ontology content: {e}")
        return False

def main():
    """Main function to run the sync process."""
    parser = argparse.ArgumentParser(description='Sync TTL ontology files to database')
    parser.add_argument('--domain', default='proethica-intermediate',
                       help='Domain ID of the ontology to sync')
    parser.add_argument('--ttl-path', help='Path to the TTL file (overrides default)')
    parser.add_argument('--all', action='store_true',
                       help='Sync all default ontologies')
    parser.add_argument('--verify-only', action='store_true',
                       help='Only verify existing ontologies without syncing')
    
    args = parser.parse_args()
    
    # Create Flask app context with proper configuration
    app = create_app('config')
    
    with app.app_context():
        try:
            if args.verify_only:
                # Verify mode
                domains = list(DEFAULT_ONTOLOGIES.keys()) if args.all else [args.domain]
                all_valid = True
                
                for domain in domains:
                    logger.info(f"\nVerifying {domain}...")
                    if not verify_sync(domain):
                        all_valid = False
                
                if all_valid:
                    logger.info("\n✅ All ontologies verified successfully!")
                else:
                    logger.error("\n❌ Some ontologies failed verification")
                    sys.exit(1)
                    
            elif args.all:
                # Sync all default ontologies
                logger.info("Syncing all default ontologies...")
                
                for domain_id, config in DEFAULT_ONTOLOGIES.items():
                    logger.info(f"\n{'='*60}")
                    logger.info(f"Syncing {domain_id}")
                    logger.info(f"{'='*60}")
                    
                    sync_ontology(domain_id, config['path'], config)
                    
                    if not verify_sync(domain_id):
                        logger.error(f"Verification failed for {domain_id}")
                        sys.exit(1)
                
                logger.info("\n✅ All ontologies synced successfully!")
                
            else:
                # Sync single ontology
                if args.ttl_path:
                    # Custom path provided
                    ttl_path = args.ttl_path
                    config = None
                else:
                    # Use default configuration
                    if args.domain not in DEFAULT_ONTOLOGIES:
                        logger.error(f"Unknown domain: {args.domain}")
                        logger.info(f"Available domains: {', '.join(DEFAULT_ONTOLOGIES.keys())}")
                        sys.exit(1)
                    
                    config = DEFAULT_ONTOLOGIES[args.domain]
                    ttl_path = config['path']
                
                sync_ontology(args.domain, ttl_path, config)
                
                if verify_sync(args.domain):
                    logger.info(f"\n✅ Successfully synced {args.domain}!")
                else:
                    logger.error(f"\n❌ Sync verification failed for {args.domain}")
                    sys.exit(1)
                    
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == '__main__':
    main()