#!/usr/bin/env python3
"""
Test script for verifying the guideline analysis functions in the MCP server.

This script tests the integration between the GuidelineAnalysisService and
the MCP server's GuidelineAnalysisModule.
"""

import os
import sys
import json
import requests
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default MCP server URL
MCP_URL = "http://localhost:5001"

def read_test_guideline():
    """Read the test guideline content."""
    try:
        guideline_path = Path("test_guideline.txt")
        if not guideline_path.exists():
            logger.error(f"Test guideline file not found at {guideline_path}")
            return None
        
        with open(guideline_path, "r") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading test guideline: {str(e)}")
        return None

def test_extract_concepts(content):
    """Test the extract_guideline_concepts tool."""
    logger.info("Testing extract_guideline_concepts tool...")
    
    try:
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "extract_guideline_concepts",
                    "arguments": {
                        "content": content[:10000],  # Limit to first 10k chars
                        "ontology_source": "engineering-ethics"
                    }
                },
                "id": 1
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                concepts = result["result"].get("concepts", [])
                logger.info(f"Successfully extracted {len(concepts)} concepts from guideline content")
                return concepts
            else:
                logger.error(f"Error extracting concepts: {result.get('error', 'Unknown error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling extract_guideline_concepts: {str(e)}")
        return None

def test_match_concepts(concepts):
    """Test the match_concepts_to_ontology tool."""
    if not concepts:
        logger.error("No concepts to match")
        return None
    
    logger.info("Testing match_concepts_to_ontology tool...")
    
    try:
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "match_concepts_to_ontology",
                    "arguments": {
                        "concepts": concepts,
                        "ontology_source": "engineering-ethics",
                        "match_threshold": 0.6
                    }
                },
                "id": 2
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                matches = result["result"].get("matches", {})
                logger.info(f"Successfully matched {len(matches)} concepts to ontology entities")
                return matches
            else:
                logger.error(f"Error matching concepts: {result.get('error', 'Unknown error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling match_concepts_to_ontology: {str(e)}")
        return None

def test_generate_triples(concepts):
    """Test the generate_concept_triples tool."""
    if not concepts:
        logger.error("No concepts to generate triples for")
        return None
    
    logger.info("Testing generate_concept_triples tool...")
    
    # Select the first 3 concepts for testing
    selected_indices = list(range(min(3, len(concepts))))
    
    try:
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "generate_concept_triples",
                    "arguments": {
                        "concepts": concepts,
                        "selected_indices": selected_indices,
                        "ontology_source": "engineering-ethics",
                        "namespace": "http://proethica.org/test/",
                        "output_format": "json"
                    }
                },
                "id": 3
            },
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if "result" in result:
                triples = result["result"].get("triples", [])
                logger.info(f"Successfully generated {len(triples)} triples for selected concepts")
                return triples
            else:
                logger.error(f"Error generating triples: {result.get('error', 'Unknown error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling generate_concept_triples: {str(e)}")
        return None

def check_mcp_server():
    """Check if the MCP server is running."""
    try:
        response = requests.get(f"{MCP_URL}", timeout=5)
        if response.status_code == 200:
            logger.info("MCP server is running")
            return True
        else:
            logger.error(f"MCP server returned unexpected status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        logger.error("MCP server is not running")
        return False

def main():
    """Main function to run the tests."""
    logger.info("Starting MCP server guideline analysis integration test")
    
    # Check if MCP server is running
    if not check_mcp_server():
        logger.error("Please start the MCP server first by running:")
        logger.error("python mcp/run_enhanced_mcp_server_with_guidelines.py")
        return
    
    # Read the test guideline content
    content = read_test_guideline()
    if not content:
        return
    
    # Test the extract concepts tool
    concepts = test_extract_concepts(content)
    if not concepts:
        return
    
    # Print sample concepts
    logger.info("Sample concepts extracted:")
    for i, concept in enumerate(concepts[:5]):
        logger.info(f"  {i+1}. {concept.get('label', 'Unnamed')} ({concept.get('type', 'unknown')})")
    
    # Test the match concepts tool
    matches = test_match_concepts(concepts)
    if not matches:
        return
    
    # Print sample matches
    logger.info("Sample concept matches:")
    for i, (concept_label, entity_matches) in enumerate(list(matches.items())[:3]):
        match_count = len(entity_matches)
        if match_count > 0:
            logger.info(f"  {i+1}. {concept_label}: {match_count} matches")
            for j, match in enumerate(entity_matches[:2]):
                logger.info(f"     - {match.get('label', 'Unknown')} ({match.get('match_type', 'unknown')}, {match.get('confidence', 0):.2f})")
    
    # Test the generate triples tool
    triples = test_generate_triples(concepts)
    if not triples:
        return
    
    # Print sample triples
    logger.info("Sample generated triples:")
    for i, triple in enumerate(triples[:5]):
        subject = triple.get("subject_label", triple.get("subject", ""))
        predicate = triple.get("predicate_label", triple.get("predicate", ""))
        obj = triple.get("object_label", triple.get("object", ""))
        logger.info(f"  {i+1}. {subject} -> {predicate} -> {obj}")
    
    logger.info("MCP server guideline analysis integration test completed successfully")

if __name__ == "__main__":
    main()
