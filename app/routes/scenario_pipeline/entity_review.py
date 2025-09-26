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


@bp.route('/case/<int:case_id>/entities/review')
def review_case_entities(case_id):
    """Display all extracted entities for a case organized by section."""
    try:
        # Get case information
        case_doc = Document.query.get(case_id)
        if not case_doc:
            flash(f'Case {case_id} not found', 'error')
            return redirect(url_for('index.index'))

        # Get RDF entities grouped by extraction_type
        all_rdf_entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

        # Group entities by extraction_type and storage_type
        rdf_by_type = {
            'roles': {'classes': [], 'individuals': []},
            'states': {'classes': [], 'individuals': []},
            'resources': {'classes': [], 'individuals': []}
        }

        for entity in all_rdf_entities:
            extraction_type = entity.extraction_type or 'unknown'
            storage_type = entity.storage_type

            if extraction_type in rdf_by_type:
                if storage_type == 'class':
                    rdf_by_type[extraction_type]['classes'].append(entity.to_dict())
                elif storage_type == 'individual':
                    rdf_by_type[extraction_type]['individuals'].append(entity.to_dict())

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

        # Prepare RDF data organized by concept type
        rdf_data = {
            'by_type': rdf_by_type,
            'total_rdf_entities': len(all_rdf_entities)
        }

        return render_template(
            'scenarios/entity_review.html',
            case=case_doc,
            section_data=section_data,
            total_entities=total_entities,
            sections_info=sections_info,
            rdf_data=rdf_data
        )

    except Exception as e:
        logger.error(f"Error displaying entity review for case {case_id}: {e}")
        flash(f'Error loading entity review: {str(e)}', 'error')
        return redirect(url_for('index.index'))


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


@bp.route('/case/<int:case_id>/entities/clear_all', methods=['POST'])
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


@bp.route('/case/<int:case_id>/entities/refresh_committed', methods=['POST'])
def refresh_committed_from_ontserve(case_id):
    """Refresh committed entities with live data from OntServe.

    This addresses synchronization issues by pulling the latest versions
    of committed entities from OntServe and updating ProEthica's records.
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
                    entity.parent_uri = ontserve_data.get('parent_uri')
                    entity.last_synced_at = datetime.utcnow()

                    # Store the fact that this was synced
                    if not entity.metadata:
                        entity.metadata = {}
                    entity.metadata['last_sync'] = {
                        'timestamp': datetime.utcnow().isoformat(),
                        'source': 'ontserve',
                        'changes_detected': len(detail.get('changes', []))
                    }

                    update_count += 1

        # Commit all updates
        if update_count > 0:
            db.session.commit()
            logger.info(f"Updated {update_count} entities with OntServe data for case {case_id}")

        # Prepare response message
        message_parts = []
        if refresh_result['unchanged'] > 0:
            message_parts.append(f"{refresh_result['unchanged']} unchanged")
        if refresh_result['modified'] > 0:
            message_parts.append(f"{refresh_result['modified']} modified")
        if refresh_result['not_found'] > 0:
            message_parts.append(f"{refresh_result['not_found']} not found in OntServe")

        message = f"Refreshed {refresh_result['refreshed']} entities: {', '.join(message_parts)}"

        return jsonify({
            'success': True,
            'message': message,
            'result': refresh_result
        })

    except Exception as e:
        logger.error(f"Error refreshing committed entities from OntServe: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        })