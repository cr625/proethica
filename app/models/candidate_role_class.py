"""
Candidate Role Class Model

Stores discovered role classes that need expert validation before integration
into the proethica-intermediate ontology.
"""

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models import db
import uuid

class CandidateRoleClass(db.Model):
    """
    Model for role classes discovered from cases that need validation
    """
    __tablename__ = 'candidate_role_classes'

    # Primary identification
    id = Column(Integer, primary_key=True)
    uuid = Column(UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4)

    # Basic role class information
    label = Column(String(255), nullable=False, index=True)
    definition = Column(Text, nullable=False)
    proposed_uri = Column(String(500), nullable=True)  # Proposed URI if approved

    # Discovery context
    discovered_in_case_id = Column(Integer, nullable=False, index=True)
    discovered_from_section = Column(String(50), nullable=True)  # facts, questions, etc.
    discovery_confidence = Column(Float, nullable=False, default=0.8)

    # Professional classification details
    distinguishing_features = Column(JSON, nullable=True)  # List of unique characteristics
    professional_scope = Column(Text, nullable=True)  # Areas of responsibility
    typical_qualifications = Column(JSON, nullable=True)  # Required education/licenses
    examples_from_case = Column(JSON, nullable=True)  # How it appeared in source case

    # Similarity analysis
    similarity_to_existing = Column(Float, nullable=False, default=0.0)
    existing_similar_classes = Column(JSON, nullable=True)  # List of similar existing classes

    # Validation workflow status
    status = Column(String(50), nullable=False, default='pending_review', index=True)
    # pending_review, under_review, approved, rejected, needs_revision

    validation_priority = Column(String(20), nullable=False, default='medium')
    # high, medium, low - based on discovery confidence and novelty

    # Expert review information
    reviewed_by = Column(String(255), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    revision_requested = Column(Text, nullable=True)  # Specific changes needed

    # Integration information (for approved classes)
    approved_label = Column(String(255), nullable=True)  # Final approved label (may differ from proposed)
    approved_definition = Column(Text, nullable=True)  # Final approved definition
    integrated_at = Column(DateTime, nullable=True)
    integrated_into_ontology = Column(String(100), nullable=True)  # Which ontology it was added to
    final_uri = Column(String(500), nullable=True)  # Final URI in ontology

    # Metadata and tracking
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    extraction_metadata = Column(JSON, nullable=True)  # LLM model, extraction session info

    # References to individuals who fulfill this role
    role_individuals = relationship("CandidateRoleIndividual", back_populates="candidate_role_class")

    def __repr__(self):
        return f"<CandidateRoleClass('{self.label}', status='{self.status}', case={self.discovered_in_case_id})>"

    @property
    def is_novel(self):
        """True if this appears to be a genuinely new role class"""
        return self.similarity_to_existing < 0.3

    @property
    def needs_expert_attention(self):
        """True if this candidate needs expert review due to complexity or ambiguity"""
        return (
            self.similarity_to_existing > 0.6 or  # Similar to existing - needs disambiguation
            self.discovery_confidence < 0.7 or    # Low confidence extraction
            not self.distinguishing_features or   # Missing key details
            self.status == 'needs_revision'       # Previously reviewed, needs changes
        )

    def approve(self, reviewed_by: str, approved_label: str = None, approved_definition: str = None, review_notes: str = None):
        """Approve this candidate for integration into ontology"""
        self.status = 'approved'
        self.reviewed_by = reviewed_by
        self.reviewed_at = datetime.utcnow()
        self.review_notes = review_notes
        self.approved_label = approved_label or self.label
        self.approved_definition = approved_definition or self.definition

        # Generate proposed URI
        safe_label = self.approved_label.replace(' ', '').replace('-', '').replace('_', '')
        self.proposed_uri = f"http://proethica.org/ontology/intermediate#{safe_label}"

    def reject(self, reviewed_by: str, review_notes: str):
        """Reject this candidate class"""
        self.status = 'rejected'
        self.reviewed_by = reviewed_by
        self.reviewed_at = datetime.utcnow()
        self.review_notes = review_notes

    def request_revision(self, reviewed_by: str, revision_notes: str, review_notes: str = None):
        """Request revisions to this candidate"""
        self.status = 'needs_revision'
        self.reviewed_by = reviewed_by
        self.reviewed_at = datetime.utcnow()
        self.revision_requested = revision_notes
        self.review_notes = review_notes

    def mark_integrated(self, ontology_name: str, final_uri: str):
        """Mark as successfully integrated into ontology"""
        self.status = 'integrated'
        self.integrated_at = datetime.utcnow()
        self.integrated_into_ontology = ontology_name
        self.final_uri = final_uri

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'uuid': str(self.uuid),
            'label': self.label,
            'definition': self.definition,
            'discovered_in_case_id': self.discovered_in_case_id,
            'discovery_confidence': self.discovery_confidence,
            'distinguishing_features': self.distinguishing_features,
            'professional_scope': self.professional_scope,
            'typical_qualifications': self.typical_qualifications,
            'examples_from_case': self.examples_from_case,
            'similarity_to_existing': self.similarity_to_existing,
            'existing_similar_classes': self.existing_similar_classes,
            'status': self.status,
            'validation_priority': self.validation_priority,
            'reviewed_by': self.reviewed_by,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'review_notes': self.review_notes,
            'revision_requested': self.revision_requested,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_novel': self.is_novel,
            'needs_expert_attention': self.needs_expert_attention
        }

class CandidateRoleIndividual(db.Model):
    """
    Model linking individuals to candidate role classes
    """
    __tablename__ = 'candidate_role_individuals'

    id = Column(Integer, primary_key=True)
    candidate_role_class_id = Column(Integer, ForeignKey('candidate_role_classes.id'), nullable=False)
    individual_name = Column(String(255), nullable=False)
    individual_attributes = Column(JSON, nullable=True)
    case_id = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationship
    candidate_role_class = relationship("CandidateRoleClass", back_populates="role_individuals")

    def __repr__(self):
        return f"<CandidateRoleIndividual('{self.individual_name}', role='{self.candidate_role_class.label if self.candidate_role_class else 'Unknown'}')>"