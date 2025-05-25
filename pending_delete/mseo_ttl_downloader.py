#!/usr/bin/env python3
"""
MSEO TTL Downloader

This script downloads the MSEO ontology directly in Turtle format
and analyzes its structure.
"""

import os
import sys
import requests
import logging
import rdflib
from rdflib import Graph, Namespace

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MSEO_URL = "http://rest.matportal.org/ontologies/MSEO/submissions/23/download?apikey=66c82e77-ce0d-4385-8056-a95898e47ebb"
OUTPUT_DIR = "mcp/mseo/data"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "mseo.ttl")

def download_ttl(url, output_path):
    """Download the MSEO ontology in Turtle format."""
    logger.info(f"Downloading MSEO ontology from {url}...")
    
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    try:
        # Send request with timeout
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        # Check if the content appears to be Turtle
        content = response.text
        if content.strip().startswith('@prefix') or content.strip().startswith('@base'):
            # Save the ontology file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"Successfully downloaded ontology to {output_path}")
            return True
        else:
            logger.error("Downloaded content does not appear to be in Turtle format")
            with open(output_path + ".error", 'w', encoding='utf-8') as f:
                f.write(content)
            return False
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading ontology: {str(e)}")
        return False

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
        
        # Find and print all namespaces
        logger.info("Namespaces in the ontology:")
        for prefix, uri in g.namespaces():
            logger.info(f"  - {prefix}: {uri}")
        
        # Find MSEO namespace
        mseo_namespace = None
        for prefix, uri in g.namespaces():
            if str(uri).startswith("https://purl.matolab.org/mseo"):
                mseo_namespace = uri
                logger.info(f"Found MSEO namespace: {uri}")
                break
        
        if not mseo_namespace:
            logger.warning("Could not find MSEO namespace")
            return {}
        
        # Define common class names in materials science
        mseo = Namespace(mseo_namespace)
        classes_to_check = [
            ('Material', 'Materials'),
            ('Property', 'Properties'),
            ('Process', 'Processes'),
            ('Structure', 'Structures'),
            ('Characterization', 'Characterizations'),
            ('Element', 'Elements'),
            ('ApplicationArea', 'Application Areas')
        ]
        
        # Count instances of each class
        entity_counts = {}
        for class_name, display_name in classes_to_check:
            # Try with MSEO namespace
            class_uri = mseo[class_name]
            instances = set(g.subjects(rdflib.RDF.type, class_uri))
            
            # Also try with OWL namespace format
            owl_class_uri = rdflib.URIRef(str(mseo_namespace) + '#' + class_name)
            instances.update(g.subjects(rdflib.RDF.type, owl_class_uri))
            
            entity_counts[display_name] = len(instances)
        
        # Print entity counts
        for entity_type, count in entity_counts.items():
            logger.info(f"  - {entity_type}: {count}")
        
        # Find top-level classes
        logger.info("Top level classes:")
        top_classes = set()
        for subj, pred, obj in g.triples((None, rdflib.RDF.type, rdflib.OWL.Class)):
            # If it doesn't have a superclass, it's a top-level class
            if not list(g.triples((subj, rdflib.RDFS.subClassOf, None))):
                top_classes.add(subj)
            # Or if its only superclass is owl:Thing or another built-in
            has_real_superclass = False
            for _, _, superclass in g.triples((subj, rdflib.RDFS.subClassOf, None)):
                if not str(superclass).startswith('http://www.w3.org/'):
                    has_real_superclass = True
                    break
            if not has_real_superclass:
                top_classes.add(subj)
        
        # Print top-level classes
        for cls in sorted(top_classes, key=str):
            label = next(g.objects(cls, rdflib.RDFS.label), None)
            if label:
                logger.info(f"  - {cls} ({label})")
            else:
                logger.info(f"  - {cls}")
        
        return entity_counts
        
    except Exception as e:
        logger.error(f"Error analyzing ontology: {str(e)}")
        import traceback
        traceback.print_exc()
        return {}

def main():
    """Main function."""
    try:
        # Download the ontology in Turtle format
        success = download_ttl(MSEO_URL, OUTPUT_PATH)
        
        if success:
            # Analyze the ontology
            analyze_ontology(OUTPUT_PATH)
            
            logger.info("MSEO setup completed successfully")
            logger.info(f"Ontology file saved to: {OUTPUT_PATH}")
            return 0
        else:
            logger.error("Failed to download ontology in Turtle format")
            return 1
    
    except Exception as e:
        logger.error(f"MSEO setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
