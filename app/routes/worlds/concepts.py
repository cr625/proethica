from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
import json
import os
import logging
import rdflib
from datetime import datetime
from app import db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.ontology import Ontology
from app.models import Document
from app.models.entity_triple import EntityTriple
from app.services.mcp_client import MCPClient
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.services.guideline_concept_integration_service import GuidelineConceptIntegrationService

from app.routes.worlds.helpers import (
    robust_json_parse,
    _generate_preview_triples,
    _extract_predicate_triples,
)

logger = logging.getLogger(__name__)

mcp_client = MCPClient.get_instance()
guideline_analysis_service = GuidelineAnalysisService()


def register_concept_routes(bp):
    @bp.route('/<int:world_id>/guidelines/<int:document_id>/save_concepts', methods=['POST'])
    def save_guideline_concepts(world_id, document_id):
        """Save selected triples from a guideline document to the ontology database."""
        logger.info(f"Saving guideline triples for document {document_id} in world {world_id}")

        world = World.query.get_or_404(world_id)

        from app.models import Document
        guideline = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Get selected concepts from form
        selected_concept_indices = request.form.getlist('selected_concepts')
        selected_indices = [int(idx) for idx in selected_concept_indices]

        if not selected_indices:
            flash('No concepts selected', 'warning')
            return redirect(url_for('worlds.guideline_processing_error',
                                    world_id=world_id,
                                    document_id=document_id,
                                    error_title='No Concepts Selected',
                                    error_message='You must select at least one concept to save to the ontology.'))

        try:
            # Get concepts data from the form - try different methods
            concepts_data = request.form.get('concepts_data', '[]')
            ontology_source = request.form.get('ontology_source', '')
            session_id = request.form.get('session_id')  # Get session ID from form

            # Debug logging
            logger.info(f"Received concepts_data length: {len(concepts_data)}")
            logger.info(f"Session ID from form: {session_id}")
            logger.info(f"Selected concept indices: {selected_indices}")

            # FIXED: Improved form data validation to avoid unnecessary LLM re-extraction
            # Check if concepts_data is valid JSON or a special cached reference
            parsed_concepts = None

            # First try to get from temporary storage if session_id is provided
            if session_id:
                logger.info(f"Attempting to retrieve concepts from temporary storage with session {session_id}")
                try:
                    from app.services.temporary_concept_service import TemporaryConceptService
                    temp_concepts = TemporaryConceptService.get_session_concepts(session_id, status='pending')
                    if temp_concepts:
                        # Extract concept data from temporary storage
                        parsed_concepts = [tc.concept_data for tc in temp_concepts]
                        logger.info(f"Retrieved {len(parsed_concepts)} concepts from temporary storage")
                        concepts = parsed_concepts
                    else:
                        logger.warning(f"No concepts found in temporary storage for session {session_id}")
                except Exception as temp_err:
                    logger.error(f"Failed to retrieve from temporary storage: {temp_err}")

            if parsed_concepts is None and concepts_data == "cached_in_session":
                # Template is using the new lightweight approach - get from cache
                logger.info("Form indicates concepts are cached, retrieving from session/database")
                parsed_concepts = None  # Will trigger cache lookup below
            else:
                # Try to parse JSON from form data (legacy approach)
                try:
                    if concepts_data and concepts_data.strip():
                        parsed_concepts = robust_json_parse(concepts_data)
                        if parsed_concepts and isinstance(parsed_concepts, list) and len(parsed_concepts) > 0:
                            logger.info(f"Successfully parsed {len(parsed_concepts)} concepts from form data")
                            concepts = parsed_concepts
                        else:
                            logger.warning("Form data parsed but contains no valid concepts")
                            parsed_concepts = None
                    else:
                        logger.warning("No concepts_data in form submission")
                except Exception as parse_error:
                    logger.warning(f"Failed to parse form concepts_data: {parse_error}")
                    parsed_concepts = None

            # Only re-extract if form data is completely invalid AND we have no cached data
            if parsed_concepts is None:
                # Get fresh data from database to avoid stale cache
                from app import db
                db.session.refresh(guideline)

                # Try multiple sources for cached concepts with detailed logging
                cached_concepts = None

                # Debug current document state
                logger.info(f"Document {document_id} metadata keys: {list(guideline.guideline_metadata.keys()) if guideline.guideline_metadata else 'None'}")

                # Check document metadata (primary source now)
                if hasattr(guideline, 'doc_metadata') and guideline.guideline_metadata:
                    if 'extracted_concepts' in guideline.guideline_metadata:
                        cached_concepts = guideline.guideline_metadata.get('extracted_concepts', [])
                        logger.info(f"Found {len(cached_concepts)} cached concepts in document metadata")
                        # Log timestamp for debugging
                        timestamp = guideline.guideline_metadata.get('extraction_timestamp', 'unknown')
                        logger.info(f"Concepts cached at: {timestamp}")
                    else:
                        logger.warning("'extracted_concepts' key not found in doc_metadata")
                else:
                    logger.warning("No doc_metadata found in guideline")

                # Fallback: Check Flask session (though it may be truncated)
                if not cached_concepts:
                    session_key = f'concepts_{document_id}'
                    if session_key in session:
                        cached_concepts = session.get(session_key, [])
                        logger.info(f"Fallback: Found {len(cached_concepts)} cached concepts in Flask session")
                    else:
                        logger.warning(f"No concepts found in session key: {session_key}")
                        logger.info(f"Available session keys: {list(session.keys())}")

                if cached_concepts and len(cached_concepts) > 0:
                    # Use cached concepts and filter to selected indices
                    concepts = [cached_concepts[i] for i in selected_indices if i < len(cached_concepts)]
                    logger.info(f"Using {len(concepts)} cached concepts from {len(cached_concepts)} total (avoiding LLM re-extraction)")
                else:
                    # Only as last resort, if no cached data exists, inform user instead of re-extracting
                    logger.error("No valid form data and no cached concepts - asking user to retry analysis")
                    logger.error(f"Debug info - Document metadata: {guideline.guideline_metadata}")
                    logger.error(f"Debug info - Session keys: {list(session.keys())}")
                    return redirect(url_for('worlds.guideline_processing_error',
                                          world_id=world_id,
                                          document_id=document_id,
                                          error_title='Concepts Data Lost',
                                          error_message='The extracted concepts were lost during form submission. Please click "Analyze Concepts" again and then "Save Concepts".',
                                          error_details='This can happen if the browser session expires or the form data is corrupted.'))

            # concepts variable should already be set by the logic above

        except Exception as json_error:
            logger.error(f"Error parsing concepts JSON: {str(json_error)}")
            return redirect(url_for('worlds.guideline_processing_error',
                                    world_id=world_id,
                                    document_id=document_id,
                                    error_title='JSON Parsing Error',
                                    error_message='Could not parse the concept data from the form submission.',
                                    error_details=str(json_error)))

        if not concepts:
            logger.error("No concepts found in parsed data")
            return redirect(url_for('worlds.guideline_processing_error',
                                    world_id=world_id,
                                    document_id=document_id,
                                    error_title='No Concepts Found',
                                    error_message='No concepts were found in the analysis results.'))

        logger.info(f"Generating triples for {len(selected_indices)} selected concepts out of {len(concepts)} total concepts")

        # At this stage, we're just saving the concepts, not generating or saving triples yet
        # No triples data is needed here

        # Save the guideline model with the triples
        try:
            # Create guideline record
            from app.models.guideline import Guideline
            new_guideline = Guideline(
                world_id=world_id,
                title=guideline.title,
                content=guideline.content,
                source_url=guideline.source,
                file_path=guideline.file_path,
                file_type=guideline.file_type,
                guideline_metadata={
                    "document_id": document_id,
                    "analyzed": True,
                    "concepts_extracted": len(concepts),
                    "concepts_selected": len(selected_indices),
                    "triple_count": 0,  # No triples yet
                    "analysis_date": datetime.utcnow().isoformat(),
                    "ontology_source": ontology_source
                }
            )
            db.session.add(new_guideline)
            db.session.flush()  # Get the guideline ID

            # Create basic entity triples for each selected concept
            # These are minimal triples just to represent the concepts, not the full semantic relationships
            created_triple_count = 0
            namespace = "http://proethica.org/guidelines/"

            for idx in selected_indices:
                if idx < len(concepts):
                    concept = concepts[idx]
                    concept_label = concept.get("label", "Unknown Concept")
                    concept_description = concept.get("description", "")

                    # Check for manual type override
                    if concept.get("manually_edited") and concept.get("manual_type_override"):
                        concept_type = concept.get("manual_type_override")
                        # Update the mapping metadata to reflect manual override
                        concept["mapping_source"] = "manual"
                        concept["mapping_justification"] = "Manually corrected by user"
                        concept["type_mapping_confidence"] = 1.0
                        concept["needs_type_review"] = False
                    else:
                        concept_type = concept.get("type", "concept")

                    # Create concept URI
                    concept_uri = f"{namespace}{concept_label.lower().replace(' ', '_')}"

                    # Create basic triples for this concept
                    # 1. Type triple (with two-tier type mapping metadata)
                    type_triple = EntityTriple(
                        subject=concept_uri,
                        subject_label=concept_label,
                        predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        predicate_label="is a",
                        object_uri=f"http://proethica.org/ontology/{concept_type}",
                        object_label=concept_type.title(),
                        is_literal=False,
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        guideline_id=new_guideline.id,
                        world_id=world_id,
                        graph=f"guideline_{new_guideline.id}",
                        # Store type mapping metadata from GuidelineAnalysisService
                        original_llm_type=concept.get("original_llm_type"),
                        type_mapping_confidence=concept.get("type_mapping_confidence"),
                        needs_type_review=concept.get("needs_type_review", False),
                        mapping_justification=concept.get("mapping_justification"),
                        # Two-tier concept type storage
                        semantic_label=concept.get("semantic_label", concept.get("category", concept.get("type", ""))),
                        primary_type=concept_type,
                        mapping_source=concept.get("mapping_source", "legacy")
                    )
                    db.session.add(type_triple)
                    created_triple_count += 1

                    # Persist role classification metadata in description triple metadata for later integration
                    role_meta = {}
                    if (concept.get("type", "").lower() == "role"):
                        if concept.get("role_classification"):
                            role_meta["role_classification"] = concept.get("role_classification")
                        if concept.get("role_signals"):
                            role_meta["role_signals"] = concept.get("role_signals")
                        if concept.get("suggested_parent_class_uri"):
                            role_meta["suggested_parent_class_uri"] = concept.get("suggested_parent_class_uri")

                    # 2. Label triple
                    label_triple = EntityTriple(
                        subject=concept_uri,
                        subject_label=concept_label,
                        predicate="http://www.w3.org/2000/01/rdf-schema#label",
                        predicate_label="label",
                        object_literal=concept_label,
                        object_label=concept_label,
                        is_literal=True,
                        entity_type="guideline_concept",
                        entity_id=new_guideline.id,
                        guideline_id=new_guideline.id,
                        world_id=world_id,
                        graph=f"guideline_{new_guideline.id}"
                    )
                    db.session.add(label_triple)
                    created_triple_count += 1

            # 3. Description triple if available
                    if concept_description:
                        description_triple = EntityTriple(
                            subject=concept_uri,
                            subject_label=concept_label,
                            predicate="http://purl.org/dc/elements/1.1/description",
                            predicate_label="has description",
                            object_literal=concept_description,
                            object_label=concept_description[:50] + "..." if len(concept_description) > 50 else concept_description,
                            is_literal=True,
                            entity_type="guideline_concept",
                            entity_id=new_guideline.id,
                            guideline_id=new_guideline.id,
                            world_id=world_id,
                graph=f"guideline_{new_guideline.id}",
                triple_metadata=role_meta or None
                        )
                        db.session.add(description_triple)
                        created_triple_count += 1

            # Update document metadata
            guideline.guideline_metadata = {
                **(guideline.guideline_metadata or {}),
                "analyzed": True,
                "guideline_id": new_guideline.id,
                "concepts_extracted": len(concepts),
                "concepts_selected": len(selected_indices),
                "triples_created": created_triple_count,  # Update with the number of created triples
                "analysis_date": datetime.utcnow().isoformat()
            }

            # Store the selected concepts in guideline metadata
            selected_concepts_for_storage = []
            for idx in selected_indices:
                if idx < len(concepts):
                    concept = concepts[idx]
                    selected_concepts_for_storage.append({
                        'label': concept.get('label', 'Unknown Concept'),
                        'type': concept.get('type', 'concept'),
                        'category': concept.get('type', 'concept'),  # Use the basic type (role, principle, etc.)
                        'description': concept.get('description', 'No description available')
                    })

            # Update the guideline_metadata with concepts and triple count
            new_guideline.guideline_metadata = {
                **(new_guideline.guideline_metadata or {}),
                "triple_count": created_triple_count,
                "concepts": selected_concepts_for_storage,
                "concepts_selected": len(selected_indices)
            }

            db.session.commit()

            logger.info(f"Successfully saved {len(selected_indices)} concepts for guideline {new_guideline.id}")

            # Automatically add concepts to the derived ontology attached to this guideline document
            integration_result = None
            try:
                commit_msg = f"Auto-added {len(selected_indices)} concepts from guideline analysis"
                from app.services.guideline_concept_integration_service import GuidelineConceptIntegrationService
                integration_result = GuidelineConceptIntegrationService.add_concepts_to_ontology(
                    concepts=[],  # service will retrieve from DB using document metadata
                    guideline_id=document_id,  # use document id; service resolves actual guideline id
                    ontology_domain='engineering-ethics',
                    commit_message=commit_msg
                )
                if integration_result.get('success'):
                    summary = integration_result.get('summary', {})
                    added = summary.get('successful_additions', 0)
                    skipped = summary.get('skipped_duplicates', 0)
                    if added or skipped:
                        flash(f"Derived ontology updated: {added} added, {skipped} skipped as duplicates.", 'success')
                    else:
                        flash("No new concepts were added to the derived ontology (all duplicates).", 'info')
                else:
                    flash(f"Concepts saved, but ontology integration failed: {integration_result.get('error','unknown error')}", 'warning')
            except Exception as integ_err:
                logger.error(f"Auto-integration error: {integ_err}")
                flash("Concepts saved, but automatic ontology integration encountered an error.", 'warning')

            # Create draft ontology in OntServe for finalized concepts
            try:
                use_draft_ontologies = os.environ.get('USE_DRAFT_ONTOLOGIES', 'false').lower() == 'true'
                if use_draft_ontologies:
                    from app.services.draft_ontology_service import TemporaryConceptCompatibilityService

                    # Store finalized/selected concepts in OntServe as draft ontology
                    selected_concepts_for_draft = [concepts[i] for i in selected_indices if i < len(concepts)]

                    draft_session_id = TemporaryConceptCompatibilityService.store_concepts(
                        concepts=selected_concepts_for_draft,
                        document_id=document_id,
                        world_id=world_id,
                        extraction_method='llm_finalized',
                        created_by=f'ProEthica User (Saved {len(selected_concepts_for_draft)} concepts)'
                    )

                    if draft_session_id:
                        logger.info(f"Created draft ontology in OntServe: {draft_session_id} with {len(selected_concepts_for_draft)} finalized concepts")
                        flash(f"Concepts saved to ProEthica and OntServe draft ontology: {draft_session_id}", 'success')
                    else:
                        logger.warning("Failed to create draft ontology in OntServe")

            except Exception as draft_err:
                logger.error(f"Draft ontology creation error: {draft_err}")
                # Don't fail the save process if draft creation fails

            # Clear temporary concepts since they've been finalized
            try:
                session_id = request.form.get('session_id')
                if session_id:
                    from app.services.temporary_concept_service import TemporaryConceptService
                    TemporaryConceptService.clear_session(session_id)
                    logger.info(f"Cleared temporary concepts for session: {session_id}")
            except Exception as clear_err:
                logger.warning(f"Failed to clear temporary concepts: {clear_err}")

            # Prepare selected concepts for display
            selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
            concepts_json = json.dumps(selected_concepts)

            # Count any existing semantic relationship triples for this document
            try:
                from app.models.guideline_semantic_triple import GuidelineSemanticTriple
                existing_semantic_triples = GuidelineSemanticTriple.get_by_guideline(document_id, approved_only=False)
                semantic_triple_count = len(existing_semantic_triples)
            except Exception:
                semantic_triple_count = 0

            # Show Saved Concepts page with auto-added status
            return render_template('guideline_saved_concepts.html',
                                   world=world,
                                   guideline=guideline,
                                   concepts=selected_concepts,
                                   concepts_json=concepts_json,
                                   selected_indices=selected_indices,
                                   concept_count=len(selected_indices),
                                   guideline_id=new_guideline.id,
                                   world_id=world_id,
                                   document_id=document_id,
                                   ontology_source=ontology_source,
                                   auto_added=True,
                                   integration_result=integration_result,
                                   semantic_triple_count=semantic_triple_count)

        except Exception as e:
            db.session.rollback()
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error saving concepts: {str(e)}\n{error_trace}")
            return redirect(url_for('worlds.guideline_processing_error',
                                   world_id=world_id,
                                   document_id=document_id,
                                   error_title='Database Error',
                                   error_message=f'Error saving concepts: {str(e)}',
                                   error_details=error_trace))

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/save_concepts_direct', methods=['POST'])
    def save_concepts_direct(world_id, document_id):
        """Save selected concepts and their relationships directly to the ontology without triple review."""
        from datetime import datetime
        logger.info(f"Saving concepts directly for document {document_id} in world {world_id}")

        try:
            world = World.query.get_or_404(world_id)

            from app.models import Document
            document = Document.query.get_or_404(document_id)

            # Check if document belongs to this world
            if document.world_id != world.id:
                return jsonify({'success': False, 'error': 'Document does not belong to this world'})

            # Get form data
            selected_indices_json = request.form.get('selected_concept_indices', '[]')
            concepts_data_json = request.form.get('concepts_data', '[]')
            session_id = request.form.get('session_id')

            try:
                selected_indices = json.loads(selected_indices_json)

                # Get concepts from temporary storage or form data
                if session_id:
                    from app.services.temporary_concept_service import TemporaryConceptService
                    temp_concepts = TemporaryConceptService.get_session_concepts(session_id)
                    all_concepts = [tc.concept_data for tc in temp_concepts]
                else:
                    all_concepts = json.loads(concepts_data_json)

                # Filter to selected concepts
                selected_concepts = [all_concepts[i] for i in selected_indices if i < len(all_concepts)]

                if not selected_concepts:
                    return jsonify({'success': False, 'error': 'No concepts selected'})

                logger.info(f"Saving {len(selected_concepts)} selected concepts directly to ontology")

                # Generate triples from selected concepts (including predicate suggestions)
                triples = _generate_preview_triples(selected_concepts, document_id, world)

                # Add predicate suggestion triples
                predicate_triples = _extract_predicate_triples(selected_concepts, document_id, world)
                if predicate_triples:
                    triples.extend(predicate_triples)
                    logger.info(f"Added {len(predicate_triples)} predicate suggestion triples")

                # Save all triples to the database
                from app.services.triple_duplicate_detection_service import TripleDuplicateDetectionService
                from app.models.guideline import Guideline
                from app.models.entity_triple import EntityTriple

                duplicate_service = TripleDuplicateDetectionService()

                # Get or create guideline record
                guideline_record = Guideline.query.filter_by(
                    title=document.title,
                    world_id=world_id
                ).first()

                if not guideline_record:
                    guideline_record = Guideline(
                        title=document.title,
                        world_id=world_id,
                        guideline_metadata={
                            'source': 'direct_concept_save',
                            'document_id': document_id,
                            'created_at': datetime.utcnow().isoformat()
                        }
                    )
                    db.session.add(guideline_record)
                    db.session.flush()

                saved_triples = []
                skipped_duplicates = []

                # Save each triple
                for triple_data in triples:
                    # Determine if literal or URI
                    is_literal = triple_data.get('is_literal', False)

                    if is_literal or 'object_literal' in triple_data:
                        object_literal = triple_data.get('object_literal', triple_data.get('object', ''))
                        object_uri = None
                        object_value = object_literal
                    else:
                        object_literal = None
                        object_uri = triple_data.get('object', '')
                        object_value = object_uri

                    # Check for duplicates
                    duplicate_result = duplicate_service.check_duplicate_with_details(
                        triple_data.get('subject', ''),
                        triple_data.get('predicate', ''),
                        object_value,
                        is_literal,
                        exclude_guideline_id=guideline_record.id
                    )

                    if duplicate_result['is_duplicate']:
                        logger.info(f"Skipping duplicate triple: {duplicate_result['details']}")
                        skipped_duplicates.append(triple_data)
                        continue

                    # Create the triple
                    triple = EntityTriple(
                        subject=triple_data.get('subject', ''),
                        subject_label=triple_data.get('subject_label', ''),
                        predicate=triple_data.get('predicate', ''),
                        predicate_label=triple_data.get('predicate_label', ''),
                        object_literal=object_literal,
                        object_uri=object_uri,
                        object_label=triple_data.get('object_label', ''),
                        is_literal=is_literal,
                        entity_type="guideline_concept",
                        entity_id=guideline_record.id,
                        guideline_id=guideline_record.id,
                        world_id=world_id,
                        graph=f"guideline_{guideline_record.id}"
                    )

                    db.session.add(triple)
                    saved_triples.append(triple_data)

                # Commit all changes
                db.session.commit()

                # Now add the concepts to the derived ontology
                logger.info(f"Adding {len(selected_concepts)} concepts to derived ontology for guideline {document_id}")
                integration_result = GuidelineConceptIntegrationService.add_concepts_to_ontology(
                    concepts=selected_concepts,
                    guideline_id=document_id,
                    ontology_domain='engineering-ethics',
                    commit_message=f'Added concepts from guideline: {document.title}'
                )

                if not integration_result.get('success'):
                    logger.warning(f"Failed to add concepts to derived ontology: {integration_result.get('error')}")
                    # Don't fail the whole operation, triples are already saved
                else:
                    logger.info(f"Successfully integrated concepts into derived ontology: {integration_result}")

                # Update document metadata to indicate concepts have been saved
                from datetime import datetime
                if not document.guideline_metadata:
                    document.guideline_metadata = {}
                document.guideline_metadata['concepts_saved_to_ontology'] = True
                document.guideline_metadata['concepts_saved_timestamp'] = datetime.utcnow().isoformat()
                document.guideline_metadata['concepts_saved_count'] = len(selected_concepts)

                # Mark the document metadata as modified for SQLAlchemy
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(document, 'doc_metadata')
                db.session.commit()

                # Clear temporary concepts if they were used
                if session_id:
                    from app.services.temporary_concept_service import TemporaryConceptService
                    TemporaryConceptService.clear_session(session_id)

                success_message = f"Successfully saved {len(selected_concepts)} concepts and {len(saved_triples)} relationships"
                if skipped_duplicates:
                    success_message += f" ({len(skipped_duplicates)} duplicates skipped)"

                if integration_result.get('success'):
                    success_message += f" and integrated into derived ontology"

                logger.info(success_message)

                return jsonify({
                    'success': True,
                    'concepts_saved': len(selected_concepts),
                    'triples_saved': len(saved_triples),
                    'duplicates_skipped': len(skipped_duplicates),
                    'message': success_message,
                    'redirect_url': url_for('worlds.view_guideline', id=world_id, document_id=document_id)
                })

            except json.JSONDecodeError as e:
                logger.error(f"Error parsing JSON data: {e}")
                return jsonify({'success': False, 'error': f'Error parsing data: {str(e)}'})

        except Exception as e:
            logger.error(f"Error in save_concepts_direct: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': f'Server error: {str(e)}'})

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/view_saved_concepts', methods=['GET'])
    def view_saved_concepts(world_id, document_id):
        """View concepts that have been saved to the derived ontology in a friendly UI."""
        world = World.query.get_or_404(world_id)

        from app.models import Document
        document = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if document.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        try:
            # Check if concepts have been saved to ontology
            if not (document.guideline_metadata and document.guideline_metadata.get('concepts_saved_to_ontology')):
                flash('No concepts have been saved to the ontology for this guideline yet', 'info')
                return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

            # Find the derived ontology for this document (skip database check, look directly)
            from app.models.ontology import Ontology
            derived_domain = f'guideline-{document_id}-concepts'
            derived_ont = Ontology.query.filter_by(domain_id=derived_domain).first()

            if not derived_ont or not derived_ont.content:
                flash('Derived ontology content not found', 'error')
                return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

            # Get concepts directly from the derived ontology
            saved_concepts = []
            derived_ontology_id = derived_ont.id
            logger.info(f"Found derived ontology: {derived_ont.name}")

            try:
                # Parse concepts directly from the ontology content
                import rdflib
                from rdflib import Graph, Namespace, RDFS, RDF
                from urllib.parse import unquote

                # Parse the RDF content
                g = Graph()
                g.parse(data=derived_ont.content, format='turtle')

                # Define namespaces
                derived_ns = Namespace(f"http://proethica.org/ontology/guideline-{document_id}-concepts#")
                intermediate_ns = Namespace("http://proethica.org/ontology/intermediate#")

                # Get all subjects that have labels (these are our concepts)
                for subject, predicate, obj in g.triples((None, RDFS.label, None)):
                    if str(subject).startswith(str(derived_ns)):
                        concept_uri = str(subject)
                        concept_label = str(obj)

                        # Get description if available
                        description = ""
                        desc_predicate = rdflib.term.URIRef("http://purl.org/dc/elements/1.1/description")
                        for _, _, desc_obj in g.triples((subject, desc_predicate, None)):
                            description = str(desc_obj)
                            break

                        # Determine type from the URI or class relationships
                        concept_type = "unknown"

                        # Try to get type from rdfs:subClassOf relationships
                        for _, _, parent_class in g.triples((subject, RDFS.subClassOf, None)):
                            parent_str = str(parent_class)
                            if "#Role" in parent_str:
                                concept_type = "role"
                            elif "#Principle" in parent_str:
                                concept_type = "principle"
                            elif "#Obligation" in parent_str:
                                concept_type = "obligation"
                            elif "#State" in parent_str:
                                concept_type = "state"
                            elif "#Resource" in parent_str:
                                concept_type = "resource"
                            elif "#Action" in parent_str:
                                concept_type = "action"
                            elif "#Event" in parent_str:
                                concept_type = "event"
                            elif "#Capability" in parent_str:
                                concept_type = "capability"
                            elif "#Constraint" in parent_str:
                                concept_type = "constraint"
                            break

                        # If no subclass relationship, try to infer from the URI fragment
                        if concept_type == "unknown":
                            fragment = concept_uri.split('#')[-1].lower()
                            if 'role' in fragment:
                                concept_type = 'role'
                            elif 'principle' in fragment:
                                concept_type = 'principle'
                            elif 'obligation' in fragment:
                                concept_type = 'obligation'
                            # Add more inference rules as needed

                        saved_concepts.append({
                            'label': concept_label,
                            'type': concept_type,
                            'description': description,
                            'uri': concept_uri,
                            'confidence': 1.0  # Saved concepts are assumed to be high confidence
                        })

                logger.info(f"Parsed {len(saved_concepts)} concepts from derived ontology content")

            except Exception as e:
                logger.warning(f"Could not parse concepts from derived ontology: {e}")
                flash('Could not parse concepts from ontology', 'warning')

            # Get saved metadata
            concepts_saved_count = document.guideline_metadata.get('concepts_saved_count', len(saved_concepts))
            concepts_saved_timestamp = document.guideline_metadata.get('concepts_saved_timestamp')

            return render_template('saved_concepts_view.html',
                                 world=world,
                                 document=document,
                                 saved_concepts=saved_concepts,
                                 concepts_saved_count=concepts_saved_count,
                                 concepts_saved_timestamp=concepts_saved_timestamp,
                                 derived_ontology_id=derived_ontology_id)

        except Exception as e:
            logger.error(f"Error viewing saved concepts for document {document_id}: {e}")
            flash(f'Error retrieving saved concepts: {str(e)}', 'error')
            return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/clear_pending', methods=['POST'])
    @login_required
    def clear_pending_concepts(world_id, document_id):
        """Clear all pending concepts for a guideline document."""
        logger.info(f"Clearing pending concepts for document {document_id} in world {world_id}")

        world = World.query.get_or_404(world_id)

        from app.models import Document
        from app.services.temporary_concept_service import TemporaryConceptService

        document = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if document.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        try:
            # Always clear temporary concepts - extraction now stores in temporary storage first
            # Draft ontologies are only created when user saves/finalizes concepts
            from app.models.temporary_concept import TemporaryConcept

            # Find all temporary concepts for this document
            all_temp_concepts = TemporaryConcept.query.filter_by(
                document_id=document_id,
                world_id=world_id
            ).all()

            total_found = len(all_temp_concepts)
            logger.info(f"Found {total_found} total temporary concepts for document {document_id}")

            if total_found > 0:
                # Show some details about what we found
                session_info = {}
                for concept in all_temp_concepts:
                    session_id = concept.session_id
                    status = concept.status
                    if session_id not in session_info:
                        session_info[session_id] = {'statuses': set(), 'count': 0}
                    session_info[session_id]['statuses'].add(status)
                    session_info[session_id]['count'] += 1

                for session_id, info in session_info.items():
                    logger.info(f"Session {session_id}: {info['count']} concepts with statuses {list(info['statuses'])}")

                # Delete all temporary concepts for this document directly
                deleted_count = TemporaryConcept.query.filter_by(
                    document_id=document_id,
                    world_id=world_id
                ).delete()

                # Commit the transaction
                db.session.commit()

                flash(f'Successfully cleared {deleted_count} pending concepts', 'success')
                logger.info(f"Successfully deleted {deleted_count} temporary concepts for document {document_id}")
            else:
                flash('No pending concepts found to clear', 'info')
                logger.info(f"No temporary concepts found for document {document_id}")

        except Exception as e:
            logger.error(f"Error clearing pending concepts for document {document_id}: {str(e)}")
            flash('Error clearing pending concepts. Please try again.', 'error')

        return redirect(url_for('worlds.view_guideline', id=world_id, document_id=document_id))

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/add_concepts_to_ontology', methods=['POST'])
    def add_concepts_to_ontology(world_id, document_id):
        """Add extracted guideline concepts directly to the engineering-ethics ontology."""
        logger.info(f"Adding concepts to ontology for document {document_id} in world {world_id}")

        world = World.query.get_or_404(world_id)

        from app.models import Document
        guideline = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        try:
            # Get commit message if provided
            commit_message = request.form.get('commit_message', '').strip()

            # Get the guideline ID from metadata if available
            actual_guideline_id = None
            if guideline.guideline_metadata and 'guideline_id' in guideline.guideline_metadata:
                actual_guideline_id = guideline.guideline_metadata['guideline_id']

            if not actual_guideline_id:
                flash('No guideline concepts found to add to ontology', 'warning')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))

            # Use the integration service to add concepts to derived ontology (avoids modifying core .ttl files)
            # Pass document_id for consistent naming/linking - service will handle concept retrieval
            result = GuidelineConceptIntegrationService.add_concepts_to_ontology(
                concepts=[],  # Service will retrieve concepts internally
                guideline_id=document_id,  # Use document ID that matches the URL
                ontology_domain='engineering-ethics',
                commit_message=commit_message or f"Added concepts from guideline analysis"
            )

            if result['success']:
                summary = result['summary']

                # Create success message based on results
                success_parts = []
                if summary['successful_additions'] > 0:
                    success_parts.append(f"{summary['successful_additions']} concepts added")
                if summary['skipped_duplicates'] > 0:
                    success_parts.append(f"{summary['skipped_duplicates']} duplicates skipped")

                if success_parts:
                    flash(f"Ontology updated successfully: {', '.join(success_parts)}", 'success')
                else:
                    flash('No new concepts were added (all were duplicates)', 'info')

                # Get concepts from result for template
                actual_guideline_id = GuidelineConceptIntegrationService._get_actual_guideline_id(document_id)
                concepts = GuidelineConceptIntegrationService.get_concepts_from_guideline(actual_guideline_id) if actual_guideline_id else []

                # Render success template with results
                return render_template('guideline_ontology_success.html',
                                      world=world,
                                      guideline=guideline,
                                      result=result,
                                      concepts=concepts,
                                      world_id=world_id,
                                      document_id=document_id)
            else:
                # Handle errors
                error_message = result.get('error', 'Unknown error occurred')
                errors = result.get('errors', [])

                flash(f'Error adding concepts to ontology: {error_message}', 'error')

                if errors:
                    for error in errors[:5]:  # Show first 5 errors
                        flash(f'Detail: {error}', 'warning')

                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))

        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error adding concepts to ontology: {str(e)}\n{error_trace}")
            flash(f'Unexpected error: {str(e)}', 'error')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))


    @bp.route('/<int:id>/guidelines/<int:document_id>/concepts', methods=['DELETE'])
    @login_required

    def remove_extracted_concepts(id, document_id):
        """Remove extracted concepts from a guideline and associated ontology entries."""
        from flask import jsonify, request
        from app.models import Document
        from app.models.guideline import Guideline
        from app.models.ontology import Ontology
        from app.models.ontology_version import OntologyVersion
        from app.models.ontology_import import OntologyImport
        try:
            # Get the world and guideline document
            world = World.query.get_or_404(id)
            guideline = Document.query.get_or_404(document_id)
            # Check if document belongs to this world
            if guideline.world_id != world.id:
                return jsonify({'error': 'Document does not belong to this world'}), 403
            # Check if document is a guideline
            if guideline.document_type != "guideline":
                return jsonify({'error': 'Document is not a guideline'}), 400
            # Check permissions: allow if user can edit the document OR the world OR is admin
            try:
                can_edit_doc = guideline.can_edit(current_user)
            except Exception:
                can_edit_doc = False
            try:
                can_edit_world = world.can_edit(current_user)
            except Exception:
                can_edit_world = False
            is_admin = getattr(current_user, 'is_admin', False)
            if not (can_edit_doc or can_edit_world or is_admin):
                logger.warning(f"Permission denied: user {getattr(current_user, 'id', '?')} remove concepts from guideline {document_id}")
                return jsonify({'error': 'Permission denied'}), 403
            logger.info(f"User {current_user.id} removing extracted concepts from guideline document {document_id}")

            # Determine associated Guideline record (Stage 1 saved concepts)
            associated_guideline_id = None
            if guideline.guideline_metadata and 'guideline_id' in guideline.guideline_metadata:
                associated_guideline_id = guideline.guideline_metadata.get('guideline_id')

            concepts_removed = 0
            triples_removed = 0
            derived_ontology_deleted = False

            # 1) Remove EntityTriples associated with this guideline extraction (both basic + alignment)
            from app.models.entity_triple import EntityTriple
            if associated_guideline_id:
                triples_removed = EntityTriple.query.filter(
                    EntityTriple.guideline_id == associated_guideline_id,
                    EntityTriple.entity_type == 'guideline_concept'
                ).delete(synchronize_session=False)
            else:
                # Fallback: delete any alignment triples linked directly to this document id
                triples_removed = EntityTriple.query.filter(
                    EntityTriple.entity_id == guideline.id,
                    EntityTriple.entity_type == 'guideline_concept',
                    EntityTriple.world_id == world.id
                ).delete(synchronize_session=False)

            # 2) Remove the Guideline record created during save_concepts, if present
            removed_guideline = 0
            if associated_guideline_id:
                related = Guideline.query.get(associated_guideline_id)
                if related:
                    # Count concepts saved in metadata for reporting
                    if related.guideline_metadata and 'concepts' in related.guideline_metadata:
                        try:
                            concepts_removed = len(related.guideline_metadata['concepts'])
                        except Exception:
                            concepts_removed = 0
                    db.session.delete(related)
                    removed_guideline = 1

            # 3) Clean document metadata flags and linkage
            if hasattr(guideline, 'doc_metadata') and isinstance(guideline.guideline_metadata, dict):
                for key in [
                    'guideline_id', 'analyzed', 'concepts_extracted', 'concepts_selected',
                    'triples_created', 'triples_saved', 'triples_generated', 'analysis_date'
                ]:
                    guideline.guideline_metadata.pop(key, None)
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(guideline, 'doc_metadata')

            # Delete the derived ontology for this document by default to prevent stale conflicts
            # Opt-out is available via either delete_derived_ontology=false or keep_derived_ontology=true
            try:
                raw_delete = request.args.get('delete_derived_ontology')
                raw_keep = request.args.get('keep_derived_ontology')
                if raw_keep is not None and str(raw_keep).lower() in ('1', 'true', 'yes', 'on'):
                    delete_derived = False
                elif raw_delete is None:
                    # Default behavior: delete derived ontology if flag not provided
                    delete_derived = True
                else:
                    delete_derived = str(raw_delete).lower() in ('1', 'true', 'yes', 'on')
            except Exception:
                delete_derived = True

            if delete_derived:
                try:
                    derived_domain = f"guideline-{document_id}-concepts"
                    derived = Ontology.query.filter_by(domain_id=derived_domain).first()
                    if derived:
                        OntologyImport.query.filter(
                            db.or_(
                                OntologyImport.importing_ontology_id == derived.id,
                                OntologyImport.imported_ontology_id == derived.id
                            )
                        ).delete(synchronize_session=False)
                        OntologyVersion.query.filter_by(ontology_id=derived.id).delete(synchronize_session=False)
                        db.session.delete(derived)
                        derived_ontology_deleted = True
                except Exception as del_err:
                    logger.warning(f"Failed to delete derived ontology for document {document_id}: {del_err}")

            db.session.commit()

            logger.info(
                f"Removed {triples_removed} triples and {removed_guideline} associated guideline(s) for document {document_id}"
            )
            return jsonify({
                'success': True,
                'message': 'Extracted concepts and triples removed',
                'concepts_removed': concepts_removed,
                'triples_removed': int(triples_removed),
                'guideline_removed': bool(removed_guideline),
                'derived_ontology_deleted': derived_ontology_deleted
            }), 200

        except Exception as e:
            db.session.rollback()
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error removing concepts from guideline {document_id}: {str(e)}\n{error_trace}")

            return jsonify({
                'error': f'Failed to remove concepts: {str(e)}'
            }), 500

    @bp.route('/<int:id>/guidelines/<int:guideline_id>/delete', methods=['POST'])
    @login_required
    def delete_guideline(id, guideline_id):
        """Delete a guideline and all associated data."""
        world = World.query.get_or_404(id)

        from app.models import Document
        from app.models.guideline import Guideline
        from app.models.entity_triple import EntityTriple

        # Try to get the guideline from the Guideline table first (new approach)
        guideline = Guideline.query.get(guideline_id)

        if guideline:
            # Check if guideline belongs to this world
            if guideline.world_id != world.id:
                flash('Guideline does not belong to this world', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if user can delete this guideline
            if not guideline.can_delete(current_user):
                flash('You do not have permission to delete this guideline.', 'error')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

            actual_guideline_id = guideline_id
        else:
            # Fallback: try to get from Document table (legacy approach)
            document = Document.query.get(guideline_id)
            if not document:
                flash('Guideline not found', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if document belongs to this world
            if document.world_id != world.id:
                flash('Document does not belong to this world', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if document is a guideline
            if document.document_type != "guideline":
                flash('Document is not a guideline', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if user can delete this document
            if not document.can_delete(current_user):
                flash('You do not have permission to delete this guideline.', 'error')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

            # Get associated guideline ID if exists
            actual_guideline_id = None
            if document.guideline_metadata and 'guideline_id' in document.guideline_metadata:
                actual_guideline_id = document.guideline_metadata['guideline_id']

        # User option: delete associated derived ontology too
        delete_derived = request.form.get('delete_derived_ontology') in ('on', 'true', '1')
        derived_ontology_id = request.form.get('derived_ontology_id')

        logger.info(f"Deleting guideline {guideline_id} (actual_guideline_id: {actual_guideline_id})")

        # Delete associated data in order (due to foreign key constraints)
        deleted_counts = {
            'triples': 0,
            'guideline': 0,
            'document': 0
        }

        try:
            # Use no_autoflush to prevent premature queries to related tables
            with db.session.no_autoflush:
                # 1. Delete entity triples associated with the guideline
                if actual_guideline_id:
                    deleted_counts['triples'] = EntityTriple.query.filter_by(
                        guideline_id=actual_guideline_id
                    ).delete(synchronize_session=False)
                    logger.info(f"Deleted {deleted_counts['triples']} triples for guideline {actual_guideline_id}")

                # 2. Delete the guideline entry
                if guideline:
                    db.session.delete(guideline)
                    deleted_counts['guideline'] = 1
                    logger.info(f"Deleted guideline {guideline_id}")
                elif 'document' in locals():
                    # Delete legacy document
                    db.session.delete(document)
                    deleted_counts['document'] = 1
                    logger.info(f"Deleted legacy document {guideline_id}")

                    # Also delete the associated guideline if it exists
                    if actual_guideline_id:
                        guideline_obj = Guideline.query.get(actual_guideline_id)
                        if guideline_obj:
                            db.session.delete(guideline_obj)
                            deleted_counts['guideline'] = 1
                            logger.info(f"Deleted associated guideline {actual_guideline_id}")

                # Optionally delete derived ontology first to avoid orphan
                if delete_derived and derived_ontology_id:
                    try:
                        from app.models.ontology import Ontology
                        derived_ont = Ontology.query.get(int(derived_ontology_id))
                        if derived_ont:
                            logger.info(f"Deleting derived ontology {derived_ontology_id} as requested")
                            db.session.delete(derived_ont)
                    except Exception as e:
                        logger.warning(f"Could not delete derived ontology {derived_ontology_id}: {e}")

                # 3. Delete temporary concepts and document chunks (only for legacy Document approach)
                if 'document' in locals():
                    from app.models.temporary_concept import TemporaryConcept
                    deleted_temp_concepts = TemporaryConcept.query.filter_by(document_id=document.id).delete(synchronize_session=False)
                    if deleted_temp_concepts > 0:
                        logger.info(f"Deleted {deleted_temp_concepts} temporary concepts for document {document.id}")

                    from app.models.document import DocumentChunk
                    deleted_chunks = DocumentChunk.query.filter_by(document_id=document.id).delete(synchronize_session=False)
                    if deleted_chunks > 0:
                        logger.info(f"Deleted {deleted_chunks} document chunks for document {document.id}")

                    # Delete the file if it exists
                    if document.file_path and os.path.exists(document.file_path):
                        try:
                            os.remove(document.file_path)
                            logger.info(f"Deleted file {document.file_path}")
                        except Exception as e:
                            flash(f'Error deleting file: {str(e)}', 'warning')

                    # Delete the document
                    db.session.delete(document)
                else:
                    # For independent Guidelines, no additional file cleanup needed
                    logger.info(f"Independent guideline deletion - no file cleanup needed")

            # Commit all deletions
            db.session.commit()

            # Provide detailed feedback
            if deleted_counts['triples'] > 0:
                flash(f'Guideline deleted successfully along with {deleted_counts["triples"]} associated triples', 'success')
            else:
                flash('Guideline deleted successfully', 'success')
            if delete_derived and derived_ontology_id:
                flash('Derived ontology deleted as well.', 'info')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting guideline: {str(e)}")
            flash(f'Error deleting guideline: {str(e)}', 'error')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

        return redirect(url_for('worlds.world_guidelines', id=world.id))

    # References routes
    @bp.route('/<int:id>/references', methods=['GET'])
    def world_references(id):
        """Display references for a world."""
        world = World.query.get_or_404(id)

        # Get search query from request parameters
        query = request.args.get('query', '')

        # Get references
        references = None
        try:
            if query:
                # Search with the provided query
                references_data = mcp_client.search_zotero_items(query, limit=10)
                references = {'results': references_data}
            else:
                # Get references based on world content
                references_data = mcp_client.get_references_for_world(world)
                references = {'results': references_data}
        except Exception as e:
            print(f"Error retrieving references: {str(e)}")
            references = {'results': []}

        return render_template('world_references.html', world=world, references=references, query=query)

    # Scenarios routes
    @bp.route('/<int:id>/scenarios', methods=['GET'])
    def world_scenarios(id):
        """Display scenarios for a specific world."""
        world = World.query.get_or_404(id)

        # Get scenarios for this world
        scenarios = Scenario.query.filter_by(world_id=world.id).all()

        return render_template('world_scenarios.html', world=world, scenarios=scenarios)
