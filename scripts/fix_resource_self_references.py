"""
Script to fix self-referencing resources in the ontology.
This will update resources that reference themselves as their own parent
to correctly point to ResourceType or appropriate parent class.
"""

import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, Namespace, URIRef, RDF, RDFS
import re

def fix_resource_self_references(ontology_id=1):
    """
    Fix self-referencing resources in the ontology.
    
    Args:
        ontology_id (int): ID of the ontology to fix
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Fixing self-referencing resources in ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology ID {ontology_id} not found.")
            return False
        
        # Parse the ontology
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Define namespaces
        namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "nspe": Namespace("http://proethica.org/ontology/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/")
        }
        
        # Helper function
        def label_or_id(s):
            label = next(g.objects(s, RDFS.label), None)
            return str(label) if label else str(s).split('#')[-1]
        
        # Get resource type URI
        resource_type_uri = namespaces["intermediate"].ResourceType
        
        # Find all self-referencing resources
        self_refs = []
        for s, p, o in g.triples((None, RDFS.subClassOf, None)):
            if s == o:
                self_refs.append(s)
                print(f"Found self-reference: {label_or_id(s)} → {label_or_id(o)}")
        
        if not self_refs:
            print("No self-referencing resources found.")
            return True
        
        print(f"Found {len(self_refs)} self-referencing resources.")
        
        # Update parent classes
        updated_count = 0
        for resource in self_refs:
            label = label_or_id(resource)
            
            # Remove self-reference
            g.remove((resource, RDFS.subClassOf, resource))
            
            # Assign proper parent based on resource type
            if "EngineeringDocument" in str(resource):
                # EngineeringDocument should be child of ResourceType
                g.add((resource, RDFS.subClassOf, resource_type_uri))
                print(f"  - Updated {label} parent to ResourceType")
            
            elif "EngineeringDrawing" in str(resource):
                # EngineeringDrawing should be child of EngineeringDocument
                eng_doc_uri = namespaces["engineering-ethics"].EngineeringDocument
                g.add((resource, RDFS.subClassOf, eng_doc_uri))
                print(f"  - Updated {label} parent to EngineeringDocument")
            
            elif "EngineeringSpecification" in str(resource):
                # EngineeringSpecification should be child of EngineeringDocument
                eng_doc_uri = namespaces["engineering-ethics"].EngineeringDocument
                g.add((resource, RDFS.subClassOf, eng_doc_uri))
                print(f"  - Updated {label} parent to EngineeringDocument")
            
            elif "EngineeringReport" in str(resource):
                # EngineeringReport should be child of EngineeringDocument
                eng_doc_uri = namespaces["engineering-ethics"].EngineeringDocument
                g.add((resource, RDFS.subClassOf, eng_doc_uri))
                print(f"  - Updated {label} parent to EngineeringDocument")
            
            elif "BuildingCode" in str(resource):
                # BuildingCode should be child of ResourceType
                g.add((resource, RDFS.subClassOf, resource_type_uri))
                print(f"  - Updated {label} parent to ResourceType")
            
            else:
                # Default to ResourceType
                g.add((resource, RDFS.subClassOf, resource_type_uri))
                print(f"  - Updated {label} parent to ResourceType")
                
            updated_count += 1
        
        # Save the updated ontology
        print("\nSaving updated ontology...")
        
        # Create new version
        try:
            # Get next version number
            latest_version = OntologyVersion.query.filter_by(
                ontology_id=ontology.id
            ).order_by(
                OntologyVersion.version_number.desc()
            ).first()
            
            next_version = 1
            if latest_version:
                next_version = latest_version.version_number + 1
                
            # Serialize updated graph
            new_content = g.serialize(format="turtle")
            
            # Create version entry
            version = OntologyVersion(
                ontology_id=ontology.id,
                version_number=next_version,
                content=new_content,
                commit_message="Fixed self-referencing resources"
            )
            
            # Update ontology content
            ontology.content = new_content
            
            # Save to database
            from app import db
            db.session.add(version)
            db.session.commit()
            
            print(f"Successfully updated ontology (version {next_version})")
            print(f"Fixed {updated_count} self-referencing resources")
            
            return True
            
        except Exception as e:
            from app import db
            db.session.rollback()
            print(f"Error saving ontology: {e}")
            return False

if __name__ == "__main__":
    # Default ontology ID is 1, but can be passed as command-line argument
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            sys.exit(1)
    
    success = fix_resource_self_references(ontology_id)
    sys.exit(0 if success else 1)
