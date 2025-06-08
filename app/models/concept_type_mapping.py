"""
Model for tracking concept type mapping decisions (audit trail).
"""

from datetime import datetime
from app.models import db


class ConceptTypeMapping(db.Model):
    """Model for tracking type mapping decisions for learning and improvement."""
    
    __tablename__ = 'concept_type_mappings'
    
    id = db.Column(db.Integer, primary_key=True)
    original_llm_type = db.Column(db.String(255), nullable=False)
    mapped_to_type = db.Column(db.String(255), nullable=False)
    mapping_confidence = db.Column(db.Float)
    is_automatic = db.Column(db.Boolean, default=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    review_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Learning fields
    usage_count = db.Column(db.Integer, default=1)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    reviewer = db.relationship('User', backref='reviewed_mappings')
    
    # Constraints
    __table_args__ = (
        db.CheckConstraint(
            (mapping_confidence >= 0) & (mapping_confidence <= 1), 
            name='valid_confidence_range'
        ),
    )
    
    def __repr__(self):
        return f'<ConceptTypeMapping {self.id}: {self.original_llm_type} -> {self.mapped_to_type}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'original_llm_type': self.original_llm_type,
            'mapped_to_type': self.mapped_to_type,
            'mapping_confidence': self.mapping_confidence,
            'is_automatic': self.is_automatic,
            'reviewed_by': self.reviewed_by,
            'review_notes': self.review_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'usage_count': self.usage_count,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
        }
    
    def record_usage(self):
        """Record that this mapping was used again."""
        self.usage_count += 1
        self.last_used_at = datetime.utcnow()
    
    def add_review(self, user_id, notes):
        """Add human review to this mapping."""
        self.reviewed_by = user_id
        self.review_notes = notes
        self.is_automatic = False
    
    @classmethod
    def get_mapping_for_type(cls, llm_type):
        """Get the most commonly used mapping for an LLM type."""
        return cls.query.filter_by(original_llm_type=llm_type)\
                       .order_by(cls.usage_count.desc(), cls.last_used_at.desc())\
                       .first()
    
    @classmethod
    def get_popular_mappings(cls, limit=20):
        """Get the most popular type mappings."""
        return cls.query.order_by(cls.usage_count.desc())\
                       .limit(limit).all()
    
    @classmethod
    def get_low_confidence_mappings(cls, threshold=0.7):
        """Get mappings with low confidence that might need review."""
        return cls.query.filter(cls.mapping_confidence < threshold)\
                       .filter_by(reviewed_by=None)\
                       .order_by(cls.mapping_confidence.asc())\
                       .all()
    
    @classmethod
    def create_or_update_mapping(cls, llm_type, mapped_type, confidence, is_automatic=True):
        """Create a new mapping or update usage of existing one."""
        existing = cls.query.filter_by(
            original_llm_type=llm_type,
            mapped_to_type=mapped_type
        ).first()
        
        if existing:
            existing.record_usage()
            # Update confidence if new confidence is higher
            if confidence > existing.mapping_confidence:
                existing.mapping_confidence = confidence
            return existing
        else:
            new_mapping = cls(
                original_llm_type=llm_type,
                mapped_to_type=mapped_type,
                mapping_confidence=confidence,
                is_automatic=is_automatic
            )
            db.session.add(new_mapping)
            return new_mapping
    
    @classmethod
    def get_mapping_statistics(cls):
        """Get statistics about type mappings."""
        total_mappings = cls.query.count()
        automatic_mappings = cls.query.filter_by(is_automatic=True).count()
        reviewed_mappings = cls.query.filter(cls.reviewed_by.isnot(None)).count()
        avg_confidence = db.session.query(db.func.avg(cls.mapping_confidence)).scalar() or 0
        
        return {
            'total_mappings': total_mappings,
            'automatic_mappings': automatic_mappings,
            'reviewed_mappings': reviewed_mappings,
            'review_percentage': (reviewed_mappings / total_mappings * 100) if total_mappings > 0 else 0,
            'average_confidence': round(avg_confidence, 3)
        }