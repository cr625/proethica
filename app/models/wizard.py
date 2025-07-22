"""
Wizard models for interactive timeline scenarios.

These models support step-by-step progression through ethical scenarios
with decision tracking and session management.
"""

from datetime import datetime
from sqlalchemy import JSON
from app.models import db


class WizardStep(db.Model):
    """
    Represents an individual step in a wizard-style scenario walkthrough.
    Each step corresponds to either an event or a decision point in the timeline.
    """
    __tablename__ = 'wizard_steps'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    step_number = db.Column(db.Integer, nullable=False)
    step_type = db.Column(db.String(50), nullable=False)  # 'event', 'decision', 'summary'
    title = db.Column(db.String(255), nullable=False)
    narrative_content = db.Column(db.Text)  # Protagonist-perspective narrative
    
    # Reference to the actual timeline element
    timeline_reference_id = db.Column(db.Integer)  # Event.id or Action.id
    timeline_reference_type = db.Column(db.String(50))  # 'event' or 'action'
    
    # Additional configuration and content
    step_metadata = db.Column(JSON, default=dict)  # Flexible storage for step-specific data
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    scenario = db.relationship('Scenario', backref='wizard_steps')
    
    def __repr__(self):
        return f'<WizardStep {self.step_number}: {self.title}>'
    
    def to_dict(self):
        """Convert wizard step to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'step_number': self.step_number,
            'step_type': self.step_type,
            'title': self.title,
            'narrative_content': self.narrative_content,
            'timeline_reference_id': self.timeline_reference_id,
            'timeline_reference_type': self.timeline_reference_type,
            'step_metadata': self.step_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class UserWizardSession(db.Model):
    """
    Tracks a user's progress through a wizard-style scenario.
    Stores their choices and allows for save/resume functionality.
    """
    __tablename__ = 'user_wizard_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    
    # Progress tracking
    current_step = db.Column(db.Integer, default=1)
    steps_completed = db.Column(db.Integer, default=0)
    total_steps = db.Column(db.Integer)
    
    # Session timing
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # User choices - {step_number: selected_option_id}
    choices = db.Column(JSON, default=dict)
    
    # Session status
    session_status = db.Column(db.String(50), default='active')  # 'active', 'completed', 'abandoned'
    
    # Additional session data
    session_metadata = db.Column(JSON, default=dict)  # For storing additional context
    
    # Relationships
    user = db.relationship('User', backref='wizard_sessions')
    scenario = db.relationship('Scenario', backref='wizard_sessions')
    
    def __repr__(self):
        return f'<UserWizardSession {self.user_id}:{self.scenario_id} - Step {self.current_step}>'
    
    def to_dict(self):
        """Convert session to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'scenario_id': self.scenario_id,
            'current_step': self.current_step,
            'steps_completed': self.steps_completed,
            'total_steps': self.total_steps,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'last_accessed_at': self.last_accessed_at.isoformat() if self.last_accessed_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'choices': self.choices,
            'session_status': self.session_status,
            'session_metadata': self.session_metadata,
            'progress_percentage': round((self.steps_completed / self.total_steps * 100) if self.total_steps else 0, 1)
        }
    
    def record_choice(self, step_number, option_id):
        """Record a user's choice for a specific step."""
        if not self.choices:
            self.choices = {}
        self.choices[str(step_number)] = option_id
        self.last_accessed_at = datetime.utcnow()
        
    def advance_step(self):
        """Move to the next step."""
        self.current_step += 1
        self.steps_completed = max(self.steps_completed, self.current_step - 1)
        self.last_accessed_at = datetime.utcnow()
        
    def go_back(self):
        """Move to the previous step."""
        if self.current_step > 1:
            self.current_step -= 1
            self.last_accessed_at = datetime.utcnow()
            
    def complete_session(self):
        """Mark the session as completed."""
        self.completed_at = datetime.utcnow()
        self.session_status = 'completed'
        self.steps_completed = self.total_steps