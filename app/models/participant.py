from sqlalchemy import JSON
from app.models import db

class Participant(db.Model):
    """Participant model representing individuals in a scenario (formerly Character)."""
    __tablename__ = 'participants'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100))  # Legacy field, kept for backward compatibility
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    attributes = db.Column(JSON, default=dict)
    
    # Ontology classification fields (new)
    bfo_class = db.Column(db.String(255), default='BFO_0000040')  # material entity (agent)
    proethica_category = db.Column(db.String(50), default='role')
    ontology_uri = db.Column(db.String(500))
    
    # Relationships
    conditions = db.relationship('Condition', backref='participant', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='participant')
    role_from_role = db.relationship('Role', foreign_keys=[role_id], overlaps="participants")
    entity_triples = db.relationship('EntityTriple', back_populates='participant', foreign_keys='EntityTriple.participant_id')
    
    def __repr__(self):
        return f'<Participant {self.name}>'
    
    def to_dict(self):
        """Convert participant to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'name': self.name,
            'role': self.role,
            'role_id': self.role_id,
            'role_name': self.role_from_role.name if self.role_from_role else None,
            'role_description': self.role_from_role.description if self.role_from_role else None,
            'attributes': self.attributes,
            'conditions': [condition.to_dict() for condition in self.conditions],
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri
        }

# Backward compatibility alias - keep Character as alias to Participant
Character = Participant