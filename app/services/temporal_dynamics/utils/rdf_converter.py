"""
RDF Converter for Enhanced Temporal Dynamics Pass

Converts actions, events, causal chains, and timeline to RDF format.
Stores in database with proper entity_type separation.
"""

from typing import Dict, List, Optional, Tuple
import logging
import re
import uuid

logger = logging.getLogger(__name__)


def _case_ns(case_id: int) -> str:
    """Canonical per-case namespace base. Single scheme for every producer so the
    persisted graph is self-describing and the read-time legacy-IRI bridge
    (ontserve_commit_service._remap_legacy_iri) can be retired after baseline
    backfill. Matches the edge materialisers + commit serializer
    (commit_case_versioned). Was the divergent http://proethica.org/cases/<id>#
    scheme (R2 namespace unification)."""
    return f"http://proethica.org/ontology/case/{case_id}#"

# A "clean" agent string is a single name followed by exactly one trailing
# parenthetical role group and nothing else, e.g.
#   "Engineer A (Professional Engineer, Structural)"
# Strings with zero or multiple parenthetical groups (e.g.
#   "Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)")
# are conjunctive/composite agents that cannot be split into a single role
# context; they are left intact for the bucket-C corrective pass.
_CLEAN_AGENT_RE = re.compile(r'^([^()]+?)\s*\(([^()]+)\)\s*$')


def split_agent_role(agent: str) -> Tuple[str, Optional[str]]:
    """Split a "Name (role)" agent string into (name, role_context).

    Returns ``(clean_name, role_context)`` when the string is a clean single
    "Name (role)" form, otherwise ``(agent_unchanged, None)``. Shared by the
    live converter (study-corrections A7) and the corpus backfill
    (study-corrections B4) so both apply identical normalization.
    """
    if not agent:
        return agent, None
    m = _CLEAN_AGENT_RE.match(agent.strip())
    if not m:
        return agent, None
    name = m.group(1).strip()
    role = m.group(2).strip()
    if not name or not role:
        return agent, None
    return name, role


# Top-level conjunctions joining multiple actors. Matched only at paren depth 0
# (parenthetical role groups are masked first) so a comma or "and" inside a role
# string ("superintendent and chief engineer") does not split the actors.
_AGENT_CONJ_RE = re.compile(r'\s+(and/or|and|or|&|with|in conjunction with)\s+', re.I)


def decompose_agents(agent: str):
    """Decompose a composite multi-actor agent string into structured agents.

    Handles the common conjunction forms, e.g.
      "Engineer A (Original Engineer) and Engineer B (Reviewing Engineer)"
      "ZZZ (project owner) and Firm C (design firm)"
      "Engineer A and Engineer B"   (bare names, no roles)
    Returns ``(agents, relation)`` where ``agents`` is a list of
    ``{"name", "role"}`` (role may be None) and ``relation`` is the joining
    keyword (``and`` / ``or`` / ``and/or`` / ``with`` / ``in_conjunction_with``),
    or ``None`` when the string is single-actor / not a conjunction (the caller
    then keeps the existing single-actor ``split_agent_role`` behaviour).

    Generalises the one-off `decompose_composite_agents.py` hand table so a
    re-extraction (Section C) decomposes new multi-actor strings without it.
    Precedent cross-references and free-text Discussion notes are NOT extracted
    here (the precedent filter handles the former; the latter were hand-specific).
    """
    if not agent or not agent.strip():
        return None
    s = agent.strip()
    # Mask parenthetical groups so conjunctions inside a role do not split actors.
    groups: list = []

    def _mask(m):
        groups.append(m.group(0))
        return f"\x00{len(groups) - 1}\x00"

    masked = re.sub(r'\([^()]*\)', _mask, s)
    parts = _AGENT_CONJ_RE.split(masked)
    if len(parts) < 3:  # no top-level conjunction -> single actor
        return None
    segments = parts[0::2]
    separators = parts[1::2]
    relation = separators[0].lower().replace(' ', '_') if separators else None

    def _unmask(x: str) -> str:
        return re.sub(r'\x00(\d+)\x00', lambda mm: groups[int(mm.group(1))], x).strip()

    agents = []
    for seg in segments:
        seg = _unmask(seg)
        if not seg:
            continue
        name, role = split_agent_role(seg)
        if name:
            agents.append({"name": name, "role": role})
    if len(agents) < 2:
        return None
    return agents, relation


