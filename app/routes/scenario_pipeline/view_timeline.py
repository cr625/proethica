"""
Timeline Viewer for Generated Scenarios

Displays the generated timeline with LLM-enhanced descriptions and expandable details.
"""

from flask import render_template, jsonify
from models import ModelConfig
from app.models import Document
from app.services.scenario_generation.timeline_constructor import TimelineConstructor
from app.services.direct_llm_service import DirectLLMService
import logging

logger = logging.getLogger(__name__)


def view_timeline(case_id):
    """
    View the generated timeline for a case.

    Shows:
    - Timeline entries in chronological order
    - Phase divisions (introduction/development/resolution)
    - Actions and events at each timepoint
    - LLM-enhanced narrative descriptions
    - Expandable details for each element
    """
    try:
        # Load case
        case = Document.query.get_or_404(case_id)

        # Build timeline
        constructor = TimelineConstructor()
        timeline = constructor.build_timeline(case_id)

        # Enhance timeline with LLM-generated descriptions
        llm_service = DirectLLMService()
        enhanced_timeline = _enhance_timeline_with_llm(
            timeline,
            case,
            llm_service
        )

        return render_template(
            'scenarios/timeline_viewer.html',
            case=case,
            timeline=enhanced_timeline,
            phases=timeline.phases
        )

    except Exception as e:
        logger.error(f"Error viewing timeline for case {case_id}: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


def _enhance_timeline_with_llm(timeline, case, llm_service):
    """
    Use LLM to generate rich narrative descriptions for timeline entries.

    Creates a cohesive narrative that:
    - Describes each timepoint in context
    - Explains the significance of actions/events
    - Highlights ethical considerations
    - Maintains chronological flow
    """
    enhanced_entries = []

    # Get case context for LLM
    case_content = case.content[:500] if case.content else 'N/A'
    case_context = f"""
Case Title: {case.title}
Summary: {case_content}...
"""

    for entry in timeline.entries:
        # Build element summary
        element_summary = []
        for element in entry.elements:
            elem_type = element.get('type', 'unknown')
            label = element.get('label', 'Unknown')
            element_summary.append(f"{elem_type.title()}: {label}")

        # Generate narrative description using LLM
        narrative_prompt = f"""Given this engineering ethics case timeline entry, generate a brief (2-3 sentence) narrative description that explains what happened and its significance.

Case Context:
{case_context}

Timeline Entry:
Timepoint: {entry.timepoint}
Phase: {entry.phase}
Elements: {', '.join(element_summary)}

Generate a narrative description:"""

        try:
            narrative_response = llm_service.generate_completion(
                prompt=narrative_prompt,
                provider='claude',
                model=ModelConfig.get_claude_model("default"),
                max_tokens=150,
                temperature=0.7
            )
            narrative = narrative_response.get('content', '').strip()
        except Exception as e:
            logger.warning(f"LLM enhancement failed for entry {entry.sequence_number}: {e}")
            narrative = f"At {entry.timepoint}, {len(entry.elements)} event(s) occurred."

        enhanced_entries.append({
            'sequence': entry.sequence_number,
            'timepoint': entry.timepoint,
            'phase': entry.phase,
            'elements': entry.elements,
            'element_count': entry.element_count,
            'narrative': narrative,
            'iso_duration': entry.iso_duration
        })

    return {
        'entries': enhanced_entries,
        'total_entries': len(enhanced_entries),
        'total_actions': timeline.total_actions,
        'total_events': timeline.total_events,
        'duration': timeline.duration_description,
        'temporal_consistency': timeline.temporal_consistency
    }
