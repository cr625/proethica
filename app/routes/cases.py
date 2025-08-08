"""
Routes for case management, including listing, viewing, and searching cases.
"""

import os
import re
import logging
from urllib.parse import urlparse
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app import db
from app.services.entity_triple_service import EntityTripleService
from app.services.case_url_processor import CaseUrlProcessor
from app.services.case_to_scenario_service import CaseToScenarioService
from app.services.scenario_generation_service import ScenarioGenerationService
from app.services.scenario_pipeline.scenario_generation_phase_a import DirectScenarioPipelineService
from app.services.agents.case_creation_agent import CaseCreationAgent
from app.services.conversation_to_case_service import ConversationToCaseService
from app.models.agent_conversation import AgentConversation

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprints
cases_bp = Blueprint('cases', __name__, url_prefix='/cases')

@cases_bp.route('/', methods=['GET'])
def list_cases():
    """Display all cases."""
    # Get world filter from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Get search query from request parameters
    query = request.args.get('query', '')
    
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
        
        # Convert documents to case format
        for doc in document_cases:
            # Extract metadata - ensuring it's a dictionary
            metadata = {}
            if doc.doc_metadata:
                if isinstance(doc.doc_metadata, dict):
                    metadata = doc.doc_metadata
                else:
                    # If it's not a dict (likely a string), initialize as empty dict
                    # and log the issue
                    print(f"Warning: doc_metadata for document {doc.id} is not a dictionary: {type(doc.doc_metadata)}")
            
            # Extract year from metadata or case number
            year = metadata.get('year', '')
            if not year and metadata.get('case_number'):
                # Try to extract year from case number (e.g., "23-4" -> "2023")
                case_num = metadata.get('case_number', '')
                if '-' in case_num:
                    year_prefix = case_num.split('-')[0]
                    if len(year_prefix) == 2:
                        century = "20" if int(year_prefix) < 50 else "19"
                        year = century + year_prefix
            
            # Extract questions and conclusions
            questions_list = metadata.get('questions_list', [])
            conclusion_items = metadata.get('conclusion_items', [])
            
            # If lists are empty, try to extract from sections
            if not questions_list and metadata.get('sections', {}).get('question'):
                # Simple extraction - just use the HTML content as a single question
                questions_list = [metadata['sections']['question']]
            
            if not conclusion_items and metadata.get('sections', {}).get('conclusion'):
                # Simple extraction - just use the HTML content as a single conclusion
                conclusion_items = [metadata['sections']['conclusion']]
            
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
                'doc_metadata': metadata  # Include full metadata for subject tags
            }
            
            cases.append(case)
    
    except Exception as e:
        error = str(e)
    
    # Group cases by year
    from collections import defaultdict
    cases_by_year = defaultdict(list)
    
    for case in cases:
        year = case.get('year', 'Unknown')
        if not year:
            year = 'Unknown'
        cases_by_year[year].append(case)
    
    # Sort years in descending order (most recent first)
    sorted_years = sorted(cases_by_year.keys(), reverse=True, key=lambda x: x if x != 'Unknown' else '0')
    
    # Create ordered dictionary to maintain sort order
    from collections import OrderedDict
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
        error=error
    )

@cases_bp.route('/search', methods=['GET'])
def search_cases():
    """Search for cases based on a query."""
    # Get search query from request parameters
    query = request.args.get('query', '')
    
    # Get world filter from query parameters
    world_id = request.args.get('world_id', type=int)
    
    # Initialize variables
    cases = []
    error = None
    
    if not query:
        return redirect(url_for('cases.list_cases', world_id=world_id))
    
    try:
        # Use the embedding service to search for similar cases
        embedding_service = EmbeddingService()
        
        # Search for similar chunks
        similar_chunks = embedding_service.search_similar_chunks(
            query=query,
            k=10,
            world_id=world_id,
            document_type=['case_study', 'case']
        )
        
        # Get the full documents for each chunk
        seen_doc_ids = set()
        
        for chunk in similar_chunks:
            # Get the document ID from the chunk
            document_id = chunk.get('document_id')
            
            # Skip if we've already seen this document
            if document_id in seen_doc_ids:
                continue
            
            # Get the document
            document = Document.query.get(document_id)
            if document:
                # Extract metadata - ensuring it's a dictionary
                metadata = {}
                if document.doc_metadata:
                    if isinstance(document.doc_metadata, dict):
                        metadata = document.doc_metadata
                    else:
                        # If it's not a dict (likely a string), initialize as empty dict
                        # and log the issue
                        print(f"Warning: doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")
                
                # Extract year from metadata or case number
                year = metadata.get('year', '')
                if not year and metadata.get('case_number'):
                    # Try to extract year from case number (e.g., "23-4" -> "2023")
                    case_num = metadata.get('case_number', '')
                    if '-' in case_num:
                        year_prefix = case_num.split('-')[0]
                        if len(year_prefix) == 2:
                            century = "20" if int(year_prefix) < 50 else "19"
                            year = century + year_prefix
                
                # Extract questions and conclusions
                questions_list = metadata.get('questions_list', [])
                conclusion_items = metadata.get('conclusion_items', [])
                
                # If lists are empty, try to extract from sections
                if not questions_list and metadata.get('sections', {}).get('question'):
                    questions_list = [metadata['sections']['question']]
                
                if not conclusion_items and metadata.get('sections', {}).get('conclusion'):
                    conclusion_items = [metadata['sections']['conclusion']]
                
                # Create case object
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
                    'doc_metadata': metadata  # Include full metadata for subject tags
                }
                
                cases.append(case)
                seen_doc_ids.add(document_id)
    
    except Exception as e:
        error = str(e)
    
    # Group cases by year
    from collections import defaultdict, OrderedDict
    grouped_by_year = defaultdict(list)
    unknown_year_cases = []
    
    for case in cases:
        year = case.get('year')
        if year:
            grouped_by_year[year].append(case)
        else:
            unknown_year_cases.append(case)
    
    # Sort years in descending order and create ordered dict
    grouped_cases = OrderedDict()
    for year in sorted(grouped_by_year.keys(), reverse=True):
        grouped_cases[year] = grouped_by_year[year]
    
    # Add unknown year cases at the end if any
    if unknown_year_cases:
        grouped_cases['Unknown Year'] = unknown_year_cases
    
    # Get all worlds for the filter dropdown
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

