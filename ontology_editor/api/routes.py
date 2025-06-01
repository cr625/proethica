"""
API routes for the ontology editor
"""
import os
import json
import re
from flask import Blueprint, request, jsonify, current_app, Response, render_template, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app.models.ontology_import import OntologyImport
from app.services.mcp_client import MCPClient
from app.services.ontology_entity_service import OntologyEntityService
from ontology_editor.services.validator import OntologyValidator

def load_ontology_from_file(ontology_name):
    """Load ontology content from file system"""
    try:
        # Map ontology names to file paths
        ontology_files = {
            'proethica-intermediate': '/home/chris/proethica/ontologies/proethica-intermediate.ttl',
            'engineering-ethics': '/home/chris/proethica/ontologies/engineering-ethics.ttl',
            'bfo': '/home/chris/proethica/ontologies/bfo.ttl'
        }
        
        file_path = ontology_files.get(ontology_name.lower())
        if not file_path or not os.path.exists(file_path):
            return None
            
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        current_app.logger.error(f"Error loading ontology file {ontology_name}: {str(e)}")
        return None

def parse_ttl_to_hierarchy(ttl_content, ontology_name):
    """Parse TTL content into hierarchical structure for visualization"""
    try:
        # Simple regex-based parsing to extract class definitions and hierarchy
        classes = {}
        
        # Extract class declarations with their properties
        class_pattern = r':(\w+)\s+(?:rdf:type|a)\s+owl:Class\s*;(.*?)(?=\n\s*:|$)'
        subclass_pattern = r'rdfs:subClassOf\s+([:\w]+)'
        label_pattern = r'rdfs:label\s+"([^"]+)"'
        comment_pattern = r'rdfs:comment\s+"([^"]+)"'
        
        for match in re.finditer(class_pattern, ttl_content, re.MULTILINE | re.DOTALL):
            class_name = match.group(1)
            class_body = match.group(2)
            
            # Extract subclass relationship
            subclass_match = re.search(subclass_pattern, class_body)
            parent = subclass_match.group(1) if subclass_match else None
            
            # Extract label
            label_match = re.search(label_pattern, class_body)
            label = label_match.group(1) if label_match else class_name
            
            # Extract comment/description
            comment_match = re.search(comment_pattern, class_body)
            description = comment_match.group(1) if comment_match else None
            
            # Determine entity type based on GuidelineConceptTypes
            entity_type = determine_entity_type(class_name, class_body)
            
            classes[class_name] = {
                'name': label,
                'uri': f'http://proethica.org/ontology/{ontology_name}#{class_name}',
                'description': description,
                'parent': parent,
                'type': entity_type,
                'entity_type': entity_type
            }
        
        # Build hierarchy tree
        hierarchy = build_hierarchy_tree(classes, ontology_name)
        return hierarchy
        
    except Exception as e:
        current_app.logger.error(f"Error parsing TTL to hierarchy: {str(e)}")
        # Return a simple fallback hierarchy
        return {
            'name': ontology_name,
            'type': 'root',
            'description': f'{ontology_name} ontology',
            'children': []
        }

def determine_entity_type(class_name, class_body):
    """Determine the entity type based on class name and body"""
    # Check for GuidelineConceptTypes
    if 'Role' in class_name:
        return 'Role'
    elif 'Principle' in class_name:
        return 'Principle'
    elif 'Obligation' in class_name:
        return 'Obligation'
    elif 'State' in class_name or 'Condition' in class_name:
        return 'State'
    elif 'Resource' in class_name:
        return 'Resource'
    elif 'Action' in class_name:
        return 'Action'
    elif 'Event' in class_name:
        return 'Event'
    elif 'Capability' in class_name:
        return 'Capability'
    elif 'BFO_' in class_name or 'bfo:' in class_body:
        return 'bfo'
    elif 'proeth:' in class_body:
        return 'bfo-aligned'
    else:
        return 'non-bfo'

