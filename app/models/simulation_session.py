from datetime import datetime
from app.models import db

class SimulationSession(db.Model):
    """
    Model for storing simulation sessions.
    
    This model stores the state and history of a simulation session, including
    all decisions made, evaluations, and the timeline of events.
    """
    __tablename__ = 'simulation_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    session_data = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scenario = db.relationship('Scenario', backref=db.backref('simulation_sessions', lazy=True))
    # TODO: Fix circular import issue with User model
    # Temporarily commented out for testing section embeddings
    # user = db.relationship('User', backref=db.backref('simulation_sessions', lazy=True))
    
    def __repr__(self):
        return f'<SimulationSession {self.id} for Scenario {self.scenario_id}>'
    
    def to_dict(self):
        """Convert the model to a dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'user_id': self.user_id,
            'session_data': self.session_data,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
