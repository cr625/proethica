"""
Phase 4 to Precedent Features Connector

Updates case_precedent_features with Phase 4 analysis results:
- Principle tensions from narrative conflicts
- Obligation conflicts from decision moments
- Transformation type (if not already set by transformation classifier)

This connects Step 4 synthesis to precedent discovery, enabling:
- Matching cases by conflict patterns
- Finding cases with similar obligation tensions
- Clustering by transformation type

References:
    Marchais-Roubelat & Roubelat (2015) - Transformation Classification
    Wiratunga et al. (2024) - CBR-RAG Case-Based Reasoning
"""

import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from models import ModelConfig
from app.models import db
from app.models.case_precedent_features import CasePrecedentFeatures

logger = logging.getLogger(__name__)


def update_precedent_features_from_phase4(
    case_id: int,
    narrative_result: Optional[Any] = None,
    transformation_type: Optional[str] = None,
    narrative_elements: Optional[Any] = None,
    insights: Optional[Any] = None
) -> bool:
    """
    Update case_precedent_features with Phase 4 analysis results.

    Called after Phase 4 completes to feed insights into precedent matching.
    Can be called with full Phase4NarrativeResult or individual components.

    Args:
        case_id: Case ID to update
        narrative_result: Phase4NarrativeResult (if available)
        transformation_type: Transformation classification type
        narrative_elements: NarrativeElements (if narrative_result not provided)
        insights: CaseInsights (if narrative_result not provided)

    Returns:
        True if update successful
    """
    try:
        # Get or create features record
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if not features:
            features = CasePrecedentFeatures(case_id=case_id)
            db.session.add(features)
            logger.info(f"Created new CasePrecedentFeatures record for case {case_id}")

        # Extract components from narrative_result if provided
        if narrative_result is not None:
            narrative_elements = narrative_result.narrative_elements
            insights = getattr(narrative_result, 'insights', None)

        # Update transformation type (if provided and not already set)
        if transformation_type and not features.transformation_type:
            features.transformation_type = transformation_type
            logger.debug(f"Set transformation_type: {transformation_type}")

        # Extract principle tensions from narrative conflicts
        if narrative_elements is not None and hasattr(narrative_elements, 'conflicts'):
            principle_tensions = _extract_principle_tensions(narrative_elements.conflicts)
            if principle_tensions:
                features.principle_tensions = principle_tensions
                logger.debug(f"Set {len(principle_tensions)} principle tensions")

        # Extract obligation conflicts from decision moments
        if narrative_elements is not None and hasattr(narrative_elements, 'decision_moments'):
            obligation_conflicts = _extract_obligation_conflicts(narrative_elements.decision_moments)
            if obligation_conflicts:
                features.obligation_conflicts = obligation_conflicts
                logger.debug(f"Set {len(obligation_conflicts)} obligation conflicts")

        # Update extraction metadata
        features.extracted_at = datetime.utcnow()
        features.extraction_method = 'phase4_narrative'
        features.llm_model_used = ModelConfig.get_claude_model("default")

        # Build extraction metadata
        metadata = features.extraction_metadata or {}
        metadata['phase4_connected_at'] = datetime.utcnow().isoformat()
        if narrative_elements:
            metadata['narrative_elements'] = {
                'characters': len(getattr(narrative_elements, 'characters', []) or []),
                'events': len(getattr(narrative_elements, 'events', []) or []),
                'conflicts': len(getattr(narrative_elements, 'conflicts', []) or []),
                'decision_moments': len(getattr(narrative_elements, 'decision_moments', []) or [])
            }
        features.extraction_metadata = metadata

        db.session.commit()
        logger.info(f"Updated precedent features for case {case_id} from Phase 4")
        return True

    except Exception as e:
        logger.error(f"Failed to update precedent features for case {case_id}: {e}")
        db.session.rollback()
        return False


