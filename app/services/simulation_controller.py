"""
Simulation Controller for the AI Ethical Decision-Making Simulator.

This module provides the SimulationController class that coordinates
between Claude and LangGraph for ethical decision-making simulations.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Union

from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.simulation_state import SimulationState
from app.services.claude_service import ClaudeService
from app.services.simulation_storage import SimulationStorage
from app.services.llm_service import Conversation, Message

# Set up logging
logger = logging.getLogger(__name__)

class SimulationController:
    """
    Controller for managing simulation sessions.
    
    This class coordinates between Claude and LangGraph to provide
    a hybrid approach to ethical decision-making simulations.
    """
    
    def __init__(self, scenario_id: int, selected_character_id=None, perspective="specific", 
                llm_service=None, use_agent_orchestrator=False, status_callback=None):
        """
        Initialize the simulation controller.
        
        Args:
            scenario_id: ID of the scenario to simulate
            selected_character_id: ID of the character to simulate from their perspective (optional)
            perspective: "specific" for a single character perspective, "all" for all perspectives
            llm_service: LLM service to use for simulation (optional)
            use_agent_orchestrator: Whether to use the agent orchestrator for decisions (optional)
            status_callback: Callback function for status updates (optional)
        """
        self.scenario_id = scenario_id
        self.selected_character_id = selected_character_id
        self.perspective = perspective
        self.use_agent_orchestrator = use_agent_orchestrator
        self.status_callback = status_callback
        
        # Try to use Claude service, fall back to LLM service if needed
        self.llm_service = llm_service
        try:
            self.claude_service = ClaudeService()
            self.use_claude = True
        except ValueError:
            # If Claude API key is not available, use LLM service instead
            logger.warning("Anthropic API key not found. Using LLM service instead.")
            if not self.llm_service:
                from app.services.llm_service import LLMService
                self.llm_service = LLMService()
            self.use_claude = False
        
        # Initialize simulation state
        self.state = self._initialize_state()
        
        # Storage for persistence
        self.storage = SimulationStorage()
        
        # Initialize agent orchestrator if enabled
        self.agent_orchestrator = None
        if self.use_agent_orchestrator:
            # Import here to avoid circular imports
            from app.services.agent_orchestrator import AgentOrchestrator
            from app.services.embedding_service import EmbeddingService
            from app.services.langchain_claude import LangChainClaudeService
            
            # Get world_id from state
            world_id = self.state.get('world_id')
            
            # Initialize services
            embedding_service = EmbeddingService()
            langchain_claude = LangChainClaudeService.get_instance()
            
            # Initialize agent orchestrator
            self.agent_orchestrator = AgentOrchestrator(
                embedding_service=embedding_service,
                langchain_claude=langchain_claude,
                world_id=world_id,
                status_callback=self._agent_status_callback
            )
            
            # Only show initialization message if this is a new simulation (no session_id)
            # This prevents the message from appearing on every action
            if not self.state.get('session_id'):
                self._update_status("Initialized Agent Orchestrator for decision processing")
        
        logger.info(f"Initialized SimulationController for scenario {scenario_id}")
    
    def _update_status(self, status: str, detail: Optional[str] = None):
        """
        Update the status of the controller.
        
        Args:
            status: Status message
            detail: Additional detail (optional)
        """
        if self.status_callback:
            # Create a concise message limited to two lines
            message = f"{status}"
            if detail:
                # Truncate detail if it's too long
                max_detail_length = 50
                truncated_detail = detail[:max_detail_length] + "..." if len(detail) > max_detail_length else detail
                message += f": {truncated_detail}"
            self.status_callback(message)
        logger.info(f"SimulationController status: {status} {detail or ''}")
    
    def _agent_status_callback(self, message: str):
        """
        Callback function for agent status updates.
        
        Args:
            message: Status message
        """
        if self.status_callback:
            # Truncate message if it's too long
            max_message_length = 50
            truncated_message = message[:max_message_length] + "..." if len(message) > max_message_length else message
            self.status_callback(truncated_message)
        logger.info(f"Agent status: {message}")
    
    def _initialize_state(self) -> Dict[str, Any]:
        """Initialize the simulation state with scenario data."""
        # Get scenario from database
        scenario = Scenario.query.get(self.scenario_id)
        
        if not scenario:
            logger.error(f"Scenario with ID {self.scenario_id} not found")
            raise ValueError(f"Scenario with ID {self.scenario_id} not found")
        
        # Get all events and actions, sorted by time
        timeline_items = self._get_timeline_items(scenario)
        
        # Initialize character states
        character_states = {}
        for character in scenario.characters:
            character_states[character.id] = {
                'character_id': character.id,
                'character_name': character.name,
                'role': character.role,
                'knowledge': [],
                'emotional_state': 'neutral',
                'conditions': []  # Will be populated from character conditions
            }
        
        # Initialize state with basic information
        state = {
            'scenario_id': self.scenario_id,
            'scenario_name': scenario.name,
            'scenario_description': scenario.description,
            'current_event_index': 0,
            'decision_history': [],
            'character_states': character_states,
            'world_id': scenario.world_id,
            'session_id': None,
            'timeline_items': timeline_items,
            'is_decision_point': False,
            'completed': False
        }
        
        return state
    
    def _get_timeline_items(self, scenario) -> List[Dict[str, Any]]:
        """Get all timeline items (events and actions) sorted by time."""
        items = []
        
        # Add actions
        if hasattr(scenario, 'actions') and scenario.actions:
            for action in scenario.actions:
                # Convert action to dictionary to avoid serialization issues
                action_dict = action.to_dict() if hasattr(action, 'to_dict') else {
                    'id': action.id,
                    'name': action.name,
                    'description': action.description,
                    'is_decision': getattr(action, 'is_decision', False),
                    'options': getattr(action, 'options', [])
                }
                
                items.append({
                    'type': 'action',
                    'time': action.action_time,
                    'data': action_dict,
                    'is_decision': getattr(action, 'is_decision', False)
                })
        
        # Add events
        if hasattr(scenario, 'events') and scenario.events:
            for event in scenario.events:
                # Convert event to dictionary to avoid serialization issues
                event_dict = event.to_dict() if hasattr(event, 'to_dict') else {
                    'id': event.id,
                    'description': event.description
                }
                
                items.append({
                    'type': 'event',
                    'time': event.event_time,
                    'data': event_dict,
                    'is_decision': False
                })
        
        # Sort by time
        def get_sort_key(item):
            time_value = item['time']
            if not time_value:
                return datetime.min
            if isinstance(time_value, str):
                try:
                    # Try to parse the string as a datetime
                    return datetime.fromisoformat(time_value)
                except (ValueError, TypeError):
                    # If parsing fails, use the string for lexicographical sorting
                    return time_value
            return time_value
        
        items.sort(key=get_sort_key)
        
        return items
    
    def start_simulation(self) -> Dict[str, Any]:
        """Start the simulation."""
        # Store initial state
        session_id = self.storage.store_state(self.state)
        self.state['session_id'] = session_id
        
        # Advance to the first event immediately
        if len(self.state['timeline_items']) > 0:
            # Get the first item
            first_item = self.state['timeline_items'][0]
            
            # Process the first item
            result = self._process_item_with_claude(first_item)
            
            # Update state
            self.state['current_event_index'] = 1
            self.state['is_decision_point'] = first_item['is_decision']
            
            # Store updated state
            self.storage.store_state(self.state, session_id)
            
            return result
        else:
            # No timeline items, return empty state
            return {
                'state': self.state,
                'message': "No events or actions found in this scenario.",
                'options': [{'id': 1, 'text': 'Start Simulation'}],
                'is_decision': False
            }
    
    def _generate_welcome_message(self, conversation: Conversation) -> str:
        """Generate a welcome message for the simulation."""
        # Get the scenario
        scenario = Scenario.query.get(self.scenario_id)
        
        # Create a system message with context
        system_message = f"""
        You are simulating an ethical decision-making scenario.
        
        SCENARIO: {scenario.description}
        
        Your task is to provide a brief welcome message introducing this scenario.
        Keep it concise and engaging, explaining that the user will be able to explore
        the scenario timeline and make decisions at key points.
        """
        
        try:
            # Generate a response using the appropriate service
            message = "Please provide a welcome message for this ethical decision-making scenario."
            
            if self.use_claude:
                response = self.claude_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
                return response.content
            else:
                response = self.llm_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
                return response.content
        except Exception as e:
            logger.error(f"Error generating welcome message: {str(e)}")
            return "Welcome to the ethical decision-making simulation. In this scenario, you will explore a timeline of events and make decisions at key points. Click 'Start Simulation' to begin."
    
    def advance_simulation(self) -> Dict[str, Any]:
        """Advance the simulation to the next step."""
        # Check if we've reached the end
        if self.state['current_event_index'] >= len(self.state['timeline_items']):
            self.state['completed'] = True
            return {
                'state': self.state,
                'message': "Simulation complete. No more events to process.",
                'options': [{'id': 1, 'text': 'Simulation Complete'}],
                'is_decision': False
            }
        
        # Get the current item
        current_item = self.state['timeline_items'][self.state['current_event_index']]
        
        # For decision points, don't process with LLM yet - just return the information
        if current_item['is_decision']:
            options = self._generate_decision_options(current_item, Conversation(), "")
            
            # Get item details for status message
            item_description = current_item['data'].get('description', "Decision")
            
            # Get character involved (if any)
            character_name = "Unknown"
            if 'character' in current_item['data'] and current_item['data']['character']:
                if isinstance(current_item['data']['character'], dict):
                    character_name = current_item['data']['character'].get('name', "Unknown")
                else:
                    character_name = getattr(current_item['data']['character'], 'name', "Unknown")
            
            # Update status with decision information
            self._update_status("Reached Decision Point", f"{item_description} - Character: {character_name}")
            
            # Create a message without LLM processing
            result = {
                'state': self.state,
                'message': f"Decision: {item_description}",
                'options': options,
                'is_decision': True
            }
        else:
            # For non-decision items, process with Claude as usual
            result = self._process_item_with_claude(current_item)
        
        # Update state
        self.state['current_event_index'] += 1
        self.state['is_decision_point'] = current_item['is_decision']
        
        # Store updated state
        self.storage.store_state(self.state, self.state['session_id'])
        
        return result
    
    def _process_item_with_claude(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Process a timeline item using the appropriate LLM service."""
        # Get the scenario
        scenario = Scenario.query.get(self.scenario_id)
        
        # Create a conversation
        conversation = Conversation()
        
        # Add system message with context
        system_message = self._create_system_message(item, scenario.world_id)
        
        # Get item details for status message
        item_type = item['type']
        item_description = item['data'].get('description', f"{item_type.capitalize()}")
        
        # Get character involved (if any)
        character_name = "Unknown"
        if 'character' in item['data'] and item['data']['character']:
            if isinstance(item['data']['character'], dict):
                character_name = item['data']['character'].get('name', "Unknown")
            else:
                character_name = getattr(item['data']['character'], 'name', "Unknown")
        
        # Update status with detailed information
        if item_type == 'event':
            self._update_status(f"Process Event", f"{item_description} - Character: {character_name}")
        else:
            self._update_status(f"Process Action", f"{item_description} - Character: {character_name}")
        
        # Generate a response using the appropriate service
        if item['is_decision']:
            # If this is a decision point, generate options
            options = self._generate_decision_options(item, conversation, system_message)
            
            # Check if we should use the agent orchestrator
            if self.use_agent_orchestrator and self.agent_orchestrator:
                try:
                    # Extract scenario data
                    scenario_data = {
                        'id': scenario.id,
                        'name': scenario.name,
                        'description': scenario.description,
                        'world_id': scenario.world_id
                    }
                    
                    # Get decision text
                    decision_text = item['data'].get('description', 'Decision point')
                    
                    # Process with agent orchestrator
                    self._update_status("Process Decision", f"{decision_text} - Character: {character_name}")
                    result = self.agent_orchestrator.process_decision(
                        scenario_data=scenario_data,
                        decision_text=decision_text,
                        options=options
                    )
                    
                    self._update_status("Agent Orchestrator processing complete")
                    
                    return {
                        'state': self.state,
                        'message': result['final_response'],
                        'options': options,
                        'is_decision': True,
                        'agent_results': result,  # Include full results for transparency
                        'status_messages': result.get('status_messages', [])  # Include status messages
                    }
                except Exception as e:
                    logger.error(f"Error processing with Agent Orchestrator: {str(e)}")
                    self._update_status("Error in Agent Orchestrator, falling back to direct Claude processing")
                    # Fall back to direct Claude processing
            
            # Direct Claude processing (fallback or if agent orchestrator is disabled)
            decision_text = item['data'].get('description', 'Decision point')
            message = f"Process the following decision point: {decision_text}"
            
            # Update status with decision information
            self._update_status("Process Decision", f"{decision_text} - Character: {character_name}")
            
            try:
                if self.use_claude:
                    response = self.claude_service.send_message(
                        message=message,
                        conversation=conversation,
                        world_id=scenario.world_id
                    )
                else:
                    response = self.llm_service.send_message(
                        message=message,
                        conversation=conversation,
                        world_id=scenario.world_id
                    )
                
                return {
                    'state': self.state,
                    'message': response.content,
                    'options': options,
                    'is_decision': True
                }
            except Exception as e:
                logger.error(f"Error processing decision point: {str(e)}")
                return {
                    'state': self.state,
                    'message': f"This is a decision point: {item['data'].get('description', 'Decision point')}. Please select one of the options below.",
                    'options': options,
                    'is_decision': True
                }
        else:
            # For regular events/actions, just return the description without LLM processing
            item_type = item['type']
            item_description = item['data'].get('description', f"{item_type.capitalize()}")
            
            # Format a simple message with the event/action details
            if item_type == 'event':
                message = f"Event: {item_description}"
            else:
                message = f"Action: {item_description}"
            
            # Return the formatted message
            return {
                'state': self.state,
                'message': message,
                'options': [{'id': 1, 'text': 'Advance Simulation'}],
                'is_decision': False
            }
    
    def _create_system_message(self, item: Dict[str, Any], world_id: int) -> str:
        """Create a system message with context for Claude."""
        # Get the scenario
        scenario = Scenario.query.get(self.scenario_id)
        
        # Format timeline context
        timeline_context = self._format_timeline_context()
        
        # Format character information
        character_context = self._format_character_context()
        
        # Get item details
        item_type = item['type']
        item_description = item['data'].get('description', f"{item_type.capitalize()}")
        
        # Handle the case where item['time'] might be a string or a datetime object
        if not item['time']:
            item_time = "Unknown time"
        elif isinstance(item['time'], str):
            item_time = item['time']
        else:
            try:
                item_time = item['time'].strftime('%Y-%m-%d %H:%M')
            except AttributeError:
                item_time = str(item['time'])
        
        # Get character involved (if any)
        character_name = "Unknown"
        if 'character' in item['data'] and item['data']['character']:
            character_name = item['data']['character'].get('name', "Unknown")
        
        # Combine all context
        system_message = f"""
        You are simulating an ethical decision-making scenario.
        
        SCENARIO: {scenario.description}
        
        TIMELINE CONTEXT:
        {timeline_context}
        
        CHARACTER INFORMATION:
        {character_context}
        
        CURRENT ITEM:
        Type: {item_type.capitalize()}
        Description: {item_description}
        Time: {item_time}
        Character: {character_name}
        
        Your task is to provide a realistic and ethically nuanced response to this {item_type}.
        If this is a decision point, describe the ethical implications and considerations.
        If this is an event or action, describe its implications and effects on the scenario.
        """
        
        return system_message
    
    def _format_timeline_context(self) -> str:
        """Format timeline context for Claude."""
        # Get past events/actions
        past_items = self.state['timeline_items'][:self.state['current_event_index']]
        
        if not past_items:
            return "No previous events or actions."
        
        context = []
        for item in past_items:
            item_type = item['type'].capitalize()
            item_description = item['data'].get('description', f"{item_type}")
            
            # Handle the case where item['time'] might be a string or a datetime object
            if not item['time']:
                item_time = "Unknown time"
            elif isinstance(item['time'], str):
                item_time = item['time']
            else:
                try:
                    item_time = item['time'].strftime('%Y-%m-%d %H:%M')
                except AttributeError:
                    item_time = str(item['time'])
            
            context.append(f"- {item_time}: {item_type} - {item_description}")
        
        return "\n".join(context)
    
    def _format_character_context(self) -> str:
        """Format character context for Claude."""
        # Get character states
        character_states = self.state['character_states']
        
        if not character_states:
            return "No character information available."
        
        context = []
        for char_id, char_state in character_states.items():
            context.append(f"- {char_state['character_name']} ({char_state['role']})")
            
            # Add emotional state if available
            if 'emotional_state' in char_state:
                context.append(f"  Emotional state: {char_state['emotional_state']}")
            
            # Add conditions if available
            if 'conditions' in char_state and char_state['conditions']:
                conditions = ", ".join(char_state['conditions'])
                context.append(f"  Conditions: {conditions}")
            
            # Add knowledge if available
            if 'knowledge' in char_state and char_state['knowledge']:
                context.append("  Knowledge:")
                for knowledge in char_state['knowledge']:
                    context.append(f"    - {knowledge}")
        
        return "\n".join(context)
    
    def _generate_decision_options(self, item: Dict[str, Any], conversation: Conversation, system_message: str) -> List[Dict[str, Any]]:
        """Generate decision options for a decision point."""
        # Check if the item already has options
        if 'options' in item['data'] and item['data']['options']:
            options = []
            for i, option in enumerate(item['data']['options']):
                option_text = option
                if isinstance(option, dict) and 'description' in option:
                    option_text = option['description']
                
                options.append({
                    'id': i + 1,
                    'text': option_text
                })
            
            return options
        
        # If no options are available, generate them using the appropriate service
        scenario = Scenario.query.get(self.scenario_id)
        
        message = f"""
        Generate 3-5 ethically distinct decision options for the following decision point:
        
        {item['data'].get('description', 'Decision point')}
        
        Format each option as a brief description of the action.
        """
        
        try:
            if self.use_claude:
                response = self.claude_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
            else:
                response = self.llm_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
            
            # Parse options from response
            import re
            options_text = response.content
            options = []
            
            # Try to extract numbered or bulleted options
            option_matches = re.findall(r'(?:^|\n)[•\-\d]+\.\s*(.*?)(?=(?:\n[•\-\d]+\.)|$)', options_text, re.DOTALL)
            
            if option_matches:
                for i, option in enumerate(option_matches):
                    options.append({
                        'id': i + 1,
                        'text': option.strip()
                    })
            else:
                # Fallback: split by newlines and take non-empty lines
                lines = [line.strip() for line in options_text.split('\n') if line.strip()]
                for i, line in enumerate(lines[:5]):  # Limit to 5 options
                    options.append({
                        'id': i + 1,
                        'text': line
                    })
            
            return options
        except Exception as e:
            logger.error(f"Error generating decision options: {str(e)}")
            return [
                {'id': 1, 'text': 'Option 1: Proceed with caution'},
                {'id': 2, 'text': 'Option 2: Take decisive action'},
                {'id': 3, 'text': 'Option 3: Seek more information'}
            ]
    
    def make_decision(self, decision_index: int) -> Dict[str, Any]:
        """Make a decision at a decision point."""
        # Get the current item
        current_item_index = self.state['current_event_index']
        if current_item_index >= len(self.state['timeline_items']):
            return {
                'state': self.state,
                'message': "Cannot make a decision: simulation is complete.",
                'is_decision': False
            }
        
        current_item = self.state['timeline_items'][current_item_index]
        
        # Check if this is a decision point
        if not current_item['is_decision']:
            return {
                'state': self.state,
                'message': "Cannot make a decision: current item is not a decision point.",
                'is_decision': False
            }
        
        # Get the options
        options = self._generate_decision_options(current_item, Conversation(), "")
        
        # Check if the decision index is valid
        if decision_index < 1 or decision_index > len(options):
            return {
                'state': self.state,
                'message': f"Invalid decision index: {decision_index}. Must be between 1 and {len(options)}.",
                'is_decision': True,
                'options': options
            }
        
        # Get the selected option
        selected_option = options[decision_index - 1]
        
        # Add the decision to the history
        self.state['decision_history'].append({
            'item_index': current_item_index,
            'decision_index': decision_index,
            'option_text': selected_option['text'],
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Get the scenario
        scenario = Scenario.query.get(self.scenario_id)
        
        # Check if we should use the agent orchestrator
        if self.use_agent_orchestrator and self.agent_orchestrator:
            try:
                # Extract scenario data
                scenario_data = {
                    'id': scenario.id,
                    'name': scenario.name,
                    'description': scenario.description,
                    'world_id': scenario.world_id
                }
                
                # Get decision text
                decision_text = current_item['data'].get('description', 'Decision point')
                
                # Create options list with just the selected option
                selected_options = [selected_option['text']]
                
                # Get character involved (if any)
                character_name = "Unknown"
                if 'character' in current_item['data'] and current_item['data']['character']:
                    if isinstance(current_item['data']['character'], dict):
                        character_name = current_item['data']['character'].get('name', "Unknown")
                    else:
                        character_name = getattr(current_item['data']['character'], 'name', "Unknown")
                
                # Process with agent orchestrator
                self._update_status("Process Selected Decision", f"{selected_option['text']} - Character: {character_name}")
                result = self.agent_orchestrator.process_decision(
                    scenario_data=scenario_data,
                    decision_text=f"{decision_text} - Selected: {selected_option['text']}",
                    options=selected_options
                )
                
                self._update_status("Agent Orchestrator processing complete")
                response_content = result['final_response']
            except Exception as e:
                logger.error(f"Error processing with Agent Orchestrator: {str(e)}")
                self._update_status("Error in Agent Orchestrator, falling back to direct Claude processing")
                # Fall back to direct Claude processing
                response_content = self._process_decision_with_claude(current_item, selected_option, scenario)
        else:
            # Get character involved (if any)
            character_name = "Unknown"
            if 'character' in current_item['data'] and current_item['data']['character']:
                if isinstance(current_item['data']['character'], dict):
                    character_name = current_item['data']['character'].get('name', "Unknown")
                else:
                    character_name = getattr(current_item['data']['character'], 'name', "Unknown")
            
            # Direct Claude processing
            self._update_status("Process Selected Decision", f"{selected_option['text']} - Character: {character_name}")
            response_content = self._process_decision_with_claude(current_item, selected_option, scenario)
            self._update_status("Claude processing complete")
        
        # Update state
        self.state['current_event_index'] += 1
        self.state['is_decision_point'] = False
        
        # Store updated state
        self.storage.store_state(self.state, self.state['session_id'])
        
        return {
            'state': self.state,
            'message': response_content,
            'is_decision': False,
            'options': [{'id': 1, 'text': 'Advance Simulation'}]
        }
    
    def _process_decision_with_claude(self, current_item: Dict[str, Any], 
                                     selected_option: Dict[str, Any],
                                     scenario) -> str:
        """Process a decision using direct Claude integration."""
        # Create a conversation for Claude
        conversation = Conversation()
        
        message = f"""
        The user has selected the following option for the decision point:
        
        Decision: {current_item['data'].get('description', 'Decision point')}
        
        Selected option: {selected_option['text']}
        
        Provide a response describing the consequences and implications of this decision.
        """
        
        try:
            if self.use_claude:
                response = self.claude_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
            else:
                response = self.llm_service.send_message(
                    message=message,
                    conversation=conversation,
                    world_id=scenario.world_id
                )
            
            return response.content
        except Exception as e:
            logger.error(f"Error processing decision: {str(e)}")
            return f"You selected: {selected_option['text']}. The simulation will now continue to the next step."
    
    def get_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the simulation state from storage."""
        state = self.storage.get_state(session_id)
        if state:
            self.state = state
            self.state['session_id'] = session_id
        
        return state
    
    def reset_simulation(self) -> Dict[str, Any]:
        """Reset the simulation to the beginning."""
        # Reset state
        self.state = self._initialize_state()
        
        # Store reset state
        session_id = self.storage.store_state(self.state)
        self.state['session_id'] = session_id
        
        # Return a simple message without using the LLM
        return {
            'state': self.state,
            'message': f"Simulation reset. Click 'Start Simulation' to begin the scenario: {self.state['scenario_name']}",
            'options': [{'id': 1, 'text': 'Start Simulation'}],
            'is_decision': False
        }
