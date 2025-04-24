"""
File storage utilities for the ontology editor.

This module provides helper functions for reading and writing ontology files.
NOTE: This version has been modified to use the database exclusively.
"""
import os
import logging
from typing import Optional
from flask import current_app

# Set up logging
logger = logging.getLogger(__name__)

# Base directory for ontology storage (kept for compatibility)
ONTOLOGIES_DIR = os.path.join(os.path.dirname(__file__), '../../ontologies')

def read_ontology_file(domain: str, relative_path: str) -> Optional[str]:
    """
    Read the content of an ontology file.
    
    This version logs a warning and returns None, as all ontologies
    should be retrieved from the database.

    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory

    Returns:
        None - all ontologies should come from database
    """
    logger.warning(
        f"Attempted to read ontology file {domain}/{relative_path} from file system. "
        f"Ontologies are now stored in database."
    )
    return None

def write_ontology_file(domain: str, relative_path: str, content: str) -> bool:
    """
    Write content to an ontology file.
    
    This version logs a warning and returns False, as all ontologies
    should be written to the database.

    Args:
        domain: Domain of the ontology
        relative_path: Relative path within the domain directory
        content: Content to write to the file

    Returns:
        False - all ontologies should be written to database
    """
    logger.warning(
        f"Attempted to write ontology file {domain}/{relative_path} to file system. "
        f"Ontologies are now stored in database."
    )
    return False
