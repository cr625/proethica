"""JSON API endpoints: evaluable-cases list, per-case views, and case facts.."""
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


def register_api_routes(bp):
    @bp.route('/api/evaluable-cases')
    def api_evaluable_cases():
        """Get list of cases available for the study (23-case pool)."""
        view_builder = SynthesisViewBuilder()
        cases = view_builder.get_evaluable_cases()
        return jsonify({'cases': cases, 'count': len(cases)})
    @bp.route('/api/case/<int:case_id>/views')
    def api_case_views(case_id):
        """Get all synthesis views for a case (for AJAX loading)."""
        view_builder = SynthesisViewBuilder()

        if not view_builder.case_has_synthesis(case_id):
            return jsonify({'error': 'Case does not have synthesis data'}), 404

        return jsonify(view_builder.get_all_views(case_id))
    @bp.route('/api/case/<int:case_id>/facts')
    def api_case_facts(case_id):
        """Get case facts only (Discussion/Conclusions withheld)."""
        view_builder = SynthesisViewBuilder()
        return jsonify(view_builder.get_case_facts(case_id))
