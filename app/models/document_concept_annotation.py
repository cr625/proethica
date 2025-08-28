"""
Document Concept Annotation model for storing mappings between document text and ontology concepts.
"""
from app.models import db
from datetime import datetime
from sqlalchemy.orm import relationship

class DocumentConceptAnnotation(db.Model):
    """
    Model for storing mappings between document text segments and ontology concepts from OntServe.
    Supports versioning and validation workflows.
    """
    __tablename__ = 'document_concept_annotations'
    
    # Primary key
    id = db.Column(db.Integer, primary_key=True)
    
    # Document reference
    document_type = db.Column(db.String(50), nullable=False)  # 'guideline' or 'case'
    document_id = db.Column(db.Integer, nullable=False)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=True)
    
    # Annotation details
    text_segment = db.Column(db.String(500), nullable=False)  # The actual text being annotated
    start_offset = db.Column(db.Integer)  # Character position in document
    end_offset = db.Column(db.Integer)
    
    # Ontology linking
    ontology_name = db.Column(db.String(100), nullable=False)  # e.g., 'proethica-intermediate'
    ontology_version = db.Column(db.String(50))
    concept_uri = db.Column(db.String(500), nullable=False)  # Full URI of the concept
    concept_label = db.Column(db.String(255))
    concept_definition = db.Column(db.Text)
    concept_type = db.Column(db.String(100))  # e.g., 'Principle', 'Obligation', etc.
    confidence = db.Column(db.Float)  # LLM confidence score (0.0 to 1.0)
    
    # Metadata
    llm_model = db.Column(db.String(100))
    llm_reasoning = db.Column(db.Text)  # Store LLM's justification
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Version tracking
    is_current = db.Column(db.Boolean, default=True)
    superseded_by = db.Column(db.Integer, db.ForeignKey('document_concept_annotations.id'), nullable=True)
    
    # Validation status
    validation_status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected'
    validated_by = db.Column(db.Integer)  # user ID who validated
    validated_at = db.Column(db.DateTime)
    
    # Relationships
    world = relationship('World', backref='concept_annotations')
    superseded_annotation = relationship('DocumentConceptAnnotation', remote_side=[id])
    
    # Table constraints
    __table_args__ = (
        db.CheckConstraint("document_type IN ('guideline', 'case')", name='valid_document_type'),
        db.CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name='valid_confidence'),
        db.CheckConstraint("validation_status IN ('pending', 'approved', 'rejected')", name='valid_validation_status'),
        db.Index('idx_doc_annotations_lookup', 'document_type', 'document_id', 'is_current'),
        db.Index('idx_doc_annotations_ontology', 'ontology_name', 'ontology_version'),
        db.Index('idx_doc_annotations_concept', 'concept_uri'),
        db.Index('idx_doc_annotations_world', 'world_id'),
        db.Index('idx_doc_annotations_validation', 'validation_status', 'is_current'),
    )
    
    def __repr__(self):
        return f'<DocumentConceptAnnotation {self.text_segment[:30]}... -> {self.concept_label}>'
    
    def to_dict(self, include_llm_reasoning=False):
        """Convert annotation to dictionary for API responses."""
        data = {
            'id': self.id,
            'document_type': self.document_type,
            'document_id': self.document_id,
            'world_id': self.world_id,
            'text_segment': self.text_segment,
            'start_offset': self.start_offset,
            'end_offset': self.end_offset,
            'ontology_name': self.ontology_name,
            'ontology_version': self.ontology_version,
            'concept_uri': self.concept_uri,
            'concept_label': self.concept_label,
            'concept_definition': self.concept_definition,
            'concept_type': self.concept_type,
            'confidence': self.confidence,
            'llm_model': self.llm_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_current': self.is_current,
            'validation_status': self.validation_status,
            'validated_by': self.validated_by,
            'validated_at': self.validated_at.isoformat() if self.validated_at else None,
        }
        
        if include_llm_reasoning:
            data['llm_reasoning'] = self.llm_reasoning
        
        return data
    
    def get_document(self):
        """Get the referenced document object."""
        if self.document_type == 'guideline':
            from app.models.guideline import Guideline
            return Guideline.query.get(self.document_id)
        elif self.document_type == 'case':
            from app.models.case import Case
            return Case.query.get(self.document_id)
        return None
    
    def supersede(self, new_annotation):
        """Mark this annotation as superseded by a newer one."""
        self.is_current = False
        self.superseded_by = new_annotation.id
        db.session.commit()
    
    def approve(self, user_id):
        """Approve this annotation."""
        self.validation_status = 'approved'
        self.validated_by = user_id
        self.validated_at = datetime.utcnow()
        db.session.commit()
    
    def reject(self, user_id):
        """Reject this annotation."""
        self.validation_status = 'rejected'
        self.validated_by = user_id
        self.validated_at = datetime.utcnow()
        db.session.commit()
    
    def get_confidence_level(self):
        """Get human-readable confidence level."""
        if self.confidence is None:
            return 'unknown'
        elif self.confidence >= 0.8:
            return 'high'
        elif self.confidence >= 0.6:
            return 'medium'
        elif self.confidence >= 0.4:
            return 'low'
        else:
            return 'very_low'
    
    def get_confidence_badge_class(self):
        """Get Bootstrap badge class for confidence display."""
        level = self.get_confidence_level()
        badge_map = {
            'high': 'badge-success',
            'medium': 'badge-info',
            'low': 'badge-warning',
            'very_low': 'badge-danger',
            'unknown': 'badge-secondary'
        }
        return badge_map.get(level, 'badge-secondary')
    
    @classmethod
    def get_annotations_for_document(cls, document_type, document_id, current_only=True):
        """Get all annotations for a specific document."""
        query = cls.query.filter_by(
            document_type=document_type,
            document_id=document_id
        )
        
        if current_only:
            query = query.filter_by(is_current=True)
        
        return query.order_by(cls.start_offset.asc()).all()
    
    @classmethod
    def get_annotations_for_world(cls, world_id, current_only=True):
        """Get all annotations for documents in a specific world."""
        query = cls.query.filter_by(world_id=world_id)
        
        if current_only:
            query = query.filter_by(is_current=True)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_annotations_by_ontology(cls, ontology_name, current_only=True):
        """Get all annotations from a specific ontology."""
        query = cls.query.filter_by(ontology_name=ontology_name)
        
        if current_only:
            query = query.filter_by(is_current=True)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_annotations_by_concept(cls, concept_uri, current_only=True):
        """Get all annotations for a specific concept."""
        query = cls.query.filter_by(concept_uri=concept_uri)
        
        if current_only:
            query = query.filter_by(is_current=True)
        
        return query.order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_pending_validations(cls):
        """Get all annotations pending validation."""
        return cls.query.filter_by(
            validation_status='pending',
            is_current=True
        ).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_annotation_statistics(cls, world_id=None):
        """Get statistics about annotations."""
        query = cls.query.filter_by(is_current=True)
        
        if world_id:
            query = query.filter_by(world_id=world_id)
        
        total = query.count()
        approved = query.filter_by(validation_status='approved').count()
        rejected = query.filter_by(validation_status='rejected').count()
        pending = query.filter_by(validation_status='pending').count()
        
        # Get counts by ontology
        ontology_counts = db.session.query(
            cls.ontology_name, 
            db.func.count(cls.id)
        ).filter(
            cls.is_current == True
        )
        
        if world_id:
            ontology_counts = ontology_counts.filter(cls.world_id == world_id)
        
        ontology_counts = ontology_counts.group_by(cls.ontology_name).all()
        
        # Get counts by confidence level
        high_confidence = query.filter(cls.confidence >= 0.8).count()
        medium_confidence = query.filter(cls.confidence >= 0.6, cls.confidence < 0.8).count()
        low_confidence = query.filter(cls.confidence < 0.6).count()
        
        return {
            'total': total,
            'approved': approved,
            'rejected': rejected,
            'pending': pending,
            'ontology_counts': dict(ontology_counts),
            'confidence_levels': {
                'high': high_confidence,
                'medium': medium_confidence,
                'low': low_confidence
            }
        }
