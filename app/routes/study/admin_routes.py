"""Admin-gated routes (admin_required_production): study dashboard with aggregations, CSV/JSON export, comparison summary, evaluator progress. Carries its own local imports (admin_required_production, Response, sqlalchemy func/distinct) at lines 1036-1038.."""
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


def register_admin_routes(bp):
    from app.utils.environment_auth import admin_required_production
    from flask import Response
    from sqlalchemy import func, distinct
    @bp.route('/admin/')
    @admin_required_production
    def admin_dashboard():
        """Validation study admin dashboard.

    Focused on the active view-utility study (validation pivot, plan
    `proethica/.claude/plans/validation-study.md`). Surfaces the operational metrics
    needed to monitor enrollment, completion, per-case coverage (against
    the 23-case pool with n>=5 threshold), and data-quality flags
    (attention-check pass rate, low-effort flags).

    The legacy comparative-prediction system (ExperimentRun / Prediction /
    double-blind evaluation) is intentionally NOT surfaced here during the
    pivot. A collapsed link to `/experiment/` remains for ad-hoc access.
    Revisit post-pivot if the legacy admin panels are still needed for
    Chapter 4 secondary analyses.
    """
        from app.config.study_case_pool import STUDY_CASE_POOL_IDS, STUDY_CASE_POOL_SIZE
        from app.models.view_utility_evaluation import RetrospectiveReflection

        # Real recruitment channels only. `preview` is the demo-walkthrough
        # bypass and `drexel_student` is the dormant legacy default (no live
        # Drexel recruitment under the post-pivot protocol), so both are noise
        # on the operational dashboard. The export endpoint still surfaces
        # them in raw data when needed for archive/audit purposes.
        REAL_SOURCES = ('prolific_engineering_trained',)

        real_session_ids_subq = db.session.query(ValidationSession.id).filter(
            ValidationSession.recruitment_source.in_(REAL_SOURCES)
        ).subquery()

        # Enrollment, by recruitment_source (real channels only).
        by_source_rows = db.session.query(
            ValidationSession.recruitment_source,
            func.count(ValidationSession.id).label('enrolled'),
            func.count(ValidationSession.completed_at).label('completed'),
        ).filter(
            ValidationSession.recruitment_source.in_(REAL_SOURCES)
        ).group_by(ValidationSession.recruitment_source).all()
        by_source = {
            row.recruitment_source: {'enrolled': row.enrolled, 'completed': row.completed}
            for row in by_source_rows
        }
        # Ensure each real channel appears in the UI even at zero.
        for src in REAL_SOURCES:
            by_source.setdefault(src, {'enrolled': 0, 'completed': 0})

        total_enrolled = sum(s['enrolled'] for s in by_source.values())
        total_completed = sum(s['completed'] for s in by_source.values())
        total_in_progress = total_enrolled - total_completed

        # Per-case coverage against the 23-case study pool.
        # Counts distinct evaluators per case (only completed evaluations from
        # real channels).
        coverage_rows = db.session.query(
            ViewUtilityEvaluation.case_id,
            func.count(distinct(ViewUtilityEvaluation.evaluator_id)).label('n_raters'),
        ).filter(
            ViewUtilityEvaluation.case_id.in_(STUDY_CASE_POOL_IDS),
            ViewUtilityEvaluation.completed_at.isnot(None),
            ViewUtilityEvaluation.session_id.in_(real_session_ids_subq),
        ).group_by(ViewUtilityEvaluation.case_id).all()
        coverage_map = {row.case_id: row.n_raters for row in coverage_rows}

        # Build coverage list ordered by case_id, with title for display.
        case_titles = {
            d.id: d.title
            for d in Document.query.filter(Document.id.in_(STUDY_CASE_POOL_IDS)).all()
        }
        coverage_threshold = 5  # Krippendorff floor per plan §0 #6
        coverage = []
        for cid in STUDY_CASE_POOL_IDS:
            n = coverage_map.get(cid, 0)
            coverage.append({
                'case_id': cid,
                'title': case_titles.get(cid, f'Case {cid}'),
                'n_raters': n,
                'meets_threshold': n >= coverage_threshold,
            })
        coverage_under = [c for c in coverage if not c['meets_threshold']]

        # Data-quality flags. Restricted to evaluations from real channels.
        real_evals_base = ViewUtilityEvaluation.query.filter(
            ViewUtilityEvaluation.session_id.in_(real_session_ids_subq)
        )
        total_evals = real_evals_base.filter(
            ViewUtilityEvaluation.completed_at.isnot(None)
        ).count()
        # The attention-check item is the reverse-coded Overall item
        # `overall_surfaced_considerations` (pass = response of 1). The dedicated
        # `attention_check_response` column is unpopulated for real sessions
        # because the rendered form field name is the item name, not
        # `attention_check_response`; derive the count from the column that
        # actually carries the participant's response.
        attn_answered = real_evals_base.filter(
            ViewUtilityEvaluation.overall_surfaced_considerations.isnot(None)
        ).count()
        attn_passed = real_evals_base.filter(
            ViewUtilityEvaluation.overall_surfaced_considerations == 1
        ).count()
        low_effort_flagged = real_evals_base.filter(
            ViewUtilityEvaluation.low_effort_flag.is_(True)
        ).count()

        # Recent sessions for the operations table (last 10, real channels only).
        recent_sessions = ValidationSession.query.filter(
            ValidationSession.recruitment_source.in_(REAL_SOURCES)
        ).order_by(
            ValidationSession.started_at.desc()
        ).limit(10).all()

        # =========================================================================
        # Results aggregations (drive the visualization section)
        # =========================================================================

        # Per-view mean utility score (1-7 Likert) across all completed
        # evaluations from real channels. Each view contributes 3 items; the
        # Overall row reverse-codes `overall_surfaced_considerations` via
        # ViewUtilityEvaluation.overall_utility_mean.
        completed_evals = real_evals_base.filter(
            ViewUtilityEvaluation.completed_at.isnot(None)
        ).all()

        def _summarize(values):
            """Return (mean, sd, n) for a list, ignoring None. SD is the
        sample standard deviation (n-1); None when n < 2."""
            clean = [v for v in values if v is not None]
            n = len(clean)
            if n == 0:
                return None, None, 0
            mean = sum(clean) / n
            if n < 2:
                return round(mean, 2), None, n
            variance = sum((v - mean) ** 2 for v in clean) / (n - 1)
            return round(mean, 2), round(variance ** 0.5, 2), n

        view_specs = [
            ('Provisions', 'provisions_view_mean'),
            ('Q&C', 'qc_view_mean'),
            ('Decisions', 'decisions_view_mean'),
            ('Timeline', 'timeline_view_mean'),
            ('Narrative', 'narrative_view_mean'),
            ('Overall', 'overall_utility_mean'),
        ]
        view_means = []
        for label, attr in view_specs:
            mean, sd, n = _summarize([getattr(e, attr) for e in completed_evals])
            view_means.append({'label': label, 'mean': mean, 'sd': sd, 'n': n})

        # Retrospective rankings: rank 1 (most valuable) to 5 (least). For
        # each view, count how many participants placed it at each rank. The
        # stacked-bar chart shows the rank-1 segment at the top, rank-5 at
        # the bottom.
        retros = RetrospectiveReflection.query.filter(
            RetrospectiveReflection.session_id.in_(real_session_ids_subq)
        ).all()
        ranking_specs = [
            ('Provisions', 'rank_provisions_view'),
            ('Q&C', 'rank_qc_view'),
            ('Decisions', 'rank_decisions_view'),
            ('Timeline', 'rank_timeline_view'),
            ('Narrative', 'rank_narrative_view'),
        ]
        ranking_counts = []
        for label, attr in ranking_specs:
            counts = [0, 0, 0, 0, 0]  # index 0 = rank 1
            for r in retros:
                val = getattr(r, attr)
                if val is not None and 1 <= val <= 5:
                    counts[val - 1] += 1
            ranking_counts.append({'label': label, 'counts': counts})

        # Per-case mean overall utility (only cases with at least one
        # completed evaluation from a real channel). Sorted descending by mean.
        case_means_by_id = {}
        for e in completed_evals:
            score = e.overall_utility_mean
            if score is None:
                continue
            case_means_by_id.setdefault(e.case_id, []).append(score)
        per_case_means = []
        for cid, scores in case_means_by_id.items():
            per_case_means.append({
                'case_id': cid,
                'title': case_titles.get(cid, f'Case {cid}'),
                'mean': round(sum(scores) / len(scores), 2),
                'n': len(scores),
            })
        per_case_means.sort(key=lambda r: r['mean'], reverse=True)

        results = {
            'view_means': view_means,
            'ranking_counts': ranking_counts,
            'per_case_means': per_case_means,
            'n_completed_evals': len(completed_evals),
            'n_retrospectives': len(retros),
        }

        stats = {
            'total_enrolled': total_enrolled,
            'total_completed': total_completed,
            'total_in_progress': total_in_progress,
            'pool_size': STUDY_CASE_POOL_SIZE,
            'coverage_threshold': coverage_threshold,
            'cases_meeting_threshold': sum(1 for c in coverage if c['meets_threshold']),
            'cases_under_threshold': len(coverage_under),
            'total_evaluations': total_evals,
            'attention_check_answered': attn_answered,
            'attention_check_passed': attn_passed,
            'attention_check_pass_rate': (
                round(100.0 * attn_passed / attn_answered, 1) if attn_answered else None
            ),
            'low_effort_flagged': low_effort_flagged,
            'by_source': by_source,
        }

        return render_template('validation_study/admin_dashboard.html',
                               stats=stats,
                               coverage=coverage,
                               coverage_under=coverage_under,
                               recent_sessions=recent_sessions,
                               results=results)
    @bp.route('/admin/export')
    @admin_required_production
    def admin_export():
        """Export study view-utility data for Krippendorff's alpha analysis.

    Default scope is the engineering domain (IRB-approved pool); pass
    `?domain=all` to include any stray non-engineering sessions.
    `?level=items` returns per-item data for Krippendorff; otherwise view means.
    """
        from app.services.experiment.validation_export_service import ValidationExportService

        format_type = request.args.get('format', 'csv')
        domain_param = request.args.get('domain', 'engineering')
        domain = None if domain_param == 'all' else domain_param
        use_means = request.args.get('level', 'means') == 'means'

        export_service = ValidationExportService()
        content, filename = export_service.export_chapter4_for_krippendorff(
            domain=domain,
            use_means=use_means,
            format=format_type
        )

        if format_type == 'json':
            mimetype = 'application/json'
        else:
            mimetype = 'text/csv'

        return Response(
            content,
            mimetype=mimetype,
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )
    @bp.route('/admin/summary')
    @admin_required_production
    def admin_summary():
        """Get summary statistics comparing baseline vs ProEthica."""
        from app.services.experiment.validation_export_service import ValidationExportService

        domain = request.args.get('domain')
        experiment_run_id = request.args.get('experiment_run_id', type=int)

        export_service = ValidationExportService()
        summary = export_service.export_comparison_summary(
            experiment_run_id=experiment_run_id,
            domain=domain
        )

        return jsonify(summary)
    @bp.route('/admin/evaluator-progress')
    @admin_required_production
    def admin_evaluator_progress():
        """Get progress summary for each evaluator."""
        from app.services.experiment.validation_export_service import ValidationExportService

        experiment_run_id = request.args.get('experiment_run_id', type=int)

        export_service = ValidationExportService()
        progress = export_service.get_evaluator_progress(
            experiment_run_id=experiment_run_id
        )

        return jsonify({'evaluators': progress})
