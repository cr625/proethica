"""Study (validation-study) blueprint package -- session/case/retrospective/api/admin/flow routes."""
import hashlib
import logging
import os
import random
import secrets
import uuid
from datetime import datetime
from flask import Blueprint, request, render_template, redirect, url_for, flash, session, jsonify
from flask_wtf.csrf import CSRFError
from app import db
from app.models import Document
from app.models.view_utility_evaluation import (
    ValidationSession, ViewUtilityEvaluation, RetrospectiveReflection
)
from app.services.validation.synthesis_view_builder import SynthesisViewBuilder
from app.services.validation.case_assignment_service import assign_cases
from app.services.validation.likert_items import (
    NARR_ITEMS, TIMELINE_ITEMS, QC_ITEMS, DECS_ITEMS, PROV_ITEMS, OVERALL_ITEMS,
)

logger = logging.getLogger(__name__)

study_bp = Blueprint('study', __name__)

from app.routes.study.session_routes import register_session_routes
from app.routes.study.case_routes import register_case_routes
from app.routes.study.retrospective_routes import register_retrospective_routes
from app.routes.study.api_routes import register_api_routes
from app.routes.study.admin_routes import register_admin_routes
from app.routes.study.flow_demo_routes import register_flow_demo_routes

register_session_routes(study_bp)
register_case_routes(study_bp)
register_retrospective_routes(study_bp)
register_api_routes(study_bp)
register_admin_routes(study_bp)
register_flow_demo_routes(study_bp)


@study_bp.before_request
def _withhold_during_anonymous_review():
    """
    Withhold the validation-study surfaces during the anonymous review window.

    The consent documents (`_info_sheet_v2.html`, `_info_sheet_v3_prolific.html`)
    and the completion page name the principal investigator, the student
    investigator, their institutional addresses, and the reviewing IRB. That
    wording is bound to the approved protocol and is checked by a wording-parity
    test, so it is not edited here: the documents stay verbatim for the research
    record and the routes are made unreachable instead.

    Recruitment closed before this guard was added, so no live participant flow
    depends on these routes. See config.ANONYMOUS_MODE.
    """
    from flask import current_app, render_template
    if current_app.config.get('ANONYMOUS_MODE', True):
        return render_template('withheld.html'), 404



# Back-compat re-export: tests/unit/test_retrospective_shuffle.py imports this directly.
from app.routes.study.helpers import _RANKING_VIEWS  # noqa: E402,F401

__all__ = ["study_bp"]
