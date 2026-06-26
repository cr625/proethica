"""HTML editor views: redirect landing page, case-template editor, guideline-template editor. Renders tools/prompt_editor_*.html..

The pages are PUBLIC (a read-only Prompt Viewer) so anyone can inspect the extraction prompts to
understand the system. Editing affordances (Save/Test/Revert) are shown only when ``can_edit`` is true;
the write/LLM APIs are independently auth-gated, so the viewer is read-only regardless of the UI."""
from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import current_user
from sqlalchemy import func

from app.models import db
from app.models.extraction_prompt_template import (
    ExtractionPromptTemplate, ExtractionPromptTemplateVersion,
    PIPELINE_STEPS, CONCEPT_COLORS, CONCEPT_SOURCE_FILES, STEP4_PHASES,
    GUIDELINE_PIPELINE_STEPS, GUIDELINE_CONCEPTS, SHARED_PROMPTS, COMPONENT_PROMPTS
)
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.utils.environment_auth import is_production

import logging

logger = logging.getLogger(__name__)


def can_edit_prompts() -> bool:
    """Whether to show the editing UI (Save/Test/Revert) vs the read-only Prompt Viewer.

    Editing is for logged-in admins in production; development stays permissive for any authenticated
    user. Anonymous users get the viewer. This only drives the UI affordances -- the write/LLM API
    routes are independently auth-gated, so an anonymous user cannot mutate anything regardless."""
    return current_user.is_authenticated and (
        getattr(current_user, 'is_admin', False) or not is_production())


def register_web_ui(bp):
    @bp.route('/tools/prompts')
    def index():
        """Redirect to the prompt editor - uses localStorage to restore last viewed template."""
        # This renders a minimal page that checks localStorage for the last viewed template
        # and redirects appropriately. Default is step 1 roles.
        return render_template('tools/prompt_editor_redirect.html')


    @bp.route('/tools/prompts/<int:step>/<concept>')
    def edit_template(step, concept):
        """View (or, for admins, edit) a specific extraction-prompt template."""
        # Get domain from query params
        selected_domain = request.args.get('domain', 'engineering')

        # Get available domains - handle case where table might be empty
        try:
            domains = db.session.query(ExtractionPromptTemplate.domain).distinct().all()
            available_domains = sorted(set(d[0] for d in domains if d[0])) or ['engineering']
        except Exception as e:
            logger.warning(f"Could not get domains: {e}")
            available_domains = ['engineering']

        # Get the template for this domain + pass (case extraction only). A component split into
        # facts/discussion passes has pass-specific rows; prefer the requested pass, else 'all', else facts.
        pass_type = request.args.get('pass')  # 'facts' | 'discussion' | None
        _q = ExtractionPromptTemplate.query.filter_by(
            extraction_type='case',
            step_number=step,
            concept_type=concept,
            domain=selected_domain,
            is_active=True
        )
        template = (_q.filter_by(pass_type=pass_type).first() if pass_type else None) \
            or _q.filter_by(pass_type='all').first() \
            or _q.filter_by(pass_type='facts').first() \
            or _q.first()

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

        # Shared prompts have no case context; the page lets Preview/Test run on a sample instead.
        from app.services.extraction.shared_prompt_samples import is_shared_prompt
        is_shared = is_shared_prompt(concept)

        # Concepts split into facts/discussion passes -> render facts/discussion sub-items in the nav.
        split_concepts = {
            r[0] for r in db.session.query(ExtractionPromptTemplate.concept_type).filter(
                ExtractionPromptTemplate.extraction_type == 'case',
                ExtractionPromptTemplate.pass_type.in_(['facts', 'discussion']),
                ExtractionPromptTemplate.is_active.is_(True)).distinct().all()
        }
        template_pass = template.pass_type if template else (pass_type or 'all')

        return render_template('tools/prompt_editor_detail.html',
                              template=template,
                              can_edit=can_edit_prompts(),
                              template_pass=template_pass,
                              request_pass=pass_type,
                              split_concepts=split_concepts,
                              is_shared_prompt=is_shared,
                              shared_prompts=SHARED_PROMPTS,
                              component_prompts=COMPONENT_PROMPTS,
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
    def edit_guideline_template(concept):
        """View (or, for admins, edit) a guideline extraction template."""
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
                              can_edit=can_edit_prompts(),
                              concept=concept,
                              concept_info=concept_info,
                              concept_color=concept_info.get('color', '#f97316'),
                              versions=versions,
                              guideline_steps=GUIDELINE_PIPELINE_STEPS,
                              guideline_concepts=GUIDELINE_CONCEPTS,
                              available_domains=available_domains,
                              selected_domain=selected_domain)
