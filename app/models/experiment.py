"""
Database models for the ProEthica experiment/validation system.

These models store information about validation studies, predictions, and evaluations.
Updated to support Chapter 4 validation metrics (RTI, PBRQ, CA, DRA).
"""

from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import JSON


class ExperimentRun(db.Model):
    """Model for tracking validation study configurations and runs."""

    __tablename__ = 'experiment_runs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(255))
    config = db.Column(JSON)  # Stores experiment configuration
    status = db.Column(db.String(50), default='created')  # created, running, completed, failed

    # Domain track (engineering or education)
    domain = db.Column(db.String(50), default='engineering')

    # Relationships
    predictions = db.relationship('Prediction', back_populates='experiment_run', cascade='all, delete-orphan')
    evaluations = db.relationship('ExperimentEvaluation', back_populates='experiment_run', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<ExperimentRun {self.id}: {self.name}>"


class PredictionTarget(db.Model):
    """Model for tracking specific prediction targets in experiments."""

    __tablename__ = 'prediction_targets'

    id = db.Column(db.Integer, primary_key=True)
    experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=True)
    name = db.Column(db.String(50), nullable=True)  # e.g., 'conclusion', 'discussion'
    description = db.Column(db.Text)

    # Relationships
    experiment_run = db.relationship('ExperimentRun')

    def __repr__(self):
        return f"<PredictionTarget {self.id}: {self.name}>"


