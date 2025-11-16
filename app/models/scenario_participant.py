"""
Scenario Participant Model

Stores enhanced participant profiles for teaching scenarios.
Part of Step 5 Stage 3 implementation.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, ARRAY
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app import db


class ScenarioParticipant(db.Model):
    """
    Represents a participant in a teaching scenario.

    Participants are enriched from basic role entities using LLM analysis
    to extract motivations, ethical tensions, and character development.
    """

    __tablename__ = 'scenario_participants'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('documents.id'), nullable=False, index=True)
    role_entity_uri = Column(Text)  # Link to original role entity

    # Basic info
    name = Column(String(200), nullable=False)  # e.g., "Engineer A"
    title = Column(String(300))  # e.g., "Senior Structural Engineer"
    background = Column(Text)  # Professional context

    # Rich profile data
    motivations = Column(ARRAY(Text))  # List of what drives them
    ethical_tensions = Column(ARRAY(Text))  # List of conflicting obligations
    character_arc = Column(Text)  # How they develop through the case

    # Relationships
    key_relationships = Column(JSONB)  # [{"participant_id": "r1", "relationship": "reports to", ...}]

    # Metadata
    metadata = Column(JSONB)  # LLM usage, confidence, extraction details
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    case = relationship('Document', foreign_keys=[case_id], backref='scenario_participants')

    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'role_entity_uri': self.role_entity_uri,
            'name': self.name,
            'title': self.title,
            'background': self.background,
            'motivations': self.motivations or [],
            'ethical_tensions': self.ethical_tensions or [],
            'character_arc': self.character_arc,
            'key_relationships': self.key_relationships or [],
            'metadata': self.metadata or {},
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f"<ScenarioParticipant {self.id}: {self.name} (Case {self.case_id})>"
