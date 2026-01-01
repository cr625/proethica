"""
Entity Match Confirmation Model

Captures user confirmations of entity-to-ontology matches for future learning.
This data can be used to improve automated matching algorithms.
"""

from datetime import datetime
from app.models import db


class EntityMatchConfirmation(db.Model):
    """
    Log of user confirmations/changes to entity-ontology matches.

    Records when users confirm LLM-suggested matches or manually
    change matches, providing training data for future improvements.
    """

    __tablename__ = 'entity_match_confirmations'

    id = db.Column(db.Integer, primary_key=True)

    # Context
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False, index=True)
    entity_id = db.Column(db.Integer, db.ForeignKey('temporary_rdf_storage.id'), nullable=False)

    # Entity information at time of confirmation
    entity_label = db.Column(db.String(255))
    entity_type = db.Column(db.String(100))

    # Original match state (before user action)
    original_match_uri = db.Column(db.String(500))
    original_match_label = db.Column(db.String(255))
    original_confidence = db.Column(db.Float)
    original_method = db.Column(db.String(50))

    # User action
    action = db.Column(db.String(50), nullable=False)  # 'confirmed', 'changed', 'marked_new'

    # New match state (after user action, if changed)
    new_match_uri = db.Column(db.String(500))
    new_match_label = db.Column(db.String(255))

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Relationships
    case = db.relationship('Document', backref=db.backref('match_confirmations', lazy='dynamic'))
    entity = db.relationship('TemporaryRDFStorage', backref=db.backref('confirmations', lazy='dynamic'))

    def __repr__(self):
        return f'<EntityMatchConfirmation {self.id}: {self.action} on {self.entity_label}>'

    def to_dict(self):
        return {
            'id': self.id,
            'case_id': self.case_id,
            'entity_id': self.entity_id,
            'entity_label': self.entity_label,
            'entity_type': self.entity_type,
            'original_match_uri': self.original_match_uri,
            'original_match_label': self.original_match_label,
            'original_confidence': self.original_confidence,
            'original_method': self.original_method,
            'action': self.action,
            'new_match_uri': self.new_match_uri,
            'new_match_label': self.new_match_label,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_id': self.user_id
        }