def _extract_principle_tensions(conflicts: List) -> List[Dict]:
    """
    Extract principle tensions from NarrativeConflict objects.

    Maps conflict data to the format expected by precedent discovery.

    Args:
        conflicts: List of NarrativeConflict objects

    Returns:
        List of tension dicts for storage in JSONB
    """
    tensions = []

    for conflict in conflicts:
        try:
            # Handle both dataclass and dict representations
            if hasattr(conflict, 'conflict_type'):
                tension = {
                    'conflict_id': conflict.conflict_id,
                    'entity1': conflict.entity1_label,
                    'entity1_type': conflict.entity1_type,
                    'entity1_uri': conflict.entity1_uri,
                    'entity2': conflict.entity2_label,
                    'entity2_type': conflict.entity2_type,
                    'entity2_uri': conflict.entity2_uri,
                    'conflict_type': conflict.conflict_type,
                    'resolution_type': conflict.resolution_type,
                    'description': conflict.description[:200] if conflict.description else ''
                }
            elif isinstance(conflict, dict):
                tension = {
                    'conflict_id': conflict.get('conflict_id', ''),
                    'entity1': conflict.get('entity1_label', conflict.get('entity1', '')),
                    'entity1_type': conflict.get('entity1_type', ''),
                    'entity1_uri': conflict.get('entity1_uri', ''),
                    'entity2': conflict.get('entity2_label', conflict.get('entity2', '')),
                    'entity2_type': conflict.get('entity2_type', ''),
                    'entity2_uri': conflict.get('entity2_uri', ''),
                    'conflict_type': conflict.get('conflict_type', ''),
                    'resolution_type': conflict.get('resolution_type'),
                    'description': conflict.get('description', '')[:200]
                }
            else:
                continue

            tensions.append(tension)

        except Exception as e:
            logger.warning(f"Error extracting tension from conflict: {e}")
            continue

    return tensions


def _extract_obligation_conflicts(decision_moments: List) -> List[Dict]:
    """
    Extract obligation conflicts from DecisionMoment objects.

    Maps decision moment data to obligation conflict format.

    Args:
        decision_moments: List of DecisionMoment objects

    Returns:
        List of conflict dicts for storage in JSONB
    """
    conflicts = []

    for dm in decision_moments:
        try:
            # Handle both dataclass and dict representations
            if hasattr(dm, 'competing_obligations'):
                competing = dm.competing_obligations or []
                if competing:
                    conflict = {
                        'decision_id': dm.decision_id,
                        'decision_uri': dm.uri,
                        'question': dm.question[:200] if dm.question else '',
                        'decision_maker': dm.decision_maker_label,
                        'decision_maker_uri': dm.decision_maker_uri,
                        'competing_obligations': competing,
                        'board_choice': dm.board_choice,
                        'options_count': len(dm.options) if dm.options else 0
                    }
                    conflicts.append(conflict)

            elif isinstance(dm, dict):
                competing = dm.get('competing_obligations', [])
                if competing:
                    conflict = {
                        'decision_id': dm.get('decision_id', ''),
                        'decision_uri': dm.get('uri', ''),
                        'question': dm.get('question', '')[:200],
                        'decision_maker': dm.get('decision_maker_label', ''),
                        'decision_maker_uri': dm.get('decision_maker_uri', ''),
                        'competing_obligations': competing,
                        'board_choice': dm.get('board_choice'),
                        'options_count': len(dm.get('options', []))
                    }
                    conflicts.append(conflict)

        except Exception as e:
            logger.warning(f"Error extracting obligation conflict from decision moment: {e}")
            continue

    return conflicts


def get_phase4_features_summary(case_id: int) -> Optional[Dict]:
    """
    Get a summary of Phase 4 features stored for a case.

    Useful for UI display and debugging.

    Args:
        case_id: Case ID

    Returns:
        Dict with feature summary or None if not found
    """
    try:
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if not features:
            return None

        return {
            'case_id': case_id,
            'transformation_type': features.transformation_type,
            'principle_tensions_count': len(features.principle_tensions or []),
            'obligation_conflicts_count': len(features.obligation_conflicts or []),
            'principle_tensions': features.principle_tensions or [],
            'obligation_conflicts': features.obligation_conflicts or [],
            'extracted_at': features.extracted_at.isoformat() if features.extracted_at else None,
            'extraction_method': features.extraction_method,
            'extraction_metadata': features.extraction_metadata
        }

    except Exception as e:
        logger.error(f"Error getting Phase 4 features summary for case {case_id}: {e}")
        return None
