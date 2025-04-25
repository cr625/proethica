#!/usr/bin/env python3
"""
Analyze ontology structure to help debug visualization issues.

This script analyzes the structure of an ontology from the database and
prints information about its classes, hierarchy, and other important elements.
"""

import sys
import os

# Add the parent directory to the path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, URIRef, RDF, RDFS, OWL

def analyze_ontology(ontology_id):
    """Analyze the structure of an ontology."""
    # Create Flask app context
    app = create_app()
    with app.app_context():
        # Get ontology from database
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            print(f"Ontology with ID {ontology_id} not found.")
            return
        
        print(f"\nAnalyzing ontology: {ontology.name} (ID={ontology_id})")
        
        # Parse TTL content
        g = Graph()
        g.parse(data=ontology.content, format='turtle')
        
        # Print namespaces
        print("\nNamespaces:")
        for prefix, namespace in g.namespaces():
            print(f"  {prefix}: {namespace}")
        
        # Print all classes
        print("\nAll classes defined in the ontology:")
        classes = []
        for s, p, o in g.triples((None, RDF.type, OWL.Class)):
            uri_str = str(s)
            label = None
            for _, _, lbl in g.triples((URIRef(uri_str), RDFS.label, None)):
                label = str(lbl)
                break
            
            if not label:
                if '#' in uri_str:
                    label = uri_str.split('#')[-1]
                else:
                    label = uri_str.split('/')[-1]
            
            classes.append((label, uri_str))
        
        for label, uri in sorted(classes):
            print(f"  {label} - {uri}")
        
        # Print class hierarchy
        print("\nClass hierarchy (based on rdfs:subClassOf):")
        hierarchy = {}
        for s, p, o in g.triples((None, RDFS.subClassOf, None)):
            if isinstance(o, URIRef):
                child_uri = str(s)
                parent_uri = str(o)
                
                if parent_uri not in hierarchy:
                    hierarchy[parent_uri] = []
                
                hierarchy[parent_uri].append(child_uri)
        
        # Find top-level classes (those with no parents)
        all_children = set()
        for children in hierarchy.values():
            all_children.update(children)
        
        all_class_uris = set(uri for _, uri in classes)
        top_level = all_class_uris - all_children
        
        print("\nTop-level classes:")
        for uri in top_level:
            label = None
            for _, _, lbl in g.triples((URIRef(uri), RDFS.label, None)):
                label = str(lbl)
                break
            
            if not label:
                if '#' in uri:
                    label = uri.split('#')[-1]
                else:
                    label = uri.split('/')[-1]
            
            print(f"  {label} - {uri}")
            
            # Print immediate children
            if uri in hierarchy:
                for child_uri in hierarchy[uri]:
                    child_label = None
                    for _, _, lbl in g.triples((URIRef(child_uri), RDFS.label, None)):
                        child_label = str(lbl)
                        break
                    
                    if not child_label:
                        if '#' in child_uri:
                            child_label = child_uri.split('#')[-1]
                        else:
                            child_label = child_uri.split('/')[-1]
                    
                    print(f"    └─ {child_label} - {child_uri}")
        
        # Specifically look for the standard top-level classes
        print("\nLooking for standard top-level classes:")
        class_types = ['Role', 'Event', 'Condition', 'Action', 'Resource']
        
        for class_type in class_types:
            found = False
            
            # Look for classes with matching labels
            for s, _, o in g.triples((None, RDFS.label, None)):
                if str(o) == class_type and (s, RDF.type, OWL.Class) in g:
                    print(f"  Found {class_type} by label: {s}")
                    found = True
                    
                    # Show subclasses
                    print("    Subclasses:")
                    has_subclasses = False
                    for subclass, _, _ in g.triples((None, RDFS.subClassOf, s)):
                        has_subclasses = True
                        subclass_label = None
                        for _, _, lbl in g.triples((subclass, RDFS.label, None)):
                            subclass_label = str(lbl)
                            break
                        print(f"      - {subclass_label or subclass}")
                    
                    if not has_subclasses:
                        print("      (none)")
                    
                    break
            
            # If not found by label, look by URI pattern
            if not found:
                for s, p, o in g.triples((None, RDF.type, OWL.Class)):
                    uri_str = str(s)
                    if uri_str.endswith(f"#{class_type}") or uri_str.endswith(f"/{class_type}"):
                        print(f"  Found {class_type} by URI pattern: {uri_str}")
                        found = True
                        break
            
            if not found:
                print(f"  {class_type} not found in the ontology")

if __name__ == "__main__":
    # Check arguments
    if len(sys.argv) < 2:
        print("Usage: python analyze_ontology.py <ontology_id>")
        sys.exit(1)
    
    # Run the analysis
    analyze_ontology(sys.argv[1])
