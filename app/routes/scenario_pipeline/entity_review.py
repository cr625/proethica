"""
Entity Review Routes

Provides user interface for reviewing, editing, and approving extracted entities
before commitment to OntServe permanent storage.
"""

import json
import logging
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.models.temporary_concept import TemporaryConcept
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)

bp = Blueprint('entity_review', __name__)


@bp.route('/case/<int:case_id>/rdf_entities/update_selection', methods=['POST'])
def update_rdf_entity_selection(case_id):
    """Update the selection status of an RDF entity."""
    try:
        data = request.get_json()
        entity_id = data.get('entity_id')
        entity_type = data.get('entity_type')
        selected = data.get('selected', False)

        # Update the RDF entity selection
        entity = TemporaryRDFStorage.query.get(entity_id)
        if entity and entity.case_id == case_id:
            entity.is_selected = selected
            db.session.commit()
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Entity not found'}), 404

    except Exception as e:
        logger.error(f"Error updating RDF entity selection: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/case/<int:case_id>/entities/review/all')
@auth_optional
def review_all_case_entities(case_id):
    """Display summary and links to ALL pass reviews."""
    try:
        case_doc = Document.query.get(case_id)
        if not case_doc:
            flash(f'Case {case_id} not found', 'error')
            return redirect(url_for('index.index'))

        # Get entity counts from Step 4 helper
        from app.routes.scenario_pipeline.step4 import get_entities_summary
        entities_summary = get_entities_summary(case_id)

        return render_template(
            'scenarios/entity_review_all.html',
            case=case_doc,
            entities_summary=entities_summary
        )

    except Exception as e:
        logger.error(f"Error displaying all entity review for case {case_id}: {e}")
        flash(f'Error loading entity review: {str(e)}', 'error')
        return redirect(url_for('index.index'))


@bp.route('/case/<int:case_id>/entities/review')
@bp.route('/case/<int:case_id>/entities/review/pass1')  # Explicit Pass 1
@auth_optional  # Allow viewing without auth
def review_case_entities(case_id, section_type='facts'):
    """Display PASS 1 (Contextual Framework) extracted entities for a case.

    Args:
        case_id: The case ID
        section_type: Which section to show entities from ('facts' or 'discussion')
    """
    try:
        # Get section_type from query param if provided
        from flask import request
        section_type = request.args.get('section_type', 'facts')

        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            flash(f'Case {case_id} not found', 'error')
            return redirect(url_for('index.index'))

        # Get extraction session IDs for this section type
        from app.models import ExtractionPrompt
        section_session_ids = set()
        section_prompts = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            section_type=section_type
        ).all()
        for prompt in section_prompts:
            if prompt.extraction_session_id:
                section_session_ids.add(prompt.extraction_session_id)

        logger.info(f"Found {len(section_session_ids)} extraction sessions for {section_type} section")

        # Get RDF entities for this section's extraction sessions
        if section_session_ids:
            all_rdf_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
            ).all()
            logger.info(f"Retrieved {len(all_rdf_entities)} RDF entities for {section_type} section")
        else:
            all_rdf_entities = []
            logger.info(f"No extraction sessions found for {section_type} section")

        # Group entities by extraction_type and storage_type
        # PASS 1 entities only (Contextual Framework)
        pass1_types = ['roles', 'states', 'resources']

        # For Questions section, also include special extraction types
        if section_type == 'questions':
            pass1_types.extend([
                'questions_entity_refs',  # Matched entities from Facts/Discussion
                'roles_new_from_questions',
                'states_new_from_questions',
                'resources_new_from_questions',
                'roles_matching',
                'states_matching',
                'resources_matching'
            ])
            logger.info(f"Extended pass1_types for questions section: {pass1_types}")

        # For Conclusions section, also include special extraction types
        if section_type == 'conclusions':
            pass1_types.extend([
                'conclusions_entity_refs',  # Matched entities from Facts/Discussion/Questions
                'roles_new_from_conclusions',
                'states_new_from_conclusions',
                'resources_new_from_conclusions',
                'roles_matching',
                'states_matching',
                'resources_matching'
            ])
            logger.info(f"Extended pass1_types for conclusions section: {pass1_types}")

        rdf_by_type = {
            'roles': {'classes': [], 'individuals': [], 'relationships': []},
            'states': {'classes': [], 'individuals': [], 'relationships': []},
            'resources': {'classes': [], 'individuals': [], 'relationships': []}
        }

        # Count only Pass 1 entities
        pass1_entity_count = 0

        for entity in all_rdf_entities:
            extraction_type = entity.extraction_type or 'unknown'
            storage_type = entity.storage_type

            # Map Questions-specific types to their base types
            base_type = extraction_type

            # For questions_entity_refs or conclusions_entity_refs, check the entityType field in JSON
            if extraction_type in ['questions_entity_refs', 'conclusions_entity_refs'] and entity.rdf_json_ld:
                json_entity_type = entity.rdf_json_ld.get('entityType', '')
                json_entity_type_lower = json_entity_type.lower()
                logger.info(f"Processing entity_ref: {entity.entity_label}, JSON entityType: {json_entity_type}, storage_type: {storage_type}")
                if 'role' in json_entity_type_lower:
                    base_type = 'roles'
                elif 'state' in json_entity_type_lower:
                    base_type = 'states'
                elif 'resource' in json_entity_type_lower:
                    base_type = 'resources'
                else:
                    base_type = 'roles'  # Default to roles for backward compatibility
                logger.info(f"  -> Mapped to base_type: {base_type}")
            elif 'roles' in extraction_type:
                base_type = 'roles'
            elif 'states' in extraction_type:
                base_type = 'states'
            elif 'resources' in extraction_type:
                base_type = 'resources'

            # Case-insensitive check for extraction_type
            if extraction_type.lower() in pass1_types:
                pass1_entity_count += 1
                if storage_type == 'class':
                    rdf_by_type[base_type]['classes'].append(entity.to_dict())
                elif storage_type == 'individual':
                    rdf_by_type[base_type]['individuals'].append(entity.to_dict())
                elif storage_type == 'relationship':
                    rdf_by_type[base_type]['relationships'].append(entity.to_dict())
                    logger.info(f"  -> Added to {base_type}/relationships")

        # Get all entities grouped by section (old format for backward compatibility)
        entities_by_section = CaseEntityStorageService.get_all_case_entities(
            case_id=case_id,
            status='pending',
            group_by_section=True
        )

        # Get section information
        sections_info = CaseEntityStorageService.NSPE_SECTIONS

        # Prepare data for template
        section_data = {}
        total_entities = 0

        for section_type, entities in entities_by_section.items():
            if section_type == 'all':
                continue

            section_data[section_type] = {
                'info': sections_info.get(section_type, {
                    'label': section_type.title(),
                    'description': 'Unknown section type',
                    'primary_entities': []
                }),
                'entities': entities,
                'count': len(entities),
                'selected_count': sum(1 for e in entities if e.concept_data.get('selected', False))
            }
            total_entities += len(entities)

        # Detect cross-section duplicates
        # Get entities from OTHER sections for comparison
        other_sections = ['facts', 'discussion', 'questions', 'conclusions', 'dissenting_opinion']
        other_sections.remove(section_type) if section_type in other_sections else None

        cross_section_entities = {}
        for other_section in other_sections:
            other_prompts = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                section_type=other_section
            ).all()
            other_session_ids = {p.extraction_session_id for p in other_prompts if p.extraction_session_id}

            if other_session_ids:
                other_entities = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.case_id == case_id,
                    TemporaryRDFStorage.extraction_session_id.in_(other_session_ids)
                ).all()

                cross_section_entities[other_section] = {
                    e.entity_label.lower(): {
                        'label': e.entity_label,
                        'section': other_section,
                        'type': e.entity_type,
                        'id': e.id
                    } for e in other_entities
                }

        # Add cross-section duplicate info to each entity
        for concept_type in rdf_by_type:
            for entity in rdf_by_type[concept_type]['classes']:
                entity['cross_section_matches'] = []
                entity_label_lower = entity['entity_label'].lower()

                for other_section, other_entities in cross_section_entities.items():
                    if entity_label_lower in other_entities:
                        entity['cross_section_matches'].append({
                            'section': other_section,
                            'section_label': other_section.replace('_', ' ').title()
                        })

            for entity in rdf_by_type[concept_type]['individuals']:
                entity['cross_section_matches'] = []
                entity_label_lower = entity['entity_label'].lower()

                for other_section, other_entities in cross_section_entities.items():
                    if entity_label_lower in other_entities:
                        entity['cross_section_matches'].append({
                            'section': other_section,
                            'section_label': other_section.replace('_', ' ').title()
                        })

        # Prepare RDF data organized by concept type
        rdf_data = {
            'by_type': rdf_by_type,
            'total_rdf_entities': pass1_entity_count  # Use Pass 1 count, not all entities
        }

        # For Conclusions section, also get Question→Conclusion links
        question_conclusion_links = []
        if section_type == 'conclusions' and section_session_ids:
            qc_links = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type == 'question_conclusion_link',
                TemporaryRDFStorage.extraction_session_id.in_(section_session_ids)
            ).all()

            for link in qc_links:
                if link.rdf_json_ld:
                    question_conclusion_links.append({
                        'question_number': link.rdf_json_ld.get('questionNumber'),
                        'question_text': link.rdf_json_ld.get('questionText', ''),
                        'conclusion_text': link.rdf_json_ld.get('conclusionText', ''),
                        'confidence': link.rdf_json_ld.get('confidence', 0),
                        'reasoning': link.rdf_json_ld.get('reasoning', '')
                    })

            logger.info(f"Found {len(question_conclusion_links)} Question→Conclusion links")

        # Fetch existing classes from OntServe for reference display
        ontserve_classes = {
            'roles': [],
            'states': [],
            'resources': []
        }
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            mcp_client = get_external_mcp_client()

            # Fetch existing role classes
            existing_roles = mcp_client.get_all_role_entities()
            for role in existing_roles:
                ontserve_classes['roles'].append({
                    'label': role.get('label', ''),
                    'description': role.get('description', role.get('comment', '')),
                    'uri': role.get('uri', '')
                })

            # Fetch existing state classes
            existing_states = mcp_client.get_all_state_entities()
            for state in existing_states:
                ontserve_classes['states'].append({
                    'label': state.get('label', ''),
                    'description': state.get('description', state.get('comment', '')),
                    'uri': state.get('uri', '')
                })

            # Fetch existing resource classes
            existing_resources = mcp_client.get_all_resource_entities()
            for resource in existing_resources:
                ontserve_classes['resources'].append({
                    'label': resource.get('label', ''),
                    'description': resource.get('description', resource.get('comment', '')),
                    'uri': resource.get('uri', '')
                })

            logger.info(f"Fetched OntServe classes: {len(ontserve_classes['roles'])} roles, "
                       f"{len(ontserve_classes['states'])} states, {len(ontserve_classes['resources'])} resources")
        except Exception as e:
            logger.warning(f"Could not fetch OntServe classes: {e}")

        return render_template(
            'scenarios/entity_review.html',
            case=case_doc,
            section_data=section_data,
            total_entities=total_entities,
            sections_info=sections_info,
            rdf_data=rdf_data,
            section_type=section_type,  # Pass section_type to template
            section_label=section_type.replace('_', ' ').title(),  # 'facts' -> 'Facts', 'discussion' -> 'Discussion'
            question_conclusion_links=question_conclusion_links,  # Pass Q→C links for Conclusions section
            ontserve_classes=ontserve_classes  # Pass OntServe classes for reference
        )

    except Exception as e:
        logger.error(f"Error displaying entity review for case {case_id}: {e}")
        flash(f'Error loading entity review: {str(e)}', 'error')
        return redirect(url_for('index.index'))


