"""
RDF Converter for Enhanced Temporal Dynamics Pass

Converts actions, events, causal chains, and timeline to RDF format.
Stores in database with proper entity_type separation.
"""

from typing import Dict, List
import logging
import uuid

logger = logging.getLogger(__name__)


def convert_action_to_rdf(action: Dict, case_id: int) -> Dict:
    """
    Convert action dictionary to RDF JSON-LD format.

    Args:
        action: Action data from Stage 3
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    action_uri = f"http://proethica.org/cases/{case_id}#Action_{_safe_id(action.get('label', 'Unknown'))}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': f'http://proethica.org/cases/{case_id}#',
            'proeth-scenario': 'http://proethica.org/ontology/scenario#',
            'time': 'http://www.w3.org/2006/time#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': action_uri,
        '@type': 'proeth:Action',
        'rdfs:label': action.get('label', 'Unknown Action'),
        'proeth:description': action.get('description', ''),
        'proeth:hasAgent': action.get('agent', 'Unknown'),
        'proeth:temporalMarker': action.get('temporal_marker', 'Unknown time')
    }

    # Add intention if present
    intention = action.get('intention', {})
    if intention:
        rdf_entity['proeth:hasMentalState'] = intention.get('mental_state', 'unknown')
        rdf_entity['proeth:intendedOutcome'] = intention.get('intended_outcome', '')
        if intention.get('foreseen_unintended_effects'):
            rdf_entity['proeth:foreseenUnintendedEffects'] = intention['foreseen_unintended_effects']

    # Add ethical context
    ethical_context = action.get('ethical_context', {})
    if ethical_context:
        if ethical_context.get('obligations_fulfilled'):
            rdf_entity['proeth:fulfillsObligation'] = ethical_context['obligations_fulfilled']
        if ethical_context.get('obligations_violated'):
            rdf_entity['proeth:violatesObligation'] = ethical_context['obligations_violated']
        if ethical_context.get('guiding_principles'):
            rdf_entity['proeth:guidedByPrinciple'] = ethical_context['guiding_principles']

    # Add competing priorities
    competing = action.get('competing_priorities', {})
    if competing.get('has_tradeoffs'):
        rdf_entity['proeth:hasCompetingPriorities'] = {
            '@type': 'proeth:CompetingPriorities',
            'proeth:priorityConflict': competing.get('priority_conflict', ''),
            'proeth:resolutionReasoning': competing.get('resolution_reasoning', '')
        }

    # Add professional context
    prof_context = action.get('professional_context', {})
    if prof_context:
        rdf_entity['proeth:withinCompetence'] = prof_context.get('within_competence', False)
        if prof_context.get('required_capabilities'):
            rdf_entity['proeth:requiresCapability'] = prof_context['required_capabilities']

    # Add scenario metadata (for interactive teaching scenarios)
    scenario_meta = action.get('scenario_metadata', {})
    if scenario_meta:
        rdf_entity['proeth-scenario:characterMotivation'] = scenario_meta.get('character_motivation', '')
        rdf_entity['proeth-scenario:ethicalTension'] = scenario_meta.get('ethical_tension', '')
        rdf_entity['proeth-scenario:decisionSignificance'] = scenario_meta.get('decision_significance', '')
        rdf_entity['proeth-scenario:narrativeRole'] = scenario_meta.get('narrative_role', '')
        rdf_entity['proeth-scenario:stakes'] = scenario_meta.get('stakes', '')
        rdf_entity['proeth-scenario:isDecisionPoint'] = scenario_meta.get('is_decision_point', False)
        if scenario_meta.get('alternative_actions'):
            rdf_entity['proeth-scenario:alternativeActions'] = scenario_meta['alternative_actions']
        if scenario_meta.get('consequences_if_alternative'):
            rdf_entity['proeth-scenario:consequencesIfAlternative'] = scenario_meta['consequences_if_alternative']

    return rdf_entity


def convert_event_to_rdf(event: Dict, case_id: int) -> Dict:
    """
    Convert event dictionary to RDF JSON-LD format.

    Args:
        event: Event data from Stage 4
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    event_uri = f"http://proethica.org/cases/{case_id}#Event_{_safe_id(event.get('label', 'Unknown'))}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': f'http://proethica.org/cases/{case_id}#',
            'proeth-scenario': 'http://proethica.org/ontology/scenario#',
            'time': 'http://www.w3.org/2006/time#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': event_uri,
        '@type': 'proeth:Event',
        'rdfs:label': event.get('label', 'Unknown Event'),
        'proeth:description': event.get('description', ''),
        'proeth:temporalMarker': event.get('temporal_marker', 'Unknown time')
    }

    # Add classification
    classification = event.get('classification', {})
    if classification:
        rdf_entity['proeth:eventType'] = classification.get('event_type', 'unknown')
        rdf_entity['proeth:emergencyStatus'] = classification.get('emergency_status', 'routine')

    # Add urgency
    urgency = event.get('urgency', {})
    if urgency:
        rdf_entity['proeth:urgencyLevel'] = urgency.get('urgency_level', 'low')
        if urgency.get('activates_constraints'):
            rdf_entity['proeth:activatesConstraint'] = urgency['activates_constraints']

    # Add triggers
    triggers = event.get('triggers', {})
    if triggers:
        if triggers.get('creates_obligations'):
            rdf_entity['proeth:createsObligation'] = triggers['creates_obligations']
        if triggers.get('state_change'):
            rdf_entity['proeth:causesStateChange'] = triggers['state_change']

    # Add causal context
    causal = event.get('causal_context', {})
    if causal and causal.get('caused_by_action'):
        action_ref = f"http://proethica.org/cases/{case_id}#Action_{_safe_id(causal['caused_by_action'])}"
        rdf_entity['proeth:causedByAction'] = action_ref

    # Add scenario metadata (for interactive teaching scenarios)
    scenario_meta = event.get('scenario_metadata', {})
    if scenario_meta:
        rdf_entity['proeth-scenario:emotionalImpact'] = scenario_meta.get('emotional_impact', '')
        rdf_entity['proeth-scenario:stakeholderConsequences'] = scenario_meta.get('stakeholder_consequences', {})
        rdf_entity['proeth-scenario:dramaticTension'] = scenario_meta.get('dramatic_tension', 'low')
        rdf_entity['proeth-scenario:narrativePacing'] = scenario_meta.get('narrative_pacing', '')
        rdf_entity['proeth-scenario:crisisIdentification'] = scenario_meta.get('crisis_identification', False)
        rdf_entity['proeth-scenario:learningMoment'] = scenario_meta.get('learning_moment', '')
        if scenario_meta.get('discussion_prompts'):
            rdf_entity['proeth-scenario:discussionPrompts'] = scenario_meta['discussion_prompts']
        rdf_entity['proeth-scenario:ethicalImplications'] = scenario_meta.get('ethical_implications', '')

    return rdf_entity


