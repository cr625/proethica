"""HTML page + redirect routes for the provenance viewer UI: /tools/provenance hub, /tools/provenance/cases list, /tools/provenance/cases/<id> redirect, and the unified /scenario_pipeline/case/<id>/provenance view. render_template/redirect/url_for only; no shared helpers or constants.."""
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


def register_viewer_routes(bp):
    @bp.route('/tools/provenance')
    @auth_optional
    def provenance_hub():
        """Provenance hub - redirects to cases view."""
        return redirect(url_for('provenance.provenance_cases'))
    @bp.route('/tools/provenance/cases')
    @auth_optional
    def provenance_cases():
        """All cases provenance viewer page with optional case pre-selected."""
        # Redirect to unified view when a specific case is selected
        selected_case_id = request.args.get('selected', type=int)
        if selected_case_id:
            return redirect(url_for('provenance.case_provenance', case_id=selected_case_id))

        selected_case = None

        # Get all cases with optional provenance activity counts
        all_cases = db.session.query(
            Document.id,
            Document.title,
            func.count(ProvenanceActivity.id).label('activity_count'),
            func.max(ProvenanceActivity.created_at).label('last_activity')
        ).outerjoin(
            ProvenanceActivity, ProvenanceActivity.case_id == Document.id
        ).group_by(
            Document.id, Document.title
        ).order_by(
            Document.id
        ).all()

        # Get summary statistics
        stats = {
            'total_cases_tracked': db.session.query(
                func.count(func.distinct(ProvenanceActivity.case_id))
            ).scalar() or 0,
            'total_activities': ProvenanceActivity.query.count(),
            'total_entities': ProvenanceEntity.query.count(),
            'total_agents': ProvenanceAgent.query.count()
        }

        return render_template('tools/provenance_viewer.html',
                             all_cases=all_cases,
                             stats=stats,
                             selected_case_id=selected_case_id,
                             selected_case=selected_case)
    @bp.route('/tools/provenance/cases/<int:case_id>')
    @auth_optional
    def provenance_case(case_id):
        """Redirect to unified provenance view with case selected."""
        return redirect(url_for('provenance.case_provenance', case_id=case_id))
    @bp.route('/scenario_pipeline/case/<int:case_id>/provenance')
    @auth_optional
    def case_provenance(case_id):
        """Unified provenance view for a single case."""
        document = Document.query.get_or_404(case_id)

        initial_step = request.args.get('step', type=int)
        initial_section = request.args.get('section')
        initial_concept = request.args.get('concept')

        return render_template('scenario_pipeline/provenance.html',
                               case=document,
                               initial_step=initial_step,
                               initial_section=initial_section,
                               initial_concept=initial_concept)
