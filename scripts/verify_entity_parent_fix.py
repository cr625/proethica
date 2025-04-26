"""
Script to verify the entity parent fix has been properly applied.
"""
import sys
import os
import requests
import json

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, URIRef, Literal, Namespace, RDF, RDFS
from ontology_editor.services.entity_service import EntityService

def check_engineering_role_in_dropdown():
    """
    Check if EngineeringRole appears in the parent dropdown options for roles.
    """
    print("Checking for Engineering Role in parent dropdown options...")
    
    app = create_app()
    with app.app_context():
        parents = EntityService.get_valid_parents(1, 'role')
        
        # Check specifically for EngineeringRole
        found_eng_role = False
        found_base_role = False
        
        print("\nAvailable parent options for roles:")
        for parent in parents:
            print(f"- {parent['label']} (ID: {parent['id']})")
            
            if 'EngineeringRole' in parent['id']:
                found_eng_role = True
            
            if 'intermediate#Role' in parent['id']:
                found_base_role = True
                
        # Print results
        print(f"\nEngineeringRole found: {'Yes' if found_eng_role else 'No'}")
        print(f"Base Role found: {'Yes' if found_base_role else 'No'}")
        
        # Check that the sort order is working
        print("\nVerifying sort order:")
        labels = [p['label'] for p in parents]
        labels_sorted = sorted(labels)
        if labels == labels_sorted:
            print("✓ Parents are correctly sorted by label")
        else:
            print("✗ Parents are NOT correctly sorted by label")
            print(f"Current order: {', '.join(labels)}")
            print(f"Sorted order: {', '.join(labels_sorted)}")
            
        # Return parents for further processing
        return parents

def check_role_parent_matches(parents):
    """
    Check which roles have parent classes that match the available dropdown options.
    """
    print("\nChecking which roles have matching parents in the dropdown...")
    
    app = create_app()
    with app.app_context():
        # Get the ontology
        ontology = Ontology.query.get(1)
        if not ontology:
            print("Ontology not found!")
            return
            
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Get all roles and their parent classes
        roles = []
        namespaces = {"eng": Namespace("http://proethica.org/ontology/engineering-ethics#")}
        
        # Define both intermediate and engineering namespaces
        int_ns = Namespace("http://proethica.org/ontology/intermediate#")
        eng_ns = Namespace("http://proethica.org/ontology/engineering-ethics#")
        
        role_class = int_ns.Role  # Base role from intermediate ontology
        eng_role_class = eng_ns.EngineeringRole  # Engineering role
        
        # Try a simpler approach - find all classes that have parent classes
        for subject, _, parent in g.triples((None, RDFS.subClassOf, None)):
            # Only include if it has a label
            label = next(g.objects(subject, RDFS.label), None)
            if label:
                # Only include subjects that are likely roles
                subj_str = str(subject)
                if 'Role' in subj_str:
                    # Make sure it's an engineering role
                    if 'engineering-ethics' in subj_str:
                        roles.append({
                            'id': subj_str,
                            'label': str(label),
                            'parent_class': str(parent)
                        })
                    
        print(f"\nFound {len(roles)} roles in the ontology")
        
        # Check for each role whether its parent_class is in the dropdown options
        parent_ids = [p['id'] for p in parents]
        matched_roles = []
        unmatched_roles = []
        
        for role in roles:
            if role['parent_class'] and role['parent_class'] in parent_ids:
                matched_parent = next((p for p in parents if p['id'] == role['parent_class']), None)
                matched_roles.append({
                    'role': role['label'],
                    'parent_class': role['parent_class'],
                    'parent_label': matched_parent['label'] if matched_parent else "Unknown"
                })
            else:
                unmatched_roles.append({
                    'role': role['label'],
                    'parent_class': role['parent_class']
                })
                
        # Print results
        print(f"\nRoles with matching parent classes: {len(matched_roles)}/{len(roles)}")
        print("Matching roles:")
        for role in matched_roles:
            print(f"- {role['role']} → {role['parent_label']} ({role['parent_class']})")
            
        print("\nRoles without matching parent classes:")
        for role in unmatched_roles:
            print(f"- {role['role']} → {role['parent_class']}")
            
def main():
    """Main function"""
    print("Verifying entity parent class fix...")
    
    # Check for EngineeringRole
    parents = check_engineering_role_in_dropdown()
    
    # Check role parent matches
    check_role_parent_matches(parents)
    
    print("\nVerification complete!")

if __name__ == '__main__':
    main()
