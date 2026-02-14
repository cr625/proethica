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

        # Get source case's features for overlap calculation
        source_features = _get_case_features(case_id)
        source_cited = set(source_features.get('cited_case_numbers', []) or []) if source_features else set()
        source_transformation = source_features.get('transformation_type') if source_features else None

        # Get source case's subject tags and outcome from doc_metadata
        source_case = Document.query.get(case_id)
        source_tags = set()
        source_outcome = None
        if source_case and source_case.doc_metadata:
            source_tags = set(source_case.doc_metadata.get('subject_tags', []) or [])
            source_outcome = source_case.doc_metadata.get('outcome')

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
                'source_outcome': source_outcome,
                'target_outcome': match.target_outcome,
                'transformation_match': transformation_match,
                'source_transformation': source_transformation,
                'target_transformation': match.target_transformation,
                'overlapping_tags': overlapping_tags,
                'overlapping_citations': overlapping_citations,
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
        min_score: Minimum similarity threshold (default: 0.3)
        component: Filter by specific similarity component
                   ('provision_overlap', 'discussion_similarity', etc.)
        component_min: Minimum score for the selected component (default: 0.3)

    Returns:
        JSON with nodes (cases) and edges (similarity relationships)
    """
    focus_case_id = request.args.get('case_id', type=int)
    min_score = request.args.get('min_score', 0.3, type=float)
    component_filter = request.args.get('component', None)
    component_min = request.args.get('component_min', 0.3, type=float)
    entity_type_filter = request.args.get('entity_type', None)
    tag_filter = request.args.get('tag', None)

    try:
        # Get all available tags for the filter UI
        tags_query = text("""
            SELECT DISTINCT unnest(subject_tags) as tag, COUNT(*) as count
            FROM case_precedent_features
            WHERE subject_tags IS NOT NULL
            GROUP BY tag
            ORDER BY count DESC, tag
        """)
        all_tags = [row[0] for row in db.session.execute(tags_query).fetchall()]

        # Get all cases with features (optionally filtered by tag)
        if tag_filter:
            cases_query = text("""
                SELECT
                    cpf.case_id,
                    d.title,
                    cpf.outcome_type,
                    cpf.transformation_type,
                    cpf.provisions_cited,
                    cpf.subject_tags,
                    (SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id = cpf.case_id) as entity_count
                FROM case_precedent_features cpf
                JOIN documents d ON cpf.case_id = d.id
                WHERE :tag = ANY(cpf.subject_tags)
                ORDER BY cpf.case_id
            """)
            cases = db.session.execute(cases_query, {'tag': tag_filter}).fetchall()
        else:
            cases_query = text("""
                SELECT
                    cpf.case_id,
                    d.title,
                    cpf.outcome_type,
                    cpf.transformation_type,
                    cpf.provisions_cited,
                    cpf.subject_tags,
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
            case_id, title, outcome, transformation, provisions, subject_tags, entity_count = case
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
                'subject_tags': subject_tags or [],
                'entity_count': entity_count or 0,
                'is_focus': case_id == focus_case_id
            })

        # Get pairwise similarities from cache or compute
        edges = []
        from app.services.precedent import PrecedentSimilarityService
        similarity_service = PrecedentSimilarityService()

        # Map component names to cache column names
        component_columns = {
            'facts_similarity': 'facts_similarity',
            'discussion_similarity': 'discussion_similarity',
            'provision_overlap': 'provision_overlap',
            'outcome_alignment': 'outcome_alignment',
            'tag_overlap': 'tag_overlap',
            'principle_overlap': 'principle_overlap'
        }

        # Build cache query with optional component filter
        if component_filter and component_filter in component_columns:
            # Filter by specific component score
            cache_query = text(f"""
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
                WHERE {component_columns[component_filter]} >= :component_min
                ORDER BY {component_columns[component_filter]} DESC
            """)
            cached = db.session.execute(cache_query, {'component_min': component_min}).fetchall()
        else:
            # No component filter - use overall similarity
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
                ORDER BY overall_similarity DESC
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

                # Determine primary component for this edge
                components = {
                    'facts_similarity': round(facts or 0, 3),
                    'discussion_similarity': round(disc or 0, 3),
                    'provision_overlap': round(prov or 0, 3),
                    'outcome_alignment': round(outcome or 0, 3),
                    'tag_overlap': round(tag or 0, 3),
                    'principle_overlap': round(principle or 0, 3)
                }
                primary_component = max(components, key=components.get)

                edges.append({
                    'source': src,
                    'target': tgt,
                    'similarity': round(overall, 3),
                    'components': components,
                    'primary_component': primary_component,
                    'matching_provisions': matching_provs
                })

        # Compute missing pairs if needed (skip if filtering by component - use cache only)
        computed_count = 0
        if not component_filter:
            for i, src_id in enumerate(case_ids):
                for tgt_id in case_ids[i + 1:]:
                    if (src_id, tgt_id) not in cached_pairs:
                        # Compute similarity
                        result = similarity_service.calculate_similarity(src_id, tgt_id)
                        if result.overall_similarity >= min_score:
                            # Determine primary component
                            components = {
                                k: round(v, 3) for k, v in result.component_scores.items()
                            }
                            primary_component = max(components, key=components.get)

                            edges.append({
                                'source': src_id,
                                'target': tgt_id,
                                'similarity': round(result.overall_similarity, 3),
                                'components': components,
                                'primary_component': primary_component,
                                'matching_provisions': result.matching_provisions
                            })
                            # Cache the result
                            similarity_service.cache_similarity(result)
                            computed_count += 1

        # Entity-based filtering (if entity_type_filter is set)
        if entity_type_filter:
            edges = []  # Replace similarity edges with entity edges

            # Get entities by case for the specified type
            entity_query = text("""
                SELECT case_id, LOWER(entity_label) as entity_label
                FROM temporary_rdf_storage
                WHERE entity_type = :entity_type
                  AND entity_label IS NOT NULL
                  AND case_id IN :case_ids
            """)
            entity_results = db.session.execute(
                entity_query,
                {'entity_type': entity_type_filter, 'case_ids': tuple(case_ids)}
            ).fetchall()

            # Build case -> entities mapping
            case_entities = {}
            for case_id, label in entity_results:
                if case_id not in case_entities:
                    case_entities[case_id] = set()
                case_entities[case_id].add(label)

            # Compute entity overlap between all case pairs
            for i, src_id in enumerate(case_ids):
                src_entities = case_entities.get(src_id, set())
                if not src_entities:
                    continue

                for tgt_id in case_ids[i + 1:]:
                    tgt_entities = case_entities.get(tgt_id, set())
                    if not tgt_entities:
                        continue

                    # Calculate Jaccard similarity
                    intersection = src_entities & tgt_entities
                    if not intersection:
                        continue

                    union = src_entities | tgt_entities
                    jaccard = len(intersection) / len(union) if union else 0

                    # Only include edges with at least one shared entity
                    if len(intersection) >= 1:
                        edges.append({
                            'source': src_id,
                            'target': tgt_id,
                            'similarity': round(jaccard, 3),
                            'components': {
                                'entity_overlap': round(jaccard, 3),
                                'shared_count': len(intersection),
                                'entity_type': entity_type_filter
                            },
                            'primary_component': 'entity_overlap',
                            'matching_entities': sorted(list(intersection))[:10],  # Top 10
                            'matching_provisions': []
                        })

            logger.info(f"Entity network ({entity_type_filter}): {len(nodes)} nodes, "
                        f"{len(edges)} edges")
        else:
            logger.info(f"Similarity network: {len(nodes)} nodes, {len(edges)} edges "
                        f"(filter={component_filter}, {computed_count} newly computed)")

        return jsonify({
            'success': True,
            'nodes': nodes,
            'edges': edges,
            'focus_case_id': focus_case_id,
            'min_score': min_score,
            'component_filter': component_filter,
            'component_min': component_min,
            'entity_type_filter': entity_type_filter,
            'tag_filter': tag_filter,
            'all_tags': all_tags,
            'metadata': {
                'total_cases': len(nodes),
                'total_edges': len(edges),
                'outcome_distribution': _count_outcomes(nodes),
                'matching_methods': MATCHING_METHODS,
                'available_filters': list(component_columns.keys())
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


@precedents_bp.route('/lineage', methods=['GET'])
@auth_optional
def lineage_graph_view():
    """Display the precedent citation lineage graph."""
    focus_case_id = request.args.get('case_id', type=int)

    focus_case = None
    if focus_case_id:
        focus_case = Document.query.get(focus_case_id)

    # Case list for the focus selector dropdown
    cases_query = text("""
        SELECT d.id, d.title, d.doc_metadata->>'case_number' as case_number
        FROM documents d
        JOIN case_precedent_features cpf ON cpf.case_id = d.id
        ORDER BY d.doc_metadata->>'case_number'
    """)
    rows = db.session.execute(cases_query).fetchall()
    case_list = [
        {'id': r[0], 'title': r[1], 'case_number': r[2] or ''}
        for r in rows
    ]

    return render_template(
        'lineage_graph.html',
        focus_case=focus_case,
        focus_case_id=focus_case_id,
        cases=case_list
    )


@precedents_bp.route('/api/lineage_graph', methods=['GET'])
@auth_optional
def api_lineage_graph():
    """
    API endpoint for directed citation lineage graph.

    Returns nodes (cases) and directed edges (citing case -> cited precedent).
    """
    focus_case_id = request.args.get('case_id', type=int)
    show_all = request.args.get('show_all', 'false').lower() == 'true'

    try:
        query = text("""
            SELECT
                cpf.case_id,
                d.title,
                d.doc_metadata->>'case_number' as case_number,
                COALESCE(
                    (d.doc_metadata->'date_parts'->>'year')::int,
                    (d.doc_metadata->>'year')::int
                ) as year,
                cpf.outcome_type,
                cpf.cited_case_ids
            FROM case_precedent_features cpf
            JOIN documents d ON cpf.case_id = d.id
            ORDER BY year NULLS FIRST, cpf.case_id
        """)
        rows = db.session.execute(query).fetchall()

        # Build node lookup and edge list
        all_nodes = {}
        all_edges = []
        valid_ids = {r[0] for r in rows}

        for case_id, title, case_number, year, outcome, cited_ids in rows:
            label = f"Case {case_number}" if case_number else title[:30]
            all_nodes[case_id] = {
                'id': case_id,
                'label': label,
                'full_title': title,
                'case_number': case_number or '',
                'year': year or 0,
                'outcome': outcome or 'unknown',
                'in_degree': 0,
                'out_degree': 0,
                'cites': [],
                'cited_by': [],
                'is_focus': case_id == focus_case_id
            }

            if cited_ids:
                for cited_id in cited_ids:
                    if cited_id in valid_ids and cited_id != case_id:
                        all_edges.append({
                            'source': case_id,
                            'target': cited_id
                        })

        # Compute degrees and build adjacency lists
        for edge in all_edges:
            src = edge['source']
            tgt = edge['target']
            if src in all_nodes:
                all_nodes[src]['out_degree'] += 1
                all_nodes[src]['cites'].append(tgt)
            if tgt in all_nodes:
                all_nodes[tgt]['in_degree'] += 1
                all_nodes[tgt]['cited_by'].append(src)

        # Focus mode: BFS to collect ego-network
        if focus_case_id and focus_case_id in all_nodes:
            reachable = {focus_case_id}
            # BFS forward (descendants: cases that cite the focus, transitively)
            queue = [focus_case_id]
            while queue:
                current = queue.pop(0)
                for neighbor in all_nodes[current].get('cited_by', []):
                    if neighbor not in reachable:
                        reachable.add(neighbor)
                        queue.append(neighbor)
            # BFS backward (ancestors: cases the focus cites, transitively)
            queue = [focus_case_id]
            visited_back = {focus_case_id}
            while queue:
                current = queue.pop(0)
                for neighbor in all_nodes[current].get('cites', []):
                    if neighbor not in visited_back:
                        visited_back.add(neighbor)
                        reachable.add(neighbor)
                        queue.append(neighbor)

            all_edges = [e for e in all_edges
                         if e['source'] in reachable and e['target'] in reachable]
            all_nodes = {k: v for k, v in all_nodes.items() if k in reachable}

        elif not show_all:
            # Filter to only cases involved in at least one citation
            connected = set()
            for edge in all_edges:
                connected.add(edge['source'])
                connected.add(edge['target'])
            all_nodes = {k: v for k, v in all_nodes.items() if k in connected}

        # Strip adjacency lists from response (used only for BFS)
        nodes_out = []
        for node in all_nodes.values():
            n = dict(node)
            del n['cites']
            del n['cited_by']
            nodes_out.append(n)

        years = [n['year'] for n in nodes_out if n['year'] > 0]

        return jsonify({
            'success': True,
            'nodes': nodes_out,
            'edges': all_edges,
            'focus_case_id': focus_case_id,
            'metadata': {
                'total_nodes': len(nodes_out),
                'total_edges': len(all_edges),
                'year_range': [min(years), max(years)] if years else [0, 0],
                'outcome_distribution': {
                    outcome: sum(1 for n in nodes_out if n['outcome'] == outcome)
                    for outcome in set(n['outcome'] for n in nodes_out)
                }
            }
        })

    except Exception as e:
        logger.error(f"Error building lineage graph: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'nodes': [],
            'edges': []
        }), 500


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
