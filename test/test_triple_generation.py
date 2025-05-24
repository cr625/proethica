#!/usr/bin/env python3
"""
Test script for guideline triple generation functionality.

This script tests the generate_concept_triples tool in the MCP server
by directly calling the JSON-RPC endpoint.
"""

import json
import requests
import time
import sys
from pprint import pprint

# Define the MCP server URL
MCP_URL = "http://localhost:5001/jsonrpc"

# Sample concepts for testing
SAMPLE_CONCEPTS = [
    {
        "id": 0,
        "label": "Public Safety",
        "description": "The paramount obligation of engineers to prioritize public safety",
        "category": "principle",
        "related_concepts": ["Professional Responsibility", "Risk Management"],
        "text_references": ["Engineers shall hold paramount the safety of the public"]
    },
    {
        "id": 1,
        "label": "Professional Competence",
        "description": "The obligation to only perform work within one's area of competence",
        "category": "obligation",
        "related_concepts": ["Professional Development", "Technical Expertise"],
        "text_references": ["Engineers shall perform services only in areas of their competence"]
    },
    {
        "id": 2,
        "label": "Ethical Behavior",
        "description": "Conducting oneself with integrity and adhering to ethical principles",
        "category": "principle",
        "related_concepts": ["Honesty", "Professional Responsibility"],
        "text_references": ["Engineers shall act in professional matters as faithful agents"]
    }
]

def test_triple_generation(concepts=None, ontology_source="engineering-ethics"):
    """
    Test the triple generation functionality.
    
    Args:
        concepts: List of concepts to generate triples for
        ontology_source: Ontology source identifier
    """
    if concepts is None:
        concepts = SAMPLE_CONCEPTS
    
    # Define the selected indices (all concepts)
    selected_indices = list(range(len(concepts)))
    
    # Create the JSON-RPC request
    request_data = {
        "jsonrpc": "2.0",
        "method": "call_tool",
        "params": {
            "name": "generate_concept_triples",
            "arguments": {
                "concepts": concepts,
                "selected_indices": selected_indices,
                "ontology_source": ontology_source,
                "namespace": "http://proethica.org/test/",
                "output_format": "json"
            }
        },
        "id": 1
    }
    
    # Print request information
    print(f"Making request to MCP server at {MCP_URL}")
    print(f"Testing with {len(concepts)} concepts and {len(selected_indices)} selected indices")
    
    # Time the operation
    start_time = time.time()
    
    # Make the request
    try:
        response = requests.post(
            MCP_URL,
            json=request_data,
            timeout=30
        )
        
        # Check the response status
        if response.status_code == 200:
            result = response.json()
            
            # Check if we have a result
            if "result" in result:
                # Get the triple generation result
                triple_result = result["result"]
                
                # Print summary
                print(f"\nTriple Generation Results:")
                print(f"Generated {triple_result.get('triple_count', 0)} triples for {triple_result.get('concept_count', 0)} concepts")
                print(f"Processing time: {triple_result.get('processing_time', 0):.2f} seconds")
                print(f"Request completed in: {time.time() - start_time:.2f} seconds")
                
                # Print the first few triples
                triples = triple_result.get("triples", [])
                if triples:
                    print("\nExample triples:")
                    for i, triple in enumerate(triples[:5]):  # Show first 5 triples
                        print(f"{i+1}. {triple.get('subject_label')} - {triple.get('predicate_label')} - {triple.get('object_label')}")
                
                # Count triple types
                predicate_counts = {}
                for triple in triples:
                    predicate = triple.get('predicate_label', '')
                    predicate_counts[predicate] = predicate_counts.get(predicate, 0) + 1
                
                print("\nTriple types:")
                for predicate, count in sorted(predicate_counts.items(), key=lambda x: x[1], reverse=True):
                    print(f"- {predicate}: {count}")
                
                # Save to file for detailed inspection
                with open('test_triple_generation_result.json', 'w') as f:
                    json.dump(triple_result, f, indent=2)
                print("\nFull results saved to 'test_triple_generation_result.json'")
                
                return True, triple_result
            else:
                print("Error: No result in response")
                if "error" in result:
                    print(f"Error message: {result['error']}")
                return False, None
        else:
            print(f"Error: HTTP status code {response.status_code}")
            return False, None
    
    except requests.exceptions.RequestException as e:
        print(f"Request error: {str(e)}")
        return False, None
    except Exception as e:
        print(f"Error: {str(e)}")
        return False, None

if __name__ == "__main__":
    # Get ontology source from command line if provided
    ontology_source = sys.argv[1] if len(sys.argv) > 1 else "engineering-ethics"
    
    # Run the test
    success, result = test_triple_generation(ontology_source=ontology_source)
    
    # Set exit code based on success
    sys.exit(0 if success else 1)
