"""
Temporal Reasoning Service: Enhanced BFO-based temporal modeling for ProEthica.

This service implements comprehensive temporal reasoning using Basic Formal Ontology (BFO)
concepts, Allen's interval algebra, and process profiles for case analysis.

Key Features:
- BFO temporal boundary tracking (BFO_0000011)
- Allen's interval algebra for event relationships
- Temporal graph structures for process profiles
- Agent succession relation tracking
- Temporal constraint propagation
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from app.models import Event, Action, Character
from app.services.bfo_service import BFOService

logger = logging.getLogger(__name__)

# Allen's Interval Algebra Relations
class AllenRelation(Enum):
    """Allen's 13 temporal relations between intervals."""
    BEFORE = "before"           # X < Y
    AFTER = "after"             # X > Y
    MEETS = "meets"             # X meets Y
    MET_BY = "met_by"           # X met by Y
    OVERLAPS = "overlaps"       # X overlaps Y
    OVERLAPPED_BY = "overlapped_by"  # X overlapped by Y
    STARTS = "starts"           # X starts Y
    STARTED_BY = "started_by"   # X started by Y
    DURING = "during"           # X during Y
    CONTAINS = "contains"       # X contains Y
    FINISHES = "finishes"       # X finishes Y
    FINISHED_BY = "finished_by" # X finished by Y
    EQUALS = "equals"           # X equals Y


class TemporalBoundaryType(Enum):
    """Types of temporal boundaries in ethics cases."""
    DECISION_POINT = "decision_point"       # Critical decision moments
    KNOWLEDGE_ACQUISITION = "knowledge_acquisition"  # Learning new information
    ROLE_TRANSITION = "role_transition"    # Agent role changes
    DEADLINE = "deadline"                  # Time constraints
    ESCALATION = "escalation"              # Issue escalation points
    CONSEQUENCE_MANIFESTATION = "consequence_manifestation"  # Results become apparent


@dataclass
class TemporalBoundary:
    """Represents a BFO temporal boundary (BFO_0000011) in the case."""
    boundary_id: str
    timestamp: datetime
    boundary_type: TemporalBoundaryType
    description: str
    triggering_event: Optional[str] = None
    affected_agents: List[str] = field(default_factory=list)
    state_changes: List[str] = field(default_factory=list)
    ethical_significance: float = 0.0  # 0-1 importance score
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'boundary_id': self.boundary_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'boundary_type': self.boundary_type.value,
            'description': self.description,
            'triggering_event': self.triggering_event,
            'affected_agents': self.affected_agents,
            'state_changes': self.state_changes,
            'ethical_significance': self.ethical_significance
        }


@dataclass
class TemporalRelation:
    """Allen relation between two temporal entities."""
    source_entity: str
    target_entity: str
    relation: AllenRelation
    confidence: float = 0.0  # 0-1 confidence in this relation
    evidence: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'source_entity': self.source_entity,
            'target_entity': self.target_entity,
            'relation': self.relation.value,
            'confidence': self.confidence,
            'evidence': self.evidence
        }


@dataclass
class ProcessProfile:
    """BFO process profile for a complete case."""
    process_id: str
    case_id: int
    temporal_boundaries: List[TemporalBoundary] = field(default_factory=list)
    temporal_relations: List[TemporalRelation] = field(default_factory=list)
    process_phases: List[Dict[str, Any]] = field(default_factory=list)
    agent_succession: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    critical_path: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'process_id': self.process_id,
            'case_id': self.case_id,
            'temporal_boundaries': [b.to_dict() for b in self.temporal_boundaries],
            'temporal_relations': [r.to_dict() for r in self.temporal_relations],
            'process_phases': self.process_phases,
            'agent_succession': self.agent_succession,
            'critical_path': self.critical_path
        }


@dataclass
class AgentState:
    """State of an agent at a specific time."""
    agent_id: str
    timestamp: datetime
    role: str
    knowledge_state: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    authority_level: float = 0.0  # 0-1 authority level
    ethical_stance: str = "neutral"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'role': self.role,
            'knowledge_state': self.knowledge_state,
            'capabilities': self.capabilities,
            'constraints': self.constraints,
            'authority_level': self.authority_level,
            'ethical_stance': self.ethical_stance
        }


