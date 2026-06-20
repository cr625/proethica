"""Precedents blueprint package -- precedent-finding, similarity network/matrix, lineage routes."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

precedents_bp = Blueprint('precedents', __name__, url_prefix='/cases/precedents')

from app.routes.precedents.find_routes import register_find_routes
from app.routes.precedents.similarity_routes import register_similarity_routes
from app.routes.precedents.lineage_routes import register_lineage_routes

register_find_routes(precedents_bp)
register_similarity_routes(precedents_bp)
register_lineage_routes(precedents_bp)

# Back-compat re-exports: external callers (scenario_pipeline/step4/views.py) and tests
# import these helpers/constants from `app.routes.precedents` directly.
from app.routes.precedents.helpers import (  # noqa: E402,F401
    MATCHING_METHODS,
    COMPONENT_COLORS,
    COMPONENT_LABELS,
    _get_case_year,
    _find_precedents_for_case,
    _get_primary_method,
    _get_matching_provisions,
    _count_outcomes,
    _get_case_features,
)

__all__ = ["precedents_bp"]
