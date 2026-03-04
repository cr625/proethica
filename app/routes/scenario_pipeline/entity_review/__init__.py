"""
Entity Review Routes Package

Provides user interface for reviewing, editing, and approving extracted entities
before commitment to OntServe permanent storage.
"""

from flask import Blueprint

bp = Blueprint('entity_review', __name__)

from app.routes.scenario_pipeline.entity_review.review_views import register_review_view_routes
from app.routes.scenario_pipeline.entity_review.entity_mgmt import register_entity_mgmt_routes
from app.routes.scenario_pipeline.entity_review.ontserve_ops import register_ontserve_ops_routes
from app.routes.scenario_pipeline.entity_review.reconciliation import register_reconciliation_routes

register_review_view_routes(bp)
register_entity_mgmt_routes(bp)
register_ontserve_ops_routes(bp)
register_reconciliation_routes(bp)


def init_entity_review_csrf_exemption(app):
    """Exempt entity review API routes from CSRF protection since they're called via AJAX."""
    if hasattr(app, 'csrf') and app.csrf:
        try:
            csrf_exempt_views = [
                'entity_review.trigger_auto_commit',
                'entity_review.clear_case_ontology',
                'entity_review.set_entity_match',
                'entity_review.mark_entity_as_new',
                'entity_review.commit_entities_to_ontserve',
                'entity_review.clear_entities_by_types',
                'entity_review.clear_all_entities',
                'entity_review.delete_rdf_entity',
                'entity_review.reconcile_run',
                'entity_review.reconcile_merge',
                'entity_review.reconcile_unmerge',
                'entity_review.reconcile_keep_separate',
                'entity_review.reconcile_undo_keep_separate',
                'entity_review.reconcile_commit_execute',
                'entity_review.reconcile_uncommit',
            ]
            for view_name in csrf_exempt_views:
                app.csrf.exempt(view_name)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not exempt entity_review routes from CSRF: {e}")
