"""Case listing and search routes."""

import logging
from collections import defaultdict, OrderedDict
from flask import render_template, request, redirect, url_for
from app.utils.environment_auth import auth_optional
from app.models import Document
from app.models.world import World
from app.services.embedding.section_embedding_service import SectionEmbeddingService
from app.services.pipeline_state_manager import get_bulk_progress
from app.services.search.unified_search_service import (
    UnifiedSearchService,
    chips_by_case,
    query_tokens,
)
from app import db

logger = logging.getLogger(__name__)


def _case_result(document, chunk=None, tag_match=None):
    """Build the template dict for one search hit, from a matched section
    chunk (semantic lane) or a matched subject tag (tag band)."""
    metadata = {}
    if document.doc_metadata:
        if isinstance(document.doc_metadata, dict):
            metadata = document.doc_metadata
        else:
            logger.warning(f"doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")

    year = metadata.get('year', '')
    if not year and metadata.get('case_number'):
        case_num = metadata.get('case_number', '')
        if '-' in case_num:
            year_prefix = case_num.split('-')[0]
            if len(year_prefix) == 2:
                century = "20" if int(year_prefix) < 50 else "19"
                year = century + year_prefix

    questions_list = metadata.get('questions_list', [])
    conclusion_items = metadata.get('conclusion_items', [])

    if not questions_list and metadata.get('sections', {}).get('question'):
        questions_list = [metadata['sections']['question']]

    if not conclusion_items and metadata.get('sections', {}).get('conclusion'):
        conclusion_items = [metadata['sections']['conclusion']]

    chunk = chunk or {}
    return {
        'id': document.id,
        'title': document.title,
        'description': document.content[:500] + '...' if document.content and len(document.content) > 500 else (document.content or ''),
        'decision': metadata.get('decision', ''),
        'outcome': metadata.get('outcome', ''),
        'ethical_analysis': metadata.get('ethical_analysis', ''),
        'source': document.source,
        'document_id': document.id,
        'is_document': True,
        'similarity_score': chunk.get('similarity'),
        'matching_chunk': chunk.get('content', ''),
        'matching_section': chunk.get('section_type', ''),
        'tag_match': tag_match,
        'year': year,
        'questions_list': questions_list,
        'conclusion_items': conclusion_items,
        'case_number': metadata.get('case_number', ''),
        'full_date': metadata.get('full_date', ''),
        'doc_metadata': metadata
    }


