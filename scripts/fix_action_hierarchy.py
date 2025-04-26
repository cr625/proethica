"""
Script to fix the action hierarchy in the ontology system.

This script will:
1. Create proper action type base classes
2. Fix actions with incorrect parent classes
3. Ensure a clean, consistent hierarchy
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from rdflib import Graph, Namespace, URIRef, RDF, RDFS, Literal
import re

def fix_action_hierarchy(ontology_id=1):
    """
    Fix the action hierarchy in the ontology.
    
    Args:
        ontology_id (int): Ontology ID
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Fixing action hierarchy in ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology ID {ontology_id} not found")
            return False
        
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Define namespaces
        namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "nspe": Namespace("http://proethica.org/nspe/"),
            "bfo": Namespace("http://purl.obolibrary.org/obo/"),
            "owl": Namespace("http://www.w3.org/2002/07/owl#")
        }
        eng_ethics = namespaces["engineering-ethics"]
        proeth = namespaces["intermediate"]
        
        # Helper function
        def label_or_id(s):
            label = next(g.objects(s, RDFS.label), None)
            return str(label) if label else str(s).split('#')[-1]
        
        # 1. Create/verify base action classes
        print("\n1. Creating or verifying base action classes...")
        
        # Ensure we have ActionType
        action_type_uri = proeth.ActionType
        action_type_exists = (action_type_uri, None, None) in g
        if not action_type_exists:
            print(f"  - Creating ActionType base class")
            g.add((action_type_uri, RDF.type, namespaces["owl"].Class))
            g.add((action_type_uri, RDFS.label, Literal("Action Type")))
            g.add((action_type_uri, RDFS.comment, Literal("Base class for all action types in the ontology")))
            g.add((action_type_uri, RDFS.subClassOf, URIRef("http://purl.obolibrary.org/obo/BFO_0000002")))
        
        # Ensure we have EngineeringAction
        engineering_action_uri = eng_ethics.EngineeringAction
        if (engineering_action_uri, None, None) in g:
            print(f"  - Found EngineeringAction base class")
            # Ensure it has proper parent
            for parent in list(g.objects(engineering_action_uri, RDFS.subClassOf)):
                g.remove((engineering_action_uri, RDFS.subClassOf, parent))
            g.add((engineering_action_uri, RDFS.subClassOf, action_type_uri))
        else:
            print(f"  - Creating EngineeringAction base class")
            g.add((engineering_action_uri, RDF.type, namespaces["owl"].Class))
            g.add((engineering_action_uri, RDFS.label, Literal("Engineering Action")))
            g.add((engineering_action_uri, RDFS.comment, Literal("Base class for all engineering actions")))
            g.add((engineering_action_uri, RDFS.subClassOf, action_type_uri))
        
        # 2. Create specialized action classes
        print("\n2. Creating specialized action types...")
        
        # Define specialized action types
        specialized_actions = {
            "ReportAction": {
                "label": "Report Action",
                "comment": "Actions related to creating, delivering, or handling reports"
            },
            "DesignAction": {
                "label": "Design Action",
                "comment": "Actions related to engineering design activities"
            },
            "ReviewAction": {
                "label": "Review Action",
                "comment": "Actions related to reviewing engineering work"
            },
            "ApprovalAction": {
                "label": "Approval Action",
                "comment": "Actions related to approving engineering work"
            },
            "DecisionAction": {
                "label": "Decision Action",
                "comment": "Actions involving engineering decisions"
            },
            "SafetyAction": {
                "label": "Safety Action",
                "comment": "Actions related to safety in engineering"
            },
            "ConsultationAction": {
                "label": "Consultation Action",
                "comment": "Actions related to engineering consultation"
            }
        }
        
        action_type_classes = {}
        
        for action_name, details in specialized_actions.items():
            action_uri = getattr(eng_ethics, action_name)
            action_type_classes[action_name] = action_uri
            
            # Check if class already exists
            if (action_uri, None, None) in g:
                print(f"  - Found {action_name} class")
                # Ensure it has proper parent
                for parent in list(g.objects(action_uri, RDFS.subClassOf)):
                    g.remove((action_uri, RDFS.subClassOf, parent))
                g.add((action_uri, RDFS.subClassOf, engineering_action_uri))
            else:
                print(f"  - Creating {action_name} class")
                g.add((action_uri, RDF.type, namespaces["owl"].Class))
                g.add((action_uri, RDFS.label, Literal(details["label"])))
                g.add((action_uri, RDFS.comment, Literal(details["comment"])))
                g.add((action_uri, RDFS.subClassOf, engineering_action_uri))
        
        # 3. Find all existing actions and fix their parent classes
        print("\n3. Finding and fixing existing actions...")
        
        # Get all ActionType instances
        action_instances = []
        for s in g.subjects(RDF.type, action_type_uri):
            action_instances.append(s)
        
        # Also look for action-related classes based on name pattern
        for s, p, o in g.triples((None, RDF.type, namespaces["owl"].Class)):
            if "Action" in str(s) or "Decision" in str(s):
                action_instances.append(s)
        
        # Make list unique
        action_instances = list(set(action_instances))
        
        # Fix each action
        for action in action_instances:
            action_label = label_or_id(action)
            print(f"  - Processing action: {action_label}")
            
            # Remove incorrect parents
            current_parents = list(g.objects(action, RDFS.subClassOf))
            invalid_parents = []
            
            for parent in current_parents:
                parent_label = label_or_id(parent)
                if "Report" in parent_label and parent != action_type_classes.get("ReportAction"):
                    invalid_parents.append(parent)
                elif parent == action and parent != action:  # Self-reference check
                    invalid_parents.append(parent)
            
            for invalid_parent in invalid_parents:
                g.remove((action, RDFS.subClassOf, invalid_parent))
                print(f"    - Removed invalid parent: {label_or_id(invalid_parent)}")
            
            # Assign to appropriate parent based on name pattern
            parent_assigned = False
            
            if any(keyword in action_label for keyword in ["Report", "Documentation"]):
                g.add((action, RDFS.subClassOf, action_type_classes["ReportAction"]))
                print(f"    - Assigned to ReportAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Design", "Revision"]):
                g.add((action, RDFS.subClassOf, action_type_classes["DesignAction"]))
                print(f"    - Assigned to DesignAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Review", "Evaluation", "Assessment"]):
                g.add((action, RDFS.subClassOf, action_type_classes["ReviewAction"]))
                print(f"    - Assigned to ReviewAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Approval", "Authorize"]):
                g.add((action, RDFS.subClassOf, action_type_classes["ApprovalAction"]))
                print(f"    - Assigned to ApprovalAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Decision"]):
                g.add((action, RDFS.subClassOf, action_type_classes["DecisionAction"]))
                print(f"    - Assigned to DecisionAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Safety", "Hazard"]):
                g.add((action, RDFS.subClassOf, action_type_classes["SafetyAction"]))
                print(f"    - Assigned to SafetyAction")
                parent_assigned = True
                
            elif any(keyword in action_label for keyword in ["Consult", "Advise"]):
                g.add((action, RDFS.subClassOf, action_type_classes["ConsultationAction"]))
                print(f"    - Assigned to ConsultationAction")
                parent_assigned = True
            
            # If no pattern matched, assign directly to EngineeringAction
            if not parent_assigned:
                g.add((action, RDFS.subClassOf, engineering_action_uri))
                print(f"    - Assigned to EngineeringAction (default)")
        
        # 4. Handle special cases
        print("\n4. Handling special cases...")
        
        # Fix Confidentiality vs Safety Decision
        confidentiality_safety_decision_uri = eng_ethics.ConfidentialityVsSafetyDecision
        if (confidentiality_safety_decision_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(confidentiality_safety_decision_uri, RDFS.subClassOf)):
                g.remove((confidentiality_safety_decision_uri, RDFS.subClassOf, parent))
            
            # Add proper parent
            g.add((confidentiality_safety_decision_uri, RDFS.subClassOf, action_type_classes["DecisionAction"]))
            print(f"  - Fixed Confidentiality vs Safety Decision parent")
        
        # Fix Safety vs Confidentiality Decision
        safety_confidentiality_decision_uri = eng_ethics.SafetyVsConfidentialityDecision
        if (safety_confidentiality_decision_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(safety_confidentiality_decision_uri, RDFS.subClassOf)):
                g.remove((safety_confidentiality_decision_uri, RDFS.subClassOf, parent))
            
            # Add proper parent
            g.add((safety_confidentiality_decision_uri, RDFS.subClassOf, action_type_classes["DecisionAction"]))
            print(f"  - Fixed Safety vs Confidentiality Decision parent")
        
        # Fix Hazard Reporting Action
        hazard_reporting_action_uri = eng_ethics.HazardReportingAction
        if (hazard_reporting_action_uri, None, None) in g:
            # Remove all parents
            for parent in list(g.objects(hazard_reporting_action_uri, RDFS.subClassOf)):
                g.remove((hazard_reporting_action_uri, RDFS.subClassOf, parent))
            
            # Add proper parents (both ReportAction and SafetyAction)
            g.add((hazard_reporting_action_uri, RDFS.subClassOf, action_type_classes["ReportAction"]))
            g.add((hazard_reporting_action_uri, RDFS.subClassOf, action_type_classes["SafetyAction"]))
            print(f"  - Fixed Hazard Reporting Action parents")
        
        # Save the updated ontology
        try:
            # Create new version
            next_version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id
            ).order_by(
                OntologyVersion.version_number.desc()
            ).first()
            
            next_version_num = 1
            if next_version:
                next_version_num = next_version.version_number + 1
                
            # Serialize updated graph
            new_content = g.serialize(format="turtle")
            
            # Create version entry
            version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=next_version_num,
                content=new_content,
                commit_message="Fixed action hierarchy"
            )
            
            # Update ontology content
            ontology.content = new_content
            
            # Save to database
            from app import db
            db.session.add(version)
            db.session.commit()
            
            print(f"\nSuccessfully updated ontology (version {next_version_num})")
            print("Fixed action hierarchy")
            
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
    
    success = fix_action_hierarchy(ontology_id)
    sys.exit(0 if success else 1)
