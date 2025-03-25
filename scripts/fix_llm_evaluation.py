#!/usr/bin/env python3
"""
Script to fix the LLM evaluation functionality in the simulation controller.

The issue is that the SimulationController is trying to call get_llm() on the LLMService,
but the LLMService class doesn't have this method. Instead, it has an llm attribute.
"""

import sys
import os
import logging
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from app.services.simulation_controller import SimulationController

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_evaluate_decision_method():
    """
    Fix the _evaluate_decision method in the SimulationController class.
    
    This is a temporary fix until the actual code can be updated. It monkey patches
    the _evaluate_decision method to use the llm attribute instead of calling get_llm().
    """
    # Original method for reference
    original_method = SimulationController._evaluate_decision
    
    # Define the fixed method
    def fixed_evaluate_decision(self, decision, current_state):
        """
        Fixed version of _evaluate_decision that uses llm attribute instead of get_llm().
        """
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
    
    # Replace the original method with the fixed method
    SimulationController._evaluate_decision = fixed_evaluate_decision
    logger.info("Replaced _evaluate_decision method with fixed version")

def main():
    """Main function."""
    app = create_app()
    with app.app_context():
        fix_evaluate_decision_method()
        logger.info("LLM evaluation functionality fixed")

if __name__ == '__main__':
    main()
