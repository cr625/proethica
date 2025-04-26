#!/usr/bin/env python
"""
Script to improve the capability hierarchy by adding intermediate capability classes.
This creates a more refined hierarchy with specialized capability types between
EngineeringCapability and specific capabilities.
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

def improve_capability_hierarchy(ontology_id=1):
    """
    Improve the capability hierarchy by adding intermediate capability classes.
    
    Args:
        ontology_id (int): The ID of the ontology to modify.
    """
    print(f"Improving capability hierarchy for ontology ID {ontology_id}...")
    
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
        
        # Base namespace
        base_namespace = "http://proethica.org/ontology/engineering-ethics#"
        
        # EngineeringCapability URI
        engineering_capability = URIRef(f"{base_namespace}EngineeringCapability")
        
        # New intermediate capability classes with descriptions
        new_intermediate_classes = [
            {
                "id": "DesignCapability",
                "label": "Design Capability",
                "description": "A capability related to designing engineering systems or components",
                "subclasses": [
                    "StructuralDesignCapability",
                    "ElectricalSystemsDesignCapability",
                    "MechanicalSystemsDesignCapability"
                ]
            },
            {
                "id": "ManagementCapability",
                "label": "Management Capability",
                "description": "A capability related to managing engineering projects or processes",
                "subclasses": [
                    "ProjectManagementCapability"
                ]
            },
            {
                "id": "AssessmentCapability",
                "label": "Assessment Capability",
                "description": "A capability related to assessing or analyzing engineering systems",
                "subclasses": [
                    "SafetyAssessmentCapability",
                    "StructuralAnalysisCapability"
                ]
            },
            {
                "id": "ReportingCapability",
                "label": "Reporting Capability",
                "description": "A capability related to preparing technical reports or documentation",
                "subclasses": [
                    "TechnicalReportingCapability"
                ]
            },
            {
                "id": "ComplianceCapability",
                "label": "Compliance Capability",
                "description": "A capability related to ensuring compliance with regulations or standards",
                "subclasses": [
                    "RegulatoryComplianceCapability"
                ]
            },
            {
                "id": "ConsultationCapability",
                "label": "Consultation Capability",
                "description": "A capability related to providing expert consultation or advice",
                "subclasses": [
                    "EngineeringConsultationCapability"
                ]
            }
        ]
        
        # First, add the intermediate capability classes
        for cls in new_intermediate_classes:
            uri = URIRef(f"{base_namespace}{cls['id']}")
            
            # Check if class already exists
            if (uri, None, None) in g:
                print(f"Class {cls['id']} already exists, skipping creation")
                continue
                
            print(f"Adding intermediate capability class: {cls['id']}")
            
            # Add basic class definitions
            g.add((uri, RDF.type, URIRef("http://www.w3.org/2002/07/owl#Class")))
            g.add((uri, RDFS.label, Literal(cls['label'])))
            g.add((uri, RDFS.comment, Literal(cls['description'])))
            
            # Make it a subclass of EngineeringCapability
            g.add((uri, RDFS.subClassOf, engineering_capability))
        
        # Now update the subclasses to point to their new parent
        for cls in new_intermediate_classes:
            intermediate_uri = URIRef(f"{base_namespace}{cls['id']}")
            
            for subclass_id in cls['subclasses']:
                subclass_uri = URIRef(f"{base_namespace}{subclass_id}")
                
                # Check if subclass exists
                if (subclass_uri, None, None) not in g:
                    print(f"Subclass {subclass_id} not found, skipping")
                    continue
                    
                # Get current parent
                current_parents = list(g.objects(subclass_uri, RDFS.subClassOf))
                updated = False
                
                for current_parent in current_parents:
                    if current_parent == engineering_capability:
                        print(f"Updating parent for {subclass_id}: {engineering_capability} -> {intermediate_uri}")
                        g.remove((subclass_uri, RDFS.subClassOf, engineering_capability))
                        g.add((subclass_uri, RDFS.subClassOf, intermediate_uri))
                        updated = True
                
                if not updated:
                    print(f"Did not update {subclass_id}, no matching parent found")
        
        # Create new ontology version
        new_content = g.serialize(format="turtle")
        
        # Create a new version
        next_version = get_next_version_number(ontology_id)
        version = OntologyVersion(
            ontology_id=ontology_id,
            version_number=next_version,
            content=new_content,
            commit_message="Improved capability hierarchy with intermediate classes"
        )
        db.session.add(version)
        
        # Update the ontology content
        ontology.content = new_content
        db.session.commit()
        
        print("Successfully improved capability hierarchy")

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
            improve_capability_hierarchy(ontology_id)
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print("Usage: python improve_capability_hierarchy.py [ontology_id]")
            sys.exit(1)
    else:
        # Default to ontology ID 1
        improve_capability_hierarchy()
