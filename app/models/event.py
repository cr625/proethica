from datetime import datetime
from sqlalchemy import JSON
from app import db
from app.models.entity import Entity
from app.models.event_entity import event_entity
from app.models.evaluation import Evaluation

class Action(db.Model):
    """Action model representing possible actions and decisions in scenarios."""
    __tablename__ = 'actions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)
    action_time = db.Column(db.DateTime, default=datetime.utcnow)
    parameters = db.Column(JSON, default=dict)  # Parameters that can be set for this action
    
    # Decision-specific fields
    is_decision = db.Column(db.Boolean, default=False)  # Flag to indicate if this is a decision point
    options = db.Column(JSON, default=list)  # Available options (for decisions)
    selected_option = db.Column(db.String(255))  # The option selected (for decisions)
    
    # Ontology integration
    ontology_uri = db.Column(db.String(255))  # Link to the ontology
    action_type = db.Column(db.String(255))  # Type of action from ontology
    
    # Relationships
    events = db.relationship('Event', backref='action')
    evaluations = db.relationship('Evaluation', backref='action', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Action {self.name}>'
        
    def __lt__(self, other):
        """Define less than comparison for sorting."""
        if isinstance(other, Action):
            return self.id < other.id
        return NotImplemented
    
    def to_dict(self):
        """Convert action to dictionary."""
        result = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'scenario_id': self.scenario_id,
            'character_id': self.character_id,
            'action_time': self.action_time.isoformat() if self.action_time else None,
            'parameters': self.parameters,
            'is_decision': self.is_decision,
            'ontology_uri': self.ontology_uri,
            'action_type': self.action_type
        }
        
        # Include decision-specific fields if this is a decision
        if self.is_decision:
            result.update({
                'options': self.options,
                'selected_option': self.selected_option,
                'evaluations': [evaluation.to_dict() for evaluation in self.evaluations] if self.evaluations else []
            })
            
        return result

class Event(db.Model):
    """Event model representing things that happen in a scenario."""
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)
    action_id = db.Column(db.Integer, db.ForeignKey('actions.id'), nullable=True)
    event_time = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    parameters = db.Column(JSON, default=dict)  # Specific parameters for this event instance
    
    # Relationships
    entities = db.relationship('Entity', secondary='event_entity', back_populates='events')
    
    def __repr__(self):
        return f'<Event {self.id} at {self.event_time}>'
        
    def __lt__(self, other):
        """Define less than comparison for sorting."""
        if isinstance(other, Event):
            return self.id < other.id
        return NotImplemented
    
    def to_dict(self):
        """Convert event to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'character_id': self.character_id,
            'action_id': self.action_id,
            'event_time': self.event_time.isoformat() if self.event_time else None,
            'description': self.description,
            'parameters': self.parameters,
            'action': self.action.to_dict() if self.action else None
        }
