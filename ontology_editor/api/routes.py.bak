"""
API routes for the ontology editor
"""
import os
import json
from flask import Blueprint, request, jsonify, current_app, Response, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.ontology_import import OntologyImport
from app.services.mcp_client import MCPClient
from ontology_editor.services.validator import OntologyValidator

def create_api_routes(config):
    """Create API Blueprint for the ontology editor"""
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    # Helper functions
    def is_authorized():
        """Check if user is authorized to access the API"""
        # Skip authentication for visualization endpoints
        endpoint = request.endpoint if request else None
        path = request.path if request else ""
        
        # Public endpoints for visualization
        if endpoint and ('get_ontology_hierarchy' in endpoint or 
                        'get_ontologies' in endpoint or
                        'get_ontology_entities' in endpoint):
            return True
            
        if config.get('require_auth', True):
            if not current_user.is_authenticated:
                return False
            # Only check admin status if admin_only is True and current_user is authenticated
            if config.get('admin_only', False) and hasattr(current_user, 'is_admin'):
                if not current_user.is_admin:
                    return False
    def ping():
        """Simple health check endpoint"""
        return jsonify({'status': 'ok'})

    @api_bp.route('/ontologies')
    def get_ontologies():
        """Get the list of available ontologies"""
        try:
            # Get all ontologies from the database
            ontologies = Ontology.query.all()
            
            # Transform to dict for JSON serialization 
            result = [{
                'id': ontology.id,
                'name': ontology.name,
                'domain_id': ontology.domain_id,
                'description': ontology.description,
                'created_at': ontology.created_at.isoformat() if ontology.created_at else None,
                'updated_at': ontology.updated_at.isoformat() if ontology.updated_at else None,
                'is_base': ontology.is_base if hasattr(ontology, 'is_base') else False,
                'is_editable': ontology.is_editable if hasattr(ontology, 'is_editable') else True
            } for ontology in ontologies]
            
            return jsonify({'ontologies': result})
        except Exception as e:
            current_app.logger.error(f"Error fetching ontologies: {str(e)}")
            return jsonify({'error': 'Failed to fetch ontologies', 'details': str(e)}), 500
            
    # Compatibility endpoint for legacy code looking for /ontologies/ID
    @api_bp.route('/ontologies/<int:ontology_id>')
    def get_ontology_by_legacy_route(ontology_id):
        """Redirect legacy ontology endpoint to new standard endpoint"""
        return get_ontology(ontology_id)

    @api_bp.route('/ontology/<int:ontology_id>')
    def get_ontology(ontology_id):
        """Get a specific ontology by ID"""
        try:
            ontology = Ontology.query.get_or_404(ontology_id)

            # Include import relationships
            imports = []
            for imp in OntologyImport.query.filter_by(importing_ontology_id=ontology.id).all():
                imported = Ontology.query.get(imp.imported_ontology_id)
                if imported:
                    imports.append({
                        'id': imported.id,
                        'name': imported.name,
                        'domain_id': imported.domain_id
                    })

            # Return ontology with its imports
            result = {
                'id': ontology.id,
                'name': ontology.name,
                'domain_id': ontology.domain_id,
                'description': ontology.description,
                'created_at': ontology.created_at.isoformat() if ontology.created_at else None,
                'updated_at': ontology.updated_at.isoformat() if ontology.updated_at else None,
                'is_base': ontology.is_base if hasattr(ontology, 'is_base') else False,
                'is_editable': ontology.is_editable if hasattr(ontology, 'is_editable') else True,
                'imports': imports,
                'content': ontology.content  # Include content directly
            }
            
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error fetching ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to fetch ontology {ontology_id}', 'details': str(e)}), 500
    
    @api_bp.route('/ontology/<int:ontology_id>/content')
    def get_ontology_content(ontology_id):
        """Get the content of a specific ontology"""
        try:
            ontology = Ontology.query.get_or_404(ontology_id)
            return Response(ontology.content, mimetype='text/turtle')
        except Exception as e:
            current_app.logger.error(f"Error fetching ontology content {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to fetch ontology content {ontology_id}', 'details': str(e)}), 500
    
    @api_bp.route('/ontology/<int:ontology_id>/content', methods=['PUT'])
    def update_ontology_content(ontology_id):
        """Update the content of a specific ontology"""
        try:
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Check if ontology is editable
            if hasattr(ontology, 'is_editable') and not ontology.is_editable:
                return jsonify({'error': f'Ontology {ontology_id} is not editable'}), 403
            
            # Get the new content
            new_content = request.data.decode('utf-8')
            
            # Validate the content
            validator = OntologyValidator()
            validation_result = validator.validate(new_content)
            
            if not validation_result['valid']:
                return jsonify({
                    'error': 'Invalid ontology content',
                    'validation': validation_result
                }), 400
            
            # Create a new version
            commit_message = request.json.get('commit_message', 'Updated ontology content')
            
            # Get the current highest version number
            latest_version = OntologyVersion.query.filter_by(ontology_id=ontology_id).order_by(OntologyVersion.version_number.desc()).first()
            new_version_number = (latest_version.version_number + 1) if latest_version else 1
            
            # Create new version
            new_version = OntologyVersion(
                ontology_id=ontology_id,
                version_number=new_version_number,
                content=new_content,
                commit_message=commit_message
            )
            
            # Update the ontology with the new content
            ontology.content = new_content
            
            # Save changes
            db.session.add(new_version)
            db.session.commit()
            
            return jsonify({
                'status': 'success', 
                'message': 'Ontology updated successfully',
                'version': new_version_number
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating ontology content {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to update ontology content {ontology_id}', 'details': str(e)}), 500
    
    @api_bp.route('/versions/<int:ontology_id>')
    def get_ontology_versions(ontology_id):
        """Get versions of a specific ontology"""
        try:
            # Check if ontology exists
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get all versions for this ontology
            versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).order_by(OntologyVersion.version_number.desc()).all()
            
            # Transform to dict for JSON serialization
            result = [version.to_dict() for version in versions]
            
            return jsonify({'versions': result})
        except Exception as e:
            current_app.logger.error(f"Error fetching versions for ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to fetch versions for ontology {ontology_id}', 'details': str(e)}), 500

    @api_bp.route('/versions/<int:version_id>')
    def get_version(version_id):
        """Get a specific version by ID"""
        try:
            version = OntologyVersion.query.get_or_404(version_id)
            
            # Get the version details
            result = version.to_dict()
            
            # Include the content
            result['content'] = version.content
            
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error fetching version {version_id}: {str(e)}")
            return jsonify({'error': f'Failed to fetch version {version_id}', 'details': str(e)}), 500
    
    @api_bp.route('/ontology/<int:ontology_id>/validate', methods=['POST'])
    def validate_ontology(ontology_id):
        """Validate the content of an ontology"""
        try:
            # Get the content to validate
            content = request.data.decode('utf-8')
            
            # If content is empty, get it from the database
            if not content and ontology_id:
                ontology = Ontology.query.get_or_404(ontology_id)
                content = ontology.content
            
            # Validate the content
            validator = OntologyValidator()
            validation_result = validator.validate(content)
            
            return jsonify(validation_result)
        except Exception as e:
            current_app.logger.error(f"Error validating ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to validate ontology {ontology_id}', 'details': str(e)}), 500

    @api_bp.route('/ontology/<int:ontology_id>/entities')
    def get_ontology_entities(ontology_id):
        """Get entities from an ontology"""
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
            }), 500

    @api_bp.route('/ontology/<int:ontology_id>/hierarchy')
    def get_ontology_hierarchy(ontology_id):
        """Get hierarchy view of an ontology, especially for visualization"""
        try:
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get hierarchy from file or generate it
            hierarchy = generate_ontology_hierarchy(ontology)
            
            return jsonify({'hierarchy': hierarchy})
        except Exception as e:
            current_app.logger.error(f"Error generating hierarchy for ontology {ontology_id}: {str(e)}")
            return jsonify({
                'error': f'Failed to generate hierarchy for ontology {ontology_id}',
                'details': str(e),
                'hierarchy': {'name': 'Error', 'children': []}  # Return minimal hierarchy to prevent UI errors
            }), 500

    def generate_ontology_hierarchy(ontology):
        """
        Generate a hierarchical representation of an ontology.
        This is a simplified mock implementation - in a real system, you'd use
        rdflib or a similar library to parse and analyze the ontology structure.
        """
        try:
            # Get entities from MCP client
            mcp_client = MCPClient.get_instance()
            entities_response = mcp_client.get_world_entities(ontology.domain_id + ".ttl")
            entities = entities_response.get('entities', {})
            
            # Create root node
            root = {
                'name': ontology.name,
                'type': 'root',
                'uri': f"http://proethica.org/ontology/{ontology.domain_id}",
                'description': ontology.description,
                'children': []
            }
            
            # BFO root classes (simplified)
            bfo_root = {
                'name': 'Entity',
                'type': 'bfo',
                'uri': 'http://purl.obolibrary.org/obo/BFO_0000001',
                'description': 'An entity is anything that exists or has existed',
                'children': []
            }
            
            # Add BFO continuant and occurrent
            continuant = {
                'name': 'Continuant',
                'type': 'bfo',
                'uri': 'http://purl.obolibrary.org/obo/BFO_0000002',
                'description': 'An entity that persists through time',
                'children': []
            }
            
            occurrent = {
                'name': 'Occurrent',
                'type': 'bfo',
                'uri': 'http://purl.obolibrary.org/obo/BFO_0000003',
                'description': 'An entity that unfolds itself in time',
                'children': []
            }
            
            # Intermediate classes
            role_bearer = {
                'name': 'RoleBearer',
                'type': 'bfo-aligned',
                'uri': 'http://proethica.org/ontology/intermediate#RoleBearer',
                'description': 'An entity that can bear roles',
                'children': []
            }
            
            condition_bearer = {
                'name': 'ConditionBearer',
                'type': 'bfo-aligned',
                'uri': 'http://proethica.org/ontology/intermediate#ConditionBearer',
                'description': 'An entity that can bear conditions',
                'children': []
            }
            
            # Add intermediate role and condition classes
            continuant['children'].append(role_bearer)
            continuant['children'].append(condition_bearer)
            
            # Add process classes
            process = {
                'name': 'Process',
                'type': 'bfo',
                'uri': 'http://purl.obolibrary.org/obo/BFO_0000015',
                'description': 'An occurrent that unfolds itself in time',
                'children': []
            }
            occurrent['children'].append(process)
            
            # Add domain-specific entities
            for entity_type, entity_list in entities.items():
                for entity in entity_list:
                    entity_node = {
                        'name': entity.get('label', 'Unknown'),
                        'description': entity.get('description', ''),
                        'type': 'non-bfo',
                        'entity_type': entity_type.rstrip('s'),  # remove plural form
                        'children': []
                    }
                    
                    # Place entity in the right category
                    if entity_type == 'roles':
                        role_bearer['children'].append(entity_node)
                    elif entity_type == 'conditions':
                        condition_bearer['children'].append(entity_node)
                    elif entity_type in ['events', 'actions']:
                        process['children'].append(entity_node)
                    elif entity_type == 'resources':
                        continuant['children'].append(entity_node)
                    else:
                        # Default - append directly to root
                        bfo_root['children'].append(entity_node)
            
            # Add BFO structure to root
            bfo_root['children'].append(continuant)  
            bfo_root['children'].append(occurrent)
            root['children'].append(bfo_root)
            
            return root
        except Exception as e:
            current_app.logger.error(f"Error in generate_ontology_hierarchy: {str(e)}")
            # Return a minimal hierarchy in case of error
            return {
                'name': ontology.name,
                'type': 'root',
                'description': f"Error generating hierarchy: {str(e)}",
                'children': []
            }

    # Return the Blueprint
    return api_bp
