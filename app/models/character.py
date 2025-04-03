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
    attributes = db.Column(JSON, default=dict)
    
    # Relationships
    conditions = db.relationship('Condition', backref='character', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='character')
    role_from_role = db.relationship('Role', foreign_keys=[role_id], overlaps="characters")
    
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
            'role_name': self.role_from_role.name if self.role_from_role else None,
            'role_description': self.role_from_role.description if self.role_from_role else None,
            'attributes': self.attributes,
            'conditions': [condition.to_dict() for condition in self.conditions]
        }
