"""Document-structure page plus structure-annotation generation. view_structure renders the main /structure/view page; generate_structure builds the structure annotations that feed it; generate_term_links is now a stub redirect back to the view (term recognition moved to OntServe). All three redirect to doc_structure.view_structure.."""
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


def register_view_routes(bp):
    @bp.route('/view/<int:id>', methods=['GET'])
    def view_structure(id):
        """View document structure for a specific case."""
        # Force a fresh load from the database to get the latest data
        # This ensures we see any recent updates from the generate_structure route
        db.session.close()
    
        # Get the document with a fresh query
        document = Document.query.get_or_404(id)
    
        # Check if it's a case
        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))
    
        # Get document metadata with explicit refresh
        metadata = {}
        if document.doc_metadata:
            if isinstance(document.doc_metadata, dict):
                metadata = document.doc_metadata
            else:
                # If it's not a dict (likely a string), try to parse it
                try:
                    metadata = json.loads(document.doc_metadata)
                except Exception:
                    logger.warning("Failed to parse document metadata", exc_info=True)
                    flash('Error parsing document metadata', 'warning')
                    metadata = {}
    
        # Check if document has structure information
        has_structure = False
        document_uri = None
        structure_triples = None
        section_metadata = None
        debug_info = {}
    
        # Add some debugging information
        debug_info['metadata_keys'] = list(metadata.keys()) if metadata else []
        debug_info['has_document_structure'] = 'document_structure' in metadata
    
        # Check for structure information in different possible locations
    
        # Case 1: Properly structured under document_structure
        if 'document_structure' in metadata:
            doc_struct = metadata['document_structure']
            debug_info['document_structure_keys'] = list(doc_struct.keys()) if doc_struct else []
        
            # Check if it has the essential components
            has_uri = 'document_uri' in doc_struct and doc_struct['document_uri']
            has_triples = 'structure_triples' in doc_struct and doc_struct['structure_triples']
        
            if has_uri and has_triples:
                has_structure = True
                document_uri = doc_struct.get('document_uri')
                structure_triples = doc_struct.get('structure_triples')
            else:
                # Structure data is incomplete
                debug_info['incomplete_structure'] = {
                    'has_uri': has_uri,
                    'has_triples': has_triples
                }
    
        # Case 2: Structure information at the top level (legacy format)
        elif 'document_uri' in metadata and 'structure_triples' in metadata:
            debug_info['structure_format'] = 'top_level'
            has_structure = True
            document_uri = metadata.get('document_uri')
            structure_triples = metadata.get('structure_triples')
    
        if 'section_embeddings_metadata' in metadata:
            section_metadata = metadata['section_embeddings_metadata']
    
        # Check for section embeddings
        has_section_embeddings = False
        section_embeddings_info = None
    
        # Add detailed logging for debugging section embeddings
        current_app.logger.info(f"Checking for section embeddings in document {id}")
    
        # First, check in document metadata (normal path)
        if 'document_structure' in metadata:
            current_app.logger.info(f"document_structure keys: {list(metadata['document_structure'].keys())}")
        
            # Check if any section has embeddings
            if 'sections' in metadata['document_structure']:
                sections = metadata['document_structure']['sections']
                sections_with_embeddings = [s for s in sections if 'embedding' in sections[s]]
                current_app.logger.info(f"Found {len(sections_with_embeddings)} sections with embeddings")
            
                # If sections have embeddings but section_embeddings key is missing, add it
                if sections_with_embeddings and 'section_embeddings' not in metadata['document_structure']:
                    current_app.logger.info("Fixing: Sections have embeddings but section_embeddings key is missing")
                
                    # Add the section_embeddings key
                    metadata['document_structure']['section_embeddings'] = {
                        'count': len(sections_with_embeddings),
                        'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
                    }
                
                    # Save the updated metadata
                    document.doc_metadata = metadata
                    db.session.commit()
                    current_app.logger.info("Added missing section_embeddings key to document metadata")
    
        # Now check if section_embeddings exists in document_structure
        if 'document_structure' in metadata and 'section_embeddings' in metadata['document_structure']:
            has_section_embeddings = True
            section_embeddings_info = metadata['document_structure']['section_embeddings']
            current_app.logger.info(f"Section embeddings info: {section_embeddings_info}")
        
            # Get list of sections with embeddings for display
            embedded_sections = []
            if 'sections' in metadata['document_structure']:
                sections = metadata['document_structure']['sections']
                if isinstance(sections, dict):
                    for section_id in sections.keys():
                        embedded_sections.append(section_id)
        
            # If no sections found in metadata, check DocumentSection table
            if not embedded_sections:
                from app.models.document_section import DocumentSection
                db_sections = DocumentSection.query.filter_by(document_id=id).all()
                embedded_sections = [section.section_type for section in db_sections]
        
            section_embeddings_info['sections'] = embedded_sections
        else:
            # Fallback: Check directly in the DocumentSection table
            from app.models.document_section import DocumentSection
        
            # Count sections for this document in the DocumentSection table
            doc_sections_count = DocumentSection.query.filter_by(document_id=id).count()
            current_app.logger.info(f"Fallback check: Found {doc_sections_count} sections in DocumentSection table")
        
            if doc_sections_count > 0:
                # We found sections in the table, but they're not reflected in the metadata
                # Update the document metadata and set has_section_embeddings
                has_section_embeddings = True
            
                # Get section types from database
                db_sections = DocumentSection.query.filter_by(document_id=id).all()
                embedded_sections = [section.section_type for section in db_sections]
            
                # Create section_embeddings_info for the template
                section_embeddings_info = {
                    'count': doc_sections_count,
                    'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    'storage_type': 'pgvector',
                    'note': 'Detected from database (metadata updated)',
                    'sections': embedded_sections
                }
            
                # Update the document metadata if needed
                if 'document_structure' not in metadata:
                    metadata['document_structure'] = {}
            
                # Add the section_embeddings info
                metadata['document_structure']['section_embeddings'] = section_embeddings_info
            
                # Save the updated metadata
                try:
                    document.doc_metadata = json.loads(json.dumps(metadata))
                    db.session.commit()
                    current_app.logger.info("Updated document metadata with section embeddings information from database")
                except Exception as e:
                    current_app.logger.warning(f"Failed to update metadata with section embeddings info: {str(e)}")
    
        # Check for guideline associations
        has_guideline_associations = False
        section_guideline_associations = None
    
        # Check if document has guideline associations in metadata
        if 'document_structure' in metadata and 'guideline_associations' in metadata['document_structure']:
            has_guideline_associations = True
            guideline_associations_info = metadata['document_structure']['guideline_associations']
            current_app.logger.info(f"Guideline associations info: {guideline_associations_info}")
        
            # Try to load guideline associations
            try:
                guideline_service = GuidelineSectionService()
                guidelines_result = guideline_service.get_document_section_guidelines(id)
                if guidelines_result.get('success') and guidelines_result.get('sections'):
                    section_guideline_associations = guidelines_result.get('sections')
                    current_app.logger.info(f"Loaded {len(section_guideline_associations)} sections with guideline associations")
            except Exception as e:
                current_app.logger.warning(f"Error loading guideline associations: {str(e)}")
    
        # Always load guideline associations from the service for up-to-date results
        guideline_service = GuidelineSectionService()
        section_guideline_associations = None
        has_guideline_associations = False
        try:
            guidelines_result = guideline_service.get_document_section_guidelines(id)
            if guidelines_result.get('success') and guidelines_result.get('sections'):
                section_guideline_associations = guidelines_result.get('sections')
                has_guideline_associations = True
                current_app.logger.info(f"Loaded {len(section_guideline_associations)} sections with guideline associations (forced refresh)")
        except Exception as e:
            current_app.logger.warning(f"Error loading guideline associations: {str(e)}")
        
        # Check for section-triple associations
        has_triple_associations = False
        section_triple_associations = None
    
        try:
            # Create the triple association storage
            triple_storage = SectionTripleAssociationStorage()
        
            # Get document sections and their associated triples
            document_associations = triple_storage.get_document_associations(id)
        
            if document_associations:
                has_triple_associations = True
                section_triple_associations = document_associations
                current_app.logger.info(f"Loaded section-triple associations for {len(document_associations)} sections")
        except Exception as e:
            current_app.logger.warning(f"Error loading section-triple associations: {str(e)}")


        # Check for ontology term links
        has_term_links = False
        section_term_links = None
    
        try:
            # Get term links for this document
            document_term_links = SectionTermLink.get_document_term_links(id)
        
            if document_term_links:
                has_term_links = True
                section_term_links = document_term_links
                total_term_links = sum(len(links) for links in document_term_links.values())
                current_app.logger.info(f"Loaded {total_term_links} term links across {len(document_term_links)} sections")
        except Exception as e:
            current_app.logger.warning(f"Error loading term links: {str(e)}")

        # Format structure triples if available
        structured_triples_data = None
        if has_structure and structure_triples:
            formatter = StructureTripleFormatter()
            structured_triples_data = formatter.parse_triples(structure_triples)
        
            # Add LLM-friendly format
            if 'error' not in structured_triples_data:
                structured_triples_data['llm_format'] = formatter.format_for_llm(structured_triples_data)
    
        # Add a timestamp query parameter to prevent browser caching
        no_cache = request.args.get('_', '')
    
        return render_template('document_structure.html', 
                              document=document,
                              has_structure=has_structure,
                              document_uri=document_uri,
                              structure_triples=structure_triples,
                              structured_triples_data=structured_triples_data,
                              section_metadata=section_metadata,
                              has_section_embeddings=has_section_embeddings,
                              section_embeddings_info=section_embeddings_info,
                              has_guideline_associations=has_guideline_associations,
                              section_guideline_associations=section_guideline_associations,
                              has_triple_associations=has_triple_associations,
                              section_triple_associations=section_triple_associations,
                              has_term_links=has_term_links,
                              section_term_links=section_term_links,
                              debug_info=debug_info,
                              no_cache=no_cache)
    @bp.route('/generate_structure/<int:id>', methods=['POST'])
    def generate_structure(id):
        """Generate document structure annotations for a document."""
        # Get the document
        document = Document.query.get_or_404(id)
    
        # Check if document already has structure - check multiple locations
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            metadata = document.doc_metadata
        
            # Check if properly structured
            if 'document_structure' in metadata and isinstance(metadata['document_structure'], dict) and \
               'document_uri' in metadata['document_structure'] and 'structure_triples' in metadata['document_structure']:
                flash("This document already has structure annotations.", "info")
                return redirect(url_for('doc_structure.view_structure', id=id))
            
            # Check if it has structure at the top level (legacy format)
            elif 'document_uri' in metadata and 'structure_triples' in metadata:
                # If found, organize it properly
                try:
                    # Create proper document_structure object
                    metadata['document_structure'] = {
                        'document_uri': metadata['document_uri'],
                        'structure_triples': metadata['structure_triples'],
                        'annotation_timestamp': metadata.get('structure_annotation_timestamp', datetime.utcnow().isoformat()),
                        'sections': {}  # Initialize empty sections
                    }
                
                    # Save reorganized metadata
                    document.doc_metadata = json.loads(json.dumps(metadata))
                    db.session.commit()
                
                    flash("Reorganized existing document structure to standard format.", "info")
                    return redirect(url_for('doc_structure.view_structure', id=id))
                except Exception as e:
                    current_app.logger.error(f"Error reorganizing structure: {str(e)}")
                    # We'll fall through and regenerate the structure
    
        try:
            # Get document metadata
            metadata = {}
            if document.doc_metadata:
                if isinstance(document.doc_metadata, dict):
                    metadata = document.doc_metadata
                else:
                    # If it's not a dict (likely a string), try to parse it
                    try:
                        metadata = json.loads(document.doc_metadata)
                    except Exception:
                        logger.warning("Failed to parse document metadata for annotation", exc_info=True)
                        flash('Error parsing document metadata', 'warning')
                        return redirect(url_for('doc_structure.view_structure', id=id))
        
            # Check if document has sections data
            if 'sections' not in metadata:
                flash("Document does not have the necessary section data for structure annotation.", "warning")
                return redirect(url_for('doc_structure.view_structure', id=id))
        
            # Prepare input data for document structure annotation step
            input_data = {
                'status': 'success',
                'case_number': metadata.get('case_number', ''),
                'year': metadata.get('year', ''),
                'title': document.title,
                'sections': metadata.get('sections', {}),
                'questions_list': metadata.get('questions_list', []),
                'conclusion_items': metadata.get('conclusion_items', [])
            }
        
            # Create and run document structure annotation step
            structure_step = DocumentStructureAnnotationStep()
            result = structure_step.process(input_data)
        
            if result.get('status') != 'success':
                flash(f"Failed to generate document structure: {result.get('message')}", "danger")
                return redirect(url_for('doc_structure.view_structure', id=id))
        
            # Update document metadata with structure information
            metadata['document_structure'] = {
                'document_uri': result['document_structure']['document_uri'],
                'structure_triples': result['document_structure']['structure_triples'],
                'annotation_timestamp': datetime.utcnow().isoformat(),
                'sections': result['document_structure'].get('sections', {})  # Use the sections from the pipeline result
            }
        
            # Add section embeddings metadata
            metadata['section_embeddings_metadata'] = result['section_embeddings_metadata']

            # Log the resulting structure for debugging
            current_app.logger.info(f"Generated document structure: {list(metadata['document_structure'].keys())}")
        
            # Ensure we're making a deep copy of any nested structures to prevent reference issues
            document.doc_metadata = json.loads(json.dumps(metadata))
        
            # Make sure changes are committed to the database
            db.session.flush()
            db.session.commit()
        
            # Force reload the document to verify changes were saved
            db.session.refresh(document)
        
            # Verify document structure was saved correctly
            if 'document_structure' in document.doc_metadata:
                flash(f"Successfully generated document structure with {len(result['document_structure'].get('graph', []))} triples", "success")
            else:
                flash("Generated document structure, but had issues saving to database. Please try again.", "warning")
    
        except Exception as e:
            flash(f"Error generating document structure: {str(e)}", "danger")
    
        # Force a new database fetch on redirect
        return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))
    @bp.route('/generate_term_links/<int:id>', methods=['POST'])
    def generate_term_links(id):
        """Generate ontology term links for a document."""
        # Get the document
        document = Document.query.get(id)
        if not document:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({
                    'success': False,
                    'message': 'Document not found'
                }), 404
            else:
                abort(404)
    
        # Ontology term recognition moved to OntServe; the former local service was
        # a stub with no loaded terms, so this route never produced links. Surface
        # that cleanly instead of attempting the unavailable operation.
        error_msg = "Ontology term recognition has moved to OntServe; term links are not generated here."
        current_app.logger.info(error_msg)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({
                'success': False,
                'message': error_msg
            }), 500
        else:
            flash(error_msg, 'warning')

        # Add timestamp to prevent caching
        return redirect(url_for('doc_structure.view_structure', id=id, _=datetime.utcnow().timestamp()))
