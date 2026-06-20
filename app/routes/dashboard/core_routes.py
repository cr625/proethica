"""Dashboard index + system-status API + world dashboard."""
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
    from app.models.case_guideline_associations import CaseGuidelineAssociation
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    CaseGuidelineAssociation = None
try:
    from app.models.temporary_concept import TemporaryConcept
except ImportError:
    # Create a placeholder for testing if the model doesn't exist yet
    TemporaryConcept = None
from app.services.step4_synthesis.firac_analysis_service import firac_analysis_service
from app.services.ethics_committee_agent import ethics_committee_agent
logger = logging.getLogger(__name__)
from app.routes.dashboard.helpers import (
    get_simplified_system_status,
    get_ontology_sync_status,
    get_system_statistics,
    get_recent_activity,
    get_workflow_status,
    assess_capabilities,
    get_world_statistics,
    get_world_analysis_status,
)


def register_core_routes(bp):
    @bp.route('/')
    @login_required
    def index():
        """Admin dashboard showing system overview and management tools."""
    
        # Get system statistics
        stats = get_system_statistics()
    
        # Get recent activity
        recent_activity = get_recent_activity()
    
        # Get ontology sync status
        sync_status = get_ontology_sync_status()
    
        # Get simplified system status (MCP server, database)
        system_status = get_simplified_system_status()
    
        return render_template(
            'dashboard/index.html',
            stats=stats,
            recent_activity=recent_activity,
            sync_status=sync_status,
            system_status=system_status
        )


    @bp.route('/api/stats')
    @login_required
    def api_system_stats():
        """API endpoint for system statistics."""
        stats = get_system_statistics()
        return jsonify(stats)


    @bp.route('/api/workflow')
    @login_required
    def api_workflow_status():
        """API endpoint for workflow status."""
        workflow = get_workflow_status()
        return jsonify(workflow)


    @bp.route('/api/capabilities')
    @login_required
    def api_capabilities():
        """API endpoint for capability assessment."""
        capabilities = assess_capabilities()
        return jsonify(capabilities)


    @bp.route('/api/sync-status')
    @login_required
    def api_sync_status():
        """API endpoint for ontology sync status."""
        sync_status = get_ontology_sync_status()
        return jsonify(sync_status)


    @bp.route('/world/<int:world_id>')
    @login_required
    def world_dashboard(world_id):
        """Detailed dashboard for a specific world."""
    
        world = World.query.get_or_404(world_id)
    
        # Get world-specific statistics
        world_stats = get_world_statistics(world_id)
    
        # Get world analysis status
        analysis_status = get_world_analysis_status(world_id)

        return render_template(
            'dashboard/world.html',
            world=world,
            stats=world_stats,
            analysis_status=analysis_status
        )


