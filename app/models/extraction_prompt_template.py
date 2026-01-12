"""
Model for extraction prompt templates.

Stores editable templates for the 9-component extraction pipeline,
allowing prompt editing through the web UI.
"""

from datetime import datetime
from jinja2 import Template
from app.models import db


class ExtractionPromptTemplate(db.Model):
    """Editable prompt template for extraction pipeline."""

    __tablename__ = 'extraction_prompt_templates'

    id = db.Column(db.Integer, primary_key=True)

    # Pipeline position
    step_number = db.Column(db.Integer, nullable=False)  # 1, 2, or 3
    concept_type = db.Column(db.String(50), nullable=False)  # roles, states, etc.
    pass_type = db.Column(db.String(20), default='all')  # facts, discussion, all

    # Template content
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    template_text = db.Column(db.Text, nullable=False)

    # Variables schema
    variables_schema = db.Column(db.JSON)

    # Versioning
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)

    # Metadata
    source_file = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.String(100))

    # Extractor metadata (added 2026-01-10)
    extractor_file = db.Column(db.String(200))  # Source Python file path
    prompt_method = db.Column(db.String(100))   # Method name that builds the prompt
    variable_builders = db.Column(db.JSON)      # Maps variables to builder methods
    output_schema = db.Column(db.JSON)          # Expected output dataclasses and fields
    domain = db.Column(db.String(50), default='engineering')  # Domain variant

    # Relationships
    versions = db.relationship('ExtractionPromptTemplateVersion', back_populates='template',
                               lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('step_number', 'concept_type', 'pass_type', 'version',
                           name='uq_template_step_concept_pass_version'),
        db.Index('idx_ept_active', 'step_number', 'concept_type', 'is_active'),
        db.Index('idx_ept_concept_active', 'concept_type', 'is_active'),
    )

    def __repr__(self):
        return f'<ExtractionPromptTemplate step={self.step_number} concept={self.concept_type} v{self.version}>'

    @classmethod
    def get_active_template(cls, step_number: int, concept_type: str, pass_type: str = None):
        """Get the active template for a given step and concept type.

        Args:
            step_number: Pipeline step (1, 2, or 3)
            concept_type: Concept type (roles, states, etc.)
            pass_type: Optional pass type filter (facts, discussion)

        Returns:
            Active ExtractionPromptTemplate or None
        """
        query = cls.query.filter_by(
            step_number=step_number,
            concept_type=concept_type,
            is_active=True
        )

        # Try specific pass_type first, then 'all'
        if pass_type and pass_type != 'all':
            template = query.filter_by(pass_type=pass_type).first()
            if template:
                return template

        # Fall back to 'all' pass type
        return query.filter_by(pass_type='all').first()

    @classmethod
    def get_all_templates(cls):
        """Get all active templates organized by step."""
        templates = cls.query.filter_by(is_active=True).order_by(
            cls.step_number, cls.concept_type
        ).all()

        return templates

    def render(self, **variables) -> str:
        """Render the template with provided variables.

        Args:
            **variables: Variables to substitute in the template

        Returns:
            Rendered prompt string
        """
        try:
            jinja_template = Template(self.template_text)
            return jinja_template.render(**variables)
        except Exception as e:
            # Return template with error comment if rendering fails
            return f"<!-- Template render error: {e} -->\n{self.template_text}"

    def save_new_version(self, new_text: str, change_description: str = None,
                         changed_by: str = 'web_editor') -> 'ExtractionPromptTemplate':
        """Save a new version of this template.

        Creates a version history record and updates the template.

        Args:
            new_text: The new template text
            change_description: Description of what changed
            changed_by: Who made the change

        Returns:
            Updated template
        """
        # Create version history record
        version_record = ExtractionPromptTemplateVersion(
            template_id=self.id,
            version_number=self.version,
            template_text=self.template_text,
            variables_schema=self.variables_schema,
            change_description=change_description,
            changed_by=changed_by
        )
        db.session.add(version_record)

        # Update template
        self.template_text = new_text
        self.version += 1
        self.updated_at = datetime.utcnow()

        db.session.commit()
        return self

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'step_number': self.step_number,
            'concept_type': self.concept_type,
            'pass_type': self.pass_type,
            'name': self.name,
            'description': self.description,
            'template_text': self.template_text,
            'variables_schema': self.variables_schema,
            'version': self.version,
            'is_active': self.is_active,
            'source_file': self.source_file,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by,
            # Extractor metadata
            'extractor_file': self.extractor_file,
            'prompt_method': self.prompt_method,
            'variable_builders': self.variable_builders,
            'output_schema': self.output_schema,
            'domain': self.domain
        }

    def get_template_variables(self) -> list:
        """Extract variable names from the Jinja2 template.

        Returns:
            List of variable names found in {{ variable }} placeholders
        """
        import re
        # Match {{ variable_name }} patterns, handling whitespace
        pattern = r'\{\{\s*(\w+)\s*\}\}'
        return list(set(re.findall(pattern, self.template_text)))

    def to_langchain_prompt(self):
        """Convert to LangChain PromptTemplate format.

        Converts Jinja2 {{ variable }} syntax to LangChain { variable } syntax
        and returns a LangChain PromptTemplate object.

        Returns:
            langchain_core.prompts.PromptTemplate instance
        """
        import re
        from langchain_core.prompts import PromptTemplate

        # Convert Jinja2 {{ var }} to LangChain { var }
        langchain_text = re.sub(r'\{\{\s*(\w+)\s*\}\}', r'{\1}', self.template_text)

        # Extract variable names from converted template
        variables = list(set(re.findall(r'\{(\w+)\}', langchain_text)))

        return PromptTemplate(
            template=langchain_text,
            input_variables=variables,
            metadata={
                'proethica_template_id': self.id,
                'version': self.version,
                'concept_type': self.concept_type,
                'step_number': self.step_number
            }
        )

    def to_langchain_chat_prompt(self):
        """Convert to LangChain ChatPromptTemplate format.

        For use with chat models. Creates a system message with the prompt.

        Returns:
            langchain_core.prompts.ChatPromptTemplate instance
        """
        import re
        from langchain_core.prompts import ChatPromptTemplate

        # Convert Jinja2 {{ var }} to LangChain { var }
        langchain_text = re.sub(r'\{\{\s*(\w+)\s*\}\}', r'{\1}', self.template_text)

        return ChatPromptTemplate.from_messages([
            ("system", langchain_text)
        ])


