"""
Step 4 Helper Functions

Shared utilities used across Step 4 route sub-modules and by external callers
(entity_review.py, run_all.py).
"""

import json
import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.models import Document, TemporaryRDFStorage, ExtractionPrompt, db
from app.services.pipeline_status_service import PipelineStatusService
from app.services.unified_entity_resolver import get_unified_entity_lookup

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


def get_entities_summary(case_id: int) -> Dict:
    """Get summary of all extracted entities from Steps 1-3.

    Counts by extraction_type (classes + individuals) so totals match
    the commit counts on the entities page.
    """
    summary = {}

    # Steps 1-2 concepts: count all entities per extraction_type
    for concept in ['roles', 'states', 'resources', 'principles',
                    'obligations', 'constraints', 'capabilities']:
        summary[concept] = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type=concept
        ).count()

    # Step 3: temporal_dynamics_enhanced covers all sub-types
    # (actions, events, allen_relations, causal_chains, timeline)
    summary['temporal_dynamics'] = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='temporal_dynamics_enhanced'
    ).count()

    # Calculate totals
    summary['pass1_total'] = (
        summary['roles'] + summary['states'] + summary['resources']
    )
    summary['pass2_total'] = (
        summary['principles'] + summary['obligations']
        + summary['constraints'] + summary['capabilities']
    )
    summary['pass3_total'] = summary['temporal_dynamics']
    summary['total'] = (
        summary['pass1_total'] + summary['pass2_total'] + summary['pass3_total']
    )

    return summary


def get_synthesis_status(case_id: int) -> Dict:
    """
    Check if synthesis has been completed for this case.

    Returns:
        Dict with synthesis status and results
    """
    # Check for code provisions
    provisions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='code_provision_reference'
    ).count()

    # Check for questions
    questions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).count()

    # Check for conclusions
    conclusions = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).count()

    # Check for precedent case references
    precedents = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='precedent_case_reference'
    ).count()

    completed = provisions > 0 or questions > 0 or conclusions > 0

    # Get transformation type from case_precedent_features
    from app.models import CasePrecedentFeatures
    transformation_type = None
    transformation_detail = {}
    features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
    if features and features.transformation_type:
        transformation_type = features.transformation_type
        # Pull richer detail from the extraction prompt response
        trans_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id, concept_type='transformation_classification'
        ).order_by(ExtractionPrompt.created_at.desc()).first()
        if trans_prompt and trans_prompt.raw_response:
            try:
                import json as _json
                raw = trans_prompt.raw_response.strip()
                # Strip markdown code fence if present
                if raw.startswith('```'):
                    raw = raw.split('\n', 1)[1] if '\n' in raw else raw[3:]
                    if raw.endswith('```'):
                        raw = raw[:-3]
                parsed = _json.loads(raw.strip())
                transformation_detail = {
                    'reasoning': parsed.get('reasoning', ''),
                    'pattern_description': parsed.get('pattern_description', ''),
                    'confidence': parsed.get('confidence'),
                }
            except (ValueError, KeyError):
                pass

    return {
        'completed': completed,
        'provisions_count': provisions,
        'questions_count': questions,
        'conclusions_count': conclusions,
        'precedents_count': precedents,
        'transformation_type': transformation_type,
        'transformation_detail': transformation_detail,
    }


def _load_phase2_entity_summaries(case_id: int) -> Dict[str, List[Dict]]:
    """Load Phase 2 entities for summary display on the extraction page.

    Returns dict keyed by extraction_type with list of {label, definition, rdf}
    dicts for server-side rendering of entity summaries.
    """
    PHASE2_TYPES = [
        'code_provision_reference',
        'precedent_case_reference',
        'ethical_question',
        'ethical_conclusion',
        'causal_normative_link',
        'question_emergence',
        'resolution_pattern',
    ]
    result = {}
    entities = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_type.in_(PHASE2_TYPES)
    ).order_by(TemporaryRDFStorage.created_at).all()

    for e in entities:
        result.setdefault(e.extraction_type, []).append({
            'id': e.id,
            'label': e.entity_label,
            'definition': e.entity_definition,
            'rdf': e.rdf_json_ld or {},
        })
    return result


# ============================================================================
# PHASE 2 DATA LOADING
# ============================================================================

