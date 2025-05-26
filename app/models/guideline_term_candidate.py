"""
Model for guideline term candidates - concepts that may become new ontology terms.
"""

from datetime import datetime
from app import db


class GuidelineTermCandidate(db.Model):
    """
    Represents a concept extracted from guidelines that is a candidate for becoming
    a new term in the ontology.
    """
    __tablename__ = 'guideline_term_candidates'
    
    id = db.Column(db.Integer, primary_key=True)
    guideline_id = db.Column(db.Integer, db.ForeignKey('guidelines.id', ondelete='CASCADE'))
    term_label = db.Column(db.String(255), nullable=False)
    term_uri = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # role, principle, obligation, etc.
    parent_class_uri = db.Column(db.String(255))
    definition = db.Column(db.Text)
    confidence = db.Column(db.Float)
    is_existing = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    
    # Relationships
    guideline = db.relationship('Guideline', backref='term_candidates')
    reviewer = db.relationship('User', backref='reviewed_terms')
    
    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'guideline_id': self.guideline_id,
            'term_label': self.term_label,
            'term_uri': self.term_uri,
            'category': self.category,
            'parent_class_uri': self.parent_class_uri,
            'definition': self.definition,
            'confidence': self.confidence,
            'is_existing': self.is_existing,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes
        }
    
    def approve(self, user_id: int, notes: str = None):
        """Approve this term candidate."""
        self.status = 'approved'
        self.reviewed_by = user_id
        self.review_notes = notes
        self.updated_at = datetime.utcnow()
        
    def reject(self, user_id: int, notes: str = None):
        """Reject this term candidate."""
        self.status = 'rejected'
        self.reviewed_by = user_id
        self.review_notes = notes
        self.updated_at = datetime.utcnow()
        
    @classmethod
    def get_pending_by_guideline(cls, guideline_id: int):
        """Get all pending term candidates for a guideline."""
        return cls.query.filter_by(
            guideline_id=guideline_id,
            status='pending'
        ).order_by(cls.confidence.desc()).all()
    
    @classmethod
    def get_by_category(cls, category: str, status: str = None):
        """Get term candidates by category and optional status."""
        query = cls.query.filter_by(category=category)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.created_at.desc()).all()