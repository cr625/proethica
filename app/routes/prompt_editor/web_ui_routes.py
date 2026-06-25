"""HTML editor views: redirect landing page, case-template editor, guideline-template editor. Renders tools/prompt_editor_*.html.."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required
from sqlalchemy import func

from app.models import db
from app.models.extraction_prompt_template import (
    ExtractionPromptTemplate, ExtractionPromptTemplateVersion,
    PIPELINE_STEPS, CONCEPT_COLORS, CONCEPT_SOURCE_FILES, STEP4_PHASES,
    GUIDELINE_PIPELINE_STEPS, GUIDELINE_CONCEPTS
)
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage

import logging

logger = logging.getLogger(__name__)


def register_web_ui(bp):
    @bp.route('/tools/prompts')
    @login_required
    def index():
        """Redirect to the prompt editor - uses localStorage to restore last viewed template."""
        # This renders a minimal page that checks localStorage for the last viewed template
        # and redirects appropriately. Default is step 1 roles.
        return render_template('tools/prompt_editor_redirect.html')


    @bp.route('/tools/prompts/<int:step>/<concept>')
    @login_required
    def edit_template(step, concept):
        """Edit a specific template."""
        # Get domain from query params
        selected_domain = request.args.get('domain', 'engineering')

        # Get available domains - handle case where table might be empty
        try:
            domains = db.session.query(ExtractionPromptTemplate.domain).distinct().all()
            available_domains = sorted(set(d[0] for d in domains if d[0])) or ['engineering']
        except Exception as e:
            logger.warning(f"Could not get domains: {e}")
            available_domains = ['engineering']

        # Get the template for this domain (case extraction only)
        template = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case',
            step_number=step,
            concept_type=concept,
            domain=selected_domain,
            is_active=True
        ).first()

        if not template:
            # Try to find any template for this concept in this domain
            template = ExtractionPromptTemplate.query.filter_by(
                extraction_type='case',
                concept_type=concept,
                domain=selected_domain,
                is_active=True
            ).first()

        if not template:
            # Fall back to any domain
            template = ExtractionPromptTemplate.query.filter_by(
                extraction_type='case',
                concept_type=concept,
                is_active=True
            ).first()

        # Get step info
        step_info = next((s for s in PIPELINE_STEPS if s['step'] == step), None)

        # Get cases that have extraction prompts for this concept
        try:
            cases_with_extractions = db.session.query(
                Document.id,
                Document.title,
                func.count(ExtractionPrompt.id).label('extraction_count'),
                func.max(ExtractionPrompt.created_at).label('last_extraction')
            ).join(
                ExtractionPrompt, ExtractionPrompt.case_id == Document.id
            ).filter(
                ExtractionPrompt.concept_type == concept
            ).group_by(
                Document.id, Document.title
            ).order_by(
                func.max(ExtractionPrompt.created_at).desc()
            ).limit(20).all()
        except Exception as e:
            logger.warning(f"Could not get cases with extractions: {e}")
            cases_with_extractions = []

        # Get version history
        versions = []
        if template:
            versions = ExtractionPromptTemplateVersion.query.filter_by(
                template_id=template.id
            ).order_by(
                ExtractionPromptTemplateVersion.version_number.desc()
            ).limit(10).all()

        # Build the JSON wrapper suffix for display in the reference panel
        from app.services.extraction.unified_dual_extractor import build_json_wrapper_suffix
        json_wrapper_suffix = build_json_wrapper_suffix(concept) if template else ''

        # Recipe scaffold (Phase 1): the component's extraction as an ordered list of typed steps.
        # Read-only for now; this prompt is the llm-prompt step in the sequence.
        from app.services.extraction.recipe import recipe_for_concept
        recipe = recipe_for_concept(concept)

        return render_template('tools/prompt_editor_detail.html',
                              recipe=recipe,
                              template=template,
                              step=step,
                              concept=concept,
                              step_info=step_info,
                              concept_color=CONCEPT_COLORS.get(concept, '#6c757d'),
                              cases_with_extractions=cases_with_extractions,
                              versions=versions,
                              pipeline_steps=PIPELINE_STEPS,
                              concept_colors=CONCEPT_COLORS,
                              available_domains=available_domains,
                              selected_domain=selected_domain,
                              json_wrapper_suffix=json_wrapper_suffix)
    @bp.route('/tools/prompts/guidelines/<concept>')
    @login_required
    def edit_guideline_template(concept):
        """Edit a guideline extraction template."""
        # Get domain from query params
        selected_domain = request.args.get('domain', 'engineering')

        # Get available domains
        try:
            domains = db.session.query(ExtractionPromptTemplate.domain).filter_by(
                extraction_type='guideline'
            ).distinct().all()
            available_domains = sorted(set(d[0] for d in domains if d[0])) or ['engineering']
        except Exception as e:
            logger.warning(f"Could not get guideline domains: {e}")
            available_domains = ['engineering']

        # Get the guideline template
        template = ExtractionPromptTemplate.query.filter_by(
            extraction_type='guideline',
            step_number=0,
            concept_type=concept,
            domain=selected_domain,
            is_active=True
        ).first()

        if not template:
            # Fall back to any domain
            template = ExtractionPromptTemplate.query.filter_by(
                extraction_type='guideline',
                concept_type=concept,
                is_active=True
            ).first()

        # Get concept info from GUIDELINE_CONCEPTS
        concept_info = GUIDELINE_CONCEPTS.get(concept, {
            'name': concept.replace('_', ' ').title(),
            'description': '',
            'color': '#f97316'
        })

        # Get version history
        versions = []
        if template:
            versions = ExtractionPromptTemplateVersion.query.filter_by(
                template_id=template.id
            ).order_by(
                ExtractionPromptTemplateVersion.version_number.desc()
            ).limit(10).all()

        return render_template('tools/prompt_editor_guideline.html',
                              template=template,
                              concept=concept,
                              concept_info=concept_info,
                              concept_color=concept_info.get('color', '#f97316'),
                              versions=versions,
                              guideline_steps=GUIDELINE_PIPELINE_STEPS,
                              guideline_concepts=GUIDELINE_CONCEPTS,
                              available_domains=available_domains,
                              selected_domain=selected_domain)