@cases_bp.route('/<int:id>', methods=['GET'])
def view_case(id):
    """Display a specific case."""
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Accept both 'case' and 'case_study' document types
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Extract metadata - ensuring it's a dictionary
    metadata = {}
    if document.doc_metadata:
        if isinstance(document.doc_metadata, dict):
            metadata = document.doc_metadata
        else:
            # If it's not a dict (likely a string), initialize as empty dict
            # and log the issue
            print(f"Warning: doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")
    
    # Create case object
    case = {
        'id': document.id,
        'title': document.title,
        'description': document.content or '',
        'decision': metadata.get('decision', ''),
        'outcome': metadata.get('outcome', ''),
        'ethical_analysis': metadata.get('ethical_analysis', ''),
        'source': document.source,
        'document_id': document.id,
        'is_document': True,
        'case_number': metadata.get('case_number', ''),
        'year': metadata.get('year', ''),
        'world_id': document.world_id,
        'doc_metadata': metadata  # Pass the full metadata to access sections
    }
    
    # Get the world
    world = World.query.get(document.world_id) if document.world_id else None
    
    # Get entity triples and related cases
    entity_triples = []
    knowledge_graph_connections = {}
    try:
        triple_service = EntityTripleService()
        # Query using the subject URI pattern which is how ontology triples are stored
        case_uri = f"http://proethica.org/cases/{document.id}"
        entity_triples = triple_service.find_triples(subject=case_uri, entity_type='document')
        
        # Find related cases by triples
        related_cases_data = triple_service.find_related_cases_by_triples(document.id)
        
        # If we have related cases, get their titles and sort by number of shared triples
        if related_cases_data:
            # For each predicate and related case
            for predicate, data in related_cases_data.items():
                for case_info in data['related_cases']:
                    case_id = case_info['entity_id']
                    # Get the document
                    related_doc = Document.query.get(case_id)
                    if related_doc:
                        # Add the title to the case info
                        case_info['title'] = related_doc.title
                
                # Sort related cases by number of shared triples in descending order
                data['related_cases'] = sorted(
                    data['related_cases'], 
                    key=lambda x: len(x['shared_triples']), 
                    reverse=True
                )
            
            # Save the data
            knowledge_graph_connections = related_cases_data
    except Exception as e:
        flash(f"Warning: Could not retrieve entity triples or related cases: {str(e)}", 'warning')
    
    # Get ontology term links for hover functionality
    term_links_by_section = {}
    try:
        from app.models.section_term_link import SectionTermLink
        document_term_links = SectionTermLink.get_document_term_links(document.id)
        
        if document_term_links:
            term_links_by_section = document_term_links
            logger.info(f"Loaded term links for document {document.id}: {len(document_term_links)} sections")
    except Exception as e:
        logger.warning(f"Could not load term links for document {document.id}: {str(e)}")
    
    return render_template('case_detail.html', case=case, world=world, 
                          entity_triples=entity_triples, 
                          knowledge_graph_connections=knowledge_graph_connections,
                          term_links_by_section=term_links_by_section)

@cases_bp.route('/new', methods=['GET'])
def case_options():
    """Display case creation options."""
    return render_template('create_case_options.html')

@cases_bp.route('/new/manual', methods=['GET'])
def manual_create_form():
    """Display form to manually create a new case."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case_manual.html', worlds=worlds)

@cases_bp.route('/new/url', methods=['GET'])
def url_form():
    """Display form to create a case from URL."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case_from_url.html', worlds=worlds)

@cases_bp.route('/process/url', methods=['GET', 'POST'])
def process_url_pipeline():
    """Process a URL through the case processing pipeline and save directly to database."""
    # Handle GET requests (typically from back button)
    if request.method == 'GET':
        url = request.args.get('url')
        if not url:
            return redirect(url_for('cases.url_form'))
        
        # Re-submit as POST to process the URL
        return render_template('process_url_form.html', url=url)
    
    # Process POST requests
    url = request.form.get('url')
    process_extraction = request.form.get('process_extraction') == 'true'
    world_id = request.form.get('world_id', type=int, default=1)  # Default to Engineering world (ID=1)
    
    if not url:
        return render_template('raw_url_content.html', 
                               error="URL is required",
                               error_details="Please provide a valid URL to process.")
    
    # Initialize pipeline
    from app.services.case_processing.pipeline_manager import PipelineManager
    from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
    from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep
    from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep
    
    pipeline = PipelineManager()
    pipeline.register_step('url_retrieval', URLRetrievalStep())
    pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())
    pipeline.register_step('document_structure', DocumentStructureAnnotationStep())
    
    # Determine which steps to run based on process_extraction
    # Always include URL retrieval, add extraction and structure annotation if requested
    steps_to_run = ['url_retrieval']
    if process_extraction:
        steps_to_run.extend(['nspe_extraction', 'document_structure'])
    
    # Run pipeline
    logger.info(f"Running pipeline for URL: {url} with steps: {', '.join(steps_to_run)}")
    result = pipeline.run_pipeline({'url': url}, steps_to_run)
    
    # Get the final result (output from the last step)
    final_result = result.get('final_result', {})
    
    # Check for errors
    if final_result.get('status') == 'error':
        return render_template('raw_url_content.html',
                               error=final_result.get('message'),
                               error_details=final_result,
                               url=url)
    
    # If extraction was requested, save the case and redirect
    if process_extraction:
        # Ensure the result has the structure the template expects
        if 'sections' not in final_result and final_result.get('status') == 'success':
            # If the sections key isn't at the top level but we have individual section data,
            # restructure it to match what the template expects
            sections_data = {
                'facts': final_result.get('facts', ''),
                'question': final_result.get('question_html', ''),
                'references': final_result.get('references', ''),
                'discussion': final_result.get('discussion', ''),
                'conclusion': final_result.get('conclusion', '')
            }
            final_result['sections'] = sections_data
        
        # If conclusion_items are not explicitly included, but we have structured conclusion data
        # in the extraction result, make sure we include it in the final_result
        if 'conclusion_items' not in final_result and isinstance(final_result.get('conclusion'), dict):
            conclusion_data = final_result.get('conclusion', {})
            if 'conclusions' in conclusion_data:
                final_result['conclusion_items'] = conclusion_data['conclusions']
            elif isinstance(conclusion_data, dict) and 'html' in conclusion_data and 'conclusions' in conclusion_data:
                final_result['conclusion_items'] = conclusion_data['conclusions']
                final_result['sections']['conclusion'] = conclusion_data['html']
        
        # Extract relevant data for saving
        title = final_result.get('title', 'Case from URL')
        case_number = final_result.get('case_number', '')
        year = final_result.get('year', '')
        full_date = final_result.get('full_date')
        date_parts = final_result.get('date_parts')
        pdf_url = final_result.get('pdf_url', '')
        facts = final_result.get('sections', {}).get('facts', '')
        question_html = final_result.get('sections', {}).get('question', '')
        references = final_result.get('sections', {}).get('references', '')
        discussion = final_result.get('sections', {}).get('discussion', '')
        conclusion = final_result.get('sections', {}).get('conclusion', '')
        dissenting_opinion = final_result.get('sections', {}).get('dissenting_opinion', '')
        
        # Get structured list data
        questions_list = final_result.get('questions_list', [])
        conclusion_items = final_result.get('conclusion_items', [])
        subject_tags = final_result.get('subject_tags', [])
            
        # Generate HTML content that matches the extraction page display format
        html_content = ""
        
        # Facts section
        if facts:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Facts</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{facts}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Questions section
        if question_html or questions_list:
            question_heading = "Questions" if questions_list and len(questions_list) > 1 else "Question"
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{question_heading}</h5>
            </div>
            <div class="card-body">
"""
            if questions_list:
                html_content += "<ol class=\"mb-0\">\n"
                for q in questions_list:
                    clean_question = q.strip()
                    html_content += f"    <li>{clean_question}</li>\n"
                html_content += "</ol>\n"
            else:
                html_content += f"<p class=\"mb-0\">{question_html}</p>\n"
            
            html_content += """
            </div>
        </div>
    </div>