def convert_action_to_rdf(action: Dict, case_id: int) -> Dict:
    """
    Convert action dictionary to RDF JSON-LD format.

    Args:
        action: Action data from Stage 3
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    action_uri = f"{_case_ns(case_id)}Action_{_safe_id(action.get('label', 'Unknown'))}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': _case_ns(case_id),
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

    # Split a clean "Name (role)" agent into name + per-event role context
    # (study-corrections A7). Composite agents are left intact (role_context
    # None) for the bucket-C pass.
    _agent_name, _role_ctx = split_agent_role(rdf_entity['proeth:hasAgent'])
    if _role_ctx is not None:
        rdf_entity['proeth:hasAgent'] = _agent_name
        rdf_entity['proeth:eventRoleContext'] = _role_ctx
    else:
        # Composite multi-actor string: capture the structured decomposition
        # (study-corrections Phase 4 made this generic, replacing the hand table
        # so Section C decomposes new multi-actor strings). hasAgent is kept as
        # the original string for provenance; consumers prefer proeth:agents.
        _decomp = decompose_agents(rdf_entity['proeth:hasAgent'])
        if _decomp:
            _agents, _relation = _decomp
            rdf_entity['proeth:agents'] = _agents
            if _relation:
                rdf_entity['proeth:agentRelation'] = _relation

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

    # competing_priorities (priority_conflict / resolution_reasoning) was dropped from
    # Step-3 extraction 2026-06-01: a utility audit found it had no real consumer (only a
    # degenerate empty-definition fallback), it was a nested object dropped at commit, and
    # its tension is durably captured by the obligation-level defeasibility edges
    # (competesWith / prevailsOver) + the action's fulfils/violates. See
    # docs-internal/reextraction/review-vs-synthesis-fields.md.

    # Add professional context
    prof_context = action.get('professional_context', {})
    if prof_context:
        rdf_entity['proeth:withinCompetence'] = prof_context.get('within_competence', False)
        if prof_context.get('required_capabilities'):
            rdf_entity['proeth:requiresCapability'] = prof_context['required_capabilities']

    _add_fluent_and_time(rdf_entity, action)
    return rdf_entity


def _add_fluent_and_time(rdf_entity: Dict, src: Dict) -> None:
    """Attach the Event-Calculus fluent transitions and the OWL-Time anchor a happening
    (action or event) carries, shared by the action and event converters.

    - proeth:initiates / proeth:terminates: the State (fluent) labels this happening brings
      into / takes out of holding (Kowalski & Sergot 1986; Berreby et al. 2017). Kept as the
      raw label lists; fluent_edges.py resolves them to the case State individuals and
      materialises proeth-core:initiates / terminates edges at commit.
    - proeth:temporalExtent: the OWL-Time extent classification, "instant" (point
      occurrence, OWL-Time time:Instant) or "interval" (extended, time:ProperInterval). The
      relational ordering is carried by the Allen-relation individuals (time:intervalBefore
      etc., separate individuals) and the discrete order by temporalSequence. A proper
      per-happening time:hasTime -> time:Instant/Interval individual is materialised at
      commit by time_anchor.py: the commit serializer emits only literal and IRI property
      values, so a nested anonymous time entity would not survive (which is why the anchor is
      minted as a separate first-class time individual rather than a nested blank node).
    """
    initiates = src.get('initiates') or []
    terminates = src.get('terminates') or []
    if isinstance(initiates, list) and initiates:
        rdf_entity['proeth:initiates'] = [str(x).strip() for x in initiates if str(x).strip()]
    if isinstance(terminates, list) and terminates:
        rdf_entity['proeth:terminates'] = [str(x).strip() for x in terminates if str(x).strip()]

    extent = (src.get('temporal_extent') or '').strip().lower()
    if extent in ('instant', 'interval'):
        rdf_entity['proeth:temporalExtent'] = extent


def convert_event_to_rdf(event: Dict, case_id: int) -> Dict:
    """
    Convert event dictionary to RDF JSON-LD format.

    Args:
        event: Event data from Stage 4
        case_id: Case ID for URI generation

    Returns:
        RDF JSON-LD dictionary
    """
    event_uri = f"{_case_ns(case_id)}Event_{_safe_id(event.get('label', 'Unknown'))}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': _case_ns(case_id),
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

    # Add classification. eventType is the Event Calculus distinction between agent-caused
    # (outcome), external (exogenous), and precondition-triggered (automatic_trigger)
    # occurrences (Berreby et al. 2017). severity is a heuristic triage indicator of how
    # serious the occurrence is, NOT a formal ontology category. The former separate
    # urgencyLevel field was dropped 2026-05-31: it duplicated severity in every case.
    classification = event.get('classification', {})
    if classification:
        rdf_entity['proeth:eventType'] = classification.get('event_type', 'unknown')
        rdf_entity['proeth:severity'] = classification.get('severity', 'routine')

    # The constraint/obligation consequences of an event are NOT emitted as direct event
    # links: in the Event Calculus an event does not activate a constraint or create an
    # obligation directly, it initiates a STATE (fluent) that then makes the
    # constraint/obligation apply. That grounded two-step path is materialised by
    # fluent_edges.py (Event -> State) + state_edges.py (State activatesConstraint /
    # activatesObligation -> the real Cs/O individual). The former proeth:activatesConstraint
    # / proeth:createsObligation literals named free-text obligations/constraints that
    # resolved to no extracted individual and duplicated that path, dropped 2026-05-31.

    # State change (prose summary of what changed; the structured, grounded form is
    # initiates / terminates, added by _add_fluent_and_time below).
    triggers = event.get('triggers', {})
    if triggers and triggers.get('state_change'):
        rdf_entity['proeth:causesStateChange'] = triggers['state_change']

    # Add causal context
    causal = event.get('causal_context', {})
    if causal and causal.get('caused_by_action'):
        action_ref = f"{_case_ns(case_id)}Action_{_safe_id(causal['caused_by_action'])}"
        rdf_entity['proeth:causedByAction'] = action_ref

    _add_fluent_and_time(rdf_entity, event)
    return rdf_entity


def convert_causal_chain_to_rdf(chain: Dict, case_id: int,
                                chain_index: Optional[int] = None) -> Dict:
    """
    Convert causal chain dictionary to RDF JSON-LD format.

    The CausalChain is reified (it carries the irreducible NESS analysis, the
    causal-language evidence span, and the responsibility attribution), so it gets an
    OPAQUE identifier (case#CausalChain_<n>, the W3C n-ary-relations convention), NOT
    one built from "cause -> effect" prose. The former entity_label-derived committed
    URI concatenated both endpoint labels (and kept a raw -> arrow), producing 90-140
    char IRIs; the cause/effect are properties resolved post-commit by causal_edges.
    The readable "cause -> effect" text stays in entity_label/rdfs:label for display.

    Args:
        chain: Causal chain data from Stage 5
        case_id: Case ID for URI generation
        chain_index: 1-based position in the case's causal-chain list, used for the
            opaque IRI. ``None`` -> a uuid suffix (still short and opaque).

    Returns:
        RDF JSON-LD dictionary
    """
    chain_id = str(chain_index) if chain_index is not None else str(uuid.uuid4())[:8]
    chain_uri = f"{_case_ns(case_id)}CausalChain_{chain_id}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': _case_ns(case_id),
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': chain_uri,
        '@type': 'proeth:CausalChain',
        'proeth:cause': chain.get('cause', 'Unknown'),
        'proeth:effect': chain.get('effect', 'Unknown'),
        'proeth:causalLanguage': chain.get('causal_language', '')
    }

    # Source-section provenance: which case section grounds this causal claim, so the
    # (irreducible) NESS analysis can be audited against the original text. Emitted under
    # proeth:discoveredInSection; the commit serializer routes it to the typed PROV-O
    # predicate. The causalLanguage quote above is the supporting span.
    if chain.get('source_section'):
        rdf_entity['proeth:discoveredInSection'] = chain['source_section']

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
    timeline_uri = f"{_case_ns(case_id)}Timeline"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': _case_ns(case_id),
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


def convert_allen_relation_to_rdf(allen_relation: Dict, case_id: int,
                                  relation_index: Optional[int] = None) -> Dict:
    """
    Convert an Allen relation to RDF JSON-LD as a REIFIED temporal relation node.

    The relation is reified (a proeth:TemporalRelation individual) only because it
    carries metadata of its own -- the verbatim proeth:evidence span, the Allen
    relation name, and the OWL-Time property. This is the W3C "Defining N-ary
    Relations on the Semantic Web" pattern, whose guidance is to give the relation
    instance an OPAQUE/sequential identifier (their `Purchase_1`) and attach the
    participants as PROPERTIES of the node -- never to build the identity out of the
    participant prose. So the IRI is `TemporalRelation_<n>` (n = ``relation_index``,
    1-based, assigned by the caller in extraction order; a short uuid suffix when no
    index is supplied), NOT the former
    `AllenRelation_<fromClause>_<relation>_<toClause>` concatenation.

    The endpoints (entity1/entity2) are NOT resolved to individual URIs here: they
    are free-text timeline phrasings ("Engineer A preparing the summary memo") that
    do not match the noun-phrase Action/Event individuals by string, and the old
    `_safe_id` URIs were both lossy (50-char truncation) and wrong-namespace, so the
    OWL-Time triples silently dangled. The committed individuals are resolved
    post-commit by embedding in
    ``app/services/extraction/temporal_relation_edges.apply_temporal_relation_edges``
    (mirroring the causal-edge appliers), which writes the proeth:fromEntity /
    proeth:toEntity object edges and the time:* triple onto real individuals. So this
    converter emits only the clean labels + metadata that resolver consumes.

    Args:
        allen_relation: Allen relation data from Stage 2
        case_id: Case ID for URI generation
        relation_index: 1-based position in the case's Allen-relation list, used for
            the opaque IRI. ``None`` -> a uuid suffix (still short and opaque).

    Returns:
        RDF JSON-LD dictionary (descriptive fields only; no precomputed endpoint URIs).
    """
    from .allen_owl_time_mapper import create_allen_relation_metadata

    entity1 = allen_relation.get('entity1', 'Unknown')
    entity2 = allen_relation.get('entity2', 'Unknown')
    relation = allen_relation.get('relation', 'unknown')

    # Get OWL-Time mapping
    allen_metadata = create_allen_relation_metadata(relation)

    # Opaque, short, stable identifier (N-ary-relations convention). The readable
    # "entity1 relation entity2" text lives in rdfs:label for display, not the IRI.
    suffix = str(relation_index) if relation_index is not None else str(uuid.uuid4())[:8]
    relation_uri = f"{_case_ns(case_id)}TemporalRelation_{suffix}"

    rdf_entity = {
        '@context': {
            'proeth': 'http://proethica.org/ontology/intermediate#',
            'proeth-case': _case_ns(case_id),
            'time': 'http://www.w3.org/2006/time#',
            'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
            'rdfs': 'http://www.w3.org/2000/01/rdf-schema#'
        },
        '@id': relation_uri,
        '@type': 'proeth:TemporalRelation',
        'rdfs:label': f'{entity1} {relation} {entity2}',

        # Clean endpoint labels (resolved to individuals post-commit by the
        # temporal_relation_edges applier). fromEntity/toEntity are declared
        # owl:ObjectProperty, so these literals land on the fromEntityText/toEntityText
        # datatype siblings at commit until the resolver overwrites with real edges.
        'proeth:fromEntity': entity1,
        'proeth:toEntity': entity2,
        'proeth:allenRelation': relation,

        # OWL-Time standard property name/URI (drives which time:* predicate the
        # resolver emits) and the supporting evidence span + human description.
        'proeth:owlTimeProperty': allen_metadata.get('owl_time_property', ''),
        'proeth:owlTimeURI': allen_metadata.get('owl_time_uri', ''),
        'proeth:evidence': allen_relation.get('evidence', ''),
        'proeth:description': allen_metadata.get('description', '')
    }

    return rdf_entity


def _safe_id(label: str) -> str:
    """Convert label to safe URI identifier."""
    # Remove special characters and replace spaces with underscores
    safe = ''.join(c if c.isalnum() or c in ['_', '-'] else '_' for c in label)
    # Truncate if too long
    return safe[:50]
