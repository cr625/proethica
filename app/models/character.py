from sqlalchemy import JSON
from app import db

class Character(db.Model):
    """Character model representing individuals in a scenario."""
    __tablename__ = 'characters'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100))  # Legacy field, kept for backward compatibility
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    attributes = db.Column(JSON)
    
    # Relationships
    conditions = db.relationship('Condition', backref='character', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='character')
    
    def __repr__(self):
        return f'<Character {self.name}>'
    
    def to_dict(self):
        """Convert character to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'role': self.role,
            'role_id': self.role_id,
            'role_name': self.role_obj.name if self.role_obj else None,
            'role_description': self.role_obj.description if self.role_obj else None,
            'attributes': self.attributes,
            'conditions': [condition.to_dict() for condition in self.conditions]
        }