</div>
"""
        
        # References section
        if references:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">NSPE Code of Ethics References</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{references}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Discussion section
        if discussion:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Discussion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{discussion}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Conclusion section
        if conclusion or conclusion_items:
            conclusion_heading = "Conclusions" if conclusion_items and len(conclusion_items) > 1 else "Conclusion"
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{conclusion_heading}</h5>
            </div>
            <div class="card-body">
"""
            if conclusion_items:
                html_content += "<ol class=\"mb-0\">\n"
                for c in conclusion_items:
                    clean_conclusion = c.strip()
                    html_content += f"    <li>{clean_conclusion}</li>\n"
                html_content += "</ol>\n"
            else:
                html_content += f"<p class=\"mb-0\">{conclusion}</p>\n"
            
            html_content += """
            </div>
        </div>
    </div>
</div>
"""
        
        # Dissenting Opinion section
        if dissenting_opinion:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-warning">
                <h5 class="mb-0">Dissenting Opinion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{dissenting_opinion}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Store original sections in metadata for future reference
        metadata = {
            'case_number': case_number,
            'year': year,
            'full_date': full_date,
            'date_parts': date_parts,
            'pdf_url': pdf_url,
            'subject_tags': subject_tags,  # NSPE subject tags
            'sections': {
                'facts': facts,
                'question': question_html,
                'references': references,
                'discussion': discussion,
                'conclusion': conclusion,
                'dissenting_opinion': dissenting_opinion
            },
            'questions_list': questions_list,
            'conclusion_items': conclusion_items,
            'extraction_method': 'direct_process',
            'display_format': 'extraction_style'  # Flag to indicate special display format
        }
        
        # Add dual format sections if available
        if 'sections_dual' in final_result:
            metadata['sections_dual'] = final_result['sections_dual']
            logger.info("Storing dual format sections (HTML and text)")
        
        # Add text-only sections for embeddings if available
        if 'sections_text' in final_result:
            metadata['sections_text'] = final_result['sections_text']
        
        # Add document structure information if available
        if 'document_structure' in final_result:
            # Store document structure in nested format as per CLAUDE.md
            from datetime import datetime
            metadata['document_structure'] = {
                'document_uri': final_result['document_structure'].get('document_uri'),
                'structure_triples': final_result['document_structure'].get('structure_triples'),
                'sections': metadata['sections'],  # Use the sections we already have
                'annotation_timestamp': datetime.utcnow().isoformat()
            }
            logger.info(f"Added document structure with URI: {metadata['document_structure']['document_uri']}")
        
        # Add section embeddings metadata if available
        if 'section_embeddings_metadata' in final_result:
            metadata['section_embeddings_metadata'] = final_result['section_embeddings_metadata']
            logger.info(f"Added section embeddings metadata with {len(metadata['section_embeddings_metadata'])} sections")
        
        # Safe way to get user_id without relying on Flask-Login being initialized
        user_id = None
        try:
            if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_id = current_user.id
                metadata['created_by_user_id'] = user_id
        except Exception:
            # If there's any error accessing current_user, just use None
            pass
        
        # Create document record
        from app.models.document import Document, PROCESSING_STATUS
        
        document = Document(
            title=title,
            content=html_content,
            document_type='case_study',
            world_id=world_id,
            source=url,
            file_type='url',
            doc_metadata=metadata,
            processing_status=PROCESSING_STATUS['COMPLETED']
        )
        
        # Save the document
        db.session.add(document)
        db.session.commit()
        
        # Generate section embeddings after saving the document
        logger.info(f"Generating section embeddings for document ID: {document.id}")
        try:
            from app.services.section_embedding_service import SectionEmbeddingService
            section_embedding_service = SectionEmbeddingService()
            
            # Process document sections to generate embeddings
            embedding_result = section_embedding_service.process_document_sections(document.id)
            
            if embedding_result.get('success'):
                logger.info(f"Successfully generated embeddings for {embedding_result.get('sections_embedded')} sections")
                # Update document metadata with embedding info
                if 'document_structure' not in metadata:
                    metadata['document_structure'] = {}
                
                metadata['document_structure']['section_embeddings'] = {
                    'count': embedding_result.get('sections_embedded', 0),
                    'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                    'storage_type': 'pgvector'
                }
                
                # Save the updated metadata
                document.doc_metadata = metadata
                db.session.commit()
                logger.info("Updated document metadata with section embedding information")
            else:
                logger.warning(f"Failed to generate section embeddings: {embedding_result.get('error')}")
        except Exception as e:
            logger.error(f"Error generating section embeddings: {str(e)}")
            # Continue anyway - embeddings can be generated later
        
        # Log success with document ID and structure information
        logger.info(f"Case saved successfully with ID: {document.id}, includes document structure: {'document_structure' in metadata}")
        
        # Redirect to view the case
        success_msg = 'Case extracted and saved successfully'
        if 'document_structure' in metadata:
            success_msg += ' with document structure annotation'
        flash(success_msg, 'success')
        return redirect(url_for('cases.view_case', id=document.id))
    
    # Otherwise, just show the raw content
    return render_template('raw_url_content.html',
                          url=final_result.get('url'),
                          content=final_result.get('content'),
                          content_type=final_result.get('content_type'),
                          content_length=final_result.get('content_length'),
                          status_code=final_result.get('status_code'),
                          encoding=final_result.get('encoding'))

@cases_bp.route('/new/document', methods=['GET'])
def upload_document_form():
    """Display form to create a case from document upload."""
    # Get all worlds for the dropdown
    worlds = World.query.all()
    
    return render_template('create_case_from_document.html', worlds=worlds)

@cases_bp.route('/<int:id>/delete', methods=['POST'])
def delete_case(id):
    """Delete a case by ID."""
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Get the world ID if applicable
    world_id = document.world_id
    
    # If this is part of a world, remove it from the world's cases list
    if world_id:
        world = World.query.get(world_id)
        if world and world.cases and id in world.cases:
            world.cases.remove(id)
            db.session.add(world)
    
    # Delete any associated entity triples
    try:
        from app.services.entity_triple_service import EntityTripleService
        triple_service = EntityTripleService()
        triple_service.delete_triples_for_entity('document', id)
    except Exception as e:
        flash(f"Warning: Could not delete associated entity triples: {str(e)}", 'warning')
    
    # Delete the document
    db.session.delete(document)
    db.session.commit()
    
    flash(f"Case '{document.title}' deleted successfully", 'success')
    return redirect(url_for('cases.list_cases'))

