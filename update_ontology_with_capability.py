"""
Script to update the ProEthica Intermediate ontology with a new Capability class
"""
import sys
import os
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

def update_proethica_intermediate_ontology(app):
    """
    Add the Capability class to the ProEthica Intermediate ontology in the database
    """
    print("Updating ProEthica Intermediate ontology with new Capability class...")
    
    with app.app_context():
        # Find the ProEthica Intermediate ontology by domain ID
        ontology = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
        if not ontology:
            print("Error: ProEthica Intermediate ontology not found in the database")
            return False
        
        print(f"Found ontology: {ontology.name} (ID: {ontology.id})")
        
        # Read the current content
        content = ontology.content
        
        # Check if Capability class already exists to avoid duplicate
        if ":Capability rdf:type owl:Class" in content:
            print("Capability class already exists in the ontology")
            return True
        
        # Add Capability class definition after the ProfessionalAction class
        new_content = content.replace(
            """:ProfessionalAction rdf:type owl:Class ;
    rdfs:subClassOf :Action ;
    rdfs:label "Professional Action"@en ;
    rdfs:comment "An action performed in a professional capacity"@en .""", 
            """:ProfessionalAction rdf:type owl:Class ;
    rdfs:subClassOf :Action ;
    rdfs:label "Professional Action"@en ;
    rdfs:comment "An action performed in a professional capacity"@en .

# Capability - Skills, abilities, and competencies
:Capability rdf:type owl:Class ;
    rdf:type :EntityType ;
    rdf:type :CapabilityType ;
    rdfs:subClassOf bfo:BFO_0000016 ; # disposition from BFO
    rdfs:label "Capability"@en ;
    rdfs:comment "A skill, ability, or competency that can be realized in professional contexts"@en .

:ProfessionalCapability rdf:type owl:Class ;
    rdfs:subClassOf :Capability ;
    rdfs:label "Professional Capability"@en ;
    rdfs:comment "A capability specifically relevant to professional roles"@en .

:TechnicalCapability rdf:type owl:Class ;
    rdfs:subClassOf :Capability ;
    rdfs:label "Technical Capability"@en ;
    rdfs:comment "A capability related to technical skills or knowledge"@en .""")
        
        # Add CapabilityType to the entity types section
        new_content = new_content.replace(
            """:ActionType rdf:type owl:Class ;
    rdfs:label "Action Type"@en ;
    rdfs:comment "Meta-class for action types recognized by the ProEthica system"@en .""",
            """:ActionType rdf:type owl:Class ;
    rdfs:label "Action Type"@en ;
    rdfs:comment "Meta-class for action types recognized by the ProEthica system"@en .

# Adding new capability type
:CapabilityType rdf:type owl:Class ;
    rdfs:label "Capability Type"@en ;
    rdfs:comment "Meta-class for capability types recognized by the ProEthica system"@en .""")
        
        # Add capability properties after the action properties section
        new_content = new_content.replace(
            """:actionAgent rdf:type owl:ObjectProperty ;
    rdfs:domain :Action ;
    rdfs:range :Agent ;
    rdfs:label "action agent"@en ;
    rdfs:comment "Indicates who performs an action"@en .""",
            """:actionAgent rdf:type owl:ObjectProperty ;
    rdfs:domain :Action ;
    rdfs:range :Agent ;
    rdfs:label "action agent"@en ;
    rdfs:comment "Indicates who performs an action"@en .

# Properties for Capabilities
:capabilityLevel rdf:type owl:DatatypeProperty ;
    rdfs:domain :Capability ;
    rdfs:range xsd:integer ;
    rdfs:label "capability level"@en ;
    rdfs:comment "Indicates the level or proficiency of a capability (1-10)"@en .

:requiresTraining rdf:type owl:DatatypeProperty ;
    rdfs:domain :Capability ;
    rdfs:range xsd:boolean ;
    rdfs:label "requires training"@en ;
    rdfs:comment "Indicates whether a capability requires formal training"@en .

:enablesAction rdf:type owl:ObjectProperty ;
    rdfs:domain :Capability ;
    rdfs:range :Action ;
    rdfs:label "enables action"@en ;
    rdfs:comment "Relates a capability to actions it enables"@en .""")
        
        # Add a relationship property for capabilities
        new_content = new_content.replace(
            """:requiresDecision rdf:type owl:ObjectProperty ;
    rdfs:domain :EthicalDilemma ;
    rdfs:range :Decision ;
    rdfs:label "requires decision"@en ;
    rdfs:comment "Relates an ethical dilemma to the decision it requires"@en .""",
            """:requiresDecision rdf:type owl:ObjectProperty ;
    rdfs:domain :EthicalDilemma ;
    rdfs:range :Decision ;
    rdfs:label "requires decision"@en ;
    rdfs:comment "Relates an ethical dilemma to the decision it requires"@en .

:requiresCapability rdf:type owl:ObjectProperty ;
    rdfs:range :Capability ;
    rdfs:label "requires capability"@en ;
    rdfs:comment "Relates an entity to capabilities required"@en .""")
        
        # Update hasCapability to properly reference the Capability class
        new_content = new_content.replace(
            """:hasCapability rdf:type owl:ObjectProperty ;
    rdfs:domain :Role ;
    rdfs:label "has capability"@en ;
    rdfs:comment "Relates a role to capabilities it possesses"@en .""",
            """:hasCapability rdf:type owl:ObjectProperty ;
    rdfs:domain :Role ;
    rdfs:range :Capability ;
    rdfs:label "has capability"@en ;
    rdfs:comment "Relates a role to capabilities it possesses"@en .""")
        
        # Update the ontology with the new content
        ontology.content = new_content
        
        # Get the current highest version number for the ontology
        latest_version = OntologyVersion.query.filter_by(ontology_id=ontology.id).order_by(OntologyVersion.version_number.desc()).first()
        new_version_number = (latest_version.version_number + 1) if latest_version else 1
        
        # Create a new version record
        version = OntologyVersion(
            ontology_id=ontology.id,
            version_number=new_version_number,
            content=new_content,
            commit_message="Added Capability class and related properties"
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
    update_proethica_intermediate_ontology(app)
