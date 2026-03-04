"""
Reconciliation Routes

Entity reconciliation and commit workflow between Step 3 and Step 4.
Handles duplicate detection, merge/unmerge operations, and final commit to OntServe.
"""

import logging
from datetime import datetime

from flask import render_template, request, jsonify
from app.models import Document, db, TemporaryRDFStorage
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)


def register_reconciliation_routes(bp):
    """Register reconciliation routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/reconcile')
    @auth_optional
    def reconcile_and_commit(case_id):
        """Reconciliation and commit page between Step 3 and Step 4.

        Page load shows entity summary. If a stored reconciliation run exists,
        its results and decisions are passed to the template for immediate display.
        """
        case_doc = Document.query.get_or_404(case_id)

        from app.services.pipeline_status_service import PipelineStatusService
        from app.models.reconciliation_run import ReconciliationRun

        pipeline_status = PipelineStatusService.get_step_status(case_id)

        # Entity counts
        unpublished_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False
        ).count()
        published_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=True
        ).count()

        # Class/individual breakdown
        class_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False, storage_type='class'
        ).count()
        individual_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False, storage_type='individual'
        ).count()

        # Concept type breakdown for summary display
        from sqlalchemy import func
        type_breakdown = db.session.query(
            TemporaryRDFStorage.extraction_type,
            TemporaryRDFStorage.storage_type,
            func.count(TemporaryRDFStorage.id)
        ).filter_by(
            case_id=case_id, is_published=False
        ).group_by(
            TemporaryRDFStorage.extraction_type,
            TemporaryRDFStorage.storage_type
        ).order_by(
            TemporaryRDFStorage.extraction_type,
            TemporaryRDFStorage.storage_type
        ).all()

        # Load stored reconciliation run if one exists
        existing_run = ReconciliationRun.query.filter_by(case_id=case_id).first()
        existing_decisions = {}
        if existing_run:
            for d in existing_run.decisions:
                key = f"{d.entity_a_id}_{d.entity_b_id}"
                existing_decisions[key] = {
                    'decision': d.user_decision,
                    'snapshots': d.merge_snapshots_json,
                }

        return render_template(
            'scenarios/reconcile.html',
            case=case_doc,
            pipeline_status=pipeline_status,
            unpublished_count=unpublished_count,
            published_count=published_count,
            class_count=class_count,
            individual_count=individual_count,
            type_breakdown=type_breakdown,
            existing_run=existing_run,
            existing_decisions=existing_decisions,
            current_step=3.5,
            step_title='Reconcile'
        )

    @bp.route('/case/<int:case_id>/reconcile/run', methods=['POST'])
    @auth_required_for_write
    def reconcile_run(case_id):
        """AJAX endpoint: run reconciliation (exact-match merges + LLM dedup).

        Persists results in ReconciliationRun + ReconciliationDecision tables
        so page reloads don't lose state.
        """
        from app.services.entity_reconciliation_service import EntityReconciliationService
        from app.models.reconciliation_run import ReconciliationRun, ReconciliationDecision

        try:
            recon_service = EntityReconciliationService()
            data = request.get_json(silent=True) or {}
            mode = data.get('mode', 'review')  # 'auto' = exact-match only, 'review' = + LLM dedup

            if mode == 'auto':
                reconciliation = recon_service.reconcile_auto(case_id)
            else:
                reconciliation = recon_service.reconcile_with_review(case_id)

            # Serialize candidates for JSON response
            candidates = []
            for c in reconciliation.review_candidates:
                candidates.append({
                    'entity_a_id': c.entity_a_id,
                    'entity_b_id': c.entity_b_id,
                    'entity_a_label': c.entity_a_label,
                    'entity_b_label': c.entity_b_label,
                    'similarity': c.similarity,
                    'recommendation': c.recommendation,
                    'llm_reason': c.llm_reason,
                    'entity_a_context': c.entity_a_context,
                    'entity_b_context': c.entity_b_context,
                })

            # Persist reconciliation run (replace any previous run for this case)
            ReconciliationRun.query.filter_by(case_id=case_id).delete()
            db.session.flush()

            run = ReconciliationRun(
                case_id=case_id,
                candidates_json=candidates,
                auto_merged=reconciliation.auto_merged,
                errors_json=reconciliation.errors,
            )
            db.session.add(run)
            db.session.flush()  # get run.id

            for c in candidates:
                decision = ReconciliationDecision(
                    run_id=run.id,
                    entity_a_id=c['entity_a_id'],
                    entity_b_id=c['entity_b_id'],
                    entity_a_label=c['entity_a_label'],
                    entity_b_label=c['entity_b_label'],
                    llm_recommendation=c['recommendation'],
                    llm_reason=c['llm_reason'],
                    similarity=c['similarity'],
                    entity_a_context=c['entity_a_context'],
                    entity_b_context=c['entity_b_context'],
                )
                db.session.add(decision)

            db.session.commit()

            # Updated entity counts after merges
            unpublished_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False
            ).count()
            class_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False, storage_type='class'
            ).count()
            individual_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, is_published=False, storage_type='individual'
            ).count()

            return jsonify({
                'success': True,
                'run_id': run.id,
                'auto_merged': reconciliation.auto_merged,
                'candidates': candidates,
                'errors': reconciliation.errors,
                'updated_counts': {
                    'unpublished': unpublished_count,
                    'classes': class_count,
                    'individuals': individual_count,
                }
            })

        except Exception as e:
            logger.error(f"Reconciliation failed for case {case_id}: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/reconcile/merge', methods=['POST'])
    @auth_required_for_write
    def reconcile_merge(case_id):
        """Merge two entities as part of reconciliation.

        Persists decision in ReconciliationDecision and returns snapshots for undo.
        """
        data = request.get_json()
        keep_id = data.get('keep_id')
        merge_id = data.get('merge_id')
        run_id = data.get('run_id')

        if not keep_id or not merge_id:
            return jsonify({'success': False, 'error': 'Missing keep_id or merge_id'}), 400

        from app.services.entity_reconciliation_service import EntityReconciliationService
        from app.models.reconciliation_run import ReconciliationDecision

        service = EntityReconciliationService()
        result = service.merge_entities(keep_id, merge_id)

        if result.get('success'):
            # Record decision in DB
            if run_id:
                decision = ReconciliationDecision.query.filter(
                    ReconciliationDecision.run_id == run_id,
                    db.or_(
                        db.and_(ReconciliationDecision.entity_a_id == keep_id,
                                ReconciliationDecision.entity_b_id == merge_id),
                        db.and_(ReconciliationDecision.entity_a_id == merge_id,
                                ReconciliationDecision.entity_b_id == keep_id),
                    )
                ).first()
                if decision:
                    decision.user_decision = 'merge'
                    decision.merge_snapshots_json = result['snapshots']
                    decision.decided_at = datetime.utcnow()
                    db.session.commit()

            return jsonify({
                'success': True,
                'snapshots': result['snapshots'],
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Merge failed')
            }), 500

    @bp.route('/case/<int:case_id>/reconcile/unmerge', methods=['POST'])
    @auth_required_for_write
    def reconcile_unmerge(case_id):
        """Undo a merge by restoring both entities from pre-merge snapshots.

        Also clears the decision record and returns the original candidate data
        so the JS can rebuild the candidate row without a page reload.
        """
        data = request.get_json()
        snapshots = data.get('snapshots')
        run_id = data.get('run_id')
        entity_a_id = data.get('entity_a_id')
        entity_b_id = data.get('entity_b_id')

        if not snapshots or 'keep' not in snapshots or 'merge' not in snapshots:
            return jsonify({'success': False, 'error': 'Missing snapshots'}), 400

        from app.services.entity_reconciliation_service import EntityReconciliationService
        from app.models.reconciliation_run import ReconciliationDecision

        service = EntityReconciliationService()
        success = service.unmerge_entities(snapshots['keep'], snapshots['merge'])

        if success:
            # Clear the decision so the candidate appears as pending again
            candidate_data = None
            if run_id and entity_a_id and entity_b_id:
                decision = ReconciliationDecision.query.filter(
                    ReconciliationDecision.run_id == run_id,
                    db.or_(
                        db.and_(ReconciliationDecision.entity_a_id == entity_a_id,
                                ReconciliationDecision.entity_b_id == entity_b_id),
                        db.and_(ReconciliationDecision.entity_a_id == entity_b_id,
                                ReconciliationDecision.entity_b_id == entity_a_id),
                    )
                ).first()
                if decision:
                    # Return the original candidate data for row rebuild
                    candidate_data = {
                        'entity_a_id': decision.entity_a_id,
                        'entity_b_id': decision.entity_b_id,
                        'entity_a_label': decision.entity_a_label,
                        'entity_b_label': decision.entity_b_label,
                        'similarity': decision.similarity,
                        'recommendation': decision.llm_recommendation,
                        'llm_reason': decision.llm_reason,
                        'entity_a_context': decision.entity_a_context or {},
                        'entity_b_context': decision.entity_b_context or {},
                    }
                    decision.user_decision = None
                    decision.merge_snapshots_json = None
                    decision.decided_at = None
                    db.session.commit()

            return jsonify({'success': True, 'candidate': candidate_data})
        else:
            return jsonify({'success': False, 'error': 'Unmerge failed'}), 500

    @bp.route('/case/<int:case_id>/reconcile/keep_separate', methods=['POST'])
    @auth_required_for_write
    def reconcile_keep_separate(case_id):
        """Record a keep-separate decision for a reconciliation candidate pair."""
        from app.models.reconciliation_run import ReconciliationDecision

        data = request.get_json()
        entity_a_id = data.get('entity_a_id')
        entity_b_id = data.get('entity_b_id')
        run_id = data.get('run_id')

        if not run_id or not entity_a_id or not entity_b_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        decision = ReconciliationDecision.query.filter(
            ReconciliationDecision.run_id == run_id,
            db.or_(
                db.and_(ReconciliationDecision.entity_a_id == entity_a_id,
                        ReconciliationDecision.entity_b_id == entity_b_id),
                db.and_(ReconciliationDecision.entity_a_id == entity_b_id,
                        ReconciliationDecision.entity_b_id == entity_a_id),
            )
        ).first()

        if decision:
            decision.user_decision = 'keep_separate'
            decision.decided_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True})

        return jsonify({'success': False, 'error': 'Decision record not found'}), 404

    @bp.route('/case/<int:case_id>/reconcile/undo_keep_separate', methods=['POST'])
    @auth_required_for_write
    def reconcile_undo_keep_separate(case_id):
        """Undo a keep-separate decision, restoring the candidate to pending state."""
        from app.models.reconciliation_run import ReconciliationDecision

        data = request.get_json()
        entity_a_id = data.get('entity_a_id')
        entity_b_id = data.get('entity_b_id')
        run_id = data.get('run_id')

        if not run_id or not entity_a_id or not entity_b_id:
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        decision = ReconciliationDecision.query.filter(
            ReconciliationDecision.run_id == run_id,
            db.or_(
                db.and_(ReconciliationDecision.entity_a_id == entity_a_id,
                        ReconciliationDecision.entity_b_id == entity_b_id),
                db.and_(ReconciliationDecision.entity_a_id == entity_b_id,
                        ReconciliationDecision.entity_b_id == entity_a_id),
            )
        ).first()

        if decision:
            candidate_data = {
                'entity_a_id': decision.entity_a_id,
                'entity_b_id': decision.entity_b_id,
                'entity_a_label': decision.entity_a_label,
                'entity_b_label': decision.entity_b_label,
                'similarity': decision.similarity,
                'recommendation': decision.llm_recommendation,
                'llm_reason': decision.llm_reason,
                'entity_a_context': decision.entity_a_context or {},
                'entity_b_context': decision.entity_b_context or {},
            }
            decision.user_decision = None
            decision.decided_at = None
            db.session.commit()
            return jsonify({'success': True, 'candidate': candidate_data})

        return jsonify({'success': False, 'error': 'Decision record not found'}), 404

    @bp.route('/case/<int:case_id>/reconcile/commit', methods=['POST'])
    @auth_required_for_write
    def reconcile_commit_execute(case_id):
        """Execute full commit to OntServe after reconciliation.

        Any unresolved reconciliation candidates are silently marked as
        keep_separate (preserving current entity state). No LLM recommendations
        are auto-applied at commit time.
        Logs commit to provenance.
        """
        from app.services.ontserve_commit_service import OntServeCommitService
        from app.models.reconciliation_run import ReconciliationRun
        from app.models.provenance import ProvenanceActivity, ProvenanceAgent

        # Mark any unresolved reconciliation candidates as 'unresolved' --
        # distinct from 'keep_separate' (explicit user choice). These pairs
        # are preserved for future review and learning analysis.
        run = ReconciliationRun.query.filter_by(case_id=case_id).first()
        if run:
            pending = run.decisions.filter_by(user_decision=None).all()
            if pending:
                for d in pending:
                    d.user_decision = 'unresolved'
                    d.decided_at = datetime.utcnow()
                db.session.commit()

        entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=False
        ).all()
        entity_ids = [e.id for e in entities]

        if not entity_ids:
            return jsonify({'success': False, 'error': 'No entities to commit'}), 400

        commit_start = datetime.utcnow()

        try:
            service = OntServeCommitService()
            result = service.commit_selected_entities(case_id, entity_ids)

            # Log commit to provenance
            try:
                agent = ProvenanceAgent.query.filter_by(
                    agent_type='system', agent_name='ontserve_commit'
                ).first()
                if not agent:
                    agent = ProvenanceAgent(
                        agent_type='system',
                        agent_name='ontserve_commit',
                        agent_version='1.0',
                    )
                    db.session.add(agent)
                    db.session.flush()

                commit_end = datetime.utcnow()
                activity = ProvenanceActivity(
                    activity_type='ontology_commit',
                    activity_name='commit_case_entities',
                    case_id=case_id,
                    started_at=commit_start,
                    ended_at=commit_end,
                    duration_ms=int((commit_end - commit_start).total_seconds() * 1000),
                    agent_id=agent.id,
                    status='completed',
                    activity_metadata={
                        'manifest': {
                            'entity_ids': entity_ids,
                            'classes_committed': result.get('classes_committed', 0),
                            'individuals_committed': result.get('individuals_committed', 0),
                            'ontserve_synced': result.get('ontserve_synced', False),
                        },
                        'reconciliation': {
                            'auto_merged': run.auto_merged if run else 0,
                            'candidates_reviewed': run.decisions.count() if run else 0,
                            'merges_accepted': run.decisions.filter_by(
                                user_decision='merge'
                            ).count() if run else 0,
                            'unresolved': run.decisions.filter_by(
                                user_decision='unresolved'
                            ).count() if run else 0,
                        },
                    }
                )
                db.session.add(activity)
                db.session.commit()
            except Exception as prov_err:
                logger.warning(f"Provenance logging failed (commit succeeded): {prov_err}")

            # Keep the reconciliation run record -- it preserves
            # unresolved pairs and decision history for future analysis.

            return jsonify({
                'success': True,
                'result': result
            })
        except Exception as e:
            logger.error(f"Commit failed for case {case_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/case/<int:case_id>/reconcile/uncommit', methods=['POST'])
    @auth_required_for_write
    def reconcile_uncommit(case_id):
        """Reverse a commit: remove entities from OntServe, reset is_published."""
        from app.services.ontserve_commit_service import OntServeCommitService
        from app.models.provenance import ProvenanceActivity, ProvenanceAgent

        published_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, is_published=True
        ).count()

        if published_count == 0:
            return jsonify({'success': False, 'error': 'No committed entities to uncommit'}), 400

        uncommit_start = datetime.utcnow()

        try:
            service = OntServeCommitService()
            result = service.uncommit_case(case_id)

            # Log uncommit to provenance
            try:
                agent = ProvenanceAgent.query.filter_by(
                    agent_type='system', agent_name='ontserve_commit'
                ).first()
                if agent:
                    uncommit_end = datetime.utcnow()
                    activity = ProvenanceActivity(
                        activity_type='ontology_uncommit',
                        activity_name='uncommit_case_entities',
                        case_id=case_id,
                        started_at=uncommit_start,
                        ended_at=uncommit_end,
                        duration_ms=int((uncommit_end - uncommit_start).total_seconds() * 1000),
                        agent_id=agent.id,
                        status='completed',
                        activity_metadata={
                            'entities_reset': result.get('entities_reset', 0),
                            'ttl_deleted': result.get('ttl_deleted', False),
                            'ontserve_cleared': result.get('ontserve_cleared', False),
                        },
                    )
                    db.session.add(activity)
                    db.session.commit()
            except Exception as prov_err:
                logger.warning(f"Provenance logging failed (uncommit succeeded): {prov_err}")

            return jsonify({'success': True, 'result': result})
        except Exception as e:
            logger.error(f"Uncommit failed for case {case_id}: {e}", exc_info=True)
            return jsonify({'success': False, 'error': str(e)}), 500
