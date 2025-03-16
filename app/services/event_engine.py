from typing import TypedDict, Dict, List, Any
from langgraph.graph import StateGraph
import json

class ScenarioState(TypedDict):
    """Type definition for the state of a scenario in the LangGraph workflow."""
    characters: Dict[str, Dict[str, Any]]
    conditions: Dict[str, List[str]]
    resources: Dict[str, int]
    timeline: List[Dict[str, Any]]
    current_time: int

class EventEngine:
    """Engine for processing events in scenarios using LangGraph."""
    
    def __init__(self):
        """Initialize the event engine with a LangGraph workflow."""
        self.workflow = StateGraph(ScenarioState)
        self._setup_nodes()
        self._setup_edges()
        self.compiled_workflow = self.workflow.compile()
    
    def _setup_nodes(self):
        """Define the nodes for the LangGraph workflow."""
        
        @self.workflow.node
        def assess_situation(state: ScenarioState) -> Dict[str, ScenarioState]:
            """Assess the current state of the scenario."""
            # This would typically involve LLM reasoning about the current state
            # For now, we'll just return the state unchanged
            return {"state": state}
        
        @self.workflow.node
        def generate_options(state: ScenarioState) -> Dict[str, Any]:
            """Generate possible decisions based on the current state."""
            # This would typically involve LLM reasoning to generate options
            # For now, we'll return a simple placeholder
            options = ["Option 1", "Option 2", "Option 3"]
            return {"state": state, "options": options}
        
        @self.workflow.node
        def evaluate_decision(state: ScenarioState, decision: str) -> Dict[str, Any]:
            """Evaluate a decision against rules and ethics."""
            # This would typically involve LLM reasoning for evaluation
            # For now, we'll return a simple placeholder
            evaluation = {
                "rules_compliance": 0.8,
                "ethical_evaluation": 0.7,
                "reasoning": f"Evaluation of decision: {decision}"
            }
            return {"state": state, "evaluation": evaluation}
    
    def _setup_edges(self):
        """Define the edges connecting the nodes in the workflow."""
        # Define the main flow
        self.workflow.add_edge("assess_situation", "generate_options")
        
        # Decision evaluation is conditional based on user input
        self.workflow.add_conditional_edges(
            "generate_options",
            lambda state_and_options: "evaluate_decision",
            {
                "evaluate_decision": lambda state_and_options: {
                    "state": state_and_options["state"],
                    "decision": "Selected option"  # This would come from user input
                }
            }
        )
    
    def process_scenario(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a scenario through the LangGraph workflow.
        
        Args:
            scenario_data: Dictionary containing scenario data from the database
            
        Returns:
            Dictionary containing the workflow results
        """
        # Convert database scenario to LangGraph state
        initial_state = self._convert_to_state(scenario_data)
        
        # Run the workflow
        result = self.compiled_workflow.invoke(initial_state)
        return result
    
    def _convert_to_state(self, scenario_data: Dict[str, Any]) -> ScenarioState:
        """
        Convert database scenario data to LangGraph state.
        
        Args:
            scenario_data: Dictionary containing scenario data from the database
            
        Returns:
            ScenarioState object for LangGraph
        """
        # Extract characters
        characters = {}
        for char in scenario_data.get('characters', []):
            characters[char['name']] = {
                'role': char.get('role', ''),
                'attributes': char.get('attributes', {})
            }
        
        # Extract conditions
        conditions = {}
        for char in scenario_data.get('characters', []):
            char_conditions = []
            for cond in char.get('conditions', []):
                if cond.get('is_active', True):
                    char_conditions.append(cond['name'])
            conditions[char['name']] = char_conditions
        
        # Extract resources
        resources = {}
        for res in scenario_data.get('resources', []):
            resources[res['name']] = res.get('quantity', 1)
        
        # Extract timeline
        timeline = []
        for event in scenario_data.get('events', []):
            timeline.append({
                'time': event.get('event_time', ''),
                'description': event.get('description', ''),
                'character': event.get('character', {}).get('name', '') if event.get('character') else '',
                'action': event.get('action', {}).get('name', '') if event.get('action') else ''
            })
        
        # Sort timeline by time
        timeline.sort(key=lambda x: x['time'])
        
        # Create state
        state: ScenarioState = {
            'characters': characters,
            'conditions': conditions,
            'resources': resources,
            'timeline': timeline,
            'current_time': 0  # Start at time 0
        }
        
        return state
