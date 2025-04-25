#!/usr/bin/env python3
"""
Script to update the ontology editor entity endpoint to use the same direct entity
extraction method as the world detail page. This ensures consistency between the
entities shown in the ontology editor and the world detail page.
"""
import os
import sys
import tempfile
import shutil

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def update_ontology_editor_api():
    """
    Update the ontology editor API to use our direct entity extraction service
    instead of the MCP client.
    """
    api_routes_path = os.path.join(os.getcwd(), "ontology_editor", "api", "routes.py")
    if not os.path.exists(api_routes_path):
        print(f"Error: Could not find API routes file at {api_routes_path}")
        return False
    
    # Create a backup
    backup_path = api_routes_path + ".bak"
    shutil.copy2(api_routes_path, backup_path)
    print(f"Created backup of API routes file at {backup_path}")
    
    # Read the file
    with open(api_routes_path, 'r') as f:
        content = f.read()
    
    # Check for imports first
    import_section = "from app import db\nfrom app.models.ontology import Ontology\nfrom app.models.ontology_version import OntologyVersion\nfrom app.models.ontology_import import OntologyImport\nfrom app.services.mcp_client import MCPClient"
    
    # Add our new import
    updated_import = import_section + "\nfrom app.services.ontology_entity_service import OntologyEntityService"
    
    # Replace the import section
    content = content.replace(import_section, updated_import)
    
    # Find the entity endpoint
    entity_endpoint = """@api_bp.route('/ontology/<int:ontology_id>/entities')
    def get_ontology_entities(ontology_id):
        \"\"\"Get entities from an ontology\"\"\"
        try:
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get entities from MCP client
            mcp_client = MCPClient.get_instance()
            entities = mcp_client.get_world_entities(ontology.domain_id + ".ttl")
            
            return jsonify(entities)
        except Exception as e:
            current_app.logger.error(f"Error fetching entities for ontology {ontology_id}: {str(e)}")
            return jsonify({
                'error': f'Failed to fetch entities for ontology {ontology_id}', 
                'details': str(e),
                'entities': {}  # Return empty entities to prevent UI errors
            }), 500"""
    
    # Create the updated endpoint
    updated_endpoint = """@api_bp.route('/ontology/<int:ontology_id>/entities')
    def get_ontology_entities(ontology_id):
        \"\"\"Get entities from an ontology\"\"\"
        try:
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get entities directly from the ontology entity service
            entity_service = OntologyEntityService.get_instance()
            
            # Create a world-like object with the required ontology_id field
            class DummyWorld:
                def __init__(self, ontology_id):
                    self.ontology_id = ontology_id
            
            dummy_world = DummyWorld(ontology_id)
            entities = entity_service.get_entities_for_world(dummy_world)
            
            return jsonify(entities)
        except Exception as e:
            current_app.logger.error(f"Error fetching entities for ontology {ontology_id}: {str(e)}")
            return jsonify({
                'error': f'Failed to fetch entities for ontology {ontology_id}', 
                'details': str(e),
                'entities': {}  # Return empty entities to prevent UI errors
            }), 500"""
    
    # Replace the endpoint
    content = content.replace(entity_endpoint, updated_endpoint)
    
    # Also update the hierarchy method's entity extraction
    old_hierarchy_entities = """            # Get entities from MCP client
            mcp_client = MCPClient.get_instance()
            entities_response = mcp_client.get_world_entities(ontology.domain_id + ".ttl")
            entities = entities_response.get('entities', {})"""
    
    new_hierarchy_entities = """            # Get entities directly from the ontology entity service
            entity_service = OntologyEntityService.get_instance()
            
            # Create a world-like object with the required ontology_id field
            class DummyWorld:
                def __init__(self, ontology_id):
                    self.ontology_id = ontology_id
            
            dummy_world = DummyWorld(ontology.id)
            entities_response = entity_service.get_entities_for_world(dummy_world)
            entities = entities_response.get('entities', {})"""
    
    # Replace the hierarchy entity fetching code
    content = content.replace(old_hierarchy_entities, new_hierarchy_entities)
    
    # Write the updated content back to the file
    with open(api_routes_path, 'w') as f:
        f.write(content)
    
    print(f"Updated API routes file with direct entity extraction approach")
    return True

if __name__ == "__main__":
    if update_ontology_editor_api():
        print("\nSuccess! The ontology editor API now uses the direct entity extraction method.")
        print("This ensures that the entities shown in the ontology editor match those on the world detail page.")
        print("You should now restart the server to apply the changes: ./restart_server.sh")
    else:
        print("\nFailed to update the ontology editor API.")
        print("Please check the error messages above for details.")
