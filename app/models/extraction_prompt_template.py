"""
Model for extraction prompt templates.

Stores editable templates for the 9-component extraction pipeline,
allowing prompt editing through the web UI.
"""

from datetime import datetime
from jinja2 import Template
from app.models import db
from app.concept_meta import CONCEPT_COLORS as _BASE_CONCEPT_COLORS


class ExtractionPromptTemplate(db.Model):
    """Editable prompt template for extraction pipeline."""

    __tablename__ = 'extraction_prompt_templates'

    id = db.Column(db.Integer, primary_key=True)

    # Extraction type - distinguishes case extraction from guideline extraction
    extraction_type = db.Column(db.String(20), default='case', nullable=False)  # 'case' or 'guideline'

    # Pipeline position
    step_number = db.Column(db.Integer, nullable=False)  # 1, 2, or 3 (case); 0 for guidelines
    concept_type = db.Column(db.String(50), nullable=False)  # roles, states, etc. (case); provision_extraction, etc. (guideline)
    pass_type = db.Column(db.String(20), default='all')  # facts, discussion, all

    # Template content
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    template_text = db.Column(db.Text, nullable=False)
    system_prompt = db.Column(db.Text)  # optional LLM system message (rendered with the same variables)

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
        db.UniqueConstraint('extraction_type', 'step_number', 'concept_type', 'pass_type', 'version',
                           name='uq_template_type_step_concept_pass_version'),
        db.Index('idx_ept_active', 'extraction_type', 'step_number', 'concept_type', 'is_active'),
        db.Index('idx_ept_concept_active', 'extraction_type', 'concept_type', 'is_active'),
        db.Index('idx_ept_type', 'extraction_type'),
    )

    def __repr__(self):
        return f'<ExtractionPromptTemplate step={self.step_number} concept={self.concept_type} v{self.version}>'

    @classmethod
    def get_active_template(cls, step_number: int, concept_type: str, pass_type: str = None,
                           extraction_type: str = 'case'):
        """Get the active template for a given step and concept type.

        Args:
            step_number: Pipeline step (1, 2, or 3 for case; 0 for guidelines)
            concept_type: Concept type (roles, states, etc.)
            pass_type: Optional pass type filter (facts, discussion)
            extraction_type: 'case' or 'guideline'

        Returns:
            Active ExtractionPromptTemplate or None
        """
        query = cls.query.filter_by(
            extraction_type=extraction_type,
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
    def get_all_templates(cls, extraction_type: str = None):
        """Get all active templates organized by step.

        Args:
            extraction_type: Filter by 'case' or 'guideline'. If None, returns all.

        Returns:
            List of active ExtractionPromptTemplate instances
        """
        query = cls.query.filter_by(is_active=True)
        if extraction_type:
            query = query.filter_by(extraction_type=extraction_type)

        templates = query.order_by(
            cls.extraction_type, cls.step_number, cls.concept_type
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

    def render_system(self, **variables) -> str:
        """Render the optional system prompt with the same variables (empty string if none)."""
        if not self.system_prompt:
            return ''
        try:
            return Template(self.system_prompt).render(**variables)
        except Exception as e:
            return f"<!-- System render error: {e} -->\n{self.system_prompt}"

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
            'extraction_type': self.extraction_type,
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
        # Phase keys into STEP4_PHASES (the step-4 nav links to view_step4_phase);
        # each phase's prompts are editable DB templates since the 2026-07-11 migration.
        'concepts': ['provisions', 'precedents', 'questions', 'conclusions', 'transformation',
                     'rich_analysis', 'decision_synthesis', 'narrative'],
    }
]

