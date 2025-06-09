"""
Model for section term links - individual words/phrases linked to ontology terms.
"""
from datetime import datetime
from app import db

class SectionTermLink(db.Model):
    """
    Model for storing links between individual terms in document sections and ontology concepts.
    
    This stores word-level mappings where specific words or phrases in section text
    are linked to corresponding terms in the engineering-ethics ontology.
    """
    __tablename__ = 'section_term_links'
    
    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    section_id = db.Column(db.String(100), nullable=False)  # e.g., 'facts', 'discussion', 'conclusion'
    term_text = db.Column(db.String(500), nullable=False)  # The actual word/phrase found
    term_start = db.Column(db.Integer, nullable=False)  # Character position start
    term_end = db.Column(db.Integer, nullable=False)  # Character position end
    ontology_uri = db.Column(db.String(500), nullable=False)  # URI of ontology concept
    ontology_label = db.Column(db.String(500))  # Human-readable label
    definition = db.Column(db.Text)  # Definition from ontology
    entity_type = db.Column(db.String(100))  # Type of ontology entity (e.g., 'role', 'principle', etc.)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    document = db.relationship('Document', backref=db.backref('term_links', lazy='dynamic', cascade='all, delete-orphan'))
    
    # Unique constraint to prevent duplicates
    __table_args__ = (
        db.UniqueConstraint('document_id', 'section_id', 'term_start', 'term_end', 'ontology_uri', 
                          name='section_term_links_unique'),
        db.Index('idx_section_term_links_document_id', 'document_id'),
        db.Index('idx_section_term_links_section_id', 'document_id', 'section_id'),
        db.Index('idx_section_term_links_ontology_uri', 'ontology_uri'),
    )
    
    def __repr__(self):
        return f'<SectionTermLink {self.document_id}:{self.section_id} "{self.term_text}" -> {self.ontology_uri}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'document_id': self.document_id,
            'section_id': self.section_id,
            'term_text': self.term_text,
            'term_start': self.term_start,
            'term_end': self.term_end,
            'ontology_uri': self.ontology_uri,
            'ontology_label': self.ontology_label,
            'definition': self.definition,
            'entity_type': self.entity_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def get_document_term_links(cls, document_id):
        """Get all term links for a document, grouped by section."""
        term_links = cls.query.filter_by(document_id=document_id).order_by(cls.section_id, cls.term_start).all()
        
        # Group by section
        sections = {}
        for link in term_links:
            if link.section_id not in sections:
                sections[link.section_id] = []
            sections[link.section_id].append(link.to_dict())
        
        return sections
    
    @classmethod
    def get_section_term_links(cls, document_id, section_id):
        """Get all term links for a specific section."""
        return cls.query.filter_by(
            document_id=document_id,
            section_id=section_id
        ).order_by(cls.term_start).all()
    
    @classmethod
    def delete_document_term_links(cls, document_id):
        """Delete all term links for a document."""
        cls.query.filter_by(document_id=document_id).delete()
        db.session.commit()
    
    @classmethod
    def delete_section_term_links(cls, document_id, section_id):
        """Delete all term links for a specific section."""
        cls.query.filter_by(document_id=document_id, section_id=section_id).delete()
        db.session.commit()