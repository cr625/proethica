#!/usr/bin/env python3
import json
import os
import sys
import asyncio
import rdflib
from rdflib import Graph, Namespace, RDF, RDFS, URIRef
from rdflib.namespace import OWL
from aiohttp import web

# Add the parent directory to the path so we can import mcp as a package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Configurable environment setup
ONTOLOGY_DIR = os.environ.get("ONTOLOGY_DIR", os.path.join(os.path.dirname(__file__), "ontology"))
DEFAULT_DOMAIN = os.environ.get("DEFAULT_DOMAIN", "military-medical-triage")
PORT = int(os.environ.get("MCP_SERVER_PORT", 5001))

class OntologyMCPServer:
    def __init__(self):
        self.jsonrpc_id = 0
        # Define known namespaces
        self.namespaces = {
            "military-medical-triage": Namespace("http://proethica.org/ontology/military-medical-triage#"),
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://proethica.org/ontology/nj-legal-ethics#"),
            "intermediate": Namespace("http://proethica.org/ontology/intermediate#"),
            "proethica-intermediate": Namespace("http://proethica.org/ontology/intermediate#")
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

    def _load_graph_from_file(self, ontology_source):
        """
        Load ontology content primarily from database with file fallback.
        
        Args:
            ontology_source: Source identifier for ontology (domain_id or filename)
            
        Returns:
            RDFLib Graph object with loaded ontology
        """
        g = Graph()
        if not ontology_source:
            print(f"Error: No ontology source specified", file=sys.stderr)
            return g
            
        # Handle cleanup of file extension if present
        if ontology_source.endswith('.ttl'):
            domain_id = ontology_source[:-4]  # Remove .ttl extension
        else:
            domain_id = ontology_source
            
        try:
            # First try to load from database
            # We need to import these here to avoid circular imports
            try:
                # Create a Flask app context for database access
                import os
                from app import create_app, db
                from app.models.ontology import Ontology
                
                app = create_app()
                with app.app_context():
                    # Try to fetch from database
                    print(f"Attempting to load ontology '{domain_id}' from database", file=sys.stderr)
                    ontology = Ontology.query.filter_by(domain_id=domain_id).first()
                    
                    if ontology:
                        print(f"Found ontology '{domain_id}' (ID: {ontology.id}) in database", file=sys.stderr)
                        print(f"Content length: {len(ontology.content)} bytes", file=sys.stderr)
                        
                        g.parse(data=ontology.content, format="turtle")
                        print(f"Successfully parsed ontology content with {len(g)} triples", file=sys.stderr)
                        return g
                    else:
                        print(f"Ontology '{domain_id}' not found in database", file=sys.stderr)
            except Exception as db_error:
                print(f"Error loading from database: {str(db_error)}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)
                
            # Fall back to file (for backward compatibility)
            print(f"Falling back to filesystem for ontology '{domain_id}'", file=sys.stderr)
            ontology_path = os.path.join(ONTOLOGY_DIR, ontology_source)
            if not os.path.exists(ontology_path):
                print(f"Error: Ontology file not found: {ontology_path}", file=sys.stderr)
                return g

            g.parse(ontology_path, format="turtle")
            print(f"Successfully loaded ontology from {ontology_path}", file=sys.stderr)
        except Exception as e:
            print(f"Failed to load ontology: {str(e)}", file=sys.stderr)
        return g

    async def handle_jsonrpc(self, request):
        try:
            request_data = await request.json()
            response = await self._process_request(request_data)
            return web.json_response(response)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": f"Internal error: {str(e)}"},
                "id": self.jsonrpc_id
            }
            return web.json_response(error_response)

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
        # Track potential matches
        matches = {}
        
        # Try to find the ontology declaration
        for s, p, o in graph.triples((None, RDF.type, OWL.Ontology)):
            ontology_uri = str(s)
            if "military-medical-triage" in ontology_uri:
                matches["military-medical-triage"] = 10  # Higher priority
            elif "engineering-ethics" in ontology_uri:
                matches["engineering-ethics"] = 10
            elif "nj-legal-ethics" in ontology_uri:
                matches["nj-legal-ethics"] = 10
            elif "intermediate" in ontology_uri:
                matches["intermediate"] = 10
        
        # Check for namespace prefixes in the graph
        for prefix, namespace in graph.namespaces():
            namespace_str = str(namespace)
            if prefix == "mmt" or "military-medical-triage" in namespace_str:
                matches["military-medical-triage"] = matches.get("military-medical-triage", 0) + 5
            elif prefix == "eng" or "engineering-ethics" in namespace_str:
                matches["engineering-ethics"] = matches.get("engineering-ethics", 0) + 5
            elif prefix == "njle" or "nj-legal-ethics" in namespace_str:
                matches["nj-legal-ethics"] = matches.get("nj-legal-ethics", 0) + 5
            elif prefix == "proeth" or "intermediate" in namespace_str:
                matches["intermediate"] = matches.get("intermediate", 0) + 5
        
        # Look for potential file identifiers in the source filename
        src_file = getattr(graph, 'source', '')
        if isinstance(src_file, str):
            if "military-medical-triage" in src_file:
                matches["military-medical-triage"] = matches.get("military-medical-triage", 0) + 3
            elif "engineering-ethics" in src_file:
                matches["engineering-ethics"] = matches.get("engineering-ethics", 0) + 3
            elif "nj-legal-ethics" in src_file:
                matches["nj-legal-ethics"] = matches.get("nj-legal-ethics", 0) + 3
            elif "intermediate" in src_file or "proethica-intermediate" in src_file:
                matches["intermediate"] = matches.get("intermediate", 0) + 3
        
        # Find the namespace with the highest score
        if matches:
            best_match = max(matches.items(), key=lambda x: x[1])[0]
            return self.namespaces[best_match]
            
        # Default to MMT if no clear match
        return self.MMT

    def _extract_entities(self, graph, entity_type):
        # Detect primary namespace
        namespace = self._detect_namespace(graph)
        
        # Always include the intermediate namespace for entity types
        proeth_namespace = self.namespaces["intermediate"]
        
        def label_or_id(s):
            return str(next(graph.objects(s, RDFS.label), s))
        
        def get_description(s):
            return str(next(graph.objects(s, RDFS.comment), ""))
        
        def safe_get_property(s, prop, default=""):
            try:
                return str(next(graph.objects(s, prop), default))
            except:
                return default

        out = {}
        if entity_type in ("all", "roles"):
            # Look for both namespace.Role and proeth:Role
            role_subjects = set()
            
            # Look for instances linked via rdf:type to Role
            role_subjects.update(graph.subjects(RDF.type, namespace.Role))
            role_subjects.update(graph.subjects(RDF.type, proeth_namespace.Role))
            
            # ADDITIONAL: Look for instances that have both EntityType and Role types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Role) in graph:
                    role_subjects.add(s)
            
            out["roles"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s),
                    "tier": safe_get_property(s, namespace.hasTier),
                    "capabilities": [
                        {
                            "id": str(o),
                            "label": label_or_id(o),
                            "description": get_description(o)
                        } 
                        for o in graph.objects(s, proeth_namespace.hasCapability)
                    ]
                }
                for s in role_subjects
            ]
        
        if entity_type in ("all", "conditions"):
            # Look for both namespace.ConditionType and proeth:ConditionType
            condition_subjects = set()
            condition_subjects.update(graph.subjects(RDF.type, namespace.ConditionType))
            condition_subjects.update(graph.subjects(RDF.type, proeth_namespace.ConditionType))
            
            # ADDITIONAL: Look for instances that have both EntityType and ConditionType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ConditionType) in graph:
                    condition_subjects.add(s)
            
            out["conditions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in condition_subjects
            ]
        
        if entity_type in ("all", "resources"):
            # Look for both namespace.ResourceType and proeth:ResourceType
            resource_subjects = set()
            resource_subjects.update(graph.subjects(RDF.type, namespace.ResourceType))
            resource_subjects.update(graph.subjects(RDF.type, proeth_namespace.ResourceType))
            
            # ADDITIONAL: Look for instances that have both EntityType and ResourceType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ResourceType) in graph:
                    resource_subjects.add(s)
            
            out["resources"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in resource_subjects
            ]
        
        if entity_type in ("all", "events"):
            # Look for both namespace.EventType and proeth:EventType
            event_subjects = set()
            event_subjects.update(graph.subjects(RDF.type, namespace.EventType))
            event_subjects.update(graph.subjects(RDF.type, proeth_namespace.EventType))
            
            # ADDITIONAL: Look for instances that have both EntityType and EventType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.EventType) in graph:
                    event_subjects.add(s)
            
            out["events"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in event_subjects
            ]
        
        if entity_type in ("all", "actions"):
            # Look for both namespace.ActionType and proeth:ActionType
            action_subjects = set()
            action_subjects.update(graph.subjects(RDF.type, namespace.ActionType))
            action_subjects.update(graph.subjects(RDF.type, proeth_namespace.ActionType))
            
            # ADDITIONAL: Look for instances that have both EntityType and ActionType types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.ActionType) in graph:
                    action_subjects.add(s)
            
            out["actions"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in action_subjects
            ]
            
        if entity_type in ("all", "capabilities"):
            # Look for capability types
            capability_subjects = set()
            capability_subjects.update(graph.subjects(RDF.type, namespace.Capability))
            capability_subjects.update(graph.subjects(RDF.type, proeth_namespace.Capability))
            
            # ADDITIONAL: Look for instances that have both EntityType and Capability types
            entity_type_subjects = set(graph.subjects(RDF.type, proeth_namespace.EntityType))
            for s in entity_type_subjects:
                if (s, RDF.type, proeth_namespace.Capability) in graph:
                    capability_subjects.add(s)
            
            # Also get capabilities that are associated with roles
            for role in graph.subjects(RDF.type, namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
            for role in graph.subjects(RDF.type, proeth_namespace.Role):
                capability_subjects.update(graph.objects(role, proeth_namespace.hasCapability))
                
            out["capabilities"] = [
                {
                    "id": str(s), 
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                for s in capability_subjects
            ]
            
        # Log what was found for debugging
        for entity_type, entity_list in out.items():
            print(f"Found {len(entity_list)} {entity_type} in ontology", file=sys.stderr)
            
        return out

    # API routes for direct access
    async def handle_get_entities(self, request):
        ontology_source = request.match_info.get('ontology_source', '')
        g = self._load_graph_from_file(ontology_source)
        entities = self._extract_entities(g, "all")
        return web.json_response({"entities": entities})

    async def handle_get_guidelines(self, request):
        world_name = request.match_info.get('world_name', '')
        # Mock guidelines for different worlds
        mock_guidelines = {
            "engineering-ethics": [
                {
                    "name": "Engineering Code of Ethics",
                    "description": "Engineers shall hold paramount the safety, health, and welfare of the public in the performance of their professional duties.",
                    "principles": [
                        "Engineers shall recognize that the lives, safety, health and welfare of the general public are dependent upon engineering judgments, decisions and practices incorporated into structures, machines, products, processes and devices.",
                        "Engineers shall approve or seal only those design documents, reviewed or prepared by them, which are determined to be safe for public health and welfare in conformity with accepted engineering standards.",
                        "Engineers shall not reveal facts, data or information obtained in a professional capacity without the prior consent of the client or employer except as authorized or required by law.",
                        "Engineers shall act in professional matters for each employer or client as faithful agents or trustees.",
                        "Engineers shall disclose all known or potential conflicts of interest to their employers or clients by promptly informing them of any business association, interest, or other circumstances which could influence or appear to influence their judgment or the quality of their services."
                    ],
                    "factors": [
                        "Public safety and welfare",
                        "Professional competence",
                        "Truthfulness and objectivity",
                        "Confidentiality",
                        "Conflicts of interest",
                        "Professional development"
                    ]
                }
            ],
            "military-medical-ethics": [
                {
                    "name": "Military Medical Triage Guidelines",
                    "description": "Triage is the process of sorting casualties based on the severity of injury and likelihood of survival to determine treatment priority.",
                    "principles": [
                        "Maximize the number of lives saved",
                        "Allocate scarce resources efficiently",
                        "Treat patients according to medical need and urgency",
                        "Reassess patients regularly",
                        "Document decisions and rationales"
                    ],
                    "categories": [
                        {
                            "name": "Immediate (T1/Red)",
                            "description": "Casualties who require immediate life-saving intervention. Without immediate treatment, they will likely die within 1-2 hours."
                        },
                        {
                            "name": "Delayed (T2/Yellow)",
                            "description": "Casualties whose treatment can be delayed without significant risk to life or limb. They require medical care but can wait hours without serious consequences."
                        },
                        {
                            "name": "Minimal (T3/Green)",
                            "description": "Casualties with minor injuries who can effectively care for themselves or be helped by untrained personnel."
                        },
                        {
                            "name": "Expectant (T4/Black)",
                            "description": "Casualties who are so severely injured that they are unlikely to survive given the available resources. In mass casualty situations, these patients receive palliative care rather than resource-intensive interventions."
                        }
                    ],
                    "considerations": [
                        "Available medical resources (personnel, equipment, supplies)",
                        "Number and types of casualties",
                        "Environmental conditions",
                        "Evacuation capabilities",
                        "Ongoing threats or hazards"
                    ]
                }
            ],
            "legal-ethics": [
                {
                    "name": "Legal Ethics Guidelines",
                    "description": "Lawyers must maintain the highest standards of ethical conduct. These guidelines outline the ethical responsibilities of legal professionals.",
                    "principles": [
                        "Competence: Lawyers shall provide competent representation to clients.",
                        "Confidentiality: Lawyers shall not reveal information relating to the representation of a client unless the client gives informed consent.",
                        "Conflicts of Interest: Lawyers shall not represent a client if the representation involves a concurrent conflict of interest.",
                        "Candor: Lawyers shall not knowingly make a false statement of fact or law to a tribunal.",
                        "Fairness: Lawyers shall deal fairly with all parties in legal proceedings."
                    ],
                    "steps": [
                        "Identify the ethical issue",
                        "Consult relevant rules and precedents",
                        "Consider all stakeholders affected",
                        "Evaluate alternative courses of action",
                        "Make a decision and implement it",
                        "Reflect on the outcome and learn from it"
                    ]
                }
            ]
        }
        
        # Return mock guidelines for the specified world or empty dictionary if not found
        return web.json_response({"guidelines": mock_guidelines.get(world_name, [])})

async def run_server():
    server = OntologyMCPServer()
    app = web.Application()
    
    # Import and register the temporal module
    from mcp.modules.temporal_module import TemporalModule
    temporal_module = TemporalModule()
    
    # Register temporal endpoints directly in the unified server
    
    # JSON-RPC endpoint
    app.router.add_post('/jsonrpc', server.handle_jsonrpc)
    
    # Direct API endpoints
    app.router.add_get('/api/ontology/{ontology_source}/entities', server.handle_get_entities)
    app.router.add_get('/api/guidelines/{world_name}', server.handle_get_guidelines)
    
    # CORS middleware
    @web.middleware
    async def cors_middleware(request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    app.middlewares.append(cors_middleware)
    
    # Start the server
    print(f"Starting HTTP MCP server on port {PORT}", file=sys.stderr)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', PORT)
    await site.start()
    
    # Keep the server running
    while True:
        await asyncio.sleep(3600)  # Sleep for an hour

if __name__ == "__main__":
    asyncio.run(run_server())
