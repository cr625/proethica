"""
Ontology model for the ontology editor.

This module defines the data structure for ontologies and their versions.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Version:
    """
    Data class for an ontology version.
    """
    id: str
    ontology_id: str
    version_number: int
    file_path: str
    commit_message: str
    committed_by: Optional[str] = None
    created_at: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Version':
        """
        Create a Version instance from a dictionary.
        
        Args:
            data: Dictionary representation of a version
            
        Returns:
            Version instance
        """
        return cls(
            id=data.get('id', ''),
            ontology_id=data.get('ontology_id', ''),
            version_number=data.get('version_number', 0),
            file_path=data.get('file_path', ''),
            commit_message=data.get('commit_message', ''),
            committed_by=data.get('committed_by'),
            created_at=data.get('created_at')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the version to a dictionary.
        
        Returns:
            Dictionary representation of the version
        """
        return {
            'id': self.id,
            'ontology_id': self.ontology_id,
            'version_number': self.version_number,
            'file_path': self.file_path,
            'commit_message': self.commit_message,
            'committed_by': self.committed_by,
            'created_at': self.created_at
        }


@dataclass
class Ontology:
    """
    Data class for an ontology.
    """
    id: str
    title: str
    domain: str
    filename: str
    description: str = ''
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    versions: List[Version] = None
    
    def __post_init__(self):
        """Initialize the versions list if it's None."""
        if self.versions is None:
            self.versions = []
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], versions: Optional[List[Dict[str, Any]]] = None) -> 'Ontology':
        """
        Create an Ontology instance from a dictionary.
        
        Args:
            data: Dictionary representation of an ontology
            versions: Optional list of version dictionaries
            
        Returns:
            Ontology instance
        """
        ontology = cls(
            id=data.get('id', ''),
            title=data.get('title', ''),
            domain=data.get('domain', ''),
            filename=data.get('filename', ''),
            description=data.get('description', ''),
            created_by=data.get('created_by'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
        
        # Add versions if provided
        if versions:
            ontology.versions = [Version.from_dict(v) for v in versions]
        
        return ontology
    
    def to_dict(self, include_versions: bool = False) -> Dict[str, Any]:
        """
        Convert the ontology to a dictionary.
        
        Args:
            include_versions: Whether to include versions in the result
            
        Returns:
            Dictionary representation of the ontology
        """
        result = {
            'id': self.id,
            'title': self.title,
            'domain': self.domain,
            'filename': self.filename,
            'description': self.description,
            'created_by': self.created_by,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
        
        # Add versions if requested
        if include_versions and self.versions:
            result['versions'] = [v.to_dict() for v in self.versions]
        
        return result
    
    def add_version(self, version: Version) -> None:
        """
        Add a version to the ontology.
        
        Args:
            version: Version to add
        """
        self.versions.append(version)
        self.updated_at = datetime.now().isoformat()
    
    def get_current_version(self) -> Optional[Version]:
        """
        Get the current version of the ontology.
        
        Returns:
            Current version or None if no versions exist
        """
        if not self.versions:
            return None
        
        # Return the version with the highest version number
        return max(self.versions, key=lambda v: v.version_number)