@bp.route('/case/<int:case_id>/entities/review/pass2')
@auth_optional  # Allow viewing without auth
def review_case_entities_pass2(case_id, section_type=None):
    """Display PASS 2 (Normative Requirements) extracted entities for a case.

    Args:
        case_id: The case ID
        section_type: Optional section filter ('facts', 'discussion', 'questions', 'conclusions', 'references')
    """
    try:
        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            flash(f'Case {case_id} not found', 'error')
            return redirect(url_for('index.index'))

        # Get section_type from query params if not provided as argument
        if section_type is None:
            section_type = request.args.get('section_type')

        # Pass 2 extraction types
        pass2_types = ['principles', 'obligations', 'constraints', 'capabilities']

        # Get RDF entities - filter by section_type if provided
        all_rdf_entities = []
        if section_type:
            # Filter by section_type using the extraction_session_id relationship
            from app.models import ExtractionPrompt
            # Get extraction sessions for this case and section
            session_ids = db.session.query(ExtractionPrompt.extraction_session_id).filter(
                ExtractionPrompt.case_id == case_id,
                ExtractionPrompt.section_type == section_type,
                ExtractionPrompt.step_number == 2
            ).distinct().all()
            session_ids = [sid[0] for sid in session_ids if sid[0]]

            if session_ids:
                all_rdf_entities = TemporaryRDFStorage.query.filter(
                    TemporaryRDFStorage.case_id == case_id,
                    TemporaryRDFStorage.extraction_session_id.in_(session_ids)
                ).all()
            else:
                # No extraction has been run for this section
                logger.warning(f"No Pass 2 extraction found for case {case_id} section_type={section_type}")
        else:
            # Get all Pass 2 entities for this case (filter by extraction_type)
            all_rdf_entities = TemporaryRDFStorage.query.filter(
                TemporaryRDFStorage.case_id == case_id,
                TemporaryRDFStorage.extraction_type.in_(pass2_types)
            ).all()

        # Group entities by extraction_type and storage_type
        # PASS 2 entities only (Normative Requirements)
        rdf_by_type = {
            'principles': {'classes': [], 'individuals': []},
            'obligations': {'classes': [], 'individuals': []},
            'constraints': {'classes': [], 'individuals': []},
            'capabilities': {'classes': [], 'individuals': []}
        }

        for entity in all_rdf_entities:
            extraction_type = entity.extraction_type or 'unknown'
            storage_type = entity.storage_type

            if extraction_type in rdf_by_type:
                if storage_type == 'class':
                    rdf_by_type[extraction_type]['classes'].append(entity.to_dict())
                elif storage_type == 'individual':
                    rdf_by_type[extraction_type]['individuals'].append(entity.to_dict())

        # Count total RDF entities for this pass
        total_rdf_entities = sum(
            len(type_data['classes']) + len(type_data['individuals'])
            for type_data in rdf_by_type.values()
        )

        # Check for any entities
        has_entities = total_rdf_entities > 0

        # Prepare RDF data with total count
        rdf_data = {
            'by_type': rdf_by_type,
            'total_rdf_entities': total_rdf_entities
        }

        # Determine section display name
        section_display = section_type.capitalize() if section_type else "All Sections"

        # Fetch existing classes from OntServe for Pass 2 concept types
        ontserve_classes = {
            'principles': [],
            'obligations': [],
            'constraints': [],
            'capabilities': []
        }
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            mcp_client = get_external_mcp_client()

            # Fetch existing principle classes
            existing_principles = mcp_client.get_all_principle_entities()
            for p in existing_principles:
                ontserve_classes['principles'].append({
                    'label': p.get('label', ''),
                    'description': p.get('description', p.get('comment', '')),
                    'uri': p.get('uri', '')
                })

            # Fetch existing obligation classes
            existing_obligations = mcp_client.get_all_obligation_entities()
            for o in existing_obligations:
                ontserve_classes['obligations'].append({
                    'label': o.get('label', ''),
                    'description': o.get('description', o.get('comment', '')),
                    'uri': o.get('uri', '')
                })

            # Fetch existing constraint classes
            existing_constraints = mcp_client.get_all_constraint_entities()
            for c in existing_constraints:
                ontserve_classes['constraints'].append({
                    'label': c.get('label', ''),
                    'description': c.get('description', c.get('comment', '')),
                    'uri': c.get('uri', '')
                })

            # Fetch existing capability classes
            existing_capabilities = mcp_client.get_all_capability_entities()
            for cap in existing_capabilities:
                ontserve_classes['capabilities'].append({
                    'label': cap.get('label', ''),
                    'description': cap.get('description', cap.get('comment', '')),
                    'uri': cap.get('uri', '')
                })

            logger.info(f"Fetched OntServe Pass 2 classes: {len(ontserve_classes['principles'])} principles, "
                       f"{len(ontserve_classes['obligations'])} obligations, {len(ontserve_classes['constraints'])} constraints, "
                       f"{len(ontserve_classes['capabilities'])} capabilities")
        except Exception as e:
            logger.warning(f"Could not fetch OntServe Pass 2 classes: {e}")

        # Return the entity review page for Pass 2
        return render_template('scenarios/entity_review_pass2.html',
                             case=case_doc,
                             rdf_data=rdf_data,
                             section_data={},  # Empty for new RDF format
                             has_entities=has_entities,
                             pass_number=2,
                             pass_name="Normative Requirements",
                             section_type=section_type,
                             section_display=section_display,
                             ontserve_classes=ontserve_classes)

    except Exception as e:
        logger.error(f"Error displaying Pass 2 entity review for case {case_id}: {e}")
        flash(f'Error loading entity review: {str(e)}', 'error')
        return redirect(url_for('index.index'))


