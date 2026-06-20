"""Similarity network / shared-entities / matrix routes."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)
from app.routes.precedents.helpers import (
    MATCHING_METHODS,
    _get_matching_provisions,
    _count_outcomes,
)


def register_similarity_routes(bp):
    @bp.route('/api/similarity_network', methods=['GET'])
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
                'component_similarity': 'component_similarity',
                'provision_overlap': 'provision_overlap',
                'tag_overlap': 'tag_overlap',
            }

            # Build cache query with optional component filter
            if component_filter and component_filter in component_columns:
                # Filter by specific component score
                cache_query = text(f"""
                SELECT
                    source_case_id,
                    target_case_id,
                    overall_similarity,
                    component_similarity,
                    provision_overlap,
                    tag_overlap
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
                    component_similarity,
                    provision_overlap,
                    tag_overlap
                FROM precedent_similarity_cache
                WHERE overall_similarity >= :min_score
                ORDER BY overall_similarity DESC
            """)
                cached = db.session.execute(cache_query, {'min_score': min_score}).fetchall()

            # Build set of cached pairs
            cached_pairs = set()
            for row in cached:
                src, tgt, overall, comp_sim, prov, tag = row
                if src in case_ids and tgt in case_ids:
                    cached_pairs.add((src, tgt))
                    cached_pairs.add((tgt, src))  # Symmetrical

                    # Get matching provisions
                    matching_provs = _get_matching_provisions(src, tgt)

                    # Determine primary component for this edge
                    components = {
                        'component_similarity': round(comp_sim or 0, 3),
                        'provision_overlap': round(prov or 0, 3),
                        'tag_overlap': round(tag or 0, 3),
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

            # On-demand computation disabled to prevent OOM on large case sets.
            # The similarity cache must be pre-populated by an offline job.
            computed_count = 0

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


    @bp.route('/api/shared_entities/<int:source_id>/<int:target_id>', methods=['GET'])
    @auth_optional
    def api_shared_entities(source_id, target_id):
        """Return shared entities between two cases, grouped by D-tuple component."""
        # Canonical display names for each component (title-cased)
        COMPONENT_TYPES = ['Roles', 'Principles', 'Obligations', 'States',
                           'Resources', 'Actions', 'Events', 'Capabilities', 'Constraints']
        # Match regardless of how entity_type is cased in the database
        COMPONENT_TYPES_LOWER = [c.lower() for c in COMPONENT_TYPES]
        # Map lowercase -> display name for grouping
        DISPLAY_NAME = {c.lower(): c for c in COMPONENT_TYPES}

        try:
            query = text("""
            SELECT case_id, LOWER(entity_type) as entity_type, LOWER(entity_label) as entity_label
            FROM temporary_rdf_storage
            WHERE case_id IN :case_ids
              AND entity_label IS NOT NULL
              AND LOWER(entity_type) IN :types
        """)
            results = db.session.execute(query, {
                'case_ids': (source_id, target_id),
                'types': tuple(COMPONENT_TYPES_LOWER)
            }).fetchall()

            # Build per-component entity sets for each case (keyed by lowercase type)
            source_entities = {}
            target_entities = {}
            for case_id, etype, label in results:
                bucket = source_entities if case_id == source_id else target_entities
                if etype not in bucket:
                    bucket[etype] = set()
                bucket[etype].add(label)

            # Compute per-component shared entities (use display names as keys)
            shared = {}
            for comp_lower in COMPONENT_TYPES_LOWER:
                src_set = source_entities.get(comp_lower, set())
                tgt_set = target_entities.get(comp_lower, set())
                intersection = src_set & tgt_set
                if intersection:
                    display = DISPLAY_NAME[comp_lower]
                    shared[display] = {
                        'shared': sorted(list(intersection)),
                        'source_count': len(src_set),
                        'target_count': len(tgt_set),
                        'shared_count': len(intersection)
                    }

            return jsonify({'success': True, 'shared_entities': shared})

        except Exception as e:
            logger.error(f"Error fetching shared entities for cases {source_id}/{target_id}: {e}")
            return jsonify({'success': False, 'error': str(e)}), 500


    @bp.route('/network', methods=['GET'])
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


    @bp.route('/api/similarity_matrix', methods=['GET'])
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


