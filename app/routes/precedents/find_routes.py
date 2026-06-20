"""Precedent-finding routes."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)
from app.routes.precedents.helpers import (
    MATCHING_METHODS,
    COMPONENT_COLORS,
    COMPONENT_LABELS,
    _get_case_year,
    _find_precedents_for_case,
)


def register_find_routes(bp):
    @bp.route('/', methods=['GET'])
    @auth_optional
    def find_precedents():
        """Display the precedent finder interface."""
        # Get all cases for the selector
        cases = Document.query.filter(
            Document.document_type.in_(['case', 'case_study'])
        ).order_by(Document.id).all()

        # Format cases for display
        case_list = []
        for case in cases:
            case_number = ''
            if case.doc_metadata and case.doc_metadata.get('case_number'):
                case_number = case.doc_metadata.get('case_number')

            case_list.append({
                'id': case.id,
                'title': case.title,
                'case_number': case_number,
                'year': _get_case_year(case)
            })

        # Check if a source case was selected
        source_case_id = request.args.get('case_id', type=int)
        precedent_results = None
        source_case = None

        if source_case_id:
            source_case = Document.query.get(source_case_id)
            if source_case:
                precedent_results = _find_precedents_for_case(source_case_id)

        return render_template(
            'precedents.html',
            cases=case_list,
            source_case=source_case,
            source_case_id=source_case_id,
            precedent_results=precedent_results,
            matching_methods=MATCHING_METHODS,
            component_colors=COMPONENT_COLORS,
            component_labels=COMPONENT_LABELS
        )


    @bp.route('/api/find', methods=['GET'])
    @auth_optional
    def api_find_precedents():
        """API endpoint for finding precedents."""
        case_id = request.args.get('case_id', type=int)
        limit = request.args.get('limit', 10, type=int)
        min_score = request.args.get('min_score', 0.1, type=float)

        if not case_id:
            return jsonify({'error': 'case_id is required'}), 400

        results = _find_precedents_for_case(case_id, limit=limit, min_score=min_score)
        return jsonify(results)


