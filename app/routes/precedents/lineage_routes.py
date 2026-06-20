"""Pending precedents + lineage graph/print + ingest routes."""
import logging
from flask import Blueprint, render_template, request, jsonify
from app.utils.environment_auth import auth_optional
from app.models import Document
from app import db
from sqlalchemy import text

logger = logging.getLogger(__name__)


def register_lineage_routes(bp):
    @bp.route('/pending', methods=['GET'])
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


    @bp.route('/api/pending', methods=['GET'])
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


    @bp.route('/lineage/print', methods=['GET'])
    @auth_optional
    def lineage_print_view():
        """Chromeless lineage graph sized for paper figures."""
        focus_case_id = request.args.get('case_id', type=int)
        hops = request.args.get('hops', 2, type=int)
        preset = request.args.get('preset', 'teaser')
        show_panel = request.args.get('panel', 'true').lower() == 'true'

        focus_case = None
        if focus_case_id:
            focus_case = Document.query.get(focus_case_id)

        cases_query = text("""
        SELECT d.id, d.title, d.doc_metadata->>'case_number' as case_number
        FROM documents d
        JOIN case_precedent_features cpf ON cpf.case_id = d.id
        ORDER BY
            CAST(split_part(d.doc_metadata->>'case_number', '-', 1) AS INTEGER),
            CAST(split_part(d.doc_metadata->>'case_number', '-', 2) AS INTEGER)
    """)
        rows = db.session.execute(cases_query).fetchall()
        case_list = [
            {'id': r[0], 'title': r[1], 'case_number': r[2] or ''}
            for r in rows
        ]

        return render_template(
            'lineage_print.html',
            focus_case=focus_case,
            focus_case_id=focus_case_id,
            cases=case_list,
            hops=hops,
            preset=preset,
            show_panel=show_panel,
        )


    @bp.route('/lineage', methods=['GET'])
    @auth_optional
    def lineage_graph_view():
        """Display the precedent citation lineage graph."""
        focus_case_id = request.args.get('case_id', type=int)

        focus_case = None
        if focus_case_id:
            focus_case = Document.query.get(focus_case_id)

        # Case list for the focus selector dropdown (numeric sort on YY-N case numbers)
        cases_query = text("""
        SELECT d.id, d.title, d.doc_metadata->>'case_number' as case_number
        FROM documents d
        JOIN case_precedent_features cpf ON cpf.case_id = d.id
        ORDER BY
            CAST(split_part(d.doc_metadata->>'case_number', '-', 1) AS INTEGER),
            CAST(split_part(d.doc_metadata->>'case_number', '-', 2) AS INTEGER)
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


    @bp.route('/api/lineage_graph', methods=['GET'])
    @auth_optional
    def api_lineage_graph():
        """
    API endpoint for directed citation lineage graph.

    Returns nodes (cases) and directed edges (citing case -> cited precedent).
    """
        focus_case_id = request.args.get('case_id', type=int)
        hops = request.args.get('hops', type=int)
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

            # Focus mode: collect ego-network around focus case
            if focus_case_id and focus_case_id in all_nodes:
                if hops is not None and hops >= 0:
                    # Undirected BFS limited to N hops from focus case
                    reachable = {focus_case_id}
                    frontier = {focus_case_id}
                    for _ in range(hops):
                        next_frontier = set()
                        for node_id in frontier:
                            for neighbor in all_nodes[node_id].get('cites', []):
                                if neighbor not in reachable and neighbor in all_nodes:
                                    next_frontier.add(neighbor)
                                    reachable.add(neighbor)
                            for neighbor in all_nodes[node_id].get('cited_by', []):
                                if neighbor not in reachable and neighbor in all_nodes:
                                    next_frontier.add(neighbor)
                                    reachable.add(neighbor)
                        frontier = next_frontier
                        if not frontier:
                            break
                else:
                    # Directed BFS: full transitive closure (ancestors + descendants)
                    reachable = {focus_case_id}
                    queue = [focus_case_id]
                    while queue:
                        current = queue.pop(0)
                        for neighbor in all_nodes[current].get('cited_by', []):
                            if neighbor not in reachable:
                                reachable.add(neighbor)
                                queue.append(neighbor)
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


    @bp.route('/api/ingest', methods=['POST'])
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
