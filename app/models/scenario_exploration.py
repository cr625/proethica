"""
Scenario Exploration Session Models

Tracks user interactive scenario explorations where they make choices
at decision points and see LLM-generated consequences.
"""

from datetime import datetime
from typing import List, Dict, Optional, Any
from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship

from app.models import db


class ScenarioExplorationSession(db.Model):
    """Tracks a user's interactive scenario exploration session."""

    __tablename__ = 'scenario_exploration_sessions'

    id = Column(Integer, primary_key=True)
    case_id = Column(Integer, ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    session_uuid = Column(String(36), unique=True, nullable=False)

    # Session state
    status = Column(String(20), nullable=False, default='in_progress')
    current_decision_index = Column(Integer, nullable=False, default=0)

    # Exploration mode
    exploration_mode = Column(String(20), nullable=False, default='interactive')

    # Event calculus state
    active_fluents = Column(JSON, default=list)
    terminated_fluents = Column(JSON, default=list)

    # Timestamps
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime)
    last_activity_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Optional user tracking
    user_id = Column(Integer)

    # Analysis results
    final_analysis = Column(JSON)

    # Relationships
    choices = relationship('ScenarioExplorationChoice', back_populates='session',
                          cascade='all, delete-orphan', order_by='ScenarioExplorationChoice.decision_point_index')
    case = relationship('Document', backref='exploration_sessions')

    def __repr__(self):
        return f'<ScenarioExplorationSession {self.session_uuid} case={self.case_id} status={self.status}>'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'case_id': self.case_id,
            'session_uuid': self.session_uuid,
            'status': self.status,
            'current_decision_index': self.current_decision_index,
            'exploration_mode': self.exploration_mode,
            'active_fluents': self.active_fluents or [],
            'choices_made': len(self.choices),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }

    def get_choices_summary(self) -> List[Dict]:
        """Get summary of all choices made in this session."""
        return [
            {
                'index': c.decision_point_index,
                'label': c.decision_point_label,
                'user_choice': c.chosen_option_label,
                'board_choice': c.board_choice_label,
                'matches_board': c.matches_board_choice
            }
            for c in self.choices
        ]


class ScenarioExplorationChoice(db.Model):
    """Records a user's choice at a decision point."""

    __tablename__ = 'scenario_exploration_choices'

    id = Column(Integer, primary_key=True)
    session_id = Column(Integer, ForeignKey('scenario_exploration_sessions.id', ondelete='CASCADE'), nullable=False)

    # Decision point info
    decision_point_index = Column(Integer, nullable=False)
    decision_point_uri = Column(String(500))
    decision_point_label = Column(Text)

    # User's choice
    chosen_option_index = Column(Integer, nullable=False)
    chosen_option_label = Column(Text)
    chosen_option_uri = Column(String(500))

    # Board's actual choice (for comparison)
    board_choice_index = Column(Integer)
    board_choice_label = Column(Text)
    matches_board_choice = Column(Boolean)

    # LLM-generated consequences
    consequences_narrative = Column(Text)
    fluents_initiated = Column(JSON, default=list)
    fluents_terminated = Column(JSON, default=list)

    # Context provided to LLM
    context_provided = Column(JSON)

    # Timing
    chosen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    time_spent_seconds = Column(Integer)

    # Relationships
    session = relationship('ScenarioExplorationSession', back_populates='choices')

    def __repr__(self):
        return f'<ScenarioExplorationChoice session={self.session_id} dp={self.decision_point_index} choice={self.chosen_option_label}>'

    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'decision_point_index': self.decision_point_index,
            'decision_point_label': self.decision_point_label,
            'chosen_option_index': self.chosen_option_index,
            'chosen_option_label': self.chosen_option_label,
            'board_choice_label': self.board_choice_label,
            'matches_board_choice': self.matches_board_choice,
            'consequences_narrative': self.consequences_narrative,
            'fluents_initiated': self.fluents_initiated or [],
            'fluents_terminated': self.fluents_terminated or [],
            'time_spent_seconds': self.time_spent_seconds,
            'chosen_at': self.chosen_at.isoformat() if self.chosen_at else None,
        }