def convert_causal_chain_to_rdf(chain: Dict, case_id: int) -> Dict:
    """
    Convert causal chain dictionary to RDF JSON-LD format.

    Args:
        chain: Causal chain data from Stage 5
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    chain_id = str(uuid.uuid4())[:8]
    chain_uri = f"http://proethica.org/cases/{case_id}#CausalChain_{chain_id}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': f'http://proethica.org/cases/{case_id}#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': chain_uri,
        '@type': 'proeth:CausalChain',
        'proeth:cause': chain.get('cause', 'Unknown'),
        'proeth:effect': chain.get('effect', 'Unknown'),
        'proeth:causalLanguage': chain.get('causal_language', '')
    }

    # Add NESS test
    ness = chain.get('ness_test', {})
    if ness:
        if ness.get('necessary_factors'):
            rdf_entity['proeth:necessaryFactors'] = ness['necessary_factors']
        if ness.get('sufficient_factors'):
            rdf_entity['proeth:sufficientFactors'] = ness['sufficient_factors']
        if ness.get('counterfactual'):
            rdf_entity['proeth:counterfactual'] = ness['counterfactual']

    # Add responsibility
    responsibility = chain.get('responsibility', {})
    if responsibility:
        rdf_entity['proeth:responsibleAgent'] = responsibility.get('responsible_agent', 'Unknown')
        rdf_entity['proeth:responsibilityType'] = responsibility.get('responsibility_type', 'unknown')
        rdf_entity['proeth:withinAgentControl'] = responsibility.get('within_control', False)

    # Add causal chain sequence
    causal_chain_data = chain.get('causal_chain', {})
    if causal_chain_data and causal_chain_data.get('sequence'):
        rdf_entity['proeth:causalSequence'] = [
            {
                'proeth:step': step.get('step'),
                'proeth:element': step.get('element'),
                'proeth:description': step.get('description')
            }
            for step in causal_chain_data['sequence']
        ]

    return rdf_entity


def convert_timeline_to_rdf(timeline_data: Dict, case_id: int) -> Dict:
    """
    Convert timeline dictionary to RDF JSON-LD format.

    Args:
        timeline_data: Timeline data from Stage 6
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    timeline_uri = f"http://proethica.org/cases/{case_id}#Timeline"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': f'http://proethica.org/cases/{case_id}#',
            'time': 'http://www.w3.org/2006/time#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': timeline_uri,
        '@type': 'time:TemporalEntity',
        'rdfs:label': f'Case {case_id} Timeline',
        'proeth:totalElements': timeline_data.get('total_elements', 0),
        'proeth:actionCount': timeline_data.get('actions', 0),
        'proeth:eventCount': timeline_data.get('events', 0)
    }

    # Add timeline entries
    timeline = timeline_data.get('timeline', [])
    rdf_entity['proeth:hasTimepoints'] = [
        {
            'proeth:timepoint': entry.get('timepoint'),
            'time:hasTime': entry.get('iso_duration', ''),
            'proeth:isInterval': entry.get('is_interval', False),
            'proeth:elementCount': len(entry.get('elements', []))
        }
        for entry in timeline
    ]

    # Add consistency check results
    consistency = timeline_data.get('temporal_consistency_check', {})
    if consistency:
        rdf_entity['proeth:temporalConsistency'] = {
            'proeth:valid': consistency.get('valid', True),
            'proeth:warnings': consistency.get('warnings', []),
            'proeth:contradictions': consistency.get('contradictions', [])
        }

    return rdf_entity


