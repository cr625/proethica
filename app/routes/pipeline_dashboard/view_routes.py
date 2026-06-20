"""Dashboard + queue page views."""
from flask import Blueprint, render_template, jsonify, request
from app.models import db
from app.models.pipeline_run import PipelineRun, PipelineQueue, PIPELINE_STATUS
from app.models.document import Document
from app.services.pipeline_state_manager import PipelineStateManager
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def register_view_routes(bp):
    @bp.route('/dashboard')
    def dashboard():
        """Main pipeline dashboard showing status of all runs."""
        # Get recent runs
        recent_runs = PipelineRun.query\
            .order_by(PipelineRun.created_at.desc())\
            .limit(20)\
            .all()

        # Get active runs
        active_runs = PipelineRun.query\
            .filter(PipelineRun.status.in_([
                PIPELINE_STATUS['RUNNING'],
                PIPELINE_STATUS['STEP1_FACTS'],
                PIPELINE_STATUS['STEP1_DISCUSSION'],
                PIPELINE_STATUS['STEP2_FACTS'],
                PIPELINE_STATUS['STEP2_DISCUSSION'],
                PIPELINE_STATUS['STEP3'],
                PIPELINE_STATUS['STEP4'],
                PIPELINE_STATUS['STEP5']
            ]))\
            .all()

        # Get queue stats
        queue_count = PipelineQueue.query.filter_by(status='queued').count()

        # Get case count
        case_count = Document.query.filter(
            Document.doc_metadata.isnot(None)
        ).count()

        # Get case IDs that have completed Step 4 synthesis
        # Used to hide Synthesize button for cases already synthesized
        # check_step4_complete checks all 7 Case Analysis substeps
        state_manager = PipelineStateManager()
        all_case_ids = [doc.id for doc in Document.query.filter(Document.doc_metadata.isnot(None)).all()]
        completed_case_ids = set(
            case_id for case_id in all_case_ids
            if state_manager.check_step4_complete(case_id)
        )

        return render_template(
            'pipeline_dashboard/index.html',
            recent_runs=recent_runs,
            active_runs=active_runs,
            queue_count=queue_count,
            case_count=case_count,
            completed_case_ids=completed_case_ids
        )


    @bp.route('/queue')
    def queue_page():
        """Queue management page for selecting and processing cases."""
        from sqlalchemy import text as sa_text

        # Get all cases with sections
        cases = Document.query\
            .filter(Document.doc_metadata.isnot(None))\
            .order_by(Document.id)\
            .all()

        # Get extraction counts per case (actual entity data)
        extraction_counts = {}
        rows = db.session.execute(sa_text("""
        SELECT case_id, COUNT(*) as total,
               COUNT(DISTINCT extraction_type) as types,
               SUM(CASE WHEN is_published THEN 1 ELSE 0 END) as published
        FROM temporary_rdf_storage
        WHERE case_id IS NOT NULL
        GROUP BY case_id
    """)).fetchall()
        for row in rows:
            extraction_counts[row[0]] = {
                'total': row[1], 'types': row[2], 'published': row[3]
            }

        # Get QC results per case (latest)
        qc_results = {}
        qc_rows = db.session.execute(sa_text("""
        SELECT DISTINCT ON (case_id) case_id, overall_status,
               entity_count_total, extraction_types_count,
               critical_count, warning_count, info_count
        FROM case_verification_results
        ORDER BY case_id, verification_date DESC
    """)).fetchall()
        for row in qc_rows:
            qc_results[row[0]] = {
                'status': row[1], 'total': row[2], 'types': row[3],
                'critical': row[4], 'warning': row[5], 'info': row[6]
            }

        # Detect label_only cases (marked in doc_metadata.extraction_mode)
        label_only_cases = set()
        lo_rows = db.session.execute(sa_text("""
        SELECT id FROM documents
        WHERE doc_metadata->>'extraction_mode' = 'label_only'
    """)).fetchall()
        for row in lo_rows:
            label_only_cases.add(row[0])

        # Filter to cases that have sections_dual
        cases_with_sections = []
        for case in cases:
            metadata = case.doc_metadata or {}
            if metadata.get('sections_dual'):
                latest_run = PipelineRun.query\
                    .filter_by(case_id=case.id)\
                    .order_by(PipelineRun.created_at.desc())\
                    .first()

                queue_entry = PipelineQueue.query\
                    .filter_by(case_id=case.id, status='queued')\
                    .first()

                ext = extraction_counts.get(case.id)
                qc = qc_results.get(case.id)

                cases_with_sections.append({
                    'id': case.id,
                    'title': case.title,
                    'latest_run': latest_run,
                    'is_queued': queue_entry is not None,
                    'has_facts': bool(metadata.get('sections_dual', {}).get('facts')),
                    'has_discussion': bool(metadata.get('sections_dual', {}).get('discussion')),
                    'extraction': ext,
                    'qc': qc,
                    'is_label_only': case.id in label_only_cases,
                })

        # Get current queue
        queue_items = PipelineQueue.query\
            .filter_by(status='queued')\
            .order_by(PipelineQueue.priority.desc(), PipelineQueue.added_at.asc())\
            .all()

        # Get distinct group names
        groups = db.session.query(PipelineQueue.group_name)\
            .filter(PipelineQueue.group_name.isnot(None))\
            .distinct()\
            .all()
        group_names = [g[0] for g in groups if g[0]]

        return render_template(
            'pipeline_dashboard/queue.html',
            cases=cases_with_sections,
            queue_items=queue_items,
            group_names=group_names
        )


    # REST API Endpoints

