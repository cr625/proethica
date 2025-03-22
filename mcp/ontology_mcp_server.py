#!/usr/bin/env python3
import json
import os
import sys
import asyncio
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL

# Configurable environment setup
ONTOLOGY_DIR = os.environ.get("ONTOLOGY_DIR", os.path.join(os.path.dirname(__file__), "ontology"))
DEFAULT_DOMAIN = os.environ.get("DEFAULT_DOMAIN", "military-medical-triage")

class OntologyMCPServer:
    def __init__(self):
        self.jsonrpc_id = 0
        self.MMT = Namespace("http://example.org/military-medical-triage#")

    def _load_graph_from_file(self, ontology_file):
        g = Graph()
        if not ontology_file:
            print(f"Error: No ontology file specified", file=sys.stderr)
            return g
            
        ontology_path = os.path.join(ONTOLOGY_DIR, ontology_file)
        try:
            if not os.path.exists(ontology_path):
                print(f"Error: Ontology file not found: {ontology_path}", file=sys.stderr)
                return g
                
            g.parse(ontology_path, format="turtle")
            print(f"Successfully loaded ontology from {ontology_path}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to load ontology: {str(e)}", file=sys.stderr)
        return g

    async def run(self):
        print("Ontology MCP server running on stdio", file=sys.stderr)
        while True:
            try:
                request_line = await self._read_line()
                if not request_line:
                    continue
                request = json.loads(request_line)
                response = await self._process_request(request)
                print(json.dumps(response), flush=True)
            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {"code": -32000, "message": f"Internal error: {str(e)}"},
                    "id": self.jsonrpc_id
                }
                print(json.dumps(error_response), flush=True)

    async def _read_line(self):
        return sys.stdin.readline().strip()

    async def _process_request(self, request):
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        self.jsonrpc_id = request_id

        handlers = {
            "list_resources": self._handle_list_resources,
            "list_resource_templates": self._handle_list_resource_templates,
            "read_resource": self._handle_read_resource,
            "list_tools": self._handle_list_tools,
            "call_tool": self._handle_call_tool
        }

        if method not in handlers:
            return {"jsonrpc": "2.0", "error": {"code": -32601, "message": f"Method not found: {method}"}, "id": request_id}

        result = await handlers[method](params)
        return {"jsonrpc": "2.0", "result": result, "id": request_id}

    async def _handle_list_resources(self, params):
        return {"resources": []}

    async def _handle_list_resource_templates(self, params):
        return {"resourceTemplates": []}

    async def _handle_read_resource(self, params):
        return {"contents": []}

    async def _handle_list_tools(self, params):
        return {"tools": ["get_world_entities"]}

    async def _handle_call_tool(self, params):
        name = params.get("name")
        arguments = params.get("arguments", {})

        if name == "get_world_entities":
            ontology_source = arguments.get("ontology_source")
            entity_type = arguments.get("entity_type", "all")
            g = self._load_graph_from_file(ontology_source)
            entities = self._extract_entities(g, entity_type)
            return {"content": [{"text": json.dumps({"entities": entities})}]}
        return {"content": [{"text": json.dumps({"error": "Unknown tool"})}]}

    def _extract_entities(self, graph, entity_type):
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))

        out = {}
        if entity_type in ("all", "roles"):
            out["roles"] = [
                {"id": str(s), "label": label_or_id(s)}
                for s in graph.subjects(RDF.type, self.MMT.Role)
            ]
        if entity_type in ("all", "conditions"):
            out["conditions"] = [
                {"id": str(s), "label": label_or_id(s)}
                for s in graph.subjects(RDF.type, self.MMT.ConditionType)
            ]
        if entity_type in ("all", "resources"):
            out["resources"] = [
                {"id": str(s), "label": label_or_id(s)}
                for s in graph.subjects(RDF.type, self.MMT.ResourceType)
            ]
        return out

if __name__ == "__main__":
    server = OntologyMCPServer()
    asyncio.run(server.run())
