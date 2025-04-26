"""
Script to analyze and display the hierarchy of conditions in the ontology to identify
issues with parent class assignments.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS

def analyze_condition_hierarchy(ontology_id=1):
    """
    Analyze the condition hierarchy in the given ontology to identify any issues.
    """
    print(f"Analyzing condition hierarchy in ontology ID {ontology_id}...")
    
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
        
        # Find all ConditionType instances
        print("\n1. Finding all condition instances...")
        
        condition_subjects = set()
        for ns_name, ns in namespaces.items():
            condition_class = ns.ConditionType
            for s in g.subjects(RDF.type, condition_class):
                condition_subjects.add(s)
                print(f"  - Found condition: {label_or_id(s)}")
        
        # Also look for instances that contain "Dilemma", "Principle", etc.
        print("\n2. Looking for additional condition-related classes (Dilemmas, Principles)...")
        keyword_conditions = set()
        keywords = ["Dilemma", "Principle", "Condition"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_conditions.add(s)
                print(f"  - Found potential condition by keyword: {s} (type: {o})")
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_conditions.add(s)
                print(f"  - Found potential condition by label: {s} (label: {o})")
        
        # Merge the sets
        all_conditions = condition_subjects.union(keyword_conditions)
        print(f"\nTotal condition-related entities found: {len(all_conditions)}")
        
        # Analyze subClassOf relationships
        print("\n3. Analyzing subClassOf relationships for conditions...")
        
        condition_hierarchy = {}
        orphaned_conditions = []
        
        for condition in all_conditions:
            parent_classes = list(g.objects(condition, RDFS.subClassOf))
            
            if not parent_classes:
                orphaned_conditions.append(condition)
                condition_hierarchy[condition] = []
                print(f"  ! Condition has no parent: {label_or_id(condition)}")
                continue
            
            condition_hierarchy[condition] = parent_classes
            
            # Display parents
            parents_str = ", ".join([label_or_id(p) for p in parent_classes])
            print(f"  - {label_or_id(condition)} → {parents_str}")
        
        # Check for condition self-references
        print("\n4. Checking for conditions that reference themselves as parents...")
        
        self_referencing_conditions = []
        for condition, parents in condition_hierarchy.items():
            if condition in parents:
                self_referencing_conditions.append(condition)
                print(f"  ! Self-reference detected: {label_or_id(condition)}")
        
        # Group conditions by common patterns
        print("\n5. Grouping conditions by type patterns...")
        
        # Initialize category maps
        dilemma_conditions = []
        principle_conditions = []
        safety_conditions = []
        conflict_conditions = []
        general_conditions = []
        
        for condition in all_conditions:
            label = label_or_id(condition)
            uri = str(condition)
            
            if "Dilemma" in label or "Dilemma" in uri:
                dilemma_conditions.append(condition)
            elif "Principle" in label or "Principle" in uri:
                principle_conditions.append(condition)
            elif "Safety" in label or "Safety" in uri:
                safety_conditions.append(condition)
            elif "Conflict" in label or "Conflict" in uri:
                conflict_conditions.append(condition)
            else:
                general_conditions.append(condition)
        
        # Print groups
        print("\nDilemma Conditions:")
        for c in dilemma_conditions:
            parents = condition_hierarchy.get(c, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(c)} → {parent_str}")
            
        print("\nPrinciple Conditions:")
        for c in principle_conditions:
            parents = condition_hierarchy.get(c, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(c)} → {parent_str}")
            
        print("\nSafety Conditions:")
        for c in safety_conditions:
            parents = condition_hierarchy.get(c, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(c)} → {parent_str}")
            
        print("\nConflict Conditions:")
        for c in conflict_conditions:
            parents = condition_hierarchy.get(c, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(c)} → {parent_str}")
            
        print("\nGeneral Conditions:")
        for c in general_conditions:
            parents = condition_hierarchy.get(c, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(c)} → {parent_str}")
        
        # Check for base conditions
        print("\n6. Looking for base condition classes...")
        
        base_classes = {
            "ConditionType": None,
            "EthicalDilemma": None, 
            "Principle": None,
            "SafetyPrinciple": None,
            "ConflictOfInterest": None
        }
        
        for base_class in base_classes.keys():
            for ns_name, ns in namespaces.items():
                class_uri = getattr(ns, base_class, None)
                if class_uri and (class_uri, None, None) in g:
                    base_classes[base_class] = class_uri
                    print(f"  - Found base class: {base_class} as {class_uri}")
                    # Check its type
                    types = list(g.objects(class_uri, RDF.type))
                    print(f"    Types: {[str(t) for t in types]}")
                    # Check its parents
                    parents = list(g.objects(class_uri, RDFS.subClassOf))
                    print(f"    Parents: {[label_or_id(p) for p in parents]}")
        
        # Identify BFO positioning
        print("\n7. Checking relationship to BFO classes...")
        bfo_prefix = "http://purl.obolibrary.org/obo/BFO_"
        
        for condition in all_conditions:
            # Find path to BFO
            current = condition
            path = [current]
            bfo_found = False
            
            while current and not bfo_found:
                parents = list(g.objects(current, RDFS.subClassOf))
                if not parents:
                    break
                    
                # Check if any parent is a BFO class
                for parent in parents:
                    parent_str = str(parent)
                    if parent_str.startswith(bfo_prefix):
                        path.append(parent)
                        bfo_found = True
                        print(f"  - {label_or_id(condition)} has a path to BFO: {label_or_id(parent)}")
                        print(f"    Path: {' → '.join([label_or_id(p) for p in path])}")
                        break
                
                if not bfo_found and parents:
                    current = parents[0]  # Just follow first parent
                    path.append(current)
                else:
                    break
            
            # If path is too long, it likely means we didn't find a direct BFO connection
            if len(path) > 5 and not bfo_found:
                print(f"  ! {label_or_id(condition)} may not have a proper BFO path")
        
        # Suggest improvements
        print("\n8. Proposing hierarchy improvements...")
        
        # Check if EthicalDilemma class exists
        ethical_dilemma_uri = None
        for ns_name, ns in namespaces.items():
            try:
                uri = ns.EthicalDilemma
                if (uri, None, None) in g:
                    ethical_dilemma_uri = uri
                    break
            except:
                pass
        
        # If not found, we'll suggest creating it
        if not ethical_dilemma_uri:
            print("  - Should create an EthicalDilemma class as parent for all dilemmas")
        
        # Check Principle classes
        principle_uri = None
        safety_principle_uri = None
        
        for ns_name, ns in namespaces.items():
            try:
                uri = ns.Principle
                if (uri, None, None) in g:
                    principle_uri = uri
            except:
                pass
                
            try:
                uri = ns.SafetyPrinciple
                if (uri, None, None) in g:
                    safety_principle_uri = uri
            except:
                pass
        
        if not principle_uri:
            print("  - Should create a Principle class as parent for all principles")
        
        if not safety_principle_uri and principle_uri:
            print("  - Should create a SafetyPrinciple class as child of Principle")
        
        # Check specific issues mentioned by user
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
            if not ethical_dilemma_uri or ethical_dilemma_uri not in parents:
                print(f"  - 'Competence vs Client Wishes Dilemma' should have EthicalDilemma as parent")
        
        if public_safety_uri:
            parents = list(g.objects(public_safety_uri, RDFS.subClassOf))
            if not safety_principle_uri or safety_principle_uri not in parents:
                print(f"  - 'Public Safety Principle' should have SafetyPrinciple as parent")
        
        # Summary
        print("\n=== SUMMARY ===")
        print(f"Total condition-related entities found: {len(all_conditions)}")
        print(f"Dilemma conditions: {len(dilemma_conditions)}")
        print(f"Principle conditions: {len(principle_conditions)}")
        print(f"Safety conditions: {len(safety_conditions)}")
        print(f"Conflict conditions: {len(conflict_conditions)}")
        print(f"General conditions: {len(general_conditions)}")
        print(f"Conditions without parents: {len(orphaned_conditions)}")
        print(f"Self-referencing conditions: {len(self_referencing_conditions)}")
        
        # Return valuable data for possible use in fixing
        return {
            'all_conditions': all_conditions,
            'condition_hierarchy': condition_hierarchy,
            'dilemma_conditions': dilemma_conditions,
            'principle_conditions': principle_conditions,
            'safety_conditions': safety_conditions,
            'conflict_conditions': conflict_conditions,
            'general_conditions': general_conditions,
            'base_classes': base_classes
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
    
    analyze_condition_hierarchy(ontology_id)
