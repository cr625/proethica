from sqlalchemy import JSON
from app.models import db

class Evaluation(db.Model):
    """Evaluation model representing assessments of actions/decisions."""
    __tablename__ = 'evaluations'
    
    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.Integer, db.ForeignKey('actions.id'), nullable=False)  # Changed from decision_id
    rules_compliance = db.Column(db.Float)  # Score for compliance with rules (0-1)
    ethical_score = db.Column(db.Float)  # Score for ethical considerations (0-1)
    reasoning = db.Column(db.Text)  # Explanation of the evaluation
    details = db.Column(JSON)  # Detailed breakdown of the evaluation
    
    def __repr__(self):
        return f'<Evaluation {self.id} for Action {self.action_id}>'
    
    def to_dict(self):
        """Convert evaluation to dictionary."""
        return {
            'id': self.id,
            'action_id': self.action_id,
            'rules_compliance': self.rules_compliance,
            'ethical_score': self.ethical_score,
            'reasoning': self.reasoning,
            'details': self.details
        }
