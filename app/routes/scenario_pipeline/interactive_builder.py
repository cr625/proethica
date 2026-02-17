"""
Interactive Scenario Builder Routes

Step-by-step scenario creation routes that provide an interactive workflow
for building scenarios from cases.
"""

import logging
from flask import Blueprint, render_template, redirect, url_for, flash
from app.models import Document
from app.utils.environment_auth import (
    auth_optional,
    auth_required_for_write,
    auth_required_for_llm
)

logger = logging.getLogger(__name__)

# Create the blueprint
interactive_scenario_bp = Blueprint('scenario_pipeline', __name__, url_prefix='/scenario_pipeline')

def init_csrf_exemption(app):
    """Exempt API endpoints from CSRF protection (they use JSON, not form submission)"""
    if hasattr(app, 'csrf') and app.csrf:
        # Exempt the tag entity routes
        app.csrf.exempt(tag_entities_in_questions_route)
        app.csrf.exempt(tag_entities_in_conclusions_route)
        # Exempt code provision extraction
        app.csrf.exempt(extract_code_provisions_route)
        # Exempt streaming extraction endpoints
        app.csrf.exempt(entities_pass_execute_streaming)
        app.csrf.exempt(normative_pass_execute_streaming)

@interactive_scenario_bp.route('/case/<int:case_id>')
@auth_optional
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

@interactive_scenario_bp.route('/case/<int:case_id>/overview')
@auth_optional  # Allow viewing without auth
def overview(case_id):
    """Route handler for Case Overview"""
    from .overview import step1 as overview_handler
    return overview_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1')
@auth_optional  # Allow viewing without auth
def step1(case_id):
    """Route handler for Step 1: Entities Pass (Roles + Resources) on Facts Section"""
    from .step1 import step1 as step1_handler
    return step1_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1b')
@auth_optional  # Allow viewing without auth
def step1b(case_id):
    """Route handler for Step 1b: Contextual Framework Pass (Discussion Section)"""
    from .step1 import step1b as step1b_handler
    return step1b_handler(case_id)

# DEPRECATED: Questions, Conclusions, and References moved to Step 4 Whole-Case Synthesis
# These routes are commented out but preserved for reference
#
# @interactive_scenario_bp.route('/case/<int:case_id>/step1c')
# @auth_optional  # Allow viewing without auth
# def step1c(case_id):
#     """Route handler for Step 1c: Contextual Framework Pass (Questions Section)"""
#     from .step1 import step1c as step1c_handler
#     return step1c_handler(case_id)
#
# @interactive_scenario_bp.route('/case/<int:case_id>/step1d')
# @auth_optional  # Allow viewing without auth
# def step1d(case_id):
#     """Route handler for Step 1d: Contextual Framework Pass (Conclusions Section)"""
#     from .step1 import step1d as step1d_handler
#     return step1d_handler(case_id)
#
# @interactive_scenario_bp.route('/case/<int:case_id>/step1e')
# @auth_optional  # Allow viewing without auth
# def step1e(case_id):
#     """Route handler for Step 1e: NSPE Code of Ethics References"""
#     from .step1 import step1e as step1e_handler
#     return step1e_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1_streaming')
def step1_streaming(case_id):
    """Route handler for Step 1: Enhanced version with streaming updates"""
    from .step1 import step1_data
    from flask import render_template
    # Get the same data as regular step1
    case_doc, facts_section, discussion_section, saved_prompts = step1_data(case_id)
    # Render the streaming template
    return render_template('scenarios/step1_streaming.html',
                         case=case_doc,
                         facts_section=facts_section,
                         discussion_section=discussion_section,
                         saved_prompts=saved_prompts)

@interactive_scenario_bp.route('/case/<int:case_id>/debug')
def debug_overview_route(case_id):
    """Debug route for overview processing"""
    from .overview import debug_step1 as debug_handler
    return debug_handler(case_id)

# Step 1a route for LangExtract analysis - DISABLED (placeholder)
# @interactive_scenario_bp.route('/case/<int:case_id>/step1a')
# def step1a_route(case_id):
#     """Step 1a: LangExtract Content Analysis"""
#     from app.routes.scenario_pipeline.step1a_langextract import step1a
#     return step1a(case_id)

# @interactive_scenario_bp.route('/case/<int:case_id>/step1a/analyze', methods=['POST'])
# def step1a_analyze(case_id):
#     """API endpoint for LangExtract section analysis in step1a"""
#     from app.routes.scenario_pipeline.step1a_langextract import analyze_section_langextract
#     return analyze_section_langextract(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/entities_pass_prompt', methods=['POST'])
def entities_pass_prompt(case_id):
    """API endpoint to generate entities pass prompt"""
    from .step1 import entities_pass_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/entities_pass_execute', methods=['POST'])
