from datetime import datetime
from sqlalchemy import JSON
from app import db

class Decision(db.Model):
    """Decision model representing choices made in scenarios."""
    __tablename__ = 'decisions'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    description = db.Column(db.Text)
    options = db.Column(JSON)  # Available options for this decision
    selected_option = db.Column(db.String(255))  # The option that was selected
    decision_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    evaluations = db.relationship('Evaluation', backref='decision', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Decision {self.id} at {self.decision_time}>'
    
    def to_dict(self):
        """Convert decision to dictionary."""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'description': self.description,
            'options': self.options,
            'selected_option': self.selected_option,
            'decision_time': self.decision_time.isoformat() if self.decision_time else None,
            'evaluations': [evaluation.to_dict() for evaluation in self.evaluations]
        }

class Evaluation(db.Model):
    """Evaluation model representing assessments of decisions."""
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    decision_id = db.Column(db.Integer, db.ForeignKey('decisions.id'), nullable=False)
    rules_compliance = db.Column(db.Float)  # Score for compliance with rules (0-1)
    ethical_score = db.Column(db.Float)  # Score for ethical considerations (0-1)
    reasoning = db.Column(db.Text)  # Explanation of the evaluation
    details = db.Column(JSON)  # Detailed breakdown of the evaluation
    
    def __repr__(self):
        return f'<Evaluation {self.id} for Decision {self.decision_id}>'
    
    def to_dict(self):
        """Convert evaluation to dictionary."""
        return {
            'id': self.id,
            'decision_id': self.decision_id,
            'rules_compliance': self.rules_compliance,
            'ethical_score': self.ethical_score,
            'reasoning': self.reasoning,
            'details': self.details
        }
