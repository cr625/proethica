"""
Ontology Editor Module for ProEthica

A modular and flexible implementation for editing BFO-based ontologies,
designed to be integrated with the ProEthica application.
"""

import os
import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify

def create_ontology_editor_blueprint(config=None, url_prefix='/ontology-editor'):
    """
    Create a Flask blueprint for the ontology editor.
    
    Args:
        config (dict): Configuration dictionary for the ontology editor
        url_prefix (str): URL prefix for the blueprint routes
        
    Returns:
        Blueprint: Flask blueprint for the ontology editor
    """
    from ontology_editor.api.routes import create_api_routes
    from ontology_editor.api.entity_routes import create_entity_routes
    from ontology_editor.services.entity_service import EntityService
    
    # Create blueprint
    blueprint = Blueprint(
        'ontology_editor',
        __name__,
        template_folder='templates',
        static_folder='static',
        url_prefix=url_prefix
    )
    
    # Register API routes
    api_routes = create_api_routes(config or {})
    entity_routes = create_entity_routes(config or {})
    blueprint.register_blueprint(api_routes)
    blueprint.register_blueprint(entity_routes, url_prefix='/api')
    
    # Add main routes
    @blueprint.route('/')
    def index():
        """Main ontology editor landing page"""
        source = request.args.get('source')
        ontology_id = request.args.get('ontology_id')
        view = request.args.get('view', 'full')
        highlight_entity = request.args.get('highlight_entity')
        entity_type = request.args.get('entity_type')
        world_id = request.args.get('world_id')
        
        # Use ontology_id if provided, otherwise use source
        # This ensures backward compatibility
        source_param = None
        if ontology_id:
            from app.models.ontology import Ontology
            ontology = Ontology.query.get(ontology_id)
            if ontology:
                source_param = str(ontology_id)
        else:
            source_param = source
            
        # If no source parameter is available, show message
        if not source_param:
            flash('No ontology ID provided. Please select an ontology from the editor.', 'warning')

        # If view is 'entities', this is a specialized entity view
        if view == 'entities':
            return entity_editor(ontology_id, world_id)

        # Default full editor view
        return render_template('editor.html',
                             source=source_param,
                             ontology_id=ontology_id,
                             highlight_entity=highlight_entity,
                             entity_type=entity_type)
    
    def entity_editor(ontology_id, world_id=None):
        """Entity editor view"""
        from app.models.ontology import Ontology
        from app.models.ontology_version import OntologyVersion
        
        # Get the ontology
        ontology = Ontology.query.get_or_404(ontology_id)
        
        # Get the latest version
        latest_version = OntologyVersion.query.filter_by(
            ontology_id=ontology_id
        ).order_by(
            OntologyVersion.version_number.desc()
        ).first()
        
        # Get entities
        from app.services.ontology_entity_service import OntologyEntityService
        entity_service = OntologyEntityService.get_instance()
        
        # Create a world-like object with the required ontology_id field
        class DummyWorld:
            def __init__(self, ontology_id):
                self.ontology_id = ontology_id
                
        dummy_world = DummyWorld(ontology_id)
        entities = entity_service.get_entities_for_world(dummy_world)
        
        # Get parent classes for each entity type
        parent_classes = {}
        for entity_type in ['role', 'condition', 'resource', 'action', 'event', 'capability']:
            parent_classes[entity_type] = EntityService.get_valid_parents(ontology_id, entity_type)
            
        # Get all capabilities for roles
        capabilities = []
        if 'entities' in entities and 'capabilities' in entities['entities']:
            capabilities = entities['entities']['capabilities']
        
        # Serialize parent classes and capabilities for JavaScript
        serialized_parents = {}
        for entity_type, parents in parent_classes.items():
            serialized_parents[entity_type] = parents
            
        serialized_capabilities = capabilities
        
        # Template helper functions
        def is_editable(entity):
            return EntityService.is_editable(entity)
            
        def get_entity_origin(entity):
            return EntityService.get_entity_origin(entity)
            
        def is_parent_of(parent, entity):
            if not entity or not parent:
                return False
                
            # Ensure consistent string comparison
            parent_id = str(parent.get('id')).strip() if parent.get('id') else None
            entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
            
            # Debug output to help troubleshoot
            print(f"Partial template comparing parent: {parent_id}")
            print(f"With entity parent: {entity_parent}")
            print(f"Match: {parent_id == entity_parent}")
            
            if parent_id and entity_parent:
                return parent_id == entity_parent
                
            return False
            if not entity or not parent:
                return False
                
            # Ensure consistent string comparison
            parent_id = str(parent.get('id')).strip() if parent.get('id') else None
            entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
            
            # Debug output to help troubleshoot
            print(f"Comparing parent: {parent_id}")
            print(f"With entity parent: {entity_parent}")
            print(f"Match: {parent_id == entity_parent}")
            
            if parent_id and entity_parent:
                return parent_id == entity_parent
                
            return False

            # DEBUG - print to console
            print(f"is_parent_of check:")
            print(f"  - parent id: {parent.get('id')}")
            print(f"  - entity parent_class: {entity.get('parent_class')}")
            print(f"  - match: {parent.get('id') == entity.get('parent_class')}")
                
            # Check if parent.id matches entity's parent_class
            if 'parent_class' in entity:
                return str(parent.get('id')) == str(entity.get('parent_class'))
            
            return False
            
        def get_valid_parents(entity_type):
            return parent_classes.get(entity_type, [])
            
        def has_capability(role, capability):
            if not role or not capability or not role.get('capabilities'):
                return False
                
            return any(cap.get('id') == capability.get('id') for cap in role.get('capabilities', []))
            
        def get_all_capabilities():
            return capabilities
        
        # Render template
        return render_template('entity_editor.html',
                               ontology=ontology,
                               entities=entities,
                               latest_version=latest_version,
                               world_id=world_id,
                               is_editable=is_editable,
                               get_entity_origin=get_entity_origin,
                               is_parent_of=is_parent_of,
                               get_valid_parents=get_valid_parents,
                               has_capability=has_capability,
                               get_all_capabilities=get_all_capabilities,
                               serialized_parents=serialized_parents,
                               serialized_capabilities=serialized_capabilities)
                             
    @blueprint.route('/api/partial/<entity_type>/<int:ontology_id>')
    def get_partial_template(entity_type, ontology_id):
        """Serve a partial template directly"""
        from app.models.ontology import Ontology
        from app.models.ontology_version import OntologyVersion
        
        # Create a mapping for template names
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
            
        template_name = template_map[entity_type]
        
        # Get the ontology
        ontology = Ontology.query.get_or_404(ontology_id)
        
        # Get entities
        from app.services.ontology_entity_service import OntologyEntityService
        entity_service = OntologyEntityService.get_instance()
        
        # Create a world-like object with the required ontology_id field
        class DummyWorld:
            def __init__(self, ontology_id):
                self.ontology_id = ontology_id
                
        dummy_world = DummyWorld(ontology_id)
        entities = entity_service.get_entities_for_world(dummy_world)
        
        # Helper functions (same as in entity_editor)
        def is_editable(entity):
            return EntityService.is_editable(entity)
            
        def get_entity_origin(entity):
            return EntityService.get_entity_origin(entity)
            
        def is_parent_of(parent, entity):
            if not entity or not parent:
                return False
                
            # Ensure consistent string comparison
            parent_id = str(parent.get('id')).strip() if parent.get('id') else None
            entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
            
            # Debug output to help troubleshoot
            print(f"Comparing parent: {parent_id}")
            print(f"With entity parent: {entity_parent}")
            print(f"Match: {parent_id == entity_parent}")
            
            if parent_id and entity_parent:
                return parent_id == entity_parent
                
            return False
                
            # DEBUG - print to console
            print(f"Partial template is_parent_of check:")
            print(f"  - parent id: {parent.get('id')}")
            print(f"  - entity parent_class: {entity.get('parent_class')}")
            print(f"  - match: {parent.get('id') == entity.get('parent_class')}")
                
            # Check if parent.id matches entity's parent_class
            if 'parent_class' in entity:
                return str(parent.get('id')) == str(entity.get('parent_class'))
            
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
        
        # Render the partial template
        html = render_template(f'partials/{template_name}',
                              ontology=ontology,
                              entities=entities,
                              is_editable=is_editable,
                              get_entity_origin=get_entity_origin,
                              is_parent_of=is_parent_of,
                              get_valid_parents=get_valid_parents,
                              has_capability=has_capability,
                              get_all_capabilities=get_all_capabilities)
        
        return jsonify({'html': html})
                             
    @blueprint.route('/visualize/<ontology_id>')
    def visualize_ontology(ontology_id):
        """Ontology visualization view"""
        # Get the ontology to ensure it exists
        from app.models.ontology import Ontology
        ontology = Ontology.query.get(ontology_id)
        
        if not ontology:
            flash('Ontology not found.', 'error')
            return redirect(url_for('ontology_editor.index'))
            
        return render_template('visualize.html', 
                              ontology_id=ontology_id,
                              source=ontology_id)
    
    @blueprint.route('/entity')
    def edit_entity():
        """Entity-specific editor view"""
        source = request.args.get('source')
        entity_id = request.args.get('highlight_entity')
        entity_type = request.args.get('entity_type')
        
        return render_template('hierarchy.html', 
                             source=source,
                             highlight_entity=entity_id,
                             entity_type=entity_type)
    
    return blueprint
