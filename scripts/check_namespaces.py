#!/usr/bin/env python3
"""
Script to check the namespaces in ontology files.
This helps debug issues with MCP server namespace detection.
"""

import os
import sys
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

def check_ontology_namespaces(ontology_source):
    """Check namespaces in an ontology file."""
    # Load the ontology file
    ontology_dir = os.path.join('mcp', 'ontology')
    ontology_path = os.path.join(ontology_dir, ontology_source)
    
    if not os.path.exists(ontology_path):
        print(f"Error: Ontology file not found: {ontology_path}")
        return
    
    print(f"Analyzing ontology file: {ontology_path}")
    
    # Parse the ontology
    g = Graph()
    try:
        g.parse(ontology_path, format="turtle")
        print(f"Successfully loaded ontology with {len(g)} triples")
    except Exception as e:
        print(f"Error parsing ontology: {str(e)}")
        return
    
    # Print namespaces
    print("\nNamespaces:")
    for prefix, namespace in g.namespaces():
        print(f"  {prefix}: {namespace}")
    
    # Check for ontology type declarations
    print("\nOntology declarations:")
    for s, p, o in g.triples((None, RDF.type, OWL.Ontology)):
        print(f"  {s}")
        print(f"  Imports:")
        for _, _, imp in g.triples((s, OWL.imports, None)):
            print(f"    {imp}")
    
    # Check for classes with type designations
    rdf_type = URIRef('http://www.w3.org/1999/02/22-rdf-syntax-ns#type')
    
    # Define the ProEthica namespace
    PROETH = Namespace("http://proethica.org/ontology/intermediate#")
    
    # Check Role types
    print("\nRole types:")
    for s in g.subjects(rdf_type, PROETH.Role):
        label = next(g.objects(s, RDFS.label), s)
        print(f"  {s} ({label})")
    
    # Check ConditionType types  
    print("\nCondition types:")
    for s in g.subjects(rdf_type, PROETH.ConditionType):
        label = next(g.objects(s, RDFS.label), s)
        print(f"  {s} ({label})")
    
    # Check ResourceType types
    print("\nResource types:")
    for s in g.subjects(rdf_type, PROETH.ResourceType):
        label = next(g.objects(s, RDFS.label), s)
        print(f"  {s} ({label})")
    
    # Check EventType types
    print("\nEvent types:")
    for s in g.subjects(rdf_type, PROETH.EventType):
        label = next(g.objects(s, RDFS.label), s)
        print(f"  {s} ({label})")
    
    # Check ActionType types
    print("\nAction types:")
    for s in g.subjects(rdf_type, PROETH.ActionType):
        label = next(g.objects(s, RDFS.label), s)
        print(f"  {s} ({label})")
        
    # Find potential namespace conflicts
    potential_clashes = []
    for prefix, namespace in g.namespaces():
        if str(namespace).startswith('http://proethica.org/ontology/'):
            for other_prefix, other_namespace in g.namespaces():
                if prefix != other_prefix and str(other_namespace).startswith('http://proethica.org/ontology/'):
                    potential_clashes.append((prefix, namespace, other_prefix, other_namespace))
    
    if potential_clashes:
        print("\nWarning: Potential namespace conflicts detected:")
        for prefix, namespace, other_prefix, other_namespace in potential_clashes:
            print(f"  {prefix}: {namespace} and {other_prefix}: {other_namespace}")

def main():
    """Main function to check namespaces in ontology files."""
    # Process command line arguments
    if len(sys.argv) > 1:
        ontology_sources = sys.argv[1:]
    else:
        # Default ontologies to check
        ontology_sources = ["proethica-intermediate.ttl", "engineering-ethics.ttl"]
    
    # Check each ontology
    for ontology_source in ontology_sources:
        check_ontology_namespaces(ontology_source)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    main()
