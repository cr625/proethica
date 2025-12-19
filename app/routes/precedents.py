"""
Routes for precedent discovery and retrieval.

Academic References:
- CBR-RAG: Wiratunga, N., Abeyratne, R., Jayawardena, L., et al. (2024). CBR-RAG:
  Case-Based Reasoning for Retrieval Augmented Generation in LLMs for Legal Question
  Answering. Proceedings of LREC-COLING 2024. https://aclanthology.org/2024.lrec-main.939/
- NS-LCR: Sun, Z., Zhang, K., Yu, W., Wang, H. & Xu, J. (2024). Logic Rules as
  Explanations for Legal Case Retrieval. Proceedings of LREC-COLING 2024.
  https://aclanthology.org/2024.lrec-main.939/
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
# CBR-RAG (Wiratunga et al., 2024) for hybrid similarity approach
# NS-LCR (Sun et al., 2024) for dual-level matching
MATCHING_METHODS = {
    'facts_similarity': {
        'name': 'Facts Similarity',
        'method': 'Cosine',
        'description': 'Semantic similarity of case facts',
        'citation': 'CBR-RAG (Wiratunga et al., 2024)'
    },
    'discussion_similarity': {
        'name': 'Discussion Similarity',
        'method': 'Cosine',
        'description': 'Semantic similarity of ethical analysis',
        'citation': 'CBR-RAG (Wiratunga et al., 2024)'
    },
    'provision_overlap': {
        'name': 'Provision Overlap',
        'method': 'Jaccard',
        'description': 'NSPE Code section overlap',
        'citation': 'NS-LCR (Sun et al., 2024)'
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
        'citation': 'NS-LCR (Sun et al., 2024)'
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

    Uses weighted combination approach from CBR-RAG (Wiratunga et al., 2024):
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

            # Get additional features from database
            principle_tensions = []
            cited_case_numbers = []
            features = _get_case_features(match.target_case_id)
            if features:
                principle_tensions = features.get('principle_tensions', []) or []
                cited_case_numbers = features.get('cited_case_numbers', []) or []

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
                'principle_tensions': principle_tensions,
                'cited_case_numbers': cited_case_numbers,
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


@precedents_bp.route('/api/similarity_network', methods=['GET'])
@auth_optional
def api_similarity_network():
    """
    API endpoint for case similarity network visualization.

    Returns graph data for D3.js force-directed visualization showing
    all cases with precedent features and their pairwise similarities.

    Query params:
        case_id: Optional focus case (will be highlighted)
        min_score: Minimum similarity threshold (default: 0.2)

    Returns:
        JSON with nodes (cases) and edges (similarity relationships)
    """
    focus_case_id = request.args.get('case_id', type=int)
    min_score = request.args.get('min_score', 0.2, type=float)

    try:
        # Get all cases with features
        cases_query = text("""
            SELECT
                cpf.case_id,
                d.title,
                cpf.outcome_type,
                cpf.transformation_type,
                cpf.provisions_cited,
                (SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id = cpf.case_id) as entity_count
            FROM case_precedent_features cpf
            JOIN documents d ON cpf.case_id = d.id
            ORDER BY cpf.case_id
        """)
        cases = db.session.execute(cases_query).fetchall()

        if not cases:
            return jsonify({
                'success': False,
                'error': 'No cases with precedent features found',
                'nodes': [],
                'edges': []
            })

        # Build nodes
        nodes = []
        case_ids = []
        for case in cases:
            case_id, title, outcome, transformation, provisions, entity_count = case
            case_ids.append(case_id)

            # Extract case number from title if present
            case_label = title
            if 'Case' in title and '-' in title:
                # Try to extract "Case XX-X" pattern
                import re
                match = re.search(r'Case\s+(\d+-\d+)', title)
                if match:
                    case_label = f"Case {match.group(1)}"

            nodes.append({
                'id': case_id,
                'label': case_label,
                'full_title': title,
                'outcome': outcome or 'unknown',
                'transformation': transformation,
                'provisions': provisions or [],
                'entity_count': entity_count or 0,
                'is_focus': case_id == focus_case_id
            })

        # Get pairwise similarities from cache or compute
        edges = []
        from app.services.precedent import PrecedentSimilarityService
        similarity_service = PrecedentSimilarityService()

        # Check cache first
        cache_query = text("""
            SELECT
                source_case_id,
                target_case_id,
                overall_similarity,
                facts_similarity,
                discussion_similarity,
                provision_overlap,
                outcome_alignment,
                tag_overlap,
                principle_overlap
            FROM precedent_similarity_cache
            WHERE overall_similarity >= :min_score
        """)
        cached = db.session.execute(cache_query, {'min_score': min_score}).fetchall()

        # Build set of cached pairs
        cached_pairs = set()
        for row in cached:
            src, tgt, overall, facts, disc, prov, outcome, tag, principle = row
            if src in case_ids and tgt in case_ids:
                cached_pairs.add((src, tgt))
                cached_pairs.add((tgt, src))  # Symmetrical

                # Get matching provisions
                matching_provs = _get_matching_provisions(src, tgt)

                edges.append({
                    'source': src,
                    'target': tgt,
                    'similarity': round(overall, 3),
                    'components': {
                        'facts_similarity': round(facts or 0, 3),
                        'discussion_similarity': round(disc or 0, 3),
                        'provision_overlap': round(prov or 0, 3),
                        'outcome_alignment': round(outcome or 0, 3),
                        'tag_overlap': round(tag or 0, 3),
                        'principle_overlap': round(principle or 0, 3)
                    },
                    'matching_provisions': matching_provs
                })

        # Compute missing pairs if needed
        computed_count = 0
        for i, src_id in enumerate(case_ids):
            for tgt_id in case_ids[i + 1:]:
                if (src_id, tgt_id) not in cached_pairs:
                    # Compute similarity
                    result = similarity_service.calculate_similarity(src_id, tgt_id)
                    if result.overall_similarity >= min_score:
                        edges.append({
                            'source': src_id,
                            'target': tgt_id,
                            'similarity': round(result.overall_similarity, 3),
                            'components': {
                                k: round(v, 3) for k, v in result.component_scores.items()
                            },
                            'matching_provisions': result.matching_provisions
                        })
                        # Cache the result
                        similarity_service.cache_similarity(result)
                        computed_count += 1

        logger.info(f"Similarity network: {len(nodes)} nodes, {len(edges)} edges "
                    f"({computed_count} newly computed)")

        return jsonify({
            'success': True,
            'nodes': nodes,
            'edges': edges,
            'focus_case_id': focus_case_id,
            'min_score': min_score,
            'metadata': {
                'total_cases': len(nodes),
                'total_edges': len(edges),
                'outcome_distribution': _count_outcomes(nodes),
                'matching_methods': MATCHING_METHODS
            }
        })

    except Exception as e:
        logger.error(f"Error building similarity network: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'nodes': [],
            'edges': []
        }), 500


@precedents_bp.route('/network', methods=['GET'])
@auth_optional
def similarity_network_view():
    """Display the case similarity network visualization."""
    focus_case_id = request.args.get('case_id', type=int)

    # Get focus case details if specified
    focus_case = None
    if focus_case_id:
        focus_case = Document.query.get(focus_case_id)

    return render_template(
        'similarity_network.html',
        focus_case=focus_case,
        focus_case_id=focus_case_id,
        matching_methods=MATCHING_METHODS
    )


@precedents_bp.route('/api/similarity_matrix', methods=['GET'])
@auth_optional
def api_similarity_matrix():
    """
    API endpoint for NxN case similarity matrix.

    Returns full pairwise similarity matrix for heatmap visualization.
    """
    component = request.args.get('component', 'overall')

    try:
        # Get all cases with features
        cases_query = text("""
            SELECT cpf.case_id, d.title, cpf.outcome_type
            FROM case_precedent_features cpf
            JOIN documents d ON cpf.case_id = d.id
            ORDER BY cpf.case_id
        """)
        cases = db.session.execute(cases_query).fetchall()

        case_list = []
        case_ids = []
        for case_id, title, outcome in cases:
            case_ids.append(case_id)
            # Extract case number
            label = title
            import re
            match = re.search(r'Case\s+(\d+-\d+)', title)
            if match:
                label = f"Case {match.group(1)}"
            case_list.append({
                'id': case_id,
                'label': label,
                'outcome': outcome or 'unknown'
            })

        n = len(case_ids)
        matrix = [[0.0] * n for _ in range(n)]

        # Fill matrix from cache
        from app.services.precedent import PrecedentSimilarityService
        similarity_service = PrecedentSimilarityService()

        for i, src_id in enumerate(case_ids):
            matrix[i][i] = 1.0  # Self-similarity
            for j, tgt_id in enumerate(case_ids):
                if i < j:
                    result = similarity_service.calculate_similarity(src_id, tgt_id)
                    if component == 'overall':
                        score = result.overall_similarity
                    else:
                        score = result.component_scores.get(component, 0)
                    matrix[i][j] = round(score, 3)
                    matrix[j][i] = round(score, 3)

        return jsonify({
            'success': True,
            'cases': case_list,
            'matrix': matrix,
            'component': component,
            'available_components': list(MATCHING_METHODS.keys()) + ['overall']
        })

    except Exception as e:
        logger.error(f"Error building similarity matrix: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


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
                   transformation_type, cited_case_numbers
            FROM case_precedent_features
            WHERE case_id = :case_id
        """)
        result = db.session.execute(query, {'case_id': case_id}).fetchone()
        if result:
            return {
                'principle_tensions': result[0],
                'obligation_conflicts': result[1],
                'transformation_type': result[2],
                'cited_case_numbers': result[3]
            }
    except Exception as e:
        logger.warning(f"Error getting case features for {case_id}: {e}")
    return None


