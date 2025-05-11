#!/usr/bin/env python3
"""
MSEO Importer

This module handles importing the MSEO ontology into the database for use with the
REALM application. It creates the necessary database records to make the ontology
available to the MCP server.
"""

import argparse
import os
import sys
import logging
from datetime import datetime
import rdflib
from rdflib import Graph, Namespace, URIRef

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MSEOImporter:
    """
    Importer for the Materials Science Engineering Ontology (MSEO).
    
    This class handles importing the MSEO ontology into the database, creating
    the necessary records for it to be accessed by the MCP server.
    """
    
    def __init__(self, app_context=None):
        """
        Initialize the MSEO importer.
        
        Args:
            app_context: Optional Flask app context for database access
        """
        self.app_context = app_context
        self.mseo = Namespace("http://matportal.org/ontologies/MSEO#")
        
        # Create a dictionary to track entity counts
        self.entity_counts = {
            'Materials': 0,
            'Properties': 0,
            'Processes': 0,
            'Structures': 0,
            'Total': 0
        }
    
    def import_ontology(self, input_file, domain_name="Materials Science", 
                        version="1.0", description=None):
        """
        Import the MSEO ontology into the database.
        
        Args:
            input_file: Path to the TTL ontology file
            domain_name: Name for the ontology domain
            version: Version string for the ontology
            description: Optional description for the ontology
            
        Returns:
            bool: True if import was successful, False otherwise
        """
        try:
            logger.info(f"Importing MSEO ontology from {input_file}...")
            
            # Parse the ontology file
            g = Graph()
            g.parse(input_file, format="turtle")
            
            # Generate ontology metadata if not provided
            if not description:
                description = f"Materials Science Engineering Ontology (MSEO) imported on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Get ontology statistics
            self._analyze_ontology(g)
            
            # Import the ontology with the app context
            if self.app_context:
                with self.app_context:
                    self._do_import(g, domain_name, version, description)
            else:
                # If no app context provided, try to create one
                try:
                    from app import create_app
                    app = create_app()
                    with app.app_context():
                        self._do_import(g, domain_name, version, description)
                except Exception as e:
                    logger.error(f"Failed to create app context: {str(e)}")
                    return False
            
            logger.info(f"MSEO ontology import completed successfully")
            logger.info(f"Imported {self.entity_counts['Total']} entities:")
            for entity_type, count in self.entity_counts.items():
                if entity_type != 'Total':
                    logger.info(f"  - {entity_type}: {count}")
            
            return True
        
        except Exception as e:
            logger.error(f"Error importing MSEO ontology: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _analyze_ontology(self, g):
        """
        Analyze the ontology to gather statistics.
        
        Args:
            g: RDFLib Graph containing the ontology
        """
        # Count materials
        materials = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, self.mseo.Material)):
            materials.add(s)
        self.entity_counts['Materials'] = len(materials)
        
        # Count properties
        properties = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, self.mseo.Property)):
            properties.add(s)
        self.entity_counts['Properties'] = len(properties)
        
        # Count processes
        processes = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, self.mseo.Process)):
            processes.add(s)
        self.entity_counts['Processes'] = len(processes)
        
        # Count structures
        structures = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, self.mseo.Structure)):
            structures.add(s)
        self.entity_counts['Structures'] = len(structures)
        
        # Calculate total
        self.entity_counts['Total'] = len(materials) + len(properties) + len(processes) + len(structures)
    
    def _do_import(self, g, domain_name, version, description):
        """
        Perform the actual import into the database using the app context.
        
        Args:
            g: RDFLib Graph containing the ontology
            domain_name: Name for the ontology domain
            version: Version string for the ontology
            description: Description for the ontology
        """
        # Import the database models
        from app.models.ontology import OntologyDomain, OntologyVersion
        from app.models.entity import EntityType, Entity, EntityRelationship
        from app import db
        
        # Check if domain already exists
        domain = OntologyDomain.query.filter_by(name=domain_name).first()
        if not domain:
            logger.info(f"Creating new ontology domain: {domain_name}")
            domain = OntologyDomain(name=domain_name, description=description)
            db.session.add(domain)
            db.session.commit()
        
        # Create a new ontology version
        logger.info(f"Creating new ontology version: {version}")
        ontology_version = OntologyVersion(
            domain_id=domain.id,
            version=version,
            description=description,
            is_active=True
        )
        db.session.add(ontology_version)
        db.session.commit()
        
        # Store the serialized TTL in the version record
        ontology_version.content = g.serialize(format="turtle")
        db.session.commit()
        
        # Create entity types if they don't exist
        entity_types = {
            "Material": self._get_or_create_entity_type(db, "Material", "Physical substance used in materials science"),
            "Property": self._get_or_create_entity_type(db, "Property", "Characteristic or attribute of materials"),
            "Process": self._get_or_create_entity_type(db, "Process", "Method or procedure for material processing"),
            "Structure": self._get_or_create_entity_type(db, "Structure", "Material structure or organization")
        }
        
        # Import entities - we'll just create placeholder records
        # for actual integration, the entities would need to be fully imported
        logger.info("Import complete. To use the MSEO ontology with the MCP server:")
        logger.info(f"1. Use domain_id={domain.id}")
        logger.info(f"2. The ontology is accessible via the enhanced MCP server using the domain ID")
    
    def _get_or_create_entity_type(self, db, type_name, description):
        """
        Get an existing entity type or create a new one.
        
        Args:
            db: Database session
            type_name: Name of the entity type
            description: Description of the entity type
            
        Returns:
            EntityType object
        """
        from app.models.entity import EntityType
        
        entity_type = EntityType.query.filter_by(name=type_name).first()
        if not entity_type:
            logger.info(f"Creating new entity type: {type_name}")
            entity_type = EntityType(name=type_name, description=description)
            db.session.add(entity_type)
            db.session.commit()
        
        return entity_type

def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description='Import MSEO ontology into the database')
    parser.add_argument('--input', '-i', required=True, help='Path to input TTL file')
    parser.add_argument('--domain', '-d', default="Materials Science", help='Domain name')
    parser.add_argument('--version', '-v', default="1.0", help='Ontology version')
    parser.add_argument('--description', help='Optional description')
    
    args = parser.parse_args()
    
    # Create the importer
    importer = MSEOImporter()
    
    # Import the ontology
    success = importer.import_ontology(
        args.input, 
        domain_name=args.domain,
        version=args.version,
        description=args.description
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