def load_phase2_data(case_id: int) -> Dict:
    """
    Load Phase 2 data needed for Phase 3 synthesis.

    Returns:
        Dict containing:
        - questions: List of ethical questions
        - conclusions: List of board conclusions
        - question_emergence: List of Toulmin question emergence analyses
        - resolution_patterns: List of resolution pattern analyses
    """
    # Load questions
    questions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_question'
    ).all()

    questions = [
        {
            'uri': q.entity_uri or f"case-{case_id}#Q{i+1}",
            'label': q.entity_label,
            'text': q.entity_definition or q.entity_label,
            'mentioned_entities': q.rdf_json_ld.get('mentionedEntities', []) if q.rdf_json_ld else [],
            'related_provisions': q.rdf_json_ld.get('relatedProvisions', []) if q.rdf_json_ld else []
        }
        for i, q in enumerate(questions_raw)
    ]

    # Load conclusions
    conclusions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).all()

    conclusions = [
        {
            'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
            'label': c.entity_label,
            'text': c.entity_definition or c.entity_label,
            'cited_provisions': c.rdf_json_ld.get('citedProvisions', []) if c.rdf_json_ld else [],
            'cited_actions': c.rdf_json_ld.get('citedActions', []) if c.rdf_json_ld else [],
            'answers_questions': c.rdf_json_ld.get('answersQuestions', []) if c.rdf_json_ld else []
        }
        for i, c in enumerate(conclusions_raw)
    ]

    # Load question emergence (Toulmin analysis)
    qe_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='question_emergence'
    ).all()

    question_emergence = []
    for qe in qe_raw:
        if qe.rdf_json_ld:
            question_emergence.append(qe.rdf_json_ld)
        else:
            question_emergence.append({
                'question_uri': qe.entity_uri or '',
                'question_text': qe.entity_definition or '',
                'competing_warrants': [],
                'data_events': [],
                'data_actions': [],
                'involves_roles': []
            })

    # Load resolution patterns
    rp_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='resolution_pattern'
    ).all()

    resolution_patterns = []
    for rp in rp_raw:
        if rp.rdf_json_ld:
            resolution_patterns.append(rp.rdf_json_ld)
        else:
            resolution_patterns.append({
                'conclusion_uri': rp.entity_uri or '',
                'conclusion_text': rp.entity_definition or '',
                'determinative_principles': [],
                'resolution_narrative': ''
            })

    logger.info(f"Loaded Phase 2 data for case {case_id}: {len(questions)} Q, {len(conclusions)} C, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

    return {
        'questions': questions,
        'conclusions': conclusions,
        'question_emergence': question_emergence,
        'resolution_patterns': resolution_patterns
    }


# ============================================================================
# PHASE 4 CALLBACK FUNCTIONS
# ============================================================================

def build_entity_foundation_for_phase4(case_id: int):
    """Build EntityFoundation for Phase 4 narrative construction."""
    from app.services.case_synthesizer import CaseSynthesizer
    synthesizer = CaseSynthesizer()
    return synthesizer._build_entity_foundation(case_id)


def load_canonical_points_for_phase4(case_id: int) -> List:
    """Load canonical decision points from Phase 3."""
    from app.services.decision_point_synthesizer import CanonicalDecisionPoint

    canonical_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).all()

    points = []
    for raw in canonical_raw:
        if raw.rdf_json_ld:
            data = raw.rdf_json_ld
            points.append(CanonicalDecisionPoint(
                focus_id=data.get('focus_id', ''),
                focus_number=data.get('focus_number', 0),
                description=data.get('description', ''),
                decision_question=data.get('decision_question', ''),
                role_uri=data.get('role_uri', ''),
                role_label=data.get('role_label', ''),
                obligation_uri=data.get('obligation_uri'),
                obligation_label=data.get('obligation_label'),
                constraint_uri=data.get('constraint_uri'),
                constraint_label=data.get('constraint_label'),
                involved_action_uris=data.get('involved_action_uris', []),
                provision_uris=data.get('provision_uris', []),
                provision_labels=data.get('provision_labels', []),
                options=data.get('options', []),
                intensity_score=data.get('intensity_score', 0.0),
                qc_alignment_score=data.get('qc_alignment_score', 0.0)
            ))

    return points


