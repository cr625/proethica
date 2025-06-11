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


class ScenarioTemplate(db.Model):
    """Database model for storing scenario templates generated from deconstructed cases."""
    
    __tablename__ = 'scenario_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    case_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=True)
    deconstructed_case_id = db.Column(db.Integer, db.ForeignKey('deconstructed_cases.id'), nullable=False)
    
    # Template configuration
    template_name = db.Column(db.String(255), nullable=False)
    template_description = db.Column(db.Text, nullable=True)
    template_data = db.Column(db.JSON, nullable=True)  # Scenario generation parameters
    
    # Generation metadata
    generation_method = db.Column(db.String(50), default='automatic')  # 'automatic', 'manual', 'hybrid'
    generation_confidence = db.Column(db.Float, default=0.0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    case = db.relationship('Document', backref='scenario_templates')
    scenario = db.relationship('Scenario', backref='templates')
    deconstructed_case = db.relationship('DeconstructedCase', backref='scenario_templates')
    
    def __repr__(self):
        return f'<ScenarioTemplate {self.id}: {self.template_name}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'case_id': self.case_id,
            'scenario_id': self.scenario_id,
            'deconstructed_case_id': self.deconstructed_case_id,
            'template_name': self.template_name,
            'template_description': self.template_description,
            'template_data': self.template_data,
            'generation_method': self.generation_method,
            'generation_confidence': self.generation_confidence,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }