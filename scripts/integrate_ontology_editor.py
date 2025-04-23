#!/usr/bin/env python3
"""
Ontology Editor Integration Script

This script demonstrates how to integrate the ontology editor with the ProEthica application.
It also sets up initial import of existing ontology files from the mcp/ontology directory.
"""
import os
import sys
import shutil
import argparse
from datetime import datetime

# Add the parent directory to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# Import the app factory
from app import create_app
from ontology_editor import create_ontology_editor_blueprint
from ontology_editor.models.metadata import MetadataStorage
from ontology_editor.services.file_storage import create_directory_structure

def integrate_ontology_editor(require_auth=True, admin_only=True):
    """
    Integrate the ontology editor with the ProEthica application.
    
    Args:
        require_auth: Whether to require authentication for the editor
        admin_only: Whether to restrict editing to admin users
    """
    print("Integrating the ontology editor with ProEthica...")
    
    # Create the Flask app
    app = create_app()
    
    # Create the ontology editor blueprint
    ontology_editor_bp = create_ontology_editor_blueprint(
        config={
            'require_auth': require_auth,
            'admin_only': admin_only
        }
    )
    
    # Register the blueprint with the app
    app.register_blueprint(ontology_editor_bp)
    
    # Print success message
    print("Successfully integrated the ontology editor!")
    print(f"The editor can be accessed at: http://localhost:5000/ontology-editor")
    print(f"Authentication required: {require_auth}")
    print(f"Admin-only editing: {admin_only}")
    
    return app

def setup_ontology_directory():
    """
    Set up the ontology directory structure and import existing ontologies.
    """
    print("Setting up ontology directory structure...")
    
    # Create directory structure
    create_directory_structure()
    
    # Initialize metadata storage
    metadata_storage = MetadataStorage()
    
    # Import existing ontologies from mcp/ontology directory
    mcp_ontology_dir = os.path.join('mcp', 'ontology')
    if os.path.exists(mcp_ontology_dir):
        print(f"Importing ontologies from {mcp_ontology_dir}...")
        
        # Get the list of TTL files in the mcp/ontology directory
        ttl_files = [f for f in os.listdir(mcp_ontology_dir) if f.endswith('.ttl')]
        
        # Import each file
        for filename in ttl_files:
            # Skip certain files
            if filename in ['bfo.ttl', 'bfo-core.ttl']:
                continue
                
            print(f"  Importing {filename}...")
            
            # Determine the domain from the filename
            domain = filename.replace('.ttl', '').replace('-', '_')
            title = domain.replace('_', ' ').title()
            
            # Check if ontology already exists
            existing_ontologies = metadata_storage.get_all_ontologies()
            if any(o.get('filename') == filename for o in existing_ontologies):
                print(f"  Ontology {filename} already exists, skipping...")
                continue
            
            # Create ontology metadata
            ontology = {
                'filename': filename,
                'title': title,
                'domain': domain,
                'description': f"Imported from {mcp_ontology_dir}/{filename}",
                'created_at': datetime.now().isoformat(),
                'updated_at': datetime.now().isoformat()
            }
            
            # Add to metadata storage
            ontology_id = metadata_storage.add_ontology(ontology)
            
            # Set up directory structure
            domain_dir = os.path.join('ontologies', 'domains', domain)
            main_dir = os.path.join(domain_dir, 'main')
            versions_dir = os.path.join(main_dir, 'versions')
            
            os.makedirs(domain_dir, exist_ok=True)
            os.makedirs(main_dir, exist_ok=True)
            os.makedirs(versions_dir, exist_ok=True)
            
            # Copy the TTL file
            source_file = os.path.join(mcp_ontology_dir, filename)
            target_file = os.path.join(main_dir, 'current.ttl')
            shutil.copy2(source_file, target_file)
            
            # Create the first version
            version_file = os.path.join(versions_dir, 'v1.ttl')
            shutil.copy2(source_file, version_file)
            
            # Add version metadata
            version = {
                'ontology_id': ontology_id,
                'version_number': 1,
                'file_path': os.path.join('domains', domain, 'main', 'versions', 'v1.ttl'),
                'commit_message': 'Initial import',
                'committed_at': datetime.now().isoformat()
            }
            
            metadata_storage.add_version(version)
            
            print(f"  Successfully imported {filename} with ID {ontology_id}")
    else:
        print(f"MCP ontology directory {mcp_ontology_dir} not found, skipping import...")
    
    print("Ontology directory setup complete!")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Integrate the ontology editor with ProEthica')
    parser.add_argument('--no-auth', action='store_true', help='Disable authentication for the editor')
    parser.add_argument('--all-users', action='store_true', help='Allow all users to edit ontologies')
    parser.add_argument('--setup-only', action='store_true', help='Only set up the ontology directory, do not integrate with app')
    
    args = parser.parse_args()
    
    # Set up the ontology directory
    setup_ontology_directory()
    
    # Integrate with the app if not setup only
    if not args.setup_only:
        integrate_ontology_editor(
            require_auth=not args.no_auth,
            admin_only=not args.all_users
        )

if __name__ == '__main__':
    main()