# Prompt-building pipeline in the prompt-editor left nav: the LLM PROMPTS a component's extraction
# uses. This represents the prompt-building pipeline (the sequence of LLM prompts), NOT the full
# extraction recipe -- non-LLM steps (canonicalize, commit, conform-repair) do not belong on a prompt
# editor. A component's own DB template (the concept link itself) is its MAIN extraction prompt.
#
# SHARED_PROMPTS are the cross-cutting LLM prompts that are NOT a single component's main extraction:
# the entity-cleanup passes (filter/split/merge) that run for every component, the upstream
# preprocessing, and the DOWNSTREAM edge/synthesis passes that run after components are extracted.
# They are grouped ONCE in a "Shared" left-nav section (organized by `phase`) -- editing one affects
# every component. COMPONENT_PROMPTS holds any component-SPECIFIC additional prompts, shown as
# sub-items under that component (none yet: Role's extras are all shared). `editable` = already a DB
# template; otherwise the prompt is still hardcoded in `source` and is a candidate to migrate.
SHARED_PROMPTS = [
    {'key': 'discussion_segmenter', 'label': 'Discussion segmenter', 'phase': 'Preprocessing',
     'editable': True, 'step': 0, 'concept': 'discussion_segmenter', 'source': 'discussion_segmenter.py',
     'note': 'Split the discussion into present-case analysis vs cited-precedent recaps'},
    {'key': 'individual_filter', 'label': 'Individual / type filter', 'phase': 'Entity passes',
     'editable': True, 'step': 0, 'concept': 'individual_filter', 'source': 'individual_type_filter.py',
     'note': 'Classify each extracted item as an individual vs a type'},
    {'key': 'splitter', 'label': 'Concept splitter', 'phase': 'Entity passes',
     'editable': True, 'step': 0, 'concept': 'concept_splitter', 'source': 'concept_splitter.py',
     'note': 'Decompose compound labels into atomic concepts'},
    {'key': 'merge_pair_eval', 'label': 'Reconciliation (pair-merge)', 'phase': 'Entity passes',
     'editable': True, 'step': 0, 'concept': 'merge_pair_eval', 'source': 'entity_reconciliation_service.py',
     'note': 'Haiku per-pair duplicate judge (merge vs keep_separate)'},
    {'key': 'merge_canonicalize', 'label': 'Canonicalization (de-compounding)', 'phase': 'Entity passes',
     'editable': True, 'step': 0, 'concept': 'merge_canonicalize', 'source': 'entity_reconciliation_service.py',
     'note': 'Reuse / generalize / keep each class label; injects the canonical reference sheet'},
    {'key': 'rpo_edges', 'label': 'R->P->O edges', 'phase': 'Ontology edges',
     'editable': True, 'step': 0, 'concept': 'rpo_edges', 'source': 'rpo_edges.py',
     'note': 'Role -> Principle -> Obligation dependency edges (axioms injected from the ontology)'},
    {'key': 'defeasibility_edges', 'label': 'Defeasibility edges', 'phase': 'Ontology edges',
     'editable': True, 'step': 0, 'concept': 'defeasibility_edges', 'source': 'defeasibility_edges.py',
     'note': 'Obligation competition: competesWith / prevailsOver / defeasibleUnder (axioms from proethica-core.ttl)'},
    {'key': 'temporal_sequence', 'label': 'Temporal sequence', 'phase': 'Synthesis & enrichment',
     'editable': True, 'step': 0, 'concept': 'temporal_sequence', 'source': 'temporal_sequence.py',
     'note': 'Action / Event temporal ordering edges (Step 3)'},
    {'key': 'obligation_engagement', 'label': 'Obligation engagement', 'phase': 'Synthesis & enrichment',
     'editable': True, 'step': 0, 'concept': 'obligation_engagement', 'source': 'obligation_engagement.py',
     'note': 'Re-classify how obligations are engaged'},
    {'key': 'board_conclusions', 'label': 'Board conclusions', 'phase': 'Synthesis & enrichment',
     'editable': True, 'step': 0, 'concept': 'board_conclusions', 'source': 'board_conclusions.py',
     'note': 'Board-conclusion gap-fill (Step 4 synthesis)'},
]

COMPONENT_PROMPTS = {}  # component-specific additional prompts (none yet; main prompt = the concept link)

# Guidelines extraction pipeline (separate from case extraction)
GUIDELINE_PIPELINE_STEPS = [
    {
        'step': 0,
        'name': 'Provision Extraction',
        'color': '#f97316',  # Orange
        'concepts': ['provision_structure', 'provision_concepts', 'provision_linkage']
    }
]

# Guideline extraction concept metadata
GUIDELINE_CONCEPTS = {
    'provision_structure': {
        'name': 'Provision Structure',
        'description': 'Extract hierarchical provision structure (canons, rules, sections)',
        'service_file': 'app/services/guideline/guideline_structure_annotation_step.py',
        'color': '#f97316'
    },
    'provision_concepts': {
        'name': 'Provision Concepts',
        'description': 'Identify principles, obligations, and constraints each provision establishes',
        'service_file': 'app/services/guideline/guideline_concept_integration_service.py',
        'color': '#fd7e14'
    },
    'provision_linkage': {
        'name': 'Provision Linkage',
        'description': 'Link provisions to ontology entities (Principles, Obligations, Constraints)',
        'service_file': 'app/services/guideline_concept_type_mapper.py',
        'color': '#ea580c'
    }
}

