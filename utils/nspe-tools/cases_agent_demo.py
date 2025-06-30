#!/usr/bin/env python3
"""
Demo script to show how the CasesAgent would work in the agent-based system.

This script demonstrates how to retrieve relevant case studies based on a decision context
and analyze them to provide insights for decision-making.
"""

import os
import sys
import json
import logging
import argparse
from typing import List, Dict, Any, Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app modules
from app import db, create_app
from app.models.document import Document
from app.models.world import World
from app.services.embedding_service import EmbeddingService

# Import the retrieve_cases functions
from utilities.retrieve_cases import search_cases_by_query

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CasesAgentDemo:
    """Demo class to show how the CasesAgent would work."""
    
    def __init__(self, world_id: int):
        """
        Initialize the CasesAgent demo.
        
        Args:
            world_id: ID of the world to get cases for
        """
        self.world_id = world_id
        self.embedding_service = EmbeddingService()
        
        # Get the world
        self.world = World.query.get(world_id)
        if not self.world:
            raise ValueError(f"World with ID {world_id} not found")
        
        logger.info(f"Initialized CasesAgentDemo for world: {self.world.name} (ID: {world_id})")
    
    def analyze(self, scenario_data: Dict[str, Any], decision_text: str, options: List[str], 
               k: int = 3) -> Dict[str, Any]:
        """
        Analyze a decision based on relevant case studies.
        
        Args:
            scenario_data: Dictionary with scenario data
            decision_text: Text describing the decision
            options: List of decision options
            k: Number of relevant cases to retrieve
            
        Returns:
            Dictionary with analysis results
        """
        # Construct a query for relevant cases
        query = self._construct_query(scenario_data, decision_text, options)
        
        # Search for relevant cases
        relevant_cases = search_cases_by_query(query, self.world_id, k)
        
        # Analyze the cases
        analysis = self._analyze_cases(relevant_cases, decision_text, options)
        
        return {
            "relevant_cases": relevant_cases,
            "analysis": analysis
        }
    
    def _construct_query(self, scenario_data: Dict[str, Any], decision_text: str, options: List[str]) -> str:
        """
        Construct a query for relevant cases.
        
        Args:
            scenario_data: Dictionary with scenario data
            decision_text: Text describing the decision
            options: List of decision options
            
        Returns:
            Query string
        """
        query = f"Decision: {decision_text}\n\n"
        
        # Add scenario information
        if 'name' in scenario_data:
            query += f"Scenario: {scenario_data['name']}\n"
        if 'description' in scenario_data:
            query += f"Description: {scenario_data['description']}\n\n"
        
        # Add options
        query += "Options:\n"
        for i, option in enumerate(options):
            query += f"{i+1}. {option}\n"
        
        return query
    
    def _analyze_cases(self, cases: List[Dict[str, Any]], decision_text: str, options: List[str]) -> str:
        """
        Analyze relevant cases to provide insights for decision-making.
        
        Args:
            cases: List of relevant cases
            decision_text: Text describing the decision
            options: List of decision options
            
        Returns:
            Analysis text
        """
        # In a real implementation, this would use LangChain to analyze the cases
        # For this demo, we'll just return a simple analysis
        
        if not cases:
            return "No relevant cases found."
        
        analysis = f"Analysis based on {len(cases)} relevant cases:\n\n"
        
        for i, case in enumerate(cases):
            analysis += f"Case {i+1}: {case['title']}\n"
            analysis += f"Similarity Score: {case.get('similarity_score', 0):.4f}\n"
            
            # Extract key points from the case
            if 'matching_chunk' in case:
                analysis += f"Key Points: {case['matching_chunk'][:200]}...\n\n"
            else:
                analysis += f"Content: {case['content'][:200]}...\n\n"
        
        # Add recommendations for each option
        analysis += "Recommendations based on similar cases:\n\n"
        
        for i, option in enumerate(options):
            analysis += f"Option {i+1}: {option}\n"
            analysis += f"Based on the similar cases, this option appears to be {'ethically sound' if i % 2 == 0 else 'potentially problematic'}.\n"
            analysis += f"Relevant case: {cases[min(i, len(cases)-1)]['title']}\n\n"
        
        return analysis

def main():
    """Main function to run the demo."""
    parser = argparse.ArgumentParser(description='Demo of how the CasesAgent would work')
    parser.add_argument('--world-id', '-w', type=int, default=2,
                        help='ID of the world to get cases for (default: 2 for Engineering Ethics (US) world)')
    parser.add_argument('--decision', '-d', type=str,
                        help='Decision text (default: example decision)')
    parser.add_argument('--output', '-o', type=str,
                        help='Output file to save results to (JSON format)')
    
    args = parser.parse_args()
    
    # Example decision if not provided
    if not args.decision:
        args.decision = "Should the engineer report a potential safety issue with a bridge design to the public authorities?"
    
    # Example scenario data
    scenario_data = {
        "name": "Bridge Safety Concern",
        "description": "An engineer discovers a potential safety issue with a bridge design that has already been approved and construction has begun. The engineer's supervisor dismisses the concern and instructs the engineer to proceed with the project as planned."
    }
    
    # Example options
    options = [
        "Report the safety concern to public authorities immediately",
        "Discuss the issue further with the supervisor and try to convince them of the seriousness",
        "Document the concern but proceed as instructed",
        "Anonymously leak information about the safety concern to the media"
    ]
    
    # Initialize Flask app
    app = create_app()
    
    with app.app_context():
        try:
            # Initialize the CasesAgent demo
            agent = CasesAgentDemo(args.world_id)
            
            # Analyze the decision
            result = agent.analyze(scenario_data, args.decision, options)
            
            # Print the analysis
            print("\n" + "="*80)
            print(f"DECISION: {args.decision}")
            print("="*80 + "\n")
            
            print(result['analysis'])
            
            # Save to file if requested
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\nResults saved to {args.output}")
            
        except Exception as e:
            logger.error(f"Error running CasesAgent demo: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    main()
