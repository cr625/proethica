"""
Model for pending concept types awaiting review.
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB
from app.models import db


class PendingConceptType(db.Model):
    """Model for concept types suggested by LLM that await human review."""
    
    __tablename__ = 'pending_concept_types'
    
    id = db.Column(db.Integer, primary_key=True)
    suggested_type = db.Column(db.String(255), nullable=False)
    suggested_description = db.Column(db.Text)
    suggested_parent_type = db.Column(db.String(255))
    source_guideline_id = db.Column(db.Integer, db.ForeignKey('guidelines.id', ondelete='CASCADE'))
    example_concepts = db.Column(JSONB, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default='pending')  # pending, approved, rejected
    reviewer_notes = db.Column(db.Text)
    approved_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    approved_at = db.Column(db.DateTime)
    
    # Relationships
    source_guideline = db.relationship('Guideline', backref='pending_types')
    approver = db.relationship('User', backref='approved_types')
    
    # Constraints
    __table_args__ = (
        db.UniqueConstraint('suggested_type', 'source_guideline_id', name='unique_pending_type'),
        db.CheckConstraint(status.in_(['pending', 'approved', 'rejected']), name='valid_status'),
    )
    
    def __repr__(self):
        return f'<PendingConceptType {self.id}: {self.suggested_type} ({self.status})>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'suggested_type': self.suggested_type,
            'suggested_description': self.suggested_description,
            'suggested_parent_type': self.suggested_parent_type,
            'source_guideline_id': self.source_guideline_id,
            'example_concepts': self.example_concepts,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'status': self.status,
            'reviewer_notes': self.reviewer_notes,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
        }
    
    def approve(self, user_id, notes=None):
        """Approve this pending type."""
        self.status = 'approved'
        self.approved_by = user_id
        self.approved_at = datetime.utcnow()
        if notes:
            self.reviewer_notes = notes
    
    def reject(self, user_id, notes=None):
        """Reject this pending type."""
        self.status = 'rejected'
        self.approved_by = user_id
        self.approved_at = datetime.utcnow()
        if notes:
            self.reviewer_notes = notes
    
    @classmethod
    def get_pending_for_review(cls):
        """Get all pending types that need review."""
        return cls.query.filter_by(status='pending').order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_for_guideline(cls, guideline_id):
        """Get all pending types for a specific guideline."""
        return cls.query.filter_by(source_guideline_id=guideline_id).all()
    
    @property
    def is_pending(self):
        """Check if this type is still pending review."""
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        """Check if this type has been approved."""
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        """Check if this type has been rejected."""
        return self.status == 'rejected'