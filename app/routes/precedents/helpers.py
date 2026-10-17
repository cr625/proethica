"""Precedent matching constants + scoring/feature helpers."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text
from app.services.precedent.similarity_service import PrecedentSimilarityService
from app.utils.provision_codes import normalize_provision_codes

logger = logging.getLogger(__name__)


# The weighted components of the component-aware score, in weight order. The
# Similar Cases page renders every one of them with its weight: until the
# 2026-10 case 24-1 review it showed three of the five, and outcome alignment
# plus tension overlap (22.7 of the top match's 62.9 points) were invisible.
RETRIEVAL_COMPONENTS = list(PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS)

MATCHING_METHODS = {
    'component_similarity': {
        'name': 'D-tuple Similarity',
        'method': 'Cosine',
        'description': '9-component weighted embedding similarity (R, P, O, S, Rs, A, E, Ca, Cs)',
    },
    'provision_overlap': {
        'name': 'Provision Overlap',
        'method': 'Jaccard',
        'description': 'NSPE Code section overlap',
    },
    'outcome_alignment': {
        'name': 'Outcome Alignment',
        'method': 'Match',
        'description': 'Board outcome agreement: 1.0 same polarity, 0.5 mixed or unclear, 0.0 opposite',
    },
    'tag_overlap': {
        'name': 'Subject Tags',
        'method': 'Jaccard',
        'description': 'NSPE subject reference overlap',
    },
    'principle_overlap': {
        'name': 'Tension Overlap',
        'method': 'Cosine',
        'description': 'Ethical-tension signature similarity',
    },
}

# Entity type colours/labels for the D-tuple per-component display
# (abbreviation-keyed). Single source: app/concept_meta.py; re-exported here so
# existing `from ...helpers import COMPONENT_COLORS` importers keep working.
from app.concept_meta import COMPONENT_COLORS, COMPONENT_LABELS




def _get_case_year(case):
    """Extract year from case metadata."""
    if case.doc_metadata:
        if case.doc_metadata.get('year'):
            return case.doc_metadata.get('year')
        if case.doc_metadata.get('date_parts'):
            parts = case.doc_metadata.get('date_parts')
            if parts.get('year'):
                return parts.get('year')
    return ''


def _find_precedents_for_case(case_id, limit=10, min_score=0.1):
    """
    Find similar cases with the component-aware similarity of the Similar
    Cases page (CBR-RAG weighted combination, Wiratunga et al., 2024):

    Score = 0.40 * component_similarity + 0.25 * provision_overlap +
            0.15 * outcome_alignment + 0.10 * tag_overlap + 0.10 * principle_overlap

    (PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS). Each result carries
    the five component scores with their weights, the shared provisions and
    subject tags from the scorer itself, and the latest Step 4 transformation
    classification of both cases.

    Results include is_cited_precedent/is_cited_by flags to distinguish
    explicitly cited precedent relationships from similarity-only matches.
    """
    from app.services.precedent import PrecedentDiscoveryService

    discovery_service = PrecedentDiscoveryService(llm_client=None)

    try:
        matches = discovery_service.find_precedents(
            source_case_id=case_id,
            limit=limit,
            min_score=min_score,
            include_llm_analysis=False,
            use_component_embedding=True
        )

        # Source case features: citations, outcome, and the transformation
        # type (the latest Step 4 classification wins over the stored column).
        source_features = _get_case_features(case_id)
        source_cited = set(source_features.get('cited_case_numbers', []) or []) if source_features else set()
        source_cited_ids = set(source_features.get('cited_case_ids', []) or []) if source_features else set()
        source_outcome = source_features.get('outcome_type') if source_features else None
        source_transformation = _resolve_transformation_type(
            case_id, source_features.get('transformation_type') if source_features else None
        )

        results = []
        for match in matches:
            # Get additional features from database
            cited_case_numbers = []
            features = _get_case_features(match.target_case_id)
            if features:
                cited_case_numbers = features.get('cited_case_numbers', []) or []

            # Calculate overlapping citations between source and target
            target_cited = set(cited_case_numbers) if cited_case_numbers else set()
            overlapping_citations = list(source_cited & target_cited)

            # Transformation match on the latest classification of both cases
            target_transformation = _resolve_transformation_type(
                match.target_case_id, match.target_transformation
            )
            transformation_match = bool(
                source_transformation and target_transformation and
                source_transformation == target_transformation
            )

            # Check if target is an explicitly cited precedent (or cites the source)
            target_cited_ids = set(features.get('cited_case_ids', []) or []) if features else set()
            is_cited_precedent = match.target_case_id in source_cited_ids
            is_cited_by = case_id in target_cited_ids

            results.append({
                'case_id': match.target_case_id,
                'title': match.target_case_title,
                'url': match.target_case_url,
                'overall_score': round(match.overall_score, 3),
                'component_scores': {
                    k: round(v, 3) for k, v in match.component_scores.items()
                },
                'weights_used': {
                    k: round(v, 3) for k, v in (match.weights_used or {}).items()
                },
                'per_component_scores': {
                    k: round(v, 3) for k, v in (match.per_component_scores or {}).items()
                },
                'matching_provisions': match.matching_provisions,
                'outcome_match': match.outcome_match,
                'source_outcome': source_outcome,
                'target_outcome': match.target_outcome,
                'transformation_match': transformation_match,
                'source_transformation': source_transformation,
                'target_transformation': target_transformation,
                # The scorer's own intersection, so the displayed topics are the
                # set tag_overlap was computed on.
                'overlapping_tags': list(match.matching_tags or []),
                'overlapping_citations': overlapping_citations,
                'is_cited_precedent': is_cited_precedent,
                'is_cited_by': is_cited_by,
            })

        return {
            'success': True,
            'source_case_id': case_id,
            'count': len(results),
            'precedents': results
        }

    except Exception as e:
        logger.error(f"Error finding precedents for case {case_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'precedents': []
        }


def _resolve_transformation_type(case_id, column_value):
    """Transformation type for display: the latest Step 4 classification
    (extraction_prompts, load_latest_transformation) when one exists, else the
    case_precedent_features column. The column is a denormalized summary and
    was stale for case 24-1 (column 'stalemate', classification 'phase_lag')."""
    try:
        from app.services.case_analysis.transformation_classifier import load_latest_transformation
        latest = load_latest_transformation(case_id)
    except Exception as e:
        logger.warning(f"Could not load the latest transformation for case {case_id}: {e}")
        return column_value
    latest_type = latest.get('type') if latest else None
    if not latest_type:
        return column_value
    if column_value and column_value != latest_type:
        logger.info(f"Stale transformation_type column for case {case_id}: "
                    f"{column_value} (latest classification {latest_type})")
    return latest_type


def _get_matching_provisions(case_a_id, case_b_id):
    """Get matching provisions between two cases (compared in canonical form)."""
    query = text("""
        SELECT
            a.provisions_cited AS prov_a,
            b.provisions_cited AS prov_b
        FROM case_precedent_features a, case_precedent_features b
        WHERE a.case_id = :case_a AND b.case_id = :case_b
    """)
    result = db.session.execute(query, {'case_a': case_a_id, 'case_b': case_b_id}).fetchone()
    if result and result[0] and result[1]:
        set_a = set(normalize_provision_codes(result[0]))
        set_b = set(normalize_provision_codes(result[1]))
        return sorted(set_a & set_b)
    return []


def _count_outcomes(nodes):
    """Count outcome distribution in node list."""
    counts = {}
    for node in nodes:
        outcome = node.get('outcome', 'unknown')
        counts[outcome] = counts.get(outcome, 0) + 1
    return counts


def _get_case_features(case_id):
    """Get case precedent features from database."""
    try:
        query = text("""
            SELECT principle_tensions, obligation_conflicts,
                   transformation_type, cited_case_numbers, cited_case_ids,
                   outcome_type
            FROM case_precedent_features
            WHERE case_id = :case_id
        """)
        result = db.session.execute(query, {'case_id': case_id}).fetchone()
        if result:
            return {
                'principle_tensions': result[0],
                'obligation_conflicts': result[1],
                'transformation_type': result[2],
                'cited_case_numbers': result[3],
                'cited_case_ids': result[4],
                'outcome_type': result[5]
            }
    except Exception as e:
        logger.warning(f"Error getting case features for {case_id}: {e}")
    return None


