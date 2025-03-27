#!/usr/bin/env python3
import os
import sys
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

# Backup the original file
original_file = 'app/routes/mcp_api.py'
backup_file = 'app/routes/mcp_api.py.bak'

if not os.path.exists(backup_file):
    with open(original_file, 'r') as f:
        original_content = f.read()
    
    with open(backup_file, 'w') as f:
        f.write(original_content)
    
    print(f"Created backup of original file at {backup_file}")

# Read the current file
with open(original_file, 'r') as f:
    content = f.read()

# Update the namespace mapping for tccc.ttl
updated_content = content.replace(
    """        # Define known namespaces
        namespaces = {
            "military-medical-triage": Namespace("http://proethica.org/ontology/military-medical-triage#"),
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://proethica.org/ontology/nj-legal-ethics#"),
            "tccc": Namespace("http://proethica.org/ontology/tccc#")
        }""",
    
    """        # Define known namespaces
        namespaces = {
            "military-medical-triage": Namespace("http://proethica.org/ontology/military-medical-triage#"),
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://proethica.org/ontology/nj-legal-ethics#"),
            "tccc": Namespace("http://proethica.org/ontology/military-medical-triage#")  # Use military-medical-triage namespace for tccc.ttl
        }"""
)

# Write the updated content back to the file
with open(original_file, 'w') as f:
    f.write(updated_content)

print(f"Updated {original_file} with correct namespace mapping for tccc.ttl")
