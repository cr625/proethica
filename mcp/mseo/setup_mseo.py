#!/usr/bin/env python3
"""
MSEO Setup Script.

This script downloads and sets up the Materials Science Engineering Ontology (MSEO)
for use with the MSEO MCP server.
"""

import os
import sys
import logging
import argparse
import tempfile
import time
import requests
from pathlib import Path
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import RDFlib for ontology validation
try:
    import rdflib
    from rdflib import Graph
    RDFLIB_AVAILABLE = True
except ImportError:
    logger.warning("RDFlib not available. Install with 'pip install rdflib' for ontology validation.")
    RDFLIB_AVAILABLE = False

def parse_args():
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Download and set up the MSEO ontology")
    
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Directory to save the ontology (default: mcp/mseo/data)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force download even if the ontology already exists"
    )
    
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate the ontology after download"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    return parser.parse_args()

def download_ontology(url, output_path, force=False):
    """Download the ontology from the given URL.
    
    Args:
        url: URL to download from
        output_path: Path to save the ontology
        force: Whether to force download even if the file exists
        
    Returns:
        True if successful, False otherwise
    """
    # Check if file already exists
    if os.path.exists(output_path) and not force:
        logger.info(f"Ontology file already exists at {output_path}. Use --force to download again.")
        return True
    
    # Create temp directory for download
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_file = os.path.join(temp_dir, "mseo.ttl")
        
        try:
            # Download the ontology
            logger.info(f"Downloading ontology from {url}")
            response = requests.get(url, stream=True)
            
            if response.status_code != 200:
                logger.error(f"Failed to download ontology: HTTP {response.status_code}")
                return False
            
            # Save to temp file
            with open(temp_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            # Move to final location
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Copy to final location
            with open(temp_file, "rb") as src, open(output_path, "wb") as dst:
                dst.write(src.read())
            
            logger.info(f"Downloaded ontology to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error downloading ontology: {e}")
            logger.error(traceback.format_exc())
            return False

def validate_ontology(file_path):
    """Validate the ontology file.
    
    Args:
        file_path: Path to the ontology file
        
    Returns:
        True if valid, False otherwise
    """
    if not RDFLIB_AVAILABLE:
        logger.warning("RDFlib not available. Skipping validation.")
        return True
    
    try:
        logger.info(f"Validating ontology at {file_path}")
        start_time = time.time()
        
        # Try to parse the ontology
        graph = Graph()
        graph.parse(file_path, format="ttl")
        
        # Count triples as basic validation
        triple_count = len(graph)
        
        # Log validation results
        logger.info(f"Ontology validated in {time.time() - start_time:.2f} seconds")
        logger.info(f"Ontology contains {triple_count} triples")
        
        return True
        
    except Exception as e:
        logger.error(f"Error validating ontology: {e}")
        logger.error(traceback.format_exc())
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Set output directory
    output_dir = args.output_dir
    if not output_dir:
        # Default to a data directory in the current module
        output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Set output file path
    output_path = os.path.join(output_dir, "MSEO.ttl")
    
    # Download the ontology
    url = "https://matportal.org/ontologies/MSEO.ttl"
    success = download_ontology(url, output_path, force=args.force)
    
    if not success:
        return 1
    
    # Validate the ontology if requested
    if args.validate:
        if not validate_ontology(output_path):
            return 1
    
    logger.info("MSEO ontology set up successfully")
    return 0

if __name__ == "__main__":
    sys.exit(main())
