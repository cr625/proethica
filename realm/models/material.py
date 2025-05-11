"""
Material Model for REALM.

This module defines the Material model for storing and managing material data.
"""

from typing import Dict, List, Any, Optional
import datetime
import json
from sqlalchemy import Column, String, Text, DateTime, JSON
from sqlalchemy.sql import func

from realm.database import Base

class Material(Base):
    """Model representing a material from the MSEO ontology."""
    
    __tablename__ = 'materials'
    
    id = Column(String(36), primary_key=True)
    uri = Column(String(255), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    label = Column(String(100))
    description = Column(Text)
    categories = Column(JSON, default=list)
    properties = Column(JSON, default=dict)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __init__(self, uri: str, name: str, label: str = "", description: str = "", id=None):
        """Initialize a material.
        
        Args:
            uri: URI of the material in the ontology
            name: Name of the material
            label: Display label for the material
            description: Description of the material
            id: Optional ID (defaults to a generated UUID)
        """
        import uuid
        self.id = id or str(uuid.uuid4())
        self.uri = uri
        self.name = name
        self.label = label if label else name
        self.description = description
        self.categories = []
        self.properties = {}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Material':
        """Create a material from a dictionary.
        
        Args:
            data: Dictionary containing material data
            
        Returns:
            Material instance
        """
        material = cls(
            uri=data.get("uri", ""),
            name=data.get("name", ""),
            label=data.get("label", ""),
            description=data.get("description", ""),
            id=data.get("id")
        )
        
        # Add categories
        if "categories" in data:
            material.categories = data["categories"]
        
        # Add properties
        if "properties" in data:
            if isinstance(data["properties"], list):
                for prop in data["properties"]:
                    material.properties[prop["name"]] = prop["value"]
            else:
                material.properties = data["properties"]
        
        return material
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert material to a dictionary.
        
        Returns:
            Dictionary representation of the material
        """
        # Convert properties from JSON dictionary to list format for API
        props_list = [
            {"name": name, "value": value}
            for name, value in self.properties.items()
        ] if self.properties else []
        
        return {
            "id": self.id,
            "uri": self.uri,
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "categories": self.categories or [],
            "properties": props_list,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Update material from a dictionary.
        
        Args:
            data: Dictionary containing material data
        """
        if "name" in data:
            self.name = data["name"]
        
        if "label" in data:
            self.label = data["label"]
        
        if "description" in data:
            self.description = data["description"]
        
        if "categories" in data:
            self.categories = data["categories"]
        
        if "properties" in data:
            if isinstance(data["properties"], list):
                for prop in data["properties"]:
                    self.properties[prop["name"]] = prop["value"]
            else:
                self.properties = data["properties"]
    
    def get_property(self, name: str) -> Optional[str]:
        """Get a property value by name.
        
        Args:
            name: Name of the property
            
        Returns:
            Property value, or None if not found
        """
        return self.properties.get(name) if self.properties else None
    
    def set_property(self, name: str, value: str) -> None:
        """Set a property value.
        
        Args:
            name: Name of the property
            value: Value of the property
        """
        if self.properties is None:
            self.properties = {}
        self.properties[name] = value
    
    def add_category(self, category: str) -> None:
        """Add a category to the material.
        
        Args:
            category: Category to add
        """
        if self.categories is None:
            self.categories = []
        if category not in self.categories:
            self.categories.append(category)
    
    def remove_category(self, category: str) -> None:
        """Remove a category from the material.
        
        Args:
            category: Category to remove
        """
        if self.categories and category in self.categories:
            self.categories.remove(category)
    
    def __str__(self) -> str:
        """Return string representation of the material.
        
        Returns:
            String representation
        """
        return f"{self.label} ({self.name})"
    
    def __repr__(self) -> str:
        """Return string representation of the material.
        
        Returns:
            String representation
        """
        return f"Material(uri='{self.uri}', name='{self.name}')"
