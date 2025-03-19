#!/usr/bin/env python3
import json
import os
import sys
import asyncio
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

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
            # Read the consolidated RDF file
            try:
                with open(os.path.join(os.path.dirname(__file__), "ontology/military_medical_triage_consolidated.ttl"), "r") as f:
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
                                        "roles": [
                                            {
                                                "id": "mmt:CombatMedic",
                                                "type": "CombatMedic",
                                                "label": "Combat Medic",
                                                "description": "Military healthcare provider trained for battlefield medicine",
                                                "tier": "Tier 1",
                                                "capabilities": ["Basic Life Support", "Trauma Care", "Tactical Combat Casualty Care"]
                                            },
                                            {
                                                "id": "mmt:FlightMedic",
                                                "type": "FlightMedic",
                                                "label": "Flight Medic",
                                                "description": "Specialized medic for aeromedical evacuation",
                                                "tier": "Tier 2",
                                                "capabilities": ["Advanced Life Support", "Critical Care Transport"]
                                            },
                                            {
                                                "id": "mmt:TraumaSurgeon",
                                                "type": "TraumaSurgeon",
                                                "label": "Trauma Surgeon",
                                                "description": "Physician specialized in surgical treatment of injuries",
                                                "tier": "Tier 3",
                                                "capabilities": ["Damage Control Surgery", "Definitive Surgical Care"]
                                            },
                                            {
                                                "id": "mmt:Patient",
                                                "type": "Patient",
                                                "label": "Patient",
                                                "description": "Individual requiring medical care"
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
                                "description": "Type of entity to retrieve (roles, conditions, resources, all)",
                                "enum": ["roles", "conditions", "resources", "all"]
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
                try:
                    # Load and parse the ontology
                    g = Graph()
                    ontology_path = os.path.join(os.path.dirname(__file__), "ontology/military_medical_triage_consolidated.ttl")
                    g.parse(ontology_path, format="turtle")
                    
                    # Define namespaces
                    MMT = Namespace("http://example.org/military-medical-triage#")
                    
                    # Initialize result structure
                    entities = {
                        "world": "Military Medical Triage",
                        "entities": {}
                    }
                    
                    # Extract roles if requested
                    if entity_type == "all" or entity_type == "roles":
                        roles = []
                        
                        # Query for all entities that are roles
                        for s in g.subjects(RDF.type, MMT.Role):
                            if isinstance(s, URIRef):
                                role = {}
                                role["id"] = str(s)
                                
                                # Get label
                                for label in g.objects(s, RDFS.label):
                                    role["label"] = str(label)
                                    break
                                
                                # Get type
                                role["type"] = s.split('#')[-1]
                                
                                # Get description
                                for comment in g.objects(s, RDFS.comment):
                                    role["description"] = str(comment)
                                    break
                                
                                # Get capabilities for roles
                                capabilities = []
                                for capability in g.objects(s, MMT.hasCapability):
                                    for cap_label in g.objects(capability, RDFS.label):
                                        capabilities.append(str(cap_label))
                                        break
                                
                                if capabilities:
                                    role["capabilities"] = capabilities
                                
                                # Get tier for roles
                                for tier in g.objects(s, MMT.hasTier):
                                    for tier_label in g.objects(tier, RDFS.label):
                                        role["tier"] = str(tier_label)
                                        break
                                
                                roles.append(role)
                        
                        # Also add Patient as a role
                        patient_role = {}
                        patient_role["id"] = str(MMT.Patient)
                        patient_role["type"] = "Patient"
                        
                        # Get label
                        for label in g.objects(MMT.Patient, RDFS.label):
                            patient_role["label"] = str(label)
                            break
                        
                        # Get description
                        for comment in g.objects(MMT.Patient, RDFS.comment):
                            patient_role["description"] = str(comment)
                            break
                        
                        roles.append(patient_role)
                        
                        entities["entities"]["roles"] = roles
                    
                    # Extract condition types if requested
                    if entity_type == "all" or entity_type == "conditions":
                        condition_types = []
                        
                        # Query for all entities that are condition types
                        for s in g.subjects(RDF.type, MMT.ConditionType):
                            if isinstance(s, URIRef):
                                cond_type = {}
                                cond_type["id"] = str(s)
                                
                                # Get label
                                for label in g.objects(s, RDFS.label):
                                    cond_type["label"] = str(label)
                                    break
                                
                                # Get type
                                cond_type["type"] = s.split('#')[-1]
                                
                                # Get description
                                for comment in g.objects(s, RDFS.comment):
                                    cond_type["description"] = str(comment)
                                    break
                                
                                condition_types.append(cond_type)
                        
                        # Also include sample individuals
                        for s in g.subjects(None, MMT.severity):
                            if isinstance(s, URIRef):
                                cond = {}
                                cond["id"] = str(s)
                                
                                # Get label
                                for label in g.objects(s, RDFS.label):
                                    cond["label"] = str(label)
                                    break
                                
                                # Get type
                                for _, p, o in g.triples((s, RDF.type, None)):
                                    if o != OWL.NamedIndividual and o != RDFS.Resource:
                                        cond["type"] = o.split('#')[-1]
                                        break
                                
                                # Get severity
                                for severity in g.objects(s, MMT.severity):
                                    cond["severity"] = str(severity)
                                    break
                                
                                # Get location
                                for location in g.objects(s, MMT.location):
                                    cond["location"] = str(location)
                                    break
                                
                                condition_types.append(cond)
                        
                        entities["entities"]["conditions"] = condition_types
                    
                    # Extract resource types if requested
                    if entity_type == "all" or entity_type == "resources":
                        resource_types = []
                        
                        # Query for all entities that are resource types
                        for s in g.subjects(RDF.type, MMT.ResourceType):
                            if isinstance(s, URIRef):
                                res_type = {}
                                res_type["id"] = str(s)
                                
                                # Get label
                                for label in g.objects(s, RDFS.label):
                                    res_type["label"] = str(label)
                                    break
                                
                                # Get type
                                res_type["type"] = s.split('#')[-1]
                                
                                # Get description
                                for comment in g.objects(s, RDFS.comment):
                                    res_type["description"] = str(comment)
                                    break
                                
                                resource_types.append(res_type)
                        
                        # Also include sample individuals
                        for s in g.subjects(None, MMT.quantity):
                            if isinstance(s, URIRef):
                                res = {}
                                res["id"] = str(s)
                                
                                # Get label
                                for label in g.objects(s, RDFS.label):
                                    res["label"] = str(label)
                                    break
                                
                                # Get type
                                for _, p, o in g.triples((s, RDF.type, None)):
                                    if o != OWL.NamedIndividual and o != RDFS.Resource:
                                        res["type"] = o.split('#')[-1]
                                        break
                                
                                # Get quantity
                                for quantity in g.objects(s, MMT.quantity):
                                    res["quantity"] = int(quantity)
                                    break
                                
                                resource_types.append(res)
                        
                        entities["entities"]["resources"] = resource_types
                    
                    return {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(entities, indent=2)
                            }
                        ]
                    }
                except Exception as e:
                    return {
                        "error": {
                            "code": -32000,
                            "message": f"Error processing ontology: {str(e)}"
                        }
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
