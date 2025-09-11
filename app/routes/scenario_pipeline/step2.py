"""
Step 2: Normative Pass for Discussion/Analysis Section
Shows the discussion/analysis section and provides a normative pass button that extracts principles, obligations, and constraints.
"""

import logging
import json
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document
from app.routes.scenario_pipeline.step1 import _format_section_for_llm
from app.services.extraction.enhanced_prompts_principles import EnhancedPrinciplesExtractor, create_enhanced_principles_prompt
from app.services.extraction.provenance_service import ProvenanceService
from app.utils.llm_utils import get_llm_client

logger = logging.getLogger(__name__)

# Function to exempt specific routes from CSRF after app initialization
def init_step2_csrf_exemption(app):
    """Exempt Step 2 normative pass routes from CSRF protection"""
    if hasattr(app, 'csrf') and app.csrf:
        # Import the route functions that actually get called
        from app.routes.scenario_pipeline.interactive_builder import normative_pass_prompt, normative_pass_execute
        # Exempt the normative pass routes from CSRF protection
        app.csrf.exempt(normative_pass_prompt)
        app.csrf.exempt(normative_pass_execute)

def step2(case_id):
    """
    Step 2: Normative Pass for Discussion/Analysis Section
    Shows the discussion/analysis section with a normative pass button for extracting principles, obligations, and constraints.
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
        
        # Find the discussion/analysis section
        discussion_section = None
        discussion_section_key = None
        
        # Look for discussion/analysis section (case insensitive)
        # Check for various naming patterns: discussion, analysis, dissenting opinion, etc.
        discussion_keywords = ['discussion', 'analysis', 'dissenting', 'opinion', 'argument', 'reasoning']
        
        for section_key, section_content in raw_sections.items():
            section_key_lower = section_key.lower()
            if any(keyword in section_key_lower for keyword in discussion_keywords):
                discussion_section_key = section_key
                discussion_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break
        
        # If no discussion section found, try to find a section that's not facts or conclusion
        if not discussion_section:
            # Skip facts and conclusion sections
            skip_keywords = ['fact', 'conclusion', 'summary', 'reference']
            for section_key, section_content in raw_sections.items():
                section_key_lower = section_key.lower()
                if not any(keyword in section_key_lower for keyword in skip_keywords):
                    discussion_section_key = section_key
                    discussion_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                    break
        
        # If still no discussion section found, use second available section as fallback
        if not discussion_section and len(raw_sections) > 1:
            keys = list(raw_sections.keys())
            # Try to use second section if available
            second_key = keys[1] if len(keys) > 1 else keys[0]
            discussion_section_key = second_key
            discussion_section = _format_section_for_llm(second_key, raw_sections[second_key], case_doc=case)
        
        # Template context
        context = {
            'case': case,
            'discussion_section': discussion_section,
            'discussion_section_key': discussion_section_key,
            'current_step': 2,
            'step_title': 'Normative Pass - Discussion/Analysis Section',
            'next_step_url': '#',  # Future: step3
            'prev_step_url': url_for('scenario_pipeline.step1a', case_id=case_id)
        }
        
        return render_template('scenarios/step2.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading step 2 for case {case_id}: {str(e)}")
        flash(f'Error loading step 2: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def normative_pass_prompt(case_id):
    """
    API endpoint to generate and return the LLM prompt for normative pass before execution.
    This will extract principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        
        logger.info(f"Generating normative pass prompt for case {case_id}")
        
        # Use enhanced principles prompt from Chapter 2 literature
        principles_prompt = create_enhanced_principles_prompt(section_text, include_ontology_context=True)

        obligations_prompt = f"""Extract professional obligations and duties from the following discussion/analysis text.

Focus on:
- Mandatory professional duties
- Role-specific obligations
- Legal vs ethical obligations
- Obligation conflicts and prioritization

Text:
{section_text[:500]}...

Return as JSON array of obligation objects."""

        constraints_prompt = f"""Extract constraints and limitations from the following discussion/analysis text.

Focus on:
- Legal limitations
- Resource constraints
- Technical/physical limitations
- Ethical boundaries
- Temporal constraints

Text:
{section_text[:500]}...

Return as JSON array of constraint objects."""
        
        return jsonify({
            'success': True,
            'principles_prompt': principles_prompt,
            'obligations_prompt': obligations_prompt,
            'constraints_prompt': constraints_prompt,
            'section_length': len(section_text)
        })
        
    except Exception as e:
        logger.error(f"Error generating normative pass prompt for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500

def normative_pass_execute(case_id):
    """
    API endpoint to execute the normative pass extraction.
    This will run the actual LLM extraction for principles, obligations, and constraints.
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        section_text = data.get('section_text')
        if not section_text:
            return jsonify({'error': 'section_text is required'}), 400
        
        logger.info(f"Executing normative pass for case {case_id}")
        
        # Initialize enhanced extractors with LLM client
        try:
            llm_client = get_llm_client()
        except Exception as e:
            logger.warning(f"Could not initialize LLM client: {str(e)}")
            llm_client = None
        
        # Initialize provenance service
        provenance_service = ProvenanceService()
        
        # Extract principles using enhanced extractor
        principles_extractor = EnhancedPrinciplesExtractor(
            llm_client=llm_client,
            provenance_service=provenance_service
        )
        
        # Create context for extraction
        case = Document.query.get(case_id)
        context = {
            'case_id': case_id,
            'case_title': case.title if case else None,
            'document_type': 'ethics_case'
        }
        
        # Extract principles
        principle_candidates = principles_extractor.extract(section_text, context=context)
        
        # Convert candidates to response format
        principles = []
        for candidate in principle_candidates:
            principle_data = {
                "label": candidate.label,
                "description": candidate.description or "",
                "type": "principle",
                "principle_category": candidate.debug.get('principle_category', 'professional'),
                "abstraction_level": candidate.debug.get('abstraction_level', 'high'),
                "requires_interpretation": candidate.debug.get('requires_interpretation', True),
                "potential_conflicts": candidate.debug.get('potential_conflicts', []),
                "extensional_examples": candidate.debug.get('extensional_examples', []),
                "derived_obligations": candidate.debug.get('derived_obligations', []),
                "scholarly_grounding": candidate.debug.get('scholarly_grounding', ''),
                "confidence": candidate.confidence
            }
            principles.append(principle_data)
        
        obligations = [
            {
                "label": "Competent Practice Obligation",
                "description": "Duty to practice only within areas of competence",
                "type": "obligation",
                "obligation_type": "professional_duty",
                "enforcement": "mandatory",
                "confidence": 0.94
            },
            {
                "label": "Disclosure Duty",
                "description": "Obligation to disclose conflicts of interest",
                "type": "obligation",
                "obligation_type": "ethical_duty",
                "enforcement": "mandatory",
                "confidence": 0.91
            }
        ]
        
        constraints = [
            {
                "label": "Budget Limitation",
                "description": "Fixed budget constraining design options",
                "type": "constraint",
                "constraint_category": "resource",
                "flexibility": "non-negotiable",
                "confidence": 0.88
            },
            {
                "label": "Regulatory Compliance",
                "description": "Must comply with local building codes and regulations",
                "type": "constraint",
                "constraint_category": "legal",
                "flexibility": "non-negotiable",
                "confidence": 0.96
            }
        ]
        
        # Summary statistics
        summary = {
            'principles_count': len(principles),
            'obligations_count': len(obligations),
            'constraints_count': len(constraints),
            'total_entities': len(principles) + len(obligations) + len(constraints)
        }
        
        # Add extraction metadata
        from datetime import datetime
        extraction_metadata = {
            'timestamp': datetime.now().isoformat(),
            'extraction_method': 'enhanced_chapter2' if llm_client else 'fallback_heuristic',
            'principles_extractor': 'EnhancedPrinciplesExtractor',
            'obligations_extractor': 'placeholder',  # Will be updated when we implement enhanced obligations
            'constraints_extractor': 'placeholder',  # Will be updated when we implement enhanced constraints
            'llm_available': llm_client is not None,
            'provenance_tracked': True,
            'model_used': getattr(llm_client, 'model', 'fallback') if llm_client else 'heuristic'
        }
        
        return jsonify({
            'success': True,
            'principles': principles,
            'obligations': obligations,
            'constraints': constraints,
            'summary': summary,
            'extraction_metadata': extraction_metadata
        })
        
    except Exception as e:
        logger.error(f"Error executing normative pass for case {case_id}: {str(e)}")
        return jsonify({'error': str(e), 'success': False}), 500