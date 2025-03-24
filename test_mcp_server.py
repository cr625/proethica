#!/usr/bin/env python3
import os
import sys
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

# Import the OntologyMCPServer class from the ontology_mcp_server.py file
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from mcp.ontology_mcp_server import OntologyMCPServer

def test_extract_entities():
    # Create an instance of the OntologyMCPServer
    server = OntologyMCPServer()
    
    # Load the tccc.ttl file
    ontology_file = "tccc.ttl"
    graph = server._load_graph_from_file(ontology_file)
    
    # Print the number of triples in the graph
    print(f"Loaded {len(graph)} triples from {ontology_file}")
    
    # Print the namespaces in the graph
    print("\nNamespaces in the graph:")
    for prefix, namespace in graph.namespaces():
        print(f"  {prefix}: {namespace}")
    
    # Detect the namespace
    namespace = server._detect_namespace(graph)
    print(f"\nDetected namespace: {namespace}")
    
    # Extract entities
    entities = server._extract_entities(graph, "all")
    
    # Print the entities
    print("\nExtracted entities:")
    for entity_type, entity_list in entities.items():
        print(f"\n{entity_type.capitalize()} ({len(entity_list)}):")
        for entity in entity_list:
            print(f"  - {entity.get('label')} ({entity.get('id')})")
    
    return entities

if __name__ == "__main__":
    entities = test_extract_entities()
    
    # Check if any entities were extracted
    if not entities:
        print("\nNo entities were extracted!")
    else:
        total_entities = sum(len(entity_list) for entity_list in entities.values())
        print(f"\nTotal entities extracted: {total_entities}")
