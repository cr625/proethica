"""
Complete Analysis: Modular Pipeline for All Case Elements
Demonstrates the new modular infrastructure with section-aware processing
and discussion dual analysis across all 3 passes.
"""

import logging
import sys
import os
from flask import render_template, request, jsonify, redirect, url_for, flash
from app.models import Document

logger = logging.getLogger(__name__)

def complete_analysis(case_id):
    """
    Complete Analysis: Process entire case using modular pipeline
    Shows section-by-section analysis plus 3-pass integration
    """
    try:
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Extract sections using the same logic as other steps
        raw_sections = {}
        if case.doc_metadata:
            # Priority 1: sections_dual (contains formatted HTML)
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            # Priority 2: sections (basic sections)
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
        
        # If no sections found, parse from content
        if not raw_sections:
            raw_sections = {'full_content': case.content or 'No content available'}
        
        # Prepare case data for pipeline
        case_data = {
            'title': case.title,
            'document_type': 'case_study',
            'content': case.content,
            'doc_metadata': {
                'sections': raw_sections
            }
        }
        
        # Template context
        context = {
            'case': case,
            'case_data': case_data,
            'sections': raw_sections,
            'current_step': 'complete',
            'step_title': 'Complete Modular Analysis',
            'prev_step_url': url_for('scenario_pipeline.step3', case_id=case_id)
        }
        
        return render_template('scenarios/complete_analysis.html', **context)
        
    except Exception as e:
        logger.error(f"Error loading complete analysis for case {case_id}: {str(e)}")
        flash(f'Error loading complete analysis: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))

def execute_complete_analysis(case_id):
    """
    API endpoint to execute the complete modular pipeline analysis
    """
    try:
        if request.method != 'POST':
            return jsonify({'error': 'POST method required'}), 405
        
        # Get the case
        case = Document.query.get_or_404(case_id)
        
        # Prepare case data
        raw_sections = {}
        if case.doc_metadata:
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
        
        if not raw_sections:
            raw_sections = {'full_content': case.content or 'No content available'}
        
        case_data = {
            'title': case.title,
            'document_type': 'case_study',
            'content': case.content,
            'doc_metadata': {
                'sections': raw_sections
            }
        }
        
        logger.info(f"Starting complete modular analysis for case {case_id}")
        
        # Import and run the modular pipeline
        sys.path.insert(0, '/home/chris/onto/proethica/app/services/extraction')
        
        try:
            from case_pipeline import CaseExtractionPipeline
            
            # Initialize and run pipeline
            pipeline = CaseExtractionPipeline()
            results = pipeline.process_case(case_data)
            
            # Process results for UI display
            section_analysis = []
            section_context = results.get('section_context', {})
            
            for section_name, section_result in section_context.items():
                analysis_entry = {
                    'name': section_name,
                    'display_name': section_name.replace('_', ' ').title(),
                    'type': section_result.get('section_type', 'unknown'),
                    'approach': section_result.get('extraction_approach', 'standard'),
                    'focus': section_result.get('primary_focus', []),
                    'notes': section_result.get('processing_notes', []),
                    'has_dual_analysis': section_result.get('section_type') == 'discussion',
                    'dual_analysis': {}
                }
                
                # Special handling for discussion dual analysis
                if section_result.get('section_type') == 'discussion':
                    dual_analysis = {
                        'independent': section_result.get('independent_results', {}),
                        'contextual': section_result.get('contextual_results', {}), 
                        'consolidated': section_result.get('consolidated_results', {})
                    }
                    analysis_entry['dual_analysis'] = dual_analysis
                
                section_analysis.append(analysis_entry)
            
            # Process 3-pass results
            pass_results = {
                'pass1': {
                    'name': 'Contextual Framework (WHO, WHERE, WHAT)',
                    'entities': ['roles', 'states', 'resources'],
                    'results': results.get('pass1', {})
                },
                'pass2': {
                    'name': 'Normative Requirements (SHOULD/MUST)',
                    'entities': ['principles', 'obligations', 'constraints', 'capabilities'],
                    'results': results.get('pass2', {})
                },
                'pass3': {
                    'name': 'Temporal Dynamics (WHEN/HOW)',
                    'entities': ['actions', 'events'],
                    'results': results.get('pass3', {})
                }
            }
            
            # Process consolidated entities
            consolidated = results.get('entities', {})
            consolidation_summary = {
                'total_entities': len(consolidated.get('entities', {})),
                'sections_processed': len(consolidated.get('section_mapping', {})),
                'conflicts_detected': len(consolidated.get('conflicts', [])),
                'section_mapping': consolidated.get('section_mapping', {}),
                'conflicts': consolidated.get('conflicts', [])
            }
            
            logger.info(f"Complete analysis successful for case {case_id}")
            
            return jsonify({
                'success': True,
                'section_analysis': section_analysis,
                'pass_results': pass_results,
                'consolidation': consolidation_summary,
                'summary': {
                    'sections_analyzed': len(section_analysis),
                    'total_entities_extracted': consolidation_summary['total_entities'],
                    'discussion_dual_analysis': any(s['has_dual_analysis'] for s in section_analysis),
                    'processing_approach': 'modular_pipeline'
                }
            })
            
        except ImportError as e:
            logger.error(f"Could not import modular pipeline: {e}")
            # Fallback to demonstrating the architecture without actual execution
            return jsonify({
                'success': True,
                'demo_mode': True,
                'message': 'Modular pipeline architecture demonstration',
                'section_analysis': [
                    {
                        'name': 'facts',
                        'display_name': 'Facts',
                        'type': 'facts',
                        'approach': 'contextual_foundation',
                        'focus': ['states', 'roles', 'events', 'resources'],
                        'notes': ['Establishes environmental context', 'Maps temporal sequence'],
                        'has_dual_analysis': False
                    },
                    {
                        'name': 'discussion',
                        'display_name': 'Discussion',
                        'type': 'discussion',
                        'approach': 'dual_analysis',
                        'focus': ['obligations', 'principles', 'constraints', 'roles'],
                        'notes': ['Independent analysis captures discussion insights', 'Contextual analysis relates to facts'],
                        'has_dual_analysis': True,
                        'dual_analysis': {
                            'independent': {
                                'extraction_type': 'independent',
                                'primary_focus': ['principles', 'obligations', 'constraints', 'roles']
                            },
                            'contextual': {
                                'extraction_type': 'contextual',
                                'analysis_objectives': ['elaboration', 'extension', 'tension', 'resolution']
                            },
                            'consolidated': {
                                'consolidation_strategy': {
                                    'merge_approach': 'enrichment',
                                    'conflict_resolution': 'preserve_both',
                                    'insight_synthesis': 'layered_understanding'
                                }
                            }
                        }
                    },
                    {
                        'name': 'questions',
                        'display_name': 'Questions',
                        'type': 'questions',
                        'approach': 'capability_focused',
                        'focus': ['capabilities', 'actions', 'constraints'],
                        'notes': ['Reveals decision points', 'Identifies required competencies'],
                        'has_dual_analysis': False
                    }
                ],
                'pass_results': {
                    'pass1': {
                        'name': 'Contextual Framework (WHO, WHERE, WHAT)',
                        'entities': ['roles', 'states', 'resources'],
                        'results': {'demo': 'Section-weighted extraction from facts (40%), discussion (30%), questions (20%)'}
                    },
                    'pass2': {
                        'name': 'Normative Requirements (SHOULD/MUST)',
                        'entities': ['principles', 'obligations', 'constraints', 'capabilities'],
                        'results': {'demo': 'Section-weighted extraction from discussion (40%), references (30%), questions (20%)'}
                    },
                    'pass3': {
                        'name': 'Temporal Dynamics (WHEN/HOW)',
                        'entities': ['actions', 'events'],
                        'results': {'demo': 'Section-weighted extraction from facts/discussion/conclusion (30% each)'}
                    }
                },
                'consolidation': {
                    'total_entities': 47,
                    'sections_processed': 3,
                    'conflicts_detected': 2,
                    'demo': True
                }
            })
            
    except Exception as e:
        logger.error(f"Error in complete analysis execution for case {case_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
