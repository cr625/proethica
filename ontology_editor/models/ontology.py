"""
Ontology models for the ontology editor.
"""
from datetime import datetime
from typing import List, Dict, Optional, Any, Union

class Ontology:
    """
    Represents an ontology with metadata.
    """
    
    def __init__(
        self,
        id: Union[int, str],
        filename: str,
        title: str,
        domain: str,
        description: str = "",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        created_by: Optional[Union[int, str]] = None
    ):
        """
        Initialize an ontology.
        
        Args:
            id: Unique identifier for the ontology
            filename: Name of the ontology file
            title: Display title for the ontology
            domain: Domain the ontology belongs to
            description: Optional description of the ontology
            created_at: When the ontology was created
            updated_at: When the ontology was last updated
            created_by: User ID of the creator
        """
        self.id = id
        self.filename = filename
        self.title = title
        self.domain = domain
        self.description = description
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.created_by = created_by
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the ontology to a dictionary.
        
        Returns:
            Dictionary representation of the ontology
        """
        return {
            "id": self.id,
            "filename": self.filename,
            "title": self.title,
            "domain": self.domain,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "created_by": self.created_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Ontology':
        """
        Create an Ontology from a dictionary.
        
        Args:
            data: Dictionary with ontology data
            
        Returns:
            Ontology instance
        """
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')
        
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        
        return cls(
            id=data.get('id'),
            filename=data.get('filename'),
            title=data.get('title'),
            domain=data.get('domain'),
            description=data.get('description', ''),
            created_at=created_at,
            updated_at=updated_at,
            created_by=data.get('created_by')
        )


class Version:
    """
    Represents a version of an ontology.
    """
    
    def __init__(
        self,
        id: Union[int, str],
        ontology_id: Union[int, str],
        version_number: int,
        file_path: str,
        commit_message: str = "",
        committed_at: Optional[datetime] = None,
        committed_by: Optional[Union[int, str]] = None
    ):
        """
        Initialize a version.
        
        Args:
            id: Unique identifier for the version
            ontology_id: ID of the associated ontology
            version_number: Sequential version number
            file_path: Path to the version file
            commit_message: Optional message describing the changes
            committed_at: When the version was committed
            committed_by: User ID of the committer
        """
        self.id = id
        self.ontology_id = ontology_id
        self.version_number = version_number
        self.file_path = file_path
        self.commit_message = commit_message
        self.committed_at = committed_at or datetime.now()
        self.committed_by = committed_by
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the version to a dictionary.
        
        Returns:
            Dictionary representation of the version
        """
        return {
            "id": self.id,
            "ontology_id": self.ontology_id,
            "version_number": self.version_number,
            "file_path": self.file_path,
            "commit_message": self.commit_message,
            "committed_at": self.committed_at.isoformat() if self.committed_at else None,
            "committed_by": self.committed_by
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Version':
        """
        Create a Version from a dictionary.
        
        Args:
            data: Dictionary with version data
            
        Returns:
            Version instance
        """
        committed_at = data.get('committed_at')
        
        if isinstance(committed_at, str):
            committed_at = datetime.fromisoformat(committed_at)
        
        return cls(
            id=data.get('id'),
            ontology_id=data.get('ontology_id'),
            version_number=data.get('version_number'),
            file_path=data.get('file_path'),
            commit_message=data.get('commit_message', ''),
            committed_at=committed_at,
            committed_by=data.get('committed_by')
        )
