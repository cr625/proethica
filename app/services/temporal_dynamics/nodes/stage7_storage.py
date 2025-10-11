"""
Stage 7 Node: RDF Storage

Converts all extracted data to RDF and stores in database.
Separates actions and events, stores causal chains and timeline.
"""

from typing import Dict
import logging
from datetime import datetime
from flask import current_app

from ..state import TemporalDynamicsState
from ..utils.rdf_converter import (
    convert_action_to_rdf,
    convert_event_to_rdf,
    convert_causal_chain_to_rdf,
    convert_timeline_to_rdf,
    convert_allen_relation_to_rdf
)
from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.provenance_service import ProvenanceService

logger = logging.getLogger(__name__)


def store_rdf_entities(state: TemporalDynamicsState) -> Dict:
    """
    Stage 7: Convert to RDF and store in database

    Args:
        state: Current graph state

    Returns:
        Dict with state updates to merge
    """
    logger.info(f"[Stage 7] Storing RDF entities for case {state['case_id']}")

    case_id = state['case_id']
    session_id = state['extraction_session_id']

    # Get Flask app instance for context
    try:
        flask_app = current_app._get_current_object()
    except RuntimeError:
        # No app context, create one
        from app import create_app
        flask_app = create_app()

    # Execute storage within Flask app context
    with flask_app.app_context():
        try:
            # Initialize counters
            actions_stored = 0
            events_stored = 0
            chains_stored = 0
            allen_relations_stored = 0
            timeline_stored = 0

            # Store actions (separate entity_type)
            for action in state['actions']:
                rdf_entity = convert_action_to_rdf(action, case_id)
                _store_entity(
                    case_id=case_id,
                    session_id=session_id,
                    entity_type='actions',  # Separate type per plan
                    entity_label=action.get('label', 'Unknown Action'),
                    rdf_data=rdf_entity
                )
                actions_stored += 1

            logger.info(f"[Stage 7] Stored {actions_stored} actions")

            # Store events (separate entity_type)
            for event in state['events']:
                rdf_entity = convert_event_to_rdf(event, case_id)
                _store_entity(
                    case_id=case_id,
                    session_id=session_id,
                    entity_type='events',  # Separate type per plan
                    entity_label=event.get('label', 'Unknown Event'),
                    rdf_data=rdf_entity
                )
                events_stored += 1

            logger.info(f"[Stage 7] Stored {events_stored} events")

            # Store causal chains
            for chain in state['causal_chains']:
                rdf_entity = convert_causal_chain_to_rdf(chain, case_id)
                _store_entity(
                    case_id=case_id,
                    session_id=session_id,
                    entity_type='causal_chains',
                    entity_label=f"{chain.get('cause', 'Unknown')} → {chain.get('effect', 'Unknown')}",
                    rdf_data=rdf_entity
                )
                chains_stored += 1

            logger.info(f"[Stage 7] Stored {chains_stored} causal chains")

            # Store Allen temporal relations (from temporal_markers)
            temporal_markers = state.get('temporal_markers', {})
            allen_relations = temporal_markers.get('allen_relations', [])
            for allen_relation in allen_relations:
                rdf_entity = convert_allen_relation_to_rdf(allen_relation, case_id)
                entity1 = allen_relation.get('entity1', 'Unknown')
                entity2 = allen_relation.get('entity2', 'Unknown')
                relation = allen_relation.get('relation', 'unknown')
                _store_entity(
                    case_id=case_id,
                    session_id=session_id,
                    entity_type='allen_relations',
                    entity_label=f'{entity1} {relation} {entity2}',
                    rdf_data=rdf_entity
                )
                allen_relations_stored += 1

            logger.info(f"[Stage 7] Stored {allen_relations_stored} Allen temporal relations")

            # Store timeline
            if state.get('timeline'):
                rdf_entity = convert_timeline_to_rdf(state['timeline'], case_id)
                _store_entity(
                    case_id=case_id,
                    session_id=session_id,
                    entity_type='timeline',
                    entity_label=f'Case {case_id} Timeline',
                    rdf_data=rdf_entity
                )
                timeline_stored = 1

            logger.info(f"[Stage 7] Stored timeline")

            # Store LLM trace if present
            llm_trace_stored = 0
            if state.get('llm_trace'):
                llm_trace_stored = _store_llm_trace(
                    case_id=case_id,
                    session_id=session_id,
                    llm_trace=state['llm_trace']
                )

            # Save extraction summary to extraction_prompts table for Step 3 display
            _save_extraction_summary(case_id, state)

            # Commit transaction
            db.session.commit()

            logger.info(f"[Stage 7] All entities committed to database")

            # Build progress message
            message = (
                f'✓ Stored {actions_stored} actions, {events_stored} events, '
                f'{chains_stored} causal chains, {allen_relations_stored} Allen relations, timeline'
            )
            if llm_trace_stored > 0:
                message += f', {llm_trace_stored} LLM traces'

            # Return state updates
            return {
                'current_stage': 'rdf_storage',
                'progress_percentage': 100,
                'stage_messages': [message],
                'end_time': datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"[Stage 7] Error: {e}", exc_info=True)
            db.session.rollback()
            return {
                'current_stage': 'rdf_storage',
                'progress_percentage': 100,
                'errors': [f'RDF storage error: {str(e)}']
            }


