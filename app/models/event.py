from datetime import datetime
from sqlalchemy import JSON
from app import db
from app.models.entity import Entity

class Action(db.Model):
    """Action model representing possible actions in scenarios."""
    __tablename__ = 'actions'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    parameters = db.Column(JSON)  # Parameters that can be set for this action
    
    # Relationships
    events = db.relationship('Event', backref='action')
    
    def __repr__(self):
        return f'<Action {self.name}>'
    
    def to_dict(self):
        """Convert action to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'parameters': self.parameters
        }

class Event(db.Model):
    """Event model representing things that happen in a scenario."""
    __tablename__ = 'events'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=True)
    action_id = db.Column(db.Integer, db.ForeignKey('actions.id'), nullable=True)
    event_time = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    parameters = db.Column(JSON)  # Specific parameters for this event instance
    
    # Relationships
    entities = db.relationship('Entity', secondary='event_entity', back_populates='events')
    
    def __repr__(self):
        return f'<Event {self.id} at {self.event_time}>'
    
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
