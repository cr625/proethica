"""
Temporal Context Service

This service provides methods for working with temporal aspects of entities
in the RDF triple-based structure. It leverages the BFO-based temporal concepts
defined in the ontology to enable temporal reasoning and timeline construction.
"""

import datetime
from typing import List, Dict, Tuple, Optional, Union, Any
from app.services.entity_triple_service import EntityTripleService
from app.models.entity_triple import EntityTriple
from app import db
from sqlalchemy import text, func
from rdflib import Namespace

# BFO namespaces for temporal concepts
BFO = Namespace("http://purl.obolibrary.org/obo/")
PROETHICA = Namespace("http://proethica.org/ontology/")
PROETHICA_INT = Namespace("http://proethica.org/ontology/intermediate#")

class TemporalContextService:
    """
    Service for handling temporal aspects of entity triples,
    including timelines, temporal queries, and temporal relationships.
    """
    
    def __init__(self):
        """Initialize with the EntityTripleService for basic triple operations."""
        self.triple_service = EntityTripleService()
    
    def find_triples_in_timeframe(self, start_time: datetime.datetime, 
                                 end_time: datetime.datetime, 
                                 entity_type: Optional[str] = None, 
                                 scenario_id: Optional[int] = None) -> List[EntityTriple]:
        """
        Find entity triples that are valid within the specified timeframe.
        
        Args:
            start_time: Start of the timeframe
            end_time: End of the timeframe
            entity_type: Optional filter by entity type
            scenario_id: Optional filter by scenario ID
            
        Returns:
            List of EntityTriple objects valid in the timeframe
        """
        query = db.session.query(EntityTriple)
        
        # Time window conditions - handle both instants and intervals
        query = query.filter(
            # Case 1: Triple is an instant within the timeframe
            ((EntityTriple.temporal_end.is_(None)) & 
             (EntityTriple.temporal_start >= start_time) & 
             (EntityTriple.temporal_start <= end_time)) |
            # Case 2: Triple is an interval that overlaps with the timeframe
            ((EntityTriple.temporal_end.isnot(None)) & 
             (EntityTriple.temporal_start <= end_time) & 
             (EntityTriple.temporal_end >= start_time))
        )
        
        if entity_type:
            query = query.filter(EntityTriple.entity_type == entity_type)
        
        if scenario_id:
            query = query.filter(EntityTriple.scenario_id == scenario_id)
        
        return query.all()
    
    def find_temporal_sequence(self, scenario_id: int, 
                             entity_type: Optional[str] = None, 
                             limit: Optional[int] = None) -> List[EntityTriple]:
        """
        Find a sequence of triples ordered by their temporal properties.
        
        Args:
            scenario_id: Scenario ID
            entity_type: Optional filter by entity type
            limit: Maximum number of results
            
        Returns:
            List of EntityTriple objects in temporal order
        """
        query = db.session.query(EntityTriple)
        
        query = query.filter(EntityTriple.scenario_id == scenario_id)
        query = query.filter(EntityTriple.temporal_start.isnot(None))
        
        if entity_type:
            query = query.filter(EntityTriple.entity_type == entity_type)
        
        query = query.order_by(EntityTriple.temporal_start)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    def find_temporal_relations(self, triple_id: int, 
                              relation_type: str) -> List[EntityTriple]:
        """
        Find triples that have a specific temporal relation to a given triple.
        
        Args:
            triple_id: ID of the reference EntityTriple
            relation_type: Type of temporal relation ('precedes', 'follows', etc.)
            
        Returns:
            List of EntityTriple objects with the specified relation
        """
        return EntityTriple.query.filter_by(
            temporal_relation_to=triple_id,
            temporal_relation_type=relation_type
        ).all()
    
    def add_temporal_data_to_triple(self, triple_id: int, 
                                  temporal_type: str, 
                                  start_time: Optional[datetime.datetime] = None,
                                  end_time: Optional[datetime.datetime] = None, 
                                  relation_type: Optional[str] = None, 
                                  relation_to: Optional[int] = None,
                                  granularity: Optional[str] = None) -> EntityTriple:
        """
        Add temporal data to an existing triple.
        
        Args:
            triple_id: ID of the EntityTriple to update
            temporal_type: BFO temporal region type ('BFO_0000038' for interval, 'BFO_0000148' for instant)
            start_time: Start timestamp for interval or timestamp for instant
            end_time: End timestamp for interval (None for instant)
            relation_type: Type of temporal relation ('precedes', 'follows', etc.)
            relation_to: ID of the related EntityTriple
            granularity: Temporal granularity ('seconds', 'minutes', 'days', etc.)
            
        Returns:
            Updated EntityTriple object
        """
        triple = EntityTriple.query.get(triple_id)
        if not triple:
            raise ValueError(f"Triple with ID {triple_id} not found")
        
        triple.temporal_region_type = temporal_type
        triple.temporal_start = start_time
        triple.temporal_end = end_time
        triple.temporal_relation_type = relation_type
        triple.temporal_relation_to = relation_to
        triple.temporal_granularity = granularity
        
        db.session.commit()
        return triple
    
    def enhance_event_with_temporal_data(self, event_id: int, 
                                       event_time: datetime.datetime, 
                                       duration_minutes: Optional[int] = None,
                                       granularity: str = "minutes") -> List[EntityTriple]:
        """
        Enhance an event's triples with temporal data.
        
        Args:
            event_id: ID of the event
            event_time: Timestamp when the event occurred
            duration_minutes: Optional duration (for non-instantaneous events)
            granularity: Temporal granularity
            
        Returns:
            List of updated triples
        """
        # Find all triples related to this event
        triples = self.triple_service.find_triples(entity_type='event', entity_id=event_id)
        updated_triples = []
        
        for triple in triples:
            # Determine temporal region type
            temporal_type = "BFO_0000148"  # zero-dimensional temporal region (instant)
            end_time = None
            
            # If duration is provided, it's an interval
            if duration_minutes:
                temporal_type = "BFO_0000038"  # one-dimensional temporal region (interval)
                end_time = event_time + datetime.timedelta(minutes=duration_minutes)
            
            # Update the triple with temporal data
            triple.temporal_region_type = temporal_type
            triple.temporal_start = event_time
            triple.temporal_end = end_time
            triple.temporal_granularity = granularity
            
            updated_triples.append(triple)
        
        db.session.commit()
        return updated_triples
    
    def enhance_action_with_temporal_data(self, action_id: int, 
                                        action_time: datetime.datetime, 
                                        duration_minutes: Optional[int] = None,
                                        is_decision: bool = False,
                                        granularity: str = "minutes") -> List[EntityTriple]:
        """
        Enhance an action's triples with temporal data.
        
        Args:
            action_id: ID of the action
            action_time: Timestamp when the action occurred
            duration_minutes: Optional duration (for non-instantaneous actions)
            is_decision: Whether this action is a decision
            granularity: Temporal granularity
            
        Returns:
            List of updated triples
        """
        # Find all triples related to this action
        triples = self.triple_service.find_triples(entity_type='action', entity_id=action_id)
        updated_triples = []
        
        for triple in triples:
            # Decisions are typically instantaneous
            if is_decision:
                temporal_type = "BFO_0000148"  # zero-dimensional temporal region (instant)
                end_time = None
            else:
                # Regular actions might have duration
                if duration_minutes:
                    temporal_type = "BFO_0000038"  # one-dimensional temporal region (interval)
                    end_time = action_time + datetime.timedelta(minutes=duration_minutes)
                else:
                    temporal_type = "BFO_0000148"  # zero-dimensional temporal region (instant)
                    end_time = None
            
            # Update the triple with temporal data
            triple.temporal_region_type = temporal_type
            triple.temporal_start = action_time
            triple.temporal_end = end_time
            triple.temporal_granularity = granularity
            
            updated_triples.append(triple)
        
        db.session.commit()
        return updated_triples
    
    def create_temporal_relation(self, from_triple_id: int, 
                               to_triple_id: int, 
                               relation_type: str) -> bool:
        """
        Create a temporal relation between two triples.
        
        Args:
            from_triple_id: ID of the source triple
            to_triple_id: ID of the target triple
            relation_type: Type of temporal relation ('precedes', 'follows', etc.)
            
        Returns:
            True if successful, False otherwise
        """
        from_triple = EntityTriple.query.get(from_triple_id)
        to_triple = EntityTriple.query.get(to_triple_id)
        
        if not from_triple or not to_triple:
            return False
        
        from_triple.temporal_relation_type = relation_type
        from_triple.temporal_relation_to = to_triple_id
        
        db.session.commit()
        return True
    
    def build_timeline(self, scenario_id: int) -> Dict[str, Any]:
        """
        Build a complete timeline representation for a scenario.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            Dictionary representing the timeline with events, actions, and decisions
        """
        # Get all event triples for the scenario
        event_triples = self.triple_service.find_triples(
            entity_type='event',
            scenario_id=scenario_id
        )
        
        # Get all action triples for the scenario
        action_triples = self.triple_service.find_triples(
            entity_type='action',
            scenario_id=scenario_id
        )
        
        # Extract events with temporal data
        events = []
        for triple in event_triples:
            # Use only triples that represent the event itself (not its properties)
            if triple.predicate == str(PROETHICA.occursAt):
                event_data = {
                    'id': triple.entity_id,
                    'time': triple.temporal_start,
                    'end_time': triple.temporal_end,
                    'description': triple.object_literal or "Unnamed event"
                }
                events.append(event_data)
        
        # Extract actions with temporal data
        actions = []
        decisions = []
        
        for triple in action_triples:
            # Check if this is a decision
            is_decision = False
            if triple.predicate == str(PROETHICA.type) and "Decision" in triple.object_uri:
                is_decision = True
            
            # Use only triples that represent the action itself (not its properties)
            if triple.predicate == str(PROETHICA.occursAt):
                action_data = {
                    'id': triple.entity_id,
                    'time': triple.temporal_start,
                    'end_time': triple.temporal_end,
                    'description': triple.object_literal or "Unnamed action"
                }
                
                if is_decision:
                    # Get decision options from other triples
                    option_triples = self.triple_service.find_triples(
                        entity_type='action',
                        entity_id=triple.entity_id,
                        predicate=str(PROETHICA_INT.decisionAlternatives)
                    )
                    
                    if option_triples:
                        action_data['options'] = option_triples[0].object_literal
                    
                    # Get selected option
                    selected_option_triples = self.triple_service.find_triples(
                        entity_type='action',
                        entity_id=triple.entity_id,
                        predicate=str(PROETHICA_INT.hasSelectedOption)
                    )
                    
                    if selected_option_triples:
                        action_data['selected_option'] = selected_option_triples[0].object_literal
                    
                    decisions.append(action_data)
                else:
                    actions.append(action_data)
        
        # Sort all items by time
        events.sort(key=lambda x: x['time'] if x['time'] else datetime.datetime.min)
        actions.sort(key=lambda x: x['time'] if x['time'] else datetime.datetime.min)
        decisions.sort(key=lambda x: x['time'] if x['time'] else datetime.datetime.min)
        
        # Combine into a timeline
        timeline = {
            'scenario_id': scenario_id,
            'events': events,
            'actions': actions,
            'decisions': decisions
        }
        
        return timeline
    
    def get_temporal_context_for_claude(self, scenario_id: int) -> str:
        """
        Generate a structured context about the timeline for Claude.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            String context with timeline information
        """
        timeline = self.build_timeline(scenario_id)
        
        # Merge all items for sequential timeline
        all_items = []
        
        for event in timeline['events']:
            all_items.append({
                'type': 'event',
                'time': event['time'],
                'end_time': event.get('end_time'),
                'description': event['description']
            })
        
        for action in timeline['actions']:
            all_items.append({
                'type': 'action',
                'time': action['time'],
                'end_time': action.get('end_time'),
                'description': action['description']
            })
        
        for decision in timeline['decisions']:
            all_items.append({
                'type': 'decision',
                'time': decision['time'],
                'end_time': decision.get('end_time'),
                'description': decision['description'],
                'options': decision.get('options', []),
                'selected_option': decision.get('selected_option')
            })
        
        # Sort all items by time
        all_items.sort(key=lambda x: x['time'] if x['time'] else datetime.datetime.min)
        
        # Build a natural language context
        context = f"Timeline for Scenario {scenario_id}:\n\n"
        
        for i, item in enumerate(all_items):
            time_str = item['time'].strftime('%Y-%m-%d %H:%M:%S') if item['time'] else "Unknown time"
            
            if item['end_time']:
                end_time_str = item['end_time'].strftime('%Y-%m-%d %H:%M:%S')
                context += f"{i+1}. [{time_str} to {end_time_str}] {item['type'].upper()}: {item['description']}\n"
            else:
                context += f"{i+1}. [{time_str}] {item['type'].upper()}: {item['description']}\n"
            
            if item['type'] == 'decision' and 'options' in item and 'selected_option' in item:
                context += "   Options:\n"
                for opt_id, opt_data in item.get('options', {}).items():
                    selected = " (SELECTED)" if opt_id == item.get('selected_option') else ""
                    description = opt_data.get('description', 'No description')
                    context += f"   - {opt_id}: {description}{selected}\n"
            
            context += "\n"
        
        # Add temporal relationships
        if len(all_items) > 1:
            context += "\nTemporal Relationships:\n"
            
            # For each item, describe its relationship to adjacent items
            for i in range(len(all_items) - 1):
                current = all_items[i]
                next_item = all_items[i+1]
                
                context += f"- {current['description']} occurs before {next_item['description']}\n"
                
                # For decisions, show consequences
                if current['type'] == 'decision' and i < len(all_items) - 1:
                    if 'selected_option' in current and current['selected_option']:
                        context += f"  The decision to {current['selected_option']} leads to {next_item['description']}\n"
        
        return context
