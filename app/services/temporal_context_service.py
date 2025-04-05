#!/usr/bin/env python
"""
TemporalContextService: Service for temporal operations on entities.

This service provides functionality for working with the temporal aspects
of entity triples, including querying based on time, building timelines,
and generating temporal context for Claude.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union, Tuple
from sqlalchemy import and_, or_, desc, asc

from app import db
from app.models.entity_triple import EntityTriple
from app.models.event import Event, Action
from app.services.entity_triple_service import EntityTripleService
from app.services.bfo_service import BFOService
from rdflib import Namespace, URIRef, Literal, Graph

# Define BFO namespace
BFO = Namespace("http://purl.obolibrary.org/obo/")
PROETHICA = Namespace("http://proethica.org/ontology/")
PROETHICA_INT = Namespace("http://proethica.org/ontology/intermediate#")


class TemporalContextService:
    """Service for temporal operations on entity triples."""

    def __init__(self):
        """Initialize the service."""
        self.triple_service = EntityTripleService()
        self.bfo_service = BFOService()

    def enhance_event_with_temporal_data(
        self, event_id: int, event_time: datetime, duration_minutes: Optional[int] = None
    ) -> bool:
        """
        Add temporal data to an event's entity triples.
        
        Args:
            event_id: ID of the event
            event_time: Timestamp of the event
            duration_minutes: Optional duration in minutes
            
        Returns:
            bool: Success indicator
        """
        try:
            # Find the event triples
            event_triples = self.triple_service.find_triples(
                entity_type="event", entity_id=event_id
            )
            
            if not event_triples:
                return False
                
            for triple in event_triples:
                # Determine temporal region type based on duration
                if duration_minutes and duration_minutes > 0:
                    # Events with duration are 1D temporal regions
                    region_type = str(BFO.BFO_0000038)  # 1D temporal region
                    temporal_end = event_time + timedelta(minutes=duration_minutes)
                else:
                    # Events without duration are 0D temporal regions (instants)
                    region_type = str(BFO.BFO_0000148)  # 0D temporal region
                    temporal_end = None
                
                # Update the triple with temporal data
                triple.temporal_region_type = region_type
                triple.temporal_start = event_time
                triple.temporal_end = temporal_end
                triple.temporal_granularity = "minutes"
                
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error enhancing event with temporal data: {str(e)}")
            return False

    def enhance_action_with_temporal_data(
        self, action_id: int, action_time: datetime, 
        duration_minutes: Optional[int] = None, is_decision: bool = False
    ) -> bool:
        """
        Add temporal data to an action's entity triples.
        
        Args:
            action_id: ID of the action
            action_time: Timestamp of the action
            duration_minutes: Optional duration in minutes
            is_decision: Whether this is a decision action
            
        Returns:
            bool: Success indicator
        """
        try:
            # Find the action triples
            action_triples = self.triple_service.find_triples(
                entity_type="action", entity_id=action_id
            )
            
            if not action_triples:
                return False
                
            for triple in action_triples:
                # Decisions are typically treated as instantaneous (0D)
                # Regular actions with duration are 1D temporal regions
                if is_decision or not duration_minutes or duration_minutes <= 0:
                    region_type = str(BFO.BFO_0000148)  # 0D temporal region
                    temporal_end = None
                else:
                    region_type = str(BFO.BFO_0000038)  # 1D temporal region
                    temporal_end = action_time + timedelta(minutes=duration_minutes)
                
                # Update the triple with temporal data
                triple.temporal_region_type = region_type
                triple.temporal_start = action_time
                triple.temporal_end = temporal_end
                
                # Use a finer granularity for decisions which often happen in sequence
                triple.temporal_granularity = "seconds" if is_decision else "minutes"
                
                # For decision triples, add additional metadata in the RDF
                if is_decision:
                    # This would involve retrieving or creating additional BFO metadata
                    # about the decision process, options, and outcomes
                    pass
                    
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error enhancing action with temporal data: {str(e)}")
            return False

    def create_temporal_relation(
        self, from_triple_id: int, to_triple_id: int, relation_type: str
    ) -> bool:
        """
        Create a temporal relation between two entity triples.
        
        Args:
            from_triple_id: ID of the source triple
            to_triple_id: ID of the target triple
            relation_type: Type of temporal relation (precedes, follows, etc.)
            
        Returns:
            bool: Success indicator
        """
        try:
            # Verify the triples exist
            from_triple = EntityTriple.query.get(from_triple_id)
            to_triple = EntityTriple.query.get(to_triple_id)
            
            if not from_triple or not to_triple:
                return False
                
            # Validate relation type
            valid_relations = [
                "precedes", "follows", "coincidesWith", "overlaps", 
                "necessitates", "hasConsequence"
            ]
            
            if relation_type not in valid_relations:
                print(f"Invalid relation type: {relation_type}")
                return False
                
            # Create the relation by setting a reference on the source triple
            from_triple.temporal_relation_type = relation_type
            from_triple.temporal_relation_to = to_triple_id
            
            # If the relation is symmetrical or has an inverse, create that too
            if relation_type == "coincidesWith":
                # Coincidence is symmetrical
                to_triple.temporal_relation_type = "coincidesWith"
                to_triple.temporal_relation_to = from_triple_id
            elif relation_type == "precedes":
                # Precedes has an inverse: follows
                to_triple.temporal_relation_type = "follows"
                to_triple.temporal_relation_to = from_triple_id
            elif relation_type == "follows":
                # Follows has an inverse: precedes
                to_triple.temporal_relation_type = "precedes"
                to_triple.temporal_relation_to = from_triple_id
            elif relation_type == "necessitates":
                # Necessitates has an inverse: isNecessitatedBy
                to_triple.temporal_relation_type = "isNecessitatedBy"
                to_triple.temporal_relation_to = from_triple_id
            elif relation_type == "hasConsequence":
                # hasConsequence has an inverse: isConsequenceOf
                to_triple.temporal_relation_type = "isConsequenceOf"
                to_triple.temporal_relation_to = from_triple_id
                
            db.session.commit()
            return True
            
        except Exception as e:
            db.session.rollback()
            print(f"Error creating temporal relation: {str(e)}")
            return False

    def find_triples_in_timeframe(
        self, start_time: datetime, end_time: datetime, 
        entity_type: Optional[str] = None, scenario_id: Optional[int] = None
    ) -> List[EntityTriple]:
        """
        Find all entity triples valid within a specific timeframe.
        
        Args:
            start_time: Start of the timeframe
            end_time: End of the timeframe
            entity_type: Optional entity type filter (event, action, etc.)
            scenario_id: Optional scenario ID filter
            
        Returns:
            List of entity triples
        """
        try:
            # Base query with timeframe conditions
            query = EntityTriple.query.filter(
                # For 1D temporal regions (intervals):
                # - Start time must be before the end of the frame
                # - End time must be after the start of the frame
                or_(
                    # Case 1: 1D temporal region (has start and end)
                    and_(
                        EntityTriple.temporal_region_type == str(BFO.BFO_0000038),
                        EntityTriple.temporal_start <= end_time,
                        or_(
                            EntityTriple.temporal_end >= start_time,
                            EntityTriple.temporal_end.is_(None)
                        )
                    ),
                    # Case 2: 0D temporal region (instant)
                    and_(
                        EntityTriple.temporal_region_type == str(BFO.BFO_0000148),
                        EntityTriple.temporal_start >= start_time,
                        EntityTriple.temporal_start <= end_time
                    )
                )
            )
            
            # Add optional filters
            if entity_type:
                query = query.filter(EntityTriple.entity_type == entity_type)
                
            if scenario_id:
                query = query.filter(EntityTriple.scenario_id == scenario_id)
                
            # Order by start time
            query = query.order_by(EntityTriple.temporal_start)
            
            return query.all()
            
        except Exception as e:
            print(f"Error finding triples in timeframe: {str(e)}")
            return []

    def find_temporal_sequence(
        self, scenario_id: int, entity_type: Optional[str] = None, 
        limit: Optional[int] = None
    ) -> List[EntityTriple]:
        """
        Find a sequence of entity triples in temporal order.
        
        Args:
            scenario_id: Scenario ID
            entity_type: Optional entity type filter
            limit: Optional limit on number of results
            
        Returns:
            List of entity triples in temporal order
        """
        try:
            # Base query with scenario filter
            query = EntityTriple.query.filter(EntityTriple.scenario_id == scenario_id)
            
            # Make sure we only include triples with temporal data
            query = query.filter(EntityTriple.temporal_start.isnot(None))
            
            # Add optional entity type filter
            if entity_type:
                query = query.filter(EntityTriple.entity_type == entity_type)
                
            # Order by start time
            query = query.order_by(EntityTriple.temporal_start)
            
            # Add optional limit
            if limit:
                query = query.limit(limit)
                
            return query.all()
            
        except Exception as e:
            print(f"Error finding temporal sequence: {str(e)}")
            return []

    def find_temporal_relations(
        self, triple_id: int, relation_type: str
    ) -> List[EntityTriple]:
        """
        Find triples with a specific temporal relation to a given triple.
        
        Args:
            triple_id: ID of the reference triple
            relation_type: Type of temporal relation to find
            
        Returns:
            List of related entity triples
        """
        try:
            # Find all triples with the specified relation to the given triple
            query = EntityTriple.query.filter(
                EntityTriple.temporal_relation_type == relation_type,
                EntityTriple.temporal_relation_to == triple_id
            )
            
            return query.all()
            
        except Exception as e:
            print(f"Error finding temporal relations: {str(e)}")
            return []

    def build_timeline(self, scenario_id: int) -> Dict[str, List[Dict]]:
        """
        Build a complete timeline for a scenario.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            Dictionary containing events, actions, and decisions
        """
        try:
            # Get all temporal triples for the scenario
            query = EntityTriple.query.filter(
                EntityTriple.scenario_id == scenario_id,
                EntityTriple.temporal_start.isnot(None)
            ).order_by(EntityTriple.temporal_start)
            
            triples = query.all()
            
            # Group triples by entity type and ID
            events = {}
            actions = {}
            decisions = {}
            
            for triple in triples:
                if triple.entity_type == "event":
                    if triple.entity_id not in events:
                        # Get the actual event
                        event = Event.query.get(triple.entity_id)
                        if event:
                            events[triple.entity_id] = {
                                "id": triple.entity_id,
                                "time": triple.temporal_start,
                                "end_time": triple.temporal_end,
                                "description": event.description,
                                "character_id": event.character_id,
                                "triples": []
                            }
                    
                    if triple.entity_id in events:
                        events[triple.entity_id]["triples"].append({
                            "id": triple.id,
                            "subject": triple.subject,
                            "predicate": triple.predicate,
                            "object": triple.object,
                            "time": triple.temporal_start,
                            "relation_type": triple.temporal_relation_type,
                            "relation_to": triple.temporal_relation_to
                        })
                
                elif triple.entity_type == "action":
                    # Check if this is a decision
                    action = Action.query.get(triple.entity_id)
                    if not action:
                        continue
                        
                    if action.is_decision:
                        if triple.entity_id not in decisions:
                            decisions[triple.entity_id] = {
                                "id": triple.entity_id,
                                "time": triple.temporal_start,
                                "name": action.name,
                                "description": action.description,
                                "character_id": action.character_id,
                                "options": action.options,
                                "selected_option": action.selected_option,
                                "triples": []
                            }
                            
                        if triple.entity_id in decisions:
                            decisions[triple.entity_id]["triples"].append({
                                "id": triple.id,
                                "subject": triple.subject,
                                "predicate": triple.predicate,
                                "object": triple.object,
                                "time": triple.temporal_start,
                                "relation_type": triple.temporal_relation_type,
                                "relation_to": triple.temporal_relation_to
                            })
                    else:
                        if triple.entity_id not in actions:
                            actions[triple.entity_id] = {
                                "id": triple.entity_id,
                                "time": triple.temporal_start,
                                "end_time": triple.temporal_end,
                                "name": action.name,
                                "description": action.description,
                                "character_id": action.character_id,
                                "triples": []
                            }
                            
                        if triple.entity_id in actions:
                            actions[triple.entity_id]["triples"].append({
                                "id": triple.id,
                                "subject": triple.subject,
                                "predicate": triple.predicate,
                                "object": triple.object,
                                "time": triple.temporal_start,
                                "relation_type": triple.temporal_relation_type,
                                "relation_to": triple.temporal_relation_to
                            })
            
            return {
                "events": list(events.values()),
                "actions": list(actions.values()),
                "decisions": list(decisions.values())
            }
            
        except Exception as e:
            print(f"Error building timeline: {str(e)}")
            return {"events": [], "actions": [], "decisions": []}

    def get_temporal_context_for_claude(self, scenario_id: int) -> str:
        """
        Generate a formatted temporal context for Claude to understand the scenario.
        
        Args:
            scenario_id: Scenario ID
            
        Returns:
            String representation of the temporal context
        """
        try:
            # Get the timeline
            timeline = self.build_timeline(scenario_id)
            
            # Combine all timeline elements and sort by time
            timeline_items = []
            
            for event in timeline["events"]:
                timeline_items.append({
                    "type": "event",
                    "time": event["time"],
                    "description": event["description"],
                    "entity_id": event["id"]
                })
                
            for action in timeline["actions"]:
                timeline_items.append({
                    "type": "action",
                    "time": action["time"],
                    "description": action["description"],
                    "name": action["name"],
                    "entity_id": action["id"]
                })
                
            for decision in timeline["decisions"]:
                timeline_items.append({
                    "type": "decision",
                    "time": decision["time"],
                    "description": decision["description"],
                    "name": decision["name"],
                    "options": decision["options"],
                    "selected_option": decision["selected_option"],
                    "entity_id": decision["id"]
                })
                
            # Sort by time
            timeline_items.sort(key=lambda x: x["time"])
            
            # Format the context
            context = "TIMELINE:\n\n"
            
            for item in timeline_items:
                time_str = item["time"].strftime("%Y-%m-%d %H:%M:%S")
                
                if item["type"] == "event":
                    context += f"EVENT [{time_str}]: {item['description']}\n"
                elif item["type"] == "action":
                    context += f"ACTION [{time_str}]: {item['name']} - {item['description']}\n"
                elif item["type"] == "decision":
                    context += f"DECISION [{time_str}]: {item['name']} - {item['description']}\n"
                    
                    # Add options
                    if item.get("options"):
                        context += "  Options:\n"
                        for option_key, option_data in item["options"].items():
                            selected = " (SELECTED)" if option_key == item.get("selected_option") else ""
                            context += f"    - {option_key}{selected}: {option_data.get('description', '')}\n"
                            
                            if "ethical_principles" in option_data:
                                principles = ", ".join(option_data["ethical_principles"])
                                context += f"      Ethical principles: {principles}\n"
                    
                context += "\n"
                
            # Add temporal relations at the end
            context += "TEMPORAL RELATIONSHIPS:\n\n"
            
            # Collect all the triples
            all_triples = []
            for event in timeline["events"]:
                all_triples.extend(event["triples"])
            for action in timeline["actions"]:
                all_triples.extend(action["triples"])
            for decision in timeline["decisions"]:
                all_triples.extend(decision["triples"])
                
            # Create a lookup dictionary for triples
            triple_dict = {triple["id"]: triple for triple in all_triples}
            
            # Add temporal relation descriptions
            for triple in all_triples:
                if triple.get("relation_type") and triple.get("relation_to"):
                    related_triple = triple_dict.get(triple["relation_to"])
                    
                    if related_triple:
                        # Try to make a human-readable description
                        relation_type = triple["relation_type"]
                        
                        # Get entity descriptions
                        from_entity = self._get_entity_description(triple["subject"])
                        to_entity = self._get_entity_description(related_triple["subject"])
                        
                        if from_entity and to_entity:
                            if relation_type == "precedes":
                                context += f"- {from_entity} happens before {to_entity}\n"
                            elif relation_type == "follows":
                                context += f"- {from_entity} happens after {to_entity}\n"
                            elif relation_type == "coincidesWith":
                                context += f"- {from_entity} happens at the same time as {to_entity}\n"
                            elif relation_type == "overlaps":
                                context += f"- {from_entity} overlaps in time with {to_entity}\n"
                            elif relation_type == "necessitates":
                                context += f"- {from_entity} creates the need for {to_entity}\n"
                            elif relation_type == "hasConsequence":
                                context += f"- {from_entity} leads to {to_entity}\n"
                            elif relation_type == "isNecessitatedBy":
                                context += f"- {from_entity} is necessitated by {to_entity}\n"
                            elif relation_type == "isConsequenceOf":
                                context += f"- {from_entity} is a consequence of {to_entity}\n"
            
            return context
            
        except Exception as e:
            print(f"Error generating temporal context: {str(e)}")
            return "Error generating timeline context."

    def _get_entity_description(self, uri: str) -> Optional[str]:
        """
        Get a human-readable description of an entity.
        
        Args:
            uri: URI of the entity
            
        Returns:
            String description or None
        """
        try:
            if not uri:
                return None
                
            # Check if this is an event
            if "event" in uri.lower():
                event_id = int(uri.split("/")[-1])
                event = Event.query.get(event_id)
                if event:
                    return f"Event '{event.description}'"
                    
            # Check if this is an action
            if "action" in uri.lower():
                action_id = int(uri.split("/")[-1])
                action = Action.query.get(action_id)
                if action:
                    return f"Action '{action.name}'"
                    
            # Otherwise just return the URI
            return uri
            
        except Exception as e:
            print(f"Error getting entity description: {str(e)}")
            return uri
