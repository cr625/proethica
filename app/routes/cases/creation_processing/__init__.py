"""Case-creation processing routes -- URL pipeline / manual / document, split by source."""
import os
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from app.utils.environment_auth import auth_required_for_write
from app.models import Document
from app.models.document import PROCESSING_STATUS
from app.models.world import World
from app.services.embedding.embedding_service import EmbeddingService
from app.services.entity.entity_triple_service import EntityTripleService
from app.services.case_url_processor import CaseUrlProcessor
from app.routes.cases.structure_embeddings import _sync_embeddings_to_precedent_features
from app import db

logger = logging.getLogger(__name__)

from app.routes.cases.creation_processing.url_manual_routes import register_creation_url_manual
from app.routes.cases.creation_processing.source_routes import register_creation_from_source


def register_creation_processing_routes(bp):
    register_creation_url_manual(bp)
    register_creation_from_source(bp)


# Back-compat re-export: cases/save_view.py lazily imports this helper from here.
from app.routes.cases.creation_processing.helpers import _build_case_html  # noqa: E402,F401

__all__ = ['register_creation_processing_routes', '_build_case_html']
