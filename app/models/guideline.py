"""
Guideline model for ethical guidelines associated with worlds.
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.models import db
from app.models.entity_triple import EntityTriple

class Guideline(db.Model):
    """Guideline model representing ethical guidelines documents and their metadata."""
    
    __tablename__ = 'guidelines'
    
    id = db.Column(db.Integer, primary_key=True)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    source_url = db.Column(db.String(1024))
    file_path = db.Column(db.String(1024))
    file_type = db.Column(db.String(50))
    embedding = db.Column(ARRAY(db.Float))
    guideline_metadata = db.Column(JSONB, default={})
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    world = db.relationship('World', back_populates='guidelines')
    entity_triples = db.relationship('EntityTriple', 
                                   primaryjoin="and_(EntityTriple.entity_type=='guideline_concept', "
                                               "EntityTriple.guideline_id==Guideline.id)",
                                   back_populates='guideline',
                                   lazy='dynamic',
                                   cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Guideline {self.id}: {self.title}>'
    
    def get_content_excerpt(self, length=300):
        """Get a short excerpt of the content for display purposes."""
        if not self.content:
            return "(No content available)"
        
        if len(self.content) <= length:
            return self.content
        
        # Find the last space before the cutoff to avoid cutting words
        last_space = self.content[:length].rfind(' ')
        if last_space == -1:  # No space found
            return self.content[:length] + '...'
        
        return self.content[:last_space] + '...'
    
    def to_dict(self):
        """Convert guideline to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'world_id': self.world_id,
            'title': self.title,
            'content_excerpt': self.get_content_excerpt(200),
            'source_url': self.source_url,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'metadata': self.guideline_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'triple_count': self.entity_triples.count()
        }
    
    @property
    def concepts(self):
        """Get the concepts (subject entities) associated with this guideline."""
        # Group by subject to get unique concepts
        return db.session.query(
            EntityTriple.subject, 
            EntityTriple.subject_label,
            db.func.string_agg(EntityTriple.predicate_label, ', ').label('predicates'),
            # Get a concept description if available
            db.func.max(db.case([
                (EntityTriple.predicate == 'http://purl.org/dc/elements/1.1/description', EntityTriple.object_literal)
            ], else_=None)).label('description'),
            # Get concept type if available
            db.func.max(db.case([
                (EntityTriple.predicate == 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type', EntityTriple.object_label)
            ], else_=None)).label('type_label')
        ).filter(
            EntityTriple.guideline_id == self.id,
            EntityTriple.entity_type == 'guideline_concept'
        ).group_by(
            EntityTriple.subject,
            EntityTriple.subject_label
        ).all()
