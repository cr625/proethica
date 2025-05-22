#!/usr/bin/env python3
"""
Test script for the OntologyTripleLoader class.

This script tests loading and processing ontology files with the OntologyTripleLoader.
"""

import os
import sys
import logging
import json
from typing import Dict, List, Any

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ttl_triple_association.ontology_triple_loader import OntologyTripleLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ontology_loading():
    """Test loading the ontology files."""
    logger.info("Testing ontology loading...")
    
    # Initialize with default ontology files
    loader = OntologyTripleLoader()
    
    try:
        # Load ontology
        loader.load()
        
        # Log basic statistics
        logger.info(f"Total concepts: {len(loader.concepts)}")
        logger.info(f"Role concepts: {len(loader.role_concepts)}")
        logger.info(f"Role-related concepts: {len(loader.role_related_concepts)}")
        logger.info(f"Principle concepts: {len(loader.principle_concepts)}")
        
        # Test successful
        logger.info("Ontology loading test successful")
        return True
    except Exception as e:
        logger.error(f"Error loading ontology: {e}")
        return False

def examine_concept_text():
    """Test the text representation of concepts for embedding."""
    logger.info("Examining concept text for embedding...")
    
    # Initialize and load ontology
    loader = OntologyTripleLoader()
    loader.load()
    
    # Get sample concepts
    role_concept = next(iter(loader.role_concepts.keys())) if loader.role_concepts else None
    principle_concept = next(iter(loader.principle_concepts.keys())) if loader.principle_concepts else None
    
    if role_concept:
        # Get text representation
        text = loader.get_concept_text_for_embedding(role_concept)
        logger.info(f"\nRole concept text example:\nURI: {role_concept}\nText: {text[:200]}...")
    
    if principle_concept:
        # Get text representation
        text = loader.get_concept_text_for_embedding(principle_concept)
        logger.info(f"\nPrinciple concept text example:\nURI: {principle_concept}\nText: {text[:200]}...")
    
    return True

def export_sample_concepts(output_file: str = "sample_concepts.json"):
    """Export sample concepts to a JSON file for inspection."""
    logger.info(f"Exporting sample concepts to {output_file}...")
    
    # Initialize and load ontology
    loader = OntologyTripleLoader()
    loader.load()
    
    # Get sample concepts (2 of each type)
    sample_concepts = {}
    
    # Get role concepts
    role_keys = list(loader.role_concepts.keys())[:2]
    for key in role_keys:
        sample_concepts[key] = {
            "type": "role",
            "data": loader.concepts[key],
            "embedding_text": loader.get_concept_text_for_embedding(key)
        }
    
    # Get role-related concepts
    role_related_keys = list(loader.role_related_concepts.keys())[:2]
    for key in role_related_keys:
        if key not in sample_concepts:
            sample_concepts[key] = {
                "type": "role_related",
                "data": loader.concepts[key],
                "embedding_text": loader.get_concept_text_for_embedding(key)
            }
    
    # Get principle concepts
    principle_keys = list(loader.principle_concepts.keys())[:2]
    for key in principle_keys:
        if key not in sample_concepts:
            sample_concepts[key] = {
                "type": "principle",
                "data": loader.concepts[key],
                "embedding_text": loader.get_concept_text_for_embedding(key)
            }
    
    # Save to JSON file
    try:
        with open(output_file, 'w') as f:
            json.dump(sample_concepts, f, indent=2)
        logger.info(f"Exported {len(sample_concepts)} sample concepts to {output_file}")
        return True
    except Exception as e:
        logger.error(f"Error exporting sample concepts: {e}")
        return False

def main():
    """Main entry point for testing."""
    success = True
    
    # Test ontology loading
    success = test_ontology_loading() and success
    
    # Examine concept text for embedding
    success = examine_concept_text() and success
    
    # Export sample concepts to JSON file
    success = export_sample_concepts() and success
    
    # Return status
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
