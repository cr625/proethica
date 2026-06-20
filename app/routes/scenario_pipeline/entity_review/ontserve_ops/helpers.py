"""Core-category resolution helper + the disjoint-category set."""
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


# The nine core components form an owl:AllDisjointClasses set.
_CORE_CATEGORIES = frozenset({
    'Role', 'Principle', 'Obligation', 'State', 'Resource',
    'Action', 'Event', 'Capability', 'Constraint',
})


def _resolve_class_core_category(class_uri):
    """Resolve an OntServe class URI to one of the nine core categories.

    Tries the curated category resolver first (covers core + intermediate +
    extended), then walks the OntServe ``parent_uri`` subClassOf chain for
    per-case classes the curated resolver does not know. Returns the core
    category name, or None when it genuinely cannot be determined (a class with
    no chain to a core component). Infrastructure errors are allowed to
    propagate so they surface rather than silently skipping the type check.
    """
    from app.services.extraction.category_resolver import resolve_core_category

    curated = resolve_core_category(class_uri)
    if curated:
        return curated

    from sqlalchemy import create_engine, text
    from app.services.ontserve.ontserve_config import get_ontserve_db_url

    engine = create_engine(get_ontserve_db_url())
    seen = set()
    current = class_uri
    with engine.connect() as conn:
        for _ in range(12):  # bounded walk; the subClassOf chain is shallow
            if not current or current in seen:
                break
            seen.add(current)
            local = current.rsplit('#', 1)[-1].rsplit('/', 1)[-1]
            if '/ontology/core#' in current and local in _CORE_CATEGORIES:
                return local
            row = conn.execute(
                text("SELECT parent_uri FROM ontology_entities "
                     "WHERE uri = :u AND parent_uri IS NOT NULL LIMIT 1"),
                {"u": current},
            ).fetchone()
            if not row:
                break
            current = row[0]
    return None