@cases_bp.route('/new/manual', methods=['POST'])
def create_case_manual():
    """Create a new case manually."""
    # Get form data
    title = request.form.get('title')
    description = request.form.get('description')
    decision = request.form.get('decision')
    outcome = request.form.get('outcome')
    ethical_analysis = request.form.get('ethical_analysis')
    source = request.form.get('source')
    world_id = request.form.get('world_id', type=int)
    rdf_metadata = request.form.get('rdf_metadata', '')
    
    # Validate required fields
    if not title:
        flash('Title is required', 'danger')
        return redirect(url_for('cases.manual_create_form'))
    
    if not description:
        flash('Description is required', 'danger')
        return redirect(url_for('cases.manual_create_form'))
    
    # Validate world_id (required)
    if not world_id:
        flash('World selection is required', 'danger')
        return redirect(url_for('cases.manual_create_form'))
        
    world = World.query.get(world_id)
    if not world:
        flash(f'World with ID {world_id} not found', 'danger')
        return redirect(url_for('cases.manual_create_form'))
    
    # Initialize metadata
    metadata = {
        'decision': decision,
        'outcome': outcome,
        'ethical_analysis': ethical_analysis
    }
    
    # Process RDF metadata if provided
    if rdf_metadata:
        try:
            import json
            rdf_data = json.loads(rdf_metadata)
            
            # Validate the basic structure
            if 'triples' not in rdf_data:
                rdf_data['triples'] = []
            
            if 'namespaces' not in rdf_data:
                rdf_data['namespaces'] = {}
                
            # Add the RDF data to the metadata
            metadata['rdf_triples'] = rdf_data['triples']
            metadata['rdf_namespaces'] = rdf_data['namespaces']
            
            # Convert to entity triples if possible
            if world_id == 1:  # Engineering world
                from app.services.entity_triple_service import EntityTripleService
                triple_service = EntityTripleService()
                
                try:
                    # Store a reference to process this document's triples later
                    metadata['process_entity_triples'] = True
                except Exception as e:
                    flash(f'Warning: RDF triples could not be converted to entity triples: {str(e)}', 'warning')
        
        except json.JSONDecodeError:
            flash('Warning: RDF metadata is not valid JSON. It will be stored as plain text.', 'warning')
            metadata['rdf_metadata_text'] = rdf_metadata
        except Exception as e:
            flash(f'Warning: Error processing RDF metadata: {str(e)}', 'warning')
            metadata['rdf_metadata_text'] = rdf_metadata
    
    # Create document record
    document = Document(
        title=title,
        content=description,
        document_type='case_study',
        world_id=world_id,
        source=source,
        doc_metadata=metadata
    )
    
    # Add to database
    db.session.add(document)
    db.session.commit()
    
    # Process document for embeddings
    try:
        embedding_service = EmbeddingService()
        embedding_service.process_document(document.id)
        
        # Process entity triples if needed
        if metadata.get('process_entity_triples'):
            try:
                from app.services.entity_triple_service import EntityTripleService
                triple_service = EntityTripleService()
                
                # Get the document with its ID
                doc = Document.query.get(document.id)
                
                # Convert RDF triples to entity triples
                for triple in metadata.get('rdf_triples', []):
                    triple_service.add_triple(
                        subject=f"http://proethica.org/entity/document_{document.id}",
                        predicate=triple['predicate'],
                        obj=triple['object'],
                        is_literal=False,  # RDF triples are URIs by default
                        entity_type='entity',  # Using 'entity' type as it's one of the valid types
                        entity_id=document.id
                    )
                
                flash('RDF triples processed successfully', 'success')
            except Exception as e:
                flash(f'Warning: Error processing entity triples: {str(e)}', 'warning')
        
        flash('Case created and processed successfully', 'success')
    except Exception as e:
        flash(f'Case created but error processing embeddings: {str(e)}', 'warning')
    
    return redirect(url_for('cases.view_case', id=document.id))
    
@cases_bp.route('/new/url', methods=['POST'])
def create_from_url():
    """Create a new case from URL."""
    # Get form data
    url = request.form.get('url')
    world_id = request.form.get('world_id', type=int)
    title = request.form.get('title')
    case_number = request.form.get('case_number')
    year = request.form.get('year')
    
    # Safe way to get user_id without relying on Flask-Login being initialized
    user_id = None
    try:
        # current_user is now directly available from flask_login
        if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = current_user.id
    except Exception:
        # If there's any error accessing current_user, just use None
        pass
    
    # Validate required fields
    if not url:
        flash('URL is required', 'danger')
        return redirect(url_for('cases.url_form'))
    
    # Validate world_id (required)
    if not world_id:
        flash('World selection is required', 'danger')
        return redirect(url_for('cases.url_form'))
        
    world = World.query.get(world_id)
    if not world:
        flash(f'World with ID {world_id} not found', 'danger')
        return redirect(url_for('cases.url_form'))
    
    try:
        # Check if we have pre-extracted content from the form
        using_extracted_content = request.form.get('extracted_content') == 'true'
        
        if using_extracted_content:
            # Use pre-extracted content sections from the form
            facts = request.form.get('facts', '')
            question_html = request.form.get('question_html', '')
            references = request.form.get('references', '')
            discussion = request.form.get('discussion', '')
            conclusion = request.form.get('conclusion', '')
            pdf_url = request.form.get('pdf_url', '')
            
            # Try to parse JSON lists if available
            questions_list = []
            conclusion_items = []
            
            try:
                import json
                if request.form.get('questions_list'):
                    questions_list = json.loads(request.form.get('questions_list'))
                if request.form.get('conclusion_items'):
                    conclusion_items = json.loads(request.form.get('conclusion_items'))
            except Exception as e:
                print(f"Warning: Error parsing JSON lists: {str(e)}")
            
            # Combine sections into a structured content for display
            combined_content = f"<h2>Facts</h2>\n{facts}\n\n"
            
            if question_html:
                if questions_list and len(questions_list) > 1:
                    combined_content += f"<h2>Questions</h2>\n"
                else:
                    combined_content += f"<h2>Question</h2>\n"
                    
                if questions_list:
                    combined_content += "<ol>\n"
                    for q in questions_list:
                        combined_content += f"<li>{q}</li>\n"
                    combined_content += "</ol>\n\n"
                else:
                    combined_content += f"{question_html}\n\n"
            
            if references:
                combined_content += f"<h2>NSPE Code of Ethics References</h2>\n{references}\n\n"
                
            if discussion:
                combined_content += f"<h2>Discussion</h2>\n{discussion}\n\n"
                
            if conclusion:
                if conclusion_items and len(conclusion_items) > 1:
                    combined_content += f"<h2>Conclusions</h2>\n"
                else:
                    combined_content += f"<h2>Conclusion</h2>\n"
                    
                if conclusion_items:
                    combined_content += "<ol>\n"
                    for c in conclusion_items:
                        combined_content += f"<li>{c}</li>\n"
                    combined_content += "</ol>\n\n"
                else:
                    combined_content += f"{conclusion}\n\n"
            
            # Prepare metadata with the extracted sections
            metadata = {
                'case_number': case_number,
                'year': year,
                'pdf_url': pdf_url,
                'sections': {
                    'facts': facts,
                    'question': question_html,
                    'references': references,
                    'discussion': discussion,
                    'conclusion': conclusion
                },
                'questions_list': questions_list,
                'conclusion_items': conclusion_items,
                'extraction_method': 'pipeline_preserved'
            }
            
            # Create document record using the extracted sections
            document = Document(
                title=title or 'Case from URL',
                content=combined_content,
                document_type='case_study',
                world_id=world_id,
                source=url,
                file_type='url',
                doc_metadata=metadata
            )
            
            # Set processing status to completed since we already have the content
            document.processing_status = PROCESSING_STATUS['COMPLETED']
            document.processing_progress = 100
            
        else:
            # If no extracted content provided, use the URL processor to extract it
            processor = CaseUrlProcessor()
            
            # Process the URL
            result = processor.process_url(url, world_id, user_id)
            
            # Check for errors in the result
            if 'status' in result and result['status'] == 'error':
                flash(result['message'], 'danger')
                return redirect(url_for('cases.url_form'))
            
            # Create document record
            document = Document(
                title=result.get('title', 'Case from URL'),
                content=result.get('content', ''),
                document_type='case_study',
                world_id=world_id,
                source=url,
                file_type='url',
                doc_metadata=result.get('metadata', {})
            )
            
            # If we have embedding data, set the processing status to completed
            if result.get('content'):
                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100
                
            # Add any extracted triples if they exist
            if 'triples' in result and result['triples']:
                # Store triples in metadata for processing after commit
                document.doc_metadata['triples_to_process'] = result['triples']
        
        # Store user_id in metadata (common for both paths)
        if user_id and document.doc_metadata:
            document.doc_metadata['created_by_user_id'] = user_id
        
        # Save the document
        db.session.add(document)
        db.session.commit()
        
        # Process triples if we have them in metadata
        if document.doc_metadata and document.doc_metadata.get('triples_to_process'):
            triple_service = EntityTripleService()
            
            for triple in document.doc_metadata['triples_to_process']:
                try:
                    # Create entity triple record using the add_triple method with valid entity_type
                    triple_service.add_triple(
                        subject=f"http://proethica.org/entity/document_{document.id}",
                        predicate=triple['predicate'],
                        obj=triple['object'],
                        is_literal=triple.get('is_literal', True),
                        entity_type='entity',  # Using 'entity' type as it's one of the valid types
                        entity_id=document.id
                    )
                except Exception as e:
                    flash(f'Warning: Error creating triple: {str(e)}', 'warning')
            
            # Remove temporary triples data from metadata
            document.doc_metadata.pop('triples_to_process', None)
            db.session.commit()
        
        flash('Case created successfully from URL', 'success')
        return redirect(url_for('cases.edit_case_form', id=document.id))
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        flash(f'Error processing URL: {str(e)}', 'danger')
        return redirect(url_for('cases.url_form'))

