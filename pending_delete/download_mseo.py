#!/usr/bin/env python3
"""
Download MSEO Ontology

This script downloads the MSEO ontology and converts it to Turtle format.
"""

import os
import requests
import logging
from urllib.parse import urlparse
from mcp.mseo.mseo_converter import MSEOConverter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MSEO_URL = "https://matportal.org/ontologies/MSEO"
OUTPUT_DIR = "mcp/mseo/data"

def download_ontology(url, output_dir):
    """Download the MSEO ontology."""
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

def convert_ontology(input_path, output_dir):
    """Convert the ontology to Turtle format."""
    logger.info(f"Converting ontology from {input_path} to Turtle format...")
    
    # Determine output filename
    output_filename = os.path.splitext(os.path.basename(input_path))[0] + ".ttl"
    output_path = os.path.join(output_dir, output_filename)
    
    # Create converter and convert the file
    converter = MSEOConverter()
    success = converter.convert(input_path, output_path)
    
    if success:
        logger.info(f"Successfully converted ontology to {output_path}")
        return output_path
    else:
        logger.error("Conversion failed")
        raise Exception("Conversion failed")

def main():
    """Main function."""
    try:
        # Download the ontology
        input_path = download_ontology(MSEO_URL, OUTPUT_DIR)
        
        # Convert the ontology
        ttl_path = convert_ontology(input_path, OUTPUT_DIR)
        
        logger.info("MSEO setup completed successfully")
        logger.info(f"Downloaded file: {input_path}")
        logger.info(f"Converted file: {ttl_path}")
        return 0
    
    except Exception as e:
        logger.error(f"MSEO setup failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    main()
