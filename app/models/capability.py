"""
Capability model representing skills and competencies in scenarios.

This model represents the 'Ca' (Capability) category in the ProEthica formal model 
D = (R, P, O, S, Rs, A, E, Ca, Cs), storing agent abilities and competencies
as first-class database objects.
"""

from app.models import db
from datetime import datetime
from sqlalchemy import JSON

class Capability(db.Model):
    """Capability model representing skills, competencies, and abilities in scenarios."""
    __tablename__ = 'capabilities'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)  # Who has this capability
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    capability_type = db.Column(db.String(100))  # e.g., 'technical_skill', 'knowledge_domain', 'authority', 'certification'
    
    # Capability attributes
    competency_level = db.Column(db.String(50), default='competent')  # 'novice', 'competent', 'proficient', 'expert'
    is_certified = db.Column(db.Boolean, default=False)  # Professional certification
    expires_date = db.Column(db.DateTime)  # When capability expires (e.g., license renewal)
    
    # BFO Ontology classification fields
    bfo_class = db.Column(db.String(255), default='BFO_0000016')  # disposition
    proethica_category = db.Column(db.String(50), default='capability')
    ontology_uri = db.Column(db.String(500))
    
    # LLM extraction metadata
    extraction_confidence = db.Column(db.Float, default=0.0)
    extraction_method = db.Column(db.String(100), default='llm_enhanced')
    validation_notes = db.Column(db.Text)
    
    # Capability evolution
    acquired_at_event_id = db.Column(db.Integer, db.ForeignKey('events.id'))  # When capability was gained
    enhanced_by_action_id = db.Column(db.Integer, db.ForeignKey('actions.id'))  # Action that improved capability
    
    # Prerequisites and dependencies
    requires_resource_id = db.Column(db.Integer, db.ForeignKey('resources.id'))  # Resource needed for capability
    prerequisite_capability_id = db.Column(db.Integer, db.ForeignKey('capabilities.id'))  # Required prerequisite
    
    # Relationships
    scenario = db.relationship('Scenario', backref='capabilities')
    character = db.relationship('Character', backref='capabilities')
    acquired_at_event = db.relationship('Event', foreign_keys=[acquired_at_event_id], post_update=True)
    enhanced_by_action = db.relationship('Action', foreign_keys=[enhanced_by_action_id], post_update=True)
    requires_resource = db.relationship('Resource', foreign_keys=[requires_resource_id], post_update=True)
    prerequisite_capability = db.relationship('Capability', remote_side=[id], post_update=True)
    
    # Metadata for additional attributes
    capability_metadata = db.Column(JSON, default=dict)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Capability {self.name} ({self.competency_level})>'
    
    def to_dict(self):
        """Convert capability to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'character_id': self.character_id,
            'character_name': self.character.name if self.character else None,
            'name': self.name,
            'description': self.description,
            'capability_type': self.capability_type,
            'competency_level': self.competency_level,
            'is_certified': self.is_certified,
            'expires_date': self.expires_date.isoformat() if self.expires_date else None,
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'extraction_confidence': self.extraction_confidence,
            'extraction_method': self.extraction_method,
            'validation_notes': self.validation_notes,
            'acquired_at_event_id': self.acquired_at_event_id,
            'enhanced_by_action_id': self.enhanced_by_action_id,
            'requires_resource_id': self.requires_resource_id,
            'prerequisite_capability_id': self.prerequisite_capability_id,
            'metadata': self.capability_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
