"""JSON API for section term links. get_term_links_api returns SectionTermLink.get_document_term_links plus counts at /structure/api/term_links/<document_id>.."""
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


def register_api_routes(bp):
    @bp.route('/api/term_links/<int:document_id>')
    def get_term_links_api(document_id):
        """Get term links for a document as JSON."""
        try:
            # Get the document to verify it exists
            document = Document.query.get(document_id)
            if not document:
                return jsonify({'error': 'Document not found'}), 404
        
            # Get term links using the model's class method
            document_term_links = SectionTermLink.get_document_term_links(document_id)
        
            # Calculate some statistics
            total_links = sum(len(links) for links in document_term_links.values())
            sections_with_links = len(document_term_links)
        
            return jsonify({
                'success': True,
                'document_id': document_id,
                'sections_with_links': sections_with_links,
                'total_term_links': total_links,
                'term_links': document_term_links
            })
        
        except Exception as e:
            current_app.logger.error(f"Error retrieving term links for document {document_id}: {str(e)}")
            return jsonify({'error': str(e)}), 500