def load_conclusions_for_phase4(case_id: int) -> List[Dict]:
    """Load conclusions for Phase 4 including mentioned_entities from extraction prompts."""
    # Load from RDF storage
    conclusions_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='ethical_conclusion'
    ).all()

    # Also load mentioned_entities from extraction prompts
    mentioned_entities_map = {}
    try:
        prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='ethical_conclusion'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if prompt and prompt.raw_response:
            raw = prompt.raw_response
            # Remove markdown code blocks if present
            raw = re.sub(r'^```json\s*', '', raw)
            raw = re.sub(r'\s*```$', '', raw)
            data = json.loads(raw)

            # Build map from conclusion labels to mentioned_entities
            for category in data.values():
                if isinstance(category, list):
                    for c in category:
                        label = c.get('conclusion_text', '')[:50]
                        if c.get('mentioned_entities'):
                            mentioned_entities_map[label] = c.get('mentioned_entities', {})
    except Exception as e:
        logger.debug(f"Could not load mentioned_entities for conclusions: {e}")

    results = []
    for i, c in enumerate(conclusions_raw):
        # Try to match with mentioned_entities by label prefix
        mentioned = {}
        label = c.entity_label or ''
        definition = c.entity_definition or ''
        for key in mentioned_entities_map:
            if key in definition or key in label:
                mentioned = mentioned_entities_map[key]
                break

        results.append({
            'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
            'label': c.entity_label,
            'text': c.entity_definition or c.entity_label,
            'cited_provisions': c.rdf_json_ld.get('citedProvisions', []) if c.rdf_json_ld else [],
            'mentioned_entities': mentioned
        })

    return results


def get_transformation_type_for_phase4(case_id: int) -> Optional[str]:
    """Get transformation classification for Phase 4."""
    from app.models import CasePrecedentFeatures

    # Try to get from case_precedent_features table
    try:
        features = CasePrecedentFeatures.query.filter_by(case_id=case_id).first()
        if features and features.transformation_type:
            return features.transformation_type
    except Exception:
        pass  # Table may not exist or other error

    # Fall back to extraction in temporary_rdf_storage
    trans_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='transformation_analysis'
    ).first()

    if trans_raw and trans_raw.rdf_json_ld:
        return trans_raw.rdf_json_ld.get('transformation_type', 'unknown')

    return None


def load_causal_links_for_phase4(case_id: int) -> List[Dict]:
    """Load causal-normative links for Phase 4."""
    links_raw = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='causal_normative_link'
    ).all()

    return [
        link.rdf_json_ld if link.rdf_json_ld else {
            'action_uri': link.entity_uri or '',
            'action_label': link.entity_label,
            'obligation_uri': '',
            'obligation_label': ''
        }
        for link in links_raw
    ]


# ============================================================================
# ENTITY GROUPING / CLASSIFICATION HELPERS
# ============================================================================

def _build_step4_entity_groups(case_id: int) -> List[Dict]:
    """Build phase-grouped entity data for the Step 4 entities page.

    Returns list of dicts, one per phase group. Each contains the phase label,
    icon, entities list, by_type sub-grouping, and count/publish stats.
    """
    PHASE_DEFS = [
        {
            'phase': '2A', 'label': 'Code Provisions',
            'icon': 'bi-file-text',
            'types': ['code_provision_reference'],
        },
        {
            'phase': '2B', 'label': 'Precedent Cases',
            'icon': 'bi-journal-bookmark',
            'types': ['precedent_case_reference'],
        },
        {
            'phase': '2C', 'label': 'Questions & Conclusions',
            'icon': 'bi-question-circle',
            'types': ['ethical_question', 'ethical_conclusion'],
        },
        {
            'phase': '2E', 'label': 'Rich Analysis',
            'icon': 'bi-diagram-3',
            'types': ['causal_normative_link', 'question_emergence', 'resolution_pattern'],
        },
        {
            'phase': '3', 'label': 'Decision Points',
            'icon': 'bi-signpost-split',
            'types': ['canonical_decision_point'],
        },
    ]

    groups = []
    for defn in PHASE_DEFS:
        entities = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.extraction_type.in_(defn['types'])
        ).order_by(
            TemporaryRDFStorage.extraction_type,
            TemporaryRDFStorage.created_at
        ).all()

        by_type = defaultdict(list)
        for e in entities:
            by_type[e.extraction_type].append(e)

        rej = sum(1 for e in entities if not e.is_published and not e.is_selected and e.is_reviewed)
        groups.append({
            'phase': defn['phase'],
            'label': defn['label'],
            'icon': defn['icon'],
            'entities': entities,
            'by_type': dict(by_type),
            'count': len(entities),
            'published_count': sum(1 for e in entities if e.is_published),
            'unpublished_count': sum(1 for e in entities if not e.is_published),
            'rejected_count': rej,
        })

    return groups


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
# REVIEW PAGE DATA LOADING
# ============================================================================

