from datetime import datetime
from app.models import db

class SimulationState(db.Model):
    """
    Model for storing simulation state.
    
    This model stores the current state of a simulation, including
    the current event index, decisions made, and other state information.
    It's designed to be simpler than the full SimulationSession model.
    """
    __tablename__ = 'simulation_states'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    current_event_index = db.Column(db.Integer, default=0)
    decisions = db.Column(db.JSON, default=list)
    state_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    scenario = db.relationship('Scenario', backref=db.backref('simulation_states', lazy=True))
    user = db.relationship('User', backref=db.backref('simulation_states', lazy=True))
    
    def __repr__(self):
        return f'<SimulationState {self.id} for Scenario {self.scenario_id}>'
    
    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'scenario_id': self.scenario_id,
            'user_id': self.user_id,
            'current_event_index': self.current_event_index,
            'decisions': self.decisions,
            'state_data': self.state_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