@cases_bp.route('/new/document', methods=['POST'])
def create_from_document():
    """Create a new case from document upload."""
    # Get form data
    title = request.form.get('title')
    world_id = request.form.get('world_id', type=int)
    
    # Validate required fields
    if not title:
        flash('Title is required', 'danger')
        return redirect(url_for('cases.upload_document_form'))
    
    # Check if document file was provided
    if 'document' not in request.files:
        flash('Document file is required', 'danger')
        return redirect(url_for('cases.upload_document_form'))
    
    document_file = request.files['document']
    
    # Check if file is empty
    if document_file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('cases.upload_document_form'))
    
    # Validate world_id (required)
    if not world_id:
        flash('World selection is required', 'danger')
        return redirect(url_for('cases.upload_document_form'))
        
    world = World.query.get(world_id)
    if not world:
        flash(f'World with ID {world_id} not found', 'danger')
        return redirect(url_for('cases.upload_document_form'))
    
    try:
        # Get file extension
        file_ext = os.path.splitext(document_file.filename)[1].lower()
        
        # Determine file type
        file_type_map = {
            '.pdf': 'pdf',
            '.docx': 'docx',
            '.doc': 'docx',
            '.txt': 'txt',
            '.html': 'html',
            '.htm': 'html'
        }
        
        if file_ext not in file_type_map:
            flash(f'Unsupported file type: {file_ext}', 'danger')
            return redirect(url_for('cases.upload_document_form'))
            
        file_type = file_type_map[file_ext]
        
        # Create upload directory if it doesn't exist
        upload_dir = os.path.join('app', 'uploads')
        os.makedirs(upload_dir, exist_ok=True)
        
        # Save the file
        from werkzeug.utils import secure_filename
        import uuid
        
        # Generate a unique filename
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        document_file.save(file_path)
        
        # Create document record
        from app.models.document import Document, PROCESSING_STATUS
        
        document = Document(
            title=title,
            document_type='case_study',
            world_id=world_id,
            file_path=file_path,
            file_type=file_type,
            source=document_file.filename,
            processing_status=PROCESSING_STATUS['PROCESSING'],
            doc_metadata={}
        )
        
        db.session.add(document)
        db.session.commit()
        
        # Process the document
        embedding_service = EmbeddingService()
        
        # Extract text based on file type
        text = embedding_service._extract_text(file_path, file_type)
        document.content = text
        
        # Split text into chunks and create embeddings
        chunks = embedding_service._split_text(text)
        embeddings = embedding_service.embed_documents(chunks)
        embedding_service._store_chunks(document.id, chunks, embeddings)
        
        # Update document status
        document.processing_status = PROCESSING_STATUS['COMPLETED']
        document.processing_progress = 100
        db.session.commit()
        
        flash('Document processed and case created successfully', 'success')
        return redirect(url_for('cases.edit_case_form', id=document.id))
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        flash(f'Error processing document: {str(e)}', 'danger')
        return redirect(url_for('cases.upload_document_form'))

@cases_bp.route('/<int:id>/edit', methods=['GET'])
def edit_case_form(id):
    """Display form to edit case title and description."""
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Get the world if applicable
    world = World.query.get(document.world_id) if document.world_id else None
    
    return render_template('edit_case_details.html', document=document, world=world)

@cases_bp.route('/<int:id>/edit', methods=['POST'])
def edit_case(id):
    """Process the case edit form submission."""
    
@cases_bp.route('/triple/<int:id>/edit', methods=['GET', 'POST'])
def dummy_edit_triples(id):
    """Temporary route to fix BuildError for cases_triple.edit_triples."""
    # Redirect to the regular case edit form
    return redirect(url_for('cases.edit_case_form', id=id))

