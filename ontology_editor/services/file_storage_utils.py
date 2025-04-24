"""
File storage utilities for the ontology editor.

This module provides helper functions for reading and writing ontology files.
"""
import os
import shutil
from typing import Optional

# Base directory for ontology storage
ONTOLOGIES_DIR = os.path.join(os.path.dirname(__file__), '../../ontologies')

def read_ontology_file(domain: str, relative_path: str) -> Optional[str]:
    """
    Read the content of an ontology file.
    
    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory
        
    Returns:
        Content of the file, or None if not found
    """
    file_path = os.path.join(ONTOLOGIES_DIR, 'domains', domain, relative_path)
    
    # Check if the file exists
    if not os.path.exists(file_path):
        # Check if we should use a source file from mcp/ontology
        mcp_path = os.path.join(os.path.dirname(__file__), '../../mcp/ontology', os.path.basename(file_path))
        
        if os.path.exists(mcp_path):
            # Create the directory structure if it doesn't exist
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Copy the file from mcp/ontology to our ontologies directory
            shutil.copy2(mcp_path, file_path)
        else:
            return None
    
    # Read the content
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except:
        return None

def write_ontology_file(domain: str, relative_path: str, content: str) -> bool:
    """
    Write content to an ontology file.
    
    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory
        content: Content to write to the file
        
    Returns:
        True if successful, False otherwise
    """
    file_path = os.path.join(ONTOLOGIES_DIR, 'domains', domain, relative_path)
    
    # Create the directory if it doesn't exist
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    # Write the content
    try:
        with open(file_path, 'w') as f:
            f.write(content)
        return True
    except:
        return False
