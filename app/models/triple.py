from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.models import db
from sqlalchemy import func
import datetime

class Triple(db.Model):
    """
    RDF Triple model for storing character data as Subject-Predicate-Object.
    This allows for flexible storage of character attributes and relationships
    aligned with ontology definitions.
    """
    __tablename__ = 'character_triples'
    
    id = db.Column(Integer, primary_key=True)
    subject = db.Column(String(255), nullable=False, index=True)  # Character URI
    predicate = db.Column(String(255), nullable=False, index=True)  # Property URI
    object_literal = db.Column(Text)  # Value as string when is_literal=True
    object_uri = db.Column(String(255))  # Value as URI when is_literal=False
    is_literal = db.Column(Boolean, nullable=False)  # Whether object is a literal or URI
    graph = db.Column(String(255), index=True)  # Named graph (e.g., scenario ID)
    
    # Vector embeddings for semantic similarity searches - stored as ARRAY initially
    # These will be cast to vector type by the setup script
    subject_embedding = db.Column(ARRAY(db.Float), nullable=True)
    predicate_embedding = db.Column(ARRAY(db.Float), nullable=True)
    object_embedding = db.Column(ARRAY(db.Float), nullable=True)
    
    # Additional metadata for the triple (renamed to avoid SQLAlchemy reserved name)
    triple_metadata = db.Column(JSONB, default=dict)
    created_at = db.Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Optional foreign keys for direct references to application entities
    character_id = db.Column(Integer, db.ForeignKey('characters.id', ondelete='CASCADE'), nullable=True)
    scenario_id = db.Column(Integer, db.ForeignKey('scenarios.id', ondelete='CASCADE'), nullable=True)
    
    def __repr__(self):
        return f'<Triple {self.subject} {self.predicate} {self.object_literal or self.object_uri}>'
    
    @property
    def object(self):
        """Return the object value, which could be either a literal or URI."""
        return self.object_literal if self.is_literal else self.object_uri
    
    def to_dict(self):
        """Convert triple to dictionary."""
        return {
            'id': self.id,
            'subject': self.subject,
            'predicate': self.predicate,
            'object': self.object_literal if self.is_literal else self.object_uri,
            'is_literal': self.is_literal,
            'graph': self.graph,
            'metadata': self.triple_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'character_id': self.character_id,
            'scenario_id': self.scenario_id
        }
    
    def to_rdf_tuple(self):
        """Convert to a simple (subject, predicate, object) tuple."""
        obj = self.object_literal if self.is_literal else self.object_uri
        return (self.subject, self.predicate, obj)
