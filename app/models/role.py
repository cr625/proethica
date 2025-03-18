from app import db
from datetime import datetime

class Role(db.Model):
    """
    Role model representing character roles within a specific world.
    Roles are defined in OWL ontologies and associated with worlds.
    """
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=False)
    tier = db.Column(db.Integer)  # For hierarchical roles (e.g., Tier 1, Tier 2)
    ontology_uri = db.Column(db.String(255))  # URI reference to the OWL entity
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with world
    world = db.relationship('World', backref='roles')
    
    # Relationship with characters
    characters = db.relationship('Character', backref='role_obj')
    
    # Metadata for storing additional information
    role_metadata = db.Column(db.JSON, default=lambda: {})
    
    def __repr__(self):
        return f'<Role {self.name}>'
    
    def to_dict(self):
        """Convert the role to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'world_id': self.world_id,
            'world_name': self.world.name if self.world else None,
            'tier': self.tier,
            'ontology_uri': self.ontology_uri,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.role_metadata
        }