# Add specific route for the URL that's causing the error
@cases_bp.route('/save-and-view', methods=['POST'])
def save_and_view_case():
    """Save case with extracted content and view it directly (no edit step)."""
    # Get form data
    url = request.form.get('url')
    world_id = request.form.get('world_id', type=int)
    title = request.form.get('title')
    case_number = request.form.get('case_number')
    year = request.form.get('year')
    full_date = request.form.get('full_date')
    
    # Try to parse date_parts if provided
    date_parts = None
    try:
        import json
        date_parts_str = request.form.get('date_parts')
        if date_parts_str:
            date_parts = json.loads(date_parts_str)
    except Exception as e:
        print(f"Warning: Error parsing date_parts: {str(e)}")
    
    # Safe way to get user_id without relying on Flask-Login being initialized
    user_id = None
    try:
        # current_user is now directly available from flask_login
        if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
            user_id = current_user.id
    except Exception:
        # If there's any error accessing current_user, just use None
        pass
    
    # Validate required fields
    if not url:
        flash('URL is required', 'danger')
        return redirect(url_for('cases.url_form'))
    
    # Validate world_id (required)
    if not world_id:
        flash('World selection is required', 'danger')
        return redirect(url_for('cases.url_form'))
        
    world = World.query.get(world_id)
    if not world:
        flash(f'World with ID {world_id} not found', 'danger')
        return redirect(url_for('cases.url_form'))
    
    try:
        # Extract content sections from the form
        # We always use the pre-extracted content for this route
        facts = request.form.get('facts', '')
        question_html = request.form.get('question_html', '')
        references = request.form.get('references', '')
        discussion = request.form.get('discussion', '')
        conclusion = request.form.get('conclusion', '')
        dissenting_opinion = request.form.get('dissenting_opinion', '')
        pdf_url = request.form.get('pdf_url', '')
        
        # Extract subject tags
        subject_tags = []
        try:
            import json
            subject_tags_str = request.form.get('subject_tags')
            if subject_tags_str:
                subject_tags = json.loads(subject_tags_str)
        except Exception as e:
            print(f"Warning: Error parsing subject_tags: {str(e)}")
            # Try to get as a single string if JSON parsing fails
            subject_tags_str = request.form.get('subject_tags', '')
            if subject_tags_str:
                subject_tags = [subject_tags_str]
        
        # Try to parse JSON lists if available
        questions_list = []
        conclusion_items = []
        
        try:
            import json
            if request.form.get('questions_list'):
                questions_list = json.loads(request.form.get('questions_list'))
            if request.form.get('conclusion_items'):
                conclusion_items = json.loads(request.form.get('conclusion_items'))
        except Exception as e:
            print(f"Warning: Error parsing JSON lists: {str(e)}")
            
        # If the questions_list is empty but we have question_html, attempt to parse them
        # This ensures backwards compatibility with older extraction code that might not populate questions_list
        if not questions_list and question_html:
            print("Attempting to parse questions from question_html")
            
            # Check if there are multiple questions in the HTML by looking for question marks
            # This handles cases where multiple questions are concatenated into a single string
            questions_raw = question_html
            
            # Split by question mark followed by a capital letter (likely new question)
            # or split by question mark at end of string
            import re
            splits = re.split(r'\?((?=[A-Z][a-z])|$)', questions_raw)
            
            # Process the splits to form complete questions
            if len(splits) > 1:  # If we found at least one question mark
                temp_questions = []
                for i in range(0, len(splits) - 1, 2):
                    if i + 1 < len(splits):
                        # Rejoin the question with its question mark
                        q = splits[i] + "?"
                        temp_questions.append(q.strip())
                
                # If we successfully parsed multiple questions, use them
                if temp_questions:
                    print(f"Successfully parsed {len(temp_questions)} questions from text")
                    questions_list = temp_questions
            
            # If still no questions_list, try looking for line breaks or numbered items
            if not questions_list:
                # Try to find numbered questions (e.g., "1. Question", "2. Question", etc.)
                numbered_questions = re.findall(r'(\d+\.\s*[^.;?!]*[.;?!])', questions_raw)
                if numbered_questions:
                    questions_list = [q.strip() for q in numbered_questions]
                    print(f"Found {len(questions_list)} numbered questions")
                else:
                    # Try to split by line breaks
                    line_splits = re.split(r'[\r\n]+', questions_raw)
                    if len(line_splits) > 1:
                        questions_list = [q.strip() for q in line_splits if q.strip()]
                        print(f"Split into {len(questions_list)} questions by line breaks")
        
        # Generate HTML content that exactly matches the extraction page display format
        # Create a structured HTML representation with the same cards and layout as case_extracted_content.html
        html_content = ""
        
        # Facts section
        if facts:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Facts</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{facts}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Questions section
        if question_html or questions_list:
            question_heading = "Questions" if questions_list and len(questions_list) > 1 else "Question"
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{question_heading}</h5>
            </div>
            <div class="card-body">
"""
            if questions_list:
                html_content += "<ol class=\"mb-0\">\n"
                # Add proper spacing and formatting for each question
                for q in questions_list:
                    # Ensure each question is on its own line with proper spacing
                    # and remove any trailing/leading whitespace
                    clean_question = q.strip()
                    html_content += f"    <li>{clean_question}</li>\n"
                html_content += "</ol>\n"
            else:
                html_content += f"<p class=\"mb-0\">{question_html}</p>\n"
            
            html_content += """
            </div>
        </div>
    </div>
</div>
"""
        
        # References section
        if references:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">NSPE Code of Ethics References</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{references}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Discussion section
        if discussion:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Discussion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{discussion}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Conclusion section
        if conclusion or conclusion_items:
            conclusion_heading = "Conclusions" if conclusion_items and len(conclusion_items) > 1 else "Conclusion"
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{conclusion_heading}</h5>
            </div>
            <div class="card-body">
"""
            if conclusion_items:
                html_content += "<ol class=\"mb-0\">\n"
                # Add proper spacing and formatting for each conclusion item
                for c in conclusion_items:
                    # Clean up the conclusion text, removing any leading/trailing whitespace
                    clean_conclusion = c.strip()
                    # Ensure proper HTML formatting with clear indentation for better readability
                    html_content += f"    <li>{clean_conclusion}</li>\n"
                html_content += "</ol>\n"
            else:
                # Only use the conclusion text if no structured items are available
                html_content += f"<p class=\"mb-0\">{conclusion}</p>\n"
            
            html_content += """
            </div>
        </div>
    </div>
</div>
"""
        
        # Dissenting Opinion section
        if dissenting_opinion:
            html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-warning">
                <h5 class="mb-0">Dissenting Opinion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{dissenting_opinion}</p>
            </div>
        </div>
    </div>
