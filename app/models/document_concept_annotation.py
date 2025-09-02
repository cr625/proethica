"""
Document Concept Annotation model for storing mappings between document text and ontology concepts.
"""
from app.models import db
from datetime import datetime
from sqlalchemy.orm import relationship
import uuid

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

    # New versioning fields
    version_number = db.Column(db.Integer, default=1)
    annotation_group_id = db.Column(db.String(36))
    approval_stage = db.Column(db.String(20), default='llm_extracted')  # llm_extracted, llm_approved, user_approved
    parent_annotation_id = db.Column(db.Integer, db.ForeignKey('document_concept_annotations.id'), nullable=True)
    user_edits = db.Column(db.JSON, nullable=True)
    
    # Validation status
    validation_status = db.Column(db.String(20), default='pending')  # 'pending', 'approved', 'rejected'
    validated_by = db.Column(db.Integer)  # user ID who validated
    validated_at = db.Column(db.DateTime)
    
    # Relationships
    world = relationship('World', backref='concept_annotations')
    superseded_annotation = relationship('DocumentConceptAnnotation',
                                       foreign_keys=[superseded_by],
                                       remote_side=[id])
    parent_annotation = relationship('DocumentConceptAnnotation',
                                   foreign_keys=[parent_annotation_id],
                                   remote_side=[id],
                                   backref='child_annotations')
    
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
    
    # ========== VERSION MANAGEMENT METHODS ==========

    def create_new_version(self, updates=None, approval_stage='llm_extracted'):
        """
        Create a new version of this annotation.

        Args:
            updates: Dict of fields to update in the new version
            approval_stage: New approval stage for the version

        Returns:
            New DocumentConceptAnnotation instance
        """
        if not self.annotation_group_id:
            self.annotation_group_id = str(uuid.uuid4())

        # Mark current version as not current
        self.is_current = False

        # Create new version
        new_version = DocumentConceptAnnotation()

        # Copy all fields from current annotation
        for column in self.__table__.columns:
            if column.name != 'id':  # Don't copy primary key
                setattr(new_version, column.name, getattr(self, column.name))

        # Set versioning fields
        new_version.version_number = self.get_next_version_number()
        new_version.annotation_group_id = self.annotation_group_id
        new_version.approval_stage = approval_stage
        new_version.parent_annotation_id = self.id
        new_version.is_current = True
        new_version.superseded_by = None

        # Reset validation status for new versions
        new_version.validation_status = 'pending'
        new_version.validated_by = None
        new_version.validated_at = None

        # Apply any updates
        if updates:
            for key, value in updates.items():
                if hasattr(new_version, key):
                    setattr(new_version, key, value)

            # Track user edits if this is a user modification
            if approval_stage == 'user_approved':
                new_version.user_edits = updates

        # Set timestamps
        new_version.created_at = datetime.utcnow()
        new_version.updated_at = datetime.utcnow()

        return new_version

    def get_next_version_number(self):
        """Get the next version number for this annotation group."""
        max_version = db.session.query(db.func.max(DocumentConceptAnnotation.version_number)) \
            .filter_by(annotation_group_id=self.annotation_group_id) \
            .scalar()
        return (max_version or 0) + 1

    def get_version_history(self):
        """Get all versions of this annotation (including itself)."""
        return DocumentConceptAnnotation.query \
            .filter_by(annotation_group_id=self.annotation_group_id) \
            .order_by(DocumentConceptAnnotation.version_number.desc()) \
            .all()

    def get_previous_version(self):
        """Get the immediate previous version of this annotation."""
        if self.version_number > 1:
            return DocumentConceptAnnotation.query \
                .filter_by(annotation_group_id=self.annotation_group_id,
                          version_number=self.version_number - 1) \
                .first()
        return None

    def mark_llm_approved(self, new_reasoning=None, new_confidence=None):
        """Mark this annotation as approved by LLM intermediate approval."""
        self.approval_stage = 'llm_approved'
        if new_reasoning:
            self.llm_reasoning = new_reasoning
        if new_confidence is not None:
            self.confidence = new_confidence
        db.session.commit()

    def mark_user_approved(self, user_id, edits=None):
        """Mark this annotation as approved by user."""
        self.approval_stage = 'user_approved'
        self.validation_status = 'approved'
        self.validated_by = user_id
        self.validated_at = datetime.utcnow()
        if edits:
            self.user_edits = edits
        db.session.commit()

    # ========== CLASS METHODS FOR VERSION MANAGEMENT ==========

    @classmethod
    def get_annotations_by_stage(cls, approval_stage, current_only=True):
        """Get all annotations in a specific approval stage."""
        query = cls.query.filter_by(approval_stage=approval_stage)
        if current_only:
            query = query.filter_by(is_current=True)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_annotations_for_user_approval(cls, world_id=None):
        """Get annotations ready for user approval (LLM-approved, pending user validation)."""
        query = cls.query.filter_by(
            approval_stage='llm_approved',
            validation_status='pending',
            is_current=True
        )
        if world_id:
            query = query.filter_by(world_id=world_id)
        return query.order_by(cls.created_at.desc()).all()

    @classmethod
    def get_latest_versions(cls, limit=10, world_id=None):
        """Get the latest version of each annotation group."""
        base_query = cls.query.filter_by(is_current=True)

        if world_id:
            base_query = base_query.filter_by(world_id=world_id)

        # Subquery to get distinct annotation groups
        groups_subq = base_query.with_entities(cls.annotation_group_id).distinct().subquery()

        # Get one annotation from each group (the current one)
        return cls.query.join(groups_subq, cls.annotation_group_id == groups_subq.c.annotation_group_id) \
            .filter(cls.is_current == True) \
            .order_by(cls.created_at.desc()) \
            .limit(limit) \
            .all()

    # ========== EXPANDED TO_DICT METHOD ==========

    def __repr__(self):
        return f'<DocumentConceptAnnotation v{self.version_number} {self.text_segment[:30]}... -> {self.concept_label} ({self.approval_stage})>'

    def to_dict(self, include_llm_reasoning=False, include_versions=False):
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
            # New version fields
            'version_number': self.version_number,
            'annotation_group_id': self.annotation_group_id,
            'approval_stage': self.approval_stage,
            'parent_annotation_id': self.parent_annotation_id,
            'user_edits': self.user_edits,
        }

        if include_llm_reasoning:
            data['llm_reasoning'] = self.llm_reasoning

        if include_versions:
            version_history = self.get_version_history()
            data['version_history'] = [v.to_dict(include_llm_reasoning=False, include_versions=False) for v in version_history]

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
