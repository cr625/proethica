"""
Base document model (includes guidelines, case studies, and other document types)
"""

from datetime import datetime
from app import db
import os
import re
from sqlalchemy.dialects.postgresql import JSON

# Processing status constants
PROCESSING_STATUS = {
    'PENDING': 'pending',
    'PROCESSING': 'processing',
    'COMPLETED': 'completed',
    'FAILED': 'failed'
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
    
    # Define relationship to world
    world = db.relationship('World', backref='documents')
    
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
    
    def __repr__(self):
        return f"<Document {self.id}: {self.title} ({self.document_type})>"
