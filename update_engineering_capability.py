"""
Script to update the Engineering Ethics NSPE Extended ontology to properly
subclass EngineeringCapability from the Capability class in ProEthica Intermediate.
"""
import sys
import os
import re
from datetime import datetime
from flask import Flask

# Change to the correct working directory if needed
if os.path.exists('app') and os.path.isdir('app'):
    # We're in the right directory
    pass
elif os.path.exists('../app') and os.path.isdir('../app'):
    # We're in a subdirectory
    os.chdir('..')

# Import the Flask app from the main application
sys.path.insert(0, os.getcwd())
from app import create_app, db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion

def update_engineering_capability(app):
    """
    Update the Engineering Ethics NSPE Extended ontology to properly subclass 
    EngineeringCapability from the Capability class in ProEthica Intermediate.
    """
    print("Updating Engineering Ethics NSPE Extended ontology...")
    
    with app.app_context():
        # Get the engineering ethics ontology
        engineering_ontology = Ontology.query.filter_by(domain_id='engineering-ethics-nspe-extended').first()
        if not engineering_ontology:
            print("Error: Engineering Ethics NSPE Extended ontology not found in the database")
            return False
        
        print(f"Found ontology: {engineering_ontology.name} (ID: {engineering_ontology.id})")
        
        # Read the current content
        content = engineering_ontology.content
        
        # Check if EngineeringCapability is already properly subclassed
        if "rdfs:subClassOf proeth:Capability" in content:
            print("EngineeringCapability is already properly subclassed from proeth:Capability")
            return True
        
        # Find and update the EngineeringCapability class definition
        capability_pattern = r':EngineeringCapability\s+rdf:type\s+owl:Class\s*;([^;]+);'
        capability_match = re.search(capability_pattern, content, re.DOTALL)
        
        if not capability_match:
            print("Error: Could not find EngineeringCapability class definition")
            return False
        
        class_def = capability_match.group(1)
        
        # Check if there's already a rdfs:subClassOf declaration
        if 'rdfs:subClassOf' in class_def:
            # If there is, we need to modify the existing one or add another one
            updated_def = class_def.replace(
                'rdfs:subClassOf', 
                'rdfs:subClassOf proeth:Capability ;\n    rdfs:subClassOf'
            )
        else:
            # If there's no subclass, add it
            updated_def = class_def + '\n    rdfs:subClassOf proeth:Capability'
        
        # Replace the class definition in the original content
        updated_content = content.replace(
            f':EngineeringCapability rdf:type owl:Class ;{class_def};',
            f':EngineeringCapability rdf:type owl:Class ;{updated_def};'
        )
        
        # Make sure the proeth prefix is defined
        if '@prefix proeth: <http://proethica.org/ontology/intermediate#>' not in content:
            # Add the prefix if it's not already there
            prefix_pattern = r'(@prefix[^.]+\.\n)+'
            prefix_match = re.search(prefix_pattern, updated_content)
            if prefix_match:
                prefix_block = prefix_match.group(0)
                new_prefix_block = prefix_block + '@prefix proeth: <http://proethica.org/ontology/intermediate#> .\n'
                updated_content = updated_content.replace(prefix_block, new_prefix_block)
        
        # Update the ontology with the new content
        engineering_ontology.content = updated_content
        
        # Get the current highest version number for the ontology
        latest_version = OntologyVersion.query.filter_by(ontology_id=engineering_ontology.id).order_by(OntologyVersion.version_number.desc()).first()
        new_version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create a new version record
        version = OntologyVersion(
            ontology_id=engineering_ontology.id,
            version_number=new_version_number,
            content=updated_content,
            commit_message="Updated EngineeringCapability to properly subclass from proeth:Capability"
        )
        
        # Save the changes to the database
        try:
            db.session.add(version)
            db.session.commit()
            print(f"Successfully updated ontology and created version {new_version_number}")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error updating ontology: {str(e)}")
            return False

if __name__ == '__main__':
    # Create a Flask application with the development configuration
    app = create_app('development')
    update_engineering_capability(app)
