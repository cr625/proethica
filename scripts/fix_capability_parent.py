#!/usr/bin/env python
"""
Script to fix the parent class of capabilities in the ontology.
Currently fixes Technical Reporting Capability to have EngineeringCapability
as parent instead of EngineeringReport
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, URIRef, Namespace, Literal
from rdflib.namespace import RDF, RDFS

def fix_capability_parent(ontology_id=1):
    """
    Fix the parent class of Technical Reporting Capability in the specified ontology.
    
    Args:
        ontology_id (int): The ID of the ontology to fix.
    """
    print(f"Fixing capability parent classes for ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        from app import db
        
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Error: Ontology with ID {ontology_id} not found")
            return
            
        print(f"Working on ontology: {ontology.name} ({ontology.domain_id})")
        
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Technical Reporting Capability URI
        tech_reporting_capability = URIRef("http://proethica.org/ontology/engineering-ethics#TechnicalReportingCapability")
        
        # Current parent (incorrect)
        old_parent = URIRef("http://proethica.org/ontology/engineering-ethics#EngineeringReport")
        
        # New parent (correct)
        new_parent = URIRef("http://proethica.org/ontology/engineering-ethics#EngineeringCapability")
        
        # Check if entity exists
        if (tech_reporting_capability, None, None) not in g:
            print(f"Error: Technical Reporting Capability not found in ontology")
            return
            
        # Check current parent class
        current_parents = list(g.objects(tech_reporting_capability, RDFS.subClassOf))
        if not current_parents:
            print(f"Error: Technical Reporting Capability has no parent class")
            return
            
        print(f"Current parents: {current_parents}")
        
        # Fix the parent class
        changed = False
        for current_parent in current_parents:
            if current_parent == old_parent:
                print(f"Replacing parent: {old_parent} -> {new_parent}")
                g.remove((tech_reporting_capability, RDFS.subClassOf, old_parent))
                g.add((tech_reporting_capability, RDFS.subClassOf, new_parent))
                changed = True
        
        if not changed:
            print("No changes needed - correct parent already set")
            return
            
        # Create new ontology version
        new_content = g.serialize(format="turtle")
        
        # Create a new version
        next_version = get_next_version_number(ontology_id)
        version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=next_version,
            content=new_content,
            commit_message="Fixed Technical Reporting Capability parent class"
        )
        db.session.add(version)
        
        # Update the ontology content
        ontology.content = new_content
        db.session.commit()
        
        print("Successfully fixed Technical Reporting Capability parent class")

def get_next_version_number(ontology_id):
    """Get the next version number for an ontology"""
    # Get the latest version
    from app import db
    from app.models.ontology_version import OntologyVersion
    
    latest_version = OntologyVersion.query.filter_by(
        ontology_id=ontology_id
    ).order_by(
        OntologyVersion.version_number.desc()
    ).first()
    
    if latest_version:
        return latest_version.version_number + 1
    else:
        return 1

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
            fix_capability_parent(ontology_id)
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print("Usage: python fix_capability_parent.py [ontology_id]")
            sys.exit(1)
    else:
        # Default to ontology ID 1
        fix_capability_parent()
