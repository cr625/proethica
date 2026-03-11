from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
from app.utils.environment_auth import (
    auth_required_for_write,
)
import json
import os
import logging
from werkzeug.utils import secure_filename
from app import db
from app.models.world import World
from app.models.ontology import Ontology
from app.models import Document
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.services.guideline_concept_integration_service import GuidelineConceptIntegrationService

from app.routes.worlds.helpers import robust_json_parse

logger = logging.getLogger(__name__)

guideline_analysis_service = GuidelineAnalysisService()


def register_guideline_routes(bp):
    # Guidelines routes
    @bp.route('/<int:id>/guidelines', methods=['GET'])
    def world_guidelines(id):
        """Display guidelines for a world."""
        world = World.query.get_or_404(id)

        # Get all guidelines documents for this world
        from app.models.guideline import Guideline
        from app.models.ontology import Ontology
        guidelines = Guideline.query.filter_by(world_id=world.id).all()

        # Check for derived ontologies for each guideline
        guideline_ontologies = {}
        for guideline in guidelines:
            derived_domain = f"guideline-{guideline.id}-concepts"
            derived_ontology = Ontology.query.filter_by(domain_id=derived_domain).first()
            if derived_ontology:
                guideline_ontologies[guideline.id] = {
                    'exists': True,
                    'id': derived_ontology.id,
                    'name': derived_ontology.name
                }

        return render_template('guidelines.html', world=world, guidelines=guidelines, guideline_ontologies=guideline_ontologies)

    @bp.route('/<int:id>/guidelines/<int:document_id>/sections')
    def view_guideline_sections(id, document_id):
        """Display extracted provisions/sections from a guideline."""
        world = World.query.get_or_404(id)

        from app.models.guideline import Guideline
        from app.models.guideline_section import GuidelineSection

        # Use Guideline model directly (consistent with view_guideline route)
        guideline = Guideline.query.get_or_404(document_id)

        # Check if guideline belongs to this world
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Get guideline sections directly by guideline ID
        sections = GuidelineSection.query.filter_by(
            guideline_id=guideline.id
        ).order_by(GuidelineSection.section_order, GuidelineSection.section_code).all()

        # Group sections by category with proper display names
        category_display_names = {
            'fundamental_canons': 'Fundamental Canons',
            'rules_of_practice': 'Rules of Practice',
            'professional_obligations': 'Professional Obligations',
            'generic': 'General Provisions'
        }

        sections_by_category = {}
        for section in sections:
            category = section.section_category or 'generic'
            display_name = category_display_names.get(category, category.replace('_', ' ').title())
            if display_name not in sections_by_category:
                sections_by_category[display_name] = []
            sections_by_category[display_name].append(section)

        # Build provision lookup dictionary for tooltips
        provision_lookup = {}
        for section in sections:
            cat = section.section_category or 'generic'
            cat_label = category_display_names.get(cat, cat.replace('_', ' ').title())
            provision_lookup[section.section_code] = {
                'code': section.section_code,
                'title': section.section_title or f'Section {section.section_code}',
                'text': section.section_text,
                'category': cat,
                'category_label': cat_label,
                'subcategory': section.section_subcategory or '',
                'establishes': (section.section_metadata or {}).get('establishes', []),
                'source_guideline': guideline.title
            }

        return render_template('guideline_sections_view.html',
                             world=world,
                             document=guideline,
                             sections=sections,
                             sections_by_category=sections_by_category,
                             provision_lookup=provision_lookup,
                             guideline_id=guideline.id)

    @bp.route('/<int:id>/guidelines/<int:document_id>/sections/regenerate', methods=['POST'])
    @login_required
    def regenerate_guideline_sections(id, document_id):
        """Regenerate extracted sections for a guideline."""
        world = World.query.get_or_404(id)

        from app.models.guideline import Guideline
        from app.services.guideline_structure_annotation_step import GuidelineStructureAnnotationStep

        guideline = Guideline.query.get_or_404(document_id)

        # Validate ownership
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        try:
            # Run section extraction directly on the guideline
            annotator = GuidelineStructureAnnotationStep()
            result = annotator.process(guideline)
            if result.get('success'):
                flash(f'Successfully extracted {result.get("sections_created", 0)} provisions.', 'success')
            else:
                flash(f'Section extraction failed: {result.get("error", "Unknown error")}', 'error')
        except Exception as e:
            logger.error(f"Error regenerating sections: {e}")
            flash(f'Error regenerating sections: {str(e)}', 'error')

        return redirect(url_for('worlds.view_guideline_sections', id=world.id, document_id=guideline.id))

    @bp.route('/<int:id>/guidelines/<int:document_id>', methods=['GET'])
    def view_guideline(id, document_id):
        """Display a specific guideline."""
        world = World.query.get_or_404(id)

        from app.models.guideline import Guideline
        guideline = Guideline.query.get_or_404(document_id)

        # Check if guideline belongs to this world
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))
            flash('Document is not a guideline', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Get associated concepts and triples
        from app.models.entity_triple import EntityTriple
        from app.models.guideline import Guideline

        # Initialize variables with default values
        triple_count = 0
        concept_count = 0
        triples = []
        concepts = []

        # Try to get related guideline if exists
        related_guideline = None
        if guideline.guideline_metadata and 'guideline_id' in guideline.guideline_metadata:
            try:
                guideline_id = guideline.guideline_metadata['guideline_id']
                related_guideline = Guideline.query.get(guideline_id)

                # If related guideline exists, get its triples
                if related_guideline:
                    triples = EntityTriple.query.filter_by(
                        guideline_id=related_guideline.id,
                        entity_type="guideline_concept"
                    ).all()
                    triple_count = len(triples)

                    # Get concept count from metadata if available
                    if related_guideline.guideline_metadata and 'concepts_selected' in related_guideline.guideline_metadata:
                        concept_count = related_guideline.guideline_metadata['concepts_selected']

                    # Get concepts from guideline metadata if available
                    concepts = []
                    if related_guideline.guideline_metadata and 'concepts' in related_guideline.guideline_metadata:
                        concepts = related_guideline.guideline_metadata['concepts']
                        logger.info(f"Retrieved {len(concepts)} concepts from guideline metadata")
            except Exception as e:
                import traceback
                traceback.print_exc()
                logger.error(f'Error retrieving guideline data: {str(e)}')
                flash(f'Error retrieving guideline data: {str(e)}', 'warning')

        # If no related guideline or metadata available, try to get counts from guideline metadata
        if triple_count == 0 and guideline.guideline_metadata:
            if 'triples_created' in guideline.guideline_metadata:
                triple_count = guideline.guideline_metadata['triples_created']
            if 'concepts_selected' in guideline.guideline_metadata:
                concept_count = guideline.guideline_metadata['concepts_selected']
            elif 'concepts_extracted' in guideline.guideline_metadata:
                concept_count = guideline.guideline_metadata['concepts_extracted']

        # Check for pending concept extractions in temporary storage
        pending_extraction = {'has_pending': False, 'session_id': None, 'concept_count': 0, 'extraction_date': None}
        try:
            from app.services.temporary_concept_service import TemporaryConceptService
            session_id = TemporaryConceptService.get_latest_session_for_document(
                document_id=document_id,
                world_id=id
            )

            if session_id:
                # Get concepts from any status (pending, reviewed, etc.)
                temp_concepts = TemporaryConceptService.get_session_concepts(session_id)
                if temp_concepts:
                    pending_extraction = {
                        'has_pending': True,
                        'session_id': session_id,
                        'concept_count': len(temp_concepts),
                        'extraction_date': temp_concepts[0].extraction_timestamp.strftime('%Y-%m-%d %H:%M') if temp_concepts[0].extraction_timestamp else None,
                        'status': temp_concepts[0].status
                    }
                    logger.info(f"Found {len(temp_concepts)} temporary concepts for document {document_id}")
        except Exception as e:
            logger.warning(f"Could not check temporary concepts: {str(e)}")

        # Check if concepts have been saved to ontology from metadata
        concepts_saved_to_ontology = False
        if guideline.guideline_metadata and guideline.guideline_metadata.get('concepts_saved_to_ontology', False):
            concepts_saved_to_ontology = True
            logger.info(f"Guideline {document_id} has concepts already saved to ontology")

        # Check if concepts have been added to the ontology
        # Use document_id for consistent naming/linking with derived ontologies
        ontology_status = {'ready_to_add': False}
        if related_guideline:
            try:
                ontology_status = GuidelineConceptIntegrationService.check_concepts_added_to_ontology(
                    guideline_id=document_id,  # Use document ID that matches the URL
                    ontology_domain='engineering-ethics'
                )
            except Exception as e:
                logger.warning(f"Could not check ontology status: {str(e)}")

        # Check if annotations exist and get statistics
        from app.models.document_concept_annotation import DocumentConceptAnnotation
        annotations_query = DocumentConceptAnnotation.query.filter_by(
            document_type='guideline',
            document_id=document_id,
            is_current=True
        )
        annotation_count = annotations_query.count()

        # Get annotation statistics if they exist
        annotation_stats = {}
        if annotation_count > 0:
            all_annotations = annotations_query.all()

            # Count by method
            method_counts = {}
            ontology_counts = {}
            for ann in all_annotations:
                method = ann.concept_type or 'basic'
                method_counts[method] = method_counts.get(method, 0) + 1

                ontology = ann.ontology_name or 'unknown'
                ontology_counts[ontology] = ontology_counts.get(ontology, 0) + 1

            # Get latest annotation date
            latest_annotation = annotations_query.order_by(
                DocumentConceptAnnotation.created_at.desc()
            ).first()

            annotation_stats = {
                'total': annotation_count,
                'methods': method_counts,
                'ontologies': ontology_counts,
                'latest_date': latest_annotation.created_at if latest_annotation else None,
                'approved': annotations_query.filter_by(validation_status='approved').count(),
                'pending': annotations_query.filter_by(validation_status='pending').count()
            }

        return render_template('guideline_content.html',
                              world=world,
                              guideline=guideline,
                              triple_count=triple_count,
                              concept_count=concept_count,
                              triples=triples,
                              concepts=concepts,
                              ontology_status=ontology_status,
                              pending_extraction=pending_extraction,
                              concepts_saved_to_ontology=concepts_saved_to_ontology,
                              annotation_count=annotation_count,
                              annotation_stats=annotation_stats)

    @bp.route('/<int:id>/guidelines/<int:document_id>/annotations')
    def view_guideline_annotations(id, document_id):
        """Simple view of extracted annotations for a guideline."""
        world = World.query.get_or_404(id)

        from app.models.guideline import Guideline
        from app.models.document_concept_annotation import DocumentConceptAnnotation

        guideline = Guideline.query.get_or_404(document_id)

        # Check if guideline belongs to this world
        if guideline.world_id != world.id:
            flash('Guideline does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Get all annotations for this guideline
        annotations = DocumentConceptAnnotation.query.filter_by(
            document_type='guideline',
            document_id=document_id,
            is_current=True
        ).order_by(
            DocumentConceptAnnotation.ontology_name,
            DocumentConceptAnnotation.concept_label
        ).all()

        # Group annotations by ontology
        annotations_by_ontology = {}
        for annotation in annotations:
            ontology = annotation.ontology_name or 'unknown'
            if ontology not in annotations_by_ontology:
                annotations_by_ontology[ontology] = []
            annotations_by_ontology[ontology].append(annotation)

        # Get stats
        total_annotations = len(annotations)
        ontology_count = len(annotations_by_ontology)

        # Count by annotation method
        method_counts = {}
        for annotation in annotations:
            method = annotation.concept_type or 'basic'
            method_counts[method] = method_counts.get(method, 0) + 1

        return render_template('guideline_annotations.html',
                              world=world,
                              guideline=guideline,
                              annotations=annotations,
                              annotations_by_ontology=annotations_by_ontology,
                              total_annotations=total_annotations,
                              ontology_count=ontology_count,
                              method_counts=method_counts)

    @bp.route('/<int:id>/guidelines/<int:document_id>/analyze', methods=['GET', 'POST'])
    def analyze_guideline(id, document_id):
        """Analyze a guideline document and extract ontology concepts."""
        # Import the direct extraction function
        from app.routes.worlds.direct_concepts import direct_concept_extraction
        from app.services.role_property_suggestions import RolePropertySuggestionsService

        # Get world object
        world = World.query.get_or_404(id)

        # Call the direct extraction function
        return direct_concept_extraction(id, document_id, world, guideline_analysis_service)

    @bp.route('/<int:id>/guidelines/<int:document_id>/match_existing_concepts', methods=['GET'])
    def match_existing_concepts(id, document_id):
        """Match guideline concepts to existing engineering-ethics ontology entities."""
        try:
            # Get world and guideline
            world = World.query.get_or_404(id)
            guideline = Document.query.get_or_404(document_id)

            # Check if document belongs to this world and is a guideline
            if guideline.world_id != world.id:
                flash('Document does not belong to this world', 'error')
                return redirect(url_for('worlds.view_world', id=world.id))

            if guideline.document_type != "guideline":
                flash('Document is not a guideline', 'error')
                return redirect(url_for('worlds.view_world', id=world.id))

            # Get guideline content
            content = guideline.content
            if not content and guideline.file_path:
                try:
                    with open(guideline.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                except Exception as e:
                    flash(f'Error reading guideline file: {str(e)}', 'error')
                    return redirect(url_for('worlds.view_world', id=world.id))

            if not content:
                flash('No content available for analysis', 'error')
                return redirect(url_for('worlds.view_world', id=world.id))

            # Initialize services
            from app.services.guideline_analysis_service import GuidelineAnalysisService
            from app.services.mcp_client import MCPClient

            analysis_service = GuidelineAnalysisService()
            mcp_client = MCPClient.get_instance()

            # Step 1: Extract concepts from guideline text
            logger.info(f"Extracting concepts from guideline: {guideline.title}")
            extraction_result = analysis_service.extract_concepts(content, document_id, id)

            if 'error' in extraction_result:
                flash(f'Error extracting concepts: {extraction_result["error"]}', 'error')
                return redirect(url_for('worlds.view_world', id=world.id))

            extracted_concepts = extraction_result.get('concepts', [])
            logger.info(f"Extracted {len(extracted_concepts)} concepts")

            # Step 2: Get existing ontology entities via MCP
            logger.info("Fetching existing ontology entities from MCP server")
            try:
                entities_response = mcp_client.get_ontology_entities('engineering-ethics')
                raw_entities = entities_response.get('entities', []) if entities_response else []
                existing_entities = raw_entities if isinstance(raw_entities, list) else list(raw_entities.values())
                logger.info(f"Retrieved {len(existing_entities)} existing ontology entities")
            except Exception as e:
                logger.error(f"Error fetching ontology entities: {e}")
                existing_entities = []

            # Step 3: Focus on roles and match to existing ontology
            role_concepts = [c for c in extracted_concepts if c.get('type', '').lower() == 'role']
            existing_roles = [e for e in existing_entities if e.get('type', '').lower() == 'role']

            # Build lookup for existing roles
            role_lookup = {}
            for role in existing_roles:
                label = role.get('label', '').lower().strip()
                role_lookup[label] = role
                # Also try without " role" suffix
                if label.endswith(' role'):
                    role_lookup[label[:-5].strip()] = role

            # Match extracted roles to existing ontology
            matched_roles = []
            unmatched_roles = []

            for concept in role_concepts:
                concept_label = concept.get('label', '').lower().strip()

                # Try exact match
                if concept_label in role_lookup:
                    matched_entity = role_lookup[concept_label]
                    concept['ontology_match'] = {
                        'found': True,
                        'entity': matched_entity,
                        'match_type': 'exact'
                    }
                    matched_roles.append(concept)
                # Try without "role" suffix
                elif concept_label.endswith(' role') and concept_label[:-5].strip() in role_lookup:
                    matched_entity = role_lookup[concept_label[:-5].strip()]
                    concept['ontology_match'] = {
                        'found': True,
                        'entity': matched_entity,
                        'match_type': 'without_suffix'
                    }
                    matched_roles.append(concept)
                else:
                    concept['ontology_match'] = {'found': False}
                    unmatched_roles.append(concept)

            logger.info(f"Role matching results: {len(matched_roles)} matched, {len(unmatched_roles)} unmatched")

            return render_template('existing_concept_matches.html',
                                 world=world,
                                 guideline=guideline,
                                 matched_roles=matched_roles,
                                 unmatched_roles=unmatched_roles,
                                 total_roles=len(role_concepts),
                                 total_existing_roles=len(existing_roles))

        except Exception as e:
            logger.error(f"Error in match_existing_concepts: {str(e)}")
            flash(f'Error matching concepts: {str(e)}', 'error')
            return redirect(url_for('worlds.view_world', id=id))

    @bp.route('/<int:id>/guidelines/<int:document_id>/extract_concepts', methods=['GET'])
    def extract_and_display_concepts(id, document_id):
        """Extract concepts from a guideline using MCP server and display them."""
        try:
            # Import the direct concept extraction function
            from app.routes.worlds.direct_concepts import direct_concept_extraction
            # Reset any failed transaction state before starting DB work
            try:
                from app import db
                db.session.rollback()
            except Exception:
                pass

            world = World.query.get_or_404(id)

            logger.info(f"Attempting to extract concepts for world {id}, document {document_id}")

            # Call the direct concept extraction function
            return direct_concept_extraction(id, document_id, world, guideline_analysis_service)

        except Exception as e:
            logger.exception(f"Error in extract_and_display_concepts for world {id}, document {document_id}: {str(e)}")
            flash(f'Unexpected error extracting concepts: {str(e)}', 'error')
            return redirect(url_for('worlds.world_guidelines', id=id))

    @bp.route('/<int:id>/guidelines/<int:document_id>/analyze_legacy', methods=['POST'])
    def analyze_guideline_legacy(id, document_id):
        """Legacy analyze route that uses the direct LLM-based concept extraction."""
        from app.routes.worlds.extraction import extract_concepts_direct

        # Log that legacy route is being used
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Using legacy direct concept extraction for world {id}, document {document_id}")

        # Call the direct extraction function
        return extract_concepts_direct(id, document_id)

    # Comprehensive error handling for guideline processing
    @bp.route('/<int:world_id>/guidelines/<int:document_id>/error', methods=['GET'])
    def guideline_processing_error(world_id, document_id):
        """Display error page for guideline processing problems."""
        try:
            world = World.query.get_or_404(world_id)

            from app.models import Document
            guideline = Document.query.get_or_404(document_id)

            # Check if document belongs to this world
            if guideline.world_id != world.id:
                flash('Document does not belong to this world', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Get error details from query parameters
            error_title = request.args.get('error_title', 'Processing Error')
            error_message = request.args.get('error_message', 'An error occurred while processing the guideline concepts.')
            error_details = request.args.get('error_details', '')

            # Log the error for debugging purposes
            logger.error(f"Guideline processing error: {error_title} - {error_message}")
            if error_details:
                logger.debug(f"Error details: {error_details[:500]}..." if len(error_details) > 500 else error_details)

            return render_template('guideline_processing_error.html',
                                  world=world,
                                  guideline=guideline,
                                  error_title=error_title,
                                  error_message=error_message,
                                  error_details=error_details)
        except Exception as e:
            # Fallback error handling if the error page itself has an error
            logger.exception(f"Error in error handler: {str(e)}")
            flash(f"An unexpected error occurred: {str(e)}", "error")
            return redirect(url_for('worlds.list_worlds'))

    @bp.route('/<int:id>/guidelines/add', methods=['GET'])
    @login_required
    def add_guideline_form(id):
        """Display form to add a guideline to a world."""
        world = World.query.get_or_404(id)

        # Get referrer URL for redirect after submission
        referrer = request.referrer or url_for('worlds.world_guidelines', id=world.id)

        return render_template('add_guideline.html', world=world, referrer=referrer)

    @bp.route('/<int:id>/guidelines/add', methods=['POST'])
    @login_required
    def add_guideline(id):
        """Process form submission to add a guideline to a world."""
        world = World.query.get_or_404(id)

        # Get form data
        title = request.form.get('guidelines_title', f"Guidelines for {world.name}")
        input_type = request.form.get('input_type')

        # Import Document model and task queue
        from app.models import Document
        from app.models.document import PROCESSING_STATUS
        from app.services.task_queue import BackgroundTaskQueue
        task_queue = BackgroundTaskQueue.get_instance()

        # Process based on input type
        if input_type == 'file' and 'guidelines_file' in request.files:
            file = request.files['guidelines_file']
            if file and file.filename:
                # Check if file type is allowed
                if '.' in file.filename and file.filename.rsplit('.', 1)[1].lower() in {'pdf', 'docx', 'txt', 'html', 'htm'}:
                    # Configure upload folder
                    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'uploads')
                    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

                    # Save file
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)

                    # Get file type
                    file_type = filename.rsplit('.', 1)[1].lower()

                    # Create guideline record
                    from app.models.guideline import Guideline
                    guideline = Guideline(
                        title=title,
                        world_id=world.id,
                        file_path=file_path,
                        file_type=file_type,
                        guideline_metadata={},
                        created_by=current_user.id,
                        data_type='user'
                    )
                    db.session.add(guideline)
                    db.session.commit()

                    # Read and store content from file
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            guideline.content = f.read()
                        db.session.commit()
                    except Exception as e:
                        logger.error(f"Error reading guideline file: {e}")

                    flash('Guideline uploaded successfully', 'success')
                else:
                    flash('File type not allowed. Allowed types: pdf, docx, txt, html, htm', 'error')
                    return redirect(url_for('worlds.add_guideline_form', id=world.id))

        elif input_type == 'url':
            guidelines_url = request.form.get('guidelines_url', '').strip()
            if guidelines_url:
                # Create guideline record for URL
                from app.models.guideline import Guideline
                guideline = Guideline(
                    title=title,
                    world_id=world.id,
                    source_url=guidelines_url,
                    file_type="url",
                    guideline_metadata={},
                    created_by=current_user.id,
                    data_type='user'
                )
                db.session.add(guideline)
                db.session.commit()

                # Fetch content from URL
                try:
                    import requests
                    response = requests.get(guidelines_url, timeout=30)
                    response.raise_for_status()
                    guideline.content = response.text
                    db.session.commit()
                except Exception as e:
                    logger.error(f"Error fetching guideline from URL: {e}")
                flash('Guidelines URL uploaded and processing started', 'success')
            else:
                flash('URL is required', 'error')
                return redirect(url_for('worlds.add_guideline_form', id=world.id))

        elif input_type == 'text':
            guidelines_text = request.form.get('guidelines_text', '').strip()
            if guidelines_text:
                # Create guideline record directly (not as a Document)
                from app.models.guideline import Guideline
                guideline = Guideline(
                    title=title,
                    world_id=world.id,
                    content=guidelines_text,
                    file_type="txt",
                    guideline_metadata={},
                    created_by=current_user.id,
                    data_type='user'
                )
                db.session.add(guideline)
                db.session.commit()

                # Process guideline structure extraction
                try:
                    from app.services.guideline_structure_annotation_step import GuidelineStructureAnnotationStep
                    structure_annotator = GuidelineStructureAnnotationStep()
                    result = structure_annotator.process(guideline)

                    if result['success']:
                        logger.info(f"Successfully extracted {result['sections_created']} sections from guideline {guideline.id}")
                        flash(f'Guideline created and {result["sections_created"]} sections extracted', 'success')
                    else:
                        logger.warning(f"Guideline structure annotation failed: {result.get('error', 'Unknown error')}")
                        flash('Guideline created but section extraction failed', 'warning')
                except Exception as e:
                    logger.error(f"Error during guideline structure annotation: {str(e)}")
                    flash('Guideline created but section extraction encountered an error', 'warning')

                flash('Guidelines text uploaded successfully', 'success')
            else:
                flash('Text is required', 'error')
                return redirect(url_for('worlds.add_guideline_form', id=world.id))

        else:
            flash('No guideline content provided', 'error')
            return redirect(url_for('worlds.add_guideline_form', id=world.id))

        # Always redirect to the guidelines page
        return redirect(url_for('worlds.world_guidelines', id=world.id))