# DEPRECATED: Old Pass 3 review route - replaced by review_enhanced_temporal
# Route removed as entity_review_pass3.html template has been archived
# Use /case/<int:case_id>/enhanced_temporal/review instead


@bp.route('/case/<int:case_id>/entities/session/<session_id>')
def review_session_entities(case_id, session_id):
    """Display entities for a specific extraction session."""
    try:
        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            flash(f'Case {case_id} not found', 'error')
            return redirect(url_for('index.index'))

        # Get session entities
        entities = CaseEntityStorageService.get_case_session_entities(
            case_id=case_id,
            session_id=session_id,
            status='pending'
        )

        if not entities:
            flash(f'No entities found for session {session_id}', 'warning')
            return redirect(url_for('entity_review.review_case_entities', case_id=case_id))

        # Get session summary
        session_summary = CaseEntityStorageService.create_entity_extraction_session_summary(
            case_id=case_id,
            session_id=session_id
        )

        return render_template(
            'scenarios/session_review.html',
            case=case_doc,
            entities=entities,
            session_summary=session_summary,
            session_id=session_id
        )

    except Exception as e:
        logger.error(f"Error displaying session review for {session_id}: {e}")
        flash(f'Error loading session review: {str(e)}', 'error')
        return redirect(url_for('entity_review.review_case_entities', case_id=case_id))


