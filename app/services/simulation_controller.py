"""
Simulation Controller for the AI Ethical Decision-Making Simulator.

This module provides the SimulationController class, which is responsible for
managing the simulation flow, user interactions, and state management.
"""

import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from app import db
from app.models import Scenario, Character, SimulationSession
from app.services.llm_service import LLMService

# Set up logging
logger = logging.getLogger(__name__)

class SimulationController:
    """
    Controller for managing simulation sessions.
    
    This class is responsible for initializing simulations, processing decisions,
    and managing the state of the simulation.
    """
    
    def __init__(self, scenario_id: int, selected_character_id: Optional[int] = None, 
                 perspective: str = "specific", llm_service: Optional[LLMService] = None):
        """
        Initialize the simulation controller.
        
        Args:
            scenario_id: ID of the scenario to simulate
            selected_character_id: ID of the character to simulate from their perspective (optional)
            perspective: "specific" for a single character perspective, "all" for all perspectives
            llm_service: LLM service to use for simulation (optional)
        """
        self.scenario = Scenario.query.get(scenario_id)
        if not self.scenario:
            raise ValueError(f"Scenario with ID {scenario_id} not found")
            
        self.selected_character = None
        if selected_character_id:
            self.selected_character = Character.query.get(selected_character_id)
            if not self.selected_character or self.selected_character.scenario_id != scenario_id:
                raise ValueError(f"Character with ID {selected_character_id} not found in scenario {scenario_id}")
                
        self.perspective = perspective
        self.llm_service = llm_service or LLMService()
        
        # Initialize state
        self.current_state = {}
        self.session_data = {
            'states': [],
            'decisions': [],
            'evaluations': [],
            'timestamps': []
        }
        
        logger.info(f"Initialized SimulationController for scenario {scenario_id}")
    
    def initialize_simulation(self) -> Dict[str, Any]:
        """
        Initialize the simulation and return the initial state.
        
        Returns:
            Dictionary containing the initial state of the simulation
        """
        # Get events sorted by time
        events = sorted(self.scenario.events, key=lambda e: e.event_time)
        
        # Initialize character states
        character_states = {}
        for character in self.scenario.characters:
            character_states[character.id] = {
                'id': character.id,
                'name': character.name,
                'role': character.role,
                'knowledge': [],  # What the character knows
                'emotional_state': 'neutral',
                'conditions': [c.name for c in character.conditions]
            }
        
        # Initialize resource states
        resource_states = {}
        for resource in self.scenario.resources:
            resource_states[resource.id] = {
                'id': resource.id,
                'name': resource.name,
                'type': resource.type,
                'quantity': resource.quantity,
                'allocated': {}  # Track allocations to characters
            }
        
        # Convert events to dictionaries
        event_dicts = [self._event_to_dict(e) for e in events]
        
        # Pre-load decision options for all decision points
        for event_dict in event_dicts:
            if self._is_decision_point(event_dict):
                # Create a temporary state for generating options
                temp_state = {
                    'character_states': character_states,
                    'resource_states': resource_states
                }
                
                # Generate decision options for this event
                event_dict['decision_options'] = self._generate_decision_options(event_dict, temp_state)
                logger.info(f"Pre-loaded decision options for event {event_dict['id']}")
        
        # Create initial state
        initial_state = {
            'scenario_id': self.scenario.id,
            'scenario_name': self.scenario.name,
            'current_time': events[0].event_time.isoformat() if events else datetime.now().isoformat(),
            'current_event_index': 0,
            'events': event_dicts,
            'character_states': character_states,
            'resource_states': resource_states,
            'decision_history': [],
            'selected_character_id': self.selected_character.id if self.selected_character else None,
            'perspective': self.perspective
        }
        
        # Set current state and record it
        self.current_state = initial_state
        self._record_state(initial_state)
        
        logger.info(f"Initialized simulation for scenario {self.scenario.id}")
        return initial_state
    
    def process_decision(self, decision_data: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Process a decision and return the next state and evaluation.
        
        Args:
            decision_data: Dictionary containing decision data
            
        Returns:
            Tuple of (next_state, evaluation)
        """
        # Validate decision data
        if 'option_id' not in decision_data:
            raise ValueError("Decision data must include option_id")
        
        # Get the current event
        current_event_index = self.current_state['current_event_index']
        events = self.current_state['events']
        
        if current_event_index >= len(events):
            raise ValueError("No more events in the scenario")
        
        current_event = events[current_event_index]
        
        # Log current event details
        logger.info(f"Processing decision for event: {current_event['id']}, action_id: {current_event.get('action_id')}, description: {current_event.get('description')}")
        
        # Get the character making the decision
        character_id = decision_data.get('character_id', self.selected_character.id if self.selected_character else None)
        if not character_id:
            raise ValueError("No character specified for decision")
        
        # Get the decision options for this event
        decision_options = current_event.get('decision_options', [])
        logger.info(f"Decision options: {decision_options}")
        
        # Record the decision with option description
        option_description = "Unknown option"
        selected_option = next((opt for opt in decision_options if opt['id'] == decision_data['option_id']), None)
        if selected_option:
            option_description = selected_option['description']
            
        decision_record = {
            'option_id': decision_data['option_id'],
            'option_description': option_description,
            'character_id': character_id,
            'event_id': current_event['id'],
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Created decision record: {decision_record}")
        
        # Evaluate the decision (simplified for now)
        evaluation = self._evaluate_decision(decision_record, self.current_state)
        
        # Record the decision and evaluation
        self._record_decision(decision_record, evaluation)
        
        # Attach the decision and evaluation to the current event
        current_event['decision'] = decision_record
        current_event['evaluation'] = evaluation
        
        # Update the event in the events list
        events[current_event_index] = current_event
        self.current_state['events'] = events
        
        # Add to decision history
        if 'decision_history' not in self.current_state:
            self.current_state['decision_history'] = []
        self.current_state['decision_history'].append({
            'event_id': current_event['id'],
            'event_index': current_event_index,
            'decision': decision_record,
            'evaluation': evaluation
        })
        
        logger.info(f"Added decision to history. Current decision history: {self.current_state['decision_history']}")
        
        # Advance to the next event
        next_state = self._advance_timeline(self.current_state)
        
        # Ensure decisions are properly attached to events in the next state
        if 'decision_history' in next_state:
            for history_item in next_state['decision_history']:
                event_index = history_item['event_index']
                if event_index < len(next_state['events']):
                    # Attach decision and evaluation to the event
                    next_state['events'][event_index]['decision'] = history_item['decision']
                    next_state['events'][event_index]['evaluation'] = history_item['evaluation']
                    logger.info(f"Attached decision to event {event_index} in next state")
        
        # Record the new state
        self._record_state(next_state)
        
        # Update current state
        self.current_state = next_state
        
        logger.info(f"Processed decision for scenario {self.scenario.id}, event {current_event['id']}")
        return next_state, evaluation
    
    def save_session(self, user_id: Optional[int] = None) -> int:
        """
        Save the simulation session to the database.
        
        Args:
            user_id: ID of the user who ran the simulation (optional)
            
        Returns:
            ID of the saved session
        """
        # Create a new session record
        session = SimulationSession(
            scenario_id=self.scenario.id,
            user_id=user_id,
            session_data=self.session_data,
            created_at=datetime.now()
        )
        
        # Save to database
        db.session.add(session)
        db.session.commit()
        
        logger.info(f"Saved simulation session {session.id} for scenario {self.scenario.id}")
        return session.id
    
    def _record_state(self, state: Dict[str, Any]) -> None:
        """
        Record a state in the session data.
        
        Args:
            state: Dictionary containing state data
        """
        self.session_data['states'].append(state)
        self.session_data['timestamps'].append(datetime.now().isoformat())
    
    def _record_decision(self, decision: Dict[str, Any], evaluation: Dict[str, Any]) -> None:
        """
        Record a decision and its evaluation in the session data.
        
        Args:
            decision: Dictionary containing decision data
            evaluation: Dictionary containing evaluation data
        """
        self.session_data['decisions'].append(decision)
        self.session_data['evaluations'].append(evaluation)
    
    def _evaluate_decision(self, decision: Dict[str, Any], current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a decision using the LLM.
        
        Args:
            decision: Dictionary containing decision data
            current_state: Dictionary containing current state data
            
        Returns:
            Dictionary containing evaluation data
        """
        # This is a simplified implementation for now
        # In the future, this will use the Character Agent System and Role-Based Virtue Ethics Engine
        
        # Get the character making the decision
        character_id = decision['character_id']
        character_state = current_state['character_states'].get(character_id, {})
        
        # Get the event
        event_id = decision['event_id']
        event = next((e for e in current_state['events'] if e['id'] == event_id), {})
        
        # Get the option
        option_id = decision['option_id']
        option = next((o for o in event.get('decision_options', []) if o['id'] == option_id), {})
        
        # Construct a prompt for the LLM
        prompt = f"""
        Evaluate the following decision from a virtue ethics perspective, focusing on the virtues associated with the professional role.
        
        Character: {character_state.get('name', 'Unknown')}
        Role: {character_state.get('role', 'Unknown')}
        
        Event: {event.get('description', 'Unknown event')}
        
        Decision: {option.get('description', 'Unknown decision')}
        
        Evaluate this decision based on:
        1. How well it exemplifies the virtues expected of someone in this role
        2. Whether it demonstrates practical wisdom in applying professional knowledge
        3. How it balances competing virtues or values in this specific context
        4. Whether it contributes to the character's development as an exemplary professional
        
        Provide:
        1. An overall assessment of the decision's alignment with role virtues (scale 1-10)
        2. Identification of specific virtues demonstrated or violated
        3. Analysis of how this decision reflects on the character as a professional
        4. Recommendations for how a virtuous professional in this role would approach this situation
        """
        
        # Get evaluation from LLM
        try:
            # Use the llm attribute directly instead of calling get_llm()
            evaluation_text = self.llm_service.llm(prompt)
            
            # For now, return a simple evaluation
            # In the future, we'll parse the LLM output to extract structured data
            evaluation = {
                'raw_evaluation': evaluation_text,
                'structured_evaluation': {
                    'alignment_score': 7,  # Placeholder
                    'virtues_demonstrated': ['integrity', 'compassion'],  # Placeholder
                    'virtues_violated': [],  # Placeholder
                    'character_reflection': 'The decision reflects positively on the character as a professional',  # Placeholder
                    'recommendations': 'A virtuous professional would consider...'  # Placeholder
                }
            }
            
            return evaluation
        except Exception as e:
            logger.error(f"Error evaluating decision: {str(e)}")
            return {
                'raw_evaluation': f"Error evaluating decision: {str(e)}",
                'structured_evaluation': None
            }
    
    def _advance_timeline(self, current_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Advance the timeline to the next event.
        
        Args:
            current_state: Dictionary containing current state data
            
        Returns:
            Dictionary containing next state data
        """
        # Create a copy of the current state
        next_state = current_state.copy()
        
        # Increment the current event index
        next_state['current_event_index'] = current_state['current_event_index'] + 1
        
        # Update the current time if there are more events
        events = current_state['events']
        next_event_index = next_state['current_event_index']
        
        if next_event_index < len(events):
            next_state['current_time'] = events[next_event_index]['event_time']
            
            # Check if the next event is a decision point
            next_event = events[next_event_index]
            if self._is_decision_point(next_event):
                # Generate decision options
                next_event['decision_options'] = self._generate_decision_options(next_event, next_state)
                next_state['events'][next_event_index] = next_event
        
        return next_state
    
    def _is_decision_point(self, event: Dict[str, Any]) -> bool:
        """
        Determine if an event is a decision point.
        
        Args:
            event: Dictionary containing event data
            
        Returns:
            True if the event is a decision point, False otherwise
        """
        # Check if the event has an action and if that action is a decision
        if event.get('action_id') is not None:
            # If we have the action data in the event, use it
            if 'action' in event and event['action'].get('is_decision') is not None:
                return event['action']['is_decision']
            
            # Otherwise, we'll still consider it a decision point if it has an action_id
            return True
        
        return False
    
    def _generate_decision_options(self, event: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate decision options for an event.
        
        Args:
            event: Dictionary containing event data
            state: Dictionary containing state data
            
        Returns:
            List of dictionaries containing decision options
        """
        # First, check if the event already has decision options from the database
        if 'decision_options' in event and event['decision_options']:
            logger.info(f"Using pre-existing decision options from the database for event {event['id']}")
            return event['decision_options']
            
        # Get character information if available
        character_id = event.get('character_id')
        character_info = state['character_states'].get(character_id, {}) if character_id else {}
        character_role = character_info.get('role', 'Unknown')
        
        # Get action information if available
        action = event.get('action', {})
        
        # If the action has options, use those
        if action and action.get('options'):
            logger.info(f"Using options from action {action['id']} for event {event['id']}")
            return action['options']
        
        logger.info(f"Generating new decision options for event {event['id']}")
        
        # Default options
        options = [
            {
                'id': 1,
                'description': 'Option 1: Take the ethical high ground'
            },
            {
                'id': 2,
                'description': 'Option 2: Compromise for practical reasons'
            },
            {
                'id': 3,
                'description': 'Option 3: Prioritize efficiency over other considerations'
            }
        ]
        
        # If we have character role information, customize the options
        if character_role:
            if 'doctor' in character_role.lower() or 'physician' in character_role.lower() or 'nurse' in character_role.lower():
                options = [
                    {
                        'id': 1,
                        'description': 'Option 1: Prioritize patient welfare above all else'
                    },
                    {
                        'id': 2,
                        'description': 'Option 2: Balance patient needs with resource constraints'
                    },
                    {
                        'id': 3,
                        'description': 'Option 3: Follow hospital protocols strictly'
                    }
                ]
            elif 'engineer' in character_role.lower():
                options = [
                    {
                        'id': 1,
                        'description': 'Option 1: Prioritize safety and reliability'
                    },
                    {
                        'id': 2,
                        'description': 'Option 2: Balance safety with cost and timeline considerations'
                    },
                    {
                        'id': 3,
                        'description': 'Option 3: Focus on innovation and efficiency'
                    }
                ]
            elif 'lawyer' in character_role.lower() or 'attorney' in character_role.lower():
                options = [
                    {
                        'id': 1,
                        'description': 'Option 1: Advocate zealously for your client'
                    },
                    {
                        'id': 2,
                        'description': 'Option 2: Seek a balanced resolution that serves justice'
                    },
                    {
                        'id': 3,
                        'description': 'Option 3: Strictly adhere to legal procedures and precedents'
                    }
                ]
            elif 'manager' in character_role.lower() or 'executive' in character_role.lower():
                options = [
                    {
                        'id': 1,
                        'description': 'Option 1: Prioritize employee wellbeing and team cohesion'
                    },
                    {
                        'id': 2,
                        'description': 'Option 2: Focus on organizational goals and performance metrics'
                    },
                    {
                        'id': 3,
                        'description': 'Option 3: Balance stakeholder interests with ethical considerations'
                    }
                ]
        
        # If we have event description, further customize based on keywords
        event_description = event.get('description', '').lower()
        if 'emergency' in event_description or 'crisis' in event_description:
            options[0]['description'] = 'Option 1: Act decisively to address the immediate crisis'
            options[1]['description'] = 'Option 2: Take time to gather more information before acting'
            options[2]['description'] = 'Option 3: Delegate responsibility to someone with more expertise'
        elif 'conflict' in event_description or 'disagreement' in event_description:
            options[0]['description'] = 'Option 1: Stand firm on your principles'
            options[1]['description'] = 'Option 2: Seek compromise and common ground'
            options[2]['description'] = 'Option 3: Defer to authority or established procedures'
        elif 'resource' in event_description or 'allocation' in event_description:
            options[0]['description'] = 'Option 1: Distribute resources based on greatest need'
            options[1]['description'] = 'Option 2: Allocate resources to maximize overall benefit'
            options[2]['description'] = 'Option 3: Follow established protocols for resource allocation'
            
        return options
    
    def _event_to_dict(self, event) -> Dict[str, Any]:
        """
        Convert an Event model to a dictionary.
        
        Args:
            event: Event model
            
        Returns:
            Dictionary containing event data
        """
        event_dict = {
            'id': event.id,
            'description': event.description,
            'event_time': event.event_time.isoformat() if event.event_time else None,
            'character_id': event.character_id,
            'action_id': event.action_id,
            'parameters': event.parameters
        }
        
        # Include action data if available
        if event.action:
            action = event.action
            event_dict['action'] = {
                'id': action.id,
                'name': action.name,
                'description': action.description,
                'is_decision': action.is_decision
            }
            
            # If this is a decision point, include the options
            if action.is_decision and action.options:
                event_dict['decision_options'] = action.options
        
        return event_dict