class TemporalReasoningService:
    """Service for BFO-based temporal reasoning and process modeling."""
    
    def __init__(self):
        self.bfo_service = BFOService()
        self.allen_relation_matrix = self._build_allen_relation_matrix()
        
    def extract_temporal_boundaries(self, events: List[Dict[str, Any]], 
                                  case_content: str) -> List[TemporalBoundary]:
        """
        Extract temporal boundaries (BFO_0000011) from case events.
        
        Args:
            events: List of events from scenario generation
            case_content: Original case text for context
            
        Returns:
            List of TemporalBoundary objects
        """
        boundaries = []
        
        # Extract decision points as temporal boundaries
        decision_events = [e for e in events if e.get('kind') == 'decision']
        for i, event in enumerate(decision_events):
            boundary = TemporalBoundary(
                boundary_id=f"decision_boundary_{i+1}",
                timestamp=self._extract_timestamp(event),
                boundary_type=TemporalBoundaryType.DECISION_POINT,
                description=event.get('text', f"Decision point {i+1}"),
                triggering_event=event.get('id'),
                ethical_significance=self._calculate_ethical_significance(event, case_content)
            )
            boundaries.append(boundary)
        
        # Extract knowledge acquisition points
        knowledge_boundaries = self._extract_knowledge_boundaries(events, case_content)
        boundaries.extend(knowledge_boundaries)
        
        # Extract role transition points
        role_boundaries = self._extract_role_boundaries(events, case_content)
        boundaries.extend(role_boundaries)
        
        # Extract deadline boundaries
        deadline_boundaries = self._extract_deadline_boundaries(events, case_content)
        boundaries.extend(deadline_boundaries)
        
        # Sort by timestamp
        boundaries.sort(key=lambda b: b.timestamp or datetime.min)
        
        logger.info(f"Extracted {len(boundaries)} temporal boundaries")
        return boundaries
    
    def calculate_temporal_relations(self, events: List[Dict[str, Any]]) -> List[TemporalRelation]:
        """
        Calculate Allen's interval relations between events.
        
        Args:
            events: List of events with temporal information
            
        Returns:
            List of TemporalRelation objects
        """
        relations = []
        
        # Convert events to temporal intervals
        intervals = self._convert_events_to_intervals(events)
        
        # Calculate pairwise relations
        for i, interval_a in enumerate(intervals):
            for j, interval_b in enumerate(intervals):
                if i != j:  # Don't compare event to itself
                    relation = self._determine_allen_relation(interval_a, interval_b)
                    if relation:
                        relations.append(relation)
        
        # Filter to only significant relations
        significant_relations = self._filter_significant_relations(relations)
        
        logger.info(f"Calculated {len(significant_relations)} temporal relations")
        return significant_relations
    
    def build_process_profile(self, case_id: int, events: List[Dict[str, Any]], 
                            case_content: str) -> ProcessProfile:
        """
        Build a comprehensive BFO process profile for the case.
        
        Args:
            case_id: Database ID of the case
            events: List of events from scenario generation
            case_content: Original case text
            
        Returns:
            ProcessProfile object
        """
        process_id = f"process_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Extract temporal components
        boundaries = self.extract_temporal_boundaries(events, case_content)
        relations = self.calculate_temporal_relations(events)
        
        # Identify process phases
        phases = self._identify_process_phases(events, boundaries)
        
        # Track agent succession
        agent_succession = self._track_agent_succession(events, boundaries)
        
        # Calculate critical path
        critical_path = self._calculate_critical_path(events, boundaries, relations)
        
        profile = ProcessProfile(
            process_id=process_id,
            case_id=case_id,
            temporal_boundaries=boundaries,
            temporal_relations=relations,
            process_phases=phases,
            agent_succession=agent_succession,
            critical_path=critical_path
        )
        
        logger.info(f"Built process profile {process_id} with {len(boundaries)} boundaries, "
                   f"{len(relations)} relations, {len(phases)} phases")
        
        return profile
    
    def analyze_succession_relations(self, agents: List[Dict[str, Any]], 
                                   events: List[Dict[str, Any]]) -> Dict[str, List[AgentState]]:
        """
        Analyze how agents and their roles evolve over time.
        
        Args:
            agents: List of agents/characters in the case
            events: List of events with temporal information
            
        Returns:
            Dictionary mapping agent IDs to their state timeline
        """
        succession_analysis = {}
        
        for agent in agents:
            agent_id = agent.get('name', agent.get('id', 'unknown'))
            agent_timeline = self._build_agent_timeline(agent, events)
            succession_analysis[agent_id] = agent_timeline
        
        # Detect role transitions and capability changes
        for agent_id, timeline in succession_analysis.items():
            self._detect_agent_transitions(timeline, events)
        
        logger.info(f"Analyzed succession relations for {len(agents)} agents")
        return succession_analysis
    
    def enhance_events_with_temporal_data(self, events: List[Dict[str, Any]], 
                                        process_profile: ProcessProfile) -> List[Dict[str, Any]]:
        """
        Enhance events with rich temporal metadata from process profile.
        
        Args:
            events: List of events to enhance
            process_profile: Process profile with temporal information
            
        Returns:
            Enhanced events with temporal metadata
        """
        enhanced_events = []
        
        for event in events:
            enhanced_event = event.copy()
            
            # Add temporal boundaries
            related_boundaries = self._find_related_boundaries(event, process_profile.temporal_boundaries)
            enhanced_event['temporal_boundaries'] = [b.to_dict() for b in related_boundaries]
            
            # Add temporal relations
            related_relations = self._find_related_relations(event, process_profile.temporal_relations)
            enhanced_event['temporal_relations'] = [r.to_dict() for r in related_relations]
            
            # Add process phase information
            phase_info = self._find_event_phase(event, process_profile.process_phases)
            if phase_info:
                enhanced_event['process_phase'] = phase_info
            
            # Add BFO temporal classification
            enhanced_event['bfo_temporal_class'] = self._classify_event_temporally(event)
            
            enhanced_events.append(enhanced_event)
        
        logger.info(f"Enhanced {len(events)} events with temporal data")
        return enhanced_events
    
    # Private helper methods
    
    def _build_allen_relation_matrix(self) -> Dict[str, Set[str]]:
        """Build matrix of valid Allen relation combinations."""
        # This would contain the transitivity rules for Allen's algebra
        # For now, returning a simplified version
        return {
            "before": {"before", "meets", "overlaps", "finishes", "during"},
            "after": {"after", "met_by", "overlapped_by", "starts", "contains"},
            # ... (full matrix would be quite large)
        }
    
    def _extract_timestamp(self, event: Dict[str, Any]) -> datetime:
        """Extract or infer timestamp from event data."""
        # Try to get explicit timestamp
        if 'timestamp' in event and event['timestamp']:
            if isinstance(event['timestamp'], str):
                try:
                    return datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                except ValueError:
                    pass
            elif isinstance(event['timestamp'], datetime):
                return event['timestamp']
        
        # Try to get sequence-based timestamp
        sequence = event.get('sequence_number', event.get('sequence', 0))
        if sequence > 0:
            # Create artificial timestamp based on sequence
            base_time = datetime(2024, 1, 1, 9, 0, 0)  # Start of business day
            return base_time + timedelta(hours=sequence)
        
        # Default to current time
        return datetime.now()
    
    def _calculate_ethical_significance(self, event: Dict[str, Any], case_content: str) -> float:
        """Calculate the ethical significance of an event (0-1)."""
        significance = 0.5  # Base significance
        
        # Higher significance for decisions
        if event.get('kind') == 'decision':
            significance += 0.3
        
        # Higher significance for events mentioning key ethical concepts
        text = event.get('text', '').lower()
        ethical_keywords = ['safety', 'public', 'disclosure', 'conflict', 'responsibility', 
                          'duty', 'harm', 'risk', 'ethical', 'professional', 'code']
        
        keyword_count = sum(1 for keyword in ethical_keywords if keyword in text)
        significance += min(keyword_count * 0.1, 0.4)
        
        # Higher significance for events with multiple stakeholders
        stakeholder_count = len(event.get('stakeholders', []))
        if stakeholder_count > 1:
            significance += min(stakeholder_count * 0.05, 0.2)
        
        return min(significance, 1.0)
    
    def _extract_knowledge_boundaries(self, events: List[Dict[str, Any]], 
                                    case_content: str) -> List[TemporalBoundary]:
        """Extract points where agents gain new knowledge."""
        boundaries = []
        
        knowledge_indicators = ['learned', 'discovered', 'found out', 'realized', 'became aware']
        
        for i, event in enumerate(events):
            text = event.get('text', '').lower()
            if any(indicator in text for indicator in knowledge_indicators):
                boundary = TemporalBoundary(
                    boundary_id=f"knowledge_boundary_{i+1}",
                    timestamp=self._extract_timestamp(event),
                    boundary_type=TemporalBoundaryType.KNOWLEDGE_ACQUISITION,
                    description=f"Knowledge acquisition: {event.get('text', '')[:100]}",
                    triggering_event=event.get('id'),
                    ethical_significance=0.6  # Knowledge often ethically significant
                )
                boundaries.append(boundary)
        
        return boundaries
    
    def _extract_role_boundaries(self, events: List[Dict[str, Any]], 
                               case_content: str) -> List[TemporalBoundary]:
        """Extract points where agent roles change."""
        boundaries = []
        
        role_indicators = ['promoted', 'assigned', 'became', 'appointed', 'replaced', 'role']
        
        for i, event in enumerate(events):
            text = event.get('text', '').lower()
            if any(indicator in text for indicator in role_indicators):
                boundary = TemporalBoundary(
                    boundary_id=f"role_boundary_{i+1}",
                    timestamp=self._extract_timestamp(event),
                    boundary_type=TemporalBoundaryType.ROLE_TRANSITION,
                    description=f"Role transition: {event.get('text', '')[:100]}",
                    triggering_event=event.get('id'),
                    ethical_significance=0.7  # Role changes often ethically significant
                )
                boundaries.append(boundary)
        
        return boundaries
    
    def _extract_deadline_boundaries(self, events: List[Dict[str, Any]], 
                                   case_content: str) -> List[TemporalBoundary]:
        """Extract deadline and time constraint boundaries."""
        boundaries = []
        
        deadline_indicators = ['deadline', 'due', 'must complete', 'time limit', 'urgently']
        
        for i, event in enumerate(events):
            text = event.get('text', '').lower()
            if any(indicator in text for indicator in deadline_indicators):
                boundary = TemporalBoundary(
                    boundary_id=f"deadline_boundary_{i+1}",
                    timestamp=self._extract_timestamp(event),
                    boundary_type=TemporalBoundaryType.DEADLINE,
                    description=f"Deadline constraint: {event.get('text', '')[:100]}",
                    triggering_event=event.get('id'),
                    ethical_significance=0.5  # Deadlines create ethical pressure
                )
                boundaries.append(boundary)
        
        return boundaries
    
    def _convert_events_to_intervals(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert events to temporal intervals for Allen relation calculation."""
        intervals = []
        
        for event in events:
            start_time = self._extract_timestamp(event)
            
            # Estimate duration based on event type
            if event.get('kind') == 'decision':
                # Decisions are typically instantaneous
                end_time = start_time
            else:
                # Other events have some duration
                duration_minutes = event.get('duration', 30)  # Default 30 minutes
                end_time = start_time + timedelta(minutes=duration_minutes)
            
            intervals.append({
                'event_id': event.get('id'),
                'start': start_time,
                'end': end_time,
                'event': event
            })
        
        return intervals
    
    def _determine_allen_relation(self, interval_a: Dict[str, Any], 
                                interval_b: Dict[str, Any]) -> Optional[TemporalRelation]:
        """Determine Allen relation between two intervals."""
        start_a, end_a = interval_a['start'], interval_a['end']
        start_b, end_b = interval_b['start'], interval_b['end']
        
        # Handle instantaneous events (decisions)
        if start_a == end_a and start_b == end_b:
            # Both are points
            if start_a < start_b:
                relation = AllenRelation.BEFORE
            elif start_a > start_b:
                relation = AllenRelation.AFTER
            else:
                relation = AllenRelation.EQUALS
        elif start_a == end_a:
            # A is point, B is interval
            if start_a < start_b:
                relation = AllenRelation.BEFORE
            elif start_a > end_b:
                relation = AllenRelation.AFTER
            elif start_a == start_b:
                relation = AllenRelation.STARTS
            elif start_a == end_b:
                relation = AllenRelation.FINISHES
            else:
                relation = AllenRelation.DURING
        elif start_b == end_b:
            # B is point, A is interval
            if start_b < start_a:
                relation = AllenRelation.AFTER
            elif start_b > end_a:
                relation = AllenRelation.BEFORE
            elif start_b == start_a:
                relation = AllenRelation.STARTED_BY
            elif start_b == end_a:
                relation = AllenRelation.FINISHED_BY
            else:
                relation = AllenRelation.CONTAINS
        else:
            # Both are intervals - full Allen relation calculation
            if end_a < start_b:
                relation = AllenRelation.BEFORE
            elif start_a > end_b:
                relation = AllenRelation.AFTER
            elif end_a == start_b:
                relation = AllenRelation.MEETS
            elif start_a == end_b:
                relation = AllenRelation.MET_BY
            elif start_a == start_b and end_a == end_b:
                relation = AllenRelation.EQUALS
            elif start_a == start_b and end_a < end_b:
                relation = AllenRelation.STARTS
            elif start_a == start_b and end_a > end_b:
                relation = AllenRelation.STARTED_BY
            elif start_a > start_b and end_a == end_b:
                relation = AllenRelation.FINISHES
            elif start_a < start_b and end_a == end_b:
                relation = AllenRelation.FINISHED_BY
            elif start_a > start_b and end_a < end_b:
                relation = AllenRelation.DURING
            elif start_a < start_b and end_a > end_b:
                relation = AllenRelation.CONTAINS
            elif start_a < start_b and end_a > start_b and end_a < end_b:
                relation = AllenRelation.OVERLAPS
            elif start_a > start_b and start_a < end_b and end_a > end_b:
                relation = AllenRelation.OVERLAPPED_BY
            else:
                return None
        
        return TemporalRelation(
            source_entity=interval_a['event_id'],
            target_entity=interval_b['event_id'],
            relation=relation,
            confidence=0.8  # Default confidence
        )
    
    def _filter_significant_relations(self, relations: List[TemporalRelation]) -> List[TemporalRelation]:
        """Filter to only include significant temporal relations."""
        # Keep direct precedence relations and contains/during relations
        significant = []
        
        for relation in relations:
            if relation.relation in [AllenRelation.BEFORE, AllenRelation.AFTER, 
                                   AllenRelation.MEETS, AllenRelation.MET_BY,
                                   AllenRelation.CONTAINS, AllenRelation.DURING]:
                significant.append(relation)
        
        return significant
    
    def _identify_process_phases(self, events: List[Dict[str, Any]], 
                               boundaries: List[TemporalBoundary]) -> List[Dict[str, Any]]:
        """Identify distinct phases in the process."""
        phases = []
        
        # Sort events and boundaries by time
        all_items = []
        for event in events:
            all_items.append(('event', event, self._extract_timestamp(event)))
        for boundary in boundaries:
            all_items.append(('boundary', boundary, boundary.timestamp))
        
        all_items.sort(key=lambda x: x[2])
        
        current_phase = {
            'phase_id': 'initial',
            'phase_name': 'Initial Phase',
            'start_time': all_items[0][2] if all_items else datetime.now(),
            'events': [],
            'boundaries': [],
            'characteristics': []
        }
        
        phase_counter = 1
        
        for item_type, item, timestamp in all_items:
            current_phase['events' if item_type == 'event' else 'boundaries'].append(
                item.get('id') if item_type == 'event' else item.boundary_id
            )
            
            # Start new phase on significant boundaries
            if (item_type == 'boundary' and 
                item.boundary_type in [TemporalBoundaryType.DECISION_POINT, 
                                     TemporalBoundaryType.ROLE_TRANSITION] and
                len(current_phase['events']) > 0):
                
                current_phase['end_time'] = timestamp
                phases.append(current_phase)
                
                phase_counter += 1
                current_phase = {
                    'phase_id': f'phase_{phase_counter}',
                    'phase_name': f'Phase {phase_counter}',
                    'start_time': timestamp,
                    'events': [],
                    'boundaries': [],
                    'characteristics': []
                }
        
        # Close final phase
        if current_phase['events'] or current_phase['boundaries']:
            current_phase['end_time'] = all_items[-1][2] if all_items else datetime.now()
            phases.append(current_phase)
        
        return phases
    
    def _track_agent_succession(self, events: List[Dict[str, Any]], 
                              boundaries: List[TemporalBoundary]) -> Dict[str, List[Dict[str, Any]]]:
        """Track how agents succeed each other in roles over time."""
        succession = defaultdict(list)
        
        # Extract agent mentions from events
        for event in events:
            # This would need more sophisticated NLP to properly extract agents
            # For now, using simple heuristics
            text = event.get('text', '')
            
            # Look for agent patterns
            if 'engineer' in text.lower():
                succession['primary_engineer'].append({
                    'timestamp': self._extract_timestamp(event),
                    'event_id': event.get('id'),
                    'role': 'engineer',
                    'action': text[:100]
                })
            
            if 'supervisor' in text.lower() or 'manager' in text.lower():
                succession['supervisor'].append({
                    'timestamp': self._extract_timestamp(event),
                    'event_id': event.get('id'),
                    'role': 'supervisor',
                    'action': text[:100]
                })
        
        return dict(succession)
    
    def _calculate_critical_path(self, events: List[Dict[str, Any]], 
                               boundaries: List[TemporalBoundary],
                               relations: List[TemporalRelation]) -> List[str]:
        """Calculate critical path through the case process."""
        # Simplified critical path - sequence of decision points
        decision_events = [e for e in events if e.get('kind') == 'decision']
        critical_path = [e.get('id') for e in decision_events]
        
        # Add high-significance boundaries
        high_sig_boundaries = [b for b in boundaries if b.ethical_significance > 0.7]
        critical_path.extend([b.boundary_id for b in high_sig_boundaries])
        
        return critical_path
    
    def _build_agent_timeline(self, agent: Dict[str, Any], 
                            events: List[Dict[str, Any]]) -> List[AgentState]:
        """Build timeline of states for a specific agent."""
        timeline = []
        agent_id = agent.get('name', agent.get('id', 'unknown'))
        
        # Find events involving this agent
        agent_events = []
        for event in events:
            text = event.get('text', '').lower()
            if agent_id.lower() in text:
                agent_events.append(event)
        
        # Create states from events
        for event in agent_events:
            state = AgentState(
                agent_id=agent_id,
                timestamp=self._extract_timestamp(event),
                role=agent.get('role', 'unknown'),
                knowledge_state=[],  # Would be inferred from event content
                capabilities=agent.get('capabilities', []),
                authority_level=agent.get('authority_level', 0.5)
            )
            timeline.append(state)
        
        return timeline
    
    def _detect_agent_transitions(self, timeline: List[AgentState], 
                                events: List[Dict[str, Any]]) -> None:
        """Detect role transitions and capability changes in agent timeline."""
        # This would analyze the timeline to detect changes
        # For now, just a placeholder
        pass
    
    def _find_related_boundaries(self, event: Dict[str, Any], 
                               boundaries: List[TemporalBoundary]) -> List[TemporalBoundary]:
        """Find temporal boundaries related to an event."""
        related = []
        event_id = event.get('id')
        
        for boundary in boundaries:
            if boundary.triggering_event == event_id:
                related.append(boundary)
        
        return related
    
    def _find_related_relations(self, event: Dict[str, Any], 
                              relations: List[TemporalRelation]) -> List[TemporalRelation]:
        """Find temporal relations involving an event."""
        related = []
        event_id = event.get('id')
        
        for relation in relations:
            if relation.source_entity == event_id or relation.target_entity == event_id:
                related.append(relation)
        
        return related
    
    def _find_event_phase(self, event: Dict[str, Any], 
                        phases: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Find which process phase an event belongs to."""
        event_id = event.get('id')
        
        for phase in phases:
            if event_id in phase.get('events', []):
                return {
                    'phase_id': phase['phase_id'],
                    'phase_name': phase['phase_name'],
                    'phase_start': phase['start_time'].isoformat() if 'start_time' in phase else None
                }
        
        return None
    
    def _classify_event_temporally(self, event: Dict[str, Any]) -> str:
        """Classify event using BFO temporal concepts."""
        kind = event.get('kind', 'event')
        
        if kind == 'decision':
            return 'BFO_0000148'  # zero-dimensional temporal region (instant)
        elif kind == 'action':
            return 'BFO_0000038'  # one-dimensional temporal region (interval)
        elif kind == 'event':
            return 'BFO_0000015'  # process
        else:
            return 'BFO_0000008'  # temporal region (general)
