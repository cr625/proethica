"""Provenance blueprint package -- QC-audit/review-log APIs, viewer, detail APIs, pipeline view."""
import logging
from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from sqlalchemy import desc, func, text
import json
from datetime import datetime

logger = logging.getLogger(__name__)

from app.models import db
from app.models.provenance import (
    ProvenanceAgent, ProvenanceActivity, ProvenanceEntity,
    ProvenanceDerivation, ProvenanceUsage, ProvenanceCommunication,
    ProvenanceBundle
)
from app.models.document import Document
from app.models.extraction_prompt import ExtractionPrompt
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.provenance_service import get_provenance_service
from app.utils.environment_auth import auth_optional

provenance_bp = Blueprint('provenance', __name__)

from app.routes.provenance.qc_review_routes import register_qc_review_routes
from app.routes.provenance.viewer_routes import register_viewer_routes
from app.routes.provenance.detail_api_routes import register_detail_api_routes
from app.routes.provenance.pipeline_routes import register_pipeline_routes

register_qc_review_routes(provenance_bp)
register_viewer_routes(provenance_bp)
register_detail_api_routes(provenance_bp)
register_pipeline_routes(provenance_bp)


def init_provenance_csrf_exemption(app):
    """Exempt API endpoints from CSRF for programmatic access.

    The handlers now live in register-function sub-modules, so retrieve them
    from app.view_functions by endpoint and exempt the same objects (identical
    outcome to the pre-split `app.csrf.exempt(run_qc_audit_api)`).
    """
    for endpoint in ('provenance.run_qc_audit_api', 'provenance.post_review_log'):
        view = app.view_functions.get(endpoint)
        if view is not None:
            app.csrf.exempt(view)

__all__ = ["provenance_bp", "init_provenance_csrf_exemption"]
