"""
Script to analyze and display the hierarchy of actions in the ontology to identify
issues with parent class assignments.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS

def analyze_action_hierarchy(ontology_id=1):
    """
    Analyze the action hierarchy in the given ontology to identify any issues.
    """
    print(f"Analyzing action hierarchy in ontology ID {ontology_id}...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology ID {ontology_id} not found.")
            return
        
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
            return str(next(g.objects(s, RDFS.label), s))
        
        # Find all ActionType instances
        print("\n1. Finding all action instances...")
        
        action_subjects = set()
        for ns_name, ns in namespaces.items():
            action_class = ns.ActionType
            for s in g.subjects(RDF.type, action_class):
                action_subjects.add(s)
                print(f"  - Found action: {label_or_id(s)}")
        
        # Also look for instances that might be actions but not explicitly typed
        print("\n2. Looking for additional action-related classes...")
        keyword_actions = set()
        keywords = ["Action", "Approval", "Decision", "Report", "Consultation", "Review", "Inspection"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_actions.add(s)
                print(f"  - Found potential action by keyword: {s} (type: {o})")
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_actions.add(s)
                print(f"  - Found potential action by label: {s} (label: {o})")
        
        # Merge the sets
        all_actions = action_subjects.union(keyword_actions)
        print(f"\nTotal action-related entities found: {len(all_actions)}")
        
        # Analyze subClassOf relationships
        print("\n3. Analyzing subClassOf relationships for actions...")
        
        action_hierarchy = {}
        orphaned_actions = []
        
        for action in all_actions:
            parent_classes = list(g.objects(action, RDFS.subClassOf))
            
            if not parent_classes:
                orphaned_actions.append(action)
                action_hierarchy[action] = []
                print(f"  ! Action has no parent: {label_or_id(action)}")
                continue
            
            action_hierarchy[action] = parent_classes
            
            # Display parents
            parents_str = ", ".join([label_or_id(p) for p in parent_classes])
            print(f"  - {label_or_id(action)} → {parents_str}")
        
        # Check for action self-references
        print("\n4. Checking for actions that reference themselves as parents...")
        
        self_referencing_actions = []
        for action, parents in action_hierarchy.items():
            if action in parents:
                self_referencing_actions.append(action)
                print(f"  ! Self-reference detected: {label_or_id(action)}")
        
        # Group actions by common patterns
        print("\n5. Grouping actions by parent type...")
        
        # Group by parent class
        grouped_by_parent = {}
        
        for action, parents in action_hierarchy.items():
            action_label = label_or_id(action)
            
            for parent in parents:
                parent_label = label_or_id(parent)
                if parent_label not in grouped_by_parent:
                    grouped_by_parent[parent_label] = []
                grouped_by_parent[parent_label].append(action)
        
        # Print groups
        for parent_name, actions in grouped_by_parent.items():
            print(f"\nActions with parent '{parent_name}':")
            for action in actions:
                print(f"  - {label_or_id(action)}")
        
        # Check for action base classes
        print("\n6. Looking for action base classes...")
        
        base_classes = {
            "ActionType": None,
            "EngineeringAction": None,
            "DesignAction": None,
            "ReviewAction": None,
            "ApprovalAction": None,
            "ReportAction": None,
            "ConsultationAction": None,
            "SafetyAction": None
        }
        
        for base_class in base_classes.keys():
            for ns_name, ns in namespaces.items():
                try:
                    class_uri = getattr(ns, base_class)
                    if (class_uri, None, None) in g:
                        base_classes[base_class] = class_uri
                        print(f"  - Found base class: {base_class} as {class_uri}")
                        # Check its type
                        types = list(g.objects(class_uri, RDF.type))
                        print(f"    Types: {[str(t) for t in types]}")
                        # Check its parents
                        parents = list(g.objects(class_uri, RDFS.subClassOf))
                        print(f"    Parents: {[label_or_id(p) for p in parents]}")
                except:
                    pass
        
        # Analyze action categorization
        print("\n7. Categorizing actions by purpose:")
        
        # Define common action categories
        action_categories = {
            "review": [],
            "reporting": [],
            "approval": [],
            "design": [],
            "consultation": [],
            "safety": [],
            "ethical": [],
            "other": []
        }
        
        for action in all_actions:
            label = label_or_id(action)
            added = False
            
            if any(keyword in label for keyword in ["Review", "Evaluation", "Assessment"]):
                action_categories["review"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Report", "Document", "Documentation"]):
                action_categories["reporting"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Approv", "Accept", "Authorize"]):
                action_categories["approval"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Design", "Engineering", "Technical"]):
                action_categories["design"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Consult", "Advise", "Recommend"]):
                action_categories["consultation"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Safety", "Risk", "Hazard", "Protection"]):
                action_categories["safety"].append(action)
                added = True
            
            if any(keyword in label for keyword in ["Ethic", "Confidential", "Integrity", "Honest"]):
                action_categories["ethical"].append(action)
                added = True
            
            if not added:
                action_categories["other"].append(action)
        
        # Print categorized actions
        for category, actions in action_categories.items():
            if not actions:
                continue
                
            print(f"\n{category.capitalize()} Actions:")
            for action in actions:
                parents = action_hierarchy.get(action, [])
                parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
                print(f"  - {label_or_id(action)} → {parent_str}")
        
        # Check for common patterns in parent assignment
        print("\n8. Analyzing action parent assignment patterns:")
        
        parent_patterns = {}
        for action, parents in action_hierarchy.items():
            action_label = label_or_id(action)
            
            for parent in parents:
                parent_label = label_or_id(parent)
                if parent_label not in parent_patterns:
                    parent_patterns[parent_label] = {"count": 0, "example": None}
                
                parent_patterns[parent_label]["count"] += 1
                
                if not parent_patterns[parent_label]["example"]:
                    parent_patterns[parent_label]["example"] = action_label
        
        # Print parent patterns
        for parent_label, data in sorted(parent_patterns.items(), key=lambda x: x[1]["count"], reverse=True):
            print(f"  - {parent_label}: {data['count']} actions (e.g., {data['example']})")
        
        # Check for inconsistencies in parent assignments
        print("\n9. Checking for action parent assignment inconsistencies:")
        
        # Group by action name pattern and check parent consistency
        name_patterns = {}
        for action in all_actions:
            label = label_or_id(action)
            name_part = label.split(' ')[0] if ' ' in label else label
            
            if name_part not in name_patterns:
                name_patterns[name_part] = {"actions": [], "parents": set()}
            
            name_patterns[name_part]["actions"].append(action)
            for parent in action_hierarchy.get(action, []):
                name_patterns[name_part]["parents"].add(label_or_id(parent))
        
        # Check for inconsistent parent assignments
        for name_part, data in name_patterns.items():
            if len(data["actions"]) > 1 and len(data["parents"]) > 1:
                print(f"  ! Inconsistent parents for actions starting with '{name_part}':")
                for action in data["actions"]:
                    parents = action_hierarchy.get(action, [])
                    parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
                    print(f"    - {label_or_id(action)} → {parent_str}")
        
        # Propose improvements
        print("\n10. Suggested improvements for action hierarchy:")
        
        # Check if we have a proper hierarchy
        if not base_classes["EngineeringAction"]:
            print("  - Create EngineeringAction as a base class for engineering actions")
        
        # Check for missing action category classes
        for category in ["DesignAction", "ReviewAction", "ReportAction", "ApprovalAction"]:
            if not base_classes[category]:
                print(f"  - Create {category} as a specialized action category")
        
        # Look for actions with inappropriate parents
        safety_decision_parent = None
        confidentiality_parent = None
        
        for parent_label, data in parent_patterns.items():
            if "Safety Decision" in parent_label:
                safety_decision_parent = parent_label
            elif "Confidentiality" in parent_label:
                confidentiality_parent = parent_label
                
        # Print summary of problematic assignments
        if safety_decision_parent:
            print(f"  - Reconsider actions with '{safety_decision_parent}' parent:")
            for action in all_actions:
                parents = action_hierarchy.get(action, [])
                for parent in parents:
                    if safety_decision_parent in label_or_id(parent):
                        print(f"    * {label_or_id(action)}")
                        
        if confidentiality_parent:
            print(f"  - Reconsider actions with '{confidentiality_parent}' parent:")
            for action in all_actions:
                parents = action_hierarchy.get(action, [])
                for parent in parents:
                    if confidentiality_parent in label_or_id(parent):
                        print(f"    * {label_or_id(action)}")
        
        # Summary
        print("\n=== SUMMARY ===")
        print(f"Total action-related entities found: {len(all_actions)}")
        print(f"Actions without parents: {len(orphaned_actions)}")
        print(f"Self-referencing actions: {len(self_referencing_actions)}")
        print(f"Different parent patterns: {len(parent_patterns)}")
        
        if safety_decision_parent or confidentiality_parent:
            print("\nRECOMMENDATION:")
            print("  Consider reorganizing action hierarchy to use more specific action types as parents")
            print("  instead of condition-based parents (Safety Decision, Confidentiality, etc.)")
        
        # Return the data for further use
        return {
            "all_actions": list(all_actions),
            "action_hierarchy": action_hierarchy,
            "base_classes": base_classes,
            "action_categories": action_categories
        }

if __name__ == '__main__':
    # Default ontology ID is 1, but can be passed as command-line argument
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            sys.exit(1)
    
    analyze_action_hierarchy(ontology_id)
