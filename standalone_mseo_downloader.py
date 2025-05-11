#!/usr/bin/env python3
"""
Standalone MSEO Downloader

This script downloads the MSEO ontology from matportal.org and converts it to Turtle format
without depending on any other modules from the project. It's a standalone solution for
getting the MSEO ontology into the system.
"""

import os
import sys
import requests
import logging
from urllib.parse import urlparse
import rdflib
from rdflib import Graph, Namespace, URIRef

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MSEO_URL = "http://rest.matportal.org/ontologies/MSEO/submissions/23/download?apikey=66c82e77-ce0d-4385-8056-a95898e47ebb"
OUTPUT_DIR = "mcp/mseo/data"

class StandaloneMSEOConverter:
    """Standalone converter for MSEO ontology."""
    
    def __init__(self):
        """Initialize the converter."""
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
        """Convert ontology from input format to Turtle."""
        try:
            logger.info(f"Converting {input_file} to {output_file}...")
            
            # Create a new RDF graph
            g = Graph()
            
            # Register namespaces
            for prefix, namespace in self.namespaces.items():
                g.bind(prefix, namespace)
            
            # Parse the input file
            input_format = self._guess_format(input_file)
            g.parse(input_file, format=input_format)
            
            # Apply any needed transformations to the graph
            self._transform_graph(g)
            
            # Serialize to Turtle format
            g.serialize(destination=output_file, format="turtle")
            
            logger.info(f"Conversion complete. Ontology saved to {output_file}")
            logger.info(f"Converted ontology contains {len(g)} triples")
            
            return True
        
        except Exception as e:
            logger.error(f"Error converting ontology: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def _guess_format(self, file_path):
        """Guess the RDF format based on file extension."""
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
        """Apply transformations to the graph if needed."""
        # Check for MSEO namespace
        found_mseo = False
        for ns_prefix, ns_uri in g.namespaces():
            if str(ns_uri).startswith("http://matportal.org/ontologies/MSEO"):
                found_mseo = True
                # Update our namespace to match the actual one
                self.mseo = Namespace(str(ns_uri))
                break
        
        if not found_mseo:
            logger.warning("MSEO namespace not found in the ontology")

def download_ontology(url, output_dir):
    """Download the MSEO ontology from the specified URL."""
    logger.info(f"Downloading MSEO ontology from {url}...")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Determine filename from URL
    url_path = urlparse(url).path
    filename = os.path.basename(url_path) or "mseo.owl"
    if not any(filename.endswith(ext) for ext in ['.owl', '.rdf', '.xml']):
        filename += ".owl"
    
    output_path = os.path.join(output_dir, filename)
    
    try:
        # Send request with timeout
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Save the ontology file
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Successfully downloaded ontology to {output_path}")
        return output_path
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading ontology: {str(e)}")
        raise

def analyze_ontology(ttl_path):
    """Analyze the ontology and print some statistics."""
    logger.info(f"Analyzing ontology at {ttl_path}...")
    
    try:
        # Create a new RDF graph
        g = Graph()
        
        # Parse the Turtle file
        g.parse(ttl_path, format="turtle")
        
        # Print basic stats
        logger.info(f"Ontology contains {len(g)} triples")
        
        # Count by entity type
        mseo = Namespace("http://matportal.org/ontologies/MSEO#")
        entity_counts = {
            'Materials': 0,
            'Properties': 0,
            'Processes': 0,
            'Structures': 0
        }
        
        # Count materials
        materials = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, mseo.Material)):
            materials.add(s)
        entity_counts['Materials'] = len(materials)
        
        # Count properties
        properties = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, mseo.Property)):
            properties.add(s)
        entity_counts['Properties'] = len(properties)
        
        # Count processes
        processes = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, mseo.Process)):
            processes.add(s)
        entity_counts['Processes'] = len(processes)
        
        # Count structures
        structures = set()
        for s, p, o in g.triples((None, rdflib.RDF.type, mseo.Structure)):
            structures.add(s)
        entity_counts['Structures'] = len(structures)
        
        # Print entity counts
        for entity_type, count in entity_counts.items():
            logger.info(f"  - {entity_type}: {count}")
        
        return entity_counts
        
    except Exception as e:
        logger.error(f"Error analyzing ontology: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    """Main function."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Download the ontology
        input_path = download_ontology(MSEO_URL, OUTPUT_DIR)
        
        # Convert the ontology to Turtle format
        converter = StandaloneMSEOConverter()
        output_path = os.path.splitext(input_path)[0] + ".ttl"
        success = converter.convert(input_path, output_path)
        
        if success:
            logger.info("MSEO setup completed successfully")
            logger.info(f"Downloaded file: {input_path}")
            logger.info(f"Converted file: {output_path}")
            
            # Analyze the converted ontology
            analyze_ontology(output_path)
            
            return 0
        else:
            logger.error("Conversion failed")
            return 1
    
    except Exception as e:
        logger.error(f"MSEO setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
