"""
Script to analyze and display the hierarchy of roles in the ontology to identify
issues with parent class assignments.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS

def analyze_role_hierarchy(ontology_id=1):
    """
    Analyze the role hierarchy in the given ontology to identify any issues.
    """
    print(f"Analyzing role hierarchy in ontology ID {ontology_id}...")
    
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
        
        # Find all Role instances
        print("\n1. Finding all role instances...")
        
        role_subjects = set()
        for ns_name, ns in namespaces.items():
            role_class = ns.Role
            for s in g.subjects(RDF.type, role_class):
                role_subjects.add(s)
                print(f"  - Found role: {label_or_id(s)}")
        
        # Analyze subClassOf relationships
        print("\n2. Analyzing subClassOf relationships for roles...")
        
        role_hierarchy = {}
        orphaned_roles = []
        
        for role in role_subjects:
            parent_classes = list(g.objects(role, RDFS.subClassOf))
            
            if not parent_classes:
                orphaned_roles.append(role)
                role_hierarchy[role] = []
                print(f"  ! Role has no parent: {label_or_id(role)}")
                continue
            
            role_hierarchy[role] = parent_classes
            
            # Display parents
            parents_str = ", ".join([label_or_id(p) for p in parent_classes])
            print(f"  - {label_or_id(role)} → {parents_str}")
        
        # Check for role self-references
        print("\n3. Checking for roles that reference themselves as parents...")
        
        self_referencing_roles = []
        for role, parents in role_hierarchy.items():
            if role in parents:
                self_referencing_roles.append(role)
                print(f"  ! Self-reference detected: {label_or_id(role)}")
        
        # Validate parent classes exist
        print("\n4. Validating that parent classes exist in the graph...")
        
        invalid_parents = []
        for role, parents in role_hierarchy.items():
            for parent in parents:
                # Check if parent exists in graph
                if (parent, None, None) not in g:
                    invalid_parents.append((role, parent))
                    print(f"  ! Invalid parent: {label_or_id(role)} → {parent}")
                
                # Check if parent is a Role or related class
                valid_parent = False
                for ns_name, ns in namespaces.items():
                    if (parent, RDF.type, ns.Role) in g or \
                       (parent, RDF.type, ns.EntityType) in g:
                        valid_parent = True
                        break
                
                if not valid_parent and (parent, None, None) in g:
                    print(f"  ! Parent not a Role or EntityType: {label_or_id(role)} → {label_or_id(parent)}")
        
        # Build full inheritance chains
        print("\n5. Building complete inheritance chains for each role...")
        
        def get_inheritance_chain(role, visited=None):
            """Get the full inheritance chain for a role"""
            if visited is None:
                visited = set()
                
            # Avoid cycles
            if role in visited:
                return [f"CYCLE: {label_or_id(role)}"]
            
            visited.add(role)
            
            parents = role_hierarchy.get(role, [])
            if not parents:
                return [label_or_id(role)]
            
            result = [label_or_id(role)]
            for parent in parents:
                # Only follow parent if it's a defined role
                if parent in role_hierarchy:
                    parent_chain = get_inheritance_chain(parent, visited.copy())
                    result.extend(parent_chain)
                else:
                    # For other entities, just add the label
                    result.append(label_or_id(parent))
            
            return result
        
        print("\nRole inheritance chains:")
        for role in role_subjects:
            chain = get_inheritance_chain(role)
            print(f"  {label_or_id(role)}: {' → '.join(chain)}")
            
        # Check EngineeringRole parent class
        print("\n6. Checking for EngineeringRole class:")
        engineering_role = namespaces["engineering-ethics"].EngineeringRole
        if (engineering_role, None, None) in g:
            print(f"  Engineering Role class exists: {engineering_role}")
            # Check what type it is
            types = list(g.objects(engineering_role, RDF.type))
            print(f"  Types: {[str(t) for t in types]}")
            # Who is the parent?
            parents = list(g.objects(engineering_role, RDFS.subClassOf))
            print(f"  Parents: {[label_or_id(p) for p in parents]}")
            # Who has this as parent?
            children = list(g.subjects(RDFS.subClassOf, engineering_role))
            print(f"  Children: {[label_or_id(c) for c in children]}")
        else:
            print("  Engineering Role class does not exist explicitly in the graph")
        
        # Check specifically the Structural Engineer Role's parent
        print("\n7. Examining Structural Engineer Role specifically:")
        structural_role = namespaces["engineering-ethics"].StructuralEngineerRole
        if (structural_role, None, None) in g:
            print(f"  Structural Engineer Role exists: {structural_role}")
            # Check types
            types = list(g.objects(structural_role, RDF.type))
            print(f"  Types: {[str(t) for t in types]}")
            # Check parent
            parents = list(g.objects(structural_role, RDFS.subClassOf))
            print(f"  Parents: {[label_or_id(p) for p in parents]}")
            
        # Summary
        print("\n=== SUMMARY ===")
        print(f"Total roles found: {len(role_subjects)}")
        print(f"Roles without parents: {len(orphaned_roles)}")
        print(f"Self-referencing roles: {len(self_referencing_roles)}")
        print(f"Roles with invalid parents: {len(invalid_parents)}")

if __name__ == '__main__':
    # Default ontology ID is 1, but can be passed as command-line argument
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            sys.exit(1)
    
    analyze_role_hierarchy(ontology_id)
