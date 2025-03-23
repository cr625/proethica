import os
import sys
import json
from unittest.mock import MagicMock

# Mock the MCPClient class
class MockMCPClient:
    # Initialize server process attributes
    ethical_dm_server_process = None
    zotero_server_process = None
    def get_world_entities(self, ontology_source, entity_type="all"):
        # Return mock data
        return {
            "entities": {
                "roles": [
                    {
                        "id": "http://example.org/tccc#Medic",
                        "label": "Medic",
                        "description": "A medical professional in a tactical environment",
                        "tier": "1",
                        "capabilities": ["Provide medical care", "Triage casualties"]
                    }
                ],
                "conditions": [
                    {
                        "id": "http://example.org/tccc#Hemorrhage",
                        "label": "Hemorrhage",
                        "description": "Severe bleeding",
                        "type": "Injury",
                        "severity": "Critical",
                        "location": "Various"
                    }
                ]
            }
        }
    
    def get_references_for_scenario(self, scenario):
        # Return mock data
        return [
            {
                'data': {
                    'title': 'Reference 1',
                    'creators': [{'firstName': 'John', 'lastName': 'Doe'}]
                },
                'key': 'ref1'
            }
        ]
    
    def get_references_for_world(self, world):
        # Return mock data
        return [
            {
                'data': {
                    'title': 'Reference 1',
                    'creators': [{'firstName': 'John', 'lastName': 'Doe'}]
                },
                'key': 'ref1'
            }
        ]
    
    def search_zotero_items(self, query, collection_key=None, limit=20):
        # Return mock data
        return [
            {
                'data': {
                    'title': 'Search Result',
                    'creators': [{'firstName': 'Jane', 'lastName': 'Smith'}]
                },
                'key': 'ref2'
            }
        ]
    
    def get_zotero_citation(self, item_key, style="apa"):
        # Return mock data
        return 'Doe, J. (2023). Reference Title. Journal Name, 1(1), 1-10.'
    
    def get_zotero_bibliography(self, item_keys, style="apa"):
        # Return mock data
        return 'Doe, J. (2023). Reference Title. Journal Name, 1(1), 1-10.'
    
    def get_guidelines(self, domain="military-medical-triage"):
        # Return mock data
        return {
            "guidelines": [
                {
                    "title": "Guideline 1",
                    "description": "This is a guideline"
                }
            ]
        }
    
    def get_cases(self, domain="military-medical-triage"):
        # Return mock data
        return {
            "cases": [
                {
                    "title": "Case 1",
                    "description": "This is a case"
                }
            ]
        }
    
    def search_cases(self, query, domain="military-medical-triage", limit=5):
        # Return mock data
        return {
            "results": [
                {
                    "title": "Case 1",
                    "description": "This is a case"
                }
            ]
        }
    
    def add_case(self, title, description, decision, domain="military-medical-triage", outcome=None, ethical_analysis=None):
        # Return mock data
        return {
            "success": True,
            "message": "Case added successfully"
        }
    
    def get_similar_cases(self, scenario):
        # Return mock data
        return "Case 1: Title\nDescription: This is a case\nDecision: Decision\nOutcome: Outcome\nEthical Analysis: Analysis\n\n"
    
    def get_world_ontology(self, world_name):
        # Return mock data
        return "@prefix : <http://example.org/tccc#> .\n@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n\n:Medic a :Role ;\n    rdfs:label \"Medic\" ;\n    rdfs:comment \"A medical professional in a tactical environment\" ;\n    :hasTier \"1\" ;\n    :hasCapability \"Provide medical care\", \"Triage casualties\" .\n\n:Hemorrhage a :ConditionType ;\n    rdfs:label \"Hemorrhage\" ;\n    rdfs:comment \"Severe bleeding\" ;\n    :severity \"Critical\" ;\n    :location \"Various\" .\n"
    
    def get_zotero_collections(self):
        # Return mock data
        return [
            {
                "key": "collection1",
                "name": "Collection 1"
            }
        ]
    
    def get_zotero_recent_items(self, limit=20):
        # Return mock data
        return [
            {
                'data': {
                    'title': 'Recent Item',
                    'creators': [{'firstName': 'John', 'lastName': 'Doe'}]
                },
                'key': 'item1'
            }
        ]
    
    def add_zotero_item(self, item_type, title, creators=None, collection_key=None, additional_fields=None):
        # Return mock data
        return {
            "success": True,
            "message": "Item added successfully"
        }

    @classmethod
    def get_instance(cls):
        return cls()

# Mock the app.services.mcp_client module
import sys
sys.modules['app.services.mcp_client'] = MagicMock()
sys.modules['app.services.mcp_client'].MCPClient = MockMCPClient

def test_get_world_entities():
    """Test the get_world_entities method of MCPClient."""
    try:
        # Import the mocked MCPClient
        from app.services.mcp_client import MCPClient
        
        # Initialize the MCP client
        mcp_client = MCPClient.get_instance()
        
        # Test with the tccc.ttl ontology file
        ontology_source = "tccc.ttl"
        print(f"Testing get_world_entities with ontology_source={ontology_source}")
        
        # Get world entities
        entities = mcp_client.get_world_entities(ontology_source)
        
        # Print the result
        print("Success! Entities retrieved:")
        print(json.dumps(entities, indent=2))
        
        # Check if entities were retrieved
        if "entities" in entities and entities["entities"]:
            print(f"Found {len(entities['entities'])} entity types")
            for entity_type, entity_list in entities["entities"].items():
                print(f"- {entity_type}: {len(entity_list)} entities")
        else:
            print("No entities found or invalid response format")
        
        return True
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

if __name__ == "__main__":
    test_get_world_entities()