class ExtractionPromptTemplateVersion(db.Model):
    """Version history for extraction prompt templates."""

    __tablename__ = 'extraction_prompt_template_versions'

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('extraction_prompt_templates.id',
                                                       ondelete='CASCADE'), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    template_text = db.Column(db.Text, nullable=False)
    variables_schema = db.Column(db.JSON)
    change_description = db.Column(db.Text)
    changed_by = db.Column(db.String(100))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    template = db.relationship('ExtractionPromptTemplate', back_populates='versions')

    __table_args__ = (
        db.UniqueConstraint('template_id', 'version_number', name='uq_template_version'),
        db.Index('idx_eptv_template', 'template_id'),
    )

    def __repr__(self):
        return f'<ExtractionPromptTemplateVersion template={self.template_id} v{self.version_number}>'

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'template_id': self.template_id,
            'version_number': self.version_number,
            'template_text': self.template_text,
            'variables_schema': self.variables_schema,
            'change_description': self.change_description,
            'changed_by': self.changed_by,
            'changed_at': self.changed_at.isoformat() if self.changed_at else None
        }


# Pipeline structure constants (matching provenance.py)
PIPELINE_STEPS = [
    {
        'step': 1,
        'name': 'Contextual Framework',
        'color': '#3b82f6',
        'concepts': ['roles', 'states', 'resources']
    },
    {
        'step': 2,
        'name': 'Normative Framework',
        'color': '#8b5cf6',
        'concepts': ['principles', 'obligations', 'constraints', 'capabilities']
    },
    {
        'step': 3,
        'name': 'Temporal Framework',
        'color': '#14b8a6',
        'concepts': ['actions', 'events']
    },
    {
        'step': 4,
        'name': 'Synthesis',
        'color': '#ec4899',
        'concepts': ['provisions', 'questions', 'conclusions', 'transformation', 'rich_analysis', 'decision_synthesis'],
        'read_only': True  # Step 4 prompts are read-only in the editor
    }
]

