"""
Script to fix the resource hierarchy in the ontology.
This will:
1. Create base classes for resource categories (EngineeringDocument, EngineeringDrawing, etc.)
2. Update parent classes for resources to have appropriate parents
3. Fix specific issues like Design Drawings having Building Code as parent
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

def fix_resource_hierarchy(ontology_id=1):
    """
    Fix the resource hierarchy in the ontology.
    
    Args:
        ontology_id (int): ID of the ontology to fix
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Fixing resource hierarchy in ontology ID {ontology_id}...")
    
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
        
        # 1. First, ensure ResourceType exists and is properly linked to BFO
        resource_type_uri = namespaces["intermediate"].ResourceType
        if (resource_type_uri, None, None) not in g:
            # Create ResourceType
            print("Creating ResourceType class")
            g.add((resource_type_uri, RDF.type, OWL.Class))
            g.add((resource_type_uri, RDFS.label, Literal("Resource Type")))
            g.add((resource_type_uri, RDFS.comment, Literal("Base class for all resource types in the ontology")))
            # Link to BFO - specifically to 'continuant' as appropriate
            g.add((resource_type_uri, RDFS.subClassOf, namespaces["bfo"].BFO_0000002))  # continuant
        
        base_classes["ResourceType"] = resource_type_uri
        print(f"- ResourceType: {resource_type_uri}")
            
        # 2. Create or reuse EngineeringDocument
        engineering_document_uri = namespaces["engineering-ethics"].EngineeringDocument
        if (engineering_document_uri, None, None) not in g:
            # Create EngineeringDocument
            print("Creating EngineeringDocument class")
            g.add((engineering_document_uri, RDF.type, OWL.Class))
            g.add((engineering_document_uri, RDFS.label, Literal("Engineering Document")))
            g.add((engineering_document_uri, RDFS.comment, Literal("Base class for all engineering documents")))
            g.add((engineering_document_uri, RDFS.subClassOf, resource_type_uri))
        
        base_classes["EngineeringDocument"] = engineering_document_uri
        print(f"- EngineeringDocument: {engineering_document_uri}")
            
        # 3. Create or reuse EngineeringDrawing
        engineering_drawing_uri = namespaces["engineering-ethics"].EngineeringDrawing
        if (engineering_drawing_uri, None, None) not in g:
            # Create EngineeringDrawing
            print("Creating EngineeringDrawing class")
            g.add((engineering_drawing_uri, RDF.type, OWL.Class))
            g.add((engineering_drawing_uri, RDFS.label, Literal("Engineering Drawing")))
            g.add((engineering_drawing_uri, RDFS.comment, Literal("Engineering representations such as plans, sections, and details")))
            g.add((engineering_drawing_uri, RDFS.subClassOf, engineering_document_uri))
        
        base_classes["EngineeringDrawing"] = engineering_drawing_uri
        print(f"- EngineeringDrawing: {engineering_drawing_uri}")
            
        # 4. Create or reuse EngineeringSpecification
        engineering_specification_uri = namespaces["engineering-ethics"].EngineeringSpecification
        if (engineering_specification_uri, None, None) not in g:
            # Create EngineeringSpecification
            print("Creating EngineeringSpecification class")
            g.add((engineering_specification_uri, RDF.type, OWL.Class))
            g.add((engineering_specification_uri, RDFS.label, Literal("Engineering Specification")))
            g.add((engineering_specification_uri, RDFS.comment, Literal("Detailed technical requirements for engineering systems or components")))
            g.add((engineering_specification_uri, RDFS.subClassOf, engineering_document_uri))
        
        base_classes["EngineeringSpecification"] = engineering_specification_uri
        print(f"- EngineeringSpecification: {engineering_specification_uri}")
            
        # 5. Create or reuse EngineeringReport
        engineering_report_uri = namespaces["engineering-ethics"].EngineeringReport
        if (engineering_report_uri, None, None) not in g:
            # Create EngineeringReport
            print("Creating EngineeringReport class")
            g.add((engineering_report_uri, RDF.type, OWL.Class))
            g.add((engineering_report_uri, RDFS.label, Literal("Engineering Report")))
            g.add((engineering_report_uri, RDFS.comment, Literal("Technical report documenting engineering analysis or findings")))
            g.add((engineering_report_uri, RDFS.subClassOf, engineering_document_uri))
        
        base_classes["EngineeringReport"] = engineering_report_uri
        print(f"- EngineeringReport: {engineering_report_uri}")
        
        # 6. Create or reuse BuildingCode
        building_code_uri = namespaces["engineering-ethics"].BuildingCode
        if (building_code_uri, None, None) not in g:
            # Create BuildingCode
            print("Creating BuildingCode class")
            g.add((building_code_uri, RDF.type, OWL.Class))
            g.add((building_code_uri, RDFS.label, Literal("Building Code")))
            g.add((building_code_uri, RDFS.comment, Literal("Regulations governing building construction and safety")))
            g.add((building_code_uri, RDFS.subClassOf, resource_type_uri))
        
        base_classes["BuildingCode"] = building_code_uri
        print(f"- BuildingCode: {building_code_uri}")
        
        # Now let's find all instances of resources and organize them
        resource_subjects = set()
        for ns_name, ns in namespaces.items():
            resource_class = ns.ResourceType
            for s in g.subjects(RDF.type, resource_class):
                resource_subjects.add(s)
        
        # Also look for instances that might be resources but not explicitly typed
        keyword_resources = set()
        keywords = ["Document", "Report", "Drawing", "Specification", "Plan", "Code"]
        
        # Find subjects that contain these keywords in their URI or label
        for s, p, o in g.triples((None, RDF.type, None)):
            if any(keyword in str(s) for keyword in keywords):
                keyword_resources.add(s)
        
        for s, p, o in g.triples((None, RDFS.label, None)):
            if any(keyword in str(o) for keyword in keywords):
                keyword_resources.add(s)
        
        # Merge the sets
        all_resources = resource_subjects.union(keyword_resources)
        
        print(f"\nCategorizing {len(all_resources)} resources...")
        
        # Loop through all resources to find the ones we need to fix
        design_drawing_uri = None
        engineering_spec_uri = None
        
        # Update parent classes for specific resources
        updated_count = 0
        drawing_count = 0
        report_count = 0
        specification_count = 0
        general_count = 0
        code_count = 0
        
        for resource in all_resources:
            label = label_or_id(resource)
            uri = str(resource)
            
            # First, check for specific cases
            if "Design Drawing" in label or "Design Drawings" in label:
                design_drawing_uri = resource
                # Fix the parent class for Design Drawings
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                for old_parent in old_parents:
                    g.remove((resource, RDFS.subClassOf, old_parent))
                
                # Set parent to EngineeringDrawing
                g.add((resource, RDFS.subClassOf, engineering_drawing_uri))
                print(f"  - Fixed Design Drawings parent to Engineering Drawing")
                updated_count += 1
                drawing_count += 1
                
            elif "Engineering Specification" in label:
                engineering_spec_uri = resource
                # Fix the parent class for Engineering Specification
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                for old_parent in old_parents:
                    g.remove((resource, RDFS.subClassOf, old_parent))
                
                # Set parent to EngineeringSpecification
                g.add((resource, RDFS.subClassOf, engineering_specification_uri))
                print(f"  - Fixed Engineering Specification parent to Engineering Specification")
                updated_count += 1
                specification_count += 1
            
            # Now categorize other resources that may need fixes
            elif "Drawing" in label or "Plot" in label or "Plan" in label:
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                if not any(str(p) == str(engineering_drawing_uri) for p in old_parents):
                    # Update to EngineeringDrawing parent
                    for old_parent in old_parents:
                        g.remove((resource, RDFS.subClassOf, old_parent))
                    g.add((resource, RDFS.subClassOf, engineering_drawing_uri))
                    print(f"  - Set parent of {label} to Engineering Drawing")
                    updated_count += 1
                    drawing_count += 1
            
            elif "Report" in label:
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                if not any(str(p) == str(engineering_report_uri) for p in old_parents):
                    # Update to EngineeringReport parent
                    for old_parent in old_parents:
                        g.remove((resource, RDFS.subClassOf, old_parent))
                    g.add((resource, RDFS.subClassOf, engineering_report_uri))
                    print(f"  - Set parent of {label} to Engineering Report")
                    updated_count += 1
                    report_count += 1
            
            elif "Specification" in label:
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                if not any(str(p) == str(engineering_specification_uri) for p in old_parents):
                    # Update to EngineeringSpecification parent
                    for old_parent in old_parents:
                        g.remove((resource, RDFS.subClassOf, old_parent))
                    g.add((resource, RDFS.subClassOf, engineering_specification_uri))
                    print(f"  - Set parent of {label} to Engineering Specification")
                    updated_count += 1
                    specification_count += 1
            
            elif "Code" in label:
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                if not any(str(p) == str(building_code_uri) for p in old_parents):
                    # Update to BuildingCode parent
                    for old_parent in old_parents:
                        g.remove((resource, RDFS.subClassOf, old_parent))
                    g.add((resource, RDFS.subClassOf, building_code_uri))
                    print(f"  - Set parent of {label} to Building Code")
                    updated_count += 1
                    code_count += 1
            
            elif "Document" in label:
                old_parents = list(g.objects(resource, RDFS.subClassOf))
                if not any(str(p) == str(engineering_document_uri) for p in old_parents):
                    # Update to EngineeringDocument parent
                    for old_parent in old_parents:
                        g.remove((resource, RDFS.subClassOf, old_parent))
                    g.add((resource, RDFS.subClassOf, engineering_document_uri))
                    print(f"  - Set parent of {label} to Engineering Document")
                    updated_count += 1
                    general_count += 1
            
            # Ensure proper typing
            if (resource, RDF.type, None) not in g:
                g.add((resource, RDF.type, OWL.Class))
        
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
                commit_message="Fixed resource hierarchy with proper parent classes"
            )
            
            # Update ontology content
            ontology.content = new_content
            
            # Save to database
            from app import db
            db.session.add(version)
            db.session.commit()
            
            print(f"Successfully updated ontology (version {next_version})")
            print(f"Updated {updated_count} resource parents:")
            print(f"  - {drawing_count} drawings")
            print(f"  - {report_count} reports")
            print(f"  - {specification_count} specifications")
            print(f"  - {code_count} building codes")
            print(f"  - {general_count} general documents")
            
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
    
    success = fix_resource_hierarchy(ontology_id)
    sys.exit(0 if success else 1)
