from app import db
from datetime import datetime

class Resource(db.Model):
    """Resource model representing available resources in a scenario."""
    __tablename__ = 'resources'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(100))  # Legacy field, kept for backward compatibility
    resource_type_id = db.Column(db.Integer, db.ForeignKey('resource_types.id'))
    quantity = db.Column(db.Integer, default=1)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Resource {self.name} ({self.quantity})>'
    
    def to_dict(self):
        """Convert resource to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'type': self.type,
            'resource_type_id': self.resource_type_id,
            'resource_type_name': self.resource_type.name if self.resource_type else None,
            'resource_type_category': self.resource_type.category if self.resource_type else None,
            'quantity': self.quantity,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
