#!/usr/bin/env python3
"""
Script to debug the entity extraction process from the ontology.
This helps diagnose issues with displaying entities on the world detail page.
"""
import os
import sys
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from app
from app import create_app, db
from app.models.ontology import Ontology

def debug_entity_extraction(ontology_id=1):
    """
    Debug the entity extraction process by examining the ontology content
    and checking if entities are correctly defined and can be extracted.
    
    Args:
        ontology_id: ID of the ontology to analyze
    """
    app = create_app()
    with app.app_context():
        # Get the ontology from the database
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Error: Ontology with ID {ontology_id} not found!")
            return
        
        print(f"Analyzing ontology '{ontology.name}' (domain_id: {ontology.domain_id})")
        
        # Parse ontology content into a graph
        g = Graph()
        try:
            g.parse(data=ontology.content, format="turtle")
            print(f"Successfully parsed ontology content. Graph contains {len(g)} triples.")
        except Exception as e:
            print(f"Error parsing ontology content: {str(e)}")
            return
        
        # Print all namespaces in the graph
        print("\nNamespaces in graph:")
        for prefix, namespace in g.namespaces():
            print(f"  {prefix}: {namespace}")
        
        # Define known namespaces
        namespaces = {
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "engineering-ethics-nspe-extended": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#")
        }
        
        # Try to find the primary namespace
        print("\nTrying to detect primary namespace:")
        primary_namespace = None
        
        # Look for owl:Ontology declaration
        for s, p, o in g.triples((None, rdflib.OWL.Ontology, None)):
            print(f"  Found ontology declaration at {s}")
            ontology_uri = str(s)
            if "engineering-ethics" in ontology_uri:
                primary_namespace = "engineering-ethics"
                print(f"  This looks like engineering-ethics namespace")
            elif "intermediate" in ontology_uri:
                primary_namespace = "intermediate"
                print(f"  This looks like intermediate namespace")
        
        # Use the primary namespace from the detection or default
        namespace = namespaces.get(primary_namespace or "engineering-ethics-nspe-extended")
        proeth_namespace = namespaces["intermediate"]
        
        print(f"\nUsing primary namespace: {namespace}")
        print(f"Using intermediate namespace: {proeth_namespace}")
        
        # Function to get label of entity
        def label_or_id(s):
            return str(next(g.objects(s, RDFS.label), s))
        
        # Check for different entity types
        entity_types = [
            ("Role", namespace.Role, proeth_namespace.Role),
            ("ConditionType", namespace.ConditionType, proeth_namespace.ConditionType),
            ("ResourceType", namespace.ResourceType, proeth_namespace.ResourceType),
            ("EventType", namespace.EventType, proeth_namespace.EventType),
            ("ActionType", namespace.ActionType, proeth_namespace.ActionType),
            ("Capability", namespace.Capability, proeth_namespace.Capability)
        ]
        
        # Also check these as RDF classes
        print("\nLooking for basic class definitions:")
        for class_name in ["Role", "ConditionType", "ResourceType", "EventType", "ActionType", "Capability"]:
            class_uri = URIRef(f"http://proethica.org/ontology/intermediate#{class_name}")
            if (class_uri, RDF.type, rdflib.OWL.Class) in g:
                print(f"  Found {class_name} defined as owl:Class")
        
        # Check for rdf:type EntityType instances
        print("\nLooking for EntityType instances:")
        entity_type_uri = URIRef("http://proethica.org/ontology/intermediate#EntityType")
        entity_type_count = len(list(g.subjects(RDF.type, entity_type_uri)))
        print(f"  Found {entity_type_count} instances of proeth:EntityType")
        
        # Check each entity type
        for name, ns_type, proeth_type in entity_types:
            print(f"\nLooking for {name} entities:")
            
            # Check domain-specific namespace
            subjects = list(g.subjects(RDF.type, ns_type))
            print(f"  Found {len(subjects)} using domain namespace")
            if subjects:
                for s in subjects[:5]:  # Show first few
                    label = label_or_id(s)
                    print(f"    - {label} ({s})")
            
            # Check proethica namespace
            subjects = list(g.subjects(RDF.type, proeth_type))
            print(f"  Found {len(subjects)} using proethica namespace")
            if subjects:
                for s in subjects[:5]:  # Show first few
                    label = label_or_id(s)
                    print(f"    - {label} ({s})")
            
            # Check with literal URI strings
            domain_uri = URIRef(f"http://proethica.org/ontology/engineering-ethics#{name}")
            subjects = list(g.subjects(RDF.type, domain_uri))
            print(f"  Found {len(subjects)} using direct domain URI: {domain_uri}")
            
            proeth_uri = URIRef(f"http://proethica.org/ontology/intermediate#{name}")
            subjects = list(g.subjects(RDF.type, proeth_uri))
            print(f"  Found {len(subjects)} using direct proethica URI: {proeth_uri}")
        
        # Check for all rdf:type relations
        print("\nAll rdf:type relations:")
        types = {}
        for s, p, o in g.triples((None, RDF.type, None)):
            if o not in types:
                types[o] = []
            types[o].append(s)
        
        for type_uri, subjects in types.items():
            print(f"  {type_uri}: {len(subjects)} instances")
            # Print a few examples if it's a relevant type
            if str(type_uri).endswith(("#Role", "#ConditionType", "#ResourceType", "#EventType", "#ActionType", "#Capability", "#EntityType")):
                for s in subjects[:3]:
                    label = label_or_id(s)
                    print(f"    - {label} ({s})")
        
        # Check the a vs rdf:type issue
        print("\nCheck for 'a' vs 'rdf:type' syntax:")
        lines = ontology.content.split("\n")
        a_count = 0
        rdftype_count = 0
        for i, line in enumerate(lines):
            if " a " in line:
                a_count += 1
                if a_count <= 3:  # Show a few examples
                    print(f"  Line {i+1}: {line.strip()}")
            if "rdf:type" in line:
                rdftype_count += 1
                if rdftype_count <= 3:  # Show a few examples
                    print(f"  Line {i+1}: {line.strip()}")
        
        print(f"  Total 'a' usage: {a_count}")
        print(f"  Total 'rdf:type' usage: {rdftype_count}")
        
        print("\nConclusion:")
        if len(g) == 0:
            print("  The ontology does not contain any triples. This is likely why no entities are showing up.")
        elif entity_type_count == 0:
            print("  No instances of EntityType found. Check that your ontology uses proeth:EntityType correctly.")
        else:
            print("  The ontology appears to have valid triples and entity types.")
            print("  The issue may be with how the MCP server extracts these entities.")
            print("  Check mcp/http_ontology_mcp_server.py:_extract_entities method.")

if __name__ == "__main__":
    ontology_id = 1
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print(f"Using default ID: {ontology_id}")
    
    debug_entity_extraction(ontology_id)
