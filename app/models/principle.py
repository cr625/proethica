"""
Principle model representing ethical principles in scenarios.

This model represents the 'P' (Principle) category in the ProEthica formal model 
D = (R, P, O, S, Rs, A, E, Ca, Cs), storing ethical guidelines and standards
as first-class database objects.
"""

from app.models import db
from datetime import datetime
from sqlalchemy import JSON

class Principle(db.Model):
    """Principle model representing ethical principles and guidelines in scenarios."""
    __tablename__ = 'principles'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    principle_type = db.Column(db.String(100))  # e.g., 'nspe_code', 'professional_duty', 'ethical_standard'
    source = db.Column(db.String(255))  # e.g., 'NSPE Code II.1.a'
    
    # BFO Ontology classification fields
    bfo_class = db.Column(db.String(255), default='BFO_0000031')  # generically dependent continuant
    proethica_category = db.Column(db.String(50), default='principle')
    ontology_uri = db.Column(db.String(500))
    
    # LLM extraction metadata
    extraction_confidence = db.Column(db.Float, default=0.0)
    extraction_method = db.Column(db.String(100), default='llm_enhanced')
    validation_notes = db.Column(db.Text)
    
    # Temporal context
    applies_from = db.Column(db.Integer)  # Event/action ID when principle becomes relevant
    applies_until = db.Column(db.Integer)  # Event/action ID when principle no longer applies
    
    # Relationships
    scenario = db.relationship('Scenario', backref='principles')
    
    # Metadata for additional attributes
    principle_metadata = db.Column(JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Principle {self.name}>'
    
    def to_dict(self):
        """Convert principle to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'description': self.description,
            'principle_type': self.principle_type,
            'source': self.source,
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'validation_notes': self.validation_notes,
            'applies_from': self.applies_from,
            'applies_until': self.applies_until,
            'metadata': self.principle_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
