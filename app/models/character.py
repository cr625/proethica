from sqlalchemy import JSON
from app.models import db

class Character(db.Model):
    """Character model representing individuals in a scenario."""
    __tablename__ = 'characters'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(100))  # Legacy field, kept for backward compatibility
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    attributes = db.Column(JSON, default=dict)
    
    # BFO Ontology classification fields (added 2025-08-08)
    bfo_class = db.Column(db.String(255), default='BFO_0000040')  # material entity (agent)
    proethica_category = db.Column(db.String(50), default='role')
    ontology_uri = db.Column(db.String(500))
    
    # Role matching fields (added 2025-08-09)
    original_llm_role = db.Column(db.String(255))  # Original role extracted by LLM
    matched_ontology_role_id = db.Column(db.String(500))  # ID of matched ontology role
    matching_confidence = db.Column(db.Float)  # Confidence score of the match
    matching_method = db.Column(db.String(50), default='semantic_llm_validated')  # Method used for matching
    matching_reasoning = db.Column(db.Text)  # LLM reasoning for the match
    
    # Relationships
    # Legacy relationship; Condition.character_id now references participants.id.
    # Provide explicit join and mark as viewonly to avoid FK configuration errors.
    conditions = db.relationship(
        'Condition',
        primaryjoin='Character.id==Condition.character_id',
        foreign_keys='Condition.character_id',
        backref='character',
        cascade='all, delete-orphan',
        viewonly=True,
    )
    events = db.relationship('Event', backref='character')
    role_from_role = db.relationship('Role', foreign_keys=[role_id], overlaps="characters")
    entity_triples = db.relationship('EntityTriple', back_populates='character', foreign_keys='EntityTriple.character_id')
    
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
            'conditions': [condition.to_dict() for condition in self.conditions],
            'bfo_class': self.bfo_class,
            'proethica_category': self.proethica_category,
            'ontology_uri': self.ontology_uri,
            'original_llm_role': self.original_llm_role,
            'matched_ontology_role_id': self.matched_ontology_role_id,
            'matching_confidence': self.matching_confidence,
            'matching_method': self.matching_method,
            'matching_reasoning': self.matching_reasoning
        }
