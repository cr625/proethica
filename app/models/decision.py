from datetime import datetime
from sqlalchemy import JSON
from app import db
from app.models.evaluation import Evaluation

class Decision(db.Model):
    """Decision model representing choices made in scenarios."""
    __tablename__ = 'decisions'
    
    id = db.Column(db.Integer, primary_key=True)
    scenario_id = db.Column(db.Integer, db.ForeignKey('scenarios.id'), nullable=False)
    description = db.Column(db.Text)
    options = db.Column(JSON)  # Available options for this decision
    selected_option = db.Column(db.String(255))  # The option that was selected
    decision_time = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships - kept for backward compatibility during migration
    # evaluations = db.relationship('Evaluation', backref='decision', cascade='all, delete-orphan')
    
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
            # 'evaluations': [evaluation.to_dict() for evaluation in self.evaluations]
        }
