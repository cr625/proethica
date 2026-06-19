"""
Step 4 Data Helpers

Shared data-access and classification functions used by both Step 4 route
modules and service-layer callers (entity_graph_service, etc.).

Moved from app/routes/scenario_pipeline/step4/helpers.py to fix the
service-imports-from-routes layering violation.  The route helpers module
re-exports these symbols for backward compatibility.

Transaction policy: does NOT commit. Callers own the transaction boundary.
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, List

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.routes.scenario_pipeline.step4.config import STEP4_SECTION_TYPE

logger = logging.getLogger(__name__)


# ============================================================================
# ENTITY QUERIES
# ============================================================================

def get_all_case_entities(case_id: int) -> Dict[str, List]:
    """
    Query ALL extracted entities from Passes 1-3.

    Returns:
        Dict with entities by type (lowercase keys):
        {
            'roles': [...],
            'states': [...],
            ...
        }

    Note: Database stores entity_type with capitalized names (Roles, States, etc.)
    but we return lowercase keys for consistency with analyzers.
    """
    # Map lowercase keys to database capitalization
    entity_type_map = {
        'roles': 'Roles',
        'states': 'States',
        'resources': 'Resources',
        'principles': 'Principles',
        'obligations': 'Obligations',
        'constraints': 'Constraints',
        'capabilities': 'Capabilities',
        'actions': 'actions',  # lowercase in DB
        'events': 'events'     # lowercase in DB
    }

    entities = {}
    for key, db_type in entity_type_map.items():
        entities[key] = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            entity_type=db_type,
            storage_type='individual'
        ).all()

    total_count = sum(len(v) for v in entities.values())
    logger.info(f"Loaded entities for case {case_id}: {total_count} total")

    return entities


# ============================================================================
# CONCLUSION CLASSIFICATION
# ============================================================================

def _classify_conclusion_type(text: str) -> str:
    """
    Classify conclusion type based on text content.

    Returns: 'ethical', 'unethical', 'mixed', or 'recommendation'
    """
    text_lower = text.lower()

    # Check for mixed/partial conclusions
    if 'partly ethical' in text_lower or 'partly unethical' in text_lower:
        return 'mixed'
    if 'was not unethical' in text_lower and 'was unethical' in text_lower:
        return 'mixed'

    # Check for clear ethical determination
    if 'was not unethical' in text_lower or 'was ethical' in text_lower:
        if 'was unethical' in text_lower and 'was not unethical' not in text_lower:
            return 'unethical'
        return 'ethical'

    if 'was unethical' in text_lower or 'violated' in text_lower:
        return 'unethical'

    # Check for recommendations
    if 'should' in text_lower or 'obligation to' in text_lower or 'no professional or ethical obligation' in text_lower:
        return 'recommendation'

    return 'unclear'


def _count_conclusion_types(conclusions: list) -> dict:
    """Count conclusions by type (from dict format)."""
    counts = {}
    for c in conclusions:
        t = c.get('type', 'unclear')
        counts[t] = counts.get(t, 0) + 1
    return counts


def _count_conclusion_types_from_list(conclusions: list) -> dict:
    """Count conclusions by type (handles both dicts and dataclass objects)."""
    counts = {}
    for c in conclusions:
        t = c.get('conclusion_type', 'unclear') if isinstance(c, dict) else getattr(c, 'conclusion_type', 'unclear')
        counts[t] = counts.get(t, 0) + 1
    return counts


# ============================================================================
# SYNTHESIS RESULTS STORAGE
# ============================================================================

def _store_synthesis_results(case_id: int, synthesis) -> None:
    """
    Store synthesis results for later viewing.

    Creates a special extraction prompt entry with synthesis results.
    """
    session_id = str(uuid.uuid4())

    # Serialize synthesis results
    synthesis_data = {
        'entity_graph': {
            'total_nodes': len(synthesis.entity_graph.nodes),
            'by_type': {k: len(v) for k, v in synthesis.entity_graph.by_type.items()},
            'by_section': {k: len(v) for k, v in synthesis.entity_graph.by_section.items()}
        },
        'causal_normative_links': [
            {
                'action_id': link.action_id,
                'action_label': link.action_label,
                'fulfills_obligations': link.fulfills_obligations,
                'violates_obligations': link.violates_obligations,
                'guided_by_principles': link.guided_by_principles,
                'constrained_by': link.constrained_by,
                'enabled_by_capabilities': link.enabled_by_capabilities,
                'agent_role': link.agent_role,
                'agent_state': link.agent_state,
                'used_resources': link.used_resources,
                'reasoning': link.reasoning,
                'confidence': link.confidence
            }
            for link in synthesis.causal_normative_links
        ],
        'question_emergence': [
            {
                'question_id': qe.question_id,
                'question_text': qe.question_text,
                'question_number': qe.question_number,
                'triggered_by_events': qe.triggered_by_events,
                'triggered_by_actions': qe.triggered_by_actions,
                'involves_states': qe.involves_states,
                'involves_roles': qe.involves_roles,
                'competing_obligations': qe.competing_obligations,
                'competing_principles': qe.competing_principles,
                'emergence_narrative': qe.emergence_narrative,
                'confidence': qe.confidence
            }
            for qe in synthesis.question_emergence
        ],
        'resolution_patterns': [
            {
                'conclusion_id': rp.conclusion_id,
                'conclusion_text': rp.conclusion_text,
                'conclusion_number': rp.conclusion_number,
                'answers_questions': rp.answers_questions,
                'determinative_principles': rp.determinative_principles,
                'determinative_facts': rp.determinative_facts,
                'cited_provisions': rp.cited_provisions,
                'pattern_type': rp.pattern_type,
                'resolution_narrative': rp.resolution_narrative,
                'confidence': rp.confidence
            }
            for rp in synthesis.resolution_patterns
        ]
    }

    # Delete old synthesis results
    ExtractionPrompt.query.filter_by(
        case_id=case_id,
        concept_type='whole_case_synthesis'
    ).delete(synchronize_session=False)

    # Store as extraction prompt
    extraction_prompt = ExtractionPrompt(
        case_id=case_id,
        concept_type='whole_case_synthesis',
        step_number=4,
        section_type=STEP4_SECTION_TYPE,
        prompt_text='Whole-case synthesis integrating all passes',
        llm_model='case_synthesis_service',
        extraction_session_id=session_id,
        raw_response=json.dumps(synthesis_data, indent=2),
        results_summary={
            'total_nodes': synthesis.total_nodes,
            'total_links': len(synthesis.causal_normative_links),
            'questions_analyzed': len(synthesis.question_emergence),
            'patterns_extracted': len(synthesis.resolution_patterns)
        },
        is_active=True,
        times_used=1,
        created_at=datetime.utcnow(),
        last_used_at=datetime.utcnow()
    )

    db.session.add(extraction_prompt)

    logger.info(f"Stored synthesis results for case {case_id}")