def _load_decision_points_for_review(case_id: int) -> List[Dict]:
    """Load canonical decision points for the review page with their arguments."""
    decision_points = []
    dp_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='canonical_decision_point'
    ).order_by(TemporaryRDFStorage.created_at).all()

    # Load arguments and validations
    arg_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_generated'
    ).all()
    val_objs = TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        extraction_type='argument_validation'
    ).all()

    # Build validation lookup
    validations = {}
    for v in val_objs:
        if v.rdf_json_ld:
            validations[v.rdf_json_ld.get('argument_id')] = v.rdf_json_ld

    # Group arguments by decision point (including all DPs in decision_point_ids array)
    args_by_dp = {}
    for arg in arg_objs:
        if arg.rdf_json_ld:
            arg_data = arg.rdf_json_ld.copy()
            # Attach validation if available
            arg_id = arg_data.get('argument_id')
            if arg_id and arg_id in validations:
                arg_data['validation'] = validations[arg_id]

            # Get all decision point IDs this argument belongs to
            dp_ids = arg.rdf_json_ld.get('decision_point_ids', [])
            if not dp_ids:
                # Fallback to singular decision_point_id
                primary_dp = arg.rdf_json_ld.get('decision_point_id', '')
                if primary_dp:
                    dp_ids = [primary_dp]

            # Add argument to each decision point it belongs to
            for dp_id in dp_ids:
                if dp_id not in args_by_dp:
                    args_by_dp[dp_id] = []
                args_by_dp[dp_id].append(arg_data)

    for obj in dp_objs:
        if obj.rdf_json_ld:
            data = obj.rdf_json_ld
            focus_id = data.get('focus_id', '')
            decision_points.append({
                'focus_id': focus_id,
                'focus_number': data.get('focus_number', 0),
                'description': data.get('description', obj.entity_label),
                'decision_question': data.get('decision_question', obj.entity_definition),
                'entity_label': obj.entity_label,
                'entity_definition': obj.entity_definition,
                'obligation_label': data.get('obligation_label', ''),
                'obligations_in_tension': data.get('obligations_in_tension', []),
                'options': data.get('options', []),
                'qc_alignment_score': data.get('qc_alignment_score', 0),
                'source': data.get('source', 'algorithmic'),
                'arguments': args_by_dp.get(focus_id, [])
            })

    return decision_points


def _enrich_decision_moment_options(case_id: int, decision_moments: List[Dict]) -> List[Dict]:
    """Enrich decision moment options with descriptions from canonical decision points.

    The narrative extractor stores options with 'label', but older runs left labels
    empty because canonical DPs use 'description' not 'label'. This fills in missing
    labels by matching decision moments to their source canonical DPs by question text.
    """
    # Check if enrichment is needed (any option with empty label)
    needs_enrichment = any(
        not opt.get('label')
        for dm in decision_moments
        for opt in dm.get('options', [])
    )
    if not needs_enrichment:
        return decision_moments

    # Load canonical decision point options keyed by question text
    dp_rows = TemporaryRDFStorage.query.filter_by(
        case_id=case_id, extraction_type='canonical_decision_point'
    ).all()

    dp_options_by_question = {}
    for row in dp_rows:
        rdf = row.rdf_json_ld or {}
        q_text = rdf.get('decision_question', '')
        if q_text and rdf.get('options'):
            dp_options_by_question[q_text] = rdf['options']

    # Enrich each decision moment
    for dm in decision_moments:
        q_text = dm.get('question', '')
        dp_opts = dp_options_by_question.get(q_text, [])
        dm_opts = dm.get('options', [])
        if dp_opts and len(dp_opts) == len(dm_opts):
            for i, opt in enumerate(dm_opts):
                if not opt.get('label') and i < len(dp_opts):
                    opt['label'] = dp_opts[i].get('description', '')
                    # Also carry over action_uri if missing
                    if not opt.get('action_uris') and dp_opts[i].get('action_uri'):
                        opt['action_uris'] = [dp_opts[i]['action_uri']]

    return decision_moments


