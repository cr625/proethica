from datetime import datetime
from app.models import db

class Condition(db.Model):
    """Condition model representing character states or conditions."""
    __tablename__ = 'conditions'
    
    id = db.Column(db.Integer, primary_key=True)
    character_id = db.Column(db.Integer, db.ForeignKey('characters.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)  # Legacy field, kept for backward compatibility
    condition_type_id = db.Column(db.Integer, db.ForeignKey('condition_types.id'))
    description = db.Column(db.Text)
    severity = db.Column(db.Integer)  # Scale of severity (e.g., 1-10)
    start_time = db.Column(db.DateTime, default=datetime.utcnow)
    end_time = db.Column(db.DateTime, nullable=True)  # Null if condition is ongoing
    
    def __repr__(self):
        return f'<Condition {self.name} for Character {self.character_id}>'
    
    def to_dict(self):
        """Convert condition to dictionary."""
        return {
            'id': self.id,
            'character_id': self.character_id,
            'name': self.name,
            'condition_type_id': self.condition_type_id,
            'condition_type_name': self.condition_type.name if self.condition_type else None,
            'condition_type_category': self.condition_type.category if self.condition_type else None,
            'description': self.description,
            'severity': self.severity,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'is_active': self.end_time is None
        }
