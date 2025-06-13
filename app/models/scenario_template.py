"""
Database model for scenario templates.

Scenario templates are generated from deconstructed cases and define
the structure for creating playable scenario instances.
"""

from datetime import datetime
from app.models import db


class ScenarioTemplate(db.Model):
    """Database model for scenario templates."""
    
    __tablename__ = 'scenario_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    deconstructed_case_id = db.Column(db.Integer, db.ForeignKey('deconstructed_cases.id'), nullable=False)
    
    # Basic template information
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    world_id = db.Column(db.Integer, db.ForeignKey('worlds.id'), nullable=True)
    
    # Template configuration data
    template_data = db.Column(db.JSON, nullable=True)  # Rich scenario structure
    
    # Template metadata
    difficulty_level = db.Column(db.String(20), default='intermediate')  # beginner, intermediate, advanced
    estimated_duration = db.Column(db.Integer, default=30)  # minutes
    complexity_score = db.Column(db.Float, default=0.5)  # 0.0 to 1.0
    
    # Version and validation
    template_version = db.Column(db.String(20), default="1.0")
    is_validated = db.Column(db.Boolean, default=False)
    validation_notes = db.Column(db.Text, nullable=True)
    
    # Usage statistics
    usage_count = db.Column(db.Integer, default=0)
    average_rating = db.Column(db.Float, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    deconstructed_case = db.relationship('DeconstructedCase', backref='scenario_templates')
    world = db.relationship('World', backref='scenario_templates')
    
    def __repr__(self):
        return f'<ScenarioTemplate {self.id}: {self.title}>'
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'deconstructed_case_id': self.deconstructed_case_id,
            'title': self.title,
            'description': self.description,
            'world_id': self.world_id,
            'template_data': self.template_data,
            'difficulty_level': self.difficulty_level,
            'estimated_duration': self.estimated_duration,
            'complexity_score': self.complexity_score,
            'template_version': self.template_version,
            'is_validated': self.is_validated,
            'usage_count': self.usage_count,
            'average_rating': self.average_rating,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
    
    @property
    def characters_count(self):
        """Get the number of characters in this template."""
        if self.template_data and 'characters' in self.template_data:
            return len(self.template_data['characters'])
        return 0
    
    @property
    def decision_points_count(self):
        """Get the number of decision points in this template."""
        if self.template_data and 'decision_tree' in self.template_data:
            nodes = self.template_data['decision_tree'].get('nodes', {})
            return len([n for n in nodes.values() if n.get('type') == 'decision'])
        return 0
    
    @property
    def learning_objectives_count(self):
        """Get the number of learning objectives in this template."""
        if self.template_data and 'learning_framework' in self.template_data:
            objectives = self.template_data['learning_framework'].get('primary_objectives', [])
            return len(objectives)
        return 0