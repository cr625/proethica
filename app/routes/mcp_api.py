from flask import Blueprint, request, jsonify, Response, render_template_string
import os
import json
import subprocess
import tempfile
import re
from urllib.parse import urlparse
from rdflib import Graph, URIRef, Namespace
from app.services.mcp_client import MCPClient

mcp_api_bp = Blueprint('mcp_api', __name__, url_prefix='/api')

@mcp_api_bp.route('/ontology/<path:ontology_source>/entities', methods=['GET'])
def get_ontology_entities(ontology_source):
    """
    Get entities from an ontology source.

    Args:
        ontology_source: Path to the ontology source file
        type: (optional query parameter) Filter entities by type (roles, conditions, resources, actions, events, or all)

    Returns:
        JSON response with entities
    """
    # Get entity_type query parameter (default to 'all')
    entity_type = request.args.get('type', 'all')
    try:
        # Parse the TTL file directly using rdflib
        import os
        import rdflib
        from rdflib import Graph, Namespace, RDF, RDFS, URIRef
        from rdflib.namespace import OWL

        # Define known namespaces
        namespaces = {
            "military-medical-triage": Namespace("http://proethica.org/ontology/military-medical-triage#"),
            "engineering-ethics": Namespace("http://proethica.org/ontology/engineering-ethics#"),
            "nj-legal-ethics": Namespace("http://proethica.org/ontology/nj-legal-ethics#"),
            "tccc": Namespace("http://proethica.org/ontology/military-medical-triage#")  # Use military-medical-triage namespace for tccc.ttl
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
        ontology_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "mcp/ontology", ontology_source)
        if not os.path.exists(ontology_path):
            print(f"Ontology file not found: {ontology_path}")
            # Fall back to mock data if the ontology file doesn't exist
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

        # Extract roles - both direct instances and roles that are also classes
        roles = []
        
        # First, get direct instances of Role
        for s in g.subjects(RDF.type, namespace.Role):
            # Skip if it's also an OWL class (we'll handle those separately)
            if (s, RDF.type, OWL.Class) not in g:
                role = {
                    "id": str(s),
                    "label": label_or_id(s),
                    "description": get_description(s)
                }
                
                # Add tier if available
                for o in g.objects(s, namespace.hasTier):
                    tier_str = str(o)
                    role["tier"] = tier_str
                    # Extract tier level based on name
                    if "EntryLevel" in tier_str:
                        role["tier_level"] = 1
                    elif "MidLevel" in tier_str:
                        role["tier_level"] = 2
                    elif "SeniorLevel" in tier_str:
                        role["tier_level"] = 3
                    elif "ExecutiveLevel" in tier_str:
                        role["tier_level"] = 4
                
                # Add capabilities if available
                capabilities = []
                for o in g.objects(s, namespace.hasCapability):
                    capability = {
                        "id": str(o),
                        "label": label_or_id(o)
                    }
                    capabilities.append(capability)
                if capabilities:
                    role["capabilities"] = capabilities
                
                roles.append(role)
        
        # Then, look for classes that are also marked as Role types
        for s in g.subjects(RDF.type, OWL.Class):
            # Check if this class is also a Role
            if (s, RDF.type, namespace.Role) in g:
                # Check if we already added this role
                if not any(r["id"] == str(s) for r in roles):
                    role = {
                        "id": str(s),
                        "label": label_or_id(s),
                        "description": get_description(s)
                    }
                    
                    # Get parent class if any
                    for parent in g.objects(s, RDFS.subClassOf):
                        parent_str = str(parent)
                        if parent_str != str(namespace.Role):
                            role["parent"] = {
                                "id": parent_str,
                                "label": label_or_id(parent)
                            }
                    
                    # Add tier if available
                    for o in g.objects(s, namespace.hasTier):
                        tier_str = str(o)
                        role["tier"] = tier_str
                        # Extract tier level based on name
                        if "EntryLevel" in tier_str:
                            role["tier_level"] = 1
                        elif "MidLevel" in tier_str:
                            role["tier_level"] = 2
                        elif "SeniorLevel" in tier_str:
                            role["tier_level"] = 3
                        elif "ExecutiveLevel" in tier_str:
                            role["tier_level"] = 4
                    
                    # Add capabilities if available
                    capabilities = []
                    for o in g.objects(s, namespace.hasCapability):
                        capability = {
                            "id": str(o),
                            "label": label_or_id(o)
                        }
                        capabilities.append(capability)
                    if capabilities:
                        role["capabilities"] = capabilities
                    
                    roles.append(role)
        
        # Sort roles by tier level if available
        roles.sort(key=lambda r: r.get("tier_level", 0))

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

        # Create the entities dictionary, filtering by entity_type if specified
        entities = {}
        if entity_type in ('all', 'roles') and roles:
            entities["roles"] = roles
        if entity_type in ('all', 'conditions') and conditions:
            entities["conditions"] = conditions
        if entity_type in ('all', 'resources') and resources:
            entities["resources"] = resources
        if entity_type in ('all', 'actions') and actions:
            entities["actions"] = actions
        if entity_type in ('all', 'events') and events:
            entities["events"] = events

        return jsonify({"success": True, "entities": entities})
    except Exception as e:
        import traceback
        error_message = f"Error parsing ontology file: {str(e)}"
        stack_trace = traceback.format_exc()
        print(error_message)
        print(stack_trace)
        print(f"Ontology source: {ontology_source}")
        print(f"Ontology path: {ontology_path}")
        
        # Fall back to mock data if there's an error
        client = MCPClient.get_instance()
        mock_entities = client.get_mock_entities(ontology_source)
        return jsonify({"success": True, "entities": mock_entities})

@mcp_api_bp.route('/ontology/world/<world_id>/entities', methods=['GET'])
def get_world_entities(world_id):
    """Get all entities for a specific world."""
    try:
        client = MCPClient.get_instance()
        entities = client.get_world_entities(world_id)
        return jsonify({"success": True, "entities": entities['entities']})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@mcp_api_bp.route('/ontology/world/<world_id>/entities/<entity_type>', methods=['GET'])
def get_world_entities_by_type(world_id, entity_type):
    """Get entities of a specific type for a world."""
    try:
        client = MCPClient.get_instance()
        entities = client.get_world_entities(world_id, entity_type=entity_type)
        return jsonify({"success": True, "entities": entities['entities'][entity_type]})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@mcp_api_bp.route('/ontology/entity/<entity_id>', methods=['GET'])
def get_ontology_entity(entity_id):
    """Get a specific entity by ID."""
    try:
        client = MCPClient.get_instance()
        entity = client.get_entity(entity_id)
        if entity is None:
            return jsonify({"success": False, "message": f"Entity not found: {entity_id}"}), 404
        return jsonify({"success": True, "entity": entity})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

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
        client = MCPClient.get_instance()
        mock_guidelines = client.get_mock_guidelines(world_name)
        return jsonify(mock_guidelines)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@mcp_api_bp.route('/zotero/search', methods=['GET'])
def search_zotero():
    """Search for items in Zotero."""
    query = request.args.get('query', '')
    try:
        client = MCPClient.get_instance()
        results = client.search_zotero_items(query)
        return jsonify({"success": True, "results": results})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@mcp_api_bp.route('/zotero/items/<item_key>/citation', methods=['GET'])
def get_zotero_citation(item_key):
    """Get a citation for a Zotero item."""
    style = request.args.get('style', 'apa')
    try:
        client = MCPClient.get_instance()
        citation = client.get_zotero_citation(item_key, style)
        return jsonify({"success": True, "citation": citation})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
