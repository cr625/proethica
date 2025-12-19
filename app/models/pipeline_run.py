"""
Pipeline Run Model for tracking automated case processing

Tracks the status of automated pipeline runs through the scenario pipeline,
enabling background processing with Celery and progress monitoring.
"""

from datetime import datetime
from app.models import db
from sqlalchemy.dialects.postgresql import JSONB


# Pipeline status constants
PIPELINE_STATUS = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'STEP1_FACTS': 'step1_facts',
    'STEP1_DISCUSSION': 'step1_discussion',
    'STEP2_FACTS': 'step2_facts',
    'STEP2_DISCUSSION': 'step2_discussion',
    'STEP3': 'step3',
    'STEP4': 'step4',
    'STEP5': 'step5',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'PAUSED': 'paused'
}


class PipelineRun(db.Model):
    """
    Tracks an automated pipeline run for a case.

    Each run processes a case through the scenario pipeline steps:
    - Step 1: Pass 1 extraction (roles, states, resources) for facts and discussion
    - Step 2: Pass 2 extraction (principles, obligations, constraints, capabilities)
    - Step 3: Pass 3 extraction (actions, events)
    - Step 4: Synthesis (provisions, questions, conclusions, transformation)
    - Step 5: Scenario generation (participants, decisions)
    """
    __tablename__ = 'pipeline_runs'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)

    # Status tracking
    status = db.Column(db.String(50), nullable=False, default=PIPELINE_STATUS['PENDING'])
    current_step = db.Column(db.String(50))

    # Celery integration
    celery_task_id = db.Column(db.String(255))

    # Progress tracking
    steps_completed = db.Column(JSONB, default=list)
    step_results = db.Column(JSONB, default=dict)

    # Error handling
    error_message = db.Column(db.Text)
    error_step = db.Column(db.String(50))
    retry_count = db.Column(db.Integer, default=0)

    # Timing
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Configuration
    config = db.Column(JSONB, default=dict)

    # User who initiated
    initiated_by = db.Column(db.Integer, db.ForeignKey('users.id'))

    # Relationships
    case = db.relationship('Document', backref=db.backref('pipeline_runs', lazy='dynamic'))
    user = db.relationship('User', backref=db.backref('initiated_runs', lazy='dynamic'))

    def __repr__(self):
        return f'<PipelineRun {self.id} case={self.case_id} status={self.status}>'

    def mark_step_complete(self, step_name: str, result: dict = None):
        """Mark a step as completed and store its result."""
        if self.steps_completed is None:
            self.steps_completed = []
        if step_name not in self.steps_completed:
            self.steps_completed = self.steps_completed + [step_name]

        if result and self.step_results is not None:
            step_results = dict(self.step_results)
            step_results[step_name] = result
            self.step_results = step_results

        self.updated_at = datetime.utcnow()

    def set_status(self, status: str):
        """Update the run status."""
        self.status = status
        self.updated_at = datetime.utcnow()
        if status == PIPELINE_STATUS['RUNNING'] and not self.started_at:
            self.started_at = datetime.utcnow()
        elif status in [PIPELINE_STATUS['COMPLETED'], PIPELINE_STATUS['FAILED']]:
            self.completed_at = datetime.utcnow()

    def set_error(self, error_message: str, error_step: str = None):
        """Record an error and mark as failed."""
        self.error_message = error_message
        self.error_step = error_step or self.current_step
        self.set_status(PIPELINE_STATUS['FAILED'])

    @property
    def duration_seconds(self) -> float:
        """Calculate run duration in seconds."""
        if not self.started_at:
            return 0
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    @property
    def is_complete(self) -> bool:
        """Check if the run completed successfully."""
        return self.status == PIPELINE_STATUS['COMPLETED']

    @property
    def is_failed(self) -> bool:
        """Check if the run failed."""
        return self.status == PIPELINE_STATUS['FAILED']

    @property
    def is_running(self) -> bool:
        """Check if the run is currently in progress."""
        return self.status not in [
            PIPELINE_STATUS['PENDING'],
            PIPELINE_STATUS['COMPLETED'],
            PIPELINE_STATUS['FAILED'],
            PIPELINE_STATUS['PAUSED']
        ]

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'status': self.status,
            'current_step': self.current_step,
            'celery_task_id': self.celery_task_id,
            'steps_completed': self.steps_completed or [],
            'step_results': self.step_results or {},
            'error_message': self.error_message,
            'error_step': self.error_step,
            'retry_count': self.retry_count,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'duration_seconds': self.duration_seconds,
            'is_complete': self.is_complete,
            'is_failed': self.is_failed,
            'is_running': self.is_running
        }


class PipelineQueue(db.Model):
    """
    Queue for batch processing of cases.

    Allows users to queue multiple cases for automated processing,
    with priority and grouping support.
    """
    __tablename__ = 'pipeline_queue'

    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), nullable=False)
    priority = db.Column(db.Integer, default=0)  # Higher = more urgent
    status = db.Column(db.String(50), nullable=False, default='queued')
    group_name = db.Column(db.String(100))
    config = db.Column(JSONB, default=dict)  # Pipeline configuration (include_step4, etc.)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)

    # Relationships
    case = db.relationship('Document', backref=db.backref('queue_entries', lazy='dynamic'))

    __table_args__ = (
        db.UniqueConstraint('case_id', 'status', name='uq_pipeline_queue_case_status'),
    )

    def __repr__(self):
        return f'<PipelineQueue {self.id} case={self.case_id} priority={self.priority}>'

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'priority': self.priority,
            'status': self.status,
            'group_name': self.group_name,
            'config': self.config or {},
            'added_at': self.added_at.isoformat() if self.added_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None
        }
