from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import relationship
from app.models import db
from sqlalchemy import func
import datetime
from sqlalchemy.ext.hybrid import hybrid_property

class EntityTriple(db.Model):
    """
    RDF Triple model for storing entity data as Subject-Predicate-Object.
    This allows for flexible storage of all entity types, including characters,
    actions, events, resources in a unified graph structure.
    """
    __tablename__ = 'entity_triples'
    
    id = db.Column(Integer, primary_key=True)
    subject = db.Column(String(255), nullable=False, index=True)  # Entity URI
    predicate = db.Column(String(255), nullable=False, index=True)  # Property URI
    object_literal = db.Column(Text)  # Value as string when is_literal=True
    object_uri = db.Column(String(255))  # Value as URI when is_literal=False
    is_literal = db.Column(Boolean, nullable=False)  # Whether object is a literal or URI
    graph = db.Column(String(255), index=True)  # Named graph (e.g., scenario ID)
    
    # Additional fields for label display
    subject_label = db.Column(String(255))  # Human readable label for subject
    predicate_label = db.Column(String(255))  # Human readable label for predicate
    object_label = db.Column(String(255))  # Human readable label for object
    
    # Vector embeddings for semantic similarity searches
    subject_embedding = db.Column(ARRAY(db.Float), nullable=True)
    predicate_embedding = db.Column(ARRAY(db.Float), nullable=True)
    object_embedding = db.Column(ARRAY(db.Float), nullable=True)
    
    # Additional metadata for the triple
    triple_metadata = db.Column(JSONB, default=dict)
    created_at = db.Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # BFO-based temporal fields
    temporal_region_type = db.Column(String(255), nullable=True)  # BFO_0000038 (1D) or BFO_0000148 (0D)
    temporal_start = db.Column(DateTime, nullable=True, index=True)  # Start time for intervals, time point for instants
    temporal_end = db.Column(DateTime, nullable=True, index=True)  # End time for intervals, None for instants
    temporal_relation_type = db.Column(String(50), nullable=True)  # precedes, follows, etc.
    temporal_relation_to = db.Column(Integer, db.ForeignKey('entity_triples.id'), nullable=True)  # Related triple
    temporal_granularity = db.Column(String(50), nullable=True)  # seconds, minutes, days, etc.
    
    # Enhanced temporal fields
    temporal_confidence = db.Column(db.Float, default=1.0)  # Confidence level in temporal information
    temporal_context = db.Column(JSONB, default=dict)  # Additional context about the temporal situation
    timeline_order = db.Column(Integer, nullable=True)  # Explicit ordering for timeline items
    timeline_group = db.Column(String(255), nullable=True)  # For grouping related temporal items
    
    # Polymorphic entity reference
    entity_type = db.Column(String(50), nullable=False)  # 'character', 'action', 'event', 'resource'
    entity_id = db.Column(Integer, nullable=False)
    
    # Foreign keys
    world_id = db.Column(Integer, db.ForeignKey('worlds.id', ondelete='CASCADE'), nullable=True)
    scenario_id = db.Column(Integer, db.ForeignKey('scenarios.id', ondelete='CASCADE'), nullable=True)
    character_id = db.Column(Integer, db.ForeignKey('characters.id', ondelete='CASCADE'), nullable=True)
    guideline_id = db.Column(Integer, db.ForeignKey('guidelines.id', ondelete='CASCADE'), nullable=True)
    
    # Relationships
    world = relationship("World", back_populates="entity_triples", foreign_keys=[world_id])
    scenario = relationship("Scenario", back_populates="entity_triples", foreign_keys=[scenario_id])
    character = relationship("Character", back_populates="entity_triples", foreign_keys=[character_id])
    guideline = relationship("Guideline", back_populates="entity_triples", foreign_keys=[guideline_id])
    
    def __repr__(self):
        return f'<EntityTriple {self.subject} {self.predicate} {self.object_literal or self.object_uri}>'
    
    @hybrid_property
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
            'subject_label': self.subject_label,
            'predicate_label': self.predicate_label,
            'object_label': self.object_label,
            'entity_type': self.entity_type,
            'entity_id': self.entity_id,
            'metadata': self.triple_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'world_id': self.world_id,
            'scenario_id': self.scenario_id,
            'character_id': self.character_id,
            'guideline_id': self.guideline_id,
            # Temporal fields
            'temporal_region_type': self.temporal_region_type,
            'temporal_start': self.temporal_start.isoformat() if self.temporal_start else None,
            'temporal_end': self.temporal_end.isoformat() if self.temporal_end else None,
            'temporal_relation_type': self.temporal_relation_type,
            'temporal_relation_to': self.temporal_relation_to,
            'temporal_granularity': self.temporal_granularity,
            # Enhanced temporal fields
            'temporal_confidence': self.temporal_confidence,
            'temporal_context': self.temporal_context,
            'timeline_order': self.timeline_order,
            'timeline_group': self.timeline_group
        }
    
    def to_rdf_tuple(self):
        """Convert to a simple (subject, predicate, object) tuple."""
        obj = self.object_literal if self.is_literal else self.object_uri
        return (self.subject, self.predicate, obj)