@bp.route('/case/<int:case_id>/entities/update_selection', methods=['POST'])
def update_entity_selection(case_id):
    """Update entity selection status."""
    try:
        data = request.get_json()
        entity_id = data.get('entity_id')
        selected = data.get('selected', False)
        review_notes = data.get('review_notes', '')

        if not entity_id:
            return jsonify({'success': False, 'error': 'Entity ID required'})

        # Update selection
        success = CaseEntityStorageService.update_entity_selection(
            temp_concept_id=entity_id,
            selected=selected,
            review_notes=review_notes,
            modified_by=request.remote_addr  # Use IP as identifier
        )

        if success:
            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'selected': selected
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Entity not found'
            })

    except Exception as e:
        logger.error(f"Error updating entity selection: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@bp.route('/case/<int:case_id>/entities/commit', methods=['POST'])
@auth_required_for_write  # Require auth for write operations
def commit_entities_to_ontserve(case_id):
    """Commit selected RDF entities to OntServe permanent storage."""
    try:
        # Import the new commit service
        from app.services.ontserve_commit_service import OntServeCommitService

        data = request.get_json() if request.is_json else request.form

        # Handle both old format (session_ids) and new format (entity_ids)
        entity_ids = data.get('entity_ids', [])

        # If no entity_ids provided, get all selected RDF entities
        if not entity_ids:
            selected_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                is_selected=True,
                is_committed=False
            ).all()
            entity_ids = [e.id for e in selected_entities]

        if not entity_ids:
            return jsonify({
                'success': False,
                'error': 'No entities selected for commit'
            })

        # Use the new commit service
        commit_service = OntServeCommitService()
        result = commit_service.commit_selected_entities(case_id, entity_ids)

        if result['success']:
            message = f"Successfully committed {result['classes_committed']} classes and {result['individuals_committed']} individuals to OntServe"

            if result.get('errors'):
                message += f" (with {len(result['errors'])} warnings)"

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': message,
                    'result': result
                })
            else:
                flash(message, 'success')
                return redirect(url_for('entity_review.review_case_entities', case_id=case_id))
        else:
            error_msg = f"Failed to commit entities: {result.get('error', 'Unknown error')}"

            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': error_msg
                })
            else:
                flash(error_msg, 'error')
                return redirect(url_for('entity_review.review_case_entities', case_id=case_id))

    except Exception as e:
        logger.error(f"Error committing entities: {e}")
        error_msg = f"Error committing entities: {str(e)}"

        if request.is_json:
            return jsonify({
                'success': False,
                'error': error_msg
            })
        else:
            flash(error_msg, 'error')
            return redirect(url_for('entity_review.review_case_entities', case_id=case_id))


