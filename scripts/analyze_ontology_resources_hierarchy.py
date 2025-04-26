"""
Script to analyze and display the hierarchy of resources in the ontology to identify
issues with parent class assignments.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS

def analyze_resource_hierarchy(ontology_id=1):
    """
    Analyze the resource hierarchy in the given ontology to identify any issues.
    """
    print(f"Analyzing resource hierarchy in ontology ID {ontology_id}...")
    
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
        
        # Find all ResourceType instances
        print("\n1. Finding all resource instances...")
        
        resource_subjects = set()
        for ns_name, ns in namespaces.items():
            resource_class = ns.ResourceType
            for s in g.subjects(RDF.type, resource_class):
                resource_subjects.add(s)
                print(f"  - Found resource: {label_or_id(s)}")
        
        # Also look for instances that might be resources but not explicitly typed
        print("\n2. Looking for additional resource-related classes (Document, Report, etc.)...")
        keyword_resources = set()
        keywords = ["Document", "Report", "Drawing", "Specification", "Plan", "Code"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_resources.add(s)
                print(f"  - Found potential resource by keyword: {s} (type: {o})")
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_resources.add(s)
                print(f"  - Found potential resource by label: {s} (label: {o})")
        
        # Merge the sets
        all_resources = resource_subjects.union(keyword_resources)
        print(f"\nTotal resource-related entities found: {len(all_resources)}")
        
        # Analyze subClassOf relationships
        print("\n3. Analyzing subClassOf relationships for resources...")
        
        resource_hierarchy = {}
        orphaned_resources = []
        
        for resource in all_resources:
            parent_classes = list(g.objects(resource, RDFS.subClassOf))
            
            if not parent_classes:
                orphaned_resources.append(resource)
                resource_hierarchy[resource] = []
                print(f"  ! Resource has no parent: {label_or_id(resource)}")
                continue
            
            resource_hierarchy[resource] = parent_classes
            
            # Display parents
            parents_str = ", ".join([label_or_id(p) for p in parent_classes])
            print(f"  - {label_or_id(resource)} → {parents_str}")
        
        # Check for resource self-references
        print("\n4. Checking for resources that reference themselves as parents...")
        
        self_referencing_resources = []
        for resource, parents in resource_hierarchy.items():
            if resource in parents:
                self_referencing_resources.append(resource)
                print(f"  ! Self-reference detected: {label_or_id(resource)}")
        
        # Group resources by common patterns
        print("\n5. Grouping resources by type patterns...")
        
        # Initialize category maps
        document_resources = []
        report_resources = []
        drawing_resources = []
        specification_resources = []
        code_resources = []
        general_resources = []
        
        for resource in all_resources:
            label = label_or_id(resource)
            uri = str(resource)
            
            if "Document" in label or "Document" in uri:
                document_resources.append(resource)
            elif "Report" in label or "Report" in uri:
                report_resources.append(resource)
            elif "Drawing" in label or "Drawing" in uri:
                drawing_resources.append(resource)  
            elif "Specification" in label or "Specification" in uri:
                specification_resources.append(resource)
            elif "Code" in label or "Code" in uri:
                code_resources.append(resource)
            else:
                general_resources.append(resource)
        
        # Print groups
        print("\nDocument Resources:")
        for r in document_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
            
        print("\nReport Resources:")
        for r in report_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
            
        print("\nDrawing Resources:")
        for r in drawing_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
            
        print("\nSpecification Resources:")
        for r in specification_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
            
        print("\nCode Resources:")
        for r in code_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
            
        print("\nGeneral Resources:")
        for r in general_resources:
            parents = resource_hierarchy.get(r, [])
            parent_str = ", ".join([label_or_id(p) for p in parents]) if parents else "NO PARENT"
            print(f"  - {label_or_id(r)} → {parent_str}")
        
        # Check for base resource classes
        print("\n6. Looking for base resource classes...")
        
        base_classes = {
            "ResourceType": None,
            "EngineeringDocument": None,
            "EngineeringReport": None, 
            "EngineeringDrawing": None,
            "EngineeringSpecification": None,
            "BuildingCode": None
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
        
        # Find problematic parent assignments
        print("\n7. Looking for problematic parent assignments...")
        design_drawings_uri = None
        engineering_spec_uri = None
        structural_report_uri = None
        
        for resource in all_resources:
            label = label_or_id(resource)
            if "Design Drawing" in label:
                design_drawings_uri = resource
                parents = list(g.objects(resource, RDFS.subClassOf))
                for parent in parents:
                    parent_label = label_or_id(parent)
                    if "Building Code" in parent_label:
                        print(f"  ! Design Drawings has incorrect parent: {parent_label}")
                        print(f"    Should be Engineering Drawing instead")
            elif "Engineering Specification" in label:
                engineering_spec_uri = resource
                parents = list(g.objects(resource, RDFS.subClassOf))
                for parent in parents:
                    parent_label = label_or_id(parent)
                    if "Building Code" in parent_label:
                        print(f"  ! Engineering Specification has incorrect parent: {parent_label}")
                        print(f"    Should be Engineering Document or Engineering Specification instead")
            elif "Structural Report" in label:
                structural_report_uri = resource
                parents = list(g.objects(resource, RDFS.subClassOf))
                correct_parent = False
                for parent in parents:
                    parent_label = label_or_id(parent)
                    if "Engineering Report" in parent_label:
                        correct_parent = True
                if not correct_parent:
                    print(f"  ! Structural Report should keep Engineering Report as parent")
                else:
                    print(f"  ✓ Structural Report has correct parent: Engineering Report")
        
        # Propose changes
        print("\n8. Proposed hierarchy improvements:")
        
        # Check if appropriate base classes exist
        if not base_classes["EngineeringDocument"]:
            print("  - Create EngineeringDocument class as base for all engineering documents")
        if not base_classes["EngineeringDrawing"]:
            print("  - Create EngineeringDrawing class as child of EngineeringDocument")
        if not base_classes["EngineeringSpecification"]:
            print("  - Create EngineeringSpecification class as child of EngineeringDocument")
        if not base_classes["EngineeringReport"]:
            print("  - Create EngineeringReport class as child of EngineeringDocument")
        
        # Recommend specific changes
        if design_drawings_uri:
            print("  - Update Design Drawings parent to be EngineeringDrawing instead of BuildingCode")
        if engineering_spec_uri:
            print("  - Update Engineering Specification parent to be EngineeringSpecification")
        
        # Summary
        print("\n=== SUMMARY ===")
        print(f"Total resource-related entities found: {len(all_resources)}")
        print(f"Document resources: {len(document_resources)}")
        print(f"Report resources: {len(report_resources)}")
        print(f"Drawing resources: {len(drawing_resources)}")
        print(f"Specification resources: {len(specification_resources)}")
        print(f"Code resources: {len(code_resources)}")
        print(f"General resources: {len(general_resources)}")
        print(f"Resources without parents: {len(orphaned_resources)}")
        print(f"Self-referencing resources: {len(self_referencing_resources)}")
        
        # Return the data for further use
        return {
            "all_resources": list(all_resources),
            "resource_hierarchy": resource_hierarchy,
            "base_classes": base_classes,
            "document_resources": document_resources,
            "report_resources": report_resources, 
            "drawing_resources": drawing_resources,
            "specification_resources": specification_resources,
            "code_resources": code_resources
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
    
    analyze_resource_hierarchy(ontology_id)
