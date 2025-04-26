"""
Script to fix the condition hierarchy in the ontology.
This will:
1. Create base classes for condition categories (EthicalDilemma, Principle, etc.)
2. Update parent classes for all conditions to have appropriate parents
"""

import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, Namespace, URIRef, RDF, RDFS, OWL, Literal
import re

def fix_condition_hierarchy(ontology_id=1):
    """
    Fix the condition hierarchy in the ontology.
    
    Args:
        ontology_id (int): ID of the ontology to fix
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Fixing condition hierarchy in ontology ID {ontology_id}...")
    
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
            "nspe": Namespace("http://proethica.org/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/")
        }
        
        # Helper function
        def label_or_id(s):
            label = next(g.objects(s, RDFS.label), None)
            return str(label) if label else str(s).split('#')[-1]
            
        # Get or create our base classes
        base_classes = {}
        
        # 1. First, ensure ConditionType exists and is properly linked to BFO
        condition_type_uri = namespaces["intermediate"].ConditionType
        if (condition_type_uri, None, None) not in g:
            # Create ConditionType
            print("Creating ConditionType class")
            g.add((condition_type_uri, RDF.type, OWL.Class))
            g.add((condition_type_uri, RDFS.label, Literal("Condition Type")))
            g.add((condition_type_uri, RDFS.comment, Literal("Base class for all condition types in the ontology")))
            # Link to BFO - specifically to 'continuant' as appropriate
            g.add((condition_type_uri, RDFS.subClassOf, namespaces["bfo"].BFO_0000002))  # continuant
        
        base_classes["ConditionType"] = condition_type_uri
        print(f"- ConditionType: {condition_type_uri}")
            
        # 2. Create or reuse EthicalDilemma
        ethical_dilemma_uri = namespaces["engineering-ethics"].EthicalDilemma
        if (ethical_dilemma_uri, None, None) not in g:
            # Create EthicalDilemma
            print("Creating EthicalDilemma class")
            g.add((ethical_dilemma_uri, RDF.type, OWL.Class))
            g.add((ethical_dilemma_uri, RDFS.label, Literal("Ethical Dilemma")))
            g.add((ethical_dilemma_uri, RDFS.comment, Literal("A situation involving a difficult ethical choice between competing considerations")))
            g.add((ethical_dilemma_uri, RDFS.subClassOf, condition_type_uri))
        
        base_classes["EthicalDilemma"] = ethical_dilemma_uri
        print(f"- EthicalDilemma: {ethical_dilemma_uri}")
            
        # 3. Create or reuse Principle
        principle_uri = namespaces["engineering-ethics"].Principle
        if (principle_uri, None, None) not in g:
            # Create Principle
            print("Creating Principle class")
            g.add((principle_uri, RDF.type, OWL.Class))
            g.add((principle_uri, RDFS.label, Literal("Principle")))
            g.add((principle_uri, RDFS.comment, Literal("A fundamental ethical principle that guides decision-making")))
            g.add((principle_uri, RDFS.subClassOf, condition_type_uri))
        
        base_classes["Principle"] = principle_uri
        print(f"- Principle: {principle_uri}")
            
        # 4. Create or reuse SafetyPrinciple
        safety_principle_uri = namespaces["engineering-ethics"].SafetyPrinciple
        if (safety_principle_uri, None, None) not in g:
            # Create SafetyPrinciple
            print("Creating SafetyPrinciple class")
            g.add((safety_principle_uri, RDF.type, OWL.Class))
            g.add((safety_principle_uri, RDFS.label, Literal("Safety Principle")))
            g.add((safety_principle_uri, RDFS.comment, Literal("A principle focused on ensuring safety in engineering practice")))
            g.add((safety_principle_uri, RDFS.subClassOf, principle_uri))
        
        base_classes["SafetyPrinciple"] = safety_principle_uri
        print(f"- SafetyPrinciple: {safety_principle_uri}")
            
        # 5. Create or reuse ConflictOfInterest
        conflict_of_interest_uri = namespaces["engineering-ethics"].ConflictOfInterestCondition
        if (conflict_of_interest_uri, None, None) not in g:
            # Create ConflictOfInterest
            print("Creating ConflictOfInterestCondition class")
            g.add((conflict_of_interest_uri, RDF.type, OWL.Class))
            g.add((conflict_of_interest_uri, RDFS.label, Literal("Conflict of Interest Condition")))
            g.add((conflict_of_interest_uri, RDFS.comment, Literal("A situation where personal interests conflict with professional responsibilities")))
            g.add((conflict_of_interest_uri, RDFS.subClassOf, condition_type_uri))
        
        base_classes["ConflictOfInterest"] = conflict_of_interest_uri
        print(f"- ConflictOfInterestCondition: {conflict_of_interest_uri}")
        
        # Now let's find all instances of conditions and organize them
        condition_subjects = set()
        for ns_name, ns in namespaces.items():
            condition_class = ns.ConditionType
            for s in g.subjects(RDF.type, condition_class):
                condition_subjects.add(s)
        
        # Also look for instances that contain "Dilemma", "Principle", etc.
        keyword_conditions = set()
        keywords = ["Dilemma", "Principle", "Condition"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_conditions.add(s)
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_conditions.add(s)
        
        # Merge the sets
        all_conditions = condition_subjects.union(keyword_conditions)
        
        print(f"\nUpdating {len(all_conditions)} conditions with appropriate parents...")
        
        # Update parent classes for all conditions
        updated_count = 0
        dilemma_count = 0
        principle_count = 0
        safety_count = 0
        conflict_count = 0
        general_count = 0
        
        for condition in all_conditions:
            label = label_or_id(condition)
            uri = str(condition)
            
            old_parents = list(g.objects(condition, RDFS.subClassOf))
            
            # Skip if parent is already one of our base classes
            if any(parent in base_classes.values() for parent in old_parents):
                continue
            
            # Categorize and assign parent
            new_parent = None
            
            if "Dilemma" in label or "Dilemma" in uri:
                new_parent = base_classes["EthicalDilemma"]
                dilemma_count += 1
            elif ("Safety" in label or "Safety" in uri) and ("Principle" in label or "Principle" in uri):
                new_parent = base_classes["SafetyPrinciple"]
                safety_count += 1
            elif "Principle" in label or "Principle" in uri:
                new_parent = base_classes["Principle"]
                principle_count += 1
            elif "Conflict" in label or "Conflict" in uri or "conflict" in label:
                new_parent = base_classes["ConflictOfInterest"]
                conflict_count += 1
            else:
                new_parent = base_classes["ConditionType"]
                general_count += 1
            
            if new_parent:
                # Remove existing parent classes
                for old_parent in old_parents:
                    g.remove((condition, RDFS.subClassOf, old_parent))
                    
                # Add new parent
                g.add((condition, RDFS.subClassOf, new_parent))
                print(f"  - Set parent of {label} to {label_or_id(new_parent)}")
                
                # Ensure proper typing as well
                if (condition, RDF.type, None) not in g:
                    g.add((condition, RDF.type, OWL.Class))
                
                updated_count += 1
            
        # Specific fixes for conditions mentioned in the task
        competence_vs_client_uri = None
        public_safety_uri = None
        
        for condition in all_conditions:
            label = label_or_id(condition)
            if "Competence vs Client Wishes" in label:
                competence_vs_client_uri = condition
            elif "Public Safety" in label and "Principle" in label:
                public_safety_uri = condition
        
        if competence_vs_client_uri:
            parents = list(g.objects(competence_vs_client_uri, RDFS.subClassOf))
            if ethical_dilemma_uri not in parents:
                # Remove old parents
                for p in parents:
                    g.remove((competence_vs_client_uri, RDFS.subClassOf, p))
                # Set EthicalDilemma as parent
                g.add((competence_vs_client_uri, RDFS.subClassOf, ethical_dilemma_uri))
                print(f"  - Fixed parent of Competence vs Client Wishes Dilemma to EthicalDilemma")
        
        if public_safety_uri:
            parents = list(g.objects(public_safety_uri, RDFS.subClassOf))
            if safety_principle_uri not in parents:
                # Remove old parents
                for p in parents:
                    g.remove((public_safety_uri, RDFS.subClassOf, p))
                # Set SafetyPrinciple as parent
                g.add((public_safety_uri, RDFS.subClassOf, safety_principle_uri))
                print(f"  - Fixed parent of Public Safety Principle to SafetyPrinciple")
        
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
                commit_message="Fixed condition hierarchy with proper parent classes"
            )
            
            # Update ontology content
            ontology.content = new_content
            
            # Save to database
            from app import db
            db.session.add(version)
            db.session.commit()
            
            print(f"Successfully updated ontology (version {next_version})")
            print(f"Updated {updated_count} condition parents:")
            print(f"  - {dilemma_count} dilemmas")
            print(f"  - {principle_count} principles")
            print(f"  - {safety_count} safety principles")
            print(f"  - {conflict_count} conflict conditions")
            print(f"  - {general_count} general conditions")
            
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
    
    success = fix_condition_hierarchy(ontology_id)
    sys.exit(0 if success else 1)
