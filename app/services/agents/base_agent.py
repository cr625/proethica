"""
Base Agent class for the AI Ethical Decision-Making Simulator.

This module provides the BaseAgent class that serves as a foundation
for all specialized agents in the multi-agent architecture.
"""

from typing import Dict, List, Any, Optional, Union
import logging

# Set up logging
logger = logging.getLogger(__name__)

class BaseAgent:
    """
    Base class for all agents in the multi-agent architecture.
    
    This class provides common functionality and interface definitions
    that all specialized agents should implement.
    """
    
    def __init__(self, name: str, world_id: Optional[int] = None):
        """
        Initialize the base agent.
        
        Args:
            name: Name of the agent
            world_id: ID of the world for context (optional)
        """
        self.name = name
        self.world_id = world_id
        logger.info(f"Initialized {name} agent")
    
    def analyze(self, scenario_data: Dict[str, Any], decision_text: str, 
               options: List[Union[str, Dict[str, Any]]], 
               previous_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Analyze a decision in the context of the agent's specialty.
        
        Args:
            scenario_data: Dictionary containing scenario data
            decision_text: Text describing the decision to analyze
            options: List of decision options
            previous_results: Results from previous agents in the chain (optional)
            
        Returns:
            Dictionary containing analysis results
        """
        raise NotImplementedError("Subclasses must implement analyze method")
    
    def _format_options(self, options: List[Union[str, Dict[str, Any]]]) -> str:
        """
        Format options for LLM input.
        
        Args:
            options: List of options (strings or dictionaries)
            
        Returns:
            Formatted options string
        """
        formatted = []
        for i, option in enumerate(options):
            option_text = option
            if isinstance(option, dict) and 'text' in option:
                option_text = option['text']
            formatted.append(f"{i+1}. {option_text}")
        return "\n".join(formatted)
    
    def _extract_scenario_data(self, scenario_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and normalize scenario data.
        
        Args:
            scenario_data: Dictionary containing scenario data
            
        Returns:
            Normalized scenario data dictionary
        """
        # Ensure basic fields exist
        normalized = {
            'id': scenario_data.get('id'),
            'name': scenario_data.get('name', 'Unnamed scenario'),
            'description': scenario_data.get('description', ''),
            'world_id': scenario_data.get('world_id', self.world_id)
        }
        
        # Copy other fields
        for key, value in scenario_data.items():
            if key not in normalized:
                normalized[key] = value
        
        return normalized
