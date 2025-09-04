"""
State model representing environmental conditions and system states in scenarios.

This model represents the 'S' (State) category in the ProEthica formal model 
D = (R, P, O, S, Rs, A, E, Ca, Cs), storing conditions and situations
as first-class database objects.
"""

from app.models import db
from datetime import datetime
from sqlalchemy import JSON

class State(db.Model):
    """State model representing environmental conditions and system states in scenarios."""
    __tablename__ = 'states'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    state_type = db.Column(db.String(100))  # e.g., 'environmental', 'regulatory', 'organizational', 'project'
    value = db.Column(db.String(255))  # Current value/status
    
    # State tracking
    is_active = db.Column(db.Boolean, default=True)
    changed_by_action_id = db.Column(db.Integer, db.ForeignKey('actions.id'))
    previous_value = db.Column(db.String(255))  # Previous state value
    
    # BFO Ontology classification fields
    bfo_class = db.Column(db.String(255), default='BFO_0000019')  # quality
    proethica_category = db.Column(db.String(50), default='state')
    ontology_uri = db.Column(db.String(500))
    
    # LLM extraction metadata
    extraction_confidence = db.Column(db.Float, default=0.0)
    extraction_method = db.Column(db.String(100), default='llm_enhanced')
    validation_notes = db.Column(db.Text)
    
    # Temporal context
    observed_at_event_id = db.Column(db.Integer, db.ForeignKey('events.id'))
    duration_start = db.Column(db.DateTime)
    duration_end = db.Column(db.DateTime)
    
    # Relationships
    scenario = db.relationship('Scenario', backref='states')
    changed_by_action = db.relationship('Action', foreign_keys=[changed_by_action_id], post_update=True)
    observed_at_event = db.relationship('Event', foreign_keys=[observed_at_event_id], post_update=True)
    
    # Metadata for additional attributes
    state_metadata = db.Column(JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<State {self.name}: {self.value}>'
    
    def to_dict(self):
        """Convert state to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'description': self.description,
            'state_type': self.state_type,
            'value': self.value,
            'is_active': self.is_active,
            'changed_by_action_id': self.changed_by_action_id,
            'previous_value': self.previous_value,
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'validation_notes': self.validation_notes,
            'observed_at_event_id': self.observed_at_event_id,
            'duration_start': self.duration_start.isoformat() if self.duration_start else None,
            'duration_end': self.duration_end.isoformat() if self.duration_end else None,
            'metadata': self.state_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
