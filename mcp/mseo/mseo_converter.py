#!/usr/bin/env python3
"""
MSEO Converter

This module converts the MSEO ontology from its native format (likely OWL or RDF/XML)
to Turtle (TTL) format for easier integration with the MCP server infrastructure.
"""

import argparse
import os
import sys
import rdflib
from rdflib import Graph, Namespace, URIRef

class MSEOConverter:
    """
    Converter for the Materials Science Engineering Ontology (MSEO).
    
    This class handles the conversion of the MSEO ontology from its original format
    to Turtle (TTL) format with appropriate namespace mappings and transformations.
    """
    
    def __init__(self):
        """Initialize the MSEO converter."""
        # Define MSEO and related namespaces
        self.mseo = Namespace("http://matportal.org/ontologies/MSEO#")
        self.namespaces = {
            "mseo": self.mseo,
            "rdf": rdflib.RDF,
            "rdfs": rdflib.RDFS,
            "owl": rdflib.OWL,
            "xsd": rdflib.XSD,
        }
    
    def convert(self, input_file, output_file):
        """
        Convert the MSEO ontology from input format to Turtle format.
        
        Args:
            input_file: Path to the input ontology file
            output_file: Path where the converted TTL file will be saved
            
        Returns:
            bool: True if conversion was successful, False otherwise
        """
        try:
            print(f"Converting {input_file} to {output_file}...")
            
            # Create a new RDF graph
            g = Graph()
            
            # Register namespaces
            for prefix, namespace in self.namespaces.items():
                g.bind(prefix, namespace)
            
            # Parse the input file
            # The format parameter will be determined from the file extension
            input_format = self._guess_format(input_file)
            g.parse(input_file, format=input_format)
            
            # Apply any needed transformations to the graph
            self._transform_graph(g)
            
            # Serialize to Turtle format
            g.serialize(destination=output_file, format="turtle")
            
            print(f"Conversion complete. Ontology saved to {output_file}")
            
            # Print some statistics
            print(f"Converted ontology contains {len(g)} triples")
            
            return True
        
        except Exception as e:
            print(f"Error converting ontology: {str(e)}", file=sys.stderr)
            import traceback
            traceback.print_exc()
            return False
    
    def _guess_format(self, file_path):
        """
        Guess the RDF format based on file extension.
        
        Args:
            file_path: Path to the ontology file
            
        Returns:
            str: RDF format string recognized by rdflib
        """
        extension = os.path.splitext(file_path)[1].lower()
        
        format_map = {
            '.owl': 'xml',
            '.rdf': 'xml',
            '.xml': 'xml',
            '.ttl': 'turtle',
            '.n3': 'n3',
            '.nt': 'nt',
            '.jsonld': 'json-ld'
        }
        
        return format_map.get(extension, 'xml')  # Default to XML if unknown
    
    def _transform_graph(self, g):
        """
        Apply transformations to the graph if needed.
        
        This method can be extended to handle specific transformations needed for MSEO.
        
        Args:
            g: RDFLib Graph object to transform
        """
        # Check for MSEO namespace
        found_mseo = False
        for ns_prefix, ns_uri in g.namespaces():
            if str(ns_uri).startswith("http://matportal.org/ontologies/MSEO"):
                found_mseo = True
                # Update our namespace to match the actual one
                self.mseo = Namespace(str(ns_uri))
                break
        
        if not found_mseo:
            print("Warning: MSEO namespace not found in the ontology", file=sys.stderr)

def main():
    """Main function for command-line interface."""
    parser = argparse.ArgumentParser(description='Convert MSEO ontology to Turtle format')
    parser.add_argument('--input', '-i', required=True, help='Path to input ontology file')
    parser.add_argument('--output', '-o', required=True, help='Path for output Turtle file')
    
    args = parser.parse_args()
    
    converter = MSEOConverter()
    success = converter.convert(args.input, args.output)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
