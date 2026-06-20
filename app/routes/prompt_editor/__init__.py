"""Prompt-editor blueprint package -- web UI, template/instance APIs, and step-4 phase routes."""
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

prompt_editor_bp = Blueprint('prompt_editor', __name__)

from app.routes.prompt_editor.web_ui_routes import register_web_ui
from app.routes.prompt_editor.templates_api_routes import register_templates_api
from app.routes.prompt_editor.step4_routes import register_step4

register_web_ui(prompt_editor_bp)
register_templates_api(prompt_editor_bp)
register_step4(prompt_editor_bp)


def init_prompt_editor_csrf_exemption(app):
    """Exempt prompt editor API routes from CSRF protection."""
    if app.csrf:
        for endpoint in (
            'prompt_editor.update_template', 'prompt_editor.preview_template',
            'prompt_editor.revert_template', 'prompt_editor.render_template_with_case',
            'prompt_editor.test_run_template', 'prompt_editor.resolve_template_variables',
            'prompt_editor.update_synthesis_config',
        ):
            view = app.view_functions.get(endpoint)
            if view is not None:
                app.csrf.exempt(view)

__all__ = ["prompt_editor_bp", "init_prompt_editor_csrf_exemption"]
