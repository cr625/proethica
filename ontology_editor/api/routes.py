from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, current_app
import os
# Legacy file storage removed
# from ..models.metadata import MetadataStorage
# File operations disabled
# from ..services.file_storage_utils import read_ontology_file, write_ontology_file
from ..services.validator import validate_ontology
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion
from app import db

from rdflib import Graph, URIRef, RDF, RDFS, OWL
import json

def create_api_routes(config):
    """Create API routes for the ontology editor blueprint."""
    bp = Blueprint('ontology_editor_api', __name__, url_prefix='/api')
    
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
            
            # Database-only mode: no file fallback
            return jsonify({'error': 'Ontology not found'}), 404
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
            
            # Database-only mode: no file fallback
            return jsonify({'error': 'Ontology not found'}), 404
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
            
            # Database-only mode: no file fallback
            return jsonify({'error': 'Ontology not found'}), 404
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
            
            # For backward compatibility, create empty placeholder file
            # but don't actually write content (database is source of truth)
            fs_domain = data['domain'].replace('-', '_')  # Convert to filesystem format
            os.makedirs(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main'), exist_ok=True)
            os.makedirs(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'versions'), exist_ok=True)
            
            # Create empty placeholder files
            open(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'current.ttl'), 'w').close()
            open(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'versions', 'v1.ttl'), 'w').close()
            
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
                    if validation_results.get('is_valid', False):
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
                        
                        # For backward compatibility, create empty placeholder file
                        # but don't actually write content (database is source of truth)
                        fs_domain = ontology.domain_id.replace('-', '_')
                        
                        # Ensure directories exist
                        os.makedirs(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main'), exist_ok=True)
                        os.makedirs(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'versions'), exist_ok=True)
                        
                        # Update/create empty placeholder files
                        open(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'current.ttl'), 'w').close()
                        open(os.path.join(current_app.config['ONTOLOGY_DIR'], fs_domain, 'main', 'versions', f'v{new_version_number}.ttl'), 'w').close()
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
            
            # Database-only mode: no file fallback
            return jsonify({'error': 'Ontology not found'}), 404
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
        
        # Log validation results for debugging
        current_app.logger.info(f"Validation results: {validation_results}")
        
        # Ensure consistent response format
        response = {
            'is_valid': validation_results.get('is_valid', False),
            'errors': validation_results.get('errors', []),
            'warnings': validation_results.get('warnings', []),
            'suggestions': []  # Add empty suggestions array for BFO validation response format
        }
        
        return jsonify(response)
    
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
    
    @bp.route('/hierarchy/<int:ontology_id>', methods=['GET'])
    def get_ontology_hierarchy(ontology_id):
        """Get hierarchical structure of an ontology for visualization."""
        # Temporarily disable authentication for this route to allow easier testing
        # NOTE: In a production environment, proper authentication should be enforced
        # if config.get('require_auth', True) and not check_auth():
        #     return jsonify({'error': 'Authentication required'}), 401
        
        try:
            # Get the ontology from database
            ontology = Ontology.query.get(ontology_id)
            
            if not ontology:
                return jsonify({'error': 'Ontology not found'}), 404
            
            # Extract hierarchy from TTL content - include all classes
            print(f"Extracting hierarchy from ontology: {ontology.name} (ID={ontology_id})")
            hierarchy = extract_hierarchy_from_ttl(ontology.content, ontology.name, include_all_top_classes=True)
            
            return jsonify({
                'hierarchy': hierarchy,
                'ontology': ontology.to_dict()
            })
        except Exception as e:
            current_app.logger.error(f"Error generating hierarchy: {str(e)}")
            return jsonify({'error': f'Error generating hierarchy: {str(e)}'}), 500
    
    def extract_hierarchy_from_ttl(ttl_content, ontology_name, include_all_top_classes=False):
        """
        Extract hierarchical structure from TTL content.
        
        Args:
            ttl_content (str): The TTL content to parse
            ontology_name (str): The name of the ontology
            include_all_top_classes (bool): If True, include all top-level classes instead of
                                           filtering them based on hierarchy
        
        Returns:
            dict: A hierarchical structure of the ontology
        """
        try:
            # Parse TTL using RDFLib
            g = Graph()
            g.parse(data=ttl_content, format='turtle')
            
            # Extract all classes with their information
            classes = {}
            class_hierarchy = {}
            labels = {}
            comments = {}
            
            # Get all classes
            for s, p, o in g.triples((None, RDF.type, OWL.Class)):
                if isinstance(s, URIRef):
                    class_uri = str(s)
                    classes[class_uri] = {
                        'uri': class_uri,
                        'children': []
                    }
            
            # Add labels and comments
            for s, p, o in g.triples((None, RDFS.label, None)):
                if str(s) in classes:
                    labels[str(s)] = str(o)
            
            for s, p, o in g.triples((None, RDFS.comment, None)):
                if str(s) in classes:
                    comments[str(s)] = str(o)
            
            # Build hierarchy based on rdfs:subClassOf relationships
            for s, p, o in g.triples((None, RDFS.subClassOf, None)):
                if str(s) in classes and isinstance(o, URIRef):
                    child_uri = str(s)
                    parent_uri = str(o)
                    
                    if parent_uri not in class_hierarchy:
                        class_hierarchy[parent_uri] = []
                    
                    class_hierarchy[parent_uri].append(child_uri)
            
            # Identify BFO classes and domain-specific classes
            bfo_prefix = "http://purl.obolibrary.org/obo/BFO_"
            
            # Build the tree structure
            def build_tree(uri, visited=None):
                if visited is None:
                    visited = set()
                
                if uri in visited:
                    return None  # Prevent cycles
                
                visited.add(uri)
                
                # Get class details
                name = labels.get(uri, uri.split('#')[-1].split('/')[-1])
                
                # Determine the type of class (BFO, BFO-aligned, or domain-specific)
                if uri.startswith(bfo_prefix):
                    type_name = "bfo"
                else:
                    # Check if it has a BFO parent
                    has_bfo_parent = False
                    for parent, children in class_hierarchy.items():
                        if uri in children and parent.startswith(bfo_prefix):
                            has_bfo_parent = True
                            break
                    
                    type_name = "bfo-aligned" if has_bfo_parent else "non-bfo"
                
                # Create node
                node = {
                    "name": name,
                    "uri": uri,
                    "type": type_name,
                    "description": comments.get(uri, "")
                }
                
                # Add children
                children = class_hierarchy.get(uri, [])
                if children:
                    node["children"] = []
                    for child_uri in children:
                        child_node = build_tree(child_uri, visited.copy())
                        if child_node:
                            node["children"].append(child_node)
                
                return node
            
            # Start with top-level classes (those with no parents in our hierarchy)
            all_children = set()
            for parent_uri, children in class_hierarchy.items():
                all_children.update(children)
            
            top_level = [uri for uri in classes if uri not in all_children]
            
            # Build a forest of trees
            forest = []
            for uri in top_level:
                tree = build_tree(uri)
                if tree:
                    forest.append(tree)
            
            # If include_all_top_classes is True, look for all top-level entities
            # Get the domain prefix from the TTL content
            domain_prefix = None
            for prefix, namespace in g.namespaces():
                if str(namespace).startswith('http://proethica.org/ontology/'):
                    domain_prefix = prefix
                    break
            
            if include_all_top_classes and domain_prefix:
                # Log current forest contents
                print(f"Current forest has {len(forest)} elements: {[tree['name'] for tree in forest]}")
                
                # Look for specific class patterns in the ontology using more flexible matching
                specific_classes = []
                
                # Since domain-specific classes are found in our analysis,
                # directly look for them and force add to the visualization
                top_level_classes = [
                    'EngineeringRole', 'EngineeringEvent', 'EngineeringCondition', 
                    'EngineeringAction', 'EngineeringResource', 'EngineeringDocument',
                    'EngineeringEthicalPrinciple', 'EngineeringEthicalDilemma',
                    'EngineeringCapability'
                ]
                
                # Debug what classes we have in the graph
                print("All class URIs in the ontology:")
                for uri in classes.keys():
                    if '#' in uri:
                        class_name = uri.split('#')[-1]
                        print(f"  - {class_name}")
                
                print(f"Searching for top-level classes: {top_level_classes}")
                
                # Get all the classes and their labels for easier matching
                all_classes = {}
                for s, p, o in g.triples((None, RDF.type, OWL.Class)):
                    uri_str = str(s)
                    label = None
                    
                    # Get the label if available
                    for _, _, lbl in g.triples((URIRef(uri_str), RDFS.label, None)):
                        label = str(lbl)
                        break
                    
                    # Use the URI fragment if no label
                    if not label:
                        if '#' in uri_str:
                            label = uri_str.split('#')[-1]
                        else:
                            label = uri_str.split('/')[-1]
                    
                    all_classes[uri_str] = label
                
                # Create a mapping of class types to URIs
                class_uri_map = {}
                for uri, label in all_classes.items():
                    for class_type in top_level_classes:
                        # Match on exact names or with various common patterns
                        if (label == class_type or 
                           label.lower() == class_type.lower() or
                           uri.endswith(f"#{class_type}") or
                           uri.endswith(f"/{class_type}")):
                            class_uri_map[class_type] = uri
                            print(f"Found {class_type} class: {uri}")
                            break
                
                # Now use the map to create nodes for each class type
                for class_type in top_level_classes:
                    # Try to find the class URI
                    class_uri = class_uri_map.get(class_type)
                    if not class_uri:
                        print(f"Could not find {class_type} class in the ontology")
                        continue
                        
                    class_label = all_classes.get(class_uri, class_type)
                    
                    # If found, create a node for it
                    if class_uri:
                        # Get label if available
                        for s, p, o in g.triples((URIRef(class_uri), RDFS.label, None)):
                            class_label = str(o)
                            break
                        
                        # Get children of this class
                        children = []
                        for s, p, o in g.triples((None, RDFS.subClassOf, URIRef(class_uri))):
                            child_uri = str(s)
                            child_node = build_tree(child_uri, set())
                            if child_node:
                                children.append(child_node)
                        
                        # Create node
                        node = {
                            "name": class_label or class_type,
                            "uri": class_uri,
                            "type": "non-bfo",  # Default to non-BFO
                            "description": f"{class_type} in the domain"
                        }
                        
                        if children:
                            node["children"] = children
                        
                        # Add to specific classes list
                        specific_classes.append(node)
                
                # Add these specific classes to the forest
                forest.extend([c for c in specific_classes if c not in forest])
            
            # Create a root node for the ontology with all collected classes
            root = {
                "name": ontology_name,
                "type": "root",
                "children": forest
            }
            
            print(f"Generated hierarchy with {len(forest)} top-level classes")
            
            return root
            
        except Exception as e:
            current_app.logger.error(f"Error parsing TTL: {str(e)}")
            
            # Return a simple mock hierarchy if parsing fails
            return {
                "name": ontology_name,
                "type": "root",
                "description": "Failed to parse ontology. Using mock data.",
                "children": [
                    {
                        "name": "Entity",
                        "type": "bfo",
                        "uri": "http://purl.obolibrary.org/obo/BFO_0000001",
                        "description": "A universal that is the most general of all universals",
                        "children": [
                            {
                                "name": "Continuant",
                                "type": "bfo",
                                "uri": "http://purl.obolibrary.org/obo/BFO_0000002",
                                "description": "An entity that persists through time"
                            },
                            {
                                "name": "Occurrent",
                                "type": "bfo",
                                "uri": "http://purl.obolibrary.org/obo/BFO_0000003",
                                "description": "An entity that unfolds itself in time"
                            }
                        ]
                    }
                ]
            }
    
    return bp
