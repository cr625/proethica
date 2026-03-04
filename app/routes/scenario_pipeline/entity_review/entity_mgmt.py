"""
Entity Management Routes

CRUD operations for entity selection, deletion, commit, clearing, and summary.
"""

import logging

from flask import request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.case_entity_storage_service import CaseEntityStorageService
from app.models.temporary_concept import TemporaryConcept
from app.utils.environment_auth import auth_required_for_write

logger = logging.getLogger(__name__)


def register_entity_mgmt_routes(bp):
    """Register entity management routes on the given blueprint."""

    @bp.route('/case/<int:case_id>/rdf_entities/update_selection', methods=['POST'])
    @auth_required_for_write
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

    @bp.route('/case/<int:case_id>/rdf_entities/<int:entity_id>/delete', methods=['DELETE', 'POST'])
    @auth_required_for_write
    def delete_rdf_entity(case_id, entity_id):
        """Delete a single RDF entity from temporary storage.

        Only unpublished (draft) entities can be deleted.
        Published entities are protected.
        """
        try:
            entity = TemporaryRDFStorage.query.get(entity_id)

            if not entity:
                return jsonify({'success': False, 'error': 'Entity not found'}), 404

            if entity.case_id != case_id:
                return jsonify({'success': False, 'error': 'Entity does not belong to this case'}), 403

            if entity.is_published:
                return jsonify({'success': False, 'error': 'Cannot delete published entities'}), 400

            entity_label = entity.entity_label
            entity_type = entity.entity_type

            db.session.delete(entity)
            db.session.commit()

            logger.info(f"Deleted entity '{entity_label}' ({entity_type}) from case {case_id}")

            return jsonify({
                'success': True,
                'message': f"Deleted '{entity_label}'"
            })

        except Exception as e:
            logger.error(f"Error deleting RDF entity: {e}")
            db.session.rollback()
            return jsonify({'success': False, 'error': str(e)}), 500

    @bp.route('/case/<int:case_id>/entities/update_selection', methods=['POST'])
    @auth_required_for_write
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
            force = data.get('force', False)

            # Check extraction step completion before allowing commit
            if not force:
                from app.services.pipeline_status_service import PipelineStatusService
                step_status = PipelineStatusService.get_step_status(case_id)
                incomplete_steps = []
                for step_key in ('step1', 'step2', 'step3'):
                    if not step_status.get(step_key, {}).get('complete', False):
                        incomplete_steps.append(step_key)
                if incomplete_steps:
                    return jsonify({
                        'success': False,
                        'error': f"Extraction steps not complete: {', '.join(incomplete_steps)}. "
                                 f"Complete all extraction steps before committing to OntServe. "
                                 f"Pass force=true to override.",
                        'incomplete_steps': incomplete_steps,
                    })

            # Handle both old format (session_ids) and new format (entity_ids)
            entity_ids = data.get('entity_ids', [])

            # If no entity_ids provided, get all selected RDF entities
            if not entity_ids:
                selected_entities = TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    is_selected=True,
                    is_published=False
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
                    is_published=False
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
                    is_published=False
                )
                if section_session_ids is not None:
                    delete_query = delete_query.filter(TemporaryRDFStorage.extraction_session_id.in_(section_session_ids))
                delete_query.delete()

            # Delete extraction prompts for specified types - ONLY for the specified section
            # to preserve prompts from other sections (e.g., don't delete facts prompts when clearing discussion)
            for extraction_type in extraction_types:
                prompt_query = db.session.query(ExtractionPrompt).filter_by(
                    case_id=case_id,
                    concept_type=extraction_type
                )
                # Apply section filter if specified
                if section_type:
                    prompt_query = prompt_query.filter_by(section_type=section_type)

                # Count prompts that will be deleted
                prompt_count = prompt_query.count()
                cleared_stats['extraction_prompts'] += prompt_count

                # Delete prompts for this extraction type (filtered by section if specified)
                delete_query = db.session.query(ExtractionPrompt).filter_by(
                    case_id=case_id,
                    concept_type=extraction_type
                )
                if section_type:
                    delete_query = delete_query.filter_by(section_type=section_type)
                delete_query.delete(synchronize_session='fetch')

            db.session.commit()

            # Count remaining entities
            remaining_count = db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                is_published=False
            ).count()

            committed_count = db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                is_published=True
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
                is_published=True
            ).count()

            # Only delete uncommitted entities
            cleared_stats['rdf_triples'] = db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                is_published=False
            ).count()
            db.session.query(TemporaryRDFStorage).filter_by(
                case_id=case_id,
                is_published=False
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
