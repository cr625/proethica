#!/usr/bin/env python3
"""
Script to debug the RDF parsing in the MCP server.
"""
from rdflib import Graph, Namespace, RDF, RDFS
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import from app
from app import create_app, db
from app.models.ontology import Ontology

def debug_ontology_parsing():
    print("Debugging ontology parsing for MCP server")
    
    app = create_app()
    with app.app_context():
        # Get the ontology with ID 1
        ontology = Ontology.query.get(1)
        if not ontology:
            print("Ontology with ID 1 not found!")
            return
            
        print(f"Ontology: {ontology.name}")
        print(f"Domain ID: {ontology.domain_id}")
        print(f"Content length: {len(ontology.content) if ontology.content else 'None'}")
        
        # Create a graph
        g = Graph()
        try:
            g.parse(data=ontology.content, format="turtle")
            print(f"Successfully parsed ontology content into RDF graph")
            print(f"Graph has {len(g)} triples")
            
            # Define namespaces
            namespaces = {
                "engineering-ethics-nspe-extended": Namespace("http://proethica.org/ontology/engineering-ethics-nspe-extended#"),
                "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
                "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#")
            }
            eng_ns = namespaces["engineering-ethics-nspe-extended"]
            proeth_ns = namespaces["intermediate"]
            
            # Function to get label or id
            def label_or_id(s):
                return str(next(g.objects(s, RDFS.label), s))
            
            # Check entity types
            entity_types = ["Role", "ConditionType", "ResourceType", "EventType", "ActionType", "Capability"]
            for entity_type in entity_types:
                # Check with engineering namespace
                subjects = list(g.subjects(RDF.type, getattr(eng_ns, entity_type)))
                print(f"Found {len(subjects)} {entity_type} subjects using engineering namespace")
                if subjects:
                    for s in subjects[:3]:  # Show first few
                        print(f"  - {label_or_id(s)}")
                
                # Check with proethica namespace
                subjects = list(g.subjects(RDF.type, getattr(proeth_ns, entity_type)))
                print(f"Found {len(subjects)} {entity_type} subjects using proethica namespace")
                if subjects:
                    for s in subjects[:3]:  # Show first few
                        print(f"  - {label_or_id(s)}")
            
            # List all namespaces in graph
            print("\nNamespaces in graph:")
            for prefix, namespace in g.namespaces():
                print(f"{prefix}: {namespace}")
                
            # Find all rdf:type triples
            print("\nAll rdf:type statements:")
            types = {}
            for s, p, o in g.triples((None, RDF.type, None)):
                if o not in types:
                    types[o] = 0
                types[o] += 1
            
            for type_uri, count in types.items():
                print(f"{type_uri}: {count} instances")
            
        except Exception as e:
            print(f"Error parsing ontology content: {str(e)}")
            # Print the first 500 characters of content for debugging
            if ontology.content:
                print("Content preview:")
                print(ontology.content[:500])

if __name__ == "__main__":
    debug_ontology_parsing()
