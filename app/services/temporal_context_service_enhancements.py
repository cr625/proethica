"""
Enhanced functionality for the TemporalContextService.

This module contains methods that leverage the new temporal fields
to provide better timeline and temporal context services.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Union, Tuple
from sqlalchemy import and_, or_, desc, asc, func

from app import db
from app.models.entity_triple import EntityTriple
from app.services.temporal_context_service import TemporalContextService


def patch_temporal_context_service():
    """Patch the TemporalContextService with enhanced functionality."""
    
    # Add new methods to TemporalContextService
    
    def group_timeline_items(self, scenario_id: int, group_by: str = 'auto'):
        """
        Group timeline items into logical segments.
        
        Args:
            scenario_id: ID of the scenario
            group_by: Grouping strategy ('auto', 'character', 'temporal_gap', 'event_type')
            
        Returns:
            Dictionary of groups and their timeline items
        """
        # Get the timeline items
        timeline = self.build_timeline(scenario_id)
        all_items = []
        
        # Flatten all items into a single list
        for event in timeline.get("events", []):
            all_items.append({
                "type": "event",
                "id": event.get("id"),
                "time": event.get("time"),
                "entity": event,
                "character_id": event.get("character_id")
            })
            
        for action in timeline.get("actions", []):
            all_items.append({
                "type": "action", 
                "id": action.get("id"),
                "time": action.get("time"),
                "entity": action,
                "character_id": action.get("character_id")
            })
            
        for decision in timeline.get("decisions", []):
            all_items.append({
                "type": "decision",
                "id": decision.get("id"), 
                "time": decision.get("time"),
                "entity": decision,
                "character_id": decision.get("character_id")
            })
        
        # Sort all items by time
        all_items.sort(key=lambda x: x["time"] if x["time"] else datetime.min)
        
        # Group items based on the strategy
        groups = {}
        
        if group_by == 'character':
            # Group by character
            for item in all_items:
                character_id = item.get("character_id")
                if not character_id:
                    # Use "system" as the group for items without a character
                    group_key = "system"
                else:
                    group_key = f"character_{character_id}"
                    
                if group_key not in groups:
                    groups[group_key] = []
                    
                groups[group_key].append(item)
                
        elif group_by == 'temporal_gap':
            # Group by significant time gaps
            current_group = 0
            last_time = None
            
            for item in all_items:
                current_time = item.get("time")
                
                if not current_time:
                    # Skip items without a timestamp
                    continue
                    
                if last_time is None:
                    # First item
                    group_key = f"segment_{current_group}"
                    if group_key not in groups:
                        groups[group_key] = []
                    groups[group_key].append(item)
                else:
                    # Check time gap
                    gap = (current_time - last_time).total_seconds()
                    
                    # Consider gaps > 1 hour as significant
                    if gap > 3600:
                        current_group += 1
                    
                    group_key = f"segment_{current_group}"
                    if group_key not in groups:
                        groups[group_key] = []
                    groups[group_key].append(item)
                
                last_time = current_time
                
        elif group_by == 'event_type':
            # Group by event type
            for item in all_items:
                item_type = item.get("type")
                group_key = f"{item_type}s"  # events, actions, decisions
                
                if group_key not in groups:
                    groups[group_key] = []
                    
                groups[group_key].append(item)
                
        else:  # 'auto' or any other value
            # Automatically choose the best grouping strategy
            # For now, just use a simple temporal sequence
            current_group = 0
            items_in_group = 0
            
            for item in all_items:
                # Start a new group every 5 items for readability
                if items_in_group >= 5:
                    current_group += 1
                    items_in_group = 0
                
                group_key = f"segment_{current_group}"
                if group_key not in groups:
                    groups[group_key] = []
                
                groups[group_key].append(item)
                items_in_group += 1
        
        return groups

    def infer_temporal_relationships(self, scenario_id: int):
        """
        Infer temporal relationships between triples based on timestamps.
        
        Args:
            scenario_id: ID of the scenario
            
        Returns:
            Number of relationships inferred
        """
        # Use the database function
        with db.engine.connect() as connection:
            result = connection.execute(
                func.infer_temporal_relationships(scenario_id)
            )
            return result.scalar()

    def recalculate_timeline_order(self, scenario_id: int):
        """
        Recalculate the timeline_order values for all triples in a scenario.
        
        Args:
            scenario_id: ID of the scenario
            
        Returns:
            True if successful
        """
        # Use the database function
        with db.engine.connect() as connection:
            connection.execute(
                func.recalculate_timeline_order(scenario_id)
            )
            return True

    def get_enhanced_temporal_context_for_claude(self, scenario_id: int, 
                                              include_confidence: bool = True,
                                              include_causal_relations: bool = True):
        """
        Generate an enhanced temporal context for Claude with additional metadata.
        
        Args:
            scenario_id: Scenario ID
            include_confidence: Whether to include confidence levels
            include_causal_relations: Whether to include causal relationships
            
        Returns:
            String representation of the enhanced temporal context
        """
        # Get the basic context
        basic_context = self.get_temporal_context_for_claude(scenario_id)
        
        # Add enhanced information if requested
        if not include_confidence and not include_causal_relations:
            return basic_context
            
        # Get the timeline items
        timeline = self.build_timeline(scenario_id)
        
        # Groups the timeline for better organization
        groups = self.group_timeline_items(scenario_id)
        
        # Enhance the context with timeline groups
        enhanced_context = basic_context + "\n\nTIMELINE ORGANIZATION:\n\n"
        
        for group_key, items in groups.items():
            if not items:
                continue
                
            enhanced_context += f"Group: {group_key}\n"
            for item in items:
                item_type = item.get("type", "unknown").upper()
                item_time = item.get("time")
                time_str = item_time.strftime("%Y-%m-%d %H:%M:%S") if item_time else "Unknown time"
                
                entity = item.get("entity", {})
                description = entity.get("description", "")
                name = entity.get("name", "")
                
                enhanced_context += f"  - {item_type} [{time_str}]: {name or description}\n"
            
            enhanced_context += "\n"
            
        # Add causal relations if requested
        if include_causal_relations:
            # Get all triples with causal relations
            causal_triples = EntityTriple.query.filter(
                EntityTriple.scenario_id == scenario_id,
                EntityTriple.temporal_relation_type.in_([
                    "causedBy", "enabledBy", "preventedBy", "hasConsequence"
                ])
            ).all()
            
            if causal_triples:
                enhanced_context += "\nCAUSAL RELATIONSHIPS:\n\n"
                
                for triple in causal_triples:
                    # Get the related triple
                    related_triple = EntityTriple.query.get(triple.temporal_relation_to)
                    if not related_triple:
                        continue
                        
                    # Try to get entity descriptions
                    from_entity = self._get_entity_description(triple.subject)
                    to_entity = self._get_entity_description(related_triple.subject)
                    
                    if from_entity and to_entity:
                        relation_type = triple.temporal_relation_type
                        confidence = ""
                        
                        if include_confidence and triple.temporal_confidence:
                            confidence = f" (confidence: {triple.temporal_confidence:.2f})"
                            
                        if relation_type == "causedBy":
                            enhanced_context += f"- {from_entity} was caused by {to_entity}{confidence}\n"
                        elif relation_type == "enabledBy":
                            enhanced_context += f"- {from_entity} was enabled by {to_entity}{confidence}\n"
                        elif relation_type == "preventedBy":
                            enhanced_context += f"- {from_entity} was prevented by {to_entity}{confidence}\n"
                        elif relation_type == "hasConsequence":
                            enhanced_context += f"- {from_entity} led to {to_entity}{confidence}\n"
        
        return enhanced_context
    
    # Attach new methods to the TemporalContextService class
    TemporalContextService.group_timeline_items = group_timeline_items
    TemporalContextService.infer_temporal_relationships = infer_temporal_relationships
    TemporalContextService.recalculate_timeline_order = recalculate_timeline_order
    TemporalContextService.get_enhanced_temporal_context_for_claude = get_enhanced_temporal_context_for_claude
    
    # Return the enhanced class for testing
    return TemporalContextService

# Apply the patch when this module is imported
patch_temporal_context_service()