def _store_entity(
    case_id: int,
    session_id: str,
    entity_type: str,
    entity_label: str,
    rdf_data: Dict
) -> None:
    """
    Store a single RDF entity in the database.

    Args:
        case_id: Case ID
        session_id: Extraction session ID
        entity_type: Type of entity (actions, events, causal_chains, timeline)
        entity_label: Label for the entity
        rdf_data: RDF JSON-LD data
    """
    entity = TemporaryRDFStorage(
        case_id=case_id,
        extraction_session_id=session_id,
        entity_type=entity_type,
        storage_type='individual',
        entity_label=entity_label,
        rdf_json_ld=rdf_data,
        extraction_type='temporal_dynamics_enhanced'
    )
    db.session.add(entity)


def _store_llm_trace(case_id: int, session_id: str, llm_trace: list) -> int:
    """
    Store LLM trace using PROV-O provenance system.

    Args:
        case_id: Case ID
        session_id: Extraction session ID
        llm_trace: List of LLM interaction dictionaries

    Returns:
        Number of trace entries stored
    """
    prov_service = ProvenanceService()

    stored_count = 0

    for trace_entry in llm_trace:
        try:
            # Create activity for this LLM interaction
            with prov_service.track_activity(
                activity_type='llm_query',
                activity_name=f"temporal_{trace_entry.get('stage', 'unknown')}",
                case_id=case_id,
                session_id=session_id,
                agent_type='llm_model',
                agent_name=trace_entry.get('model', 'unknown')
            ) as activity:
                # Record prompt entity
                prompt_entity = prov_service.record_prompt(
                    prompt_text=trace_entry.get('prompt', ''),
                    activity=activity,
                    metadata={
                        'stage': trace_entry.get('stage'),
                        'timestamp': trace_entry.get('timestamp')
                    }
                )

                # Record response entity
                if trace_entry.get('response'):
                    prov_service.record_response(
                        response_text=trace_entry.get('response', ''),
                        activity=activity,
                        derived_from=prompt_entity,
                        metadata={
                            'parsed_output': trace_entry.get('parsed_output', {}),
                            'tokens': trace_entry.get('tokens', {})
                        }
                    )

                stored_count += 1

        except Exception as e:
            logger.error(f"Error storing LLM trace entry: {e}")
            # Continue with other entries

    db.session.flush()
    logger.info(f"[Stage 7] Stored {stored_count} LLM trace entries via PROV-O")

    return stored_count


def _save_extraction_summary(case_id: int, state: Dict) -> None:
    """
    Save extraction summary to extraction_prompts table for Step 3 page display.

    This allows the Step 3 page to show saved prompts/responses when refreshed,
    maintaining consistency with other extraction steps.

    Args:
        case_id: Case ID
        state: Complete extraction state with LLM traces
    """
    from app.models.extraction_prompt import ExtractionPrompt

    try:
        # Compile all prompts and responses from llm_trace
        llm_trace = state.get('llm_trace', [])
        if not llm_trace:
            logger.info("[Stage 7] No LLM trace to save to extraction_prompts")
            return

        # Build combined prompt and response from all stages
        combined_prompt_parts = []
        combined_response_parts = []

        for i, trace_entry in enumerate(llm_trace, 1):
            stage = trace_entry.get('stage', f'stage_{i}')
            prompt = trace_entry.get('prompt', '')
            response = trace_entry.get('response', '')

            if prompt:
                combined_prompt_parts.append(f"=== {stage.upper()} ===\n{prompt}\n")
            if response:
                combined_response_parts.append(f"=== {stage.upper()} RESPONSE ===\n{response}\n")

        combined_prompt = "\n".join(combined_prompt_parts)
        combined_response = "\n".join(combined_response_parts)

        # Get model from first trace entry
        llm_model = llm_trace[0].get('model', 'claude-opus-4-1-20250805') if llm_trace else 'unknown'

        # Save to extraction_prompts table
        ExtractionPrompt.save_prompt(
            case_id=case_id,
            concept_type='actions_events',
            prompt_text=combined_prompt,
            raw_response=combined_response,
            step_number=3,
            llm_model=llm_model,
            section_type='facts'
        )

        logger.info(f"[Stage 7] Saved extraction summary to extraction_prompts for Step 3 display")

    except Exception as e:
        logger.error(f"[Stage 7] Error saving extraction summary: {e}")
        # Don't fail the whole storage if this fails
        pass
