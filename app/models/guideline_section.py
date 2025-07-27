"""
GuidelineSection model for structured ethical guideline sections.
Represents individual sections (like I.1, II.1.c, III.3) extracted from guidelines documents.
"""

from datetime import datetime
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from app.models import db

class GuidelineSection(db.Model):
    """
    Individual section of an ethical guideline document.
    
    This model stores structured sections extracted from guidelines documents,
    allowing for precise referencing (e.g., [I.1], [II.1.c]) and interactive
    tooltips in case analysis.
    """
    
    __tablename__ = 'guideline_sections'
    
    id = db.Column(db.Integer, primary_key=True)
    guideline_id = db.Column(db.Integer, db.ForeignKey('guidelines.id', ondelete='CASCADE'), nullable=False)
    
    # Section identification
    section_code = db.Column(db.String(20), nullable=False, index=True)  # e.g., "I.1", "II.1.c", "III.3"
    section_title = db.Column(db.String(500))  # e.g., "Fundamental Canon I.1"
    section_text = db.Column(db.Text, nullable=False)  # Full text content
    
    # Classification and organization
    section_category = db.Column(db.String(100))  # e.g., "fundamental_canons", "rules_of_practice"
    section_subcategory = db.Column(db.String(100))  # e.g., "safety_health_welfare", "competence"
    section_order = db.Column(db.Integer)  # Order within the document
    parent_section_code = db.Column(db.String(20))  # For hierarchical sections (e.g., II.1.c -> II.1)
    
    # Content processing
    embedding = db.Column(ARRAY(db.Float))  # Vector embedding for semantic search
    section_metadata = db.Column(JSONB, default={})  # Additional metadata
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    guideline = db.relationship('Guideline', back_populates='sections')
    
    # Indexes for fast lookups
    __table_args__ = (
        db.Index('ix_guideline_sections_code_lookup', 'section_code', 'guideline_id'),
        db.Index('ix_guideline_sections_category', 'section_category'),
    )
    
    def __repr__(self):
        return f'<GuidelineSection {self.section_code}: {self.section_title}>'
    
    def get_display_title(self):
        """Get formatted title for display purposes."""
        if self.section_title:
            return self.section_title
        elif self.section_category:
            return f"{self.section_category.replace('_', ' ').title()} {self.section_code}"
        else:
            return f"Section {self.section_code}"
    
    def get_tooltip_data(self):
        """Get data structure for interactive tooltips."""
        return {
            'code': self.section_code,
            'title': self.get_display_title(),
            'text': self.section_text,
            'category': self.section_category,
            'subcategory': self.section_subcategory
        }
    
    def get_parent_section(self):
        """Get the parent section if this is a subsection."""
        if not self.parent_section_code:
            return None
        
        return GuidelineSection.query.filter_by(
            guideline_id=self.guideline_id,
            section_code=self.parent_section_code
        ).first()
    
    def get_child_sections(self):
        """Get child sections of this section."""
        return GuidelineSection.query.filter_by(
            guideline_id=self.guideline_id,
            parent_section_code=self.section_code
        ).order_by(GuidelineSection.section_order).all()
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'guideline_id': self.guideline_id,
            'section_code': self.section_code,
            'section_title': self.section_title,
            'section_text': self.section_text,
            'section_category': self.section_category,
            'section_subcategory': self.section_subcategory,
            'section_order': self.section_order,
            'parent_section_code': self.parent_section_code,
            'display_title': self.get_display_title(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def find_by_code(cls, section_code: str, guideline_id: int = None, world_id: int = None):
        """
        Find a guideline section by its code.
        
        Args:
            section_code: Code like "I.1", "II.1.c"
            guideline_id: Optional specific guideline ID
            world_id: Optional world context for scoping
            
        Returns:
            GuidelineSection or None
        """
        query = cls.query.filter_by(section_code=section_code)
        
        if guideline_id:
            query = query.filter_by(guideline_id=guideline_id)
        elif world_id:
            # Join with guidelines table to filter by world
            query = query.join(cls.guideline).filter(Guideline.world_id == world_id)
        
        return query.first()
    
    @classmethod
    def find_by_codes(cls, section_codes: list, guideline_id: int = None, world_id: int = None):
        """
        Find multiple guideline sections by their codes.
        
        Args:
            section_codes: List of codes like ["I.1", "II.1.c", "III.3"]
            guideline_id: Optional specific guideline ID
            world_id: Optional world context for scoping
            
        Returns:
            List of GuidelineSection objects
        """
        query = cls.query.filter(cls.section_code.in_(section_codes))
        
        if guideline_id:
            query = query.filter_by(guideline_id=guideline_id)
        elif world_id:
            # Join with guidelines table to filter by world
            query = query.join(cls.guideline).filter(Guideline.world_id == world_id)
        
        return query.all()
    
    @classmethod
    def get_tooltip_data_for_codes(cls, section_codes: list, world_id: int = None):
        """
        Get tooltip data for multiple section codes.
        
        Args:
            section_codes: List of codes like ["I.1", "II.1.c"]
            world_id: Optional world context
            
        Returns:
            Dictionary mapping codes to tooltip data
        """
        sections = cls.find_by_codes(section_codes, world_id=world_id)
        return {section.section_code: section.get_tooltip_data() for section in sections}