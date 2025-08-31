"""
Debug routes for development.
"""
from flask import Blueprint, jsonify, render_template, current_app
import sys
import os
import requests
import psycopg2
import json
from datetime import datetime
from app.models.deconstructed_case import DeconstructedCase
from app.models import Document

debug_bp = Blueprint('debug', __name__)

@debug_bp.route('/test-triple-preview', methods=['GET'])
def test_triple_preview():
    """
    Test route to verify the triple preview functionality.
    """
    # Generate sample triples for testing
    sample_triples = [
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
            "predicate_label": "type",
            "object": "http://proethica.org/engineering-ethics/principle",
            "object_label": "Principle",
            "is_literal": False
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
            "predicate_label": "label",
            "object": "Safety Critical Design",
            "is_literal": True
        },
        {
            "subject": "http://proethica.org/engineering-ethics/concept/safety_critical_design",
            "subject_label": "Safety Critical Design",
            "predicate": "http://purl.org/dc/elements/1.1/description",
            "predicate_label": "description",
            "object": "The practice of ensuring safety in systems where failure could cause serious harm",
            "is_literal": True
        }
    ]
    
    # Return platform info and triples
    return jsonify({
        "status": "success",
        "message": "Triple preview test route is functioning",
        "python_version": sys.version,
        "sample_triples": sample_triples,
        "triple_count": len(sample_triples)
    })

@debug_bp.route('/status', methods=['GET'])
def debug_status():
    """
    Redirect to admin system health page.
    This route is deprecated - functionality has been moved to /admin/system-health
    """
    from flask import redirect, url_for, flash
    flash('Debug status has been moved to Admin System Health', 'info')
    return redirect(url_for('admin.system_health'))


@debug_bp.route('/deconstruction/<int:case_id>')
def view_deconstruction(case_id):
    """View case deconstruction results."""
    # Get the case
    case = Document.query.get_or_404(case_id)
    
    # Get deconstruction results
    deconstruction = DeconstructedCase.query.filter_by(case_id=case_id).first()
    
    if not deconstruction:
        return jsonify({
            "error": "No deconstruction found for this case",
            "case_id": case_id,
            "case_title": case.title
        }), 404
    
    # Convert to viewable format
    result = {
        "case": {
            "id": case.id,
            "title": case.title,
            "world": case.world.name if case.world else "Unknown",
            "source": case.source
        },
        "deconstruction": deconstruction.to_dict(),
        "analysis": {
            "stakeholders": deconstruction.stakeholders or [],
            "decision_points": deconstruction.decision_points or [],
            "reasoning_chain": deconstruction.reasoning_chain or {}
        }
    }
    
    return jsonify(result)


@debug_bp.route('/deconstructions')
def list_deconstructions():
    """List all case deconstructions."""
    deconstructions = DeconstructedCase.query.join(Document).all()
    
    results = []
    for d in deconstructions:
        results.append({
            "id": d.id,
            "case_id": d.case_id,
            "case_title": d.case.title,
            "adapter_type": d.adapter_type,
            "stakeholder_count": len(d.stakeholders) if d.stakeholders else 0,
            "decision_point_count": len(d.decision_points) if d.decision_points else 0,
            "confidence_avg": round((d.stakeholder_confidence + d.decision_points_confidence + d.reasoning_confidence) / 3, 2),
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "human_validated": d.human_validated
        })
    
    return jsonify({
        "total": len(results),
        "deconstructions": results
    })
