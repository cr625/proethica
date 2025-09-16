"""
Step 1a: LangExtract Content Analysis Route

Enhanced content analysis step using LangExtract integration for structured 
document analysis. Shows LLM-optimized text with detailed LangExtract analysis.
"""

import logging
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document
from app.routes.scenario_pipeline.step1 import _format_section_for_llm
from app.services.ontology_driven_langextract_service import OntologyDrivenLangExtractService
from app.services.proethica_langextract_service import ProEthicaLangExtractService
from app.services.database_langextract_service import DatabaseLangExtractService
import os

logger = logging.getLogger(__name__)

# Initialize LangExtract service based on configuration
use_database_examples = os.environ.get('USE_DATABASE_LANGEXTRACT_EXAMPLES', 'true').lower() == 'true'
use_ontology_driven = os.environ.get('ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT', 'true').lower() == 'true'

if use_database_examples and use_ontology_driven:
    logger.info("Using DatabaseLangExtractService with database examples")
    langextract_service = DatabaseLangExtractService()
elif use_ontology_driven:
    logger.info("Using OntologyDrivenLangExtractService with hardcoded examples")
    langextract_service = OntologyDrivenLangExtractService()
else:
    logger.info("Using ProEthicaLangExtractService (basic)")
    langextract_service = ProEthicaLangExtractService()

# Function to exempt specific routes from CSRF after app initialization
def init_step1a_csrf_exemption(app):
    """Exempt Step 1a LangExtract analysis routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route function that actually gets called
        from app.routes.scenario_pipeline.interactive_builder import step1a_analyze
        # Exempt the LangExtract analysis route from CSRF protection
        app.csrf.exempt(step1a_analyze)

def step1a(case_id):
    """
    Step 1a: LangExtract Content Analysis
    Shows LLM-optimized content with LangExtract analysis capabilities
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections using the same logic as step1
        raw_sections = {}
        if case.doc_metadata:
            # Priority 1: sections_dual (contains formatted HTML with enumerated lists)
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            # Priority 2: sections (basic sections)
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            # Priority 3: document_structure sections
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']
        
        # If no sections found, create basic structure
        if not raw_sections:
            raw_sections = {
                'full_content': case.content or 'No content available'
            }
        
        # Process sections for LLM-optimal display (reuse step1 formatting)
        sections = {}
        for section_key, section_content in raw_sections.items():
            formatted_section = _format_section_for_llm(section_key, section_content)
            if formatted_section:
                sections[section_key] = formatted_section
        
        # Get LangExtract service status
        service_status = langextract_service.get_service_status()
        
        # Template context
        context = {
            'case': case,
            'sections': sections,
            'current_step': '1a',
            'step_title': 'LangExtract Content Analysis',
            'langextract_status': service_status,
            'next_step_url': '#',  # Future: step1b or step2
            'prev_step_url': url_for('scenario_pipeline.step1', case_id=case_id)
        }
        
        return render_template('scenarios/step1a.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 1a for case {case_id}: {str(e)}")
        flash(f'Error loading step 1a: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def analyze_section_langextract(case_id):
    """
    API endpoint to perform LangExtract analysis on a specific section
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_key = data.get('section_key')
        section_text = data.get('section_text')
        
        if not section_key or not section_text:
            return jsonify({'error': 'section_key and section_text are required'}), 400
        
        logger.info(f"Starting LangExtract analysis for case {case_id}, section: {section_key}")
        
        # Perform ontology-driven LangExtract analysis
        # Determine case domain from case metadata or default to engineering_ethics
        case_domain = 'engineering_ethics'  # Default for NSPE cases
        
        # Get the case to check for domain information
        case = Document.query.get(case_id)
        if case and case.doc_metadata and 'domain' in case.doc_metadata:
            case_domain = case.doc_metadata['domain']
        
        analysis_result = langextract_service.analyze_section_content(
            section_title=section_key,
            section_text=section_text,
            case_id=case_id,
            case_domain=case_domain
        )
        
        # Add request metadata
        analysis_result['request_metadata'] = {
            'case_id': case_id,
            'section_key': section_key,
            'text_length': len(section_text),
            'analysis_requested_at': analysis_result.get('analysis_timestamp')
        }
        
        # Add formatted JSON for structured_analysis if it exists
        if 'structured_analysis' in analysis_result:
            import json
            analysis_result['formatted_structured_analysis'] = json.dumps(
                analysis_result['structured_analysis'], 
                indent=2, 
                ensure_ascii=False
            )
        
        logger.info(f"LangExtract analysis completed for case {case_id}, section: {section_key}")
        
        return jsonify(analysis_result)
        
    except Exception as e:
        logger.error(f"Error in LangExtract analysis for case {case_id}: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'fallback_available': True
        }), 500

def get_langextract_status():
    """
    API endpoint to get LangExtract service status
    """
    try:
        status = langextract_service.get_service_status()
        return jsonify(status)
    except Exception as e:
        logger.error(f"Error getting LangExtract status: {str(e)}")
        return jsonify({
            'error': str(e),
            'integration_status': 'error'
        }), 500