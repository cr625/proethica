"""The vertical-timeline pipeline API: GET /api/provenance/case/<id>/pipeline (get_case_pipeline). This is the ONLY route that consumes the shared constants and helpers; it iterates PIPELINE_STRUCTURE and calls _get_extraction_data, _get_temporal_extraction_data, _get_step4_phase_data, and reads ENTITY_COLORS. Must import those names from helpers.."""
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
from app.routes.provenance.helpers import (
    PIPELINE_STRUCTURE,
    ENTITY_COLORS,
    _get_extraction_data,
    _get_temporal_extraction_data,
    _get_step4_phase_data,
)


def register_pipeline_routes(bp):
    @bp.route('/api/provenance/case/<int:case_id>/pipeline')
    @auth_optional
    def get_case_pipeline(case_id):
        """
    Get structured pipeline data for vertical timeline view.
    Returns all extraction prompts and entities organized by step/pass/concept.
    """
        document = Document.query.get_or_404(case_id)

        # Build pipeline data structure
        pipeline = []

        # Steps 1-3: Entity extraction
        for step_def in PIPELINE_STRUCTURE['steps']:
            step_data = {
                'step': step_def['step'],
                'name': step_def['name'],
                'color': step_def['color'],
                'passes': []
            }

            if step_def['step'] == 3:
                # Step 3 uses a single LangGraph extraction (not per-section passes)
                pass_data = {
                    'name': 'Temporal Dynamics',
                    'section_type': 'facts',
                    'extractions': []
                }
                for concept in step_def['concepts']:
                    extraction_data = _get_temporal_extraction_data(case_id, concept)
                    pass_data['extractions'].append(extraction_data)
                step_data['passes'].append(pass_data)
            else:
                for section_type in PIPELINE_STRUCTURE['passes']:
                    pass_name = 'Pass 1 (Facts)' if section_type == 'facts' else 'Pass 2 (Discussion)'
                    pass_data = {
                        'name': pass_name,
                        'section_type': section_type,
                        'extractions': []
                    }

                    for concept in step_def['concepts']:
                        extraction_data = _get_extraction_data(
                            case_id,
                            step_def['step'],
                            section_type,
                            concept
                        )
                        pass_data['extractions'].append(extraction_data)

                    step_data['passes'].append(pass_data)

            pipeline.append(step_data)

        # Step 4: Synthesis phases
        step4_data = {
            'step': 4,
            'name': 'Synthesis & Analysis',
            'color': PIPELINE_STRUCTURE['step4_color'],
            'phases': []
        }

        for phase_def in PIPELINE_STRUCTURE['step4_phases']:
            phase_data = _get_step4_phase_data(case_id, phase_def)
            step4_data['phases'].append(phase_data)

        pipeline.append(step4_data)

        # QC verification results (latest audit for this case)
        qc_result = None
        qc_row = db.session.execute(text("""
        SELECT verification_date, protocol_version, overall_status,
               entity_count_total, extraction_types_count,
               critical_count, warning_count, info_count, check_results
        FROM case_verification_results
        WHERE case_id = :case_id
        ORDER BY verification_date DESC LIMIT 1
    """), {'case_id': case_id}).fetchone()
        if qc_row:
            qc_result = {
                'verification_date': qc_row[0].isoformat() if qc_row[0] else None,
                'protocol_version': qc_row[1],
                'overall_status': qc_row[2],
                'entity_count_total': qc_row[3],
                'extraction_types_count': qc_row[4],
                'critical_count': qc_row[5],
                'warning_count': qc_row[6],
                'info_count': qc_row[7],
                'check_results': json.loads(qc_row[8]) if isinstance(qc_row[8], str) else qc_row[8],
            }

        # Review log entries (newest first)
        review_rows = db.session.execute(text("""
        SELECT id, entry_type, entry_key, status, summary, details, author, created_at
        FROM case_review_log
        WHERE case_id = :case_id
        ORDER BY created_at DESC
    """), {'case_id': case_id}).fetchall()

        review_log = [{
            'id': r[0],
            'entry_type': r[1],
            'entry_key': r[2],
            'status': r[3],
            'summary': r[4],
            'details': r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else None),
            'author': r[6],
            'created_at': r[7].isoformat() if r[7] else None,
        } for r in review_rows]

        # Consolidation-and-commit trail: the post-extraction activities
        # (reconcile, enrichment, edge materialization, guards, SHACL/OWL
        # conformance) that turn the working store into the committed record.
        # Recorded in the PROV tables all along but previously not displayed.
        consolidation_rows = db.session.execute(text("""
        SELECT activity_type, activity_name, started_at, duration_ms, status,
               execution_plan, error_message
        FROM provenance_activities
        WHERE case_id = :case_id
          AND activity_type IN ('reconciliation', 'enrichment', 'materialization',
                                'guard', 'filter', 'validation')
        ORDER BY started_at DESC
        LIMIT 30
    """), {'case_id': case_id}).fetchall()

        consolidation = [{
            'activity_type': r[0],
            'activity_name': r[1],
            'started_at': r[2].isoformat() if r[2] else None,
            'duration_ms': r[3],
            'status': r[4],
            'execution_plan': r[5] if isinstance(r[5], dict) else (json.loads(r[5]) if r[5] else None),
            'error_message': r[6],
        } for r in consolidation_rows]

        return jsonify({
            'case': {
                'id': document.id,
                'title': document.title
            },
            'pipeline': pipeline,
            'entity_colors': ENTITY_COLORS,
            'qc_verification': qc_result,
            'consolidation': consolidation,
            'review_log': review_log
        })