</div>
"""
        
        # Store original sections in metadata for future reference
        metadata = {
            'case_number': case_number,
            'year': year,
            'full_date': full_date,
            'date_parts': date_parts,
            'pdf_url': pdf_url,
            'subject_tags': subject_tags,  # NSPE subject tags
            'sections': {
                'facts': facts,
                'question': question_html,
                'references': references,
                'discussion': discussion,
                'conclusion': conclusion,
                'dissenting_opinion': dissenting_opinion
            },
            'questions_list': questions_list,
            'conclusion_items': conclusion_items,
            'extraction_method': 'direct_view',
            'display_format': 'extraction_style' # Flag to indicate special display format
        }
        
        # Create document record
        document = Document(
            title=title or 'Case from URL',
            content=html_content,
            document_type='case_study',
            world_id=world_id,
            source=url,
            file_type='url',
            doc_metadata=metadata
        )
        
        # Set processing status to completed since we already have the content
        document.processing_status = PROCESSING_STATUS['COMPLETED']
        document.processing_progress = 100
        
        # Store user_id in metadata
        if user_id and document.doc_metadata:
            document.doc_metadata['created_by_user_id'] = user_id
        
        # Save the document
        db.session.add(document)
        db.session.commit()
        
        flash('Case saved successfully', 'success')
        return redirect(url_for('cases.view_case', id=document.id))
        
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        flash(f'Error saving case: {str(e)}', 'danger')
        return redirect(url_for('cases.url_form'))

@cases_bp.route('/<int:id>/triple/edit', methods=['GET', 'POST'])
def dummy_edit_triples_alt(id):
    """Alternative temporary route to fix BuildError for cases_triple.edit_triples."""
    # Redirect to the regular case edit form
    return redirect(url_for('cases.edit_case_form', id=id))
    # Try to get the case as a document
    document = Document.query.get_or_404(id)
    
    # Check if it's a case
    if document.document_type not in ['case', 'case_study']:
        flash('The requested document is not a case', 'warning')
        return redirect(url_for('cases.list_cases'))
    
    # Get form data
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate required fields
    if not title:
        flash('Title is required', 'danger')
        return redirect(url_for('cases.edit_case_form', id=id))
    
    if not description:
        flash('Description is required', 'danger')
        return redirect(url_for('cases.edit_case_form', id=id))
    
    # Update document
    document.title = title
    document.content = description
    
    # Save changes
    try:
        db.session.commit()
        flash('Case details updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating case: {str(e)}', 'danger')
    
    return redirect(url_for('cases.view_case', id=id))

@cases_bp.route('/api/related-cases', methods=['POST'])
def get_related_cases():
    """Get cases related to specified triples."""
    data = request.json
    document_id = data.get('document_id')
    selected_triples = data.get('selected_triples', [])
    
    if not document_id:
        return jsonify({'error': 'Document ID is required'}), 400
    
    try:
        triple_service = EntityTripleService()
        
        # If no triples selected, return empty result
        if not selected_triples:
            return jsonify({'related_cases': []})
        
        # Find cases that match ALL selected triples (intersection)
        matching_cases = triple_service.find_cases_matching_all_triples(document_id, selected_triples)
        
        return jsonify({'related_cases': matching_cases})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Scenario Generation Routes
@cases_bp.route('/<int:case_id>/generate_scenario', methods=['POST'])
@login_required
def generate_scenario_from_case(case_id):
    """Generate a scenario from a case using background processing."""
    try:
        logger.info(f"Starting scenario generation for case {case_id}")
        
        case = Document.query.get_or_404(case_id)
        scenario_service = CaseToScenarioService()
        
        # Check if case can be deconstructed
        can_process, reason = scenario_service.can_deconstruct_case(case)
        logger.info(f"Can deconstruct case {case_id}: {can_process}, reason: {reason}")
        
        if not can_process:
            return jsonify({
                'success': False,
                'error': f'Cannot generate scenario: {reason}'
            }), 400
        
        # Start async processing
        task_id = scenario_service.deconstruct_case_async(case_id)
        logger.info(f"Started async deconstruction for case {case_id} with task_id: {task_id}")
        
        return jsonify({
            'success': True,
            'task_id': task_id,
            'message': 'Scenario generation started'
        })
        
    except Exception as e:
        logger.error(f"Error starting scenario generation for case {case_id}: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/<int:case_id>/scenario_generation_progress', methods=['GET'])
def get_scenario_generation_progress(case_id):
    """Get the progress of scenario generation for a case."""
    try:
        scenario_service = CaseToScenarioService()
        progress = scenario_service.get_deconstruction_progress(case_id)
        
        return jsonify({
            'success': True,
            'progress': progress
        })
        
    except Exception as e:
        logger.error(f"Error getting scenario generation progress for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/<int:case_id>/scenario_status', methods=['GET'])
def get_scenario_status(case_id):
    """Check if a case has been deconstructed and can generate scenarios."""
    try:
        from app.models.deconstructed_case import DeconstructedCase
        from app.models.scenario_template import ScenarioTemplate
        
        case = Document.query.get_or_404(case_id)
        scenario_service = CaseToScenarioService()
        
        # Check if case can be deconstructed
        can_deconstruct, reason = scenario_service.can_deconstruct_case(case)
        
        # Check if case has been deconstructed
        deconstructed = DeconstructedCase.query.filter_by(case_id=case_id).first()
        
        # Check if scenario templates exist
        templates = []
        scenarios = []
        if deconstructed:
            try:
                templates = ScenarioTemplate.query.filter_by(deconstructed_case_id=deconstructed.id).all()
            except Exception as e:
                logger.warning(f"Error querying scenario templates: {str(e)}")
                templates = []
                
            # Find playable scenarios for this case
            try:
                from app.models.scenario import Scenario
                all_scenarios = Scenario.query.filter_by(world_id=case.world_id).all()
                for scenario in all_scenarios:
                    if scenario.scenario_metadata and scenario.scenario_metadata.get('source_case_id') == case_id:
                        scenarios.append(scenario)
            except Exception as e:
                logger.warning(f"Error querying scenarios: {str(e)}")
                scenarios = []
        
        return jsonify({
            'success': True,
            'can_deconstruct': can_deconstruct,
            'deconstruct_reason': reason,
            'is_deconstructed': deconstructed is not None,
            'deconstructed_case_id': deconstructed.id if deconstructed else None,
            'has_templates': len(templates) > 0,
            'template_count': len(templates),
            'templates': [{'id': t.id, 'title': t.title} for t in templates],
            'has_scenarios': len(scenarios) > 0,
            'scenario_count': len(scenarios),
            'scenarios': [{'id': s.id, 'name': s.name, 'url': f'/scenarios/{s.id}'} for s in scenarios]
        })
        
    except Exception as e:
        logger.error(f"Error getting scenario status for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/<int:case_id>/create_scenario_template', methods=['POST'])
@login_required
def create_scenario_template(case_id):
    """Create a scenario template from a deconstructed case."""
    try:
        from app.models.deconstructed_case import DeconstructedCase
        
        # Get the deconstructed case
        deconstructed = DeconstructedCase.query.filter_by(case_id=case_id).first()
        if not deconstructed:
            return jsonify({
                'success': False,
                'error': 'Case must be deconstructed first'
            }), 400
        
        # Generate scenario template
        generation_service = ScenarioGenerationService()
        template = generation_service.generate_scenario_template(deconstructed)
        
        if not template:
            return jsonify({
                'success': False,
                'error': 'Failed to generate scenario template'
            }), 500
        
        return jsonify({
            'success': True,
            'template_id': template.id,
            'template_title': template.title,
            'message': 'Scenario template created successfully'
        })
        
    except Exception as e:
        logger.error(f"Error creating scenario template for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/templates/<int:template_id>/create_scenario', methods=['POST'])
@login_required
def create_scenario_from_template(template_id):
    """Create a playable scenario from a template."""
    try:
        from app.models.scenario_template import ScenarioTemplate
        
        template = ScenarioTemplate.query.get_or_404(template_id)
        
        # Get customizations from request
        customizations = request.json or {}
        
        # Create scenario instance
        generation_service = ScenarioGenerationService()
        scenario = generation_service.create_scenario_instance(
            template, 
            current_user.id,
            customizations
        )
        
        if not scenario:
            return jsonify({
                'success': False,
                'error': 'Failed to create scenario instance'
            }), 500
        
        return jsonify({
            'success': True,
            'scenario_id': scenario.id,
            'scenario_title': scenario.title,
            'redirect_url': url_for('scenarios.view_scenario', id=scenario.id)
        })
        
    except Exception as e:
        logger.error(f"Error creating scenario from template {template_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/<int:case_id>/direct_scenario', methods=['POST'])
def generate_direct_scenario(case_id):
    """Generate a direct scenario (Phase A pipeline) from case sections without full deconstruction."""
    try:
        case = Document.query.get_or_404(case_id)
        overwrite = (request.args.get('overwrite', 'false').lower() == 'true')
        
        # Handle enhanced generation toggle from JSON body
        enhanced_generation = None
        if request.is_json:
            data = request.get_json()
            if 'enhanced_generation' in data:
                enhanced_generation = data['enhanced_generation'].lower() == 'true'
                overwrite = data.get('overwrite', overwrite)
        
        # Temporarily set environment variable for this request if specified
        original_enhanced_setting = None
        if enhanced_generation is not None:
            import os
            original_enhanced_setting = os.environ.get('ENHANCED_SCENARIO_GENERATION')
            os.environ['ENHANCED_SCENARIO_GENERATION'] = 'true' if enhanced_generation else 'false'
        
        try:
            pipeline = DirectScenarioPipelineService()
            data = pipeline.generate(case, overwrite=overwrite)
        finally:
            # Restore original setting
            if original_enhanced_setting is not None:
                if original_enhanced_setting is None:
                    os.environ.pop('ENHANCED_SCENARIO_GENERATION', None)
                else:
                    os.environ['ENHANCED_SCENARIO_GENERATION'] = original_enhanced_setting

        # Optionally include full events list; default now True for developer inspection.
        include_events = request.args.get('include_events', 'true').lower() != 'false'
        payload = {
            'success': True,
            'case_id': case_id,
            'version_number': data.get('version_number'),
            'stats': data.get('stats'),
            'event_count': data['stats']['event_count'],
            'decision_count': data['stats']['decision_count']
        }
        if include_events:
            # Optionally allow truncated mode if query param trim is provided
            if request.args.get('trim'):
                trimmed = []
                for ev in data['events']:
                    trimmed.append({
                        'id': ev.get('id'),
                        'kind': ev.get('kind'),
                        'section': ev.get('section'),
                        'text': (ev.get('text','')[:160] + ('…' if len(ev.get('text',''))>160 else '')),
                        'options': ev.get('options') and [o.get('label') for o in ev['options']],
                        'refined': ev.get('refined')
                    })
                payload['events'] = trimmed
                payload['trimmed'] = True
            else:
                payload['events'] = data['events']
        return jsonify(payload)
    except Exception as e:
        logger.error(f"Direct scenario generation failed for case {case_id}: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@cases_bp.route('/<int:case_id>/scenario_interim', methods=['GET'])
def view_interim_scenario(case_id):
    """Interim scenario view: shows direct scenario timeline with ontology summary and participants.

    This is a read-only visualization layer over latest_scenario produced by the Phase A pipeline.
    """
    try:
        case = Document.query.get_or_404(case_id)
        latest = None
        if case.doc_metadata and isinstance(case.doc_metadata, dict):
            latest = case.doc_metadata.get('latest_scenario')
        if not latest:
            flash('No direct scenario generated yet. Click Regenerate on case page first.', 'warning')
            return redirect(url_for('cases.view_case', case_id=case_id))
        return render_template('scenario_interim.html', case=case, scenario=latest)
    except Exception as e:
        logger.error(f"Error loading interim scenario for case {case_id}: {e}")
        flash(f"Error loading interim scenario: {e}", 'danger')
        return redirect(url_for('cases.view_case', case_id=case_id))


@cases_bp.route('/new/agent', methods=['GET'])
@login_required
def agent_assisted_creation():
    """Display agent-assisted case creation interface with ontology integration."""
    try:
        # Get current user and available worlds
        from app.models.world import World
        worlds = World.query.all()
        # current_user is now directly available from flask_login
        
        # Get default world (first available world)
        default_world = worlds[0] if worlds else None
        
        # Initialize case creation agent
        case_agent = CaseCreationAgent(world_id=default_world.id if default_world else None)
        
        # Get ontology categories from the service
        ontology_categories = []
        if default_world:
            entities = case_agent.ontology_service.get_entities_for_world(default_world)
            for category_name, concepts in entities.get("entities", {}).items():
                ontology_categories.append({
                    "name": category_name,
                    "count": len(concepts),
                    "concepts": concepts[:5]  # Show first 5 as preview
                })
        
        # Fallback categories if no world available
        if not ontology_categories:
            fallback_categories = ["Role", "Principle", "Obligation", "State", "Resource", "Action", "Event", "Capability"]
            ontology_categories = [{"name": cat, "count": 0, "concepts": []} for cat in fallback_categories]
        
        return render_template('agent_case_creation.html', 
                             worlds=worlds,
                             ontology_categories=ontology_categories,
                             default_world=default_world,
                             current_user=current_user)
                             
    except Exception as e:
        logger.error(f"Error loading agent case creation interface: {e}")
        flash(f"Error loading AI assistant: {str(e)}", 'error')
        return redirect(url_for('cases.case_options'))


@cases_bp.route('/new/agent/api', methods=['POST'])
@login_required
def agent_creation_api():
    """API endpoint for agent interactions with ontology integration."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No data provided'
            }), 400
        
        # Get parameters
        prompt = data.get('prompt', '')
        world_id = data.get('world_id')
        selected_categories = data.get('selected_categories', [])
        selected_concepts = data.get('selected_concepts', {})
        conversation_history = data.get('conversation_history', [])
        
        if not prompt:
            return jsonify({
                'success': False,
                'error': 'No prompt provided'
            }), 400
        
        # Initialize case creation agent
        case_agent = CaseCreationAgent(world_id=world_id)
        case_agent.set_selected_categories(selected_categories)
        case_agent.set_selected_concepts(selected_concepts)
        
        # Prepare scenario data
        scenario_data = {
            'world_id': world_id,
            'conversation_history': conversation_history,
            'request_type': 'case_creation'
        }
        
        # Get analysis from agent
        analysis = case_agent.analyze(
            scenario_data=scenario_data,
            decision_text=prompt,
            options=[],  # No predefined options for case creation
            previous_results=None
        )
        
        # Format response for UI
        formatted_response = case_agent.format_response_for_ui(analysis)
        
        return jsonify({
            'success': True,
            'response': formatted_response
        })
        
    except Exception as e:
        logger.error(f"Error in agent creation API: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/new/agent/concepts/<category>', methods=['GET'])
@login_required 
def get_category_concepts(category):
    """Get concepts for a specific ontological category."""
    try:
        world_id = request.args.get('world_id', type=int)
        
        if not world_id:
            return jsonify({
                'success': False,
                'error': 'World ID required'
            }), 400
        
        # Initialize case creation agent
        case_agent = CaseCreationAgent(world_id=world_id)
        
        # Get concepts for the category
        concepts = case_agent.get_category_concepts(category, world_id)
        
        return jsonify({
            'success': True,
            'category': category,
            'concepts': concepts
        })
        
    except Exception as e:
        logger.error(f"Error getting concepts for category {category}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@cases_bp.route('/new/agent/generate', methods=['POST'])
@login_required
def generate_case_from_conversation():
    """Generate NSPE-format case from agent conversation."""
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({
                'success': False,
                'error': 'No conversation data provided'
            }), 400
        
        # Get conversation data
        world_id = data.get('world_id')
        conversation_history = data.get('conversation_history', [])
        selected_concepts = data.get('selected_concepts', {})
        conversation_metadata = data.get('conversation_metadata', {})
        
        if not conversation_history:
            return jsonify({
                'success': False,
                'error': 'No conversation history provided'
            }), 400
        
        # Get current user
        # current_user is now directly available from flask_login
        
        # Create AgentConversation record
        import uuid
        session_id = str(uuid.uuid4())
        
        conversation = AgentConversation(
            session_id=session_id,
            user_id=current_user.username if current_user else None,
            world_id=world_id,
            title="Language Model-Assisted Case Creation",
            metadata=conversation_metadata
        )
        
        # Add messages to conversation
        for msg in conversation_history:
            conversation.add_message(
                content=msg.get('content', ''),
                role=msg.get('type', 'user'),  # Convert 'type' to 'role'
                metadata=msg.get('metadata', {})
            )
        
        # Add ontology selections
        for category, concepts in selected_concepts.items():
            if concepts:
                conversation.update_ontology_selections(category, concepts)
        
        # Save conversation
        db.session.add(conversation)
        db.session.flush()  # Get ID
        
        # Generate case using the conversation
        case_service = ConversationToCaseService()
        generated_case = case_service.generate_case_from_conversation(conversation)
        
        if not generated_case:
            return jsonify({
                'success': False,
                'error': 'Failed to generate case from conversation'
            }), 500
        
        # Return success with case details
        return jsonify({
            'success': True,
            'case_id': generated_case.id,
            'case_title': generated_case.title,
            'case_url': url_for('cases.view_case', id=generated_case.id),
            'conversation_id': conversation.id,
            'message': 'Case generated successfully from conversation'
        })
        
    except Exception as e:
        logger.error(f"Error generating case from conversation: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
