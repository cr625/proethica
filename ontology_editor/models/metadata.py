"""
Database models for ontology metadata.
"""
from typing import Dict, List, Optional, Any, Union
import json
import os
import time
from datetime import datetime

# In a production environment, this would be a proper ORM model (e.g., SQLAlchemy)
# For simplicity in this MVP, we'll use a file-based approach

class MetadataStorage:
    """
    Handles storage and retrieval of ontology metadata.
    """
    
    def __init__(self, storage_dir: str = None):
        """
        Initialize the metadata storage.
        
        Args:
            storage_dir: Directory for metadata storage
        """
        self.storage_dir = storage_dir or os.path.join(os.path.dirname(__file__), '../../ontologies')
        self.metadata_file = os.path.join(self.storage_dir, 'metadata.json')
        self.versions_file = os.path.join(self.storage_dir, 'versions.json')
        
        # Create directory if it doesn't exist
        os.makedirs(self.storage_dir, exist_ok=True)
        
        # Initialize metadata file if it doesn't exist
        if not os.path.exists(self.metadata_file):
            with open(self.metadata_file, 'w') as f:
                json.dump([], f)
        
        # Initialize versions file if it doesn't exist
        if not os.path.exists(self.versions_file):
            with open(self.versions_file, 'w') as f:
                json.dump([], f)
    
    def get_all_ontologies(self) -> List[Dict[str, Any]]:
        """
        Get all ontology metadata.
        
        Returns:
            List of ontology metadata dictionaries
        """
        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_ontology_by_id(self, ontology_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get ontology metadata by ID.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            Ontology metadata or None if not found
        """
        ontologies = self.get_all_ontologies()
        
        for ontology in ontologies:
            if str(ontology.get('id')) == str(ontology_id):
                return ontology
        
        return None
    
    def add_ontology(self, ontology: Dict[str, Any]) -> str:
        """
        Add a new ontology to the metadata.
        
        Args:
            ontology: Ontology metadata dictionary
            
        Returns:
            ID of the new ontology
        """
        ontologies = self.get_all_ontologies()
        
        # Generate a unique ID if not provided
        if 'id' not in ontology:
            ontology['id'] = str(int(time.time()))
        
        # Set creation and update timestamps
        if 'created_at' not in ontology:
            ontology['created_at'] = datetime.now().isoformat()
        
        if 'updated_at' not in ontology:
            ontology['updated_at'] = datetime.now().isoformat()
        
        ontologies.append(ontology)
        
        with open(self.metadata_file, 'w') as f:
            json.dump(ontologies, f, indent=2)
        
        return ontology['id']
    
    def update_ontology(self, ontology_id: Union[int, str], updates: Dict[str, Any]) -> bool:
        """
        Update an existing ontology's metadata.
        
        Args:
            ontology_id: ID of the ontology
            updates: Dictionary of updates to apply
            
        Returns:
            True if successful, False if not found
        """
        ontologies = self.get_all_ontologies()
        
        for i, ontology in enumerate(ontologies):
            if str(ontology.get('id')) == str(ontology_id):
                # Update fields
                for key, value in updates.items():
                    if key != 'id':  # Don't allow changing the ID
                        ontology[key] = value
                
                # Update the timestamp
                ontology['updated_at'] = datetime.now().isoformat()
                
                # Save the changes
                with open(self.metadata_file, 'w') as f:
                    json.dump(ontologies, f, indent=2)
                
                return True
        
        return False
    
    def delete_ontology(self, ontology_id: Union[int, str]) -> bool:
        """
        Delete an ontology from the metadata.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            True if successful, False if not found
        """
        ontologies = self.get_all_ontologies()
        
        for i, ontology in enumerate(ontologies):
            if str(ontology.get('id')) == str(ontology_id):
                # Remove the ontology
                del ontologies[i]
                
                # Save the changes
                with open(self.metadata_file, 'w') as f:
                    json.dump(ontologies, f, indent=2)
                
                # Also delete associated versions
                self.delete_versions_for_ontology(ontology_id)
                
                return True
        
        return False
    
    def get_all_versions(self) -> List[Dict[str, Any]]:
        """
        Get all version metadata.
        
        Returns:
            List of version metadata dictionaries
        """
        try:
            with open(self.versions_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []
    
    def get_versions_for_ontology(self, ontology_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        Get all versions for a specific ontology.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            List of version metadata dictionaries
        """
        versions = self.get_all_versions()
        
        return [v for v in versions if str(v.get('ontology_id')) == str(ontology_id)]
    
    def get_version_by_id(self, version_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get version metadata by ID.
        
        Args:
            version_id: ID of the version
            
        Returns:
            Version metadata or None if not found
        """
        versions = self.get_all_versions()
        
        for version in versions:
            if str(version.get('id')) == str(version_id):
                return version
        
        return None
    
    def add_version(self, version: Dict[str, Any]) -> str:
        """
        Add a new version to the metadata.
        
        Args:
            version: Version metadata dictionary
            
        Returns:
            ID of the new version
        """
        versions = self.get_all_versions()
        
        # Generate a unique ID if not provided
        if 'id' not in version:
            version['id'] = str(int(time.time()))
        
        # Set commit timestamp
        if 'committed_at' not in version:
            version['committed_at'] = datetime.now().isoformat()
        
        # Calculate version number if not provided
        if 'version_number' not in version:
            existing_versions = self.get_versions_for_ontology(version['ontology_id'])
            version['version_number'] = 1 + max([v.get('version_number', 0) for v in existing_versions], default=0)
        
        versions.append(version)
        
        with open(self.versions_file, 'w') as f:
            json.dump(versions, f, indent=2)
        
        return version['id']
    
    def delete_versions_for_ontology(self, ontology_id: Union[int, str]) -> int:
        """
        Delete all versions for a specific ontology.
        
        Args:
            ontology_id: ID of the ontology
            
        Returns:
            Number of versions deleted
        """
        versions = self.get_all_versions()
        
        # Filter out versions for the specified ontology
        new_versions = [v for v in versions if str(v.get('ontology_id')) != str(ontology_id)]
        
        # Calculate number of versions deleted
        num_deleted = len(versions) - len(new_versions)
        
        # Save the changes
        with open(self.versions_file, 'w') as f:
            json.dump(new_versions, f, indent=2)
        
        return num_deleted
