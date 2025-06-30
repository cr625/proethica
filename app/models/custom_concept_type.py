"""
Model for approved custom concept types.
"""

from datetime import datetime
from app.models import db


class CustomConceptType(db.Model):
    """Model for approved custom concept types that can be added to the ontology."""
    
    __tablename__ = 'custom_concept_types'
    
    id = db.Column(db.Integer, primary_key=True)
    type_name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    parent_type = db.Column(db.String(255), nullable=False)
    ontology_uri = db.Column(db.String(500))
    created_from_pending_id = db.Column(db.Integer, db.ForeignKey('pending_concept_types.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    created_from_pending = db.relationship('PendingConceptType', backref='created_custom_type')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            parent_type.in_(['role', 'principle', 'obligation', 'state', 'resource', 'action', 'event', 'capability']), 
            name='valid_parent_type'
        ),
        db.CheckConstraint(
            db.func.length(type_name) >= 2, 
            name='type_name_min_length'
        ),
        db.CheckConstraint(
            db.func.length(description) >= 10, 
            name='description_min_length'
        ),
    )
    
    def __repr__(self):
        return f'<CustomConceptType {self.id}: {self.type_name} -> {self.parent_type}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'type_name': self.type_name,
            'description': self.description,
            'parent_type': self.parent_type,
            'ontology_uri': self.ontology_uri,
            'created_from_pending_id': self.created_from_pending_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'is_active': self.is_active,
        }
    
    def deactivate(self):
        """Deactivate this custom type."""
        self.is_active = False
    
    def activate(self):
        """Activate this custom type."""
        self.is_active = True
    
    @classmethod
    def get_active_types(cls):
        """Get all active custom types."""
        return cls.query.filter_by(is_active=True).order_by(cls.type_name).all()
    
    @classmethod
    def get_by_parent_type(cls, parent_type):
        """Get all custom types with a specific parent type."""
        return cls.query.filter_by(parent_type=parent_type, is_active=True).all()
    
    @classmethod
    def create_from_pending(cls, pending_type, ontology_uri=None):
        """Create a custom type from an approved pending type."""
        custom_type = cls(
            type_name=pending_type.suggested_type,
            description=pending_type.suggested_description,
            parent_type=pending_type.suggested_parent_type,
            ontology_uri=ontology_uri,
            created_from_pending_id=pending_type.id
        )
        return custom_type
    
    @property
    def is_core_type(self):
        """Check if this is one of the 8 core ontology types."""
        core_types = {'role', 'principle', 'obligation', 'state', 'resource', 'action', 'event', 'capability'}
        return self.type_name.lower() in core_types
    
    def get_full_hierarchy(self):
        """Get the full type hierarchy for this custom type."""
        hierarchy = [self.type_name]
        if self.parent_type:
            hierarchy.append(self.parent_type)
        return ' -> '.join(reversed(hierarchy))