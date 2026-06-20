"""Precedent matching constants + scoring/feature helpers."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


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
    'tag_overlap': {
        'name': 'Subject Tags',
        'method': 'Jaccard',
        'description': 'Topic category overlap',
    }
}

# Entity type colors for D-tuple per-component display
COMPONENT_COLORS = {
    'R': '#0d6efd', 'S': '#6f42c1', 'Rs': '#20c997',
    'P': '#fd7e14', 'O': '#dc3545', 'Cs': '#6c757d',
    'Ca': '#0dcaf0', 'A': '#198754', 'E': '#ffc107',
}

COMPONENT_LABELS = {
    'R': 'Roles', 'P': 'Principles', 'O': 'Obligations',
    'S': 'States', 'Rs': 'Resources', 'A': 'Actions',
    'E': 'Events', 'Ca': 'Capabilities', 'Cs': 'Constraints',
}




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
    Find similar cases using multi-factor similarity.

    Uses weighted combination approach from CBR-RAG (Wiratunga et al., 2024):
    Score = w1*facts_sim + w2*discussion_sim + w3*provision_overlap +
            w4*outcome_alignment + w5*tag_overlap + w6*principle_overlap

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

        # Get source case's features for overlap calculation
        source_features = _get_case_features(case_id)
        source_cited = set(source_features.get('cited_case_numbers', []) or []) if source_features else set()
        source_cited_ids = set(source_features.get('cited_case_ids', []) or []) if source_features else set()
        source_transformation = source_features.get('transformation_type') if source_features else None

        # Get source case's subject tags and outcome
        source_case = Document.query.get(case_id)
        source_tags = set()
        source_outcome = None
        if source_case and source_case.doc_metadata:
            source_tags = set(source_case.doc_metadata.get('subject_tags', []) or [])

        # Outcome comes from case_precedent_features
        source_features_for_outcome = _get_case_features(case_id)
        if source_features_for_outcome:
            source_outcome = source_features_for_outcome.get('outcome_type')

        results = []
        for match in matches:
            # Determine primary matching method based on highest component score
            primary_method = _get_primary_method(match.component_scores)

            # Get additional features from database
            cited_case_numbers = []
            features = _get_case_features(match.target_case_id)
            if features:
                cited_case_numbers = features.get('cited_case_numbers', []) or []

            # Calculate overlapping citations between source and target
            target_cited = set(cited_case_numbers) if cited_case_numbers else set()
            overlapping_citations = list(source_cited & target_cited)

            # Calculate overlapping subject tags
            target_case = Document.query.get(match.target_case_id)
            target_tags = set()
            if target_case and target_case.doc_metadata:
                target_tags = set(target_case.doc_metadata.get('subject_tags', []) or [])
            overlapping_tags = list(source_tags & target_tags)

            # Calculate transformation match
            transformation_match = (
                source_transformation and match.target_transformation and
                source_transformation == match.target_transformation
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
                'per_component_scores': {
                    k: round(v, 3) for k, v in (match.per_component_scores or {}).items()
                },
                'matching_provisions': match.matching_provisions,
                'outcome_match': match.outcome_match,
                'source_outcome': source_outcome,
                'target_outcome': match.target_outcome,
                'transformation_match': transformation_match,
                'source_transformation': source_transformation,
                'target_transformation': match.target_transformation,
                'overlapping_tags': overlapping_tags,
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


def _get_primary_method(component_scores):
    """Determine the primary matching method based on highest score."""
    if not component_scores:
        return 'provision_overlap'  # Default

    # Find highest non-zero score
    max_score = 0
    primary = 'provision_overlap'

    for method, score in component_scores.items():
        if score > max_score:
            max_score = score
            primary = method

    return primary




def _get_matching_provisions(case_a_id, case_b_id):
    """Get matching provisions between two cases."""
    query = text("""
        SELECT
            a.provisions_cited AS prov_a,
            b.provisions_cited AS prov_b
        FROM case_precedent_features a, case_precedent_features b
        WHERE a.case_id = :case_a AND b.case_id = :case_b
    """)
    result = db.session.execute(query, {'case_a': case_a_id, 'case_b': case_b_id}).fetchone()
    if result and result[0] and result[1]:
        set_a = set(result[0])
        set_b = set(result[1])
        return sorted(list(set_a & set_b))
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


