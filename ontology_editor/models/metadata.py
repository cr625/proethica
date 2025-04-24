"""
Metadata storage for ontologies.

This module handles storing and retrieving metadata about ontologies
and their versions. It uses a JSON file for storage.
"""

import os
import json
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import threading

class MetadataStorage:
    """Class for storing and retrieving ontology metadata."""
    
    # File paths
    _BASE_DIR = os.path.join(os.path.dirname(__file__), '../../ontologies')
    _METADATA_FILE = os.path.join(_BASE_DIR, 'metadata.json')
    _VERSIONS_FILE = os.path.join(_BASE_DIR, 'versions.json')
    
    # Locks for file access
    _metadata_lock = threading.Lock()
    _versions_lock = threading.Lock()
    
    def __init__(self):
        """Initialize the metadata storage."""
        # Create base directory if it doesn't exist
        os.makedirs(self._BASE_DIR, exist_ok=True)
        
        # Create metadata file if it doesn't exist
        if not os.path.exists(self._METADATA_FILE):
            with open(self._METADATA_FILE, 'w') as f:
                json.dump([], f)
        
        # Create versions file if it doesn't exist
        if not os.path.exists(self._VERSIONS_FILE):
            with open(self._VERSIONS_FILE, 'w') as f:
                json.dump([], f)
    
    def get_all_ontologies(self) -> List[Dict[str, Any]]:
        """
        Get all ontologies.
        
        Returns:
            List of ontology objects
        """
        with self._metadata_lock:
            with open(self._METADATA_FILE, 'r') as f:
                return json.load(f)
    
    def get_ontology(self, ontology_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get an ontology by ID.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            Ontology object or None if not found
        """
        ontology_id = str(ontology_id)
        
        with self._metadata_lock:
            with open(self._METADATA_FILE, 'r') as f:
                ontologies = json.load(f)
            
            for ontology in ontologies:
                if str(ontology.get('id')) == ontology_id:
                    return ontology
        
        return None
    
    def get_ontology_by_id(self, ontology_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """Alias for get_ontology."""
        return self.get_ontology(ontology_id)
    
    def add_ontology(self, ontology: Dict[str, Any]) -> str:
        """
        Add a new ontology.
        
        Args:
            ontology: Ontology object
            
        Returns:
            ID of the new ontology
        """
        with self._metadata_lock:
            with open(self._METADATA_FILE, 'r') as f:
                ontologies = json.load(f)
            
            # Generate a new ID
            if ontologies:
                new_id = str(max([int(o.get('id', 0)) for o in ontologies]) + 1)
            else:
                new_id = '1'
            
            # Set the ID and timestamps
            ontology['id'] = new_id
            ontology['created_at'] = datetime.now().isoformat()
            ontology['updated_at'] = datetime.now().isoformat()
            
            # Add the ontology
            ontologies.append(ontology)
            
            # Save the ontologies
            with open(self._METADATA_FILE, 'w') as f:
                json.dump(ontologies, f, indent=2)
            
            return new_id
    
    def update_ontology(self, ontology_id: Union[int, str], updates: Dict[str, Any]) -> bool:
        """
        Update an ontology.
        
        Args:
            ontology_id: ID of the ontology
            updates: Dictionary of updates
            
        Returns:
            True if successful, False if not found
        """
        ontology_id = str(ontology_id)
        
        with self._metadata_lock:
            with open(self._METADATA_FILE, 'r') as f:
                ontologies = json.load(f)
            
            # Find the ontology
            for i, ontology in enumerate(ontologies):
                if str(ontology.get('id')) == ontology_id:
                    # Update the ontology
                    ontologies[i].update(updates)
                    ontologies[i]['updated_at'] = datetime.now().isoformat()
                    
                    # Save the ontologies
                    with open(self._METADATA_FILE, 'w') as f:
                        json.dump(ontologies, f, indent=2)
                    
                    return True
        
        return False
    
    def delete_ontology(self, ontology_id: Union[int, str]) -> bool:
        """
        Delete an ontology.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            True if successful, False if not found
        """
        ontology_id = str(ontology_id)
        
        with self._metadata_lock:
            with open(self._METADATA_FILE, 'r') as f:
                ontologies = json.load(f)
            
            # Find the ontology
            for i, ontology in enumerate(ontologies):
                if str(ontology.get('id')) == ontology_id:
                    # Remove the ontology
                    del ontologies[i]
                    
                    # Save the ontologies
                    with open(self._METADATA_FILE, 'w') as f:
                        json.dump(ontologies, f, indent=2)
                    
                    # Delete associated versions
                    self.delete_versions_for_ontology(ontology_id)
                    
                    return True
        
        return False
    
    def get_versions(self, ontology_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Get all versions for an ontology.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            List of version objects
        """
        ontology_id = str(ontology_id)
        
        with self._versions_lock:
            with open(self._VERSIONS_FILE, 'r') as f:
                versions = json.load(f)
            
            # Filter versions for the ontology
            return [v for v in versions if str(v.get('ontology_id')) == ontology_id]
    
    def get_versions_for_ontology(self, ontology_id: Union[int, str]) -> List[Dict[str, Any]]:
        """Alias for get_versions."""
        return self.get_versions(ontology_id)
    
    def get_version_by_id(self, version_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get a version by ID.
        
        Args:
            version_id: ID of the version
            
        Returns:
            Version object or None if not found
        """
        version_id = str(version_id)
        
        with self._versions_lock:
            with open(self._VERSIONS_FILE, 'r') as f:
                versions = json.load(f)
            
            for version in versions:
                if str(version.get('id')) == version_id:
                    return version
        
        return None
    
    def add_version(self, version: Dict[str, Any]) -> str:
        """
        Add a new version.
        
        Args:
            version: Version object
            
        Returns:
            ID of the new version
        """
        with self._versions_lock:
            with open(self._VERSIONS_FILE, 'r') as f:
                versions = json.load(f)
            
            # Generate a new ID
            if versions:
                new_id = str(max([int(v.get('id', 0)) for v in versions]) + 1)
            else:
                new_id = '1'
            
            # Set the ID and timestamps
            version['id'] = new_id
            version['created_at'] = datetime.now().isoformat()
            
            # Add the version
            versions.append(version)
            
            # Save the versions
            with open(self._VERSIONS_FILE, 'w') as f:
                json.dump(versions, f, indent=2)
            
            return new_id
    
    def delete_versions_for_ontology(self, ontology_id: Union[int, str]) -> bool:
        """
        Delete all versions for an ontology.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            True if successful
        """
        ontology_id = str(ontology_id)
        
        with self._versions_lock:
            with open(self._VERSIONS_FILE, 'r') as f:
                versions = json.load(f)
            
            # Filter out versions for the ontology
            versions = [v for v in versions if str(v.get('ontology_id')) != ontology_id]
            
            # Save the versions
            with open(self._VERSIONS_FILE, 'w') as f:
                json.dump(versions, f, indent=2)
            
            return True
