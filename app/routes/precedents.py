"""
Routes for precedent discovery and retrieval.

Academic References:
- CBR-RAG: Markel, D., Gerstl, A., & Mirsky, Y. (2024). CBR-RAG: Case-based reasoning
  for retrieval augmented generation. arXiv. https://arxiv.org/html/2404.04302v1
- NS-LCR: Zhang, Y., et al. (2024). NS-LCR: Neural-symbolic legal case retrieval.
  arXiv. https://arxiv.org/html/2403.01457v1
"""

import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)

precedents_bp = Blueprint('precedents', __name__, url_prefix='/cases/precedents')


# Method descriptions with APA citations
# CBR-RAG (Markel et al., 2024) for hybrid similarity approach
# NS-LCR (Zhang et al., 2024) for dual-level matching
MATCHING_METHODS = {
    'facts_similarity': {
        'name': 'Facts Similarity',
        'method': 'Cosine',
        'description': 'Semantic similarity of case facts',
        'citation': 'CBR-RAG (Markel et al., 2024)'
    },
    'discussion_similarity': {
        'name': 'Discussion Similarity',
        'method': 'Cosine',
        'description': 'Semantic similarity of ethical analysis',
        'citation': 'CBR-RAG (Markel et al., 2024)'
    },
    'provision_overlap': {
        'name': 'Provision Overlap',
        'method': 'Jaccard',
        'description': 'NSPE Code section overlap',
        'citation': 'NS-LCR (Zhang et al., 2024)'
    },
    'outcome_alignment': {
        'name': 'Outcome Match',
        'method': 'Categorical',
        'description': 'Ethical/unethical outcome alignment',
        'citation': None
    },
    'tag_overlap': {
        'name': 'Subject Tags',
        'method': 'Jaccard',
        'description': 'Topic category overlap',
        'citation': None
    },
    'principle_overlap': {
        'name': 'Principle Tensions',
        'method': 'Jaccard',
        'description': 'Ethical principle conflicts',
        'citation': 'NS-LCR (Zhang et al., 2024)'
    }
}


@precedents_bp.route('/', methods=['GET'])
@auth_optional
def find_precedents():
    """Display the precedent finder interface."""
    # Get all cases for the selector
    cases = Document.query.filter(
        Document.document_type.in_(['case', 'case_study'])
    ).order_by(Document.id).all()

    # Format cases for display
    case_list = []
    for case in cases:
        case_number = ''
        if case.doc_metadata and case.doc_metadata.get('case_number'):
            case_number = case.doc_metadata.get('case_number')

        case_list.append({
            'id': case.id,
            'title': case.title,
            'case_number': case_number,
            'year': _get_case_year(case)
        })

    # Check if a source case was selected
    source_case_id = request.args.get('case_id', type=int)
    precedent_results = None
    source_case = None

    if source_case_id:
        source_case = Document.query.get(source_case_id)
        if source_case:
            precedent_results = _find_precedents_for_case(source_case_id)

    return render_template(
        'precedents.html',
        cases=case_list,
        source_case=source_case,
        source_case_id=source_case_id,
        precedent_results=precedent_results,
        matching_methods=MATCHING_METHODS
    )


@precedents_bp.route('/api/find', methods=['GET'])
@auth_optional
def api_find_precedents():
    """API endpoint for finding precedents."""
    case_id = request.args.get('case_id', type=int)
    limit = request.args.get('limit', 10, type=int)
    min_score = request.args.get('min_score', 0.1, type=float)

    if not case_id:
        return jsonify({'error': 'case_id is required'}), 400

    results = _find_precedents_for_case(case_id, limit=limit, min_score=min_score)
    return jsonify(results)


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
    Find precedent cases using multi-factor similarity.

    Uses weighted combination approach from CBR-RAG (Markel et al., 2024):
    Score = w1*facts_sim + w2*discussion_sim + w3*provision_overlap +
            w4*outcome_alignment + w5*tag_overlap + w6*principle_overlap
    """
    from app.services.precedent import PrecedentDiscoveryService

    discovery_service = PrecedentDiscoveryService(llm_client=None)

    try:
        matches = discovery_service.find_precedents(
            source_case_id=case_id,
            limit=limit,
            min_score=min_score,
            include_llm_analysis=False
        )

        results = []
        for match in matches:
            # Determine primary matching method based on highest component score
            primary_method = _get_primary_method(match.component_scores)

            results.append({
                'case_id': match.target_case_id,
                'title': match.target_case_title,
                'url': match.target_case_url,
                'overall_score': round(match.overall_score, 3),
                'component_scores': {
                    k: round(v, 3) for k, v in match.component_scores.items()
                },
                'matching_provisions': match.matching_provisions,
                'outcome_match': match.outcome_match,
                'target_outcome': match.target_outcome,
                'target_transformation': match.target_transformation,
                'primary_method': primary_method,
                'method_info': MATCHING_METHODS.get(primary_method, {})
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
