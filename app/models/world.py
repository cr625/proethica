from app.models import db
from datetime import datetime
import json
from sqlalchemy.orm import relationship

class World(db.Model):
    """
    A World represents a collection of characters, resources, events, and decisions
    that can be used in scenarios. The data for these worlds comes from an ontology source.
    """
    __tablename__ = 'worlds'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    ontology_source = db.Column(db.String(255))  # Reference to the ontology source (kept for backward compatibility)
    ontology_id = db.Column(db.Integer, nullable=True)  # Removed FK constraint - ontologies moved to OntServe
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User ownership and data classification
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    data_type = db.Column(db.String(20), default='user')  # 'system' or 'user'
    
    # Cases and rulesets
    cases = db.Column(db.JSON, default=lambda: [])  # List of cases associated with this world
    rulesets = db.Column(db.JSON, default=lambda: [])  # List of rulesets associated with this world
    
    # Relationships
    creator = db.relationship('User', backref='created_worlds')
    scenarios = relationship('Scenario', back_populates='world', lazy=True)
    guidelines = relationship('Guideline', back_populates='world', lazy=True, cascade="all, delete-orphan")
    entity_triples = relationship('EntityTriple', back_populates='world', lazy=True,
                              primaryjoin="World.id==EntityTriple.world_id")
    
    # Metadata for storing additional information
    world_metadata = db.Column(db.JSON, default=lambda: {})
    
    def __repr__(self):
        return f'<World {self.name}>'
    
    def to_dict(self):
        """Convert the world to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'ontology_source': self.ontology_source,
            'ontology_id': self.ontology_id,
            'cases': self.cases,
            'rulesets': self.rulesets,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.world_metadata,
            'guideline_count': len(self.guidelines) if self.guidelines else 0,
            'entity_triple_count': len(self.entity_triples) if self.entity_triples else 0,
            'created_by': self.created_by,
            'data_type': self.data_type,
            'is_system_data': self.is_system_data()
        }
    
    def can_edit(self, user):
        """Check if the user can edit this world."""
        if not user or not user.is_authenticated:
            return False
        
        # Admin can edit everything
        if getattr(user, 'is_admin', False):
            return True
        
        # System data can only be edited by admins
        if self.data_type == 'system':
            return False
        
        # User can edit their own content
        return self.created_by == user.id
    
    def can_delete(self, user):
        """Check if the user can delete this world."""
        # Same rules as editing
        return self.can_edit(user)
    
    def can_view(self, user):
        """Check if the user can view this world."""
        # All users can view all worlds (read-only for system data)
        return True
    
    def is_system_data(self):
        """Check if this is system data (read-only for non-admins)."""
        return self.data_type == 'system'
    
    def is_user_data(self):
        """Check if this is user-created data."""
        return self.data_type == 'user'
