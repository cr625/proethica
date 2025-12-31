"""
Constraint model representing boundaries and limitations in scenarios.

This model represents the 'Cs' (Constraint) category in the ProEthica formal model 
D = (R, P, O, S, Rs, A, E, Ca, Cs), storing boundaries and limitations
as first-class database objects.
"""

from app.models import db
from datetime import datetime
from sqlalchemy import JSON

class Constraint(db.Model):
    """Constraint model representing boundaries, limitations, and restrictions in scenarios."""
    __tablename__ = 'constraints'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    constraint_type = db.Column(db.String(100))  # e.g., 'legal', 'physical', 'temporal', 'resource', 'ethical'
    
    # Constraint attributes
    severity = db.Column(db.String(50), default='medium')  # 'low', 'medium', 'high', 'absolute'
    is_absolute = db.Column(db.Boolean, default=False)  # Whether constraint can be violated
    violation_consequences = db.Column(db.Text)  # What happens if constraint is violated
    
    # Scope - what the constraint applies to
    applies_to_character_id = db.Column(db.Integer, db.ForeignKey('characters.id'))
    applies_to_action_id = db.Column(db.Integer, db.ForeignKey('actions.id'))
    applies_to_resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'))
    constrains_capability_id = db.Column(db.Integer, db.ForeignKey('capabilities.id'))
    
    # BFO Ontology classification fields
    bfo_class = db.Column(db.String(255), default='BFO_0000017')  # realizable entity (matches ontology)
    proethica_category = db.Column(db.String(50), default='constraint')
    ontology_uri = db.Column(db.String(500))
    
    # LLM extraction metadata
    extraction_confidence = db.Column(db.Float, default=0.0)
    extraction_method = db.Column(db.String(100), default='llm_enhanced')
    validation_notes = db.Column(db.Text)
    
    # Temporal aspects
    active_from_event_id = db.Column(db.Integer, db.ForeignKey('events.id'))  # When constraint becomes active
    expires_at_event_id = db.Column(db.Integer, db.ForeignKey('events.id'))   # When constraint expires
    created_by_action_id = db.Column(db.Integer, db.ForeignKey('actions.id')) # Action that created constraint
    
    # Constraint relationships and dependencies
    conflicts_with_constraint_id = db.Column(db.Integer, db.ForeignKey('constraints.id'))  # Conflicting constraints
    supersedes_constraint_id = db.Column(db.Integer, db.ForeignKey('constraints.id'))     # Constraint this replaces
    
    # Relationships
    scenario = db.relationship('Scenario', backref='constraints')
    applies_to_character = db.relationship('Character', foreign_keys=[applies_to_character_id], post_update=True)
    applies_to_action = db.relationship('Action', foreign_keys=[applies_to_action_id], post_update=True)
    applies_to_resource = db.relationship('Resource', foreign_keys=[applies_to_resource_id], post_update=True)
    constrains_capability = db.relationship('Capability', foreign_keys=[constrains_capability_id], post_update=True)
    
    active_from_event = db.relationship('Event', foreign_keys=[active_from_event_id], post_update=True)
    expires_at_event = db.relationship('Event', foreign_keys=[expires_at_event_id], post_update=True)
    created_by_action = db.relationship('Action', foreign_keys=[created_by_action_id], post_update=True)
    
    conflicts_with = db.relationship('Constraint', remote_side=[id], foreign_keys=[conflicts_with_constraint_id], post_update=True)
    supersedes = db.relationship('Constraint', remote_side=[id], foreign_keys=[supersedes_constraint_id], post_update=True)
    
    # Metadata for additional attributes
    constraint_metadata = db.Column(JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Constraint {self.name} ({self.constraint_type})>'
    
    def to_dict(self):
        """Convert constraint to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'description': self.description,
            'constraint_type': self.constraint_type,
            'severity': self.severity,
            'is_absolute': self.is_absolute,
            'violation_consequences': self.violation_consequences,
            'applies_to_character_id': self.applies_to_character_id,
            'applies_to_action_id': self.applies_to_action_id,
            'applies_to_resource_id': self.applies_to_resource_id,
            'constrains_capability_id': self.constrains_capability_id,
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'validation_notes': self.validation_notes,
            'active_from_event_id': self.active_from_event_id,
            'expires_at_event_id': self.expires_at_event_id,
            'created_by_action_id': self.created_by_action_id,
            'conflicts_with_constraint_id': self.conflicts_with_constraint_id,
            'supersedes_constraint_id': self.supersedes_constraint_id,
            'metadata': self.constraint_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
