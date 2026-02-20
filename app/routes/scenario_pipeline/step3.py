"""
Step 3: Temporal Dynamics Pass
Shows case sections and provides LangGraph-based extraction for Pass 3:
Actions, Events, Causal Chains, Allen Relations, and Timeline.
"""

import logging
from flask import render_template, redirect, url_for, flash, request
from app.models import Document, db
from app.routes.scenario_pipeline.overview import _format_section_for_llm
from app.services.pipeline_status_service import PipelineStatusService
from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)


def init_step3_csrf_exemption(app):
    """Exempt Step 3 routes from CSRF protection.
    The enhanced SSE endpoint uses GET and doesn't need CSRF exemption.
    """
    pass


def step3(case_id):
    """
    Step 3: Temporal Dynamics Pass
    Shows the facts section with extraction button for Pass 3 entities.
    """
    try:
        # Redirect to review if Step 3 is complete (unless ?force=1)
        pipeline_status = PipelineStatusService.get_step_status(case_id)
        if (pipeline_status.get('step3', {}).get('complete', False)
                and not request.args.get('force')):
            return redirect(url_for('entity_review.review_enhanced_temporal',
                                    case_id=case_id))

        case = Document.query.get_or_404(case_id)

        # Extract sections using the same logic as step2
        raw_sections = {}
        if case.doc_metadata:
            if 'sections_dual' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections_dual']
            elif 'sections' in case.doc_metadata:
                raw_sections = case.doc_metadata['sections']
            elif 'document_structure' in case.doc_metadata and 'sections' in case.doc_metadata['document_structure']:
                raw_sections = case.doc_metadata['document_structure']['sections']

        if not raw_sections:
            raw_sections = {
                'full_content': case.content or 'No content available'
            }

        # Find the facts section
        facts_section = None
        facts_section_key = None

        for section_key, section_content in raw_sections.items():
            if 'fact' in section_key.lower():
                facts_section_key = section_key
                facts_section = _format_section_for_llm(section_key, section_content, case_doc=case)
                break

        if not facts_section and raw_sections:
            first_key = list(raw_sections.keys())[0]
            facts_section_key = first_key
            facts_section = _format_section_for_llm(first_key, raw_sections[first_key], case_doc=case)

        # Load existing extraction results for page-load display
        existing_extractions = _load_existing_temporal_extractions(case_id)

        context = {
            'case': case,
            'discussion_section': facts_section,
            'discussion_section_key': facts_section_key,
            'current_step': 3,
            'step_title': 'Temporal Dynamics Pass',
            'next_step_url': url_for('step4.step4_synthesis', case_id=case_id),
            'next_step_name': 'Whole-Case Synthesis',
            'prev_step_url': url_for('scenario_pipeline.step2b', case_id=case_id),
            'existing_extractions': existing_extractions,
            'pipeline_status': pipeline_status
        }

        return render_template('scenarios/step3_streaming.html', **context)

    except Exception as e:
        logger.error(f"Error loading step 3 for case {case_id}: {str(e)}")
        flash(f'Error loading step 3: {str(e)}', 'danger')
        return redirect(url_for('cases.view_case', id=case_id))


def _load_existing_temporal_extractions(case_id):
    """Load most recent temporal extraction results for page-load display.

    Returns a dict keyed by entity_type with card-friendly summaries,
    matching the format sent by SSE during live extraction.
    """
    results = {}

    latest_session = db.session.query(
        TemporaryRDFStorage.extraction_session_id
    ).filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_type == 'temporal_dynamics_enhanced',
    ).order_by(
        TemporaryRDFStorage.created_at.desc()
    ).first()

    if not latest_session:
        return results

    session_id = latest_session[0]
    entities = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='temporal_dynamics_enhanced',
        extraction_session_id=session_id,
    ).all()

    for e in entities:
        et = e.entity_type
        rdf = e.rdf_json_ld or {}

        if et == 'actions':
            results.setdefault(et, []).append({
                'label': e.entity_label or '',
                'description': (rdf.get('proeth:description', '') or '')[:200],
                'agent': rdf.get('proeth:hasAgent', ''),
                'temporal_marker': rdf.get('proeth:temporalMarker', ''),
                'intention': rdf.get('proeth:hasMentalState', ''),
            })
        elif et == 'events':
            results.setdefault(et, []).append({
                'label': e.entity_label or '',
                'description': (rdf.get('proeth:description', '') or '')[:200],
                'temporal_marker': rdf.get('proeth:temporalMarker', ''),
                'classification': rdf.get('proeth:eventType', ''),
                'urgency': rdf.get('proeth:urgencyLevel', ''),
            })
        elif et == 'causal_chains':
            results.setdefault(et, []).append({
                'cause': rdf.get('proeth:cause', ''),
                'effect': rdf.get('proeth:effect', ''),
                'responsibility_type': rdf.get('proeth:responsibilityType', ''),
                'counterfactual': rdf.get('proeth:counterfactual', ''),
            })
        elif et == 'allen_relations':
            results.setdefault(et, []).append({
                'entity1': rdf.get('proeth:fromEntity', ''),
                'relation': rdf.get('proeth:allenRelation', ''),
                'entity2': rdf.get('proeth:toEntity', ''),
            })
        elif et == 'timeline':
            timepoints = rdf.get('proeth:hasTimepoints', [])
            results[et] = {
                'total_elements': rdf.get('proeth:totalElements', 0),
                'actions': rdf.get('proeth:actionCount', 0),
                'events': rdf.get('proeth:eventCount', 0),
                'timepoints': [tp.get('proeth:timepoint', '') for tp in timepoints[:10]] if isinstance(timepoints, list) else [],
            }

    return results
