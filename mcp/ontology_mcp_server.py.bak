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
        # Define known namespaces
        self.namespaces = {
            "military-medical-triage": Namespace("http://proethica.org/ontology/military-medical-triage#"),
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://proethica.org/ontology/nj-legal-ethics#")
        }
        # Default namespace
        self.MMT = self.namespaces["military-medical-triage"]
    
    def register_namespace(self, key, uri):
        """
        Register a new namespace for use with ontologies.
        
        Args:
            key: Key to identify the namespace (e.g., 'legal-ethics')
            uri: URI for the namespace (e.g., 'http://example.org/legal-ethics#')
            
        Returns:
            The namespace object
        """
        namespace = Namespace(uri)
        self.namespaces[key] = namespace
        return namespace

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
                    await asyncio.sleep(0.01)  # Add a small delay to reduce CPU usage when idle
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

    def _detect_namespace(self, graph):
        """Detect the primary namespace used in the ontology."""
        # Try to find the ontology declaration
        for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
            ontology_uri = str(s)
            if "military-medical-triage" in ontology_uri:
                return self.namespaces["military-medical-triage"]
            elif "engineering-ethics" in ontology_uri:
                return self.namespaces["engineering-ethics"]
            elif "nj-legal-ethics" in ontology_uri:
                return self.namespaces["nj-legal-ethics"]
        
        # Check for namespace prefixes in the graph
        for prefix, namespace in graph.namespaces():
            namespace_str = str(namespace)
            if prefix == "mmt" or "military-medical-triage" in namespace_str:
                return self.namespaces["military-medical-triage"]
            elif prefix == "eng" or "engineering-ethics" in namespace_str:
                return self.namespaces["engineering-ethics"]
            elif prefix == "njle" or "nj-legal-ethics" in namespace_str:
                return self.namespaces["nj-legal-ethics"]
            
        # Check for common entity types in each namespace
        for namespace_key, namespace in self.namespaces.items():
            # Check if any entities with this namespace's Role type exist
            if any(graph.subjects(RDF.type, namespace.Role)):
                return namespace
        
        # Default to MMT if not found
        return self.MMT

    def _extract_entities(self, graph, entity_type):
        # Detect namespace
        namespace = self._detect_namespace(graph)
        
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))

        out = {}
        if entity_type in ("all", "roles"):
            out["roles"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "tier": str(next(graph.objects(s, namespace.hasTier), "")),
                    "capabilities": [str(o) for o in graph.objects(s, namespace.hasCapability)]
                }
                for s in graph.subjects(RDF.type, namespace.Role)
            ]
        if entity_type in ("all", "conditions"):
            out["conditions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "type": str(next((o for o in graph.objects(s, RDF.type) if o != namespace.ConditionType), "")),
                    "severity": str(next(graph.objects(s, namespace.severity), "")),
                    "location": str(next(graph.objects(s, namespace.location), ""))
                }
                for s in graph.subjects(RDF.type, namespace.ConditionType)
            ]
        if entity_type in ("all", "resources"):
            out["resources"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "type": str(next((o for o in graph.objects(s, RDF.type) if o != namespace.ResourceType), "")),
                    "quantity": str(next(graph.objects(s, namespace.quantity), ""))
                }
                for s in graph.subjects(RDF.type, namespace.ResourceType)
            ]
        if entity_type in ("all", "events"):
            out["events"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "type": str(next((o for o in graph.objects(s, RDF.type) if o != namespace.EventType), "")),
                    "severity": str(next(graph.objects(s, namespace.eventSeverity), "")),
                    "location": str(next(graph.objects(s, namespace.eventLocation), ""))
                }
                for s in graph.subjects(RDF.type, namespace.EventType)
            ]
        if entity_type in ("all", "actions"):
            out["actions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "type": str(next((o for o in graph.objects(s, RDF.type) if o != namespace.ActionType), "")),
                    "priority": str(next(graph.objects(s, namespace.actionPriority), "")),
                    "duration": str(next(graph.objects(s, namespace.actionDuration), ""))
                }
                for s in graph.subjects(RDF.type, namespace.ActionType)
            ]
        return out

if __name__ == "__main__":
    server = OntologyMCPServer()
    asyncio.run(server.run())
