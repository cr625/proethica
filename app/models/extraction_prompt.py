"""
Model for storing extraction prompts for cases.

Stores the prompts used for extracting entities from cases,
enabling provenance tracking and reuse of prompts.
"""

from datetime import datetime
from app.models import db


class ExtractionPrompt(db.Model):
    """Store extraction prompts used for each case and concept type."""

    __tablename__ = 'extraction_prompts'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, nullable=False, index=True)
    concept_type = db.Column(db.String(50), nullable=False)  # 'roles', 'states', 'resources', etc.
    step_number = db.Column(db.Integer, nullable=False)  # 1, 2, or 3

    # The actual prompt text
    prompt_text = db.Column(db.Text, nullable=False)

    # The raw LLM response
    raw_response = db.Column(db.Text)  # Store the complete raw response from the LLM

    # Metadata
    prompt_version = db.Column(db.String(50))  # e.g., 'dual_extraction_v1'
    llm_model = db.Column(db.String(100))  # Model used with this prompt

    # Timestamps
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Track if this is the current/active prompt for this case/concept
    is_active = db.Column(db.Boolean, default=True)

    # Optional link to extraction session
    extraction_session_id = db.Column(db.String(100))

    # Statistics
    times_used = db.Column(db.Integer, default=0)

    # Results summary (JSON)
    results_summary = db.Column(db.JSON)  # e.g., {'classes_found': 2, 'individuals_found': 5}

    # Index for faster lookups of active prompts
    __table_args__ = (
        db.Index('ix_active_prompts', 'case_id', 'concept_type', 'is_active'),
    )

    def __repr__(self):
        return f'<ExtractionPrompt case={self.case_id} type={self.concept_type} created={self.created_at}>'

    @classmethod
    def get_active_prompt(cls, case_id, concept_type):
        """Get the current active prompt for a case and concept type."""
        return cls.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            is_active=True
        ).first()

    @classmethod
    def save_prompt(cls, case_id, concept_type, prompt_text, step_number=1,
                   llm_model=None, extraction_session_id=None, results_summary=None,
                   raw_response=None):
        """Save a new prompt, deactivating any previous active prompt."""
        # Deactivate any existing active prompts
        existing = cls.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            is_active=True
        ).all()

        for prompt in existing:
            prompt.is_active = False

        # Create new active prompt
        new_prompt = cls(
            case_id=case_id,
            concept_type=concept_type,
            step_number=step_number,
            prompt_text=prompt_text,
            raw_response=raw_response,
            llm_model=llm_model,
            extraction_session_id=extraction_session_id,
            results_summary=results_summary,
            is_active=True,
            times_used=1
        )

        db.session.add(new_prompt)
        db.session.commit()

        return new_prompt

    def update_usage(self, extraction_session_id=None, results_summary=None):
        """Update usage statistics for this prompt."""
        self.last_used_at = datetime.utcnow()
        self.times_used += 1

        if extraction_session_id:
            self.extraction_session_id = extraction_session_id

        if results_summary:
            self.results_summary = results_summary

        db.session.commit()