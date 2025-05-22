"""
Database models for the ProEthica experiment.

These models store information about experiment runs, predictions, and evaluations.
"""

from datetime import datetime
from app import db
from sqlalchemy.dialects.postgresql import JSON

class ExperimentRun(db.Model):
    """Model for tracking experiment configurations and runs."""
    
    __tablename__ = 'experiment_runs'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(255))
    config = db.Column(JSON)  # Stores experiment configuration
    status = db.Column(db.String(50), default='created')  # created, running, completed, failed
    
    # Relationships
    predictions = db.relationship('Prediction', back_populates='experiment_run', cascade='all, delete-orphan')
    evaluations = db.relationship('ExperimentEvaluation', back_populates='experiment_run', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<ExperimentRun {self.id}: {self.name}>"


class Prediction(db.Model):
    """Model for storing predictions generated under experimental conditions."""
    
    __tablename__ = 'experiment_predictions'
    
    id = db.Column(db.Integer, primary_key=True)
    experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    condition = db.Column(db.String(50), nullable=False)  # 'baseline' or 'proethica'
    prediction_text = db.Column(db.Text)
    reasoning = db.Column(db.Text)
    prompt = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    meta_data = db.Column(JSON)  # Additional metadata (e.g., concepts used)
    
    # Relationships
    experiment_run = db.relationship('ExperimentRun', back_populates='predictions')
    document = db.relationship('Document', backref=db.backref('predictions', cascade='all, delete-orphan'))
    evaluations = db.relationship('ExperimentEvaluation', back_populates='prediction', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<Prediction {self.id}: {self.condition} for document {self.document_id}>"


class ExperimentEvaluation(db.Model):
    """Model for storing reviewer feedback on predictions."""
    
    __tablename__ = 'experiment_evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    experiment_run_id = db.Column(db.Integer, db.ForeignKey('experiment_runs.id'), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey('experiment_predictions.id'), nullable=False)
    evaluator_id = db.Column(db.String(255))  # Could be a user ID or anonymous identifier
    
    # Core evaluation metrics
    reasoning_quality = db.Column(db.Float)  # 0-10 scale
    persuasiveness = db.Column(db.Float)  # 0-10 scale
    coherence = db.Column(db.Float)  # 0-10 scale
    accuracy = db.Column(db.Boolean)  # Does it match the original NSPE conclusion?
    agreement = db.Column(db.Boolean)  # Does it agree with original conclusion?
    support_quality = db.Column(db.Float)  # 0-10 scale
    
    # Additional metrics
    preference_score = db.Column(db.Float)  # 0-10 scale
    alignment_score = db.Column(db.Float)  # 0-10 scale
    
    # Comments
    comments = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Metadata
    meta_data = db.Column(JSON)  # Additional metadata
    
    # Relationships
    experiment_run = db.relationship('ExperimentRun', back_populates='evaluations')
    prediction = db.relationship('Prediction', back_populates='evaluations')
    
    def __repr__(self):
        return f"<Evaluation {self.id} by {self.evaluator_id} for prediction {self.prediction_id}>"
