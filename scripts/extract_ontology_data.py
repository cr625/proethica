#!/usr/bin/env python3
"""
Extract detailed information from ontologies via MCP server
"""

import os
import sys
import json
import requests
import time
from datetime import datetime

def extract_ontology_data():
    """Extract detailed information from ontologies via the MCP server"""
    
    # MCP server URL
    mcp_server_url = "http://localhost:5001"
    
    print(f"Connecting to MCP server at {mcp_server_url}...")
    
    # Ontologies to check
    ontology_domain_ids = ["bfo", "proethica-intermediate", "engineering-ethics"]
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(os.path.dirname(__file__), '..', 'ontology_data')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    for domain_id in ontology_domain_ids:
        print(f"\nExtracting data from ontology: {domain_id}")
        ontology_data = {
            "domain_id": domain_id,
            "extraction_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "classes": [],
            "properties": [],
            "all_triples": []
        }
        
        # Get classes using SPARQL
        print("- Fetching classes...")
        try:
            jsonrpc_payload = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "execute_sparql",
                    "arguments": {
                        "ontology_source": domain_id,
                        "query": """
                            SELECT DISTINCT ?class ?label
                            WHERE {
                                { ?class a <http://www.w3.org/2002/07/owl#Class> } 
                                UNION 
                                { ?class a <http://www.w3.org/2000/01/rdf-schema#Class> }
                                OPTIONAL { ?class <http://www.w3.org/2000/01/rdf-schema#label> ?label }
                            }
                            ORDER BY ?class
                        """
                    }
                },
                "id": 1
            }
            
            response = requests.post(f"{mcp_server_url}/jsonrpc", json=jsonrpc_payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                content = result.get("content", [])
                
                if content and len(content) > 0:
                    try:
                        # Extract text content and parse JSON
                        text_content = content[0].get("text", "{}")
                        classes_data = json.loads(text_content)
                        bindings = classes_data.get("results", {}).get("bindings", [])
                        
                        for binding in bindings:
                            class_uri = binding.get("class", {}).get("value")
                            label = binding.get("label", {}).get("value") if "label" in binding else None
                            
                            if class_uri:
                                ontology_data["classes"].append({
                                    "uri": class_uri,
                                    "label": label
                                })
                        
                        print(f"  Found {len(ontology_data['classes'])} classes")
                    except Exception as e:
                        print(f"  Error parsing classes data: {e}")
                else:
                    print("  No class data returned")
            else:
                print(f"  Failed to fetch classes: Status {response.status_code}")
        except Exception as e:
            print(f"  Error fetching classes: {e}")
        
        # Get properties using SPARQL
        print("- Fetching properties...")
        try:
            jsonrpc_payload = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "execute_sparql",
                    "arguments": {
                        "ontology_source": domain_id,
                        "query": """
                            SELECT DISTINCT ?property ?label
                            WHERE {
                                { ?property a <http://www.w3.org/2002/07/owl#ObjectProperty> } 
                                UNION 
                                { ?property a <http://www.w3.org/2002/07/owl#DatatypeProperty> }
                                OPTIONAL { ?property <http://www.w3.org/2000/01/rdf-schema#label> ?label }
                            }
                            ORDER BY ?property
                        """
                    }
                },
                "id": 2
            }
            
            response = requests.post(f"{mcp_server_url}/jsonrpc", json=jsonrpc_payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                content = result.get("content", [])
                
                if content and len(content) > 0:
                    try:
                        # Extract text content and parse JSON
                        text_content = content[0].get("text", "{}")
                        properties_data = json.loads(text_content)
                        bindings = properties_data.get("results", {}).get("bindings", [])
                        
                        for binding in bindings:
                            property_uri = binding.get("property", {}).get("value")
                            label = binding.get("label", {}).get("value") if "label" in binding else None
                            
                            if property_uri:
                                ontology_data["properties"].append({
                                    "uri": property_uri,
                                    "label": label
                                })
                        
                        print(f"  Found {len(ontology_data['properties'])} properties")
                    except Exception as e:
                        print(f"  Error parsing properties data: {e}")
                else:
                    print("  No property data returned")
            else:
                print(f"  Failed to fetch properties: Status {response.status_code}")
        except Exception as e:
            print(f"  Error fetching properties: {e}")
        
        # Get all triples (limited sample)
        print("- Fetching sample of triples...")
        try:
            jsonrpc_payload = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "execute_sparql",
                    "arguments": {
                        "ontology_source": domain_id,
                        "query": """
                            SELECT ?s ?p ?o
                            WHERE { ?s ?p ?o }
                            LIMIT 100
                        """
                    }
                },
                "id": 3
            }
            
            response = requests.post(f"{mcp_server_url}/jsonrpc", json=jsonrpc_payload)
            if response.status_code == 200:
                data = response.json()
                result = data.get("result", {})
                content = result.get("content", [])
                
                if content and len(content) > 0:
                    try:
                        # Extract text content and parse JSON
                        text_content = content[0].get("text", "{}")
                        triples_data = json.loads(text_content)
                        bindings = triples_data.get("results", {}).get("bindings", [])
                        
                        for binding in bindings:
                            subject = binding.get("s", {}).get("value")
                            predicate = binding.get("p", {}).get("value")
                            object_value = binding.get("o", {}).get("value")
                            
                            if subject and predicate and object_value:
                                ontology_data["all_triples"].append({
                                    "subject": subject,
                                    "predicate": predicate,
                                    "object": object_value
                                })
                        
                        print(f"  Found {len(ontology_data['all_triples'])} triples (limited sample)")
                    except Exception as e:
                        print(f"  Error parsing triples data: {e}")
                else:
                    print("  No triple data returned")
            else:
                print(f"  Failed to fetch triples: Status {response.status_code}")
        except Exception as e:
            print(f"  Error fetching triples: {e}")
        
        # Save the data to a file
        output_file = os.path.join(output_dir, f"{domain_id}_data_{timestamp}.json")
        try:
            with open(output_file, 'w') as f:
                json.dump(ontology_data, f, indent=2)
            print(f"- Data saved to: {output_file}")
        except Exception as e:
            print(f"- Error saving data to file: {e}")
        
        # Wait briefly between ontologies to avoid overwhelming server
        if domain_id != ontology_domain_ids[-1]:
            time.sleep(1)
    
    print("\nOntology data extraction completed.")

if __name__ == "__main__":
    extract_ontology_data()
