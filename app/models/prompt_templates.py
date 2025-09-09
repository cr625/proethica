"""
Database models for the LangExtract prompt builder system.

Provides flexible, database-backed prompt management separate from ontology structure.
"""

from datetime import datetime
from app.models import db


class SectionPromptTemplate(db.Model):
    """
    Template for generating LangExtract prompts for specific section types and domains.
    
    Replaces hardcoded ontology prompts with flexible, manageable database templates.
    """
    __tablename__ = 'section_prompt_templates'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Section identification
    section_type = db.Column(db.String(100), nullable=False, index=True)  # 'FactualSection', 'EthicalQuestionSection'
    ontology_class_uri = db.Column(db.String(500), nullable=False)  # Full URI to ontology class
    domain = db.Column(db.String(50), nullable=False, default='generic', index=True)  # 'generic', 'engineering', 'medical'
    
    # Template details
    name = db.Column(db.String(200), nullable=False)  # Human-readable name
    description = db.Column(db.Text)  # What this template is for
    prompt_template = db.Column(db.Text, nullable=False)  # The actual prompt with variables
    variables = db.Column(db.JSON)  # Template variables and their descriptions
    
    # Configuration
    extraction_targets = db.Column(db.String(500))  # Comma-separated extraction targets
    analysis_priority = db.Column(db.Integer, default=1)  # Processing priority (1-10)
    active = db.Column(db.Boolean, default=True, index=True)  # Whether this template is active
    
    # Metadata
    created_by = db.Column(db.String(100))  # Who created this template
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = db.Column(db.Integer, default=1)  # Template version for tracking changes
    
    # Performance tracking
    usage_count = db.Column(db.Integer, default=0)  # How many times this template was used
    avg_performance_score = db.Column(db.Float)  # Average effectiveness score
    
    # Relationships
    instances = db.relationship('SectionPromptInstance', back_populates='template', lazy='dynamic')
    
    __table_args__ = (
        db.UniqueConstraint('section_type', 'domain', 'name', name='unique_section_domain_name'),
        db.Index('idx_section_domain_active', 'section_type', 'domain', 'active'),
    )
    
    def __repr__(self):
        return f'<SectionPromptTemplate {self.domain}:{self.section_type}:{self.name}>'
    
    def render_prompt(self, **variables):
        """
        Render the prompt template with provided variables.
        
        Args:
            **variables: Variables to substitute in the template
            
        Returns:
            Rendered prompt string
        """
        from jinja2 import Template
        template = Template(self.prompt_template)
        return template.render(**variables)
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'section_type': self.section_type,
            'ontology_class_uri': self.ontology_class_uri,
            'domain': self.domain,
            'name': self.name,
            'description': self.description,
            'prompt_template': self.prompt_template,
            'variables': self.variables,
            'extraction_targets': self.extraction_targets,
            'analysis_priority': self.analysis_priority,
            'active': self.active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'version': self.version,
            'usage_count': self.usage_count,
            'avg_performance_score': self.avg_performance_score
        }


class SectionPromptInstance(db.Model):
    """
    Record of a specific prompt instance used in analysis.
    
    Tracks how templates were used and their effectiveness for continuous improvement.
    """
    __tablename__ = 'section_prompt_instances'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Template reference
    template_id = db.Column(db.Integer, db.ForeignKey('section_prompt_templates.id'), nullable=False)
    template = db.relationship('SectionPromptTemplate', back_populates='instances')
    
    # Usage context
    case_id = db.Column(db.Integer, index=True)  # Which case this was used for
    section_title = db.Column(db.String(200))  # Original section title
    section_content_length = db.Column(db.Integer)  # Length of analyzed content
    
    # Rendered content
    rendered_prompt = db.Column(db.Text, nullable=False)  # Final prompt sent to LangExtract
    variables_used = db.Column(db.JSON)  # Variables that were substituted
    
    # Results and performance
    analysis_successful = db.Column(db.Boolean, default=True)
    performance_score = db.Column(db.Float)  # Effectiveness rating (0.0-1.0)
    processing_time_ms = db.Column(db.Integer)  # How long analysis took
    tokens_used = db.Column(db.Integer)  # API tokens consumed
    
    # Output quality metrics
    concepts_extracted = db.Column(db.Integer)  # Number of concepts found
    output_length = db.Column(db.Integer)  # Length of analysis output
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    user_feedback = db.Column(db.Text)  # Optional user feedback on quality
    
    def __repr__(self):
        return f'<SectionPromptInstance {self.template_id}:{self.case_id}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'template_id': self.template_id,
            'case_id': self.case_id,
            'section_title': self.section_title,
            'rendered_prompt': self.rendered_prompt,
            'variables_used': self.variables_used,
            'analysis_successful': self.analysis_successful,
            'performance_score': self.performance_score,
            'processing_time_ms': self.processing_time_ms,
            'concepts_extracted': self.concepts_extracted,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'user_feedback': self.user_feedback
        }


class PromptTemplateVersion(db.Model):
    """
    Version history for prompt templates to track changes and enable rollback.
    """
    __tablename__ = 'prompt_template_versions'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('section_prompt_templates.id'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    
    # Snapshot of template at this version
    prompt_template = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON)
    extraction_targets = db.Column(db.String(500))
    analysis_priority = db.Column(db.Integer)
    
    # Change tracking
    change_description = db.Column(db.Text)  # What changed in this version
    changed_by = db.Column(db.String(100))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Performance comparison
    performance_before = db.Column(db.Float)  # Performance of previous version
    performance_after = db.Column(db.Float)  # Performance of this version
    
    __table_args__ = (
        db.UniqueConstraint('template_id', 'version_number', name='unique_template_version'),
    )
    
    def __repr__(self):
        return f'<PromptTemplateVersion {self.template_id}:v{self.version_number}>'