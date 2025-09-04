"""
Obligation model representing professional duties and requirements in scenarios.

This model represents the 'O' (Obligation) category in the ProEthica formal model 
D = (R, P, O, S, Rs, A, E, Ca, Cs), storing concrete requirements and duties
as first-class database objects.
"""

from app.models import db
from datetime import datetime
from sqlalchemy import JSON

class Obligation(db.Model):
    """Obligation model representing professional duties and requirements in scenarios."""
    __tablename__ = 'obligations'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    obligation_type = db.Column(db.String(100))  # e.g., 'legal_requirement', 'professional_duty', 'ethical_mandate'
    severity = db.Column(db.String(50), default='medium')  # 'low', 'medium', 'high', 'critical'
    
    # Source tracking
    source_principle_id = db.Column(db.Integer, db.ForeignKey('principles.id'))  # Links to underlying principle
    legal_basis = db.Column(db.String(255))  # Legal or regulatory basis
    
    # BFO Ontology classification fields
    bfo_class = db.Column(db.String(255), default='BFO_0000017')  # realizable entity
    proethica_category = db.Column(db.String(50), default='obligation')
    ontology_uri = db.Column(db.String(500))
    
    # LLM extraction metadata
    extraction_confidence = db.Column(db.Float, default=0.0)
    extraction_method = db.Column(db.String(100), default='llm_enhanced')
    validation_notes = db.Column(db.Text)
    
    # Temporal and conditional context
    triggered_by_event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    fulfilled_by_action_id = db.Column(db.Integer, db.ForeignKey('actions.id'))
    deadline = db.Column(db.DateTime)  # When obligation must be fulfilled
    
    # Relationships
    scenario = db.relationship('Scenario', backref='obligations')
    source_principle = db.relationship('Principle', foreign_keys=[source_principle_id])
    triggered_by_event = db.relationship('Event', foreign_keys=[triggered_by_event_id], post_update=True)
    fulfilled_by_action = db.relationship('Action', foreign_keys=[fulfilled_by_action_id], post_update=True)
    
    # Metadata for additional attributes
    obligation_metadata = db.Column(JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Obligation {self.name}>'
    
    def to_dict(self):
        """Convert obligation to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'description': self.description,
            'obligation_type': self.obligation_type,
            'severity': self.severity,
            'source_principle_id': self.source_principle_id,
            'legal_basis': self.legal_basis,
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'validation_notes': self.validation_notes,
            'triggered_by_event_id': self.triggered_by_event_id,
            'fulfilled_by_action_id': self.fulfilled_by_action_id,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'metadata': self.obligation_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
