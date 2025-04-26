"""
Entity API routes for the ontology editor

These routes handle CRUD operations for entities in ontologies:
- Create new entities
- Update existing entities
- Delete entities
- Get entity information
"""

from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from ontology_editor.services.entity_service import EntityService

def create_entity_routes(config):
    """Create Entity API Blueprint for the ontology editor"""
    entity_bp = Blueprint('entity_api', __name__, url_prefix='/entities')
    
    # Helper functions
    def is_authorized():
        """Check if user is authorized to access the API"""
        if config.get('require_auth', True):
            if not current_user.is_authenticated:
                return False
            # Only check admin status if admin_only is True and current_user is authenticated
            if config.get('admin_only', False) and hasattr(current_user, 'is_admin'):
                if not current_user.is_admin:
                    return False
        return True
    
    @entity_bp.route('/<int:ontology_id>/<entity_type>', methods=['GET'])
    def get_entity_list(ontology_id, entity_type):
        """Get list of entities of a specific type from an ontology"""
        try:
            # Implement based on your entity service
            # This is a placeholder
            return jsonify({'entities': []})
        except Exception as e:
            current_app.logger.error(f"Error getting entities: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @entity_bp.route('/<int:ontology_id>/<entity_type>', methods=['POST'])
    def create_entity(ontology_id, entity_type):
        """Create a new entity in the ontology"""
        try:
            # Check authorization
            if not is_authorized():
                return jsonify({'error': 'Unauthorized'}), 401
                
            # Get request data
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            # Create entity
            success, result = EntityService.create_entity(ontology_id, entity_type, data)
            
            if success:
                return jsonify(result), 201
            else:
                return jsonify(result), 400
        except Exception as e:
            current_app.logger.error(f"Error creating entity: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @entity_bp.route('/<int:ontology_id>/<entity_type>/<entity_id>', methods=['PUT'])
    def update_entity(ontology_id, entity_type, entity_id):
        """Update an existing entity in the ontology"""
        try:
            # Check authorization
            if not is_authorized():
                return jsonify({'error': 'Unauthorized'}), 401
                
            # Get request data
            data = request.json
            if not data:
                return jsonify({'error': 'No data provided'}), 400
                
            # Update entity
            success, result = EntityService.update_entity(ontology_id, entity_type, entity_id, data)
            
            if success:
                return jsonify(result)
            else:
                return jsonify(result), 400
        except Exception as e:
            current_app.logger.error(f"Error updating entity: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @entity_bp.route('/<int:ontology_id>/<entity_type>/<entity_id>', methods=['DELETE'])
    def delete_entity(ontology_id, entity_type, entity_id):
        """Delete an entity from the ontology"""
        try:
            # Check authorization
            if not is_authorized():
                return jsonify({'error': 'Unauthorized'}), 401
                
            # Delete entity
            success, result = EntityService.delete_entity(ontology_id, entity_type, entity_id)
            
            if success:
                return jsonify(result)
            else:
                return jsonify(result), 400
        except Exception as e:
            current_app.logger.error(f"Error deleting entity: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    @entity_bp.route('/<int:ontology_id>/<entity_type>/parents', methods=['GET'])
    def get_valid_parents(ontology_id, entity_type):
        """Get valid parent classes for a given entity type"""
        try:
            # Get valid parents
            parents = EntityService.get_valid_parents(ontology_id, entity_type)
            
            return jsonify({'parents': parents})
        except Exception as e:
            current_app.logger.error(f"Error getting valid parents: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    # Route to serve partial templates
    @entity_bp.route('/<int:ontology_id>/partial/<entity_type>', methods=['GET'])
    def get_entity_partial(ontology_id, entity_type):
        """Serve a partial template for entity types"""
        from flask import render_template
        try:
            # Map singular tab IDs to template names
            template_map = {
                'resource': 'resources_tab.html',
                'action': 'actions_tab.html',
                'event': 'events_tab.html',
                'capability': 'capabilities_tab.html',
                'resources': 'resources_tab.html',
                'actions': 'actions_tab.html',
                'events': 'events_tab.html',
                'capabilities': 'capabilities_tab.html'
            }
            
            if entity_type not in template_map:
                return jsonify({'error': f'Invalid entity type: {entity_type}'}), 400
                
            # Render the partial template
            from app.models.ontology import Ontology
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Use the same entity service as the main entity editor
            from app.services.ontology_entity_service import OntologyEntityService
            entity_service = OntologyEntityService.get_instance()
            
            # Create a world-like object with the required ontology_id field
            class DummyWorld:
                def __init__(self, ontology_id):
                    self.ontology_id = ontology_id
                    
            dummy_world = DummyWorld(ontology_id)
            entities = entity_service.get_entities_for_world(dummy_world)
            
            # Helpers needed for the templates - same as in entity_editor view
            def is_editable(entity):
                return EntityService.is_editable(entity)
                
            def get_entity_origin(entity):
                return EntityService.get_entity_origin(entity)
                
            def is_parent_of(parent, entity):
                if not entity or not parent:
                    return False
                    
                if 'parent_class' in entity:
                    return parent.get('id') == entity.get('parent_class')
                
                return False
                
            def get_valid_parents(entity_type):
                return EntityService.get_valid_parents(ontology_id, entity_type)
                
            def has_capability(role, capability):
                if not role or not capability or not role.get('capabilities'):
                    return False
                    
                return any(cap.get('id') == capability.get('id') for cap in role.get('capabilities', []))
                
            def get_all_capabilities():
                if 'entities' in entities and 'capabilities' in entities['entities']:
                    return entities['entities']['capabilities']
                return []
            
            # Render the appropriate partial template
            template_name = template_map[entity_type]
            partial_html = render_template(f'partials/{template_name}',
                                         ontology=ontology,
                                         entities=entities,
                                         is_editable=is_editable,
                                         get_entity_origin=get_entity_origin,
                                         is_parent_of=is_parent_of,
                                         get_valid_parents=get_valid_parents,
                                         has_capability=has_capability,
                                         get_all_capabilities=get_all_capabilities)
            
            return jsonify({'html': partial_html})
        except Exception as e:
            current_app.logger.error(f"Error getting partial template: {str(e)}")
            return jsonify({'error': str(e)}), 500
    
    return entity_bp