def _load_narrative_for_review(case_id: int) -> Optional[Dict]:
    """Load Phase 4 narrative data for the review page."""
    try:
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(ExtractionPrompt.created_at.desc()).first()

        if phase4_prompt and phase4_prompt.raw_response:
            data = json.loads(phase4_prompt.raw_response)

            # Extract narrative_elements
            ne = data.get('narrative_elements', {})
            characters = ne.get('characters', []) if isinstance(ne, dict) else []
            conflicts = ne.get('conflicts', []) if isinstance(ne, dict) else []
            decision_moments = ne.get('decision_moments', []) if isinstance(ne, dict) else []

            # Enrich decision moment options: the narrative extractor may have
            # stored options with empty labels (old code read 'label' but canonical
            # DPs use 'description'). Pull descriptions from canonical DPs.
            decision_moments = _enrich_decision_moment_options(case_id, decision_moments)

            # Extract timeline
            tl = data.get('timeline', {})
            events = tl.get('events', []) if isinstance(tl, dict) else (tl if isinstance(tl, list) else [])
            initial_fluents = tl.get('initial_fluents', []) if isinstance(tl, dict) else []
            causal_links = tl.get('causal_links', []) if isinstance(tl, dict) else []
            event_trace = tl.get('event_trace', '') if isinstance(tl, dict) else ''

            # Extract scenario_seeds
            seeds = data.get('scenario_seeds', {})
            opening_context = seeds.get('opening_context', '') if isinstance(seeds, dict) else ''
            protagonist = seeds.get('protagonist_label', '') if isinstance(seeds, dict) else ''

            # Extract insights
            insights = data.get('insights', {})
            key_takeaways = insights.get('key_takeaways', []) if isinstance(insights, dict) else []
            patterns = insights.get('patterns', []) if isinstance(insights, dict) else []

            return {
                'has_data': True,
                'timestamp': phase4_prompt.created_at.isoformat() if phase4_prompt.created_at else None,
                # Narrative elements
                'characters': characters,
                'conflicts': conflicts,
                'decision_moments': decision_moments,
                # Timeline
                'events': events,
                'initial_fluents': initial_fluents,
                'causal_links': causal_links,
                'event_trace': event_trace,
                # Scenario seeds
                'opening_context': opening_context,
                'protagonist': protagonist,
                # Insights
                'key_takeaways': key_takeaways,
                'patterns': patterns,
                # Summary for counts
                'summary': data.get('summary', {})
            }
    except Exception as e:
        logger.debug(f"Could not load narrative for case {case_id}: {e}")

    return {'has_data': False}


def _get_all_entities_for_graph(case_id: int) -> List:
    """
    Get all extracted entities from Passes 1-4 for graph visualization.
    Returns list of entity objects for D3/Cytoscape rendering (both committed and uncommitted).
    """
    # Include all entity types shown in the entity graph (matches entity_graph API)
    extraction_types = [
        'roles', 'states', 'resources',  # Pass 1
        'principles', 'obligations', 'constraints', 'capabilities',  # Pass 2
        'temporal_dynamics_enhanced',  # Pass 3 (all temporal entities)
        'code_provision_reference', 'ethical_question', 'ethical_conclusion',  # Step 4 core
        'causal_normative_link', 'question_emergence', 'resolution_pattern',  # Step 4 rich analysis
        'canonical_decision_point',  # Step 4 decision points
        'precedent_case_reference'  # Step 6 precedent discovery
    ]

    all_entities = []
    # Query by extraction_type to get relevant entities
    entities = TemporaryRDFStorage.query.filter(
        TemporaryRDFStorage.case_id == case_id,
        TemporaryRDFStorage.extraction_type.in_(extraction_types),
        TemporaryRDFStorage.storage_type == 'individual'
    ).all()
    all_entities.extend(entities)

    return all_entities


def _build_entity_lookup_dict(case_id: int) -> Dict[str, Dict]:
    """
    Build a lookup dictionary mapping entity URIs to their metadata.

    DEPRECATED: Use get_unified_entity_lookup() from unified_entity_resolver instead.
    This function is kept for backwards compatibility.

    Args:
        case_id: The case ID to load entities for

    Returns:
        Dict mapping entity_uri -> entity metadata
    """
    return get_unified_entity_lookup(case_id)


# ============================================================================
# SYNTHESIS RESULTS STORAGE
# ============================================================================

def _store_synthesis_results(case_id: int, synthesis) -> None:
    """
    Store synthesis results for later viewing

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
    db.session.commit()

    logger.info(f"Stored synthesis results for case {case_id}")
