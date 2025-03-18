from app import db
from datetime import datetime

class ConditionType(db.Model):
    """
    ConditionType model representing types of conditions available within a specific world.
    Condition types are defined in OWL ontologies and associated with worlds.
    """
    __tablename__ = 'condition_types'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=False)
    category = db.Column(db.String(100))  # E.g., injury, disease, psychological
    severity_range = db.Column(db.JSON, default=lambda: {"min": 1, "max": 10})  # Define possible severity range
    ontology_uri = db.Column(db.String(255))  # URI reference to the OWL entity
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with world
    world = db.relationship('World', backref='condition_types')
    
    # Relationship with conditions
    conditions = db.relationship('Condition', backref='condition_type')
    
    # Metadata for storing additional information
    condition_type_metadata = db.Column(db.JSON, default=lambda: {})
    
    def __repr__(self):
        return f'<ConditionType {self.name}>'
    
    def to_dict(self):
        """Convert the condition type to a dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'world_id': self.world_id,
            'world_name': self.world.name if self.world else None,
            'category': self.category,
            'severity_range': self.severity_range,
            'ontology_uri': self.ontology_uri,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.condition_type_metadata
        }
