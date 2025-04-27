"""
Script to verify ontology consistency between ProEthica Intermediate and Engineering Ethics NSPE Extended.
Specifically checks if EngineeringCapability properly subclasses from the new Capability class in the intermediate ontology.
"""
import sys
import os
from datetime import datetime
from flask import Flask
import re

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
from app.models.ontology_import import OntologyImport

def verify_ontology_consistency(app):
    """
    Verify that the Engineering Ethics NSPE Extended ontology properly connects to 
    the Capability class in the ProEthica Intermediate ontology.
    """
    print("Verifying ontology consistency...")
    
    with app.app_context():
        # Get both ontologies
        intermediate_ontology = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
        engineering_ontology = Ontology.query.filter_by(domain_id='engineering-ethics-nspe-extended').first()
        
        if not intermediate_ontology or not engineering_ontology:
            print("Error: Could not find one or both ontologies")
            return False
        
        print(f"Found ontologies: {intermediate_ontology.name} and {engineering_ontology.name}")
        
        # Verify Capability exists in intermediate ontology
        if ":Capability rdf:type owl:Class" not in intermediate_ontology.content:
            print("Error: Capability class not found in intermediate ontology")
            return False
        
        print("✓ Capability class exists in intermediate ontology")
        
        # Verify Engineering Ethics imports ProEthica Intermediate
        imports = OntologyImport.query.filter_by(importing_ontology_id=engineering_ontology.id).all()
        imported_ids = [imp.imported_ontology_id for imp in imports]
        if intermediate_ontology.id not in imported_ids:
            print("Error: Engineering Ethics ontology does not import ProEthica Intermediate")
            return False
        
        print("✓ Engineering Ethics ontology correctly imports ProEthica Intermediate")
        
        # Check if EngineeringCapability exists in engineering ontology
        if ":EngineeringCapability rdf:type owl:Class" not in engineering_ontology.content:
            print("Error: EngineeringCapability class not found in engineering ontology")
            return False
        
        print("✓ EngineeringCapability class exists in engineering ontology")
        
        # Parse the ontology to see if EngineeringCapability references the intermediate ontology
        eng_content = engineering_ontology.content
        
        # Search for the import statement for the intermediate ontology
        import_match = re.search(r'owl:imports <(http://proethica.org/ontology/intermediate)>', eng_content)
        if not import_match:
            print("Error: Could not find explicit import of intermediate ontology in TTL file")
            return False
        
        print("✓ Found explicit owl:imports statement for intermediate ontology")
        
        # Optional: look for specific class references
        capability_reference = "proeth:Capability" in eng_content
        if not capability_reference:
            print("Warning: No explicit reference to proeth:Capability found (might be using inheritance only)")
        else:
            print("✓ Found explicit references to proeth:Capability")
        
        # Check if EngineeringCapability is subclassed correctly
        eng_capability_match = re.search(r':EngineeringCapability\s+rdf:type\s+owl:Class\s*;([^;]+);', eng_content, re.DOTALL)
        if eng_capability_match:
            class_def = eng_capability_match.group(1)
            has_subclass = re.search(r'rdfs:subClassOf\s+(?:proeth:Capability|:Capability)', class_def)
            if not has_subclass:
                print("Warning: EngineeringCapability may not be properly subclassed from Capability")
                print("  Consider updating the EngineeringCapability in engineering-ethics-nspe-extended to subclass from proeth:Capability")
                return True
            else:
                print("✓ EngineeringCapability is properly subclassed from Capability")
        else:
            print("Warning: Could not parse EngineeringCapability class definition")
        
        return True

if __name__ == '__main__':
    # Create a Flask application with the development configuration
    app = create_app('development')
    verify_ontology_consistency(app)
