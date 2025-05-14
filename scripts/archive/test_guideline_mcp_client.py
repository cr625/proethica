#!/usr/bin/env python3
"""
Test Guideline MCP Client

This script tests the guideline analysis functionality of the MCP server.
It extracts concepts from a test guideline, matches them to ontology entities,
and generates RDF triples.
"""

import os
import sys
import json
import time
import logging
import asyncio
import requests
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# MCP server URL
MCP_URL = "http://localhost:5001"

# Test guideline file path
TEST_GUIDELINE_PATH = "test_guideline.txt"

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

def call_mcp_tool(tool_name, arguments):
    """
    Call a tool on the MCP server.
    
    Args:
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool
        
    Returns:
        Result from the tool
    """
    logger.info(f"Calling MCP tool: {tool_name}")
    
    # Prepare JSON-RPC request
    request_data = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": tool_name,
            "arguments": arguments
        },
        "id": int(time.time())
    }
    
    try:
        # Make the request
        response = requests.post(
            f"{MCP_URL}/jsonrpc",
            json=request_data,
            timeout=300  # Long timeout for LLM operations
        )
        
        # Check response status
        if response.status_code != 200:
            logger.error(f"HTTP error {response.status_code}: {response.text}")
            return {"error": f"HTTP error {response.status_code}"}
        
        # Parse response
        result = response.json()
        
        # Check for JSON-RPC error
        if "error" in result:
            logger.error(f"JSON-RPC error: {result['error']}")
            return {"error": result["error"]}
        
        # Return result
        return result.get("result", {})
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return {"error": f"Request failed: {str(e)}"}
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {"error": f"Invalid JSON response: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"error": f"Unexpected error: {str(e)}"}

def save_json(data, filename):
    """Save data to a JSON file."""
    try:
        with open(filename, "w") as f:
            json.dump(data, indent=2, fp=f)
        logger.info(f"Saved data to {filename}")
    except Exception as e:
        logger.error(f"Error saving to {filename}: {str(e)}")

def save_turtle(triples_data, filename):
    """
    Save triples data as Turtle RDF.
    
    This is a simple conversion - in a real implementation,
    use a proper RDF library like rdflib.
    
    Args:
        triples_data: Dictionary containing triples
        filename: Output filename
    """
    try:
        # Get triples from data
        triples = triples_data.get("triples", [])
        
        if not triples:
            logger.warning("No triples to save")
            return
        
        # Start with prefixes
        ttl_content = [
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .",
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
            "@prefix owl: <http://www.w3.org/2002/07/owl#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "@prefix dc: <http://purl.org/dc/elements/1.1/> .",
            "@prefix proeth: <http://proethica.org/ontology/> .",
            "@prefix guide: <http://proethica.org/guidelines/> .",
            ""
        ]
        
        # Group triples by subject
        subjects = {}
        for triple in triples:
            subject = triple["subject"]
            if subject not in subjects:
                subjects[subject] = []
            subjects[subject].append(triple)
        
        # Generate Turtle content
        for subject, subject_triples in subjects.items():
            ttl_content.append(f"<{subject}>")
            
            # Add predicates and objects
            for i, triple in enumerate(subject_triples):
                predicate = triple["predicate"]
                obj = triple["object"]
                
                # Check if object is a URI or literal
                if obj.startswith("http://"):
                    obj_ttl = f"<{obj}>"
                else:
                    # Simple quoting - a real implementation would handle datatypes
                    obj_ttl = f'"""{obj}"""'
                
                # Add separator
                separator = ";" if i < len(subject_triples) - 1 else "."
                
                # Add the triple
                ttl_content.append(f"    <{predicate}> {obj_ttl}{separator}")
            
            # Add empty line between subjects
            ttl_content.append("")
        
        # Write to file
        with open(filename, "w") as f:
            f.write("\n".join(ttl_content))
            
        logger.info(f"Saved Turtle RDF to {filename}")
        
    except Exception as e:
        logger.error(f"Error saving Turtle to {filename}: {str(e)}")

async def main():
    """Main function."""
    logger.info("Starting Guideline MCP Client test")
    
    # Check if MCP server is running
    if not wait_for_server():
        logger.error("Cannot connect to MCP server. Make sure it's running.")
        return 1
    
    # Check for test guideline
    if not os.path.exists(TEST_GUIDELINE_PATH):
        logger.error(f"Test guideline file not found: {TEST_GUIDELINE_PATH}")
        return 1
    
    try:
        # Read guideline content
        with open(TEST_GUIDELINE_PATH, "r") as f:
            guideline_content = f.read()
        
        # Step 1: Extract concepts
        logger.info("Extracting concepts from guideline...")
        extract_result = call_mcp_tool("extract_guideline_concepts", {
            "content": guideline_content,
            "ontology_source": "engineering-ethics"
        })
        
        if "error" in extract_result:
            logger.error(f"Failed to extract concepts: {extract_result['error']}")
            return 1
        
        # Save the concepts
        save_json(extract_result, "guideline_concepts.json")
        
        # Get the concepts
        concepts = extract_result.get("concepts", [])
        if not concepts:
            logger.warning("No concepts extracted")
            return 0
        
        # Step 2: Match concepts to ontology
        logger.info("Matching concepts to ontology entities...")
        match_result = call_mcp_tool("match_concepts_to_ontology", {
            "concepts": concepts,
            "ontology_source": "engineering-ethics",
            "match_threshold": 0.6
        })
        
        if "error" in match_result:
            logger.error(f"Failed to match concepts: {match_result['error']}")
            return 1
        
        # Save the matches
        save_json(match_result, "guideline_matches.json")
        
        # Step 3: Generate triples
        logger.info("Generating triples...")
        
        # Get all concept indices
        selected_indices = list(range(len(concepts)))
        
        triple_result = call_mcp_tool("generate_concept_triples", {
            "concepts": concepts,
            "selected_indices": selected_indices,
            "ontology_source": "engineering-ethics",
            "namespace": "http://proethica.org/guidelines/",
            "output_format": "turtle"
        })
        
        if "error" in triple_result:
            logger.error(f"Failed to generate triples: {triple_result['error']}")
            return 1
        
        # Save the triples as JSON
        save_json(triple_result, "guideline_triples.json")
        
        # Save the triples as Turtle
        save_turtle(triple_result, "guideline_triples.ttl")
        
        # Report results
        logger.info(f"Extracted {len(concepts)} concepts")
        logger.info(f"Generated {triple_result.get('triple_count', 0)} triples")
        logger.info("Test completed successfully!")
        
        return 0
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
