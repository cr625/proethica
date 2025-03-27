#!/usr/bin/env python3
import os
import sys
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

# Backup the original file
original_file = 'mcp/ontology_mcp_server.py'
backup_file = 'mcp/ontology_mcp_server.py.bak'

if not os.path.exists(backup_file):
    with open(original_file, 'r') as f:
        original_content = f.read()
    
    with open(backup_file, 'w') as f:
        f.write(original_content)
    
    print(f"Created backup of original file at {backup_file}")

# Read the current file
with open(original_file, 'r') as f:
    content = f.read()

# Update the _detect_namespace method to better handle the tccc.ttl file
updated_content = content.replace(
    """    def _detect_namespace(self, graph):
        \"\"\"Detect the primary namespace used in the ontology.\"\"\"
        # Try to find the ontology declaration
        for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
            ontology_uri = str(s)
            if "military-medical-triage" in ontology_uri:
                return self.namespaces["military-medical-triage"]
            elif "engineering-ethics" in ontology_uri:
                return self.namespaces["engineering-ethics"]
            elif "nj-legal-ethics" in ontology_uri:
                return self.namespaces["nj-legal-ethics"]

        # Check for namespace prefixes in the graph
        for prefix, namespace in graph.namespaces():
            namespace_str = str(namespace)
            if prefix == "mmt" or "military-medical-triage" in namespace_str:
                return self.namespaces["military-medical-triage"]
            elif prefix == "eng" or "engineering-ethics" in namespace_str:
                return self.namespaces["engineering-ethics"]
            elif prefix == "njle" or "nj-legal-ethics" in namespace_str:
                return self.namespaces["nj-legal-ethics"]

        # Check for common entity types in each namespace
        for namespace_key, namespace in self.namespaces.items():
            # Check if any entities with this namespace's Role type exist
            if any(graph.subjects(RDF.type, namespace.Role)):
                return namespace

        # Default to MMT if not found
        return self.MMT""",
    
    """    def _detect_namespace(self, graph):
        \"\"\"Detect the primary namespace used in the ontology.\"\"\"
        # Try to find the ontology declaration
        for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
            ontology_uri = str(s)
            print(f"Found ontology URI: {ontology_uri}", file=sys.stderr)
            if "military-medical-triage" in ontology_uri:
                print(f"Detected military-medical-triage namespace from ontology URI", file=sys.stderr)
                return self.namespaces["military-medical-triage"]
            elif "engineering-ethics" in ontology_uri:
                print(f"Detected engineering-ethics namespace from ontology URI", file=sys.stderr)
                return self.namespaces["engineering-ethics"]
            elif "nj-legal-ethics" in ontology_uri:
                print(f"Detected nj-legal-ethics namespace from ontology URI", file=sys.stderr)
                return self.namespaces["nj-legal-ethics"]

        # Check for namespace prefixes in the graph
        print(f"Checking namespace prefixes in the graph", file=sys.stderr)
        for prefix, namespace in graph.namespaces():
            namespace_str = str(namespace)
            print(f"Found prefix: {prefix}, namespace: {namespace_str}", file=sys.stderr)
            if prefix == "mmt" or "military-medical-triage" in namespace_str:
                print(f"Detected military-medical-triage namespace from prefix", file=sys.stderr)
                return self.namespaces["military-medical-triage"]
            elif prefix == "eng" or "engineering-ethics" in namespace_str:
                print(f"Detected engineering-ethics namespace from prefix", file=sys.stderr)
                return self.namespaces["engineering-ethics"]
            elif prefix == "njle" or "nj-legal-ethics" in namespace_str:
                print(f"Detected nj-legal-ethics namespace from prefix", file=sys.stderr)
                return self.namespaces["nj-legal-ethics"]

        # Special case for tccc.ttl which uses the military-medical-triage namespace
        print(f"Checking for special case for tccc.ttl", file=sys.stderr)
        for s, p, o in graph.triples((None, RDF.type, None)):
            if "military-medical-triage" in str(o):
                print(f"Detected military-medical-triage namespace from type", file=sys.stderr)
                return self.namespaces["military-medical-triage"]

        # Check for common entity types in each namespace
        print(f"Checking for common entity types in each namespace", file=sys.stderr)
        for namespace_key, namespace in self.namespaces.items():
            # Check if any entities with this namespace's Role type exist
            if any(graph.subjects(RDF.type, namespace.Role)):
                print(f"Detected {namespace_key} namespace from Role type", file=sys.stderr)
                return namespace

        # Default to MMT if not found
        print(f"Defaulting to MMT namespace", file=sys.stderr)
        return self.MMT"""
)

# Write the updated content back to the file
with open(original_file, 'w') as f:
    f.write(updated_content)

print(f"Updated {original_file} with improved namespace detection logic")
