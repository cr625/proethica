from flask import Blueprint, request, jsonify
import os
import json
import subprocess
import tempfile

mcp_api_bp = Blueprint('mcp_api', __name__, url_prefix='/api')

@mcp_api_bp.route('/ontology/<path:ontology_source>/entities', methods=['GET'])
def get_ontology_entities(ontology_source):
    """
    Get entities from an ontology source.

    Args:
        ontology_source: Path to the ontology source file

    Returns:
        JSON response with entities
    """
    try:
        # Parse the TTL file directly using rdflib
        import os
        import rdflib
        from rdflib import Graph, Namespace, RDF, RDFS, URIRef
        from rdflib.namespace import OWL

        # Define known namespaces
        namespaces = {
            "military-medical-triage": Namespace("http://example.org/military-medical-triage#"),
            "engineering-ethics": Namespace("http://example.org/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://example.org/nj-legal-ethics#"),
            "tccc": Namespace("http://example.org/tccc#")
        }

        # Determine the namespace to use based on the ontology source
        namespace_key = None
        if "engineering_ethics" in ontology_source:
            namespace_key = "engineering-ethics"
        elif "nj_legal_ethics" in ontology_source:
            namespace_key = "nj-legal-ethics"
        elif "tccc" in ontology_source:
            namespace_key = "tccc"
        else:
            namespace_key = "military-medical-triage"

        namespace = namespaces[namespace_key]

        # Load the ontology file
        ontology_path = os.path.join("mcp/ontology", ontology_source)
        if not os.path.exists(ontology_path):
            print(f"Ontology file not found: {ontology_path}")
            # Fall back to mock data if the ontology file doesn't exist
            from app.services.mcp_client import MCPClient
            client = MCPClient.get_instance()
            mock_entities = client.get_mock_entities(ontology_source)
            return jsonify(mock_entities)

        # Parse the ontology file
        g = Graph()
        g.parse(ontology_path, format="turtle")

        # Extract entities
        def label_or_id(s):
            for o in g.objects(s, RDFS.label):
                return str(o)
            return str(s)

        def get_description(s):
            for o in g.objects(s, RDFS.comment):
                return str(o)
            return ""

        # Extract roles
        roles = []
        for s in g.subjects(RDF.type, namespace.Role):
            role = {
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            }
            
            # Add tier if available
            for o in g.objects(s, namespace.hasTier):
                role["tier"] = str(o)
            
            # Add capabilities if available
            capabilities = []
            for o in g.objects(s, namespace.hasCapability):
                capabilities.append(str(o))
            if capabilities:
                role["capabilities"] = capabilities
            
            roles.append(role)

        # Extract conditions
        conditions = []
        for s in g.subjects(RDF.type, namespace.ConditionType):
            condition = {
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            }
            
            # Add type if available
            for o in g.objects(s, RDF.type):
                if o != namespace.ConditionType:
                    condition["type"] = str(o)
                    break
            
            # Add severity if available
            for o in g.objects(s, namespace.severity):
                condition["severity"] = str(o)
            
            # Add location if available
            for o in g.objects(s, namespace.location):
                condition["location"] = str(o)
            
            conditions.append(condition)

        # Extract resources
        resources = []
        for s in g.subjects(RDF.type, namespace.ResourceType):
            resource = {
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            }
            
            # Add type if available
            for o in g.objects(s, RDF.type):
                if o != namespace.ResourceType:
                    resource["type"] = str(o)
                    break
            
            # Add quantity if available
            for o in g.objects(s, namespace.quantity):
                resource["quantity"] = str(o)
            
            resources.append(resource)

        # Extract actions
        actions = []
        for s in g.subjects(RDF.type, namespace.ActionType):
            action = {
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            }
            
            # Add type if available
            for o in g.objects(s, RDF.type):
                if o != namespace.ActionType:
                    action["type"] = str(o)
                    break
            
            # Add priority if available
            for o in g.objects(s, namespace.actionPriority):
                action["priority"] = str(o)
            
            # Add duration if available
            for o in g.objects(s, namespace.actionDuration):
                action["duration"] = str(o)
            
            actions.append(action)

        # Extract events
        events = []
        for s in g.subjects(RDF.type, namespace.EventType):
            event = {
                "id": str(s),
                "label": label_or_id(s),
                "description": get_description(s)
            }
            
            # Add type if available
            for o in g.objects(s, RDF.type):
                if o != namespace.EventType:
                    event["type"] = str(o)
                    break
            
            # Add severity if available
            for o in g.objects(s, namespace.eventSeverity):
                event["severity"] = str(o)
            
            # Add location if available
            for o in g.objects(s, namespace.eventLocation):
                event["location"] = str(o)
            
            events.append(event)

        # Create the entities dictionary
        entities = {}
        if roles:
            entities["roles"] = roles
        if conditions:
            entities["conditions"] = conditions
        if resources:
            entities["resources"] = resources
        if actions:
            entities["actions"] = actions
        if events:
            entities["events"] = events

        return jsonify({"entities": entities})
    except Exception as e:
        print(f"Error parsing ontology file: {str(e)}")
        # Fall back to mock data if there's an error
        from app.services.mcp_client import MCPClient
        client = MCPClient.get_instance()
        mock_entities = client.get_mock_entities(ontology_source)
        return jsonify(mock_entities)

@mcp_api_bp.route('/guidelines/<path:world_name>', methods=['GET'])
def get_guidelines(world_name):
    """
    Get guidelines for a specific world.
    
    Args:
        world_name: Name of the world
        
    Returns:
        JSON response with guidelines
    """
    try:
        # Return the mock guidelines
        from app.services.mcp_client import MCPClient
        client = MCPClient.get_instance()
        mock_guidelines = client.get_mock_guidelines(world_name)
        return jsonify(mock_guidelines)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
