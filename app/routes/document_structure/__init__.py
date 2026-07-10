"""Document-structure blueprint package -- view, embedding, ontology-association, API routes."""
import os
import sys
import json
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, jsonify, request, current_app, abort
from flask_sqlalchemy import SQLAlchemy
from app.models import Document
from app.models.scenario import Scenario
from app.models.document_section import DocumentSection
from app.models.section_term_link import SectionTermLink
from app.services.embedding.section_embedding_service import SectionEmbeddingService
from app.services.guideline_section_service import GuidelineSectionService 
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
from app.services.structure_triple_formatter import StructureTripleFormatter
from datetime import datetime
from app import db

# Import the section triple association service
from app.services.ttl_triple_association.section_triple_association_service import SectionTripleAssociationService
from app.services.ttl_triple_association.section_triple_association_storage import SectionTripleAssociationStorage

logger = logging.getLogger(__name__)

doc_structure_bp = Blueprint('doc_structure', __name__, url_prefix='/structure')

from app.routes.document_structure.view_routes import register_view_routes
from app.routes.document_structure.embedding_routes import register_embedding_routes
from app.routes.document_structure.api_routes import register_api_routes

register_view_routes(doc_structure_bp)
register_embedding_routes(doc_structure_bp)
register_api_routes(doc_structure_bp)


def init_doc_structure_csrf_exemption(app):
    """Exempt document structure routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        for endpoint in ('doc_structure.generate_structure', 'doc_structure.generate_embeddings'):
            view = app.view_functions.get(endpoint)
            if view is not None:
                app.csrf.exempt(view)

__all__ = ["doc_structure_bp", "init_doc_structure_csrf_exemption"]
