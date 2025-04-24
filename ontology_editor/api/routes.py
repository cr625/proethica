from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
import os
from ..models.metadata import MetadataStorage
from ..services.file_storage import read_ontology_file, write_ontology_file
from ..services.validator import validate_ontology

def create_api_routes(config):
    """Create API routes for the ontology editor blueprint."""
    bp = Blueprint('ontology_editor_api', __name__, url_prefix='/ontology-editor/api')
    
    @bp.route('/ontologies', methods=['GET'])
    def list_ontologies():
        """List all ontologies."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get ontologies from metadata storage
        metadata_storage = MetadataStorage()
        ontologies = metadata_storage.get_all_ontologies()
        return jsonify({'ontologies': ontologies})
    
    @bp.route('/ontologies/<int:ontology_id>', methods=['GET'])
    def get_ontology(ontology_id):
        """Get an ontology by ID."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get ontology from metadata storage
        metadata_storage = MetadataStorage()
        ontology = metadata_storage.get_ontology(ontology_id)
        if not ontology:
            return jsonify({'error': 'Ontology not found'}), 404
        
        # Read ontology file
        content = read_ontology_file(ontology['domain'], 'main/current.ttl')
        if content is None:
            return jsonify({'error': 'Ontology file not found'}), 404
        
        # Return ontology data
        return jsonify({
            'ontology': ontology,
            'content': content
        })
    
    @bp.route('/ontologies', methods=['POST'])
    def create_ontology():
        """Create a new ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check admin permission if required
        if config.get('admin_only', False) and not check_admin():
            return jsonify({'error': 'Admin permission required'}), 403
        
        # Get ontology data from request
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['title', 'domain', 'filename']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Create ontology
        metadata_storage = MetadataStorage()
        ontology_id = metadata_storage.add_ontology({
            'title': data['title'],
            'domain': data['domain'],
            'filename': data['filename'],
            'description': data.get('description', '')
        })
        
        # Create ontology file with template content
        template_content = f"""
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix BFO: <http://purl.obolibrary.org/obo/BFO_> .
@prefix {data['domain']}: <http://proethica.org/ontology/{data['domain']}#> .

{data['domain']}:Ontology rdf:type owl:Ontology ;
    rdfs:label "{data['title']}" ;
    rdfs:comment "{data.get('description', '')}" .

# Roles
{data['domain']}:Role rdf:type owl:Class ;
    rdfs:subClassOf BFO:0000023 ; # Role
    rdfs:label "Role" ;
    rdfs:comment "A role in the {data['domain']} domain" .

# Conditions
{data['domain']}:Condition rdf:type owl:Class ;
    rdfs:subClassOf BFO:0000019 ; # Quality
    rdfs:label "Condition" ;
    rdfs:comment "A condition in the {data['domain']} domain" .

# Resources
{data['domain']}:Resource rdf:type owl:Class ;
    rdfs:subClassOf BFO:0000040 ; # Material entity
    rdfs:label "Resource" ;
    rdfs:comment "A resource in the {data['domain']} domain" .

# Events
{data['domain']}:Event rdf:type owl:Class ;
    rdfs:subClassOf BFO:0000015 ; # Process
    rdfs:label "Event" ;
    rdfs:comment "An event in the {data['domain']} domain" .

# Actions
{data['domain']}:Action rdf:type owl:Class ;
    rdfs:subClassOf BFO:0000015 ; # Process
    rdfs:label "Action" ;
    rdfs:comment "An action in the {data['domain']} domain" .
