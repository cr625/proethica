"""
Scenario Participant Model - Updated to match actual database schema

The database already has a more comprehensive schema (22 columns) from November 11, 2025.
This model is updated to match that schema rather than the migration 013 schema.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, VARCHAR
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.models import db


class ScenarioParticipant(db.Model):
    """
    Represents a participant in a teaching scenario.

    Schema matches actual database (22 columns) - more comprehensive than migration 013.
    """

    __tablename__ = 'scenario_participants'

    # Primary key
    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)

    # Participant identification
    participant_id = Column(VARCHAR(255))  # Short ID like "p0", "p1"
    source_role_uri = Column(VARCHAR(500))  # Link to original role entity (not role_entity_uri)

    # Basic info
    name = Column(String(200), nullable=False)  # e.g., "Engineer A"
    title = Column(String(300))  # e.g., "Senior Structural Engineer"
    role_type = Column(VARCHAR(255))  # e.g., "professional", "stakeholder"
    background = Column(Text)  # Professional context

    # Structured profile data (JSONB for flexibility)
    expertise = Column(JSONB)  # {"areas": [...], "years_experience": N}
    qualifications = Column(JSONB)  # {"degrees": [...], "certifications": [...]}
    goals = Column(JSONB)  # What they're trying to achieve
    obligations = Column(JSONB)  # Professional/ethical obligations
    constraints = Column(JSONB)  # Limitations, pressures, conflicts

    # Narrative elements
    narrative_role = Column(VARCHAR(50))  # "protagonist", "antagonist", "stakeholder"
    relationships = Column(JSONB)  # Array of relationship objects (not key_relationships)

    # LLM enrichment tracking
    llm_enhanced = Column(Boolean, default=False)  # Whether LLM enhanced this participant
    llm_enrichment = Column(JSONB)  # LLM-generated insights (not metadata)
    llm_model = Column(VARCHAR(100))  # Model used for enrichment

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    case = relationship('Document', foreign_keys=[case_id], backref='scenario_participants')

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'participant_id': self.participant_id,
            'source_role_uri': self.source_role_uri,
            'name': self.name,
            'title': self.title,
            'role_type': self.role_type,
            'background': self.background,
            'expertise': self.expertise or {},
            'qualifications': self.qualifications or {},
            'goals': self.goals or [],
            'obligations': self.obligations or [],
            'constraints': self.constraints or [],
            'narrative_role': self.narrative_role,
            'relationships': self.relationships or [],
            'llm_enhanced': self.llm_enhanced,
            'llm_enrichment': self.llm_enrichment or {},
            'llm_model': self.llm_model,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<ScenarioParticipant {self.id}: {self.name} (Case {self.case_id})>"
