"""
Document section model for storing and retrieving document sections with vector embeddings.
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app.models import db
from sqlalchemy.dialects.postgresql import JSON, ARRAY
from sqlalchemy import Index, UniqueConstraint
from sqlalchemy import text
from sqlalchemy.types import TypeDecorator, UserDefinedType
from app.models.pgvector import Vector

class DocumentSection(db.Model):
    """
    Document section model for storing document structure with section-level embeddings.
    Uses pgvector for efficient similarity searches between sections.
    """
    __tablename__ = 'document_sections'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    section_id = db.Column(db.String(255), nullable=False)  # e.g., 'facts', 'discussion', 'question_1'
    section_type = db.Column(db.String(50), nullable=False)  # e.g., 'facts', 'discussion', 'question'
    position = db.Column(db.Integer, nullable=True)  # For ordering sections
    content = db.Column(db.Text, nullable=False)
    embedding = db.Column(Vector(384), nullable=True)  # Use our custom Vector type for pgvector compatibility
    section_metadata = db.Column(JSON, nullable=True)  # Additional metadata for the section
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationship to document
    document = db.relationship('Document', backref=db.backref('document_sections', cascade='all, delete-orphan'))
    
    # Add unique constraint for document_id + section_id
    __table_args__ = (
        UniqueConstraint('document_id', 'section_id', name='document_section_unique'),
    )
    
    def __repr__(self):
        return f"<DocumentSection {self.id}: {self.document_id}:{self.section_id} ({self.section_type})>"
