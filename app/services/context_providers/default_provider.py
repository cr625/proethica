#!/usr/bin/env python
"""
Default context provider implementation.

Provides basic application information and entity context
from the database.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action
from app.models.resource import Resource
from app.models.entity_triple import EntityTriple

from app.services.context_providers.base_provider import ContextProvider


class DefaultContextProvider(ContextProvider):
    """
    Default implementation of context provider.
    Provides core application context including world, scenario, 
    and entity information.
    """
    
    def get_context(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get default application context.
        
        Args:
            request_context: Dictionary with context parameters
                May include world_id, scenario_id, query, etc.
            
        Returns:
            Dictionary with application context
        """
        world_id = request_context.get('world_id')
        scenario_id = request_context.get('scenario_id')
        
        context = {
            'application_state': self._get_application_state(),
            'world_context': self._get_world_context(world_id) if world_id else None,
            'scenario_context': self._get_scenario_context(scenario_id) if scenario_id else None
        }
        
        return context
    
    def format_context(self, context: Dict[str, Any]) -> str:
        """
        Format context for this provider.
        
        Args:
            context: Context from get_context
            
        Returns:
            Formatted string representation
        """
        text = ""
        
        # Format application state
        if 'application_state' in context:
            text += self._format_application_state(context['application_state'])
        
        # Format world context
        if 'world_context' in context and context['world_context']:
            text += "\n\n" + self._format_world_context(context['world_context'])
        
        # Format scenario context
        if 'scenario_context' in context and context['scenario_context']:
            text += "\n\n" + self._format_scenario_context(context['scenario_context'])
        
        return text
    
    def _get_application_state(self) -> Dict[str, Any]:
        """Get the current state of the application."""
        return {
            'worlds_count': World.query.count(),
            'scenarios_count': Scenario.query.count(),
            'characters_count': Character.query.count(),
            'triples_count': EntityTriple.query.count(),
            'timestamp': datetime.now().isoformat()
        }
    
    def _get_world_context(self, world_id: int) -> Optional[Dict[str, Any]]:
        """
        Get context information for a specific world.
        
        Args:
            world_id: ID of the world
            
        Returns:
            World context dictionary or None if not found
        """
        world = World.query.get(world_id)
        if not world:
            return None
        
        # Get entities from the world's ontology
        entities = {}
        if hasattr(world, 'ontology_source') and world.ontology_source:
            # This would use MCP client in the real implementation
            # For now, just create a placeholder
            entities = {
                'roles': [],
                'conditions': [],
                'resources': [],
                'actions': []
            }
        
        # Get scenarios in this world
        scenarios = Scenario.query.filter_by(world_id=world_id).all()
        scenario_summaries = []
        
        for scenario in scenarios:
            scenario_summaries.append({
                'id': scenario.id,
                'name': scenario.name,
                'description': scenario.description[:100] + '...' if scenario.description and len(scenario.description) > 100 else scenario.description
            })
        
        return {
            'id': world.id,
            'name': world.name,
            'description': world.description,
            'ontology_source': world.ontology_source if hasattr(world, 'ontology_source') else None,
            'entities': entities,
            'scenarios': scenario_summaries,
            'metadata': world.world_metadata if hasattr(world, 'world_metadata') else {}
        }
    
    def _get_scenario_context(self, scenario_id: int) -> Optional[Dict[str, Any]]:
        """
        Get context information for a specific scenario.
        
        Args:
            scenario_id: ID of the scenario
            
        Returns:
            Scenario context dictionary or None if not found
        """
        scenario = Scenario.query.get(scenario_id)
        if not scenario:
            return None
        
        # Get characters in this scenario
        characters = Character.query.filter_by(scenario_id=scenario_id).all()
        character_summaries = []
        
        for character in characters:
            character_summaries.append({
                'id': character.id,
                'name': character.name,
                'role': character.role.name if hasattr(character, 'role') and character.role else None,
                'attributes': character.attributes if hasattr(character, 'attributes') else {}
            })
        
        # Get events in this scenario
        events = Event.query.filter_by(scenario_id=scenario_id).all()
        event_summaries = []
        
        for event in events:
            event_summaries.append({
                'id': event.id,
                'description': event.description,
                'event_time': event.event_time.isoformat() if event.event_time else None,
                'character_id': event.character_id
            })
        
        # Get resources for this scenario
        resources = Resource.query.filter_by(scenario_id=scenario_id).all()
        resource_summaries = []
        
        for resource in resources:
            resource_summaries.append({
                'id': resource.id,
                'name': resource.name,
                'description': resource.description,
                'resource_type': resource.resource_type if hasattr(resource, 'resource_type') else None
            })
        
        # Get actions/decisions for this scenario
        actions = Action.query.filter_by(scenario_id=scenario_id).all()
        action_summaries = []
        decision_summaries = []
        
        for action in actions:
            summary = {
                'id': action.id,
                'name': action.name,
                'description': action.description,
                'action_time': action.action_time.isoformat() if action.action_time else None,
                'character_id': action.character_id
            }
            
            if action.is_decision:
                summary['options'] = action.options if hasattr(action, 'options') else {}
                summary['selected_option'] = action.selected_option if hasattr(action, 'selected_option') else None
                decision_summaries.append(summary)
            else:
                action_summaries.append(summary)
        
        return {
            'id': scenario.id,
            'name': scenario.name,
            'description': scenario.description,
            'world_id': scenario.world_id,
            'characters': character_summaries,
            'events': event_summaries,
            'resources': resource_summaries,
            'actions': action_summaries,
            'decisions': decision_summaries,
            'metadata': scenario.metadata if hasattr(scenario, 'metadata') else {}
        }
    
    def _format_application_state(self, state: Dict[str, Any]) -> str:
        """Format application state for LLM."""
        return f"""APPLICATION STATE:
- Worlds: {state['worlds_count']}
- Scenarios: {state['scenarios_count']}
- Characters: {state['characters_count']}
- Entity Triples: {state['triples_count']}"""
    
    def _format_world_context(self, world: Dict[str, Any]) -> str:
        """Format world context for LLM."""
        text = f"""WORLD CONTEXT:
ID: {world['id']}
Name: {world['name']}
Description: {world['description']}
"""
        
        # Add entities
        if 'entities' in world and world['entities']:
            text += "\nENTITIES:\n"
            
            # Add roles
            if 'roles' in world['entities'] and world['entities']['roles']:
                text += "Roles:\n"
                for role in world['entities']['roles']:
                    text += f"- {role.get('label', 'Unnamed')}: {role.get('description', '')}\n"
            
            # Add conditions
            if 'conditions' in world['entities'] and world['entities']['conditions']:
                text += "\nConditions:\n"
                for condition in world['entities']['conditions']:
                    text += f"- {condition.get('label', 'Unnamed')}: {condition.get('description', '')}\n"
            
            # Add resources
            if 'resources' in world['entities'] and world['entities']['resources']:
                text += "\nResources:\n"
                for resource in world['entities']['resources']:
                    text += f"- {resource.get('label', 'Unnamed')}: {resource.get('description', '')}\n"
            
            # Add actions
            if 'actions' in world['entities'] and world['entities']['actions']:
                text += "\nActions:\n"
                for action in world['entities']['actions']:
                    text += f"- {action.get('label', 'Unnamed')}: {action.get('description', '')}\n"
        
        # Add scenarios
        if 'scenarios' in world and world['scenarios']:
            text += "\nSCENARIOS:\n"
            
            for scenario in world['scenarios']:
                text += f"- [{scenario['id']}] {scenario['name']}: {scenario['description']}\n"
        
        return text
    
    def _format_scenario_context(self, scenario: Dict[str, Any]) -> str:
        """Format scenario context for LLM."""
        text = f"""SCENARIO CONTEXT:
ID: {scenario['id']}
Name: {scenario['name']}
Description: {scenario['description']}
World ID: {scenario['world_id']}
"""
        
        # Add characters
        if 'characters' in scenario and scenario['characters']:
            text += "\nCHARACTERS:\n"
            
            for character in scenario['characters']:
                role_text = f" ({character['role']})" if character['role'] else ""
                text += f"- [{character['id']}] {character['name']}{role_text}\n"
                
                if 'attributes' in character and character['attributes']:
                    text += "  Attributes:\n"
                    for key, value in character['attributes'].items():
                        text += f"  - {key}: {value}\n"
        
        # Add events
        if 'events' in scenario and scenario['events']:
            text += "\nEVENTS:\n"
            
            # Sort events by time
            events = sorted(
                scenario['events'], 
                key=lambda x: x.get('event_time', '') or ''
            )
            
            for event in events[:5]:  # Limit to 5 events for brevity
                time_str = event.get('event_time', '')
                time_info = f" [{time_str}]" if time_str else ""
                
                text += f"- {event.get('description', '')}{time_info}\n"
            
            if len(scenario['events']) > 5:
                text += f"  (+ {len(scenario['events']) - 5} more events)\n"
        
        # Add decisions
        if 'decisions' in scenario and scenario['decisions']:
            text += "\nDECISIONS:\n"
            
            # Sort decisions by time
            decisions = sorted(
                scenario['decisions'], 
                key=lambda x: x.get('action_time', '') or ''
            )
            
            for decision in decisions[:3]:  # Limit to 3 decisions for brevity
                time_str = decision.get('action_time', '')
                time_info = f" [{time_str}]" if time_str else ""
                
                text += f"- {decision.get('name', '')}: {decision.get('description', '')}{time_info}\n"
                
                # Add selected option if present
                if 'selected_option' in decision and decision['selected_option']:
                    text += f"  Selected: {decision['selected_option']}\n"
            
            if len(scenario['decisions']) > 3:
                text += f"  (+ {len(scenario['decisions']) - 3} more decisions)\n"
        
        return text
