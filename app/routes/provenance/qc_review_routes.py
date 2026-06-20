"""Write/log APIs: the V0-V9 QC audit trigger (POST) and the case review-log endpoints (POST append + GET list). run_qc_audit_api and post_review_log are the two CSRF-exempt handlers referenced by object in init_provenance_csrf_exemption (kept in __init__), so they must live in this module's register fn.."""
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


def register_qc_review_routes(bp):
    @bp.route('/api/qc/audit/<int:case_id>', methods=['POST'])
    @auth_optional
    def run_qc_audit_api(case_id):
        """Run V0-V9 QC audit for a case and store results."""
        try:
            from app.services.qc.run_qc_audit import run_audit, store_audit
            audit = run_audit(case_id)
            store_audit(audit)
            return jsonify({'success': True, 'audit': audit})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
    @bp.route('/api/provenance/case/<int:case_id>/review-log', methods=['POST'])
    @auth_optional
    def post_review_log(case_id):
        """Append a review log entry for a case."""
        Document.query.get_or_404(case_id)
        data = request.get_json()
        if not data or not data.get('summary'):
            return jsonify({'success': False, 'error': 'summary is required'}), 400

        entry_type = data.get('entry_type', 'manual_review')
        if entry_type not in ('agent_check', 'qc_script', 'manual_review', 'revision'):
            return jsonify({'success': False, 'error': f'Invalid entry_type: {entry_type}'}), 400

        details_val = data.get('details')
        if details_val is not None and not isinstance(details_val, dict):
            return jsonify({'success': False, 'error': 'details must be a JSON object'}), 400

        result = db.session.execute(text("""
        INSERT INTO case_review_log (case_id, entry_type, entry_key, status, summary, details, author)
        VALUES (:case_id, :entry_type, :entry_key, :status, :summary, :details, :author)
        RETURNING id, created_at
    """), {
            'case_id': case_id,
            'entry_type': entry_type,
            'entry_key': data.get('entry_key'),
            'status': data.get('status'),
            'summary': data['summary'],
            'details': json.dumps(details_val) if details_val else None,
            'author': data.get('author', 'manual'),
        })
        db.session.commit()
        row = result.fetchone()
        return jsonify({
            'success': True,
            'id': row[0],
            'created_at': row[1].isoformat() if row[1] else None,
        }), 201
    @bp.route('/api/provenance/case/<int:case_id>/review-log', methods=['GET'])
    @auth_optional
    def get_review_log(case_id):
        """List all review log entries for a case (newest first)."""
        Document.query.get_or_404(case_id)
        rows = db.session.execute(text("""
        SELECT id, entry_type, entry_key, status, summary, details, author, created_at
        FROM case_review_log
        WHERE case_id = :case_id
        ORDER BY created_at DESC
    """), {'case_id': case_id}).fetchall()

        entries = [{
            'id': r[0],
            'entry_type': r[1],
            'entry_key': r[2],
            'status': r[3],
            'summary': r[4],
            'details': r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else None),
            'author': r[6],
            'created_at': r[7].isoformat() if r[7] else None,
        } for r in rows]

        return jsonify({'review_log': entries})