def convert_allen_relation_to_rdf(allen_relation: Dict, case_id: int) -> Dict:
    """
    Convert Allen relation dictionary to RDF JSON-LD format with OWL-Time integration.

    Args:
        allen_relation: Allen relation data from Stage 2
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary with both ProEthica custom and OWL-Time properties
    """
    from .allen_owl_time_mapper import create_allen_relation_metadata

    entity1 = allen_relation.get('entity1', 'Unknown')
    entity2 = allen_relation.get('entity2', 'Unknown')
    relation = allen_relation.get('relation', 'unknown')

    # Get OWL-Time mapping
    allen_metadata = create_allen_relation_metadata(relation)

    # Create unique URI for this relation instance
    relation_id = f"{_safe_id(entity1)}_{_safe_id(relation)}_{_safe_id(entity2)}"
    relation_uri = f"http://proethica.org/cases/{case_id}#AllenRelation_{relation_id}"

    # Entity URIs (assume they're actions or events)
    entity1_uri = f"http://proethica.org/cases/{case_id}#Action_{_safe_id(entity1)}"
    entity2_uri = f"http://proethica.org/cases/{case_id}#Action_{_safe_id(entity2)}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': f'http://proethica.org/cases/{case_id}#',
            'time': 'http://www.w3.org/2006/time#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': relation_uri,
        '@type': 'proeth:TemporalRelation',
        'rdfs:label': f'{entity1} {relation} {entity2}',

        # ProEthica custom properties (preserved for backward compatibility)
        'proeth:fromEntity': entity1,
        'proeth:toEntity': entity2,
        'proeth:allenRelation': relation,
        'proeth:fromEntityURI': entity1_uri,
        'proeth:toEntityURI': entity2_uri,

        # OWL-Time standard property
        'proeth:owlTimeProperty': allen_metadata.get('owl_time_property', ''),
        'proeth:owlTimeURI': allen_metadata.get('owl_time_uri', ''),

        # Evidence and description
        'proeth:evidence': allen_relation.get('evidence', ''),
        'proeth:description': allen_metadata.get('description', '')
    }

    # Add the actual OWL-Time property assertion (makes this queryable with standard SPARQL)
    owl_time_prop = allen_metadata.get('owl_time_property')
    if owl_time_prop:
        # Add the OWL-Time property directly to the RDF
        rdf_entity[owl_time_prop] = entity2_uri  # Entity1 [relation] Entity2

    return rdf_entity


def _safe_id(label: str) -> str:
    """Convert label to safe URI identifier."""
    # Remove special characters and replace spaces with underscores
    safe = ''.join(c if c.isalnum() or c in ['_', '-'] else '_' for c in label)
    # Truncate if too long
    return safe[:50]
