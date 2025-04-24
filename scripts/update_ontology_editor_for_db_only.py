#!/usr/bin/env python3
"""
Script to update ontology editor to use database exclusively.
"""

import os
import sys
import shutil

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from app.models.ontology_version import OntologyVersion

def update_ontology_editor():
    """Update ontology editor files to use database only."""
    # Path to ontology_editor/services/file_storage_utils.py
    file_utils_path = os.path.join(
        os.path.dirname(__file__), 
        '../ontology_editor/services/file_storage_utils.py'
    )
    
    # Create backup of the file
    backup_path = file_utils_path + '.bak'
    shutil.copy2(file_utils_path, backup_path)
    print(f"Created backup of file_storage_utils.py at {backup_path}")
    
    # Update the file with database-only implementation
    new_content = """\"\"\"
File storage utilities for the ontology editor.

This module provides helper functions for reading and writing ontology files.
NOTE: This version has been modified to use the database exclusively.
\"\"\"
import os
import logging
from typing import Optional
from flask import current_app

# Set up logging
logger = logging.getLogger(__name__)

# Base directory for ontology storage (kept for compatibility)
ONTOLOGIES_DIR = os.path.join(os.path.dirname(__file__), '../../ontologies')

def read_ontology_file(domain: str, relative_path: str) -> Optional[str]:
    \"\"\"
    Read the content of an ontology file.
    
    This version logs a warning and returns None, as all ontologies
    should be retrieved from the database.

    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory

    Returns:
        None - all ontologies should come from database
    \"\"\"
    logger.warning(
        f"Attempted to read ontology file {domain}/{relative_path} from file system. "
        f"Ontologies are now stored in database."
    )
    return None

def write_ontology_file(domain: str, relative_path: str, content: str) -> bool:
    \"\"\"
    Write content to an ontology file.
    
    This version logs a warning and returns False, as all ontologies
    should be written to the database.

    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory
        content: Content to write to the file

    Returns:
        False - all ontologies should be written to database
    \"\"\"
    logger.warning(
        f"Attempted to write ontology file {domain}/{relative_path} to file system. "
        f"Ontologies are now stored in database."
    )
    return False
"""
    
    # Write the updated file
    with open(file_utils_path, 'w') as f:
        f.write(new_content)
    
    print(f"Updated file_storage_utils.py to database-only implementation")
    
    # Now update routes.py to remove file fallback
    routes_path = os.path.join(
        os.path.dirname(__file__), 
        '../ontology_editor/api/routes.py'
    )
    
    # Create backup of the routes file
    backup_routes_path = routes_path + '.bak'
    shutil.copy2(routes_path, backup_routes_path)
    print(f"Created backup of routes.py at {backup_routes_path}")
    
    # Read the current routes file
    with open(routes_path, 'r') as f:
        routes_content = f.read()
    
    # Update file with patterns to remove file fallbacks
    # This is a simplistic approach - might need manual review
    patterns = [
        ("            # If not in database, try the legacy metadata storage", 
         "            # Database-only mode: no file fallback\n            return jsonify({'error': 'Ontology not found'}), 404"),
        ("            # If not in database, try the legacy file-based approach", 
         "            # Database-only mode: no file fallback\n            return jsonify({'error': 'Ontology not found'}), 404"),
        ("from ..models.metadata import MetadataStorage", 
         "# Legacy file storage removed\n# from ..models.metadata import MetadataStorage"),
        ("from ..services.file_storage_utils import read_ontology_file, write_ontology_file",
         "# File operations disabled\n# from ..services.file_storage_utils import read_ontology_file, write_ontology_file"),
    ]
    
    for old, new in patterns:
        routes_content = routes_content.replace(old, new)
    
    # Write updated routes file
    with open(routes_path, 'w') as f:
        f.write(routes_content)
    
    print(f"Updated routes.py to remove file fallbacks")
    
    # Finally, remove the ontologies directory
    ontologies_dir = os.path.join(os.path.dirname(__file__), '../ontologies')
    backup_ontologies_dir = os.path.join(os.path.dirname(__file__), '../ontologies_removed')
    
    # Only move if not already moved
    if os.path.exists(ontologies_dir) and not os.path.exists(backup_ontologies_dir):
        shutil.move(ontologies_dir, backup_ontologies_dir)
        print(f"Moved ontologies directory to {backup_ontologies_dir}")
        
        # Create placeholder ontologies directory with empty metadata
        os.makedirs(ontologies_dir, exist_ok=True)
        with open(os.path.join(ontologies_dir, 'metadata.json'), 'w') as f:
            f.write('[]')
        with open(os.path.join(ontologies_dir, 'versions.json'), 'w') as f:
            f.write('[]')
        os.makedirs(os.path.join(ontologies_dir, 'domains'), exist_ok=True)
        print(f"Created empty placeholder ontologies directory")
    else:
        print(f"Ontologies directory already processed or moved")
    
    print("\nUpdate complete. The system will now exclusively use the database for ontologies.")
    print("Restart the server to apply these changes.")

if __name__ == "__main__":
    update_ontology_editor()
