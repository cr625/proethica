#!/usr/bin/env python3
"""
Test script for case analysis using the Unified Ontology Server.

This script demonstrates how to use the case analysis module
to extract entities from text and analyze case structure.
"""

import os
import sys
import json
import requests
import argparse


def print_json(data):
    """Print JSON data in a formatted way."""
    print(json.dumps(data, indent=2))


def extract_entities_from_text(text, ontology_source):
    """Extract entities from text using the MCP server."""
    print(f"Extracting entities from text using ontology: {ontology_source}")
    
    response = requests.post(
        "http://localhost:5001/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "extract_entities",
                "arguments": {
                    "text": text,
                    "ontology_source": ontology_source
                }
            }
        }
    )
    
    # Process the response
    result = response.json()
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return None
    
    content_text = result["result"]["content"][0]["text"]
    return json.loads(content_text)


def analyze_case_structure(case_id, ontology_source):
    """Analyze a case structure using the MCP server."""
    print(f"Analyzing case structure for case ID: {case_id}")
    
    response = requests.post(
        "http://localhost:5001/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "analyze_case_structure",
                "arguments": {
                    "case_id": case_id,
                    "ontology_source": ontology_source
                }
            }
        }
    )
    
    # Process the response
    result = response.json()
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return None
    
    content_text = result["result"]["content"][0]["text"]
    return json.loads(content_text)


def generate_ontology_summary(case_id, ontology_source):
    """Generate an ontology-based summary for a case."""
    print(f"Generating ontology summary for case ID: {case_id}")
    
    response = requests.post(
        "http://localhost:5001/jsonrpc",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "call_tool",
            "params": {
                "name": "generate_summary",
                "arguments": {
                    "case_id": case_id,
                    "ontology_source": ontology_source
                }
            }
        }
    )
    
    # Process the response
    result = response.json()
    
    if "error" in result:
        print(f"Error: {result['error']}")
        return None
    
    content_text = result["result"]["content"][0]["text"]
    return json.loads(content_text)


def test_entity_extraction(text, ontology_source):
    """Test entity extraction functionality."""
    print("\n=== Testing Entity Extraction ===\n")
    
    # Extract entities
    entities_result = extract_entities_from_text(text, ontology_source)
    
    if entities_result:
        print(f"\nFound {entities_result['count']} entities in text:")
        for entity in entities_result.get("entities", []):
            print(f"  - {entity['label']} ({entity['type']}): {entity['text']}")
    
    return entities_result


def test_case_analysis(case_id, ontology_source):
    """Test case analysis functionality."""
    print("\n=== Testing Case Analysis ===\n")
    
    # Analyze case structure
    structure_result = analyze_case_structure(case_id, ontology_source)
    
    if structure_result and "error" not in structure_result:
        print(f"\nCase Title: {structure_result.get('title')}")
        print(f"Found {structure_result.get('entity_count')} entities in case")
        
        # Print entities by type
        entities_by_type = structure_result.get("entities_by_type", {})
        for entity_type, entities in entities_by_type.items():
            print(f"\n{entity_type.title()} entities ({len(entities)}):")
            for entity in entities[:5]:  # Show only first 5 of each type
                print(f"  - {entity.get('label')}")
            
            if len(entities) > 5:
                print(f"  ... and {len(entities) - 5} more")
    
    return structure_result


def test_ontology_summary(case_id, ontology_source):
    """Test ontology summary functionality."""
    print("\n=== Testing Ontology Summary Generation ===\n")
    
    # Generate summary
    summary_result = generate_ontology_summary(case_id, ontology_source)
    
    if summary_result and "error" not in summary_result:
        print(f"\nCase Title: {summary_result.get('title')}")
        
        # Print summary sections
        print("\nSummary:")
        for section in summary_result.get("summary_sections", []):
            print(f"\n{section['title']}:")
            print(f"{section['content']}")
    
    return summary_result


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Test case analysis using the Unified Ontology Server"
    )
    
    parser.add_argument(
        "--text",
        type=str,
        default="The engineer faced an ethical dilemma regarding safety vs costs.",
        help="Text to extract entities from"
    )
    
    parser.add_argument(
        "--case-id",
        type=int,
        default=1,
        help="Case ID to analyze"
    )
    
    parser.add_argument(
        "--ontology-source",
        type=str,
        default="engineering",
        help="Ontology source to use"
    )
    
    parser.add_argument(
        "--mode",
        choices=["extract", "analyze", "summary", "all"],
        default="all",
        help="Test mode: extract entities, analyze case, generate summary, or all"
    )
    
    args = parser.parse_args()
    
    try:
        # Check if server is running
        try:
            response = requests.get("http://localhost:5001/health", timeout=2)
            if response.status_code != 200:
                print("Error: Server is not responding correctly.")
                return 1
        except requests.exceptions.ConnectionError:
            print("Error: Cannot connect to the ontology server.")
            print("Please start the server using: ./start_unified_ontology_server.sh")
            return 1
        
        # Run the requested test mode
        if args.mode in ["extract", "all"]:
            test_entity_extraction(args.text, args.ontology_source)
        
        if args.mode in ["analyze", "all"]:
            test_case_analysis(args.case_id, args.ontology_source)
        
        if args.mode in ["summary", "all"]:
            test_ontology_summary(args.case_id, args.ontology_source)
        
        return 0
    
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
