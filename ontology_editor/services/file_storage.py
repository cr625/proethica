"""
File storage service for the ontology editor.

This service handles the storage and retrieval of ontology files,
including version control and metadata management.
"""
import os
import json
import shutil
from typing import List, Dict, Optional, Any, Union
from datetime import datetime

from ontology_editor.models.metadata import MetadataStorage
from ontology_editor.models.ontology import Ontology, Version

# Initialize metadata storage
metadata_storage = MetadataStorage()

# Base directory for ontology storage
ONTOLOGIES_DIR = os.path.join(os.path.dirname(__file__), '../../ontologies')

def create_directory_structure():
    """Create the necessary directory structure for ontology storage."""
    # Create base directory if it doesn't exist
    os.makedirs(ONTOLOGIES_DIR, exist_ok=True)
    
    # Create domains directory
    domains_dir = os.path.join(ONTOLOGIES_DIR, 'domains')
    os.makedirs(domains_dir, exist_ok=True)
    
    # Create imports directory
    imports_dir = os.path.join(ONTOLOGIES_DIR, 'imports')
    os.makedirs(imports_dir, exist_ok=True)
    
    # Create bfo directory in imports
    bfo_dir = os.path.join(imports_dir, 'bfo')
    os.makedirs(bfo_dir, exist_ok=True)

# Create directory structure on module import
create_directory_structure()

def get_all_ontologies() -> List[Dict[str, Any]]:
    """
    Get all ontologies with metadata.
    
    Returns:
        List of ontology metadata
    """
    return metadata_storage.get_all_ontologies()

def get_ontology_content(ontology_id: Union[int, str]) -> str:
    """
    Get the content of an ontology file.
    
    Args:
        ontology_id: ID of the ontology
        
    Returns:
        Content of the ontology file
        
    Raises:
        FileNotFoundError: If the ontology file doesn't exist
    """
    ontology = metadata_storage.get_ontology_by_id(ontology_id)
    
    if not ontology:
        raise FileNotFoundError(f"Ontology with ID {ontology_id} not found")
    
    # Construct the path to the current version of the ontology
    domain = ontology.get('domain')
    filename = ontology.get('filename')
    
    file_path = os.path.join(ONTOLOGIES_DIR, 'domains', domain, 'main', 'current.ttl')
    
    # If no file exists yet, check if we should use a source file from mcp/ontology
    if not os.path.exists(file_path) and filename:
        # Check if the file exists in the mcp/ontology directory
        mcp_path = os.path.join(os.path.dirname(__file__), '../../mcp/ontology', filename)
        
        if os.path.exists(mcp_path):
            # Create the directory structure if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Copy the file from mcp/ontology to our ontologies directory
            shutil.copy2(mcp_path, file_path)
    
    # If the file still doesn't exist, raise an error
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Ontology file not found at {file_path}")
    
    # Read the content
    with open(file_path, 'r') as f:
        content = f.read()
    
    return content

