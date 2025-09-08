"""
Interactive Scenario Builder Routes

Step-by-step scenario creation routes that provide an interactive workflow
for building scenarios from cases.
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash
from app.models import Document

logger = logging.getLogger(__name__)

# Create the blueprint
interactive_scenario_bp = Blueprint('scenario_pipeline', __name__, url_prefix='/scenario_pipeline')

@interactive_scenario_bp.route('/case/<int:case_id>')
def scenario_pipeline_builder(case_id):
    """
    Interactive scenario pipeline builder starting page.
    Shows case content divided by sections with navigation tooling.
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections from case metadata
        sections = {}
        if case.doc_metadata:
            # Get sections from different possible locations in metadata
            if 'sections' in case.doc_metadata:
                sections = case.doc_metadata['sections']
            elif 'sections_dual' in case.doc_metadata:
                sections = case.doc_metadata['sections_dual']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                sections = case.doc_metadata['document_structure']['sections']
        
        # If no sections found, create a basic structure with the full content
        if not sections:
            sections = {
                'full_content': {
                    'title': 'Full Case Content',
                    'content': case.content or case.description or 'No content available',
                    'html': case.content or case.description or 'No content available'
                }
            }
        
        return render_template('scenario_pipeline/builder.html', 
                             case=case, 
                             sections=sections)
        
    except Exception as e:
        logger.error(f"Error loading scenario pipeline for case {case_id}: {str(e)}")
        flash(f'Error loading scenario pipeline: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

@interactive_scenario_bp.route('/case/<int:case_id>/step1')
def step1(case_id):
    """Route handler for Step 1: Content Review"""
    from .step1 import step1 as step1_handler
    return step1_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/debug')
def debug_step1_route(case_id):
    """Debug route for Step 1 processing"""
    from .step1 import debug_step1 as debug_handler
    return debug_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1a')
def step1a(case_id):
    """Route handler for Step 1a: LangExtract Content Analysis"""
    from .step1a import step1a as step1a_handler
    return step1a_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/langextract_analysis', methods=['POST'])
def langextract_analysis(case_id):
    """API endpoint for LangExtract section analysis"""
    from .step1a import analyze_section_langextract as analysis_handler
    return analysis_handler(case_id)

@interactive_scenario_bp.route('/langextract_status')
def langextract_status():
    """API endpoint to get LangExtract service status"""
    from .step1a import get_langextract_status as status_handler
    return status_handler()