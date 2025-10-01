"""
SQLAlchemy model for extraction_section_prompts table.

Stores section-specific prompts for multi-section NSPE case extraction.
Enables web-based prompt editing and version tracking.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB
from app.models import db


class ExtractionSectionPrompt(db.Model):
    """
    Model for section-specific extraction prompts.

    Stores prompts for extracting ProEthica concepts from different NSPE case sections
    (Facts, Discussion, Questions, Conclusions, Dissenting Opinion, References).

    Attributes:
        section_type: NSPE section ('facts', 'discussion', 'questions', etc.)
        extraction_pass: Pass number (1=Contextual, 2=Normative, 3=Behavioral, 4=Synthesis)
        concept_type: ProEthica concept ('roles', 'principles', 'actions', etc.)
        extraction_guidance: Section-specific instructions for extraction
    """

    __tablename__ = 'extraction_section_prompts'

    # Primary key
    id = Column(Integer, primary_key=True)

    # Section identification
    section_type = Column(String(50), nullable=False, index=True)
    extraction_pass = Column(Integer, nullable=False, index=True)
    concept_type = Column(String(50), nullable=False, index=True)

    # Prompt components
    system_prompt = Column(Text)
    instruction_template = Column(Text)
    examples = Column(JSONB)  # Few-shot examples specific to section

    # Section-specific extraction guidance
    extraction_guidance = Column(Text)

    # Metadata
    prompt_name = Column(String(200))
    description = Column(Text)

    # Versioning
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100))
    is_active = Column(Boolean, default=True)

    # Usage statistics
    times_used = Column(Integer, default=0)
    avg_entities_extracted = Column(Float)
    avg_confidence = Column(Float)
    last_used_at = Column(DateTime)

    # Constraints
    __table_args__ = (
        CheckConstraint(
            section_type.in_([
                'facts', 'discussion', 'questions', 'conclusions',
                'dissenting_opinion', 'references', 'synthesis'
            ]),
            name='valid_section_type'
        ),
        CheckConstraint(
            extraction_pass.between(1, 4),
            name='valid_extraction_pass'
        ),
        CheckConstraint(
            concept_type.in_([
                'roles', 'states', 'resources',
                'principles', 'obligations', 'constraints', 'capabilities',
                'actions', 'events', 'synthesis'
            ]),
            name='valid_concept_type'
        ),
    )

    @classmethod
    def get_prompt_for_section(cls, section_type: str, extraction_pass: int,
                               concept_type: str, version: int = None):
        """
        Get the active prompt for a specific section/pass/concept combination.

        Args:
            section_type: Section identifier ('facts', 'discussion', etc.)
            extraction_pass: Pass number (1-4)
            concept_type: Concept type ('roles', 'principles', etc.)
            version: Specific version (defaults to latest active)

        Returns:
            ExtractionSectionPrompt instance or None
        """
        query = cls.query.filter_by(
            section_type=section_type,
            extraction_pass=extraction_pass,
            concept_type=concept_type,
            is_active=True
        )

        if version:
            query = query.filter_by(version=version)

        return query.order_by(cls.version.desc()).first()

    @classmethod
    def get_all_prompts_for_section(cls, section_type: str, extraction_pass: int):
        """
        Get all active prompts for a section and pass.

        Args:
            section_type: Section identifier
            extraction_pass: Pass number

        Returns:
            List of ExtractionSectionPrompt instances
        """
        return cls.query.filter_by(
            section_type=section_type,
            extraction_pass=extraction_pass,
            is_active=True
        ).order_by(cls.concept_type).all()

    @classmethod
    def get_all_prompts_for_pass(cls, extraction_pass: int):
        """
        Get all active prompts for an extraction pass across all sections.

        Args:
            extraction_pass: Pass number (1-4)

        Returns:
            Dictionary mapping (section_type, concept_type) to prompt
        """
        prompts = cls.query.filter_by(
            extraction_pass=extraction_pass,
            is_active=True
        ).all()

        return {
            (p.section_type, p.concept_type): p
            for p in prompts
        }

    def record_usage(self, entities_extracted: int = None, avg_confidence: float = None):
        """
        Record usage of this prompt.

        Args:
            entities_extracted: Number of entities extracted
            avg_confidence: Average confidence score
        """
        self.times_used += 1
        self.last_used_at = datetime.utcnow()

        if entities_extracted is not None:
            if self.avg_entities_extracted is None:
                self.avg_entities_extracted = float(entities_extracted)
            else:
                # Running average
                self.avg_entities_extracted = (
                    (self.avg_entities_extracted * (self.times_used - 1) + entities_extracted)
                    / self.times_used
                )

        if avg_confidence is not None:
            if self.avg_confidence is None:
                self.avg_confidence = avg_confidence
            else:
                # Running average
                self.avg_confidence = (
                    (self.avg_confidence * (self.times_used - 1) + avg_confidence)
                    / self.times_used
                )

        db.session.commit()

    def __repr__(self):
        return (
            f"<ExtractionSectionPrompt("
            f"section={self.section_type}, "
            f"pass={self.extraction_pass}, "
            f"concept={self.concept_type}, "
            f"v={self.version})>"
        )