def register_listing_routes(bp):

    @bp.route('/', methods=['GET'])
    @auth_optional
    def list_cases():
        """Display all cases."""
        # Get world filter from query parameters
        world_id = request.args.get('world_id', type=int)

        # Get search query from request parameters
        query = request.args.get('query', '')

        # Get status filter from query parameters
        # Values: 'all', 'extracted', 'synthesized' (default)
        # 'extracted' = Passes 1-3 complete, 'synthesized' = Step 4 complete
        status_filter = request.args.get('status', 'synthesized')

        # Get subject tag filter from query parameters
        selected_tag = request.args.get('tag', '')

        # Initialize variables
        cases = []
        error = None

        try:
            # Import necessary models
            from sqlalchemy import text
            from app.models.section_term_link import SectionTermLink

            # Filter cases by world if specified
            if world_id:
                # Get document-based cases for the specified world
                document_cases = Document.query.filter(
                    Document.world_id == world_id,
                    Document.document_type.in_(['case_study', 'case'])
                ).all()
            else:
                # Get all document-based cases
                document_cases = Document.query.filter(
                    Document.document_type.in_(['case_study', 'case'])
                ).all()

            # Get all case IDs for bulk status checking
            case_ids = [doc.id for doc in document_cases]

            # Bulk check for term links
            term_links_status = {}
            if case_ids:
                with db.engine.connect() as conn:
                    result = conn.execute(
                        text("""
                            SELECT DISTINCT document_id
                            FROM section_term_links
                            WHERE document_id = ANY(:document_ids)
                        """),
                        {"document_ids": case_ids}
                    )
                    for row in result:
                        term_links_status[row[0]] = True

            # Get pipeline progress for all cases (15-substep completion + active runs)
            pipeline_progress_map = get_bulk_progress(case_ids)

            # Convert documents to case format
            for doc in document_cases:
                # Extract metadata - ensuring it's a dictionary
                metadata = {}
                if doc.doc_metadata:
                    if isinstance(doc.doc_metadata, dict):
                        metadata = doc.doc_metadata
                    else:
                        logger.warning(f"doc_metadata for document {doc.id} is not a dictionary: {type(doc.doc_metadata)}")

                # Extract year from metadata or case number
                year = metadata.get('year', '')
                if not year and metadata.get('case_number'):
                    case_num = metadata.get('case_number', '')
                    if '-' in case_num:
                        year_prefix = case_num.split('-')[0]
                        if len(year_prefix) == 2:
                            century = "20" if int(year_prefix) < 50 else "19"
                            year = century + year_prefix

                # Extract questions and conclusions
                questions_list = metadata.get('questions_list', [])
                conclusion_items = metadata.get('conclusion_items', [])

                if not questions_list and metadata.get('sections', {}).get('question'):
                    questions_list = [metadata['sections']['question']]

                if not conclusion_items and metadata.get('sections', {}).get('conclusion'):
                    conclusion_items = [metadata['sections']['conclusion']]

                # Get pipeline progress from bulk query
                progress = pipeline_progress_map.get(doc.id, {
                    'complete': 0, 'total': 15, 'pct': 0,
                    'status': 'not_started', 'active_run': None,
                })

                # Create case object
                case = {
                    'id': doc.id,
                    'title': doc.title,
                    'description': doc.content[:500] + '...' if doc.content and len(doc.content) > 500 else (doc.content or ''),
                    'decision': metadata.get('decision', ''),
                    'outcome': metadata.get('outcome', ''),
                    'ethical_analysis': metadata.get('ethical_analysis', ''),
                    'source': doc.source,
                    'document_id': doc.id,
                    'is_document': True,
                    'year': year,
                    'questions_list': questions_list,
                    'conclusion_items': conclusion_items,
                    'case_number': metadata.get('case_number', ''),
                    'full_date': metadata.get('full_date', ''),
                    'has_term_links': term_links_status.get(doc.id, False),
                    'pipeline_status': progress['status'],
                    'pipeline_progress': progress,
                    'doc_metadata': metadata
                }

                cases.append(case)

        except Exception as e:
            error = str(e)

        # Collect all unique tags BEFORE filtering (so we can show all options)
        all_tags = set()
        for case in cases:
            tags = case.get('doc_metadata', {}).get('subject_tags', [])
            if tags:
                all_tags.update(tags)
        all_tags = sorted(all_tags)

        # Apply status filter if not 'all'
        if status_filter == 'synthesized':
            cases = [case for case in cases if case.get('pipeline_status') == 'synthesized']
        elif status_filter == 'extracted':
            cases = [case for case in cases if case.get('pipeline_status') in ('extracted', 'synthesized')]

        # Apply tag filter if specified
        if selected_tag:
            cases = [
                case for case in cases
                if case.get('doc_metadata', {}).get('subject_tags')
                and selected_tag in case['doc_metadata']['subject_tags']
            ]

        # Group cases by year
        cases_by_year = defaultdict(list)

        for case in cases:
            year = case.get('year', 'Unknown')
            if not year:
                year = 'Unknown'
            cases_by_year[year].append(case)

        # Sort years in descending order (most recent first)
        sorted_years = sorted(cases_by_year.keys(), reverse=True, key=lambda x: x if x != 'Unknown' else '0')

        # Create ordered dictionary to maintain sort order
        grouped_cases = OrderedDict()
        for year in sorted_years:
            grouped_cases[year] = sorted(cases_by_year[year], key=lambda x: x.get('case_number', ''))

        # Get all worlds for the filter dropdown
        worlds = World.query.all()

        return render_template(
            'cases.html',
            cases=cases,
            grouped_cases=grouped_cases,
            worlds=worlds,
            selected_world_id=world_id,
            query=query,
            status_filter=status_filter,
            selected_tag=selected_tag,
            all_tags=all_tags,
            error=error
        )

    @bp.route('/search', methods=['GET'])
    def search_cases():
        """Search for cases based on a query."""
        query = request.args.get('query', '')
        world_id = request.args.get('world_id', type=int)

        cases = []
        error = None

        if not query:
            return redirect(url_for('cases.list_cases', world_id=world_id))

        # Entity lane: matching OntServe ontology entities (unified search
        # increment 1). A failure here must stay visible, not empty the panel.
        entity_results = []
        entity_error = None
        try:
            entity_results = UnifiedSearchService().search_entities(query)
        except Exception as e:
            logger.error(f"OntServe entity search failed for query '{query}': {e}")
            entity_error = str(e)

        # Titles for the entity back-links ("appears in N cases").
        linked_case_ids = {cid for e in entity_results for cid in e.get('case_ids', [])}
        case_titles = {}
        if linked_case_ids:
            for doc in Document.query.filter(Document.id.in_(linked_case_ids)).all():
                case_titles[doc.id] = doc.title

        # Chips: which of the matched concepts each case result contains
        # (increment 4; back-links inverted, top-ranked concepts first).
        entity_chips = chips_by_case(entity_results)

        # Subject-tag matches first: tags were assigned to the case by the
        # board/editors, so a query matching one is authoritative and outranks
        # any similarity signal (plan decision D7). Token-subset matching with
        # the same plural-insensitive tokens as the entity lane, so "Faithful
        # Agents" matches the tag "Faithful Agents and Trustees".
        tag_matched_cases = []
        tag_matched_ids = set()
        matched_tags = []
        q_tokens = set(query_tokens(query))
        if q_tokens:
            docs = Document.query.filter(Document.document_type.in_(('case', 'case_study')))
            if world_id is not None:
                docs = docs.filter(Document.world_id == world_id)
            for document in docs.all():
                metadata = document.doc_metadata if isinstance(document.doc_metadata, dict) else {}
                for tag in metadata.get('subject_tags') or []:
                    if q_tokens <= set(query_tokens(tag)):
                        tag_matched_ids.add(document.id)
                        if tag not in matched_tags:
                            matched_tags.append(tag)
                        tag_matched_cases.append(_case_result(document, tag_match=tag))
                        break
            tag_matched_cases.sort(key=lambda c: (c.get('year') or '', c.get('case_number') or ''), reverse=True)

        try:
            # Case lane: section-level pgvector similarity. The corpus carries
            # embeddings on document_sections (not document_chunks), so search
            # sections and keep each document's best-scoring section.
            section_service = SectionEmbeddingService()
            similar_sections = section_service.find_similar_sections(query, limit=40)

            seen_doc_ids = set(tag_matched_ids)

            for chunk in similar_sections:
                document_id = chunk.get('document_id')

                if document_id in seen_doc_ids:
                    continue
                seen_doc_ids.add(document_id)
                if len(cases) >= 10:
                    break

                document = Document.query.get(document_id)
                if document and document.document_type in ('case', 'case_study'):
                    cases.append(_case_result(document, chunk=chunk))

        except Exception as e:
            # Roll back so a failed search query cannot leave the session
            # aborted for the queries that render the rest of the page.
            db.session.rollback()
            logger.error(f"Case chunk search failed for query '{query}': {e}")
            error = str(e)

        # Group: the tag-match band leads, then semantic results by year.
        grouped_by_year = defaultdict(list)
        unknown_year_cases = []

        for case in cases:
            year = case.get('year')
            if year:
                grouped_by_year[year].append(case)
            else:
                unknown_year_cases.append(case)

        grouped_cases = OrderedDict()
        if tag_matched_cases:
            label = 'Tagged ' + ', '.join(f'“{t}”' for t in matched_tags)
            grouped_cases[label] = tag_matched_cases
        for year in sorted(grouped_by_year.keys(), reverse=True):
            grouped_cases[year] = grouped_by_year[year]

        if unknown_year_cases:
            grouped_cases['Unknown Year'] = unknown_year_cases

        worlds = World.query.all()

        return render_template(
            'cases.html',
            grouped_cases=grouped_cases,
            worlds=worlds,
            selected_world_id=world_id,
            query=query,
            error=error,
            search_results=True,
            entity_results=entity_results,
            entity_error=entity_error,
            case_titles=case_titles,
            entity_chips=entity_chips
        )