class Prediction(db.Model):
    """Model for storing predictions generated under experimental conditions."""

    __tablename__ = 'experiment_predictions'

    id = db.Column(db.Integer, primary_key=True)
    experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=True)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=True)
    condition = db.Column(db.String(50), nullable=True)  # 'baseline' or 'proethica'
    target = db.Column(db.String(50), nullable=True, default='full')  # 'full', 'conclusion', 'discussion'
    prediction_text = db.Column(db.Text)
    reasoning = db.Column(db.Text)
    prompt = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    meta_info = db.Column(JSON)  # Additional metadata (e.g., concepts used)

    # Relationships
    experiment_run = db.relationship('ExperimentRun', back_populates='predictions')
    document = db.relationship('Document', backref=db.backref('predictions', cascade='all, delete-orphan'))
    evaluations = db.relationship('ExperimentEvaluation', back_populates='prediction', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Prediction {self.id}: {self.condition} for document {self.document_id}>"


class ExperimentEvaluation(db.Model):
    """Model for storing evaluator feedback on predictions.

    Updated to support Chapter 4 validation metrics:
    - RTI: Reasoning Transparency Index (4 sub-items)
    - PBRQ: Precedent-Based Reasoning Quality (4 sub-items)
    - CA: Citation Accuracy (3 sub-items)
    - DRA: Domain Relevance Assessment (4 sub-items)

    All sub-items use 1-7 Likert scale.
    """

    __tablename__ = 'experiment_evaluations'

    id = db.Column(db.Integer, primary_key=True)
    experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey('experiment_predictions.id'), nullable=True)
    evaluator_id = db.Column(db.String(255))  # Anonymous participant ID (P001, etc.)

    # Evaluator metadata
    evaluator_domain = db.Column(db.String(50))  # 'engineering' or 'education'
    evaluator_program = db.Column(db.String(100))  # Specific program (optional)

    # =========================================================================
    # Chapter 4 Validation Metrics (1-7 Likert scale)
    # =========================================================================

    # RTI: Reasoning Transparency Index (4 sub-items)
    # "How clearly does the reasoning trace from facts through principles to conclusions?"
    rti_premises_clear = db.Column(db.Integer)  # Are factual premises clearly stated?
    rti_steps_explicit = db.Column(db.Integer)  # Are reasoning steps explicit and followable?
    rti_conclusion_supported = db.Column(db.Integer)  # Is conclusion clearly supported?
    rti_alternatives_acknowledged = db.Column(db.Integer)  # Are alternatives acknowledged?

    # PBRQ: Precedent-Based Reasoning Quality (4 sub-items)
    # "Does the system employ sound case-based reasoning methodology?"
    pbrq_precedents_identified = db.Column(db.Integer)  # Are relevant precedents identified?
    pbrq_principles_extracted = db.Column(db.Integer)  # Are principles correctly extracted?
    pbrq_adaptation_appropriate = db.Column(db.Integer)  # Is adaptation to facts appropriate?
    pbrq_selection_justified = db.Column(db.Integer)  # Is precedent selection justified?

    # CA: Citation Accuracy (3 sub-items)
    # "Are references to codes and precedents factually correct?"
    ca_code_citations_correct = db.Column(db.Integer)  # Are code provisions correctly cited?
    ca_precedents_characterized = db.Column(db.Integer)  # Are precedents accurately characterized?
    ca_citations_support_claims = db.Column(db.Integer)  # Do citations support claims made?

    # DRA: Domain Relevance Assessment (4 sub-items)
    # "Does the analysis address concerns relevant to professional practice?"
    dra_concerns_relevant = db.Column(db.Integer)  # Does analysis address relevant concerns?
    dra_patterns_accepted = db.Column(db.Integer)  # Does reasoning follow accepted patterns?
    dra_guidance_helpful = db.Column(db.Integer)  # Would this guidance help a practitioner?
    dra_domain_weighted = db.Column(db.Integer)  # Are domain considerations appropriately weighted?

    # =========================================================================
    # Overall Preference (5-point scale)
    # =========================================================================
    # -2: Strongly prefer this system
    # -1: Somewhat prefer this system
    #  0: No meaningful difference
    #  1: Somewhat prefer other system
    #  2: Strongly prefer other system
    # Note: Stored per-prediction, interpreted relative to baseline/proethica
    overall_preference = db.Column(db.Integer)
    preference_justification = db.Column(db.Text)  # Brief justification (required)

    # =========================================================================
    # Legacy fields (kept for backward compatibility, can be removed later)
    # =========================================================================
    reasoning_quality = db.Column(db.Float)  # Legacy: 0-10 scale
    persuasiveness = db.Column(db.Float)  # Legacy: 0-10 scale
    coherence = db.Column(db.Float)  # Legacy: 0-10 scale
    accuracy = db.Column(db.Boolean)  # Legacy
    agreement = db.Column(db.Boolean)  # Legacy
    support_quality = db.Column(db.Float)  # Legacy: 0-10 scale
    preference_score = db.Column(db.Float)  # Legacy: 0-10 scale
    alignment_score = db.Column(db.Float)  # Legacy: 0-10 scale

    # Comments
    comments = db.Column(db.Text)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Metadata
    meta_info = db.Column(JSON)  # Additional metadata

    # Relationships
    experiment_run = db.relationship('ExperimentRun', back_populates='evaluations')
    prediction = db.relationship('Prediction', back_populates='evaluations')

    # =========================================================================
    # Computed Properties for Metric Means
    # =========================================================================

    @property
    def rti_mean(self):
        """Compute mean RTI score across sub-items."""
        scores = [
            self.rti_premises_clear,
            self.rti_steps_explicit,
            self.rti_conclusion_supported,
            self.rti_alternatives_acknowledged
        ]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def pbrq_mean(self):
        """Compute mean PBRQ score across sub-items."""
        scores = [
            self.pbrq_precedents_identified,
            self.pbrq_principles_extracted,
            self.pbrq_adaptation_appropriate,
            self.pbrq_selection_justified
        ]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def ca_mean(self):
        """Compute mean CA score across sub-items."""
        scores = [
            self.ca_code_citations_correct,
            self.ca_precedents_characterized,
            self.ca_citations_support_claims
        ]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def dra_mean(self):
        """Compute mean DRA score across sub-items."""
        scores = [
            self.dra_concerns_relevant,
            self.dra_patterns_accepted,
            self.dra_guidance_helpful,
            self.dra_domain_weighted
        ]
        valid = [s for s in scores if s is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    @property
    def all_metrics_complete(self):
        """Check if all Chapter 4 metrics have been filled."""
        required = [
            self.rti_premises_clear, self.rti_steps_explicit,
            self.rti_conclusion_supported, self.rti_alternatives_acknowledged,
            self.pbrq_precedents_identified, self.pbrq_principles_extracted,
            self.pbrq_adaptation_appropriate, self.pbrq_selection_justified,
            self.ca_code_citations_correct, self.ca_precedents_characterized,
            self.ca_citations_support_claims,
            self.dra_concerns_relevant, self.dra_patterns_accepted,
            self.dra_guidance_helpful, self.dra_domain_weighted
        ]
        return all(s is not None for s in required)

    def __repr__(self):
        return f"<Evaluation {self.id} by {self.evaluator_id} for prediction {self.prediction_id}>"