# Step 4 phase metadata - describes the synthesis phases. Each prompt entry's
# 'template' is its editable DB template (step_number=4 row, seeded from
# app/utils/prompts/step4/<template>.md); 'method' remains the builder that
# assembles the variables and renders it (source view).
STEP4_PHASES = {
    'provisions': {
        'name': 'Provisions',
        'description': 'NSPE code provision detection and entity linking',
        'service_file': 'app/services/provision/provision_group_validator.py',
        'color': '#f97316',
        'prompts': [
            {'name': 'Provision Group Validator', 'method': '_create_validation_prompt',
             'template': 'step4_provision_validate'},
            {'name': 'Code Provision Linker', 'method': '_create_batch_linking_prompt',
             'file': 'app/services/provision/code_provision_linker.py',
             'template': 'step4_provision_link'}
        ]
    },
    'precedents': {
        'name': 'Precedents',
        'description': 'Cited-precedent extraction with citation-treatment classification',
        'service_file': 'app/routes/scenario_pipeline/step4/precedents.py',
        'color': '#eab308',
        'prompts': [
            {'name': 'Precedent Extraction', 'method': 'build_precedent_prompt',
             'template': 'step4_precedents'}
        ]
    },
    'questions': {
        'name': 'Questions',
        'description': 'Board and analytical question extraction',
        'service_file': 'app/services/step4_synthesis/question_analyzer.py',
        'color': '#3b82f6',
        'prompts': [
            {'name': 'Board Question Extraction', 'method': '_create_board_extraction_prompt',
             'template': 'step4_q_board'},
            {'name': 'Analytical Question Generation', 'method': '_create_analytical_prompt',
             'template': 'step4_q_analytical'}
        ]
    },
    'conclusions': {
        'name': 'Conclusions',
        'description': 'Board and analytical conclusion extraction with Q-C linking',
        'service_file': 'app/services/step4_synthesis/conclusion_analyzer.py',
        'color': '#10b981',
        'prompts': [
            {'name': 'Board Conclusion Extraction', 'method': '_create_board_extraction_prompt',
             'template': 'step4_c_board'},
            {'name': 'Analytical Conclusion Generation', 'method': '_create_analytical_prompt',
             'template': 'step4_c_analytical'},
            {'name': 'Question-Conclusion Linking', 'method': '_create_linking_prompt',
             'file': 'app/services/step4_synthesis/question_conclusion_linker.py',
             'template': 'step4_qc_link'}
        ]
    },
    'transformation': {
        'name': 'Transformation',
        'description': 'Case transformation type classification',
        'service_file': 'app/services/case_analysis/transformation_classifier.py',
        'color': '#8b5cf6',
        'prompts': [
            {'name': 'Transformation Classification', 'method': 'classify',
             'template': 'step4_transformation'}
        ]
    },
    'rich_analysis': {
        'name': 'Rich Analysis',
        'description': 'Causal-normative links, question emergence, resolution patterns',
        'service_file': 'app/services/step4_synthesis/rich_analysis.py',
        'color': '#06b6d4',
        'prompts': [
            {'name': 'Causal-Normative Analysis', 'method': '_analyze_causal_normative_links',
             'template': 'step4_causal_reasoning'},
            {'name': 'Question Emergence', 'method': '_analyze_question_emergence',
             'template': 'step4_question_emergence'},
            {'name': 'Resolution Patterns', 'method': '_analyze_resolution_patterns',
             'template': 'step4_resolution_patterns'}
        ]
    },
    'decision_synthesis': {
        'name': 'Decision Synthesis',
        'description': 'E1-E3 algorithmic composition + LLM refinement with Toulmin structure',
        'service_file': 'app/services/decision_point_synthesizer/strategies.py',
        'color': '#ec4899',
        'prompts': [
            {'name': 'DP from Causal Links (fallback)', 'method': '_llm_generate_from_causal_links',
             'template': 'step4_dp_causal'},
            {'name': 'DP from Q&C Direct (last resort)', 'method': '_llm_generate_from_qc_direct',
             'template': 'step4_dp_qc_direct'},
            {'name': 'Decision Refinement', 'method': '_build_refinement_prompt',
             'template': 'step4_dp_refine'},
            {'name': 'Board Choice Verification', 'method': 'verify_board_choices',
             'file': 'app/services/decision_point_synthesizer/board_choice_verifier.py',
             'template': 'step4_dp_board_verify'},
            {'name': 'Obligation Decision-Relevance (E1 fallback)', 'method': '_llm_identify_decision_relevant',
             'file': 'app/services/entity_analysis/obligation_coverage_analyzer.py',
             'template': 'step4_obligation_relevance'}
        ],
        'algorithmic_stages': ['E1: Obligation Coverage', 'E2: Action-Option Mapping', 'E3: Decision Composition', 'Q&C Alignment Scoring']
    },
    'narrative': {
        'name': 'Narrative',
        'description': 'Phase-4 narrative construction: characters, tensions, timeline, options, insights',
        'service_file': 'app/services/narrative/narrative_element_extractor.py',
        'color': '#64748b',
        'prompts': [
            {'name': 'Character Enhancement', 'method': '_enhance_characters_with_llm',
             'template': 'step4_narrative_characters'},
            {'name': 'Ethical Tension Rating', 'method': '_enhance_tensions_with_llm',
             'template': 'step4_narrative_tensions'},
            {'name': 'Timeline Enhancement', 'method': '_enhance_timeline_with_llm',
             'file': 'app/services/narrative/timeline_constructor.py',
             'template': 'step4_narrative_timeline'},
            {'name': 'Option Label', 'method': '_generate_option_label_llm',
             'file': 'app/services/narrative/scenario_seed_generator.py',
             'template': 'step4_narrative_option_label'},
            {'name': 'Option Set', 'method': '_generate_options_llm',
             'file': 'app/services/narrative/scenario_seed_generator.py',
             'template': 'step4_narrative_option_set'},
            {'name': 'Opening Context', 'method': '_enhance_opening_with_llm',
             'file': 'app/services/narrative/scenario_seed_generator.py',
             'template': 'step4_narrative_opening'},
            {'name': 'Insights', 'method': '_generate_insights_with_llm',
             'file': 'app/services/narrative/insight_deriver.py',
             'template': 'step4_narrative_insights'},
            {'name': 'Case Summary (alternate surface)', 'method': '_construct_narrative_with_llm',
             'file': 'app/services/case_synthesizer/narrative.py',
             'template': 'step4_case_summary'},
            {'name': 'Timeline Phases (alternate surface)', 'method': '_construct_narrative_with_llm',
             'file': 'app/services/case_synthesizer/narrative.py',
             'template': 'step4_timeline_phases'}
        ]
    }
}