def create_new_ontology(
    filename: str,
    title: str,
    domain: str,
    content: str = "",
    description: str = "",
    created_by: Optional[Union[int, str]] = None
) -> str:
    """
    Create a new ontology.
    
    Args:
        filename: Name of the ontology file
        title: Display title for the ontology
        domain: Domain the ontology belongs to
        content: Initial content of the ontology file
        description: Description of the ontology
        created_by: ID of the user creating the ontology
        
    Returns:
        ID of the new ontology
        
    Raises:
        ValueError: If the ontology creation fails
    """
    # Create the ontology metadata
    ontology = {
        'filename': filename,
        'title': title,
        'domain': domain,
        'description': description,
        'created_by': created_by,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    # Add the ontology to the metadata storage
    ontology_id = metadata_storage.add_ontology(ontology)
    
    # Construct the path to the ontology file
    domain_dir = os.path.join(ONTOLOGIES_DIR, 'domains', domain)
    main_dir = os.path.join(domain_dir, 'main')
    versions_dir = os.path.join(main_dir, 'versions')
    
    # Create the directories if they don't exist
    os.makedirs(domain_dir, exist_ok=True)
    os.makedirs(main_dir, exist_ok=True)
    os.makedirs(versions_dir, exist_ok=True)
    
    # Create the current version file
    current_file = os.path.join(main_dir, 'current.ttl')
    
    try:
        # Write the content to the file
        with open(current_file, 'w') as f:
            f.write(content)
        
        # Create the first version
        version = {
            'ontology_id': ontology_id,
            'version_number': 1,
            'file_path': os.path.join('domains', domain, 'main', 'versions', 'v1.ttl'),
            'commit_message': 'Initial version',
            'committed_by': created_by
        }
        
        # Add the version to the metadata storage
        version_id = metadata_storage.add_version(version)
        
        # Copy the current file to the version file
        version_file = os.path.join(ONTOLOGIES_DIR, version['file_path'])
        shutil.copy2(current_file, version_file)
        
        return ontology_id
    
    except Exception as e:
        # Clean up the metadata if file creation fails
        metadata_storage.delete_ontology(ontology_id)
        
        # Re-raise the exception
        raise ValueError(f"Failed to create ontology file: {str(e)}")

def update_ontology_content(
    ontology_id: Union[int, str],
    content: str,
    description: str = "",
    committed_by: Optional[Union[int, str]] = None
) -> bool:
    """
    Update the content of an ontology.
    
    Args:
        ontology_id: ID of the ontology
        content: New content for the ontology file
        description: Updated description (optional)
        committed_by: ID of the user making the update
        
    Returns:
        True if successful, False if not found
        
    Raises:
        FileNotFoundError: If the ontology doesn't exist
    """
    ontology = metadata_storage.get_ontology_by_id(ontology_id)
    
    if not ontology:
        raise FileNotFoundError(f"Ontology with ID {ontology_id} not found")
    
    # Update the description if provided
    if description:
        updates = {'description': description}
        metadata_storage.update_ontology(ontology_id, updates)
    
    # Construct the path to the current version of the ontology
    domain = ontology.get('domain')
    main_dir = os.path.join(ONTOLOGIES_DIR, 'domains', domain, 'main')
    current_file = os.path.join(main_dir, 'current.ttl')
    
    # Write the content to the file
    with open(current_file, 'w') as f:
        f.write(content)
    
    # Get the next version number
    versions = metadata_storage.get_versions_for_ontology(ontology_id)
    version_number = 1 + max([v.get('version_number', 0) for v in versions], default=0)
    
    # Create a new version
    version = {
        'ontology_id': ontology_id,
        'version_number': version_number,
        'file_path': os.path.join('domains', domain, 'main', 'versions', f'v{version_number}.ttl'),
        'commit_message': f'Update to version {version_number}',
        'committed_by': committed_by
    }
    
    # Add the version to the metadata storage
    version_id = metadata_storage.add_version(version)
    
    # Copy the current file to the version file
    version_file = os.path.join(ONTOLOGIES_DIR, version['file_path'])
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    shutil.copy2(current_file, version_file)
    
    return True

def delete_ontology(ontology_id: Union[int, str]) -> bool:
    """
    Delete an ontology.
    
    Args:
        ontology_id: ID of the ontology
        
    Returns:
        True if successful, False if not found
    """
    ontology = metadata_storage.get_ontology_by_id(ontology_id)
    
    if not ontology:
        return False
    
    # Delete the ontology from the metadata storage
    result = metadata_storage.delete_ontology(ontology_id)
    
    if result:
        # Delete the ontology directory
        domain = ontology.get('domain')
        domain_dir = os.path.join(ONTOLOGIES_DIR, 'domains', domain)
        
        # Only delete the domain directory if it exists
        if os.path.exists(domain_dir):
            shutil.rmtree(domain_dir)
    
    return result

def get_ontology_versions(ontology_id: Union[int, str]) -> List[Dict[str, Any]]:
    """
    Get all versions for an ontology.
    
    Args:
        ontology_id: ID of the ontology
        
    Returns:
        List of version metadata
    """
    return metadata_storage.get_versions_for_ontology(ontology_id)

def get_version_content(version_id: Union[int, str]) -> str:
    """
    Get the content of a specific version.
    
    Args:
        version_id: ID of the version
        
    Returns:
        Content of the version file
        
    Raises:
        FileNotFoundError: If the version file doesn't exist
    """
    version = metadata_storage.get_version_by_id(version_id)
    
    if not version:
        raise FileNotFoundError(f"Version with ID {version_id} not found")
    
    # Construct the path to the version file
    file_path = os.path.join(ONTOLOGIES_DIR, version.get('file_path'))
    
    # If the file doesn't exist, raise an error
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Version file not found at {file_path}")
    
    # Read the content
    with open(file_path, 'r') as f:
        content = f.read()
    
    return content

def create_new_version(
    ontology_id: Union[int, str],
    content: str,
    commit_message: str = "",
    committed_by: Optional[Union[int, str]] = None
) -> str:
    """
    Create a new version for an ontology.
    
    Args:
        ontology_id: ID of the ontology
        content: Content for the new version
        commit_message: Message describing the changes
        committed_by: ID of the user making the commit
        
    Returns:
        ID of the new version
        
    Raises:
        FileNotFoundError: If the ontology doesn't exist
    """
    ontology = metadata_storage.get_ontology_by_id(ontology_id)
    
    if not ontology:
        raise FileNotFoundError(f"Ontology with ID {ontology_id} not found")
    
    # Update the current file
    domain = ontology.get('domain')
    main_dir = os.path.join(ONTOLOGIES_DIR, 'domains', domain, 'main')
    current_file = os.path.join(main_dir, 'current.ttl')
    
    # Write the content to the current file
    with open(current_file, 'w') as f:
        f.write(content)
    
    # Get the next version number
    versions = metadata_storage.get_versions_for_ontology(ontology_id)
    version_number = 1 + max([v.get('version_number', 0) for v in versions], default=0)
    
    # Create a new version
    version = {
        'ontology_id': ontology_id,
        'version_number': version_number,
        'file_path': os.path.join('domains', domain, 'main', 'versions', f'v{version_number}.ttl'),
        'commit_message': commit_message or f'Update to version {version_number}',
        'committed_by': committed_by
    }
    
    # Add the version to the metadata storage
    version_id = metadata_storage.add_version(version)
    
    # Copy the current file to the version file
    version_file = os.path.join(ONTOLOGIES_DIR, version['file_path'])
    os.makedirs(os.path.dirname(version_file), exist_ok=True)
    shutil.copy2(current_file, version_file)
    
    return version_id