@bp.route('/case/<int:case_id>/entities/commit_status')
def get_commit_status(case_id):
    """Get the commit status for a case."""
    try:
        from app.services.ontserve_commit_service import OntServeCommitService

        commit_service = OntServeCommitService()
        status = commit_service.get_commit_status(case_id)

        return jsonify({
            'success': True,
            'status': status
        })

    except Exception as e:
        logger.error(f"Error getting commit status: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@bp.route('/case/<int:case_id>/entities/sessions')
def list_extraction_sessions(case_id):
    """List all extraction sessions for a case."""
    try:
        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            return jsonify({'error': 'Case not found'})

        # Get all sessions for this case
        sessions_query = db.session.query(
            TemporaryConcept.session_id,
            TemporaryConcept.extraction_timestamp,
            TemporaryConcept.extraction_method,
            TemporaryConcept.status,
            db.func.count(TemporaryConcept.id).label('entity_count'),
            db.func.avg(
                db.cast(TemporaryConcept.concept_data['confidence'].astext, db.Float)
            ).label('avg_confidence')
        ).filter_by(
            document_id=case_id
        ).group_by(
            TemporaryConcept.session_id,
            TemporaryConcept.extraction_timestamp,
            TemporaryConcept.extraction_method,
            TemporaryConcept.status
        ).order_by(
            TemporaryConcept.extraction_timestamp.desc()
        )

        sessions = []
        for session in sessions_query.all():
            # Get section type from first entity in session
            first_entity = TemporaryConcept.query.filter_by(
                document_id=case_id,
                session_id=session.session_id
            ).first()

            section_type = 'unknown'
            if first_entity and first_entity.concept_data:
                section_type = first_entity.concept_data.get('section_type', 'unknown')

            sessions.append({
                'session_id': session.session_id,
                'extraction_timestamp': session.extraction_timestamp.isoformat(),
                'extraction_method': session.extraction_method,
                'status': session.status,
                'entity_count': session.entity_count,
                'avg_confidence': float(session.avg_confidence) if session.avg_confidence else 0.0,
                'section_type': section_type,
                'section_info': CaseEntityStorageService.NSPE_SECTIONS.get(section_type, {})
            })

        return jsonify({
            'case_id': case_id,
            'sessions': sessions,
            'total_sessions': len(sessions)
        })

    except Exception as e:
        logger.error(f"Error listing sessions for case {case_id}: {e}")
        return jsonify({'error': str(e)})


@bp.route('/case/<int:case_id>/entities/clear_by_types', methods=['POST'])
@auth_required_for_write  # Require auth for write operations
def clear_entities_by_types(case_id):
    """Clear temporary entities for specific extraction types, optionally filtered by section."""
    try:
        # Get the extraction types to clear from request
        data = request.get_json() or {}
        extraction_types = data.get('extraction_types', [])
        section_type = data.get('section_type')  # Optional section filter

        if not extraction_types:
            return jsonify({'success': False, 'error': 'No extraction types specified'})

        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            return jsonify({'success': False, 'error': 'Case not found'})

        cleared_stats = {
            'rdf_triples': 0,
            'extraction_prompts': 0,
            'types_cleared': extraction_types,
            'section_type': section_type
        }

        # If section_type is specified, get session IDs for that section
        from app.models import TemporaryRDFStorage, ExtractionPrompt

        section_session_ids = None
        if section_type:
            section_prompts = ExtractionPrompt.query.filter_by(
                case_id=case_id,
                section_type=section_type
            ).all()
            section_session_ids = {p.extraction_session_id for p in section_prompts if p.extraction_session_id}
            logger.info(f"Clearing entities from {section_type} section (sessions: {section_session_ids})")

        # Count and delete entities for specified types
        for extraction_type in extraction_types:
            query = db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                extraction_type=extraction_type,
                is_committed=False
            )

            # Add section filter if specified
            if section_session_ids is not None:
                query = query.filter(TemporaryRDFStorage.extraction_session_id.in_(section_session_ids))

            type_count = query.count()
            cleared_stats['rdf_triples'] += type_count

            # Delete with same filters
            delete_query = db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                extraction_type=extraction_type,
                is_committed=False
            )
            if section_session_ids is not None:
                delete_query = delete_query.filter(TemporaryRDFStorage.extraction_session_id.in_(section_session_ids))
            delete_query.delete()

        # Delete extraction prompts for specified types
        # NOTE: We delete prompts for ALL sections, not just the current section,
        # because prompts can exist in different sections than the entities
        for extraction_type in extraction_types:
            prompt_query = db.session.query(ExtractionPrompt).filter_by(
                case_id=case_id,
                concept_type=extraction_type
            )

            # Count prompts that will be deleted
            prompt_count = prompt_query.count()
            cleared_stats['extraction_prompts'] += prompt_count

            # Delete prompts for this extraction type (all sections)
            delete_query = db.session.query(ExtractionPrompt).filter_by(
                case_id=case_id,
                concept_type=extraction_type
            )
            delete_query.delete(synchronize_session='fetch')

        db.session.commit()

        # Count remaining entities
        remaining_count = db.session.query(TemporaryRDFStorage).filter_by(
            case_id=case_id,
            is_committed=False
        ).count()

        committed_count = db.session.query(TemporaryRDFStorage).filter_by(
            case_id=case_id,
            is_committed=True
        ).count()

        section_label = section_type.replace('_', ' ').title() if section_type else 'all sections'
        message = f"Cleared {cleared_stats['rdf_triples']} entities from {section_label} for types: {', '.join(extraction_types)}"
        if remaining_count > 0:
            message += f"\n{remaining_count} entities from other passes/sections remain."
        if committed_count > 0:
            message += f"\n{committed_count} committed entities preserved."

        return jsonify({
            'success': True,
            'message': message,
            'cleared_stats': cleared_stats,
            'cleared_count': cleared_stats['rdf_triples'],
            'remaining_count': remaining_count,
            'preserved_count': committed_count
        })

    except Exception as e:
        logger.error(f"Error clearing entities by types for case {case_id}: {e}")
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})


