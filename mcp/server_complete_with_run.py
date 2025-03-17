#!/usr/bin/env python3
import json
import os
import sys
import asyncio

class EthicalDMServer:
    """MCP server for the AI Ethical Decision-Making Simulator."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.jsonrpc_id = 0
    
    async def run(self):
        """Run the MCP server."""
        print("Ethical DM MCP server running on stdio", file=sys.stderr)
        
        # Process stdin/stdout
        while True:
            try:
                # Read request from stdin
                request_line = await self._read_line()
                if not request_line:
                    continue
                
                # Parse request
                request = json.loads(request_line)
                
                # Process request
                response = await self._process_request(request)
                
                # Send response
                print(json.dumps(response), flush=True)
            except Exception as e:
                print(f"Error processing request: {str(e)}", file=sys.stderr)
                # Send error response
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32000,
                        "message": f"Internal error: {str(e)}"
                    },
                    "id": self.jsonrpc_id
                }
                print(json.dumps(error_response), flush=True)
    
    async def _read_line(self):
        """Read a line from stdin."""
        return sys.stdin.readline().strip()
    
    async def _process_request(self, request):
        """Process a JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        self.jsonrpc_id = request_id
        
        # Process method
        if method == "list_resources":
            result = await self._handle_list_resources(params)
        elif method == "list_resource_templates":
            result = await self._handle_list_resource_templates(params)
        elif method == "read_resource":
            result = await self._handle_read_resource(params)
        elif method == "list_tools":
            result = await self._handle_list_tools(params)
        elif method == "call_tool":
            result = await self._handle_call_tool(params)
        else:
            # Method not found
            return {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                },
                "id": request_id
            }
        
        # Return result
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }
    
    async def _handle_list_resources(self, params):
        """Handle request to list available resources."""
        return {
            "resources": [
                # Military Medical Triage
                {
                    "uri": "ethical-dm://guidelines/military-medical-triage",
                    "name": "Military Medical Triage Guidelines",
                    "mimeType": "application/json",
                    "description": "Guidelines for military medical triage scenarios"
                },
                {
                    "uri": "ethical-dm://cases/military-medical-triage",
                    "name": "Military Medical Triage Case Repository",
                    "mimeType": "application/json",
                    "description": "Repository of past military medical triage cases"
                },
                {
                    "uri": "ethical-dm://worlds/military-medical-triage",
                    "name": "Military Medical Triage World",
                    "mimeType": "application/rdf+xml",
                    "description": "Ontology for military medical triage world"
                }
            ]
        }
    
    async def _handle_list_resource_templates(self, params):
        """Handle request to list available resource templates."""
        return {
            "resourceTemplates": [
                {
                    "uriTemplate": "ethical-dm://cases/search/{query}",
                    "name": "Search Cases",
                    "mimeType": "application/json",
                    "description": "Search for cases matching a query"
                },
                {
                    "uriTemplate": "ethical-dm://worlds/{world_name}/entities",
                    "name": "World Entities",
                    "mimeType": "application/json",
                    "description": "Get entities from a specific world"
                }
            ]
        }
    
    async def _handle_read_resource(self, params):
        """Handle request to read a resource."""
        uri = params.get("uri")
        
        # Handle Military Medical Triage resources
        if uri == "ethical-dm://guidelines/military-medical-triage":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "guidelines": [
                                {
                                    "name": "START Triage Protocol",
                                    "description": "Simple Triage and Rapid Treatment protocol for mass casualty incidents",
                                    "categories": [
                                        {"name": "Immediate (Red)", "description": "Patients requiring immediate life-saving intervention"},
                                        {"name": "Delayed (Yellow)", "description": "Patients with significant injuries but stable for the moment"},
                                        {"name": "Minimal (Green)", "description": "Patients with minor injuries who can wait for treatment"},
                                        {"name": "Expectant (Black)", "description": "Patients unlikely to survive given severity of injuries and available resources"}
                                    ]
                                },
                                {
                                    "name": "Military Triage Considerations",
                                    "description": "Additional considerations specific to military contexts",
                                    "factors": [
                                        "Military necessity and mission requirements",
                                        "Resource limitations in combat environments",
                                        "Tactical situation and security concerns",
                                        "Return to duty potential"
                                    ]
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
        elif uri == "ethical-dm://cases/military-medical-triage":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "cases": [
                                {
                                    "id": 1,
                                    "title": "Field Hospital Mass Casualty",
                                    "description": "Field hospital receiving multiple casualties from an IED attack with limited resources",
                                    "decision": "Prioritized treatment based on severity and survivability",
                                    "outcome": "Maximized survival rates but some potentially salvageable patients were classified as expectant",
                                    "ethical_analysis": "Utilitarian approach maximized overall survival but raised concerns about individual rights"
                                },
                                {
                                    "id": 2,
                                    "title": "Civilian and Military Casualties",
                                    "description": "Mixed civilian and military casualties with limited evacuation capacity",
                                    "decision": "Evacuated based on medical need regardless of status",
                                    "outcome": "Aligned with humanitarian principles but delayed return of some military personnel to duty",
                                    "ethical_analysis": "Prioritized medical ethics over military necessity, reflecting deontological principles"
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
        elif uri == "ethical-dm://worlds/military-medical-triage":
            # Read the RDF file
            try:
                with open(os.path.join(os.path.dirname(__file__), "ontology/military_medical_triage.ttl"), "r") as f:
                    rdf_content = f.read()
                
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/rdf+xml",
                            "text": rdf_content
                        }
                    ]
                }
            except Exception as e:
                return {
                    "error": {
                        "code": -32000,
                        "message": f"Error reading ontology file: {str(e)}"
                    }
                }
        
        # Handle resource templates
        if uri.startswith("ethical-dm://cases/search/"):
            query = uri.split("/")[-1]
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "query": query,
                            "results": [
                                {
                                    "id": 1,
                                    "title": "Field Hospital Mass Casualty",
                                    "relevance": 0.85,
                                    "snippet": "Field hospital receiving multiple casualties from an IED attack with limited resources..."
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
        elif uri.startswith("ethical-dm://worlds/"):
            parts = uri.split("/")
            if len(parts) >= 4 and parts[3] == "entities":
                world_name = parts[2]
                if world_name == "military-medical-triage":
                    return {
                        "contents": [
                            {
                                "uri": uri,
                                "mimeType": "application/json",
                                "text": json.dumps({
                                    "world": "Military Medical Triage",
                                    "entities": {
                                        "characters": [
                                            {
                                                "id": "mmt:Patient1",
                                                "type": "Patient",
                                                "label": "Patient 1",
                                                "conditions": ["mmt:Hemorrhage1"],
                                                "triage_category": "mmt:Immediate"
                                            },
                                            {
                                                "id": "mmt:Patient2",
                                                "type": "Patient",
                                                "label": "Patient 2",
                                                "conditions": ["mmt:Fracture1"],
                                                "triage_category": "mmt:Delayed"
                                            },
                                            {
                                                "id": "mmt:Patient3",
                                                "type": "Patient",
                                                "label": "Patient 3",
                                                "conditions": ["mmt:BurnInjury1"],
                                                "triage_category": "mmt:Minimal"
                                            },
                                            {
                                                "id": "mmt:Medic1",
                                                "type": "Medic",
                                                "label": "Combat Medic",
                                                "resources": ["mmt:Tourniquet1", "mmt:Bandage1", "mmt:Morphine1"]
                                            }
                                        ],
                                        "conditions": [
                                            {
                                                "id": "mmt:Hemorrhage1",
                                                "type": "Hemorrhage",
                                                "label": "Severe Hemorrhage",
                                                "severity": "Severe",
                                                "location": "Left Leg"
                                            },
                                            {
                                                "id": "mmt:Fracture1",
                                                "type": "Fracture",
                                                "label": "Compound Fracture",
                                                "severity": "Moderate",
                                                "location": "Right Arm"
                                            },
                                            {
                                                "id": "mmt:BurnInjury1",
                                                "type": "BurnInjury",
                                                "label": "First Degree Burn",
                                                "severity": "Mild",
                                                "location": "Left Hand"
                                            }
                                        ],
                                        "resources": [
                                            {
                                                "id": "mmt:Tourniquet1",
                                                "type": "Tourniquet",
                                                "label": "Combat Application Tourniquet",
                                                "quantity": 2
                                            },
                                            {
                                                "id": "mmt:Bandage1",
                                                "type": "Bandage",
                                                "label": "Pressure Bandage",
                                                "quantity": 5
                                            },
                                            {
                                                "id": "mmt:Morphine1",
                                                "type": "Morphine",
                                                "label": "Morphine Autoinjector",
                                                "quantity": 3
                                            }
                                        ]
                                    }
                                }, indent=2)
                            }
                        ]
                    }
                else:
                    return {
                        "error": {
                            "code": -32602,
                            "message": f"World not found: {world_name}"
                        }
                    }
        
        # Resource not found
        return {
            "error": {
                "code": -32602,
                "message": f"Resource not found: {uri}"
            }
        }
    
    async def _handle_list_tools(self, params):
        """Handle request to list available tools."""
        return {
            "tools": [
                {
                    "name": "search_cases",
                    "description": "Search for similar cases based on a scenario description",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query or scenario description"
                            },
                            "domain": {
                                "type": "string",
                                "description": "Domain to search in (military-medical-triage, engineering-ethics, us-law-practice)",
                                "enum": ["military-medical-triage", "engineering-ethics", "us-law-practice"]
                            },
                            "limit": {
                                "type": "number",
                                "description": "Maximum number of results to return"
                            }
                        },
                        "required": ["query"]
                    }
                },
                {
                    "name": "get_world_entities",
                    "description": "Get entities from a specific world",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "world_name": {
                                "type": "string",
                                "description": "Name of the world (e.g., military-medical-triage)",
                                "enum": ["military-medical-triage"]
                            },
                            "entity_type": {
                                "type": "string",
                                "description": "Type of entity to retrieve (characters, conditions, resources, all)",
                                "enum": ["characters", "conditions", "resources", "all"]
                            }
                        },
                        "required": ["world_name"]
                    }
                }
            ]
        }
    
    async def _handle_call_tool(self, params):
        """Handle request to call a tool."""
        tool_name = params.get("name")
        args = params.get("arguments", {})
        
        if tool_name == "search_cases":
            if "query" not in args:
                return {
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: query"
                    }
                }
            
            query = args["query"]
            limit = args.get("limit", 5)
            domain = args.get("domain", "military-medical-triage")
            
            # This would typically involve vector search
            # For now, we'll return domain-specific placeholder results
            if domain == "military-medical-triage":
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "query": query,
                                "domain": domain,
                                "results": [
                                    {
                                        "id": 1,
                                        "title": "Field Hospital Mass Casualty",
                                        "description": "Field hospital receiving multiple casualties from an IED attack with limited resources",
                                        "decision": "Prioritized treatment based on severity and survivability",
                                        "outcome": "Maximized survival rates but some potentially salvageable patients were classified as expectant",
                                        "ethical_analysis": "Utilitarian approach maximized overall survival but raised concerns about individual rights",
                                        "relevance": 0.85
                                    },
                                    {
                                        "id": 2,
                                        "title": "Civilian and Military Casualties",
                                        "description": "Mixed civilian and military casualties with limited evacuation capacity",
                                        "decision": "Evacuated based on medical need regardless of status",
                                        "outcome": "Aligned with humanitarian principles but delayed return of some military personnel to duty",
                                        "ethical_analysis": "Prioritized medical ethics over military necessity, reflecting deontological principles",
                                        "relevance": 0.72
                                    }
                                ]
                            }, indent=2)
                        }
                    ]
                }
            else:
                # Default to military medical triage if domain not recognized
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "query": query,
                                "domain": "military-medical-triage",
                                "message": f"Domain '{domain}' not recognized, defaulting to military-medical-triage",
                                "results": [
                                    {
                                        "id": 1,
                                        "title": "Field Hospital Mass Casualty",
                                        "description": "Field hospital receiving multiple casualties from an IED attack with limited resources",
                                        "decision": "Prioritized treatment based on severity and survivability",
                                        "outcome": "Maximized survival rates but some potentially salvageable patients were classified as expectant",
                                        "ethical_analysis": "Utilitarian approach maximized overall survival but raised concerns about individual rights",
                                        "relevance": 0.85
                                    }
                                ]
                            }, indent=2)
                        }
                    ]
                }
        elif tool_name == "get_world_entities":
            if "world_name" not in args:
                return {
                    "error": {
                        "code": -32602,
                        "message": "Missing required parameter: world_name"
                    }
                }
            
            world_name = args["world_name"]
            entity_type = args.get("entity_type", "all")
            
            if world_name == "military-medical-triage":
                entities = {
                    "world": "Military Medical Triage",
                    "entities": {}
                }
                
                if entity_type == "all" or entity_type == "characters":
                    entities["entities"]["characters"] = [
                        {
                            "id": "mmt:Patient1",
                            "type": "Patient",
                            "label": "Patient 1",
                            "conditions": ["mmt:Hemorrhage1"],
                            "triage_category": "mmt:Immediate"
                        },
                        {
                            "id": "mmt:Patient2",
                            "type": "Patient",
                            "label": "Patient 2",
                            "conditions": ["mmt:Fracture1"],
                            "triage_category": "mmt:Delayed"
                        },
                        {
                            "id": "mmt:Patient3",
                            "type": "Patient",
                            "label": "Patient 3",
                            "conditions": ["mmt:BurnInjury1"],
                            "triage_category": "mmt:Minimal"
                        },
                        {
                            "id": "mmt:Medic1",
                            "type": "Medic",
                            "label": "Combat Medic",
                            "resources": ["mmt:Tourniquet1", "mmt:Bandage1", "mmt:Morphine1"]
                        }
                    ]
                
                if entity_type == "all" or entity_type == "conditions":
                    entities["entities"]["conditions"] = [
                        {
                            "id": "mmt:Hemorrhage1",
                            "type": "Hemorrhage",
                            "label": "Severe Hemorrhage",
                            "severity": "Severe",
                            "location": "Left Leg"
                        },
                        {
                            "id": "mmt:Fracture1",
                            "type": "Fracture",
                            "label": "Compound Fracture",
                            "severity": "Moderate",
                            "location": "Right Arm"
                        },
                        {
                            "id": "mmt:BurnInjury1",
                            "type": "BurnInjury",
                            "label": "First Degree Burn",
                            "severity": "Mild",
                            "location": "Left Hand"
                        }
                    ]
                
                if entity_type == "all" or entity_type == "resources":
                    entities["entities"]["resources"] = [
                        {
                            "id": "mmt:Tourniquet1",
                            "type": "Tourniquet",
                            "label": "Combat Application Tourniquet",
                            "quantity": 2
                        },
                        {
                            "id": "mmt:Bandage1",
                            "type": "Bandage",
                            "label": "Pressure Bandage",
                            "quantity": 5
                        },
                        {
                            "id": "mmt:Morphine1",
                            "type": "Morphine",
                            "label": "Morphine Autoinjector",
                            "quantity": 3
                        }
                    ]
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(entities, indent=2)
                        }
                    ]
                }
            else:
                return {
                    "error": {
                        "code": -32602,
                        "message": f"Invalid world_name: {world_name}. Must be one of: military-medical-triage"
                    }
                }
        else:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Unknown tool: {tool_name}"
                }
            }

# Main entry point
if __name__ == "__main__":
    server = EthicalDMServer()
    asyncio.run(server.run())
