"""set-match, mark-new, confirm-match, entity-overlap."""
import logging
from datetime import datetime

from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document, db, TemporaryRDFStorage
from app.services.entity.case_entity_storage_service import CaseEntityStorageService
from app.services.extraction.field_classification import group_properties
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write
)

logger = logging.getLogger(__name__)
from app.routes.scenario_pipeline.entity_review.ontserve_ops.helpers import (
    _resolve_class_core_category,
)


def register_ontserve_matching_ops(bp):
    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/set_match', methods=['POST'])
    @auth_required_for_write
    def set_entity_match(case_id, entity_id):
        """
        Set or update the match for an entity.

        Used for manual linking from the match details modal.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.entity_match_confirmation import EntityMatchConfirmation
            from flask_login import current_user

            data = request.get_json() or {}
            matched_uri = data.get('matched_uri')
            matched_label = data.get('matched_label')
            method = data.get('method', 'manual')
            confidence = data.get('confidence', 1.0)
            reasoning = data.get('reasoning', 'Manually linked by user')

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            # Type-safe override gate. The nine core components are an
            # owl:AllDisjointClasses set, so an override whose target class resolves
            # to a different core category than the entity's extraction component
            # would force a disjointness clash at commit/conformance time. Reject it
            # here (fail-fast) rather than letting it reach the conformance gate.
            # When either category cannot be resolved (entity is not one of the nine
            # components, or the target is unknown to the curated tiers) the check is
            # skipped -- absence of proof is not a violation.
            if matched_uri:
                from app.services.extraction.unified_dual_extractor import (
                    CONCEPT_TYPE_TO_CORE_CATEGORY,
                )

                entity_category = CONCEPT_TYPE_TO_CORE_CATEGORY.get(entity.extraction_type)
                target_category = _resolve_class_core_category(matched_uri)
                if entity_category and target_category and entity_category != target_category:
                    return jsonify({
                        'success': False,
                        'error': (
                            f"Type mismatch: this entity is a {entity_category}; "
                            f"'{matched_label or matched_uri}' is a {target_category} class. "
                            f"An override must stay within the same core category."
                        )
                    }), 400

            # Capture the pre-update match state for the audit trail before mutating.
            confirmation = EntityMatchConfirmation(
                case_id=case_id,
                entity_id=entity_id,
                entity_label=entity.entity_label,
                entity_type=entity.entity_type,
                original_match_uri=entity.matched_ontology_uri,
                original_match_label=entity.matched_ontology_label,
                original_confidence=entity.match_confidence,
                original_method=entity.match_method,
                action='changed',
                new_match_uri=matched_uri,
                new_match_label=matched_label,
                user_id=current_user.id if current_user and hasattr(current_user, 'id') else None
            )
            db.session.add(confirmation)

            # Update match fields
            entity.matched_ontology_uri = matched_uri
            entity.matched_ontology_label = matched_label
            entity.match_confidence = confidence
            entity.match_method = method
            entity.match_reasoning = reasoning

            db.session.commit()

            logger.info(f"Updated match for entity {entity_id}: {matched_label} ({matched_uri})")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'matched_uri': matched_uri,
                'matched_label': matched_label,
                'confidence': confidence,
                'method': method
            })

        except Exception as e:
            logger.error(f"Error setting entity match: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/mark_new', methods=['POST'])
    @auth_required_for_write
    def mark_entity_as_new(case_id, entity_id):
        """
        Mark an entity as a new class (clear any existing match).

        Used when the user wants to create a new class instead of linking to existing.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.entity_match_confirmation import EntityMatchConfirmation
            from flask_login import current_user

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            # Log the mark-new action with the match state being discarded, so the
            # audit trail captures every rejected auto-match (a canonicalization signal).
            confirmation = EntityMatchConfirmation(
                case_id=case_id,
                entity_id=entity_id,
                entity_label=entity.entity_label,
                entity_type=entity.entity_type,
                original_match_uri=entity.matched_ontology_uri,
                original_match_label=entity.matched_ontology_label,
                original_confidence=entity.match_confidence,
                original_method=entity.match_method,
                action='marked_new',
                new_match_uri=None,
                new_match_label=None,
                user_id=current_user.id if current_user and hasattr(current_user, 'id') else None
            )
            db.session.add(confirmation)

            # Clear match fields
            entity.matched_ontology_uri = None
            entity.matched_ontology_label = None
            entity.match_confidence = None
            entity.match_method = 'manual'
            entity.match_reasoning = 'Marked as new class by user'

            db.session.commit()

            logger.info(f"Marked entity {entity_id} as new class")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'message': 'Entity marked as new class'
            })

        except Exception as e:
            logger.error(f"Error marking entity as new: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/<int:entity_id>/confirm_match', methods=['POST'])
    @auth_required_for_write
    def confirm_entity_match(case_id, entity_id):
        """
        Confirm the current match for an entity.

        Logs the confirmation for future learning and updates confidence to 1.0.
        """
        try:
            from app.models.temporary_rdf_storage import TemporaryRDFStorage
            from app.models.entity_match_confirmation import EntityMatchConfirmation
            from flask_login import current_user

            # Find the entity
            entity = TemporaryRDFStorage.query.filter_by(id=entity_id, case_id=case_id).first()
            if not entity:
                return jsonify({
                    'success': False,
                    'error': 'Entity not found'
                }), 404

            if not entity.matched_ontology_uri:
                return jsonify({
                    'success': False,
                    'error': 'No match to confirm'
                }), 400

            # Log the confirmation
            confirmation = EntityMatchConfirmation(
                case_id=case_id,
                entity_id=entity_id,
                entity_label=entity.entity_label,
                entity_type=entity.entity_type,
                original_match_uri=entity.matched_ontology_uri,
                original_match_label=entity.matched_ontology_label,
                original_confidence=entity.match_confidence,
                original_method=entity.match_method,
                action='confirmed',
                new_match_uri=entity.matched_ontology_uri,
                new_match_label=entity.matched_ontology_label,
                user_id=current_user.id if current_user and hasattr(current_user, 'id') else None
            )
            db.session.add(confirmation)

            # Update entity confidence to 1.0 (user confirmed)
            entity.match_confidence = 1.0
            entity.match_method = 'manual_confirmed'

            db.session.commit()

            logger.info(f"Confirmed match for entity {entity_id}: {entity.matched_ontology_label}")

            return jsonify({
                'success': True,
                'entity_id': entity_id,
                'matched_uri': entity.matched_ontology_uri,
                'matched_label': entity.matched_ontology_label,
                'message': 'Match confirmed'
            })

        except Exception as e:
            logger.error(f"Error confirming entity match: {e}")
            db.session.rollback()
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @bp.route('/case/<int:case_id>/entities/entity_overlap')
    @auth_optional
    def get_entity_overlap(case_id):
        """
        Get entity class overlap between this case and other cases for Jaccard similarity.

        Returns the entity_classes for this case and overlap statistics with other cases.
        """
        try:
            from sqlalchemy import text

            # Get entity_classes for this case
            query = text("""
                SELECT case_id, entity_classes
                FROM case_precedent_features
                WHERE entity_classes IS NOT NULL
            """)
            results = db.session.execute(query).fetchall()

            if not results:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'entity_classes': {},
                    'overlap_with_cases': [],
                    'message': 'No cases have entity_classes data yet'
                })

            # Find this case's entity classes
            this_case_classes = None
            other_cases = []

            for row in results:
                if row[0] == case_id:
                    this_case_classes = row[1] or {}
                else:
                    other_cases.append({
                        'case_id': row[0],
                        'entity_classes': row[1] or {}
                    })

            if this_case_classes is None:
                return jsonify({
                    'success': True,
                    'case_id': case_id,
                    'entity_classes': {},
                    'overlap_with_cases': [],
                    'message': 'This case has no entity_classes data. Run auto-commit first.'
                })

            # Calculate Jaccard overlap with each other case
            def calculate_jaccard(classes_a, classes_b):
                """Calculate Jaccard similarity across all entity types."""
                all_uris_a = set()
                all_uris_b = set()

                for entity_type, uris in classes_a.items():
                    all_uris_a.update(uris)
                for entity_type, uris in classes_b.items():
                    all_uris_b.update(uris)

                if not all_uris_a and not all_uris_b:
                    return 0.0, []

                intersection = all_uris_a & all_uris_b
                union = all_uris_a | all_uris_b

                if not union:
                    return 0.0, []

                return len(intersection) / len(union), list(intersection)

            overlap_results = []
            for other in other_cases:
                jaccard, shared_uris = calculate_jaccard(this_case_classes, other['entity_classes'])
                if jaccard > 0:  # Only include cases with some overlap
                    overlap_results.append({
                        'case_id': other['case_id'],
                        'jaccard_similarity': round(jaccard, 3),
                        'shared_classes_count': len(shared_uris),
                        'shared_class_uris': shared_uris[:10]  # Limit to first 10 for display
                    })

            # Sort by similarity descending
            overlap_results.sort(key=lambda x: x['jaccard_similarity'], reverse=True)

            return jsonify({
                'success': True,
                'case_id': case_id,
                'entity_classes': this_case_classes,
                'total_classes': sum(len(uris) for uris in this_case_classes.values()),
                'overlap_with_cases': overlap_results,
                'cases_with_overlap': len(overlap_results)
            })

        except Exception as e:
            logger.error(f"Error getting entity overlap for case {case_id}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
