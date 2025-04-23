"""
API routes for the ontology editor.
"""
from flask import jsonify, request, render_template, redirect, url_for, current_app
from flask_login import login_required, current_user

def register_routes(blueprint, config=None):
    """
    Register routes with the blueprint.
    
    Args:
        blueprint: Flask blueprint
        config: Configuration dictionary
    """
    # Initialize configuration
    if config is None:
        config = {}
    
    # Default configuration
    require_auth = config.get('require_auth', True)
    admin_only = config.get('admin_only', True)
    
    # Define a decorator for authentication
    def auth_required(f):
        if require_auth:
            return login_required(f)
        return f
    
    # Define a decorator for admin-only access
    def admin_only_required(f):
        def decorated_function(*args, **kwargs):
            if require_auth and admin_only and not getattr(current_user, 'is_admin', False):
                return jsonify({"error": "Admin access required"}), 403
            return f(*args, **kwargs)
        decorated_function.__name__ = f.__name__
        return decorated_function if require_auth else f
    
    # Main editor page
    @blueprint.route('/')
    @auth_required
    def index():
        """Main editor page."""
        return render_template('editor.html')
    
    # API: List all ontologies
    @blueprint.route('/api/ontologies', methods=['GET'])
    @auth_required
    def list_ontologies():
        """List all available ontologies."""
        from ontology_editor.services.file_storage import get_all_ontologies
        
        try:
            ontologies = get_all_ontologies()
            return jsonify({"ontologies": ontologies})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Get ontology content
    @blueprint.route('/api/ontologies/<ontology_id>', methods=['GET'])
    @auth_required
    def get_ontology(ontology_id):
        """Get the content of a specific ontology."""
        from ontology_editor.services.file_storage import get_ontology_content
        
        try:
            content = get_ontology_content(ontology_id)
            return jsonify({"content": content})
        except FileNotFoundError:
            return jsonify({"error": f"Ontology {ontology_id} not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Update ontology
    @blueprint.route('/api/ontologies/<ontology_id>', methods=['PUT'])
    @auth_required
    @admin_only_required
    def update_ontology(ontology_id):
        """Update a specific ontology."""
        from ontology_editor.services.file_storage import update_ontology_content
        
        try:
            data = request.get_json()
            if not data or 'content' not in data:
                return jsonify({"error": "Missing content in request"}), 400
                
            content = data['content']
            description = data.get('description', '')
            
            # Validate the content before saving
            from ontology_editor.services.validator import validate_ttl_syntax
            valid, errors = validate_ttl_syntax(content)
            
            if not valid:
                return jsonify({
                    "valid": False,
                    "errors": errors
                }), 400
            
            # Get the current user's ID for attribution
            user_id = getattr(current_user, 'id', None) if require_auth else None
            
            # Update the ontology
            updated = update_ontology_content(
                ontology_id, 
                content, 
                description=description,
                committed_by=user_id
            )
            
            return jsonify({
                "valid": True,
                "updated": updated
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Create new ontology
    @blueprint.route('/api/ontologies', methods=['POST'])
    @auth_required
    @admin_only_required
    def create_ontology():
        """Create a new ontology."""
        from ontology_editor.services.file_storage import create_new_ontology
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing data in request"}), 400
                
            required_fields = ['filename', 'title', 'domain']
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing required field: {field}"}), 400
            
            # Get optional fields
            content = data.get('content', '')
            description = data.get('description', '')
            
            # Validate the content if provided
            if content:
                from ontology_editor.services.validator import validate_ttl_syntax
                valid, errors = validate_ttl_syntax(content)
                
                if not valid:
                    return jsonify({
                        "valid": False,
                        "errors": errors
                    }), 400
            
            # Get the current user's ID for attribution
            user_id = getattr(current_user, 'id', None) if require_auth else None
            
            # Create the ontology
            ontology_id = create_new_ontology(
                data['filename'],
                data['title'],
                data['domain'],
                content=content,
                description=description,
                created_by=user_id
            )
            
            return jsonify({
                "valid": True,
                "ontology_id": ontology_id
            }), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Delete ontology
    @blueprint.route('/api/ontologies/<ontology_id>', methods=['DELETE'])
    @auth_required
    @admin_only_required
    def delete_ontology(ontology_id):
        """Delete a specific ontology."""
        from ontology_editor.services.file_storage import delete_ontology
        
        try:
            deleted = delete_ontology(ontology_id)
            if deleted:
                return jsonify({"deleted": True})
            else:
                return jsonify({"error": f"Ontology {ontology_id} not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Validate ontology against BFO
    @blueprint.route('/api/validate/<ontology_id>', methods=['GET'])
    @auth_required
    def validate_ontology(ontology_id):
        """Validate a specific ontology against BFO."""
        from ontology_editor.services.file_storage import get_ontology_content
        from ontology_editor.services.validator import validate_bfo_compliance
        
        try:
            content = get_ontology_content(ontology_id)
            results = validate_bfo_compliance(content)
            return jsonify(results)
        except FileNotFoundError:
            return jsonify({"error": f"Ontology {ontology_id} not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: List versions for an ontology
    @blueprint.route('/api/versions/<ontology_id>', methods=['GET'])
    @auth_required
    def list_versions(ontology_id):
        """List all versions for a specific ontology."""
        from ontology_editor.services.file_storage import get_ontology_versions
        
        try:
            versions = get_ontology_versions(ontology_id)
            return jsonify({"versions": versions})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Get specific version
    @blueprint.route('/api/versions/<version_id>', methods=['GET'])
    @auth_required
    def get_version(version_id):
        """Get a specific version of an ontology."""
        from ontology_editor.services.file_storage import get_version_content
        
        try:
            content = get_version_content(version_id)
            return jsonify({"content": content})
        except FileNotFoundError:
            return jsonify({"error": f"Version {version_id} not found"}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # API: Create new version (commit)
    @blueprint.route('/api/versions/<ontology_id>', methods=['POST'])
    @auth_required
    @admin_only_required
    def create_version(ontology_id):
        """Create a new version (commit) for a specific ontology."""
        from ontology_editor.services.file_storage import create_new_version
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"error": "Missing data in request"}), 400
                
            content = data.get('content')
            commit_message = data.get('commit_message', '')
            
            if not content:
                return jsonify({"error": "Missing content in request"}), 400
            
            # Validate the content before saving
            from ontology_editor.services.validator import validate_ttl_syntax
            valid, errors = validate_ttl_syntax(content)
            
            if not valid:
                return jsonify({
                    "valid": False,
                    "errors": errors
                }), 400
            
            # Get the current user's ID for attribution
            user_id = getattr(current_user, 'id', None) if require_auth else None
            
            # Create the version
            version_id = create_new_version(
                ontology_id,
                content, 
                commit_message=commit_message,
                committed_by=user_id
            )
            
            return jsonify({
                "valid": True,
                "version_id": version_id
            }), 201
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    # Visualization page for an ontology
    @blueprint.route('/visualize/<ontology_id>')
    @auth_required
    def visualize_ontology(ontology_id):
        """Visualize a specific ontology."""
        return render_template('hierarchy.html', ontology_id=ontology_id)
