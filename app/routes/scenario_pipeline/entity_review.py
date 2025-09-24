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

        # Get RDF entities (new classes and individuals)
        rdf_classes = TemporaryRDFStorage.get_case_entities(case_id, storage_type='class')
        rdf_individuals = TemporaryRDFStorage.get_case_entities(case_id, storage_type='individual')

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

        # Add RDF data
        rdf_data = {
            'classes': [c.to_dict() for c in rdf_classes],
            'individuals': [i.to_dict() for i in rdf_individuals],
            'class_count': len(rdf_classes),
            'individual_count': len(rdf_individuals),
            'total_rdf_entities': len(rdf_classes) + len(rdf_individuals)
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
    """Commit selected entities to OntServe permanent storage."""
    try:
        data = request.get_json() if request.is_json else request.form
        session_ids = data.get('session_ids', [])
        commit_all_reviewed = data.get('commit_all_reviewed', False)

        # Convert string session_ids to list if needed
        if isinstance(session_ids, str):
            session_ids = [session_ids]

        # Commit entities
        result = CaseEntityStorageService.commit_selected_entities_to_ontserve(
            case_id=case_id,
            session_ids=session_ids if session_ids else None,
            commit_all_reviewed=commit_all_reviewed
        )

        if result['success']:
            message = f"Successfully committed {result['committed_count']} entities to OntServe"

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

        # 2. Clear RDF storage (new format with classes and individuals)
        from app.models import TemporaryRDFStorage
        cleared_stats['rdf_triples'] = db.session.query(TemporaryRDFStorage).filter_by(case_id=case_id).count()
        db.session.query(TemporaryRDFStorage).filter_by(case_id=case_id).delete()

        # 3. Clear saved extraction prompts and responses
        from app.models.extraction_prompt import ExtractionPrompt
        cleared_stats['extraction_prompts'] = db.session.query(ExtractionPrompt).filter_by(case_id=case_id).count()
        db.session.query(ExtractionPrompt).filter_by(case_id=case_id).delete()

        # Commit all changes
        db.session.commit()

        total_cleared = sum(cleared_stats.values())
        logger.info(f"Cleared all data for case {case_id}: {cleared_stats}")

        return jsonify({
            'success': True,
            'cleared_count': total_cleared,
            'details': cleared_stats,
            'case_id': case_id,
            'message': f"Cleared {cleared_stats['legacy_concepts']} legacy entities, {cleared_stats['rdf_triples']} RDF storage records, and {cleared_stats['extraction_prompts']} saved prompts"
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