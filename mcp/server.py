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
                }
            ]
        }
    
    async def handle_read_resource(self, request):
        """Handle request to read a resource."""
        uri = request.params.uri
        
        # Handle static resources
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
                            "outcome": {
                                "type": "string",
                                "description": "Outcome of the decision"
                            },
                            "ethical_analysis": {
                                "type": "string",
                                "description": "Ethical analysis of the case"
                            }
                        },
                        "required": ["title", "description", "decision"]
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
            
            # This would typically involve vector search
            # For now, we'll return placeholder results
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "query": query,
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
        elif tool_name == "add_case":
            required_fields = ["title", "description", "decision"]
            for field in required_fields:
                if field not in args:
                    raise McpError(
                        ErrorCode.InvalidParams,
                        f"Missing required parameter: {field}"
                    )
            
            # This would typically involve adding to a database
            # For now, we'll just return success
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": True,
                            "message": "Case added successfully",
                            "case_id": 3  # Placeholder ID
                        }, indent=2)
                    }
                ]
            }
        
        # Tool not found
        raise McpError(
            ErrorCode.MethodNotFound,
            f"Tool not found: {tool_name}"
        )
    
    async def run(self):
        """Run the MCP server."""
        transport = StdioServerTransport()
        await self.server.connect(transport)
        print("Ethical DM MCP server running on stdio", file=sys.stderr)

if __name__ == "__main__":
    import asyncio
    
    server = EthicalDMServer()
    asyncio.run(server.run())
