#!/usr/bin/env python3
"""
Test Guideline Analysis MCP Client

This script tests the guideline analysis functionality through the MCP client.
It sends the test guideline to the server for analysis and displays the results.
"""

import os
import sys
import json
import time
import asyncio
import requests
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# MCP server URL
MCP_URL = "http://localhost:5001"

# Test guideline file path
TEST_GUIDELINE_PATH = Path("test_guideline.txt")

def read_test_guideline():
    """Read the test guideline content."""
    try:
        if not TEST_GUIDELINE_PATH.exists():
            logger.error(f"Test guideline file not found at {TEST_GUIDELINE_PATH}")
            return None
        
        with open(TEST_GUIDELINE_PATH, "r") as f:
            content = f.read()
            logger.info(f"Read {len(content)} characters from test guideline")
            return content
    except Exception as e:
        logger.error(f"Error reading test guideline: {str(e)}")
        return None

def wait_for_server(timeout=30):
    """Wait for the server to start, with timeout."""
    logger.info(f"Waiting up to {timeout} seconds for MCP server...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Test the JSON-RPC endpoint with a simple ping request
            response = requests.post(
                f"{MCP_URL}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "params": {},
                    "id": 0
                },
                timeout=2
            )
            if response.status_code == 200:
                logger.info("MCP server is running!")
                return True
        except requests.exceptions.RequestException:
            # Keep waiting
            pass
        
        time.sleep(1)
    
    logger.error(f"Timed out after {timeout} seconds waiting for server to start")
    return False

def list_available_tools():
    """List all available tools from the MCP server."""
    try:
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data and "tools" in data["result"]:
                tools = data["result"]["tools"]
                logger.info(f"Available tools: {json.dumps(tools, indent=2)}")
                return tools
            else:
                logger.error(f"Unexpected response format: {data}")
                return None
        else:
            logger.error(f"Error listing tools: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception while listing tools: {str(e)}")
        return None

def extract_concepts(content):
    """Extract concepts from the guideline content."""
    try:
        logger.info("Calling extract_guideline_concepts tool...")
        
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "extract_guideline_concepts",
                    "arguments": {
                        "content": content,
                        "ontology_source": "engineering-ethics"  # Optional
                    }
                },
                "id": 1
            },
            timeout=60  # Longer timeout for LLM processing
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                logger.info(f"Successfully extracted concepts")
                result = data["result"]
                
                # Log the number of concepts extracted
                if "concepts" in result:
                    concepts = result["concepts"]
                    logger.info(f"Extracted {len(concepts)} concepts")
                    
                    # Display first few concepts
                    for i, concept in enumerate(concepts[:3]):
                        logger.info(f"Concept {i+1}: {concept.get('label')} - {concept.get('category')}")
                
                return result
            else:
                logger.error(f"Error in response: {data.get('error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception while extracting concepts: {str(e)}")
        return None

def match_concepts_to_ontology(concepts):
    """Match extracted concepts to ontology entities."""
    if not concepts or "concepts" not in concepts:
        logger.error("No concepts to match")
        return None
    
    try:
        logger.info("Calling match_concepts_to_ontology tool...")
        
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "match_concepts_to_ontology",
                    "arguments": {
                        "concepts": concepts["concepts"],
                        "ontology_source": "engineering-ethics",  # Optional
                        "match_threshold": 0.5  # Optional
                    }
                },
                "id": 2
            },
            timeout=60  # Longer timeout for LLM processing
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                logger.info(f"Successfully matched concepts to ontology")
                result = data["result"]
                
                # Log the number of matches
                if "matches" in result:
                    matches = result["matches"]
                    logger.info(f"Found {len(matches)} ontology matches")
                    
                    # Display first few matches
                    for i, match in enumerate(matches[:3]):
                        logger.info(f"Match {i+1}: {match.get('concept_label')} -> {match.get('ontology_entity')} "
                                   f"(confidence: {match.get('confidence')})")
                
                return result
            else:
                logger.error(f"Error in response: {data.get('error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception while matching concepts: {str(e)}")
        return None

