"""
Temporary storage for extracted guideline concepts during the review and manipulation workflow.
This allows concepts to persist between page loads and be manipulated before final commitment.
"""

from datetime import datetime, timedelta
from app.models import db
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import Index


class TemporaryConcept(db.Model):
    """
    Temporary storage for extracted concepts from guidelines.
    
    This table stores concepts after extraction but before they are committed
    to the ontology. It allows for manipulation, review, and editing of concepts
    during the extraction workflow without losing data between page loads.
    """
    __tablename__ = 'temporary_concepts'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Links to the source guideline document
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=False)
    
    # Session identifier for grouping concepts from same extraction session
    session_id = db.Column(db.String(100), nullable=False)
    
    # The concept data
    concept_data = db.Column(JSONB, nullable=False)
    # Expected structure:
    # {
    #     "label": "Concept Name",
    #     "type": "principle|obligation|role|state|resource|action|event|capability|constraint",
    #     "description": "Concept description",
    #     "source_text": "Original text this was extracted from",
    #     "confidence": 0.85,
    #     "is_new": true,
    #     "ontology_match": {...},  # If matched to existing ontology entity
    #     "selected": true,  # Whether user has selected this for inclusion
    #     "edited": false,  # Whether user has edited this concept
    #     "original_data": {...}  # Original extraction before any edits
    # }
    
    # Status tracking
    status = db.Column(db.String(50), default='pending')  # pending, reviewed, committed, discarded
    
    # Metadata
    extraction_method = db.Column(db.String(50))  # 'llm', 'manual', 'hybrid'
    extraction_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    last_modified = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime)  # Auto-cleanup after this time
    
    # User tracking (if needed)
    created_by = db.Column(db.String(100))  # Could be user ID or session ID
    modified_by = db.Column(db.String(100))
    
    # Additional metadata (renamed to avoid conflict with SQLAlchemy's reserved 'metadata' attribute)
    extra_metadata = db.Column('metadata', JSONB, default={})
    # Can store:
    # - llm_model_used
    # - extraction_parameters
    # - parent_concept_ids (for hierarchical relationships)
    # - tags
    # - notes
    
    # Relationships
    document = db.relationship('Document', backref='temporary_concepts')
    world = db.relationship('World', backref='temporary_concepts')
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_temp_concepts_session', 'session_id'),
        Index('idx_temp_concepts_document', 'document_id'),
        Index('idx_temp_concepts_world', 'world_id'),
        Index('idx_temp_concepts_status', 'status'),
        Index('idx_temp_concepts_expires', 'expires_at'),
    )
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set default expiration to 7 days if not specified
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=7)
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'world_id': self.world_id,
            'session_id': self.session_id,
            'concept_data': self.concept_data,
            'status': self.status,
            'extraction_method': self.extraction_method,
            'extraction_timestamp': self.extraction_timestamp.isoformat() if self.extraction_timestamp else None,
            'last_modified': self.last_modified.isoformat() if self.last_modified else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_by': self.created_by,
            'modified_by': self.modified_by,
            'metadata': self.extra_metadata
        }
    
    @classmethod
    def cleanup_expired(cls):
        """Remove expired temporary concepts."""
        expired = cls.query.filter(
            cls.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
        return expired
    
    @classmethod
    def get_session_concepts(cls, session_id, status=None):
        """Get all concepts for a given session."""
        query = cls.query.filter_by(session_id=session_id)
        if status:
            query = query.filter_by(status=status)
        return query.order_by(cls.id).all()
    
    @classmethod
    def get_document_concepts(cls, document_id, status='pending'):
        """Get all pending concepts for a document."""
        return cls.query.filter_by(
            document_id=document_id,
            status=status
        ).order_by(cls.extraction_timestamp.desc()).all()
    
    def mark_reviewed(self):
        """Mark concept as reviewed."""
        self.status = 'reviewed'
        self.last_modified = datetime.utcnow()
        db.session.commit()
    
    def mark_committed(self):
        """Mark concept as committed to ontology."""
        self.status = 'committed'
        self.last_modified = datetime.utcnow()
        db.session.commit()
    
    def mark_discarded(self):
        """Mark concept as discarded."""
        self.status = 'discarded'
        self.last_modified = datetime.utcnow()
        db.session.commit()
    
    def update_concept_data(self, new_data):
        """Update the concept data, preserving original if not already saved."""
        if not self.concept_data.get('original_data'):
            # Save original data before first edit
            self.concept_data['original_data'] = dict(self.concept_data)
        
        self.concept_data.update(new_data)
        self.concept_data['edited'] = True
        self.last_modified = datetime.utcnow()
        db.session.commit()
    
    def __repr__(self):
        return f'<TemporaryConcept {self.id}: {self.concept_data.get("label", "Unknown")} ({self.status})>'