@precedents_bp.route('/pending', methods=['GET'])
@auth_optional
def pending_precedents():
    """View pending precedent URLs that could be ingested."""
    from app.services.precedent.cited_case_ingestor import CitedCaseIngestor, get_ingestion_summary

    ingestor = CitedCaseIngestor()

    # Get pending URLs from case metadata
    pending_summary = ingestor.get_all_pending_url_summary()

    # Get missing URLs from current case content (real-time scan)
    missing_urls = ingestor.find_missing_case_urls()

    # Get ingestion summary
    summary = get_ingestion_summary()

    # Get case source distribution
    source_query = text("""
        SELECT
            COALESCE(doc_metadata->>'case_source', 'unknown') as source,
            COUNT(*) as count
        FROM documents
        WHERE document_type IN ('case', 'case_study')
        GROUP BY doc_metadata->>'case_source'
    """)
    source_results = db.session.execute(source_query).fetchall()
    case_sources = {row[0]: row[1] for row in source_results}

    return render_template(
        'pending_precedents.html',
        pending_summary=pending_summary,
        missing_urls=missing_urls[:50],  # Limit display
        total_missing=len(missing_urls),
        summary=summary,
        case_sources=case_sources
    )


@precedents_bp.route('/api/pending', methods=['GET'])
@auth_optional
def api_pending_precedents():
    """API endpoint for pending precedent URLs."""
    from app.services.precedent.cited_case_ingestor import CitedCaseIngestor, get_ingestion_summary

    ingestor = CitedCaseIngestor()
    missing_urls = ingestor.find_missing_case_urls()
    summary = get_ingestion_summary()
    pending_summary = ingestor.get_all_pending_url_summary()

    return jsonify({
        'success': True,
        'summary': summary,
        'pending_from_metadata': pending_summary,
        'missing_urls': missing_urls,
        'total_missing': len(missing_urls)
    })


@precedents_bp.route('/api/ingest', methods=['POST'])
@auth_optional
def api_ingest_pending():
    """API endpoint to ingest pending precedent URLs."""
    from app.services.precedent.cited_case_ingestor import CitedCaseIngestor

    data = request.get_json() or {}
    url = data.get('url')
    max_cases = data.get('max_cases', 10)
    world_id = data.get('world_id', 1)

    ingestor = CitedCaseIngestor()

    if url:
        # Ingest single URL
        result = ingestor.ingest_from_url(url, world_id=world_id)
        return jsonify(result)
    else:
        # Ingest batch of missing URLs
        result = ingestor.ingest_missing_urls(max_cases=max_cases, world_id=world_id)
        return jsonify(result)
