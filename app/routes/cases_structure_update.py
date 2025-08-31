"""
DEPRECATED: This module has been consolidated into the main cases.py route.

The document structure annotation functionality has been merged into the main
case processing pipeline at /cases/process/url.

This file is kept for reference but is no longer registered as a blueprint.
See app/routes/cases.py for the current implementation.

Original description:
Updated routes for case management with document structure annotation.
This file provides the implementation of the enhanced pipeline with document structure annotation.
"""
import logging
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from flask_login import current_user
from app.models import Document, PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app import db
from app.services.entity_triple_service import EntityTripleService
from app.services.case_processing.pipeline_manager import PipelineManager
from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint for structure-enhanced case routes
cases_structure_bp = Blueprint('cases_structure', __name__, url_prefix='/cases_enhanced')

@cases_structure_bp.route('/process/url', methods=['GET', 'POST'])
def process_url_pipeline_enhanced():
    """Process a URL with enhanced pipeline including document structure annotation."""
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
    
    # Initialize pipeline with document structure annotation step
    pipeline = PipelineManager()
    pipeline.register_step('url_retrieval', URLRetrievalStep())
    pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())
    pipeline.register_step('document_structure', DocumentStructureAnnotationStep())
    
    # Determine which steps to run based on process_extraction
    # Always include URL retrieval, only add extraction and structure if requested
    steps_to_run = ['url_retrieval']
    if process_extraction:
        steps_to_run.extend(['nspe_extraction', 'document_structure'])
    
    # Run pipeline
    logger.info(f"Running enhanced pipeline for URL: {url} with steps: {', '.join(steps_to_run)}")
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
        pdf_url = final_result.get('pdf_url', '')
        facts = final_result.get('sections', {}).get('facts', '')
        question_html = final_result.get('sections', {}).get('question', '')
        references = final_result.get('sections', {}).get('references', '')
        discussion = final_result.get('sections', {}).get('discussion', '')
        conclusion = final_result.get('sections', {}).get('conclusion', '')
        
        # Get structured list data
        questions_list = final_result.get('questions_list', [])
        conclusion_items = final_result.get('conclusion_items', [])
            
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
        
        # Store original sections in metadata for future reference
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
            'extraction_method': 'direct_process',
            'display_format': 'extraction_style'  # Flag to indicate special display format
        }
        
        # Add document structure information if available
        if 'document_structure' in final_result:
            # Add document URI
            metadata['document_uri'] = final_result['document_structure'].get('document_uri')
            
            # Add structure triples as serialized string
            metadata['structure_triples'] = final_result['document_structure'].get('structure_triples')
            
            # Add annotation timestamp
            from datetime import datetime
            metadata['structure_annotation_timestamp'] = datetime.utcnow().isoformat()
            
            logger.info(f"Added document structure information with URI: {metadata['document_uri']}")
        
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
        
        # Log success with document ID and structure information
        logger.info(f"Case saved successfully with ID: {document.id}, includes document structure: {'document_structure' in final_result}")
        
        # Redirect to view the case
        flash('Case extracted and saved successfully with document structure annotation', 'success')
        return redirect(url_for('cases.view_case', id=document.id))
    
    # Otherwise, just show the raw content
    return render_template('raw_url_content.html',
                          url=final_result.get('url'),
                          content=final_result.get('content'),
                          content_type=final_result.get('content_type'),
                          content_length=final_result.get('content_length'),
                          status_code=final_result.get('status_code'),
                          encoding=final_result.get('encoding'))
