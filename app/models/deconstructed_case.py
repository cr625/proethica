"""
Database models for storing case deconstruction results.
"""

from datetime import datetime
from app.models import db


class DeconstructedCase(db.Model):
    """Database model for storing case deconstruction results."""
    
    __tablename__ = 'deconstructed_cases'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    adapter_type = db.Column(db.String(50), nullable=False)  # 'engineering_ethics', 'medical_ethics', etc.
    
    # JSON fields for storing complex data structures
    stakeholders = db.Column(db.JSON, nullable=True)
    decision_points = db.Column(db.JSON, nullable=True)
    reasoning_chain = db.Column(db.JSON, nullable=True)
    
    # Confidence scores
    stakeholder_confidence = db.Column(db.Float, default=0.0)
    decision_points_confidence = db.Column(db.Float, default=0.0)
    reasoning_confidence = db.Column(db.Float, default=0.0)
    
    # Validation and metadata
    human_validated = db.Column(db.Boolean, default=False)
    validation_notes = db.Column(db.Text, nullable=True)
    adapter_version = db.Column(db.String(20), default="1.0")
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = db.relationship('Document', backref='deconstructed_cases')
    
    def __repr__(self):
        return f'<DeconstructedCase {self.id}: Case {self.case_id} ({self.adapter_type})>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'adapter_type': self.adapter_type,
            'stakeholders': self.stakeholders,
            'decision_points': self.decision_points,
            'reasoning_chain': self.reasoning_chain,
            'stakeholder_confidence': self.stakeholder_confidence,
            'decision_points_confidence': self.decision_points_confidence,
            'reasoning_confidence': self.reasoning_confidence,
            'human_validated': self.human_validated,
            'validation_notes': self.validation_notes,
            'adapter_version': self.adapter_version,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_data_model(cls, deconstructed_case_data, case_id):
        """Create database model from data model."""
        analysis = deconstructed_case_data.analysis
        
        return cls(
            case_id=case_id,
            adapter_type=deconstructed_case_data.adapter_type,
            stakeholders=[s.to_dict() for s in analysis.stakeholders],
            decision_points=[dp.to_dict() for dp in analysis.decision_points],
            reasoning_chain=analysis.reasoning_chain.to_dict() if analysis.reasoning_chain else None,
            stakeholder_confidence=analysis.stakeholder_confidence,
            decision_points_confidence=analysis.decision_points_confidence,
            reasoning_confidence=analysis.reasoning_confidence,
            human_validated=deconstructed_case_data.human_validated,
            validation_notes=deconstructed_case_data.validation_notes,
            adapter_version=analysis.adapter_version
        )


