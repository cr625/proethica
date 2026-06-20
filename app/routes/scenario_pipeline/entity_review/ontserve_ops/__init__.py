"""OntServe entity-review ops -- split into extraction/commit, auto-commit/search, and entity-matching groups."""
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

from app.routes.scenario_pipeline.entity_review.ontserve_ops.extraction_ops import register_ontserve_extraction_ops
from app.routes.scenario_pipeline.entity_review.ontserve_ops.commit_search_ops import register_ontserve_commit_search_ops
from app.routes.scenario_pipeline.entity_review.ontserve_ops.matching_ops import register_ontserve_matching_ops


def register_ontserve_ops_routes(bp):
    register_ontserve_extraction_ops(bp)
    register_ontserve_commit_search_ops(bp)
    register_ontserve_matching_ops(bp)


# Back-compat re-export: tests + callers access these via the ontserve_ops module directly.
from app.routes.scenario_pipeline.entity_review.ontserve_ops.helpers import _CORE_CATEGORIES, _resolve_class_core_category  # noqa: E402,F401

__all__ = ['register_ontserve_ops_routes', '_CORE_CATEGORIES', '_resolve_class_core_category']
