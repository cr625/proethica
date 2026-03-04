"""Case listing and search routes."""

import logging
from collections import defaultdict, OrderedDict
from flask import render_template, request, redirect, url_for
from app.utils.environment_auth import auth_optional
from app.models import Document
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app.services.pipeline_status_service import PipelineStatusService
from app import db

logger = logging.getLogger(__name__)


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

            # Bulk check for enhanced associations
            enhanced_associations_status = {}
            if case_ids:
                with db.engine.connect() as conn:
                    result = conn.execute(
                        text("""
                            SELECT DISTINCT case_id
                            FROM case_guideline_associations
                            WHERE case_id = ANY(:case_ids)
                        """),
                        {"case_ids": case_ids}
                    )
                    for row in result:
                        enhanced_associations_status[row[0]] = True

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

            # Get pipeline status for all cases using the state machine
            # Returns: 'not_started', 'extracted', or 'synthesized'
            pipeline_status_map = PipelineStatusService.get_bulk_simple_status(case_ids)

            # Convert documents to case format
            for doc in document_cases:
                # Extract metadata - ensuring it's a dictionary
                metadata = {}
                if doc.doc_metadata:
                    if isinstance(doc.doc_metadata, dict):
                        metadata = doc.doc_metadata
                    else:
                        print(f"Warning: doc_metadata for document {doc.id} is not a dictionary: {type(doc.doc_metadata)}")

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

                # Get pipeline status from state machine
                pipeline_status = pipeline_status_map.get(doc.id, 'not_started')

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
                    'has_enhanced_associations': enhanced_associations_status.get(doc.id, False),
                    'has_term_links': term_links_status.get(doc.id, False),
                    'pipeline_status': pipeline_status,
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

        try:
            embedding_service = EmbeddingService()

            similar_chunks = embedding_service.search_similar_chunks(
                query=query,
                k=10,
                world_id=world_id,
                document_type=['case_study', 'case']
            )

            seen_doc_ids = set()

            for chunk in similar_chunks:
                document_id = chunk.get('document_id')

                if document_id in seen_doc_ids:
                    continue

                document = Document.query.get(document_id)
                if document:
                    metadata = {}
                    if document.doc_metadata:
                        if isinstance(document.doc_metadata, dict):
                            metadata = document.doc_metadata
                        else:
                            print(f"Warning: doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")

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

                    case = {
                        'id': document.id,
                        'title': document.title,
                        'description': document.content[:500] + '...' if document.content and len(document.content) > 500 else (document.content or ''),
                        'decision': metadata.get('decision', ''),
                        'outcome': metadata.get('outcome', ''),
                        'ethical_analysis': metadata.get('ethical_analysis', ''),
                        'source': document.source,
                        'document_id': document.id,
                        'is_document': True,
                        'similarity_score': 1.0 - chunk.get('distance', 0.0),
                        'matching_chunk': chunk.get('chunk_text', ''),
                        'year': year,
                        'questions_list': questions_list,
                        'conclusion_items': conclusion_items,
                        'case_number': metadata.get('case_number', ''),
                        'full_date': metadata.get('full_date', ''),
                        'doc_metadata': metadata
                    }

                    cases.append(case)
                    seen_doc_ids.add(document_id)

        except Exception as e:
            error = str(e)

        # Group cases by year
        grouped_by_year = defaultdict(list)
        unknown_year_cases = []

        for case in cases:
            year = case.get('year')
            if year:
                grouped_by_year[year].append(case)
            else:
                unknown_year_cases.append(case)

        grouped_cases = OrderedDict()
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
            search_results=True
        )