@auth_required_for_llm
def entities_pass_execute(case_id):
    """API endpoint to execute entities pass extraction"""
    from .step1 import entities_pass_execute as execute_handler
    return execute_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/entities_pass_execute_streaming', methods=['POST'])
@auth_required_for_llm
def entities_pass_execute_streaming(case_id):
    """API endpoint to execute entities pass extraction with streaming updates"""
    from .step1_enhanced import entities_pass_execute_streaming as streaming_handler
    return streaming_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/entities_pass_prompt_discussion', methods=['POST'])
def entities_pass_prompt_discussion(case_id):
    """API endpoint to generate entities pass prompt for Discussion section"""
    from .step1 import entities_pass_prompt_discussion as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/entities_pass_execute_discussion', methods=['POST'])
@auth_required_for_llm
def entities_pass_execute_discussion(case_id):
    """API endpoint to execute entities pass extraction for Discussion section"""
    from .step1 import entities_pass_execute_discussion as execute_handler
    return execute_handler(case_id)

# NOTE: extract_questions route removed - now handled by step4.py with streaming support
# The step4.py version auto-loads question text from case metadata
# @interactive_scenario_bp.route('/case/<int:case_id>/extract_questions', methods=['POST'])
# def extract_questions_route(case_id):
#     from .step1 import extract_questions
#     return extract_questions(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/tag_entities_in_questions', methods=['POST'])
@auth_required_for_llm
def tag_entities_in_questions_route(case_id):
    """API endpoint to tag entities from Facts/Discussion in Questions section"""
    from .step1 import tag_entities_in_questions
    return tag_entities_in_questions(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/tag_entities_in_conclusions', methods=['POST'])
@auth_required_for_llm
def tag_entities_in_conclusions_route(case_id):
    """API endpoint to tag entities from Facts/Discussion/Questions in Conclusions section"""
    from .step1 import tag_entities_in_conclusions
    return tag_entities_in_conclusions(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/link_questions_conclusions', methods=['POST'])
@auth_required_for_llm  # Requires LLM for verification
def link_questions_conclusions_route(case_id):
    """API endpoint to create Question→Conclusion relationship mappings"""
    from .step1 import link_questions_to_conclusions
    return link_questions_to_conclusions(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/extract_code_provisions', methods=['POST'])
@auth_required_for_llm  # Requires LLM for entity linking
def extract_code_provisions_route(case_id):
    """API endpoint to extract and link NSPE code provisions"""
    from .step1 import extract_code_provisions
    return extract_code_provisions(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2')
@auth_optional  # Allow viewing without auth
def step2(case_id):
    """Route handler for Step 2: Normative Pass (Principles + Obligations + Constraints) on Facts Section"""
    from .step2 import step2 as step2_handler
    return step2_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2b')
@auth_optional
def step2b(case_id):
    """Route handler for Step 2b: Normative Pass on Discussion Section"""
    from .step2 import step2b as step2b_handler
    return step2b_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2c')
@auth_optional
def step2c(case_id):
    """Route handler for Step 2c: Normative Pass on Questions Section"""
    from .step2 import step2c as step2c_handler
    return step2c_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2d')
@auth_optional
def step2d(case_id):
    """Route handler for Step 2d: Normative Pass on Conclusions Section"""
    from .step2 import step2d as step2d_handler
    return step2d_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2e')
@auth_optional
def step2e(case_id):
    """Route handler for Step 2e: Normative Pass on References Section"""
    from .step2 import step2e as step2e_handler
    return step2e_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/normative_pass_prompt', methods=['POST'])
def normative_pass_prompt(case_id):
    """API endpoint to generate normative pass prompt"""
    from .step2 import normative_pass_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/normative_pass_execute', methods=['POST'])
@auth_required_for_llm
def normative_pass_execute(case_id):
    """API endpoint to execute normative pass extraction"""
    from .step2 import normative_pass_execute as execute_handler
    return execute_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2/extract', methods=['POST'])
@auth_required_for_llm
def step2_extract(case_id):
    """API endpoint for Step 2 extraction (alias for normative_pass_execute)"""
    from .step2 import normative_pass_execute as execute_handler
    return execute_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1/extract_individual', methods=['POST'])
@auth_required_for_llm
def step1_extract_individual(case_id):
    """API endpoint for individual concept extraction in Step 1"""
    from .step1 import extract_individual_concept as individual_handler
    return individual_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step1/get_saved_prompt', methods=['GET'])
def step1_get_saved_prompt(case_id):
    """API endpoint to get saved extraction prompt for Step 1"""
    from .step1 import get_saved_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2/extract_individual', methods=['POST'])
@auth_required_for_llm
def step2_extract_individual(case_id):
    """API endpoint for individual concept extraction in Step 2"""
    from .step2 import extract_individual_concept as individual_handler
    return individual_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2/get_saved_prompt', methods=['GET'])
def step2_get_saved_prompt(case_id):
    """API endpoint to get saved extraction prompt for Step 2"""
    from .step2 import get_saved_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2/clear_prompt', methods=['POST'])
def step2_clear_prompt(case_id):
    """API endpoint to clear saved extraction prompt for Step 2"""
    from .step2 import clear_saved_prompt as clear_handler
    return clear_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step2_streaming')
def step2_streaming(case_id):
    """Route handler for Step 2: Enhanced version with streaming updates"""
    from .step2 import step2_data
    from flask import render_template
    # Get the same data as regular step2
    case_doc, facts_section, saved_prompts = step2_data(case_id)
    # Render the streaming template
    return render_template('scenarios/step2_streaming.html',
                         case=case_doc,
                         discussion_section=facts_section,  # Keep name for template compatibility
                         saved_prompts=saved_prompts)

@interactive_scenario_bp.route('/case/<int:case_id>/normative_pass_execute_streaming', methods=['POST'])
@auth_required_for_llm
def normative_pass_execute_streaming(case_id):
    """API endpoint to execute normative pass extraction with streaming updates"""
    from .step2_enhanced import normative_pass_execute_streaming as streaming_handler
    return streaming_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step3')
@auth_optional  # Allow viewing without auth
def step3(case_id):
    """Route handler for Step 3: Behavioral Pass (States + Actions + Events + Capabilities) on Facts Section"""
    from .step3 import step3 as step3_handler
    return step3_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/behavioral_pass_prompt', methods=['POST'])
def behavioral_pass_prompt(case_id):
    """API endpoint to generate behavioral pass prompt"""
    from .step3 import behavioral_pass_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/behavioral_pass_execute', methods=['POST'])
@auth_required_for_llm
def behavioral_pass_execute(case_id):
    """API endpoint to execute behavioral pass extraction"""
    from .step3 import behavioral_pass_execute as execute_handler
    return execute_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step3/extract', methods=['POST'])
@auth_required_for_llm
def step3_extract(case_id):
    """API endpoint for Step 3 extraction using dual extractor that saves to database"""
    from .step3 import extract_individual_actions_events as execute_handler
    return execute_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step3/extract_enhanced', methods=['GET'])
@auth_required_for_llm
def step3_extract_enhanced(case_id):
    """API endpoint for enhanced temporal dynamics extraction with LangGraph streaming (SSE uses GET)"""
    from .step3_enhanced import extract_enhanced_temporal_dynamics
    return extract_enhanced_temporal_dynamics(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step3/extract_individual', methods=['POST'])
@auth_required_for_llm
def step3_extract_individual(case_id):
    """API endpoint for individual actions & events extraction in Step 3"""
    from .step3 import extract_individual_actions_events as individual_handler
    return individual_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/step3/get_saved_prompt', methods=['GET'])
def step3_get_saved_prompt(case_id):
    """API endpoint to get saved extraction prompt for Step 3"""
    from .step3 import step3_get_saved_prompt as prompt_handler
    return prompt_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/complete')
def complete_analysis(case_id):
    """Route handler for Complete Analysis: Modular Pipeline for All Case Elements"""
    from .complete_analysis import complete_analysis as complete_handler
    return complete_handler(case_id)

@interactive_scenario_bp.route('/case/<int:case_id>/complete_analysis_execute', methods=['POST'])
def execute_complete_analysis(case_id):
    """API endpoint to execute complete modular analysis"""
    from .complete_analysis import execute_complete_analysis as execute_handler
    return execute_handler(case_id)

# LangExtract routes (archived - DISABLED)
# @interactive_scenario_bp.route('/case/<int:case_id>/langextract_analysis', methods=['POST'])
# def langextract_analysis_archived(case_id):
#     """API endpoint for LangExtract section analysis (archived)"""
#     from .step1a_langextract import analyze_section_langextract as analysis_handler
#     return analysis_handler(case_id)

# @interactive_scenario_bp.route('/langextract_status')
# def langextract_status():
#     """API endpoint to get LangExtract service status (archived)"""
#     from .step1a_langextract import get_langextract_status as status_handler
#     return status_handler()
