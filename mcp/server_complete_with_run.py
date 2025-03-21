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
        # Load ontology files
        self.graph = self._load_ontology_files()
        # Define namespace
        self.MMT = Namespace("http://example.org/military-medical-triage#")
    
    def _load_ontology_files(self):
        """Load all ontology files into a single graph."""
        g = Graph()
        ontology_path = os.path.dirname(__file__)
        try:
            # Load the consolidated file if it exists
            g.parse(os.path.join(ontology_path, "ontology/military_medical_triage_consolidated.ttl"), format="turtle")
        except Exception as e:
            print(f"Error loading consolidated ontology: {str(e)}", file=sys.stderr)
            
            # Try loading individual files if consolidated fails
            try:
                g.parse(os.path.join(ontology_path, "ontology/military_medical_triage.ttl"), format="turtle")
                g.parse(os.path.join(ontology_path, "ontology/military_medical_triage_roles.ttl"), format="turtle")
            except Exception as e:
                print(f"Error loading ontology files: {str(e)}", file=sys.stderr)
                
        return g
    
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
        # Get world definition from ontology
        world_label = None
        world_comment = None
        for s, p, o in self.graph.triples((None, RDF.type, OWL.Ontology)):
            for label in self.graph.objects(s, RDFS.label):
                world_label = str(label)
            for comment in self.graph.objects(s, RDFS.comment):
                world_comment = str(comment)
                break
        
        if not world_label:
            world_label = "Military Medical Triage"
        
        if not world_comment:
            world_comment = "Ontology for military medical triage world"
            
        return {
            "resources": [
                # Military Medical Triage
                {
                    "uri": "ethical-dm://guidelines/military-medical-triage",
                    "name": f"{world_label} Guidelines",
                    "mimeType": "application/json",
                    "description": f"Guidelines for {world_label.lower()} scenarios"
                },
                {
                    "uri": "ethical-dm://cases/military-medical-triage",
                    "name": f"{world_label} Case Repository",
                    "mimeType": "application/json",
                    "description": f"Repository of past {world_label.lower()} cases"
                },
                {
                    "uri": "ethical-dm://worlds/military-medical-triage",
                    "name": world_label,
                    "mimeType": "application/rdf+xml",
                    "description": world_comment
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
            # Get triage categories from ontology
            triage_categories = []
            for s in self.graph.subjects(RDF.type, self.MMT.TriageCategory):
                category = {}
                for s_class in self.graph.subjects(RDFS.subClassOf, self.MMT.TriageCategory):
                    if s == s_class:
                        for label in self.graph.objects(s, RDFS.label):
                            category["name"] = str(label)
                        for comment in self.graph.objects(s, RDFS.comment):
                            category["description"] = str(comment)
                        if category:
                            triage_categories.append(category)
            
            # If no categories found in ontology, provide defaults
            if not triage_categories:
                triage_categories = [
                    {"name": "Immediate (Red)", "description": "Patients requiring immediate life-saving intervention"},
                    {"name": "Delayed (Yellow)", "description": "Patients with significant injuries but stable for the moment"},
                    {"name": "Minimal (Green)", "description": "Patients with minor injuries who can wait for treatment"},
                    {"name": "Expectant (Black)", "description": "Patients unlikely to survive given severity of injuries and available resources"}
                ]
            
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
                                    "categories": triage_categories
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
            # Get sample patient data from ontology
            cases = []
            patient_id = 1
            
            # Look for patient individuals in the ontology
            for s in self.graph.subjects(RDF.type, self.MMT.Patient):
                if isinstance(s, URIRef):
                    patient_label = None
                    triage_category = None
                    condition_label = None
                    condition_severity = None
                    
                    # Get patient label
                    for label in self.graph.objects(s, RDFS.label):
                        patient_label = str(label)
                        break
                        
                    # Get triage category
                    for o in self.graph.objects(s, self.MMT.hasTriageCategory):
                        for cat_label in self.graph.objects(o, RDFS.label):
                            triage_category = str(cat_label)
                            break
                    
                    # Get condition information
                    for condition in self.graph.objects(s, self.MMT.hasCondition):
                        for cond_label in self.graph.objects(condition, RDFS.label):
                            condition_label = str(cond_label)
                        for severity in self.graph.objects(condition, self.MMT.severity):
                            condition_severity = str(severity)
                        break
                    
                    if patient_label and triage_category and condition_label:
                        if triage_category.startswith("Immediate"):
                            decision = "Prioritized for immediate life-saving intervention"
                            outcome = "Stabilized for further treatment"
                            analysis = "Ethical principle of urgency: treating those at immediate risk of death"
                        elif triage_category.startswith("Delayed"):
                            decision = "Treatment delayed to prioritize more critical patients"
                            outcome = "Condition managed successfully after initial delay"
                            analysis = "Utilitarian approach: maximizing benefit across all patients"
                        elif triage_category.startswith("Minimal"):
                            decision = "Basic first aid provided, advised self-care"
                            outcome = "Recovered without advanced intervention"
                            analysis = "Resource conservation: directing limited resources to those in greater need"
                        else:
                            decision = "Palliative care provided"
                            outcome = "Comfort measures maintained"
                            analysis = "Ethical allocation of limited resources in mass casualty scenario"
                        
                        cases.append({
                            "id": patient_id,
                            "title": f"Patient with {condition_label}",
                            "description": f"Patient classified as {triage_category} with {condition_severity} {condition_label}",
                            "decision": decision,
                            "outcome": outcome,
                            "ethical_analysis": analysis
                        })
                        patient_id += 1
            
            # If no patients found in ontology, provide default cases
            if not cases:
                cases = [
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
            
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": "application/json",
                        "text": json.dumps({
                            "cases": cases
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
                    # This functionality is already implemented with ontology data in _handle_call_tool
                    # for the get_world_entities tool, so we'll reuse that logic
                    entities = await self._extract_world_entities("all")
                    
                    if entities and "entities" in entities:
                        return {
                            "contents": [
                                {
                                    "uri": uri,
                                    "mimeType": "application/json",
                                    "text": json.dumps(entities, indent=2)
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
    
    async def _extract_world_entities(self, entity_type):
        """Extract world entities from the ontology."""
        # Define namespaces
        MMT = self.MMT
        
        # Initialize result structure
        entities = {
            "world": "Military Medical Triage",
            "entities": {}
        }
        
        # Get world name from ontology if available
        for s, p, o in self.graph.triples((None, RDF.type, OWL.Ontology)):
            for label in self.graph.objects(s, RDFS.label):
                entities["world"] = str(label)
                break
        
        # Extract roles if requested
        if entity_type == "all" or entity_type == "roles":
            roles = []
            
            # Query for all entities that are roles
            for s in self.graph.subjects(RDF.type, MMT.Role):
                if isinstance(s, URIRef):
                    role = {}
                    role["id"] = str(s)
                    
                    # Get label
                    for label in self.graph.objects(s, RDFS.label):
                        role["label"] = str(label)
                        break
                    
                    # Get type
                    role["type"] = s.split('#')[-1]
                    
                    # Get description
                    for comment in self.graph.objects(s, RDFS.comment):
                        role["description"] = str(comment)
                        break
                    
                    # Get capabilities for roles
                    capabilities = []
                    for capability in self.graph.objects(s, MMT.hasCapability):
                        for cap_label in self.graph.objects(capability, RDFS.label):
                            capabilities.append(str(cap_label))
                            break
                    
                    if capabilities:
                        role["capabilities"] = capabilities
                    
                    # Get tier for roles
                    for tier in self.graph.objects(s, MMT.hasTier):
                        for tier_label in self.graph.objects(tier, RDFS.label):
                            role["tier"] = str(tier_label)
                            break
                    
                    roles.append(role)
            
            # Also add Patient as a role
            patient_role = {}
            patient_role["id"] = str(MMT.Patient)
            patient_role["type"] = "Patient"
            
            # Get label
            for label in self.graph.objects(MMT.Patient, RDFS.label):
                patient_role["label"] = str(label)
                break
            
            # Get description
            for comment in self.graph.objects(MMT.Patient, RDFS.comment):
                patient_role["description"] = str(comment)
                break
            
            roles.append(patient_role)
            
            entities["entities"]["roles"] = roles
        
        # Extract condition types if requested
        if entity_type == "all" or entity_type == "conditions":
            condition_types = []
            
            # Query for all entities that are condition types
            for s in self.graph.subjects(RDF.type, MMT.ConditionType):
                if isinstance(s, URIRef):
                    cond_type = {}
                    cond_type["id"] = str(s)
                    
                    # Get label
                    for label in self.graph.objects(s, RDFS.label):
                        cond_type["label"] = str(label)
                        break
                    
                    # Get type
                    cond_type["type"] = s.split('#')[-1]
                    
                    # Get description
                    for comment in self.graph.objects(s, RDFS.comment):
                        cond_type["description"] = str(comment)
                        break
                    
                    condition_types.append(cond_type)
            
            # Also include sample individuals
            for s in self.graph.subjects(None, MMT.severity):
                if isinstance(s, URIRef):
                    cond = {}
                    cond["id"] = str(s)
                    
                    # Get label
                    for label in self.graph.objects(s, RDFS.label):
                        cond["label"] = str(label)
                        break
                    
                    # Get type
                    for _, p, o in self.graph.triples((s, RDF.type, None)):
                        if o != OWL.NamedIndividual and o != RDFS.Resource:
                            cond["type"] = o.split('#')[-1]
                            break
                    
                    # Get severity
                    for severity in self.graph.objects(s, MMT.severity):
                        cond["severity"] = str(severity)
                        break
                    
                    # Get location
                    for location in self.graph.objects(s, MMT.location):
                        cond["location"] = str(location)
                        break
                    
                    condition_types.append(cond)
            
            entities["entities"]["conditions"] = condition_types
        
        # Extract resource types if requested
        if entity_type == "all" or entity_type == "resources":
            resource_types = []
            
            # Query for all entities that are resource types
            for s in self.graph.subjects(RDF.type, MMT.ResourceType):
                if isinstance(s, URIRef):
                    res_type = {}
                    res_type["id"] = str(s)
                    
                    # Get label
                    for label in self.graph.objects(s, RDFS.label):
                        res_type["label"] = str(label)
                        break
                    
                    # Get type
                    res_type["type"] = s.split('#')[-1]
                    
                    # Get description
                    for comment in self.graph.objects(s, RDFS.comment):
                        res_type["description"] = str(comment)
                        break
                    
                    resource_types.append(res_type)
            
            # Also include sample individuals
            for s in self.graph.subjects(None, MMT.quantity):
                if isinstance(s, URIRef):
                    res = {}
                    res["id"] = str(s)
                    
                    # Get label
                    for label in self.graph.objects(s, RDFS.label):
                        res["label"] = str(label)
                        break
                    
                    # Get type
                    for _, p, o in self.graph.triples((s, RDF.type, None)):
                        if o != OWL.NamedIndividual and o != RDFS.Resource:
                            res["type"] = o.split('#')[-1]
                            break
                    
                    # Get quantity
                    for quantity in self.graph.objects(s, MMT.quantity):
                        res["quantity"] = int(quantity)
                        break
                    
                    resource_types.append(res)
            
            entities["entities"]["resources"] = resource_types
        
        return entities

    async def _handle_list_tools(self, params):
        """Handle request to list available tools."""
        # Get domain names from ontology
        domains = ["military-medical-triage"]  # Default
        
        # Look for world definitions in ontology
        worlds = []
        for s in self.graph.subjects(RDF.type, OWL.Ontology):
            for label in self.graph.objects(s, RDFS.label):
                world_name = str(label).lower().replace(" ", "-")
                if world_name not in worlds:
                    worlds.append(world_name)
        
        if worlds:
            domains = worlds
        
        # Get entity types from ontology
        entity_types = ["roles", "conditions", "resources", "all"]  # Default
        
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
                                "description": f"Domain to search in ({', '.join(domains)})",
                                "enum": domains
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
                                "description": f"Name of the world (e.g., {domains[0]})",
                                "enum": domains
                            },
                            "entity_type": {
                                "type": "string",
                                "description": "Type of entity to retrieve (roles, conditions, resources, all)",
                                "enum": entity_types
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
            
            # Get world label for the domain
            world_label = domain.replace("-", " ").title()
            for s, p, o in self.graph.triples((None, RDF.type, OWL.Ontology)):
                for label in self.graph.objects(s, RDFS.label):
                    if domain == str(label).lower().replace(" ", "-"):
                        world_label = str(label)
                        break
            
            # Get relevant patient cases from ontology
            cases = []
            
            if domain == "military-medical-triage":
                # Simple keyword matching for the query against patient conditions
                relevant_patients = []
                
                # Search for matching conditions
                for s in self.graph.subjects(RDF.type, self.MMT.MedicalCondition):
                    condition_matches = False
                    
                    # Check if condition label matches query
                    for label in self.graph.objects(s, RDFS.label):
                        if query.lower() in str(label).lower():
                            condition_matches = True
                            break
                    
                    # Check if condition description matches query
                    if not condition_matches:
                        for comment in self.graph.objects(s, RDFS.comment):
                            if query.lower() in str(comment).lower():
                                condition_matches = True
                                break
                    
                    if condition_matches:
                        # Find patients with this condition
                        for patient, _, condition in self.graph.triples((None, self.MMT.hasCondition, s)):
                            relevant_patients.append(patient)
                
                # Generate cases from relevant patients
                case_id = 1
                processed_patients = []
                
                for patient in relevant_patients:
                    if patient in processed_patients:
                        continue
                    
                    processed_patients.append(patient)
                    patient_label = None
                    triage_category = None
                    condition_label = None
                    condition_severity = None
                    
                    # Get patient label
                    for label in self.graph.objects(patient, RDFS.label):
                        patient_label = str(label)
                        break
                    
                    # Get triage category
                    for o in self.graph.objects(patient, self.MMT.hasTriageCategory):
                        for cat_label in self.graph.objects(o, RDFS.label):
                            triage_category = str(cat_label)
                            break
                    
                    # Get condition information
                    for condition in self.graph.objects(patient, self.MMT.hasCondition):
                        for cond_label in self.graph.objects(condition, RDFS.label):
                            condition_label = str(cond_label)
                        for severity in self.graph.objects(condition, self.MMT.severity):
                            condition_severity = str(severity)
                        break
                    
                    if patient_label and triage_category and condition_label:
                        case = {
                            "id": case_id,
                            "title": f"Patient with {condition_label}",
                            "description": f"Patient classified as {triage_category} with {condition_severity} {condition_label}",
                            "relevance": 0.9 if query.lower() in condition_label.lower() else 0.7
                        }
                        
                        if triage_category.startswith("Immediate"):
                            case["decision"] = "Prioritized for immediate life-saving intervention"
                            case["outcome"] = "Stabilized for further treatment"
                            case["ethical_analysis"] = "Ethical principle of urgency: treating those at immediate risk of death"
                        elif triage_category.startswith("Delayed"):
                            case["decision"] = "Treatment delayed to prioritize more critical patients"
                            case["outcome"] = "Condition managed successfully after initial delay"
                            case["ethical_analysis"] = "Utilitarian approach: maximizing benefit across all patients"
                        elif triage_category.startswith("Minimal"):
                            case["decision"] = "Basic first aid provided, advised self-care"
                            case["outcome"] = "Recovered without advanced intervention"
                            case["ethical_analysis"] = "Resource conservation: directing limited resources to those in greater need"
                        else:
                            case["decision"] = "Palliative care provided"
                            case["outcome"] = "Comfort measures maintained"
                            case["ethical_analysis"] = "Ethical allocation of limited resources in mass casualty scenario"
                        
                        cases.append(case)
                        case_id += 1
                        
                        if case_id > limit:
                            break
                
                # If no cases found from ontology, provide fallback cases
                if not cases:
                    cases = [
                        {
                            "id": 1,
                            "title": "Field Hospital Mass Casualty",
                            "description": f"Field hospital receiving multiple casualties with limited resources, matching query: {query}",
                            "decision": "Prioritized treatment based on severity and survivability",
                            "outcome": "Maximized survival rates but some potentially salvageable patients were classified as expectant",
                            "ethical_analysis": "Utilitarian approach maximized overall survival but raised concerns about individual rights",
                            "relevance": 0.85
                        },
                        {
                            "id": 2,
                            "title": "Civilian and Military Casualties",
                            "description": f"Mixed civilian and military casualties with limited evacuation capacity, matching query: {query}",
                            "decision": "Evacuated based on medical need regardless of status",
                            "outcome": "Aligned with humanitarian principles but delayed return of some military personnel to duty",
                            "ethical_analysis": "Prioritized medical ethics over military necessity, reflecting deontological principles",
                            "relevance": 0.72
                        }
                    ]
                
                return {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps({
                                "query": query,
                                "domain": domain,
                                "world": world_label,
                                "results": cases
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
                                        "description": f"Field hospital receiving multiple casualties from an IED attack with limited resources, matching query: {query}",
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
                    # Use the pre-loaded ontology and extract entities
                    entities = await self._extract_world_entities(entity_type)
                    
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