def build_hierarchy_tree(classes, ontology_name):
    """Build a hierarchical tree structure from class definitions"""
    # Find root classes (no parent or parent is external)
    roots = []
    children_map = {}
    
    # Group children by parent
    for class_name, class_data in classes.items():
        parent = class_data.get('parent')
        if parent and parent.startswith(':'):
            parent = parent[1:]  # Remove prefix
        elif parent and parent.startswith('proeth:'):
            parent = parent[7:]  # Remove proeth: prefix
        elif parent and parent.startswith('bfo:'):
            parent = parent[4:]  # Remove bfo: prefix
            
        if not parent or parent not in classes:
            # This is a root class
            roots.append(class_data)
        else:
            # Add to parent's children
            if parent not in children_map:
                children_map[parent] = []
            children_map[parent].append(class_data)
    
    # Recursively build tree
    def add_children(node_data):
        # Get the actual class name for lookups
        class_name = None
        for cls_name, cls_data in classes.items():
            if cls_data == node_data:
                class_name = cls_name
                break
        
        # Also try looking up by the display name
        if not class_name:
            class_name = node_data['name']
                
        if class_name and class_name in children_map:
            node_data['children'] = []
            for child in children_map[class_name]:
                add_children(child)
                node_data['children'].append(child)
        return node_data
    
    # Add children to all root nodes
    for root in roots:
        add_children(root)
    
    # Sort roots to show GuidelineConceptTypes first
    guideline_types = ['Role', 'Principle', 'Obligation', 'State', 'Resource', 'Action', 'Event', 'Capability']
    roots.sort(key=lambda x: (
        0 if x['name'] in guideline_types else 1,
        guideline_types.index(x['name']) if x['name'] in guideline_types else 999,
        x['name']
    ))
    
    # Create the main hierarchy structure
    hierarchy = {
        'name': ontology_name.replace('-', ' ').title(),
        'type': 'root',
        'description': f'{ontology_name} ontology hierarchy',
        'children': roots
    }
    
    return hierarchy

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
    
    
    @api_bp.route('/versions/<int:ontology_id>/<int:version_number>')
    def get_version_by_number(ontology_id, version_number):
        """Get a specific version by ontology ID and version number"""
        try:
            version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id,
                version_number=version_number
            ).first_or_404()
            
            # Get the version details
            result = version.to_dict()
            
            # Include the content
            result['content'] = version.content
            
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error fetching version {ontology_id}/{version_number}: {str(e)}")
            return jsonify({'error': f'Failed to fetch version {ontology_id}/{version_number}', 'details': str(e)}), 500
    @api_bp.route('/ontology/<int:ontology_id>/validate', methods=['POST'])
    def validate_ontology(ontology_id):
        """Validate the content of an ontology"""
        try:
            # Get JSON data if available
            data = request.json
            
            # Extract content from the JSON data if provided
            content = None
            if data and 'content' in data:
                content = data['content']
            else:
                # Fallback to raw data if JSON is not used
                try:
                    content = request.data.decode('utf-8')
                except Exception as decode_error:
                    current_app.logger.error(f"Error decoding request data: {str(decode_error)}")
                    pass
            
            # If content is still empty, get it from the database
            if not content and ontology_id:
                ontology = Ontology.query.get_or_404(ontology_id)
                content = ontology.content
            
            # Log what we're validating for debugging purposes
            current_app.logger.debug(f"Validating ontology content (first 100 chars): {content[:100] if content else 'None'}")
            
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
            }), 500

    @api_bp.route('/download/<int:ontology_id>')
    def download_ontology(ontology_id):
        """Download ontology as TTL file"""
        try:
            # Get the ontology
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get the latest version or raw content
            latest_version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id
            ).order_by(OntologyVersion.version_number.desc()).first()
            
            if latest_version and latest_version.content:
                ttl_content = latest_version.content
            else:
                # Fallback to loading from file
                ttl_content = load_ontology_from_file(ontology.name)
                
            if not ttl_content:
                return jsonify({'error': 'No content available for this ontology'}), 404
            
            # Create filename
            filename = f"{ontology.name.lower().replace(' ', '-')}.ttl"
            
            # Return as downloadable file
            response = Response(
                ttl_content,
                mimetype='text/turtle',
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )
            return response
            
        except Exception as e:
            current_app.logger.error(f"Error downloading ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to download ontology: {str(e)}'}), 500

    @api_bp.route('/hierarchy/<int:ontology_id>')
    def get_ontology_hierarchy(ontology_id):
        """Get ontology hierarchy for visualization"""
        if not is_authorized():
            return jsonify({'error': 'Unauthorized'}), 401
            
        try:
            # Get the ontology
            ontology = Ontology.query.get_or_404(ontology_id)
            
            # Get the latest version or raw content
            latest_version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id
            ).order_by(OntologyVersion.version_number.desc()).first()
            
            if latest_version and latest_version.content:
                ttl_content = latest_version.content
            else:
                # Fallback to loading from file
                ttl_content = load_ontology_from_file(ontology.name)
                
            if not ttl_content:
                return jsonify({'error': 'No content available for this ontology'}), 404
                
            # Parse TTL content to hierarchy
            hierarchy = parse_ttl_to_hierarchy(ttl_content, ontology.name)
            
            return jsonify({
                'hierarchy': hierarchy,
                'ontology': {
                    'id': ontology.id,
                    'name': ontology.name,
                    'description': ontology.description
                }
            })
            
        except Exception as e:
            current_app.logger.error(f"Error getting hierarchy for ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to generate hierarchy: {str(e)}'}), 500

    

    @api_bp.route('/versions/<int:ontology_id>/diff')
    def get_versions_diff(ontology_id):
        """Generate a diff between two versions of an ontology"""
        try:
            # Get query parameters
            from_version = request.args.get('from')
            to_version = request.args.get('to')
            format_type = request.args.get('format', 'unified')  # unified or split
            
            if not from_version:
                return jsonify({'error': 'Missing "from" parameter'}), 400
            
            # If to_version is not specified, compare with the current version
            if not to_version:
                # Get the current (latest) version
                latest_version = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id
                ).order_by(OntologyVersion.version_number.desc()).first()
                
                if not latest_version:
                    return jsonify({'error': f'No versions found for ontology {ontology_id}'}), 404
                
                to_version = str(latest_version.version_number)
            
            # Check if versions are the same
            if from_version == to_version:
                return jsonify({
                    'diff': 'No differences (same version)',
                    'format': format_type,
                    'from_version': {
                        'number': int(from_version),
                        'created_at': None,
                        'commit_message': None
                    },
                    'to_version': {
                        'number': int(to_version),
                        'created_at': None,
                        'commit_message': None
                    }
                })
            
            try:
                # Get the content of both versions
                from_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(from_version)
                ).first()
                
                to_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(to_version)
                ).first()
                
                if not from_version_obj:
                    return jsonify({'error': f'Version {from_version} not found for ontology {ontology_id}'}), 404
                
                if not to_version_obj:
                    return jsonify({'error': f'Version {to_version} not found for ontology {ontology_id}'}), 404
                
                # Get the content of both versions
                from_content = from_version_obj.content
                to_content = to_version_obj.content
                
                # Generate the diff
                import difflib
                from_lines = from_content.splitlines(keepends=True)
                to_lines = to_content.splitlines(keepends=True)
                
                if format_type == 'unified':
                    diff = difflib.unified_diff(
                        from_lines, 
                        to_lines,
                        fromfile=f'Version {from_version}',
                        tofile=f'Version {to_version}',
                        lineterm=''
                    )
                    diff_text = ''.join(list(diff))
                else:  # HTML diff with side-by-side option for frontend
                    diff = difflib.HtmlDiff()
                    diff_text = diff.make_table(
                        from_lines,
                        to_lines,
                        fromdesc=f'Version {from_version}',
                        todesc=f'Version {to_version}',
                        context=True,
                        numlines=3
                    )
                
                # Return the diff and metadata
                result = {
                    'diff': diff_text,
                    'format': format_type,
                    'from_version': {
                        'number': from_version_obj.version_number,
                        'created_at': from_version_obj.created_at.isoformat() if from_version_obj.created_at else None,
                        'commit_message': from_version_obj.commit_message
                    },
                    'to_version': {
                        'number': to_version_obj.version_number,
                        'created_at': to_version_obj.created_at.isoformat() if to_version_obj.created_at else None,
                        'commit_message': to_version_obj.commit_message
                    }
                }
                
                return jsonify(result)
            except ValueError:
                return jsonify({'error': 'Version numbers must be integers'}), 400
        except Exception as e:
            current_app.logger.error(f"Error generating diff: {str(e)}")
            return jsonify({'error': f'Failed to generate diff: {str(e)}', 'details': str(e)}), 500

    return api_bp
