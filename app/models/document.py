"""
Base document model (includes guidelines, case studies, and other document types)
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from app.models import db
import os
import re
from sqlalchemy.dialects.postgresql import JSON
from app.models.pgvector import Vector

# Processing status constants
PROCESSING_STATUS = {
    'PENDING': 'pending',
    'PROCESSING': 'processing',
    'COMPLETED': 'completed',
    'FAILED': 'failed'
}

# Processing phases constants
PROCESSING_PHASES = {
    'INITIALIZING': 'initializing',
    'EXTRACTING': 'extracting',
    'CHUNKING': 'chunking',
    'EMBEDDING': 'embedding',
    'STORING': 'storing',
    'FINALIZING': 'finalizing'
}

class Document(db.Model):
    """
    Document model for various document types including guidelines and case studies.
    """
    __tablename__ = 'documents'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    document_type = db.Column(db.String(50), nullable=False)  # e.g., 'guideline', 'case_study'
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=False)
    content = db.Column(db.Text, nullable=True)  # Text content if available
    source = db.Column(db.String(1024), nullable=True)  # URL or reference to source
    file_path = db.Column(db.String(1024), nullable=True)  # Local file path if uploaded
    file_type = db.Column(db.String(10), nullable=True)  # e.g., 'pdf', 'docx', 'txt'
    processing_status = db.Column(db.String(20), default=PROCESSING_STATUS['PENDING'])
    doc_metadata = db.Column(JSON, nullable=True)  # Additional metadata for processing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # User ownership and data classification
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    data_type = db.Column(db.String(20), default='user')  # 'system' or 'user'
    
    # Define relationships
    world = db.relationship('World', backref='documents')
    creator = db.relationship('User', backref='created_documents')

    # Aliases for domain terminology (world == domain in ProEthica context)
    @property
    def domain_id(self):
        """Alias for world_id - domain and world are synonymous."""
        return self.world_id

    @property
    def domain(self):
        """Alias for world relationship - domain and world are synonymous."""
        return self.world

    @property
    def case_number(self):
        """Extract case number from metadata or title."""
        # Check metadata first
        if self.doc_metadata and isinstance(self.doc_metadata, dict):
            if 'case_number' in self.doc_metadata:
                return self.doc_metadata['case_number']

        # Try to extract from title (e.g., "BER Case 57-8")
        if self.title:
            import re
            match = re.search(r'(?:Case|BER)\s*(\d+[-\d]*)', self.title, re.IGNORECASE)
            if match:
                return match.group(1)

        return None
    
    def get_content(self):
        """Get document content from file if not already loaded"""
        if self.content:
            return self.content
        
        if self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    self.content = f.read()
                return self.content
            except Exception as e:
                print(f"Error reading file {self.file_path}: {str(e)}")
                return f"Error reading file: {str(e)}"
        
        return None
    
    def get_content_excerpt(self, max_length=200):
        """Get a short excerpt of the document content for display"""
        content = self.content
        
        if not content and self.file_path and os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception:
                return "Error reading file content"
        
        if not content:
            return "No content available"
        
        # Remove markdown formatting
        clean_content = re.sub(r'#+ ', '', content)  # Remove headers
        clean_content = re.sub(r'\*\*|__', '', clean_content)  # Remove bold
        clean_content = re.sub(r'\*|_', '', clean_content)  # Remove italics
        clean_content = re.sub(r'```[\s\S]*?```', '', clean_content)  # Remove code blocks
        clean_content = re.sub(r'`.*?`', '', clean_content)  # Remove inline code
        clean_content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_content)  # Replace links with just text
        
        # Get excerpt
        if len(clean_content) > max_length:
            excerpt = clean_content[:max_length].strip() + "..."
        else:
            excerpt = clean_content.strip()
        
        return excerpt
    
    def can_edit(self, user):
        """Check if the user can edit this document."""
        if not user or not user.is_authenticated:
            return False
        
        # Admin can edit everything
        if getattr(user, 'is_admin', False):
            return True
        
        # System data can only be edited by admins
        if self.data_type == 'system':
            return False
        
        # User can edit their own content
        return self.created_by == user.id
    
    def can_delete(self, user):
        """Check if the user can delete this document."""
        # Same rules as editing
        return self.can_edit(user)
    
    def can_view(self, user):
        """Check if the user can view this document."""
        # All users can view all documents (read-only for system data)
        return True
    
    def is_system_data(self):
        """Check if this is system data (read-only for non-admins)."""
        return self.data_type == 'system'
    
    def is_user_data(self):
        """Check if this is user-created data."""
        return self.data_type == 'user'
    
    def __repr__(self):
        return f"<Document {self.id}: {self.title} ({self.document_type})>"


class DocumentChunk(db.Model):
    """
    Document chunk model for storing and retrieving document chunks (for vector search and embeddings)
    """
    __tablename__ = 'document_chunks'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    content = db.Column(db.Text, nullable=False)
    # Use pgvector for better similarity search performance (existing data uses 1536-dim)
    embedding = db.Column(Vector(1536), nullable=True)
    # New: local 384-dim embedding column to support fast pgvector search without hosted APIs
    embedding_384 = db.Column(Vector(384), nullable=True)
    chunk_metadata = db.Column(JSON, nullable=True)  # Renamed from metadata which is reserved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Define relationship to document
    document = db.relationship('Document', backref='chunks')
    
    def __repr__(self):
        return f"<DocumentChunk {self.id}: {self.document_id}:{self.chunk_index}>"
