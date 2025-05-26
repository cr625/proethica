"""
Model for guideline semantic triples - relationships between concepts extracted from guidelines.
"""

from datetime import datetime
from app import db


class GuidelineSemanticTriple(db.Model):
    """
    Represents semantic relationships (triples) between concepts extracted from guidelines.
    These can be explicit relationships found in text or inferred relationships.
    """
    __tablename__ = 'guideline_semantic_triples'
    
    id = db.Column(db.Integer, primary_key=True)
    guideline_id = db.Column(db.Integer, db.ForeignKey('guidelines.id', ondelete='CASCADE'))
    subject_uri = db.Column(db.String(255), nullable=False)
    predicate = db.Column(db.String(255), nullable=False)
    object_uri = db.Column(db.String(255), nullable=False)
    confidence = db.Column(db.Float, default=1.0)
    inference_type = db.Column(db.String(50))  # explicit, pattern, llm
    explanation = db.Column(db.Text)
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    guideline = db.relationship('Guideline', backref='semantic_triples')
    
    def to_dict(self):
        """Convert to dictionary representation."""
        return {
            'id': self.id,
            'guideline_id': self.guideline_id,
            'subject_uri': self.subject_uri,
            'predicate': self.predicate,
            'object_uri': self.object_uri,
            'confidence': self.confidence,
            'inference_type': self.inference_type,
            'explanation': self.explanation,
            'is_approved': self.is_approved,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_rdf_dict(self):
        """Convert to RDF-style dictionary."""
        return {
            'subject': self.subject_uri,
            'predicate': self.predicate,
            'object': self.object_uri,
            'metadata': {
                'confidence': self.confidence,
                'inference_type': self.inference_type,
                'explanation': self.explanation
            }
        }
    
    def to_turtle(self):
        """Convert to Turtle format string."""
        # Handle literal objects (quoted strings)
        if self.object_uri.startswith('"'):
            object_str = self.object_uri
        else:
            object_str = f"<{self.object_uri}>"
            
        return f"<{self.subject_uri}> <{self.predicate}> {object_str} ."
    
    @classmethod
    def get_by_guideline(cls, guideline_id: int, approved_only: bool = False):
        """Get all semantic triples for a guideline."""
        query = cls.query.filter_by(guideline_id=guideline_id)
        if approved_only:
            query = query.filter_by(is_approved=True)
        return query.order_by(cls.confidence.desc()).all()
    
    @classmethod
    def get_by_subject(cls, subject_uri: str):
        """Get all triples with a specific subject."""
        return cls.query.filter_by(subject_uri=subject_uri).all()
    
    @classmethod
    def get_by_predicate(cls, predicate: str):
        """Get all triples with a specific predicate."""
        return cls.query.filter_by(predicate=predicate).all()
    
    @classmethod
    def get_relationships_between(cls, uri1: str, uri2: str):
        """Get all relationships between two URIs (in either direction)."""
        return cls.query.filter(
            db.or_(
                db.and_(cls.subject_uri == uri1, cls.object_uri == uri2),
                db.and_(cls.subject_uri == uri2, cls.object_uri == uri1)
            )
        ).all()