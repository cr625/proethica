#!/usr/bin/env python3
from modelcontextprotocol.sdk.server import Server
from modelcontextprotocol.sdk.server.stdio import StdioServerTransport
from modelcontextprotocol.sdk.types import (
    CallToolRequestSchema,
    ErrorCode,
    ListResourcesRequestSchema,
    ListResourceTemplatesRequestSchema,
    ListToolsRequestSchema,
    McpError,
    ReadResourceRequestSchema,
)
import json
import os
import sys
import asyncio

class EthicalDMServer:
    """MCP server for the AI Ethical Decision-Making Simulator."""
    
    def __init__(self):
        """Initialize the MCP server."""
        self.server = Server(
            {
                "name": "ethical-dm-server",
                "version": "0.1.0",
            },
            {
                "capabilities": {
                    "resources": {},
                    "tools": {},
                },
            }
        )
        
        # Setup handlers
        self.setup_resource_handlers()
        self.setup_tool_handlers()
        
        # Error handling
        self.server.onerror = lambda error: print(f"[MCP Error] {error}", file=sys.stderr)
        
    def setup_resource_handlers(self):
        """Set up handlers for MCP resources."""
        
        # List available resources
        self.server.setRequestHandler(ListResourcesRequestSchema, async_handler=self.handle_list_resources)
        
        # List resource templates
        self.server.setRequestHandler(ListResourceTemplatesRequestSchema, async_handler=self.handle_list_resource_templates)
        
        # Read resource
        self.server.setRequestHandler(ReadResourceRequestSchema, async_handler=self.handle_read_resource)
    
    def setup_tool_handlers(self):
        """Set up handlers for MCP tools."""
        
        # List available tools
        self.server.setRequestHandler(ListToolsRequestSchema, async_handler=self.handle_list_tools)
        
        # Call tool
        self.server.setRequestHandler(CallToolRequestSchema, async_handler=self.handle_call_tool)
    
    async def handle_list_resources(self, request):
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
                },
                # Engineering Ethics
                {
                    "uri": "ethical-dm://guidelines/engineering-ethics",
                    "name": "Engineering Ethics Guidelines",
                    "mimeType": "application/json",
                    "description": "Guidelines for engineering ethics scenarios"
                },
                {
                    "uri": "ethical-dm://cases/engineering-ethics",
                    "name": "Engineering Ethics Case Repository",
                    "mimeType": "application/json",
                    "description": "Repository of past engineering ethics cases"
                },
                # US Law Practice
                {
                    "uri": "ethical-dm://guidelines/us-law-practice",
                    "name": "US Law Practice Guidelines",
                    "mimeType": "application/json",
                    "description": "Guidelines for US law practice scenarios"
                },
                {
                    "uri": "ethical-dm://cases/us-law-practice",
                    "name": "US Law Practice Case Repository",
                    "mimeType": "application/json",
                    "description": "Repository of past US law practice cases"
                }
            ]
        }
    
    async def handle_list_resource_templates(self, request):
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
    
    async def handle_read_resource(self, request):
        """Handle request to read a resource."""
        uri = request.params.uri
        
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
                raise McpError(
                    ErrorCode.InternalError,
                    f"Error reading ontology file: {str(e)}"
                )
        
        # Handle Engineering Ethics resources
        elif uri == "ethical-dm://guidelines/engineering-ethics":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "guidelines": [
                                {
                                    "name": "Engineering Code of Ethics",
                                    "description": "Professional code of ethics for engineers",
                                    "principles": [
                                        "Hold paramount the safety, health, and welfare of the public",
                                        "Perform services only in areas of their competence",
                                        "Issue public statements only in an objective and truthful manner",
                                        "Act for each employer or client as faithful agents or trustees",
                                        "Avoid deceptive acts",
                                        "Conduct themselves honorably, responsibly, ethically, and lawfully"
                                    ]
                                },
                                {
                                    "name": "Risk Assessment Framework",
                                    "description": "Framework for assessing engineering risks",
                                    "steps": [
                                        "Identify potential hazards",
                                        "Assess likelihood and severity",
                                        "Develop mitigation strategies",
                                        "Implement controls",
                                        "Monitor and review"
                                    ]
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
        elif uri == "ethical-dm://cases/engineering-ethics":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "cases": [
                                {
                                    "id": 1,
                                    "title": "Challenger Disaster",
                                    "description": "Engineers raised concerns about O-ring performance in cold temperatures but were overruled",
                                    "decision": "Launch proceeded despite engineering concerns",
                                    "outcome": "Catastrophic failure resulting in loss of life",
                                    "ethical_analysis": "Failure to prioritize safety over schedule pressures; whistleblowing responsibilities"
                                },
                                {
                                    "id": 2,
                                    "title": "Software Safety Critical System",
                                    "description": "Deadline pressure to release software with known but rare edge case bugs",
                                    "decision": "Delayed release to fix critical safety issues despite business pressure",
                                    "outcome": "Short-term financial impact but maintained safety record and professional integrity",
                                    "ethical_analysis": "Prioritized public safety over business concerns; professional responsibility"
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
            
        # Handle US Law Practice resources
        elif uri == "ethical-dm://guidelines/us-law-practice":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "guidelines": [
                                {
                                    "name": "ABA Model Rules of Professional Conduct",
                                    "description": "Ethical standards for legal professionals",
                                    "principles": [
                                        "Client-Lawyer Relationship",
                                        "Counselor",
                                        "Advocate",
                                        "Transactions with Persons Other Than Clients",
                                        "Law Firms and Associations",
                                        "Public Service",
                                        "Information About Legal Services",
                                        "Maintaining the Integrity of the Profession"
                                    ]
                                },
                                {
                                    "name": "Legal Ethics Framework",
                                    "description": "Framework for ethical decision-making in legal practice",
                                    "considerations": [
                                        "Confidentiality and attorney-client privilege",
                                        "Conflicts of interest",
                                        "Duty of candor to the tribunal",
                                        "Fairness to opposing party and counsel",
                                        "Impartiality and decorum of the tribunal",
                                        "Truthfulness in statements to others",
                                        "Professional independence"
                                    ]
                                }
                            ]
                        }, indent=2)
                    }
                ]
            }
        elif uri == "ethical-dm://cases/us-law-practice":
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "cases": [
                                {
                                    "id": 1,
                                    "title": "Confidentiality vs. Preventing Harm",
                                    "description": "Attorney learns client plans to commit a violent crime",
                                    "decision": "Disclosed minimum information necessary to prevent harm",
                                    "outcome": "Prevented harm while maintaining most of client confidentiality",
                                    "ethical_analysis": "Balanced duty of confidentiality with duty to prevent harm to others"
                                },
                                {
                                    "id": 2,
                                    "title": "Discovery Document Dilemma",
                                    "description": "Attorney discovers damaging document not requested in discovery",
                                    "decision": "Advised client of obligation to disclose relevant information",
                                    "outcome": "Maintained ethical standards and professional integrity",
                                    "ethical_analysis": "Upheld duties of candor to tribunal and fairness to opposing counsel"
                                }
                            ]
                        }, indent=2)
                    }
                ]
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
                    raise McpError(
                        ErrorCode.InvalidRequest,
                        f"World not found: {world_name}"
                    )
        
        # Resource not found
        raise McpError(
            ErrorCode.InvalidRequest,
            f"Resource not found: {uri}"
        )
    
    async def handle_list_tools(self, request):
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
                    "name": "add_case",
                    "description": "Add a new case to the repository",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Case title"
                            },
                            "description": {
                                "type": "string",
                                "description": "Case description"
                            },
                            "decision": {
                                "type": "string",
                                "description": "Decision made in the case"
                            },
                            "domain": {
                                "type": "string",
                                "description": "Domain for the case (military-medical-triage, engineering-ethics, us-law-practice)",
                                "enum": ["military-medical-triage", "engineering-ethics", "us-law-practice"]
                            },
                            "outcome": {
                                "type": "string",
                                "description": "Outcome of the decision"
                            },
                            "ethical_analysis": {
                                "type": "string",
                                "description": "Ethical analysis of the case"
                            }
                        },
                        "required": ["title", "description", "decision", "domain"]
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
                },
                {
                    "name": "create_world",
                    "description": "Create a new world with entities",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Name of the world"
                            },
                            "description": {
                                "type": "string",
                                "description": "Description of the world"
                            },
                            "ontology_source": {
                                "type": "string",
                                "description": "Source of the ontology (e.g., UMLS, SNOMED CT)"
                            },
                            "entities": {
                                "type": "object",
                                "description": "Entities in the world",
                                "properties": {
                                    "characters": {
                                        "type": "array",
                                        "items": {
                                            "type": "object"
                                        }
                                    },
                                    "conditions": {
                                        "type": "array",
                                        "items": {
                                            "type": "object"
                                        }
                                    },
                                    "resources": {
                                        "type": "array",
                                        "items": {
                                            "type": "object"
                                        }
                                    }
                                }
                            }
                        },
                        "required": ["name", "description"]
                    }
                }
            ]
        }
    
    async def handle_call_tool(self, request):
        """Handle request to call a tool."""
        tool_name = request.params.name
        args = request.params.arguments
        
        if tool_name == "search_cases":
            if "query" not in args:
                raise McpError(
                    ErrorCode.InvalidParams,
                    "Missing required parameter: query"
                )
            
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
            elif domain == "engineering-ethics":
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
                                        "title": "Challenger Disaster",
                                        "description": "Engineers raised concerns about O-ring performance in cold temperatures but were overruled",
                                        "decision": "Launch proceeded despite engineering concerns",
                                        "outcome": "Catastrophic failure resulting in loss of life",
                                        "ethical_analysis": "Failure to prioritize safety over schedule pressures; whistleblowing responsibilities",
                                        "relevance": 0.88
                                    },
                                    {
                                        "id": 2,
                                        "title": "Software Safety Critical System",
                                        "description": "Deadline pressure to release software with known but rare edge case bugs",
                                        "decision": "Delayed release to fix critical safety issues despite business pressure",
                                        "outcome": "Short-term financial impact but maintained safety record and professional integrity",
                                        "ethical_analysis": "Prioritized public safety over business concerns; professional responsibility",
                                        "relevance": 0.75
                                    }
                                ]
                            }, indent=2)
                        }
                    ]
                }
            elif domain == "us-law-practice":
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
                                        "title": "Confidentiality vs. Preventing Harm",
                                        "description": "Attorney learns client plans to commit a violent crime",
                                        "decision": "Disclosed minimum information necessary to prevent harm",
                                        "outcome": "Prevented harm while maintaining most of client confidentiality",
                                        "ethical_analysis": "Balanced duty of confidentiality with duty to prevent harm to others",
                                        "relevance": 0.91
                                    },
                                    {
                                        "id": 2,
                                        "title": "Discovery Document Dilemma",
                                        "description": "Attorney discovers damaging document not requested in discovery",
                                        "decision": "Advised client of obligation to disclose relevant information",
                                        "outcome": "Maintained ethical standards and professional integrity",
                                        "ethical_analysis": "Upheld duties of candor to tribunal and fairness to opposing counsel",
                                        "relevance": 0.79
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
        elif tool_name == "add_case":
            required_fields = ["title", "description", "decision", "domain"]
            for field in required_fields:
                if field not in args:
                    raise McpError(
                        ErrorCode.InvalidParams,
                        f"Missing required parameter: {field}"
                    )
            
            domain = args["domain"]
            if domain not in ["military-medical-triage", "engineering-ethics", "us-law-practice"]:
                raise McpError(
                    ErrorCode.InvalidParams,
                    f"Invalid domain: {domain}. Must be one of: military-medical-triage, engineering-ethics, us-law-practice"
                )
            
            # This would typically involve adding to a database
            # For now, we'll just return success
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": True,
                            "message": f"Case added successfully to {domain} domain",
                            "case_id": 3,  # Placeholder ID
                            "domain": domain
                        }, indent=2)
                    }
                ]
            }
        elif tool_name == "get_world_entities":
            if "world_name" not in args:
                raise McpError(
                    ErrorCode.InvalidParams,
                    "Missing required parameter: world_name"
                )
            
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
                            "resources": ["mmt:Tourniquet1", "mmt:Bandage1", "
