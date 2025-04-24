from app import db
from datetime import datetime
import json

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
    ontology_id = db.Column(db.Integer, db.ForeignKey('ontologies.id'), nullable=True)  # Direct reference to Ontology model
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Cases and rulesets
    cases = db.Column(db.JSON, default=lambda: [])  # List of cases associated with this world
    rulesets = db.Column(db.JSON, default=lambda: [])  # List of rulesets associated with this world
    
    # Relationship with scenarios
    scenarios = db.relationship('Scenario', backref='world', lazy=True)
    
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
            'metadata': self.world_metadata
        }
