"""Auto-commit + status, clear-ontology, search-ontserve-classes."""
import logging
from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.entity.case_entity_storage_service import CaseEntityStorageService
from app.services.extraction.field_classification import group_properties
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)


def register_ontserve_commit_search_ops(bp):
    @bp.route('/case/<int:case_id>/entities/auto_commit', methods=['POST'])
    @auth_required_for_write
    def trigger_auto_commit(case_id):
        """
        Manually trigger auto-commit for entity-ontology linking.

        Links extracted entities to OntServe classes based on LLM match decisions,
        generates case TTL file, and updates precedent features for Jaccard calculation.
        """
        try:
            from app.services.commit.auto_commit_service import AutoCommitService

            data = request.get_json() or {}
            force = data.get('force', False)

            auto_commit_service = AutoCommitService()
            result = auto_commit_service.commit_case_entities(case_id, force=force)

            # Convert dataclass to dict for JSON response
            response = {
                'success': True,
                'case_id': result.case_id,
                'total_entities': result.total_entities,
                'linked_count': result.linked_count,
                'new_class_count': result.new_class_count,
                'skipped_count': result.skipped_count,
                'error_count': result.error_count,
                'entity_classes': result.entity_classes,
                'ttl_file': result.ttl_file,
                'message': f"Auto-commit complete: {result.linked_count} linked, {result.new_class_count} new classes"
            }

            # Include detailed results if requested
            if data.get('include_details', False) and result.results:
                response['results'] = [
                    {
                        'entity_id': r.entity_id,
                        'entity_label': r.entity_label,
                        'entity_type': r.entity_type,
                        'action': r.action,
                        'linked_uri': r.linked_uri,
                        'confidence': r.confidence,
                        'reasoning': r.reasoning,
                        'error': r.error
                    }
                    for r in result.results
                ]

            return jsonify(response)

        except Exception as e:
            logger.error(f"Error in auto-commit for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/auto_commit_status')
    @auth_optional
    def get_auto_commit_status(case_id):
        """
        Get the auto-commit status for a case.

        Returns information about entity matching status and Jaccard readiness.
        """
        try:
            from app.services.commit.auto_commit_service import AutoCommitService

            auto_commit_service = AutoCommitService()
            status = auto_commit_service.get_commit_status(case_id)

            return jsonify({
                'success': True,
                'status': status
            })

        except Exception as e:
            logger.error(f"Error getting auto-commit status for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/clear_ontology', methods=['POST'])
    @auth_required_for_write
    def clear_case_ontology(case_id):
        """
        Clear a case's OntServe ontology to prepare for re-extraction.

        This removes the case TTL file and resets committed entities,
        preventing circular matches when re-running extraction.

        Should be called before re-running extraction on a case that
        has already been committed to OntServe.
        """
        try:
            from app.services.commit.auto_commit_service import AutoCommitService

            data = request.get_json() or {}
            reset_committed = data.get('reset_committed', True)

            auto_commit_service = AutoCommitService()
            result = auto_commit_service.clear_case_ontology(case_id, reset_committed=reset_committed)

            return jsonify(result)

        except Exception as e:
            logger.error(f"Error clearing case ontology for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/search_ontserve')
    @auth_optional
    def search_ontserve_classes(case_id):
        """
        Search OntServe for matching classes.

        Used by the match details modal for manual linking.
        """
        try:
            from sqlalchemy import create_engine, text
            from app.services.ontserve.ontserve_config import get_ontserve_db_url

            query_param = request.args.get('q', '').strip()
            if not query_param:
                return jsonify({
                    'success': False,
                    'error': 'Search query required'
                }), 400

            # Search OntServe database for matching classes
            ontserve_engine = create_engine(get_ontserve_db_url())

            with ontserve_engine.connect() as conn:
                # Search by label (case-insensitive)
                search_query = text("""
                    SELECT uri, label, entity_type, comment
                    FROM ontology_entities
                    WHERE uri LIKE 'http://proethica.org/ontology/%'
                    AND (
                        LOWER(label) LIKE LOWER(:search_pattern)
                        OR LOWER(comment) LIKE LOWER(:search_pattern)
                    )
                    ORDER BY
                        CASE WHEN LOWER(label) = LOWER(:exact_match) THEN 0 ELSE 1 END,
                        label
                    LIMIT 20
                """)

                result = conn.execute(search_query, {
                    'search_pattern': f'%{query_param}%',
                    'exact_match': query_param
                })

                results = []
                for row in result:
                    results.append({
                        'uri': row[0],
                        'label': row[1],
                        'entity_type': row[2],
                        'description': row[3]
                    })

            return jsonify({
                'success': True,
                'query': query_param,
                'results': results,
                'count': len(results)
            })

        except Exception as e:
            logger.error(f"Error searching OntServe: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