@bp.route('/case/<int:case_id>/entities/clear_all', methods=['POST'])
@auth_required_for_write  # Require auth for write operations
def clear_all_entities(case_id):
    """Clear all temporary entities, RDF storage, and extraction prompts for a case."""
    try:
        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            return jsonify({'success': False, 'error': 'Case not found'})

        cleared_stats = {
            'legacy_concepts': 0,
            'rdf_triples': 0,
            'extraction_prompts': 0
        }

        # 1. Clear legacy temporary entities for this case
        from app.models.temporary_concept import TemporaryConcept
        cleared_stats['legacy_concepts'] = db.session.query(TemporaryConcept).filter_by(document_id=case_id).count()
        db.session.query(TemporaryConcept).filter_by(document_id=case_id).delete()

        # 2. Clear ONLY UNCOMMITTED RDF storage (preserve committed records)
        from app.models import TemporaryRDFStorage

        # Count committed entities that will be preserved
        committed_count = db.session.query(TemporaryRDFStorage).filter_by(
            case_id=case_id,
            is_committed=True
        ).count()

        # Only delete uncommitted entities
        cleared_stats['rdf_triples'] = db.session.query(TemporaryRDFStorage).filter_by(
            case_id=case_id,
            is_committed=False
        ).count()
        db.session.query(TemporaryRDFStorage).filter_by(
            case_id=case_id,
            is_committed=False
        ).delete()

        # 3. Clear saved extraction prompts and responses
        from app.models.extraction_prompt import ExtractionPrompt
        cleared_stats['extraction_prompts'] = db.session.query(ExtractionPrompt).filter_by(case_id=case_id).count()
        db.session.query(ExtractionPrompt).filter_by(case_id=case_id).delete()

        # Add committed count to stats
        cleared_stats['preserved_committed'] = committed_count

        # Commit all changes
        db.session.commit()

        total_cleared = sum(cleared_stats.values())
        logger.info(f"Cleared all data for case {case_id}: {cleared_stats}")

        # Create appropriate message based on what was cleared and preserved
        message_parts = []
        if cleared_stats['legacy_concepts'] > 0:
            message_parts.append(f"{cleared_stats['legacy_concepts']} legacy entities")
        if cleared_stats['rdf_triples'] > 0:
            message_parts.append(f"{cleared_stats['rdf_triples']} uncommitted RDF records")
        if cleared_stats['extraction_prompts'] > 0:
            message_parts.append(f"{cleared_stats['extraction_prompts']} saved prompts")

        message = f"Cleared {', '.join(message_parts)}" if message_parts else "No uncommitted entities to clear"

        if committed_count > 0:
            message += f". Preserved {committed_count} committed entities in OntServe."

        return jsonify({
            'success': True,
            'cleared_count': total_cleared,
            'preserved_count': committed_count,
            'details': cleared_stats,
            'case_id': case_id,
            'message': message
        })

    except Exception as e:
        logger.error(f"Error clearing entities for case {case_id}: {e}")
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        })


@bp.route('/case/<int:case_id>/entities/summary')
def get_case_summary(case_id):
    """Get summary statistics for case entities."""
    try:
        # Get all entities for the case
        entities_by_section = CaseEntityStorageService.get_all_case_entities(
            case_id=case_id,
            status='pending',
            group_by_section=True
        )

        # Calculate summary statistics
        summary = {
            'case_id': case_id,
            'total_entities': 0,
            'total_selected': 0,
            'sections': {},
            'categories': {},
            'confidence_distribution': {
                'high': 0,    # >0.8
                'medium': 0,  # 0.6-0.8
                'low': 0      # <0.6
            }
        }

        for section_type, entities in entities_by_section.items():
            if section_type == 'all':
                continue

            section_stats = {
                'entity_count': len(entities),
                'selected_count': 0,
                'categories': {}
            }

            for entity in entities:
                summary['total_entities'] += 1

                if entity.concept_data.get('selected', False):
                    summary['total_selected'] += 1
                    section_stats['selected_count'] += 1

                # Category statistics
                category = entity.concept_data.get('category', 'Unknown')
                summary['categories'][category] = summary['categories'].get(category, 0) + 1
                section_stats['categories'][category] = section_stats['categories'].get(category, 0) + 1

                # Confidence distribution
                confidence = entity.concept_data.get('confidence', 0.8)
                if confidence > 0.8:
                    summary['confidence_distribution']['high'] += 1
                elif confidence >= 0.6:
                    summary['confidence_distribution']['medium'] += 1
                else:
                    summary['confidence_distribution']['low'] += 1

            summary['sections'][section_type] = section_stats

        return jsonify(summary)

    except Exception as e:
        logger.error(f"Error getting case summary for {case_id}: {e}")
        return jsonify({'error': str(e)})


@bp.route('/ontology/clear_extracted_classes', methods=['POST'])
def clear_extracted_classes():
    """Clear all extracted classes from proethica-intermediate-extracted.ttl.

    This is useful for testing with a clean slate.
    Creates a backup before clearing.
    """
    try:
        from app.services.ontserve_commit_service import OntServeCommitService

        commit_service = OntServeCommitService()
        result = commit_service.clear_extracted_classes()

        if result['success']:
            message = result.get('message', 'Successfully cleared extracted classes')

            if request.is_json:
                return jsonify({
                    'success': True,
                    'message': message,
                    'result': result
                })
            else:
                flash(message, 'success')
                # Redirect to a sensible location - maybe the main page
                return redirect(url_for('index.index'))
        else:
            error_msg = f"Failed to clear extracted classes: {result.get('error', 'Unknown error')}"

            if request.is_json:
                return jsonify({
                    'success': False,
                    'error': error_msg
                })
            else:
                flash(error_msg, 'error')
                return redirect(url_for('index.index'))

    except Exception as e:
        logger.error(f"Error clearing extracted classes: {e}")
        error_msg = f"Error clearing extracted classes: {str(e)}"

        if request.is_json:
            return jsonify({
                'success': False,
                'error': error_msg
            })
        else:
            flash(error_msg, 'error')
            return redirect(url_for('index.index'))


