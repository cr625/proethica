#!/usr/bin/env python3
"""
Script to validate the syntax of an ontology and provide detailed error information.
"""

import sys
import os
import re

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph
from rdflib.exceptions import ParserError

def validate_ontology_syntax(ontology_id):
    """Validate the syntax of an ontology with the given ID."""
    app = create_app()
    
    with app.app_context():
        # Get the ontology from the database
        ontology = Ontology.query.get(ontology_id)
        
        if not ontology:
            print(f"No ontology found with ID {ontology_id}")
            return
        
        print(f"Found ontology: ID={ontology.id}, Name={ontology.name}, Domain={ontology.domain_id}")
        print(f"Content length: {len(ontology.content) if ontology.content else 0} characters")
        print("\nValidating syntax...")
        
        if not ontology.content:
            print("Error: Ontology content is empty")
            return
        
        # Validate the ontology using RDFLib
        g = Graph()
        try:
            g.parse(data=ontology.content, format='turtle')
            print("Syntax validation successful! The ontology is valid.")
            print(f"Graph contains {len(g)} statements.")
            
            # Print some statistics about the ontology
            namespaces = list(g.namespaces())
            print(f"\nNamespaces ({len(namespaces)}):")
            for prefix, uri in namespaces:
                print(f"  {prefix}: {uri}")
            
        except ParserError as e:
            print("Syntax validation failed!")
            error_message = str(e)
            print(f"\nError details: {error_message}")
            
            # Try to extract line number from error message
            line_match = re.search(r'line (\d+)', error_message)
            if line_match:
                line_number = int(line_match.group(1))
                print(f"\nError around line {line_number}:")
                
                # Display the problematic lines with context
                lines = ontology.content.split('\n')
                start_line = max(0, line_number - 5)
                end_line = min(len(lines), line_number + 5)
                
                for i in range(start_line, end_line):
                    prefix = ">>>" if i + 1 == line_number else "   "
                    print(f"{prefix} Line {i+1}: {lines[i]}")
            
        except Exception as e:
            print(f"Error during validation: {str(e)}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        ontology_id = int(sys.argv[1])
    else:
        ontology_id = 1  # Default to ID 1
    
    validate_ontology_syntax(ontology_id)
