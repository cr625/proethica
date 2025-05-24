#!/usr/bin/env python3
"""
Analyze BFO.ttl file to verify it's a valid Basic Formal Ontology representation
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from rdflib import Graph, Namespace, RDF, RDFS, OWL
from collections import defaultdict

def analyze_bfo(ttl_path):
    """Analyze BFO TTL file and report on its structure."""
    print(f"Analyzing BFO file: {ttl_path}")
    print("=" * 80)
    
    # Load the graph
    g = Graph()
    g.parse(ttl_path, format='turtle')
    
    # Define namespaces
    BFO = Namespace("http://purl.obolibrary.org/obo/BFO_")
    SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
    
    # Get ontology metadata
    ontology_uri = None
    for s in g.subjects(RDF.type, OWL.Ontology):
        ontology_uri = s
        print(f"Ontology URI: {s}")
        # Get version
        for version in g.objects(s, OWL.versionIRI):
            print(f"Version IRI: {version}")
        break
    
    print("\n" + "=" * 80)
    print("BFO CLASSES:")
    print("=" * 80)
    
    # Collect all classes
    classes = []
    class_labels = {}
    
    for class_uri in g.subjects(RDF.type, OWL.Class):
        if str(class_uri).startswith("http://purl.obolibrary.org/obo/BFO_"):
            classes.append(class_uri)
            # Get labels
            labels = list(g.objects(class_uri, RDFS.label))
            if labels:
                class_labels[class_uri] = str(labels[0])
    
    # Sort classes by their BFO ID
    classes.sort(key=lambda x: str(x))
    
    # Print core BFO hierarchy
    core_classes = {
        "BFO_0000001": "entity",
        "BFO_0000002": "continuant", 
        "BFO_0000003": "occurrent",
        "BFO_0000004": "independent continuant",
        "BFO_0000020": "specifically dependent continuant",
        "BFO_0000031": "generically dependent continuant",
        "BFO_0000015": "process",
        "BFO_0000035": "process boundary",
        "BFO_0000008": "temporal region",
        "BFO_0000011": "spatiotemporal region",
        "BFO_0000006": "spatial region",
        "BFO_0000040": "material entity",
        "BFO_0000030": "object",
        "BFO_0000024": "fiat object part",
        "BFO_0000027": "object aggregate",
        "BFO_0000019": "quality",
        "BFO_0000017": "realizable entity",
        "BFO_0000016": "disposition",
        "BFO_0000023": "role",
        "BFO_0000034": "function"
    }
    
    print("\nCore BFO Class Hierarchy:")
    for bfo_id, expected_label in core_classes.items():
        uri = f"http://purl.obolibrary.org/obo/{bfo_id}"
        actual_label = class_labels.get(Graph().resource(uri), "NOT FOUND")
        status = "✓" if actual_label.lower() == expected_label.lower() else "✗"
        print(f"  {status} {bfo_id}: {actual_label} (expected: {expected_label})")
    
    print(f"\nTotal BFO Classes: {len(classes)}")
    
    # Analyze object properties
    print("\n" + "=" * 80)
    print("BFO OBJECT PROPERTIES:")
    print("=" * 80)
    
    properties = []
    prop_labels = {}
    
    for prop_uri in g.subjects(RDF.type, OWL.ObjectProperty):
        if str(prop_uri).startswith("http://purl.obolibrary.org/obo/BFO_"):
            properties.append(prop_uri)
            labels = list(g.objects(prop_uri, RDFS.label))
            if labels:
                prop_labels[prop_uri] = str(labels[0])
    
    properties.sort(key=lambda x: str(x))
    
    # Core BFO relations
    core_relations = [
        "has part", "part of", "has participant", "participates in",
        "realizes", "has realization", "bearer of", "inheres in",
        "specifically depends on", "specifically depended on by",
        "generically depends on", "concretizes", "is concretized by",
        "precedes", "preceded by", "occurs in", "location of",
        "located in", "occupies spatial region", "occupies temporal region",
        "occupies spatiotemporal region"
    ]
    
    print("\nCore BFO Relations Found:")
    found_relations = set()
    for prop in properties:
        label = prop_labels.get(prop, "")
        if label:
            found_relations.add(label)
            if label in core_relations:
                print(f"  ✓ {label}")
    
    print(f"\nTotal BFO Object Properties: {len(properties)}")
    
    # Check for missing core relations
    missing = set(core_relations) - found_relations
    if missing:
        print("\nMissing Core Relations:")
        for rel in missing:
            print(f"  ✗ {rel}")
    
    # Summary statistics
    print("\n" + "=" * 80)
    print("SUMMARY:")
    print("=" * 80)
    print(f"Total triples: {len(g)}")
    print(f"Total BFO classes: {len(classes)}")
    print(f"Total BFO object properties: {len(properties)}")
    
    # Determine BFO version
    if "BFO 2020" in str(g.serialize(format='turtle')):
        print("BFO Version: BFO 2020")
    elif "BFO 2.0" in str(g.serialize(format='turtle')):
        print("BFO Version: BFO 2.0")
    else:
        print("BFO Version: Unknown")
    
    return len(classes) > 30 and len(properties) > 20  # Basic validity check

if __name__ == "__main__":
    ttl_path = "ontologies/bfo.ttl"
    is_valid = analyze_bfo(ttl_path)
    print(f"\nIs valid BFO: {'Yes' if is_valid else 'No'}")