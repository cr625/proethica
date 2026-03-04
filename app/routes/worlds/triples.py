from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
import json
import os
import logging
from datetime import datetime
from app import db
from app.models.world import World
from app.models import Document
from app.models.entity_triple import EntityTriple
from app.services.guideline_analysis_service import GuidelineAnalysisService
from app.services.role_property_suggestions import RolePropertySuggestionsService

from app.routes.worlds.helpers import (
    robust_json_parse,
    _generate_preview_triples,
    _calculate_triple_stats,
    _extract_predicate_triples,
    _organize_triples_by_concept,
)

logger = logging.getLogger(__name__)

guideline_analysis_service = GuidelineAnalysisService()


def register_triple_routes(bp):
    @bp.route('/<int:world_id>/guidelines/<int:guideline_id>/manage_triples', methods=['GET'])
    def manage_guideline_triples(world_id, guideline_id):
        """Display and manage triples for a guideline."""
        world = World.query.get_or_404(world_id)

        from app.models import Document
        from app.models.guideline import Guideline
        guideline = Document.query.get_or_404(guideline_id)

        # Cleanup: remove triples pointing to deleted guidelines (orphan records)
        try:
            from sqlalchemy import text as _text
            del_sql = _text(
                            """
                            DELETE FROM entity_triples et
                            WHERE et.entity_type = 'guideline_concept'
                                AND et.guideline_id IS NOT NULL
                                AND NOT EXISTS (
                                    SELECT 1 FROM guidelines g WHERE g.id = et.guideline_id
                                )
                            """
            )
            res = db.session.execute(del_sql)
            if res.rowcount and res.rowcount > 0:
                logger.info(f"Cleanup removed {res.rowcount} orphan guideline triples")
            db.session.commit()
        except Exception as _cleanup_err:
            logger.debug(f"Guideline triple cleanup skipped/failed: {_cleanup_err}")

        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Get the actual guideline ID if this is a Document with guideline metadata
        actual_guideline_id = None
        if guideline.guideline_metadata and 'guideline_id' in guideline.guideline_metadata:
            actual_guideline_id = guideline.guideline_metadata['guideline_id']

        # Get all triples for this guideline (with proper world filtering)
        from app.models.entity_triple import EntityTriple
        if actual_guideline_id:
            triples = EntityTriple.query.filter_by(
                guideline_id=actual_guideline_id,
                world_id=world.id
            ).all()
        else:
            triples = EntityTriple.query.filter_by(
                guideline_id=guideline.id,
                world_id=world.id
            ).all()

        # Add ontology status to each triple with enhanced categorization
        from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
        duplicate_service = get_duplicate_detection_service()

        core_ontology_terms = []      # In actual ontology files
        other_guidelines_terms = []   # From different guidelines
        same_guideline_old_terms = [] # Old runs of same guideline
        orphaned_terms = []          # No clear source
        guideline_specific_terms = [] # New unique terms

        # Optional: ignore duplicates sourced from configured guideline IDs (comma-separated env)
        import os
        ignore_ids_env = os.getenv('IGNORE_DUPLICATE_GUIDELINE_IDS', '').strip()
        ignore_guideline_ids = set()
        if ignore_ids_env:
            try:
                ignore_guideline_ids = {int(x) for x in ignore_ids_env.split(',') if x.strip().isdigit()}
            except Exception:
                ignore_guideline_ids = set()

        for triple in triples:
            # Check if this triple exists in ontology or database
            object_value = triple.object_uri if triple.object_uri else triple.object_literal

            # Skip triples with no object value
            if object_value is None:
                logger.warning(f"Skipping triple with None object value: {triple.subject} {triple.predicate}")
                continue

            duplicate_result = duplicate_service.check_duplicate_with_details(
                triple.subject,
                triple.predicate,
                object_value,
                triple.is_literal,
                exclude_guideline_id=triple.guideline_id
            )

            # Apply ignore filter: if duplicate is only due to an existing triple from an ignored guideline, treat as non-duplicate
            try:
                existing = duplicate_result.get('existing_triple') if isinstance(duplicate_result, dict) else None
                if existing and getattr(existing, 'guideline_id', None) in ignore_guideline_ids:
                    duplicate_result['is_duplicate'] = False
                    duplicate_result['in_database'] = False
                    duplicate_result['details'] = f"Ignoring duplicate from guideline {existing.guideline_id} by config"
                    duplicate_result['existing_triple'] = None
            except Exception:
                pass

            # Add the duplicate check result to the triple
            triple.ontology_status = duplicate_result

            # Also annotate whether subject/object concepts already exist independently
            try:
                subj_presence = duplicate_service.check_concept_presence(triple.subject)
            except Exception:
                subj_presence = {'in_ontology': False, 'in_database': False}
            try:
                obj_uri = None if triple.is_literal else (triple.object_uri or getattr(triple, 'object', None))
                obj_presence = duplicate_service.check_concept_presence(obj_uri) if obj_uri else {'in_ontology': False, 'in_database': False}
            except Exception:
                obj_presence = {'in_ontology': False, 'in_database': False}
            # Attach lightweight flags for template use
            triple.subject_known = subj_presence
            triple.object_known = obj_presence

            # Enhanced categorization logic
            if duplicate_result['in_ontology']:
                # Found in actual ontology files (engineering-ethics.ttl, etc.)
                core_ontology_terms.append(triple)
            elif duplicate_result['in_database'] and duplicate_result['existing_triple']:
                existing_triple = duplicate_result['existing_triple']
                # Check if it's from the same guideline (old run) vs different guideline
                if existing_triple.guideline_id == triple.guideline_id:
                    # Same guideline - this is from an old run, probably should be cleaned up
                    same_guideline_old_terms.append(triple)
                elif existing_triple.guideline_id and existing_triple.guideline_id != triple.guideline_id:
                    # Different guideline - this is a shared concept
                    other_guidelines_terms.append(triple)
                else:
                    # No clear guideline association - orphaned
                    orphaned_terms.append(triple)
            else:
                # No duplicates found - this is a new guideline-specific term
                guideline_specific_terms.append(triple)

        # Group triples by predicate type for easier management
        def group_triples_by_predicate(triple_list, prefix=""):
            groups = {}
            for triple in triple_list:
                predicate = triple.predicate_label or triple.predicate
                if predicate not in groups:
                    groups[predicate] = {
                        'predicate': predicate,
                        'predicate_uri': triple.predicate,
                        'triples': [],
                        'count': 0
                    }
                groups[predicate]['triples'].append(triple)
                groups[predicate]['count'] += 1
            return sorted(groups.values(), key=lambda x: x['count'], reverse=True)

        # NEW: Group triples by subject (extracted concept/term) for organized view
        def group_triples_by_subject(triple_list):
            """Group triples by their subject (extracted concept), showing all predicates for each concept."""
            groups = {}
            for triple in triple_list:
                subject_key = triple.subject_label or triple.subject
                if subject_key not in groups:
                    groups[subject_key] = {
                        'subject': subject_key,
                        'subject_uri': triple.subject,
                        'triples': [],
                        'predicates': {},  # Track predicates for this subject
                        'count': 0,
                        'concept_type': None,  # Will detect from rdf:type or similar
                        'ontology_relationships': [],  # Semantic relationships from ontology
                        'is_in_ontology': False  # Whether this concept exists in ontology
                    }

                groups[subject_key]['triples'].append(triple)
                groups[subject_key]['count'] += 1

                # Track predicate types for this concept
                predicate = triple.predicate_label or triple.predicate
                if predicate not in groups[subject_key]['predicates']:
                    groups[subject_key]['predicates'][predicate] = []
                groups[subject_key]['predicates'][predicate].append(triple)

                # Try to detect concept type from rdf:type or proethica-intermediate predicates
                if 'type' in predicate.lower() and not triple.is_literal:
                    object_value = triple.object_label or triple.object_uri or str(triple.object_literal)
                    if 'Role' in object_value:
                        groups[subject_key]['concept_type'] = 'Role'
                    elif 'Principle' in object_value:
                        groups[subject_key]['concept_type'] = 'Principle'
                    elif 'Obligation' in object_value:
                        groups[subject_key]['concept_type'] = 'Obligation'
                    elif any(t in object_value for t in ['State', 'Resource', 'Action', 'Event', 'Capability', 'Constraint']):
                        for t in ['State', 'Resource', 'Action', 'Event', 'Capability', 'Constraint']:
                            if t in object_value:
                                groups[subject_key]['concept_type'] = t
                                break

            # Check for ontology relationships for each concept
            for subject_key, group in groups.items():
                ontology_rels = get_ontology_relationships_for_concept(subject_key, group.get('concept_type'))
                if ontology_rels:
                    group['ontology_relationships'] = ontology_rels
                    group['is_in_ontology'] = True

            # Sort by count (most triples first) and then alphabetically
            return sorted(groups.values(), key=lambda x: (-x['count'], x['subject']))

        def get_ontology_relationships_for_concept(concept_label, concept_type):
            """Get semantic relationships from the ontology for a concept that matches an existing entity."""
            # Map common concept labels to ontology entities
            concept_mappings = {
                # Roles
                'engineer role': ':Engineer',
                'professional engineer role': ':Engineer',
                'structural engineer role': ':StructuralEngineerRole',
                'electrical engineer role': ':ElectricalEngineerRole',
                'mechanical engineer role': ':MechanicalEngineerRole',
                'client representative role': ':ClientRepresentativeRole',
                'project manager role': ':ProjectManagerRole',
                'public official role': ':PublicOfficialRole',

                # Principles
                'public safety principle': ':PublicSafetyPrinciple',
                'professional integrity principle': ':ProfessionalIntegrityPrinciple',
                'competence principle': ':CompetencePrinciple',
                'sustainability principle': ':SustainabilityPrinciple',

                # Obligations
                'public welfare obligation': ':PublicWelfareObligation',
                'honest service obligation': ':HonestServiceObligation',
                'continuous learning obligation': ':ContinuousLearningObligation',

                # States
                'professional competence state': ':ProfessionalCompetenceState',
                'conflict of interest state': ':ConflictOfInterestState',
                'ethical dilemma state': ':EthicalDilemmaState',
                'compliance state': ':ComplianceState',
                'risk state': ':RiskState'
            }

            # Known semantic relationships for key entities from engineering-ethics.ttl
            ontology_relationships = {
                ':Engineer': [
                    {'predicate': 'hasObligation', 'objects': ['Public Welfare Obligation', 'Honest Service Obligation', 'Continuous Learning Obligation'], 'source': 'engineering-ethics.ttl:406'},
                    {'predicate': 'adheresToPrinciple', 'objects': ['Public Safety Principle', 'Professional Integrity Principle', 'Competence Principle'], 'source': 'engineering-ethics.ttl:407'},
                    {'predicate': 'pursuesEnd', 'objects': ['Protect Public Safety, Health, and Welfare', 'Truthful and Objective Public Communication'], 'source': 'engineering-ethics.ttl:408'},
                    {'predicate': 'governedByCode', 'objects': ['NSPE Code of Ethics'], 'source': 'engineering-ethics.ttl:409'}
                ],
                ':PublicSafetyPrinciple': [
                    {'predicate': 'isAdheredToBy', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:407'},
                    {'predicate': 'isPrimaryPrinciple', 'objects': ['true'], 'source': 'NSPE Code Section I.1'},
                    {'predicate': 'sourceDocument', 'objects': ['NSPE Code of Ethics Section I.1'], 'source': 'engineering-ethics.ttl:171'}
                ],
                ':PublicWelfareObligation': [
                    {'predicate': 'isObligationOf', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:406'},
                    {'predicate': 'isPrimaryObligation', 'objects': ['true'], 'source': 'engineering-ethics.ttl:340'},
                    {'predicate': 'supersedesOtherDuties', 'objects': ['true'], 'source': 'NSPE Code I.1 fundamental canon'}
                ],
                ':CompetencePrinciple': [
                    {'predicate': 'isAdheredToBy', 'objects': ['Engineer Role'], 'source': 'Inferred from engineering-ethics.ttl:407'},
                    {'predicate': 'requiresAction', 'objects': ['Continuous Learning Obligation'], 'source': 'Professional competency requirements'},
                    {'predicate': 'sourceDocument', 'objects': ['NSPE Code of Ethics Section I.2'], 'source': 'engineering-ethics.ttl:193'}
                ]
            }

            # Check if concept matches an ontology entity (case insensitive)
            concept_key = concept_label.lower() if concept_label else ''
            ontology_entity = concept_mappings.get(concept_key)

            if ontology_entity and ontology_entity in ontology_relationships:
                return ontology_relationships[ontology_entity]

            return []

        # Create grouped data for each category (by predicate - original view)
        core_ontology_groups = group_triples_by_predicate(core_ontology_terms)
        other_guidelines_groups = group_triples_by_predicate(other_guidelines_terms)
        same_guideline_old_groups = group_triples_by_predicate(same_guideline_old_terms)
        orphaned_groups = group_triples_by_predicate(orphaned_terms)
        guideline_specific_groups = group_triples_by_predicate(guideline_specific_terms)

        # NEW: Create subject-based groupings (by extracted concept/term)
        core_ontology_subjects = group_triples_by_subject(core_ontology_terms)
        other_guidelines_subjects = group_triples_by_subject(other_guidelines_terms)
        same_guideline_old_subjects = group_triples_by_subject(same_guideline_old_terms)
        orphaned_subjects = group_triples_by_subject(orphaned_terms)
        guideline_specific_subjects = group_triples_by_subject(guideline_specific_terms)

        # All triples subject-based grouping
        all_subjects = group_triples_by_subject(triples)

        # Also create the original combined grouping for backward compatibility
        triple_groups = {}
        for triple in triples:
            predicate = triple.predicate_label or triple.predicate
            if predicate not in triple_groups:
                triple_groups[predicate] = {
                    'predicate': predicate,
                    'predicate_uri': triple.predicate,
                    'triples': [],
                    'count': 0
                }
            triple_groups[predicate]['triples'].append(triple)
            triple_groups[predicate]['count'] += 1

        # Sort groups by count (descending)
        sorted_groups = sorted(triple_groups.values(), key=lambda x: x['count'], reverse=True)

        return render_template('manage_guideline_triples.html',
                              world=world,
                              guideline=guideline,
                              triple_groups=sorted_groups,
                              core_ontology_groups=core_ontology_groups,
                              other_guidelines_groups=other_guidelines_groups,
                              same_guideline_old_groups=same_guideline_old_groups,
                              orphaned_groups=orphaned_groups,
                              guideline_specific_groups=guideline_specific_groups,
                              # NEW: Subject-based groupings (organized by extracted concept/term)
                              all_subjects=all_subjects,
                              core_ontology_subjects=core_ontology_subjects,
                              other_guidelines_subjects=other_guidelines_subjects,
                              same_guideline_old_subjects=same_guideline_old_subjects,
                              orphaned_subjects=orphaned_subjects,
                              guideline_specific_subjects=guideline_specific_subjects,
                              total_triples=len(triples),
                              core_ontology_count=len(core_ontology_terms),
                              other_guidelines_count=len(other_guidelines_terms),
                              same_guideline_old_count=len(same_guideline_old_terms),
                              orphaned_count=len(orphaned_terms),
                              guideline_specific_count=len(guideline_specific_terms))

    @bp.route('/<int:world_id>/guidelines/<int:guideline_id>/delete_triples', methods=['POST'])
    def delete_guideline_triples(world_id, guideline_id):
        """Delete selected triples for a guideline."""
        try:
            data = request.get_json()
            triple_ids = data.get('triple_ids', [])

            if not triple_ids:
                return jsonify({'success': False, 'message': 'No triples selected'}), 400

            # Verify world and guideline
            world = World.query.get_or_404(world_id)
            from app.models import Document
            guideline = Document.query.get_or_404(guideline_id)

            if guideline.world_id != world.id:
                return jsonify({'success': False, 'message': 'Invalid guideline'}), 403

            # Delete the triples
            from app.models.entity_triple import EntityTriple
            deleted_count = 0

            for triple_id in triple_ids:
                triple = EntityTriple.query.get(triple_id)
                if triple:
                    # Verify the triple belongs to this guideline
                    if (triple.guideline_id == guideline_id or
                        (guideline.guideline_metadata and
                         triple.guideline_id == guideline.guideline_metadata.get('guideline_id'))):
                        db.session.delete(triple)
                        deleted_count += 1

            db.session.commit()

            return jsonify({
                'success': True,
                'message': f'Successfully deleted {deleted_count} triples',
                'deleted_count': deleted_count
            })

        except Exception as e:
            logger.error(f"Error deleting triples: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/review_triples', methods=['GET', 'POST'])
    def review_guideline_triples(world_id, document_id):
        """Generate triples from selected concepts and allow editing before saving to ontology."""
        logger.info(f"Reviewing triples for guideline document {document_id} in world {world_id}")
        logger.info(f"Request method: {request.method}")
        logger.info(f"Form data keys: {list(request.form.keys()) if request.form else 'No form data'}")
        logger.info(f"CSRF token in form: {request.form.get('csrf_token', 'NOT FOUND')}")

        world = World.query.get_or_404(world_id)
        from app.models import Document
        guideline = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        # Handle both GET (direct access) and POST (form submission from review)
        if request.method == 'POST':
            # This is coming from the concept review form
            form_action = request.form.get('form_action')
            if form_action == 'review_triples':
                # Process concept data directly from form (no session storage to avoid cookie size limit)

                selected_concept_indices = request.form.getlist('selected_concepts')
                if not selected_concept_indices:
                    flash('No concepts selected for triple generation', 'warning')
                    return redirect(url_for('worlds.extract_concepts', id=world_id, document_id=document_id))

                # Get concepts data from form
                concepts_data = request.form.get('concepts_data')
                session_id = request.form.get('session_id')

                # Handle both temporary storage concepts and direct concepts data
                parsed_concepts = []
                if concepts_data == "cached_in_temp_storage" and session_id:
                    # Retrieve concepts from temporary storage (includes predicate suggestions)
                    try:
                        from app.services.temporary_concept_service import TemporaryConceptService
                        temp_concepts = TemporaryConceptService.get_session_concepts(session_id, status='pending')
                        parsed_concepts = [tc.concept_data for tc in temp_concepts]
                        logger.info(f"Retrieved {len(parsed_concepts)} concepts from temporary storage with session {session_id}")
                    except Exception as e:
                        logger.error(f"Error retrieving concepts from temporary storage: {e}")
                        flash('Error retrieving concepts from temporary storage', 'error')
                        return redirect(url_for('worlds.extract_concepts', id=world_id, document_id=document_id))
                elif concepts_data:
                    # Parse concepts from form data
                    try:
                        parsed_concepts = json.loads(concepts_data)
                    except Exception as e:
                        logger.error(f"Failed to parse concepts data: {e}")
                        flash('Error processing concept data', 'error')
                        return redirect(url_for('worlds.extract_concepts', id=world_id, document_id=document_id))

                if parsed_concepts and isinstance(parsed_concepts, list):
                    # Filter to selected concepts only
                    selected_indices = [int(idx) for idx in selected_concept_indices]
                    selected_concepts = [parsed_concepts[i] for i in selected_indices if i < len(parsed_concepts)]

                    logger.info(f"Processing {len(selected_concepts)} selected concepts for triple review")

                    # Generate preview triples from concepts
                    triples = _generate_preview_triples(selected_concepts, document_id, world)

                    # Extract predicate suggestions from concepts and add as relationship triples
                    predicate_triples = _extract_predicate_triples(selected_concepts, document_id, world)
                    if predicate_triples:
                        triples.extend(predicate_triples)
                        logger.info(f"Added {len(predicate_triples)} predicate suggestion triples")

                    # Organize triples by concept for better user experience
                    concept_organized_triples = _organize_triples_by_concept(selected_concepts, triples, document_id)

                    # Keep categorized version for stats
                    categorized_triples = {
                        'new_concepts': [t for t in triples if t.get('category') == 'new_concept'],
                        'additional_relationships': [t for t in triples if t.get('category') == 'relationship'],
                        'predicate_suggestions': [t for t in triples if t.get('category') == 'predicate_suggestion'],
                        'core_ontology': [t for t in triples if t.get('category') == 'existing'],
                        'other_guidelines': []
                    }

                    # Render the review page directly with the data
                    return render_template('review_guideline_triples.html',
                                         world=world,
                                         guideline=guideline,
                                         concepts=selected_concepts,
                                         triples=triples,
                                         categorized_triples=categorized_triples,
                                         concept_organized_triples=concept_organized_triples,
                                         stats=_calculate_triple_stats(triples),
                                         selected_indices=selected_indices)

                flash('No valid concept data found', 'error')
                return redirect(url_for('worlds.extract_concepts', id=world_id, document_id=document_id))

        # GET request - should not happen directly anymore, redirect to extraction
        if request.method == 'GET':
            # Direct GET access to review page is not supported without POST data
            flash('Please extract and select concepts first before reviewing triples.', 'info')
            return redirect(url_for('worlds.extract_concepts', id=world_id, document_id=document_id))

    @bp.route('/<int:world_id>/guidelines/<int:document_id>/save_triples', methods=['POST'])
    def save_guideline_triples(world_id, document_id):
        """Save the selected RDF triples to the database."""
        logger.info(f"Saving selected RDF triples for guideline document {document_id} in world {world_id}")

        world = World.query.get_or_404(world_id)

        from app.models import Document
        from app.models.guideline import Guideline
        guideline = Document.query.get_or_404(document_id)

        # Check if document belongs to this world
        if guideline.world_id != world.id:
            flash('Document does not belong to this world', 'error')
            return redirect(url_for('worlds.world_guidelines', id=world.id))

        try:
            # Get the selected triple indices from the form
            selected_triple_indices = request.form.getlist('selected_triples')

            if not selected_triple_indices:
                flash('No triples selected for saving', 'warning')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=document_id))

            # Convert to integers
            selected_indices = [int(idx) for idx in selected_triple_indices]

            # Get triples data from the form
            triples_data = request.form.get('triples_data', '[]')
            ontology_source = request.form.get('ontology_source', '')

            try:
                # First try direct JSON parsing
                try:
                    all_triples = json.loads(triples_data)
                except json.JSONDecodeError:
                    # Fall back to robust parsing only if needed
                    logger.warning("Standard JSON parsing failed, falling back to robust parser")
                    all_triples = robust_json_parse(triples_data)
            except Exception as json_error:
                logger.error(f"Error parsing triples JSON: {str(json_error)}")
                return redirect(url_for('worlds.guideline_processing_error',
                                        world_id=world_id,
                                        document_id=document_id,
                                        error_title='JSON Parsing Error',
                                        error_message='Could not parse the triple data from the form submission.',
                                        error_details=str(json_error)))

            if not all_triples:
                logger.error("No triples found in parsed data")
                return redirect(url_for('worlds.guideline_processing_error',
                                        world_id=world_id,
                                        document_id=document_id,
                                        error_title='No Triples Found',
                                        error_message='No triples were found in the data.'))

            # Get only the selected triples
            selected_triples = [all_triples[idx] for idx in selected_indices if idx < len(all_triples)]

            logger.info(f"Saving {len(selected_triples)} selected triples out of {len(all_triples)} total")

            # Get the related guideline record
            guideline_id = None
            if guideline.guideline_metadata and 'guideline_id' in guideline.guideline_metadata:
                guideline_id = guideline.guideline_metadata['guideline_id']

            if not guideline_id:
                logger.error("No guideline_id found in document metadata")
                return redirect(url_for('worlds.guideline_processing_error',
                                        world_id=world_id,
                                        document_id=document_id,
                                        error_title='Missing Guideline Record',
                                        error_message='The related guideline record was not found. Please extract and save concepts first.'))

            guideline_record = Guideline.query.get(guideline_id)

            if not guideline_record:
                logger.error(f"Guideline record with ID {guideline_id} not found")
                return redirect(url_for('worlds.guideline_processing_error',
                                        world_id=world_id,
                                        document_id=document_id,
                                        error_title='Missing Guideline Record',
                                        error_message=f'The related guideline record with ID {guideline_id} was not found.'))

            # Check for duplicates before saving
            from app.services.triple_duplicate_detection_service import get_duplicate_detection_service
            duplicate_service = get_duplicate_detection_service()

            # Save the selected triples to the database
            saved_triples = []
            skipped_duplicates = []

            for triple_data in selected_triples:
                # Check if triple has all required fields
                if not all(key in triple_data for key in ['subject', 'predicate']):
                    logger.warning(f"Skipping triple due to missing required fields: {triple_data}")
                    continue

                # Determine if this is a literal or URI object
                is_literal = triple_data.get('is_literal', False)

                if is_literal or 'object_literal' in triple_data:
                    object_literal = triple_data.get('object_literal', triple_data.get('object', ''))
                    object_uri = None
                    object_value = object_literal
                else:
                    object_literal = None
                    object_uri = triple_data.get('object', '')
                    object_value = object_uri

                # Check for duplicates before saving
                duplicate_result = duplicate_service.check_duplicate_with_details(
                    triple_data.get('subject', ''),
                    triple_data.get('predicate', ''),
                    object_value,
                    is_literal,
                    exclude_guideline_id=guideline_record.id
                )

                if duplicate_result['is_duplicate']:
                    logger.info(f"Skipping duplicate triple: {duplicate_result['details']}")
                    skipped_duplicates.append({
                        'triple': triple_data,
                        'reason': duplicate_result['details']
                    })
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

            # Update the guideline metadata
            guideline_record.guideline_metadata = {
                **(guideline_record.guideline_metadata or {}),
                "ontology_source": ontology_source,
                "updated_at": datetime.utcnow().isoformat(),
                "triples_saved": len(saved_triples)
            }

            # Update document metadata
            guideline.guideline_metadata = {
                **(guideline.guideline_metadata or {}),
                "guideline_id": guideline_record.id,
                "triples_saved": len(saved_triples),
                "triples_generated": len(all_triples)
            }

            # Commit changes
            db.session.commit()

            logger.info(f"Successfully saved {len(saved_triples)} triples for guideline {guideline_record.id} (skipped {len(skipped_duplicates)} duplicates)")

            # Add flash message with duplicate info
            if skipped_duplicates:
                flash(f'Successfully saved {len(saved_triples)} triples. Skipped {len(skipped_duplicates)} duplicates.', 'success')
            else:
                flash(f'Successfully saved {len(saved_triples)} triples.', 'success')

            # Return the success page
            return render_template('guideline_triples_saved.html',
                                   world=world,
                                   guideline=guideline,
                                   saved_triples=saved_triples,
                                   skipped_duplicates=skipped_duplicates,
                                   triple_count=len(saved_triples),
                                   world_id=world_id,
                                   document_id=document_id)

        except Exception as e:
            db.session.rollback()
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"Error saving triples: {str(e)}\n{error_trace}")
            return redirect(url_for('worlds.guideline_processing_error',
                                  world_id=world_id,
                                  document_id=document_id,
                                  error_title='Unexpected Error',
                                  error_message=f'Error saving triples: {str(e)}',
                                  error_details=error_trace))

    @bp.route('/<int:world_id>/roles/property_suggestions', methods=['GET'])
    def world_role_property_suggestions(world_id):
        """Return aggregated role property suggestions for a world as JSON."""
        try:
            world = World.query.get_or_404(world_id)
            data = RolePropertySuggestionsService.build_for_world(world.id)
            return jsonify(data)
        except Exception as e:
            logger.exception(f"Error building role property suggestions: {e}")
            return jsonify({"error": str(e)}), 500

    @bp.route('/<int:world_id>/roles/backfill_triples', methods=['POST'])
    def world_backfill_triples(world_id):
        """Backfill guideline_semantic_triples from cached relationships for this world."""
        try:
            world = World.query.get_or_404(world_id)
            from app.services.role_property_suggestions import RolePropertySuggestionsService
            result = RolePropertySuggestionsService.backfill_triples_from_cache(world.id)
            return jsonify({ 'success': True, **result })
        except Exception as e:
            logger.exception(f"Error backfilling triples: {e}")
            return jsonify({ 'success': False, 'error': str(e) }), 500
