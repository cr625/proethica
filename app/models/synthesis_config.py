"""
Synthesis configuration model for Step 4 tunable parameters.

Stores configurable parameters for the synthesis pipeline, allowing
adjustment without code changes.
"""

from datetime import datetime
from app.models import db


class SynthesisConfig(db.Model):
    """Configuration parameters for Step 4 synthesis pipeline."""

    __tablename__ = 'synthesis_configs'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)

    # Decision synthesis parameters
    alignment_score_threshold = db.Column(db.Float, default=0.3)
    top_candidates_limit = db.Column(db.Integer, default=8)
    provision_confidence_threshold = db.Column(db.Float, default=0.7)
    skip_algorithmic_fallback = db.Column(db.Boolean, default=False)

    # LLM parameters
    llm_model = db.Column(db.String(100), default='claude-sonnet-4-5-20250929')
    llm_temperature = db.Column(db.Float, default=0.2)
    llm_max_tokens = db.Column(db.Integer, default=4000)

    # Phase control
    enable_provisions = db.Column(db.Boolean, default=True)
    enable_questions = db.Column(db.Boolean, default=True)
    enable_conclusions = db.Column(db.Boolean, default=True)
    enable_transformation = db.Column(db.Boolean, default=True)
    enable_rich_analysis = db.Column(db.Boolean, default=True)
    enable_decision_synthesis = db.Column(db.Boolean, default=True)

    # Metadata
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.String(100))

    def __repr__(self):
        return f'<SynthesisConfig {self.name}>'

    @classmethod
    def get_active(cls) -> 'SynthesisConfig':
        """Get the active configuration, creating default if none exists."""
        config = cls.query.filter_by(is_active=True).first()
        if not config:
            config = cls.create_default()
        return config

    @classmethod
    def create_default(cls) -> 'SynthesisConfig':
        """Create default configuration."""
        config = cls(
            name='default',
            description='Default synthesis configuration',
            is_active=True
        )
        db.session.add(config)
        db.session.commit()
        return config

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            # Decision synthesis
            'alignment_score_threshold': self.alignment_score_threshold,
            'top_candidates_limit': self.top_candidates_limit,
            'provision_confidence_threshold': self.provision_confidence_threshold,
            'skip_algorithmic_fallback': self.skip_algorithmic_fallback,
            # LLM
            'llm_model': self.llm_model,
            'llm_temperature': self.llm_temperature,
            'llm_max_tokens': self.llm_max_tokens,
            # Phase control
            'enable_provisions': self.enable_provisions,
            'enable_questions': self.enable_questions,
            'enable_conclusions': self.enable_conclusions,
            'enable_transformation': self.enable_transformation,
            'enable_rich_analysis': self.enable_rich_analysis,
            'enable_decision_synthesis': self.enable_decision_synthesis,
            # Meta
            'is_active': self.is_active,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'updated_by': self.updated_by
        }

    def update_from_dict(self, data: dict):
        """Update configuration from dictionary."""
        # Decision synthesis params
        if 'alignment_score_threshold' in data:
            self.alignment_score_threshold = float(data['alignment_score_threshold'])
        if 'top_candidates_limit' in data:
            self.top_candidates_limit = int(data['top_candidates_limit'])
        if 'provision_confidence_threshold' in data:
            self.provision_confidence_threshold = float(data['provision_confidence_threshold'])
        if 'skip_algorithmic_fallback' in data:
            self.skip_algorithmic_fallback = bool(data['skip_algorithmic_fallback'])

        # LLM params
        if 'llm_model' in data:
            self.llm_model = data['llm_model']
        if 'llm_temperature' in data:
            self.llm_temperature = float(data['llm_temperature'])
        if 'llm_max_tokens' in data:
            self.llm_max_tokens = int(data['llm_max_tokens'])

        # Phase control
        for phase in ['provisions', 'questions', 'conclusions', 'transformation', 'rich_analysis', 'decision_synthesis']:
            key = f'enable_{phase}'
            if key in data:
                setattr(self, key, bool(data[key]))

        if 'updated_by' in data:
            self.updated_by = data['updated_by']

        self.updated_at = datetime.utcnow()


# Parameter metadata for UI rendering
SYNTHESIS_PARAMETERS = {
    'alignment_score_threshold': {
        'label': 'Alignment Score Threshold',
        'description': 'Minimum Q&C alignment score for decision point candidates (0.0-1.0)',
        'type': 'float',
        'min': 0.0,
        'max': 1.0,
        'step': 0.05,
        'default': 0.3
    },
    'top_candidates_limit': {
        'label': 'Top Candidates Limit',
        'description': 'Maximum number of candidates to refine via LLM',
        'type': 'int',
        'min': 1,
        'max': 20,
        'default': 8
    },
    'provision_confidence_threshold': {
        'label': 'Provision Confidence',
        'description': 'Minimum confidence for provision detection (0.0-1.0)',
        'type': 'float',
        'min': 0.0,
        'max': 1.0,
        'step': 0.05,
        'default': 0.7
    },
    'skip_algorithmic_fallback': {
        'label': 'Skip Algorithmic Fallback',
        'description': 'If true, only use LLM for decision synthesis (no E1-E3 stages)',
        'type': 'bool',
        'default': False
    },
    'llm_model': {
        'label': 'LLM Model',
        'description': 'Model to use for synthesis LLM calls',
        'type': 'select',
        'options': [
            {'value': 'claude-sonnet-4-5-20250929', 'label': 'Sonnet 4.5 (Default)'},
            {'value': 'claude-haiku-4-5-20251022', 'label': 'Haiku 4.5 (Fast)'},
            {'value': 'claude-opus-4-5-20251101', 'label': 'Opus 4.5 (Powerful)'}
        ],
        'default': 'claude-sonnet-4-5-20250929'
    },
    'llm_temperature': {
        'label': 'LLM Temperature',
        'description': 'Temperature for LLM responses (0.0=deterministic, 1.0=creative)',
        'type': 'float',
        'min': 0.0,
        'max': 1.0,
        'step': 0.1,
        'default': 0.2
    },
    'llm_max_tokens': {
        'label': 'Max Tokens',
        'description': 'Maximum tokens for LLM responses',
        'type': 'int',
        'min': 1000,
        'max': 8000,
        'step': 500,
        'default': 4000
    }
}