"""
        write_ontology_file(data['domain'], 'main/current.ttl', template_content)
        
        # Create first version
        metadata_storage.add_version({
            'ontology_id': ontology_id,
            'version_number': 1,
            'commit_message': 'Initial creation',
            'file_path': f"domains/{data['domain']}/main/versions/v1.ttl"
        })
        write_ontology_file(data['domain'], 'main/versions/v1.ttl', template_content)
        
        return jsonify({
            'success': True,
            'message': 'Ontology created successfully',
            'ontology_id': ontology_id
        })
    
    @bp.route('/ontologies/<int:ontology_id>', methods=['PUT'])
    def update_ontology(ontology_id):
        """Update an ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Check admin permission if required
        if config.get('admin_only', False) and not check_admin():
            return jsonify({'error': 'Admin permission required'}), 403
        
        # Get ontology data from request
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Get ontology from metadata storage
        metadata_storage = MetadataStorage()
        ontology = metadata_storage.get_ontology(ontology_id)
        if not ontology:
            return jsonify({'error': 'Ontology not found'}), 404
        
        # Update ontology fields
        if 'title' in data:
            ontology['title'] = data['title']
        if 'description' in data:
            ontology['description'] = data['description']
        
        # Update ontology in metadata storage
        metadata_storage.update_ontology(ontology_id, ontology)
        
        # Update ontology content if provided
        if 'content' in data:
            # Validate ontology content
            validation_results = validate_ontology(data['content'])
            if validation_results.get('is_valid', False):
                # Write ontology content to file
                write_ontology_file(ontology['domain'], 'main/current.ttl', data['content'])
                
                # Create new version
                versions = metadata_storage.get_versions(ontology_id)
                new_version_number = len(versions) + 1
                metadata_storage.add_version({
                    'ontology_id': ontology_id,
                    'version_number': new_version_number,
                    'commit_message': data.get('commit_message', 'Updated ontology'),
                    'file_path': f"domains/{ontology['domain']}/main/versions/v{new_version_number}.ttl"
                })
                write_ontology_file(
                    ontology['domain'], 
                    f"main/versions/v{new_version_number}.ttl", 
                    data['content']
                )
            else:
                # Return validation errors
                return jsonify({
                    'success': False,
                    'message': 'Ontology validation failed',
                    'validation_results': validation_results
                }), 400
        
        return jsonify({
            'success': True,
            'message': 'Ontology updated successfully'
        })
    
    @bp.route('/ontologies/<int:ontology_id>/validate', methods=['POST'])
    def validate_ontology_content(ontology_id):
        """Validate ontology content."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get ontology content from request
        data = request.json
        if not data or 'content' not in data:
            return jsonify({'error': 'No content provided'}), 400
        
        # Validate ontology content
        validation_results = validate_ontology(data['content'])
        return jsonify(validation_results)
    
    @bp.route('/ontologies/<int:ontology_id>/versions', methods=['GET'])
    def get_versions(ontology_id):
        """Get versions of an ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get ontology from metadata storage
        metadata_storage = MetadataStorage()
        ontology = metadata_storage.get_ontology(ontology_id)
        if not ontology:
            return jsonify({'error': 'Ontology not found'}), 404
        
        # Get versions from metadata storage
        versions = metadata_storage.get_versions(ontology_id)
        return jsonify({'versions': versions})
    
    @bp.route('/ontologies/<int:ontology_id>/versions/<int:version_number>', methods=['GET'])
    def get_version(ontology_id, version_number):
        """Get a specific version of an ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        # Get ontology from metadata storage
        metadata_storage = MetadataStorage()
        ontology = metadata_storage.get_ontology(ontology_id)
        if not ontology:
            return jsonify({'error': 'Ontology not found'}), 404
        
        # Get versions from metadata storage
        versions = metadata_storage.get_versions(ontology_id)
        for version in versions:
            if version['version_number'] == version_number:
                # Read version file
                content = read_ontology_file(ontology['domain'], f"main/versions/v{version_number}.ttl")
                if content is None:
                    return jsonify({'error': 'Version file not found'}), 404
                
                # Return version data
                return jsonify({
                    'version': version,
                    'content': content
                })
        
        # Version not found
        return jsonify({'error': 'Version not found'}), 404
        
    @bp.route('/entity', methods=['GET'])
    def edit_entity():
        """Edit a specific entity from a world context."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return redirect(url_for('auth.login'))
        
        # Check admin permission if required
        if config.get('admin_only', False) and not check_admin():
            flash('Admin permission required to edit ontologies', 'error')
            return redirect(url_for('worlds.list_worlds'))
        
        # Get parameters
        entity_id = request.args.get('entity_id')
        entity_type = request.args.get('type')
        ontology_source = request.args.get('source')
        
        if not entity_id or not entity_type or not ontology_source:
            flash('Missing required parameters', 'error')
            return redirect(url_for('ontology_editor.index'))
        
        # Get the ontology ID from the source
        try:
            metadata_storage = MetadataStorage()
            ontologies = metadata_storage.get_all_ontologies()
            ontology_id = None
            
            for ontology in ontologies:
                if ontology['filename'] == ontology_source:
                    ontology_id = ontology['id']
                    break
                    
            if not ontology_id:
                flash(f'Ontology not found for source: {ontology_source}', 'error')
                return redirect(url_for('ontology_editor.index'))
                
        except Exception as e:
            flash(f'Error finding ontology: {str(e)}', 'error')
            return redirect(url_for('ontology_editor.index'))
        
        # Redirect to the editor with entity highlighted
        return redirect(url_for('ontology_editor.edit', 
                               ontology_id=ontology_id,
                               highlight_entity=entity_id,
                               entity_type=entity_type))
    
    def check_auth():
        """Check if user is authenticated."""
        try:
            from flask_login import current_user
            return current_user.is_authenticated
        except ImportError:
            return True  # If Flask-Login is not installed, assume authentication is not required
    
    def check_admin():
        """Check if user has admin permission."""
        try:
            from flask_login import current_user
            return current_user.is_authenticated and current_user.is_admin
        except (ImportError, AttributeError):
            return True  # If Flask-Login is not installed or user has no is_admin attribute, assume admin permission is not required
    
    return bp