def generate_triples(concepts, selected_indices=None):
    """Generate RDF triples for selected concepts."""
    if not concepts or "concepts" not in concepts:
        logger.error("No concepts to generate triples for")
        return None
    
    # If no indices specified, use the first 5 concepts
    if selected_indices is None:
        selected_indices = list(range(min(5, len(concepts["concepts"]))))
    
    try:
        logger.info(f"Calling generate_concept_triples tool for {len(selected_indices)} concepts...")
        
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json={
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "generate_concept_triples",
                    "arguments": {
                        "concepts": concepts["concepts"],
                        "selected_indices": selected_indices,
                        "namespace": "http://proethica.org/guidelines/engineering/",
                        "output_format": "turtle"
                    }
                },
                "id": 3
            },
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "result" in data:
                logger.info(f"Successfully generated triples")
                result = data["result"]
                
                # Log the number of triples
                if "triples" in result:
                    triples = result["triples"]
                    logger.info(f"Generated {len(triples)} RDF triples")
                    
                    # Display first few triples
                    for i, triple in enumerate(triples[:3]):
                        logger.info(f"Triple {i+1}: {triple.get('subject_label')} -> "
                                   f"{triple.get('predicate_label')} -> {triple.get('object_label')}")
                
                return result
            else:
                logger.error(f"Error in response: {data.get('error')}")
                return None
        else:
            logger.error(f"HTTP error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception while generating triples: {str(e)}")
        return None

def save_results(concepts, matches, triples):
    """Save the analysis results to files."""
    try:
        # Save concepts
        if concepts and "concepts" in concepts:
            with open("guideline_concepts.json", "w") as f:
                json.dump(concepts, f, indent=2)
            logger.info(f"Saved concepts to guideline_concepts.json")
        
        # Save matches
        if matches and "matches" in matches:
            with open("guideline_matches.json", "w") as f:
                json.dump(matches, f, indent=2)
            logger.info(f"Saved matches to guideline_matches.json")
        
        # Save triples
        if triples and "triples" in triples:
            with open("guideline_triples.json", "w") as f:
                json.dump(triples, f, indent=2)
            logger.info(f"Saved triples to guideline_triples.json")
            
            # Create a simple Turtle file from the triples
            try:
                with open("guideline_triples.ttl", "w") as f:
                    f.write("@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n")
                    f.write("@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n")
                    f.write("@prefix proeth: <http://proethica.org/ontology/> .\n")
                    f.write("@prefix guide: <http://proethica.org/guidelines/engineering/> .\n\n")
                    
                    for triple in triples["triples"]:
                        subject = triple["subject"]
                        predicate = triple["predicate"]
                        obj = triple["object"]
                        
                        # Handle literal vs URI objects
                        if predicate.endswith("label") or predicate.endswith("description") or predicate.endswith("Text"):
                            # Escape quotes in literals
                            obj_str = f'"{obj.replace('"', '\\"')}"'
                        else:
                            obj_str = f"<{obj}>"
                        
                        f.write(f"<{subject}> <{predicate}> {obj_str} .\n")
                
                logger.info(f"Saved Turtle triples to guideline_triples.ttl")
            except Exception as e:
                logger.error(f"Error creating Turtle file: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error saving results: {str(e)}")

def main():
    """Main function."""
    logger.info("Starting guideline analysis test")
    
    # Wait for the server to be available
    if not wait_for_server(timeout=30):
        logger.error("Server not available, exiting")
        return
    
    # Read the test guideline
    content = read_test_guideline()
    if not content:
        return
    
    # List available tools
    tools = list_available_tools()
    if not tools:
        logger.error("Could not list available tools, exiting")
        return
    
    # Extract concepts
    concepts = extract_concepts(content)
    if not concepts:
        logger.error("Failed to extract concepts, exiting")
        return
    
    # Match concepts to ontology
    matches = match_concepts_to_ontology(concepts)
    
    # Generate triples
    # If we have matches, use the indices of matched concepts
    selected_indices = None
    if matches and "matches" in matches:
        # Get the concept labels that have matches
        matched_labels = [m["concept_label"] for m in matches["matches"]]
        # Find their indices in the concepts list
        if "concepts" in concepts:
            selected_indices = [
                i for i, concept in enumerate(concepts["concepts"])
                if concept.get("label") in matched_labels
            ]
            # Limit to top 10 matches if there are many
            if len(selected_indices) > 10:
                selected_indices = selected_indices[:10]
    
    triples = generate_triples(concepts, selected_indices)
    
    # Save results
    save_results(concepts, matches, triples)
    
    logger.info("Guideline analysis test completed")

if __name__ == "__main__":
    main()
