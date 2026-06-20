"""Guideline and ontology-concept association lifecycle. associate_guidelines and associate_ontology_concepts start associations (the latter via the async BackgroundTaskQueue), association_progress polls async progress, and clear_associations deletes case_guideline_associations rows plus metadata.."""
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


def register_association_routes(bp):
    @bp.route('/associate_guidelines/<int:id>', methods=['POST'])
    def associate_guidelines(id):
        """Associate ethical guidelines with document sections."""
        # Get the document
        document = Document.query.get_or_404(id)
    
        try:
            # Create the guideline service
            guideline_service = GuidelineSectionService()
        
            # Process document sections
            result = guideline_service.associate_guidelines_with_sections(document.id)
        
            if result.get('success'):
                flash(f"Successfully created {result.get('associations_created', 0)} guideline associations across {result.get('sections_processed', 0)} sections", 'success')
            else:
                error_msg = result.get('error', 'Unknown error')
                flash(f"Error associating guidelines: {error_msg}", 'danger')
    
        except Exception as e:
            flash(f"Error processing section guideline associations: {str(e)}", 'danger')
    
        # Add timestamp to prevent caching
        return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))
    @bp.route('/associate_ontology_concepts/<int:id>', methods=['POST'])
    def associate_ontology_concepts(id):
        """Associate ontology concepts with document sections using enhanced service."""
        current_app.logger.info(f"🔥 ENHANCED ROUTE HIT: POST to associate_ontology_concepts/{id}")
        current_app.logger.info(f"🔥 Form data: {dict(request.form)}")
        current_app.logger.info(f"🔥 Request method: {request.method}")
        # Try to get the document - could be stored as Document or Scenario
        document = Document.query.get(id)
        if not document:
            # Try as Scenario (cases are sometimes stored as scenarios)
            from app.models.scenario import Scenario
            document = Scenario.query.get_or_404(id)
            # For scenarios, we need to use scenario_metadata instead of doc_metadata
            metadata_field = 'scenario_metadata'
        else:
            metadata_field = 'doc_metadata'
    
        # Get association method from form
        association_method = request.form.get('association_method', 'embedding')
    
        try:
            # Use async processing instead of synchronous
            from app.services.task_queue import BackgroundTaskQueue
        
            task_queue = BackgroundTaskQueue.get_instance()
        
            # Initialize processing status in document metadata
            if not document.doc_metadata:
                document.doc_metadata = {}
        
            # Check if already processing
            current_status = document.doc_metadata.get('association_processing_status')
            if current_status == 'processing':
                flash("Associations are already being processed for this document. Please wait for completion.", "info")
                return redirect(url_for('doc_structure.view_structure', id=id))
        
            # Start async processing
            success = task_queue.process_associations_async(id, association_method)
        
            if success:
                # Initialize status
                document.doc_metadata['association_processing_status'] = 'pending'
                document.doc_metadata['association_processing_progress'] = 0
                document.doc_metadata['association_processing_phase'] = 'initializing'
                db.session.commit()
            
                current_app.logger.info(f"Started async association processing for document {id} with {association_method} method")
                flash(f"Association processing started using {association_method} method. This may take 2-3 minutes. The page will show progress updates.", "info")
            else:
                flash("Failed to start association processing. Please try again.", "error")
            
        except Exception as e:
            current_app.logger.exception(f"Error associating ontology concepts: {str(e)}")
            flash(f"Error associating ontology concepts: {str(e)}", "danger")
    
        # Add timestamp to prevent caching
        return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))
    @bp.route('/association_progress/<int:id>', methods=['GET'])
    def association_progress(id):
        """Get association processing progress for a document."""
        try:
            # Force refresh from database to avoid session isolation issues
            db.session.expire_all()
            document = Document.query.get_or_404(id)
            db.session.refresh(document)
        
            if not document.doc_metadata:
                return jsonify({
                    'status': 'not_started',
                    'progress': 0,
                    'phase': 'none'
                })
        
            status = document.doc_metadata.get('association_processing_status', 'not_started')
            progress = document.doc_metadata.get('association_processing_progress', 0)
            phase = document.doc_metadata.get('association_processing_phase', 'none')
            error = document.doc_metadata.get('association_processing_error')
            results = document.doc_metadata.get('association_results')
        
            # Fallback: Check if associations actually exist (workaround for session isolation issue)
            if status == 'not_started':
                try:
                    # Query the associations table directly (using correct column name: case_id)
                    from sqlalchemy import text
                    result = db.session.execute(
                        text("SELECT COUNT(*) FROM case_guideline_associations WHERE case_id = :case_id"),
                        {"case_id": id}
                    ).scalar()
                
                    if result and result > 0:
                        status = 'completed'
                        progress = 100
                        phase = 'completed'
                        # Try to get results from associations if not in metadata
                        if not results:
                            results = {
                                'total_associations': result,
                                'method_used': 'hybrid',
                                'processed_at': 'recently'
                            }
                except Exception as e:
                    current_app.logger.error(f"Error checking existing associations: {e}")
        
            response = {
                'status': status,
                'progress': progress,
                'phase': phase
            }
        
            if error:
                response['error'] = error
            
            if results:
                response['results'] = results
            
            return jsonify(response)
        
        except Exception as e:
            current_app.logger.error(f"Error getting association progress: {str(e)}")
            return jsonify({
                'status': 'error',
                'error': str(e)
            }), 500
    @bp.route('/clear_associations/<int:id>', methods=['POST'])
    def clear_associations(id):
        """Clear enhanced guideline associations for a document."""
        current_app.logger.info(f"Clearing enhanced associations for document {id}")
    
        try:
            # Clear from database
            from sqlalchemy import text
            with db.engine.connect() as conn:
                result = conn.execute(
                    text("DELETE FROM case_guideline_associations WHERE case_id = :case_id"),
                    {"case_id": id}
                )
                deleted_count = result.rowcount
                conn.commit()
        
            # Clear from document metadata if it exists
            document = Document.query.get(id)
            if not document:
                # Try as Scenario
                from app.models.scenario import Scenario
                document = Scenario.query.get(id)
                metadata_field = 'scenario_metadata'
            else:
                metadata_field = 'doc_metadata'
            
            if document:
                metadata = getattr(document, metadata_field) or {}
                if isinstance(metadata, dict):
                    if 'document_structure' in metadata and 'enhanced_associations' in metadata['document_structure']:
                        del metadata['document_structure']['enhanced_associations']
                        setattr(document, metadata_field, json.loads(json.dumps(metadata)))
                        db.session.commit()
        
            success_message = f"Cleared {deleted_count} enhanced associations"
            current_app.logger.info(success_message)
        
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': True,
                    'message': success_message,
                    'deleted_count': deleted_count
                })
            else:
                flash(success_message, 'success')
            
        except Exception as e:
            error_message = f"Error clearing associations: {str(e)}"
            current_app.logger.error(error_message)
        
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': error_message
                }), 500
            else:
                flash(error_message, 'danger')
    
        # Add timestamp to prevent caching for clear route
        return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))