# Step 4 phase metadata - describes the synthesis phases
STEP4_PHASES = {
    'provisions': {
        'name': 'Provisions',
        'description': 'NSPE code provision detection and entity linking',
        'service_file': 'app/services/provision_group_validator.py',
        'color': '#f97316',
        'prompts': [
            {'name': 'Provision Group Validator', 'method': '_create_validation_prompt'},
            {'name': 'Code Provision Linker', 'method': '_create_linking_prompt', 'file': 'app/services/code_provision_linker.py'}
        ]
    },
    'questions': {
        'name': 'Questions',
        'description': 'Board and analytical question extraction',
        'service_file': 'app/services/question_analyzer.py',
        'color': '#3b82f6',
        'prompts': [
            {'name': 'Board Question Extraction', 'method': '_create_board_extraction_prompt'},
            {'name': 'Analytical Question Generation', 'method': '_create_analytical_prompt'}
        ]
    },
    'conclusions': {
        'name': 'Conclusions',
        'description': 'Board and analytical conclusion extraction with Q-C linking',
        'service_file': 'app/services/conclusion_analyzer.py',
        'color': '#10b981',
        'prompts': [
            {'name': 'Board Conclusion Extraction', 'method': '_create_board_extraction_prompt'},
            {'name': 'Analytical Conclusion Generation', 'method': '_create_analytical_prompt'}
        ]
    },
    'transformation': {
        'name': 'Transformation',
        'description': 'Case transformation type classification',
        'service_file': 'app/services/case_analysis/transformation_classifier.py',
        'color': '#8b5cf6',
        'prompts': [
            {'name': 'Transformation Classification', 'method': 'classify'}
        ]
    },
    'rich_analysis': {
        'name': 'Rich Analysis',
        'description': 'Causal-normative links, question emergence, resolution patterns',
        'service_file': 'app/services/case_synthesizer.py',
        'color': '#06b6d4',
        'prompts': [
            {'name': 'Causal-Normative Analysis', 'method': '_analyze_causal_normative_links'},
            {'name': 'Question Emergence', 'method': '_analyze_question_emergence'},
            {'name': 'Resolution Patterns', 'method': '_analyze_resolution_patterns'}
        ]
    },
    'decision_synthesis': {
        'name': 'Decision Synthesis',
        'description': 'E1-E3 algorithmic composition + LLM refinement with Toulmin structure',
        'service_file': 'app/services/decision_point_synthesizer.py',
        'color': '#ec4899',
        'prompts': [
            {'name': 'Decision Refinement', 'method': '_build_refinement_prompt'}
        ],
        'algorithmic_stages': ['E1: Obligation Coverage', 'E2: Action-Option Mapping', 'E3: Decision Composition', 'Q&C Alignment Scoring']
    }
}

CONCEPT_COLORS = {
    # Steps 1-3 concepts
    'roles': '#0d6efd',
    'states': '#6f42c1',
    'resources': '#20c997',
    'principles': '#fd7e14',
    'obligations': '#dc3545',
    'constraints': '#6c757d',
    'capabilities': '#0dcaf0',
    'actions': '#198754',
    'events': '#ffc107',
    # Step 4 phases
    'provisions': '#f97316',
    'questions': '#3b82f6',
    'conclusions': '#10b981',
    'transformation': '#8b5cf6',
    'rich_analysis': '#06b6d4',
    'decision_synthesis': '#ec4899'
}

CONCEPT_SOURCE_FILES = {
    'roles': 'app/services/extraction/enhanced_prompts_roles_resources.py',
    'resources': 'app/services/extraction/enhanced_prompts_roles_resources.py',
    'states': 'app/services/extraction/enhanced_prompts_states_capabilities.py',
    'capabilities': 'app/services/extraction/enhanced_prompts_states_capabilities.py',
    'principles': 'app/services/extraction/enhanced_prompts_principles.py',
    'obligations': 'app/services/extraction/enhanced_prompts_obligations.py',
    'constraints': 'app/services/extraction/enhanced_prompts_constraints.py',
    'actions': 'app/services/extraction/enhanced_prompts_actions.py',
    'events': 'app/services/extraction/enhanced_prompts_events.py'
}
