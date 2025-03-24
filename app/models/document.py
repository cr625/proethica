from app import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB

# Import Vector type from pgvector
from pgvector.sqlalchemy import Vector
VECTOR_AVAILABLE = True

class Document(db.Model):
    """
    A Document represents a file uploaded to the system, such as guidelines,
    case studies, or academic papers. Documents are associated with worlds
    and are processed for vector embeddings.
    """
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.Text, nullable=False)
    source = db.Column(db.Text)
    document_type = db.Column(db.Text, nullable=False)  # 'guideline', 'case_study', 'academic_paper', etc.
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id', ondelete='CASCADE'))
    file_path = db.Column(db.Text)
    file_type = db.Column(db.Text)
    content = db.Column(db.Text)
    doc_metadata = db.Column(JSONB)  # Renamed from metadata to avoid conflict with SQLAlchemy
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship with world
    world = db.relationship('World', backref=db.backref('documents', lazy=True, cascade='all, delete-orphan'))
    
    # Relationship with chunks
    chunks = db.relationship('DocumentChunk', backref='document', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Document {self.title}>'
    
    def to_dict(self):
        """Convert the document to a dictionary."""
        return {
            'id': self.id,
            'title': self.title,
            'source': self.source,
            'document_type': self.document_type,
            'world_id': self.world_id,
            'file_path': self.file_path,
            'file_type': self.file_type,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'metadata': self.doc_metadata
        }

class DocumentChunk(db.Model):
    """
    A DocumentChunk represents a portion of a document with its vector embedding.
    Documents are split into chunks for more effective retrieval using vector similarity.
    """
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'))
    chunk_index = db.Column(db.Integer, nullable=False)
    chunk_text = db.Column(db.Text, nullable=False)
    # Use Vector type for embedding
    embedding = db.Column(Vector(384))  # 384 is the dimension of the all-MiniLM-L6-v2 model
    chunk_metadata = db.Column(JSONB)  # Renamed from metadata to avoid conflict with SQLAlchemy
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DocumentChunk {self.id} of Document {self.document_id}>'
    
    def to_dict(self):
        """Convert the document chunk to a dictionary."""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'chunk_index': self.chunk_index,
            'chunk_text': self.chunk_text,
            'metadata': self.chunk_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