@bp.route('/case/<int:case_id>/entities/refresh_committed', methods=['POST'])
@auth_required_for_write  # Require auth for write operations
def refresh_committed_from_ontserve(case_id):
    """Refresh committed entities with live data from OntServe.

    This addresses synchronization issues by pulling the latest versions
    of committed entities from OntServe and updating ProEthica's records.
    Also removes entities that have been deleted from OntServe.
    """
    try:
        from app.services.ontserve_data_fetcher import OntServeDataFetcher

        # Get all committed entities from ProEthica
        committed_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            is_committed=True
        ).all()

        if not committed_entities:
            return jsonify({
                'success': True,
                'message': 'No committed entities to refresh',
                'refreshed': 0
            })

        # Convert to dictionary format for comparison
        proethica_entities = [entity.to_dict() for entity in committed_entities]

        # Initialize fetcher and refresh
        fetcher = OntServeDataFetcher()
        refresh_result = fetcher.refresh_committed_entities(case_id, proethica_entities)

        # Update ProEthica records with OntServe data if there are changes
        update_count = 0
        delete_count = 0

        for detail in refresh_result['details']:
            if detail['status'] == 'modified':
                # Find the entity in ProEthica
                entity_uri = detail['entity_uri']
                entity = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    entity_uri=entity_uri,
                    is_committed=True
                ).first()

                if entity and 'ontserve_data' in detail:
                    # Update with live data from OntServe
                    ontserve_data = detail['ontserve_data']
                    entity.entity_label = ontserve_data.get('label', entity.entity_label)
                    # Note: parent_uri field doesn't exist in TemporaryRDFStorage
                    # entity.parent_uri = ontserve_data.get('parent_uri')

                    # Update the review notes to track sync
                    sync_note = f"Synced from OntServe at {datetime.utcnow().isoformat()}"
                    if entity.review_notes:
                        entity.review_notes = f"{entity.review_notes}\n{sync_note}"
                    else:
                        entity.review_notes = sync_note

                    update_count += 1

            elif detail['status'] == 'not_found':
                # Entity was deleted from OntServe, remove from ProEthica
                entity_uri = detail['entity_uri']
                entity = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    entity_uri=entity_uri,
                    is_committed=True
                ).first()

                if entity:
                    db.session.delete(entity)
                    delete_count += 1
                    logger.info(f"Removed deleted entity {entity_uri} from ProEthica")

        # Commit all updates and deletions
        if update_count > 0 or delete_count > 0:
            db.session.commit()
            logger.info(f"Updated {update_count} entities and removed {delete_count} deleted entities for case {case_id}")

        # Prepare response message
        message_parts = []
        if refresh_result['unchanged'] > 0:
            message_parts.append(f"{refresh_result['unchanged']} unchanged")
        if refresh_result['modified'] > 0:
            message_parts.append(f"{refresh_result['modified']} updated")
        if delete_count > 0:
            message_parts.append(f"{delete_count} removed (deleted from OntServe)")
        elif refresh_result['not_found'] > 0:
            message_parts.append(f"{refresh_result['not_found']} removed (not found in OntServe)")

        message = f"Refreshed {refresh_result['refreshed']} entities: {', '.join(message_parts)}"

        return jsonify({
            'success': True,
            'message': message,
            'result': refresh_result,
            'deleted_count': delete_count
        })

    except Exception as e:
        logger.error(f"Error refreshing committed entities from OntServe: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })


@bp.route('/case/<int:case_id>/entities/temporal/commit', methods=['POST'])
def commit_temporal_entities(case_id):
    """Commit all temporal dynamics entities to OntServe."""
    try:
        from app.services.temporal_commit_service import TemporalCommitService

        commit_service = TemporalCommitService()
        result = commit_service.commit_temporal_entities(case_id)

        if result['success']:
            return jsonify(result)
        else:
            # Check if this is "already committed" vs actual error
            error_msg = result.get('error', '')
            if 'No uncommitted' in error_msg or 'already committed' in error_msg.lower():
                # Not an error - entities are already committed
                return jsonify({
                    'success': True,
                    'message': 'All temporal entities have already been committed',
                    'already_committed': True
                })
            else:
                # Actual error
                return jsonify(result), 500

    except Exception as e:
        logger.error(f"Error committing temporal entities: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@bp.route('/case/<int:case_id>/enhanced_temporal/review')
@auth_optional
def review_enhanced_temporal(case_id):
    """
    Review page for Enhanced Temporal Dynamics extraction results.

    Displays:
    - Extracted actions and events
    - Temporal markers and Allen relations
    - Timeline visualization with OWL-Time integration
    - Causal chains and NESS test results
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)

        # Get all temporal dynamics entities from database
        temporal_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).all()

        # Separate entities by type
        actions = []
        events = []
        allen_relations = []
        causal_chains = []
        timeline = None

        for entity in temporal_entities:
            entity_dict = entity.to_dict()
            rdf_data = entity.rdf_json_ld or {}
            entity_type = rdf_data.get('@type', '')

            if 'Action' in entity_type:
                actions.append({
                    'id': entity.id,
                    'label': entity.entity_label,
                    'uri': entity.entity_uri,
                    'description': rdf_data.get('proeth:description', ''),
                    'agent': rdf_data.get('proeth:hasAgent', ''),
                    'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                    'mental_state': rdf_data.get('proeth:hasMentalState', ''),
                    'intended_outcome': rdf_data.get('proeth:intendedOutcome', ''),
                    'fulfills_obligation': rdf_data.get('proeth:fulfillsObligation', []),
                    'guided_by_principle': rdf_data.get('proeth:guidedByPrinciple', []),
                    'within_competence': rdf_data.get('proeth:withinCompetence', False),
                    'requires_capability': rdf_data.get('proeth:requiresCapability', []),
                    'rdf_json': rdf_data
                })

            elif 'Event' in entity_type:
                events.append({
                    'id': entity.id,
                    'label': entity.entity_label,
                    'uri': entity.entity_uri,
                    'description': rdf_data.get('proeth:description', ''),
                    'affected_entity': rdf_data.get('proeth:affectsEntity', ''),
                    'temporal_marker': rdf_data.get('proeth:temporalMarker', ''),
                    'triggers_state': rdf_data.get('proeth:triggersState', []),
                    'activates_constraint': rdf_data.get('proeth:activatesConstraint', []),
                    'transforms_obligation': rdf_data.get('proeth:transformsObligation', []),
                    'emergency_level': rdf_data.get('proeth:emergencyLevel', ''),
                    'rdf_json': rdf_data
                })

            elif 'CausalChain' in entity_type:
                causal_chains.append({
                    'id': entity.id,
                    'cause': rdf_data.get('proeth:cause', ''),
                    'effect': rdf_data.get('proeth:effect', ''),
                    'causal_language': rdf_data.get('proeth:causalLanguage', ''),
                    'necessary_factors': rdf_data.get('proeth:necessaryFactors', []),
                    'sufficient_factors': rdf_data.get('proeth:sufficientFactors', []),
                    'counterfactual': rdf_data.get('proeth:counterfactual', ''),
                    'responsible_agent': rdf_data.get('proeth:responsibleAgent', ''),
                    'responsibility_type': rdf_data.get('proeth:responsibilityType', ''),
                    'within_agent_control': rdf_data.get('proeth:withinAgentControl', False),
                    'causal_sequence': rdf_data.get('proeth:causalSequence', []),
                    'rdf_json': rdf_data
                })

            elif 'Timeline' in entity.entity_label:
                timeline = {
                    'id': entity.id,
                    'label': entity.entity_label,
                    'uri': entity.entity_uri,
                    'total_elements': rdf_data.get('proeth:totalElements', 0),
                    'action_count': rdf_data.get('proeth:actionCount', 0),
                    'event_count': rdf_data.get('proeth:eventCount', 0),
                    'timepoints': rdf_data.get('proeth:hasTimepoints', []),
                    'temporal_consistency': rdf_data.get('proeth:temporalConsistency', {}),
                    'rdf_json': rdf_data
                }

            elif entity.entity_type == 'allen_relations':
                # Allen relation with OWL-Time mapping
                allen_relations.append({
                    'id': entity.id,
                    'label': entity.entity_label,
                    'from_entity': rdf_data.get('proeth:fromEntity', ''),
                    'to_entity': rdf_data.get('proeth:toEntity', ''),
                    'relation_type': rdf_data.get('proeth:allenRelation', 'unknown'),
                    'owl_time_property': rdf_data.get('proeth:owlTimeProperty', ''),
                    'owl_time_uri': rdf_data.get('proeth:owlTimeURI', ''),
                    'description': rdf_data.get('proeth:description', ''),
                    'evidence': rdf_data.get('proeth:evidence', ''),
                    'rdf_json': rdf_data
                })

        extraction_complete = len(temporal_entities) > 0

        # Check commit status
        uncommitted_count = sum(1 for e in temporal_entities if not e.is_committed)
        committed_count = sum(1 for e in temporal_entities if e.is_committed)
        all_committed = extraction_complete and uncommitted_count == 0

        # Calculate summary statistics
        summary = {
            'total_entities': len(temporal_entities),
            'actions': len(actions),
            'events': len(events),
            'allen_relations': len(allen_relations),
            'causal_chains': len(causal_chains),
            'has_timeline': timeline is not None,
            'committed_count': committed_count,
            'uncommitted_count': uncommitted_count,
            'all_committed': all_committed
        }

        context = {
            'case': case,
            'current_step': 3,
            'step_title': 'Enhanced Temporal Dynamics - Review',
            'extraction_complete': extraction_complete,
            'actions': actions,
            'events': events,
            'allen_relations': allen_relations,
            'causal_chains': causal_chains,
            'timeline': timeline,
            'summary': summary,
            'all_committed': all_committed
        }

        return render_template('entity_review/enhanced_temporal_review.html', **context)

    except Exception as e:
        logger.error(f"Error loading enhanced temporal review for case {case_id}: {e}")
        flash(f"Error loading review page: {str(e)}", 'danger')
        return redirect(url_for('scenario_pipeline.step3', case_id=case_id))


@bp.route('/case/<int:case_id>/entities/clear_and_rerun/<extraction_pass>', methods=['POST'])
@auth_required_for_write
def clear_and_rerun_pass(case_id, extraction_pass):
    """Clear entities for a pass and redirect to extraction."""
    try:
        data = request.get_json() or {}
        section_type = data.get('section_type')

        logger.info(f"clear_and_rerun_pass called: case_id={case_id}, extraction_pass={extraction_pass}, section_type={section_type}")

        # Clear the extraction pass
        result = CaseEntityStorageService.clear_extraction_pass(
            case_id=case_id,
            extraction_pass=extraction_pass,
            section_type=section_type
        )

        if not result['success']:
            logger.error(f"clear_extraction_pass failed: {result}")
            return jsonify(result), 400

        # Determine redirect URL based on pass
        if extraction_pass == 'pass1':
            redirect_url = url_for('scenario_pipeline.step1', case_id=case_id)
        elif extraction_pass == 'pass2':
            redirect_url = url_for('scenario_pipeline.step2', case_id=case_id)
        elif extraction_pass == 'pass3':
            redirect_url = url_for('scenario_pipeline.step3', case_id=case_id)
        elif extraction_pass == 'pass4':
            redirect_url = url_for('step4.step4_synthesis', case_id=case_id)
        else:
            redirect_url = url_for('scenario_pipeline.overview', case_id=case_id)

        return jsonify({
            'success': True,
            'message': result['message'],
            'redirect_url': redirect_url,
            'cleared_stats': result['cleared_stats']
        })

    except Exception as e:
        logger.error(f"Error in clear_and_rerun for case {case_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@bp.route('/case/<int:case_id>/entities/check_extraction/<extraction_pass>')
@auth_optional
def check_extraction_status(case_id, extraction_pass):
    """Check if an extraction pass has been run before."""
    try:
        section_type = request.args.get('section_type')

        has_been_run = CaseEntityStorageService.has_extraction_been_run(
            case_id=case_id,
            extraction_pass=extraction_pass,
            section_type=section_type
        )

        return jsonify({
            'success': True,
            'has_been_run': has_been_run,
            'case_id': case_id,
            'extraction_pass': extraction_pass,
            'section_type': section_type
        })

    except Exception as e:
        logger.error(f"Error checking extraction status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500