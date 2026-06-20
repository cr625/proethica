"""Pipeline automation dashboard blueprint package."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

pipeline_bp = Blueprint('pipeline', __name__, url_prefix='/pipeline')

from app.routes.pipeline_dashboard.view_routes import register_view_routes
from app.routes.pipeline_dashboard.injection_routes import register_injection_routes
from app.routes.pipeline_dashboard.run_routes import register_run_routes
from app.routes.pipeline_dashboard.queue_routes import register_queue_routes
from app.routes.pipeline_dashboard.case_routes import register_case_routes
from app.routes.pipeline_dashboard.stats_routes import register_stats_routes

register_view_routes(pipeline_bp)
register_injection_routes(pipeline_bp)
register_run_routes(pipeline_bp)
register_queue_routes(pipeline_bp)
register_case_routes(pipeline_bp)
register_stats_routes(pipeline_bp)


def init_pipeline_csrf_exemption(app):
    """Exempt pipeline API routes from CSRF protection.

    The handler functions now live in register-function sub-modules, so they
    are retrieved from app.view_functions by endpoint and the SAME function
    objects are exempted (Flask-CSRF matches on the view's module.__name__, so
    exempting the live objects is identical in outcome to the pre-split code).
    """
    if hasattr(app, 'csrf'):
        for endpoint in (
            'pipeline.api_add_to_queue',
            'pipeline.api_remove_from_queue',
            'pipeline.api_update_queue_item',
            'pipeline.api_start_queue_processing',
            'pipeline.api_clear_queue',
            'pipeline.api_run_single_case',
            'pipeline.api_run_step4',
            'pipeline.api_retry_run',
            'pipeline.api_cancel_run',
            'pipeline.api_service_status',
            'pipeline.api_reprocess_case',
            'pipeline.api_set_injection_mode',
        ):
            view = app.view_functions.get(endpoint)
            if view is not None:
                app.csrf.exempt(view)



__all__ = ["pipeline_bp", "init_pipeline_csrf_exemption"]
