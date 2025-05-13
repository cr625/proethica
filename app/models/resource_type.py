from app.models import db
from datetime import datetime

class ResourceType(db.Model):
    """
    ResourceType model representing types of resources available within a specific world.
    Resource types are defined in OWL ontologies and associated with worlds.
    """
    __tablename__ = 'resource_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=False)
    category = db.Column(db.String(100))  # E.g., medical, equipment, personnel
    ontology_uri = db.Column(db.String(255))  # URI reference to the OWL entity
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with world
    world = db.relationship('World', backref='resource_types')
    
    # Relationship with resources
    resources = db.relationship('Resource', backref='resource_type')
    
    # Metadata for storing additional information
    resource_type_metadata = db.Column(db.JSON, default=lambda: {})
    
    def __repr__(self):
        return f'<ResourceType {self.name}>'
    
    def to_dict(self):
        """Convert the resource type to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'world_id': self.world_id,
            'world_name': self.world.name if self.world else None,
            'category': self.category,
            'ontology_uri': self.ontology_uri,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.resource_type_metadata
        }
