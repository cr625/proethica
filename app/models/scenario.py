from datetime import datetime
from sqlalchemy import JSON
from app import db

class Scenario(db.Model):
    """Scenario model representing a simulation scenario."""
    __tablename__ = 'scenarios'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    domain_id = db.Column(db.Integer, db.ForeignKey('domains.id'), nullable=False)
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
            'domain_id': self.domain_id,
            'domain_name': self.domain.name if self.domain else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.scenario_metadata
        }
