"""Dashboard blueprint package -- system dashboard + case analysis (FIRAC / ethics-committee) routes."""
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required
from sqlalchemy import func, desc
from datetime import datetime, timedelta
import json
import logging

from app.models import db
from app.models.world import World
from app.models.guideline import Guideline
from app.models import Document
from app.models.document_section import DocumentSection
from app.models.entity_triple import EntityTriple
from app.models.ontology import Ontology
from app.models.deconstructed_case import DeconstructedCase
try:
    from app.models.temporary_concept import TemporaryConcept
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    TemporaryConcept = None
from app.services.step4_synthesis.firac_analysis_service import firac_analysis_service
from app.services.ethics_committee_agent import ethics_committee_agent
logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

from app.routes.dashboard.core_routes import register_core_routes
from app.routes.dashboard.analysis_routes import register_analysis_routes

register_core_routes(dashboard_bp)
register_analysis_routes(dashboard_bp)


__all__ = ["dashboard_bp"]