CONCEPT_COLORS = {
    # Steps 1-3 concepts (roles..events) -- single source: app/concept_meta.py
    **_BASE_CONCEPT_COLORS,
    # Step 4 entities - matches docs/concepts/color-scheme.md
    'provisions': '#6c757d',         # Gray (same as Constraints)
    'questions': '#0dcaf0',          # Cyan (same as Capabilities)
    'conclusions': '#198754',        # Green (same as Actions)
    # Step 4 internal phases (not user-facing entity colors)
    'transformation': '#64748b',     # Slate (Step 4 color)
    'rich_analysis': '#64748b',      # Slate (Step 4 color)
    'decision_synthesis': '#64748b'  # Slate (Step 4 color)
}

# Originating seed file per concept. NOTE: the LIVE prompt for case extraction
# is the editable ``extraction_prompt_templates`` DB row (template_text),
# rendered by ``app/services/extraction/unified_dual_extractor.py``. These
# paths point at where each prompt's literature-grounded text originated. The
# states/capabilities/principles/obligations/constraints seed modules were
# archived 2026-05-26 (8d502bfc) and removed 2026-06-11; their content is in
# git history at the recorded paths. The roles/resources seed module
# (enhanced_prompts_roles_resources.py) was removed with the dormant guideline
# extraction subsystem (2026-06; its content is in git history). Actions/events
# never had a seed module (the prior enhanced_prompts_actions/events paths were
# dead).
CONCEPT_SOURCE_FILES = {
    'states': 'app/services/extraction/_archived/enhanced_prompts_states_capabilities.py (removed 2026-06-11; in git history)',
    'capabilities': 'app/services/extraction/_archived/enhanced_prompts_states_capabilities.py (removed 2026-06-11; in git history)',
    'principles': 'app/services/extraction/_archived/enhanced_prompts_principles.py (removed 2026-06-11; in git history)',
    'obligations': 'app/services/extraction/_archived/enhanced_prompts_obligations.py (removed 2026-06-11; in git history)',
    'constraints': 'app/services/extraction/_archived/enhanced_prompts_constraints.py (removed 2026-06-11; in git history)',
    'actions': 'app/services/extraction/unified_dual_extractor.py',
    'events': 'app/services/extraction/unified_dual_extractor.py'
}
