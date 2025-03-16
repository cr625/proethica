from datetime import datetime
from sqlalchemy import JSON
from app import db

class Scenario(db.Model):
    """Scenario model representing a simulation scenario."""
    __tablename__ = 'scenarios'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    scenario_metadata = db.Column(JSON)
    
    # Relationships
    characters = db.relationship('Character', backref='scenario', cascade='all, delete-orphan')
    resources = db.relationship('Resource', backref='scenario', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='scenario', cascade='all, delete-orphan')
    decisions = db.relationship('Decision', backref='scenario', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Scenario {self.name}>'
    
    def to_dict(self):
        """Convert scenario to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.scenario_metadata
        }
