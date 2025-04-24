from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
import os
from ..models.metadata import MetadataStorage
from ..services.file_storage_utils import read_ontology_file, write_ontology_file
from ..services.validator import validate_ontology
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app import db

def create_api_routes(config):
    """Create API routes for the ontology editor blueprint."""
    bp = Blueprint('ontology_editor_api', __name__, url_prefix='/ontology-editor/api')
    
    @bp.route('/ontologies', methods=['GET'])
    def list_ontologies():
        """List all ontologies."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # First try to get ontologies from database
            ontologies = Ontology.query.all()
            result = [ontology.to_dict() for ontology in ontologies]
            
            # If no ontologies found in database, try the legacy metadata storage
            if not result:
                metadata_storage = MetadataStorage()
                result = metadata_storage.get_all_ontologies()
            
            return jsonify({'ontologies': result})
        except Exception as e:
            current_app.logger.error(f"Error listing ontologies: {str(e)}")
            return jsonify({'error': f'Error listing ontologies: {str(e)}'}), 500
    
    @bp.route('/ontologies/<int:ontology_id>', methods=['GET'])
    def get_ontology(ontology_id):
        """Get an ontology by ID."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # First try to get from database
            ontology = Ontology.query.get(ontology_id)
            
            if ontology:
                return jsonify({
                    'ontology': ontology.to_dict(),
                    'content': ontology.content
                })
            
            # If not in database, try the legacy metadata storage
            metadata_storage = MetadataStorage()
            ontology_meta = metadata_storage.get_ontology(ontology_id)
            
            if not ontology_meta:
                return jsonify({'error': 'Ontology not found'}), 404
            
            # Read ontology file
            content = read_ontology_file(ontology_meta['domain'], 'main/current.ttl')
            if content is None:
                return jsonify({'error': 'Ontology file not found'}), 404
            
            # Return ontology data
            return jsonify({
                'ontology': ontology_meta,
                'content': content
            })
        except Exception as e:
            current_app.logger.error(f"Error getting ontology: {str(e)}")
            return jsonify({'error': f'Error getting ontology: {str(e)}'}), 500
    
    @bp.route('/versions/<int:ontology_id>', methods=['GET'])
    def get_versions(ontology_id):
        """Get versions of an ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # First try to get from database
            ontology = Ontology.query.get(ontology_id)
            
            if ontology:
                versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).all()
                return jsonify({'versions': [v.to_dict() for v in versions]})
            
            # If not in database, try the legacy metadata storage
            metadata_storage = MetadataStorage()
            ontology_meta = metadata_storage.get_ontology(ontology_id)
            if not ontology_meta:
                return jsonify({'error': 'Ontology not found'}), 404
            
            # Get versions from metadata storage
            versions = metadata_storage.get_versions(ontology_id)
            return jsonify({'versions': versions})
        except Exception as e:
            current_app.logger.error(f"Error getting versions: {str(e)}")
            return jsonify({'error': f'Error getting versions: {str(e)}'}), 500
    
    @bp.route('/versions/<int:version_id>', methods=['GET'])
    def get_version(version_id):
        """Get a specific version of an ontology."""
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # First try to get from database
            version = OntologyVersion.query.get(version_id)
            
            if version:
                return jsonify({
                    'version': version.to_dict(),
                    'content': version.content
                })
            
            # If not in database, try the legacy metadata storage
            metadata_storage = MetadataStorage()
            version_meta = metadata_storage.get_version_by_id(version_id)
            if not version_meta:
                return jsonify({'error': 'Version not found'}), 404
            
            # Get the ontology for this version
            ontology_meta = metadata_storage.get_ontology(version_meta['ontology_id'])
            if not ontology_meta:
                return jsonify({'error': 'Ontology not found for version'}), 404
            
            # Read version file
            content = read_ontology_file(
                ontology_meta['domain'], 
                f"main/versions/v{version_meta['version_number']}.ttl"
            )
            if content is None:
                return jsonify({'error': 'Version file not found'}), 404
            
            # Return version data
            return jsonify({
                'version': version_meta,
                'content': content
            })
        except Exception as e:
            current_app.logger.error(f"Error getting version: {str(e)}")
            return jsonify({'error': f'Error getting version: {str(e)}'}), 500
    
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
        
        try:
            # Create ontology in database
            domain_id = data['domain'].replace('_', '-')  # Standardize domain ID format
            
            # Check if ontology already exists
            existing = Ontology.query.filter_by(domain_id=domain_id).first()
            if existing:
                return jsonify({'error': f'Ontology with domain ID {domain_id} already exists'}), 409
            
            # Create template content
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
            
            # Create ontology record
            ontology = Ontology(
                name=data['title'],
                description=data.get('description', ''),
                domain_id=domain_id,
                content=template_content
            )
            db.session.add(ontology)
            db.session.flush()  # Get ID without committing
            
            # Create first version
            version = OntologyVersion(
                ontology_id=ontology.id,
                version_number=1,
                content=template_content,
                commit_message='Initial creation'
            )
            db.session.add(version)
            db.session.commit()
            
            # For backward compatibility, also write to file
            fs_domain = data['domain'].replace('-', '_')  # Convert to filesystem format
            write_ontology_file(fs_domain, 'main/current.ttl', template_content)
            write_ontology_file(fs_domain, 'main/versions/v1.ttl', template_content)
            
            return jsonify({
                'success': True,
                'message': 'Ontology created successfully',
                'ontology_id': ontology.id
            })
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating ontology: {str(e)}")
            return jsonify({'error': f'Error creating ontology: {str(e)}'}), 500
    
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
        
        try:
            # First try to update in database
            ontology = Ontology.query.get(ontology_id)
            
            if ontology:
                # Update ontology fields
                if 'title' in data:
                    ontology.name = data['title']
                if 'description' in data:
                    ontology.description = data['description']
                
                # Update ontology content if provided
                if 'content' in data:
                    # Validate ontology content
                    validation_results = validate_ontology(data['content'])
                    if validation_results.get('valid', False):
                        # Update content
                        ontology.content = data['content']
                        
                        # Create new version
                        versions = OntologyVersion.query.filter_by(ontology_id=ontology_id).all()
                        new_version_number = len(versions) + 1
                        
                        version = OntologyVersion(
                            ontology_id=ontology_id,
                            version_number=new_version_number,
                            content=data['content'],
                            commit_message=data.get('commit_message', 'Updated ontology')
                        )
                        db.session.add(version)
                        
                        # For backward compatibility, also write to file
                        # Convert domain ID to filesystem format
                        fs_domain = ontology.domain_id.replace('-', '_')
                        
                        # Write to files
                        write_ontology_file(fs_domain, 'main/current.ttl', data['content'])
                        write_ontology_file(
                            fs_domain, 
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
                
                # Commit changes
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': 'Ontology updated successfully'
                })
            
            # If not in database, try the legacy file-based approach
            metadata_storage = MetadataStorage()
            ontology_meta = metadata_storage.get_ontology(ontology_id)
            if not ontology_meta:
                return jsonify({'error': 'Ontology not found'}), 404
            
            # Update ontology fields
            if 'title' in data:
                ontology_meta['title'] = data['title']
            if 'description' in data:
                ontology_meta['description'] = data['description']
            
            # Update ontology in metadata storage
            metadata_storage.update_ontology(ontology_id, ontology_meta)
            
            # Update ontology content if provided
            if 'content' in data:
                # Validate ontology content
                validation_results = validate_ontology(data['content'])
                if validation_results.get('valid', False):
                    # Write ontology content to file
                    write_ontology_file(ontology_meta['domain'], 'main/current.ttl', data['content'])
                    
                    # Create new version
                    versions = metadata_storage.get_versions(ontology_id)
                    new_version_number = len(versions) + 1
                    metadata_storage.add_version({
                        'ontology_id': ontology_id,
                        'version_number': new_version_number,
                        'commit_message': data.get('commit_message', 'Updated ontology'),
                        'file_path': f"domains/{ontology_meta['domain']}/main/versions/v{new_version_number}.ttl"
                    })
                    write_ontology_file(
                        ontology_meta['domain'], 
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
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating ontology: {str(e)}")
            return jsonify({'error': f'Error updating ontology: {str(e)}'}), 500
        
    @bp.route('/validate/<int:ontology_id>', methods=['POST'])
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
    
    @bp.route('/ontology/<path:source>')
    def get_ontology_by_source(source):
        """Get an ontology by source identifier."""
        # Log the request for debugging
        current_app.logger.info(f"Getting ontology by source: {source}")
        
        # Check authentication if required
        if config.get('require_auth', True) and not check_auth():
            return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # Strip .ttl extension if present
            domain_id = None
            
            if source.lower().endswith('.ttl'):
                domain_id = source[:-4]  # Remove .ttl extension
            else:
                domain_id = source
                
            current_app.logger.info(f"Looking for domain ID: {domain_id}")
            
            # First try to get ontology from database
            # Standardize domain ID format with dashes
            std_domain_id = domain_id.replace('_', '-')
            ontology = Ontology.query.filter_by(domain_id=std_domain_id).first()
            
            if ontology:
                current_app.logger.info(f"Found ontology in database for domain: {std_domain_id}")
                return jsonify({
                    'ontology': ontology.to_dict(),
                    'content': ontology.content
                })
            
            # If not in database, try to read from filesystem (legacy approach)
            # Convert dashes to underscores for directory lookup
            fs_domain_id = domain_id.replace('-', '_')
            
            current_app.logger.info(f"Looking for filesystem ontology: {fs_domain_id}")
            
            # Try to read the file directly using the domain name
            content = read_ontology_file(fs_domain_id, 'main/current.ttl')
            
            if content is None:
                current_app.logger.error(f"Could not find ontology file for domain: {fs_domain_id}")
                return jsonify({
                    'error': f'Ontology file not found for source: {source}, domain: {domain_id}'
                }), 404
            
            # Find or create metadata entry for this ontology
            metadata_storage = MetadataStorage()
            ontologies = metadata_storage.get_all_ontologies()
            
            ontology_meta = None
            for o in ontologies:
                if o['filename'] == source or o['domain'] == fs_domain_id:
                    ontology_meta = o
                    break
            
            if not ontology_meta:
                # Create a new metadata entry if none exists
                ontology_meta = {
                    'title': domain_id.replace('_', ' ').replace('-', ' ').title(),
                    'filename': source,
                    'domain': fs_domain_id,
                    'description': f'Ontology for {domain_id.replace("_", " ").replace("-", " ")}'
                }
                ontology_id = metadata_storage.add_ontology(ontology_meta)
                ontology_meta['id'] = ontology_id
            
            # Return ontology data
            return jsonify({
                'ontology': ontology_meta,
                'content': content
            })
        except Exception as e:
            current_app.logger.error(f"Error getting ontology by source: {str(e)}")
            return jsonify({'error': str(e)}), 500
            
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
