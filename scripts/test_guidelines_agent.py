#!/usr/bin/env python
"""
Test script for the Guidelines Agent.

This script tests the Guidelines Agent by processing a sample decision
and printing the results.
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.embedding_service import EmbeddingService
from app.services.langchain_claude import LangChainClaudeService
from app.services.agents.guidelines_agent import GuidelinesAgent
from app.services.agent_orchestrator import AgentOrchestrator

def main():
    """Run the Guidelines Agent test."""
    print("Testing Guidelines Agent...")
    
    # Create a test scenario
    test_scenario = {
        "id": 1,
        "name": "Engineering Ethics Dilemma",
        "description": "An engineer discovers a potential safety issue in a building design that has already been approved and construction has begun. The issue could lead to structural problems in certain extreme weather conditions, but the probability is low. Addressing it would require significant delays and cost overruns.",
        "world_id": 2  # Engineering Ethics world
    }
    
    # Create a test decision
    decision_text = "How should the engineer handle the potential safety issue?"
    
    # Create test options
    options = [
        "Report the issue immediately to all stakeholders and recommend halting construction",
        "Conduct further analysis to quantify the risk before making any recommendations",
        "Develop a modified design that addresses the issue with minimal disruption",
        "Document the concern but allow construction to continue since the probability is low"
    ]
    
    # Initialize services
    print("Initializing services...")
    embedding_service = EmbeddingService()
    langchain_claude = LangChainClaudeService.get_instance()
    
    # Test Guidelines Agent directly
    print("\n--- Testing Guidelines Agent Directly ---\n")
    guidelines_agent = GuidelinesAgent(
        embedding_service=embedding_service,
        langchain_claude=langchain_claude,
        world_id=test_scenario["world_id"]
    )
    
    print(f"Processing decision: {decision_text}")
    print(f"Options: {json.dumps(options, indent=2)}")
    
    guidelines_result = guidelines_agent.analyze(
        scenario_data=test_scenario,
        decision_text=decision_text,
        options=options
    )
    
    print("\nGuidelines Agent Analysis:")
    print("-" * 80)
    print(guidelines_result["analysis"])
    print("-" * 80)
    
    # Test Agent Orchestrator
    print("\n--- Testing Agent Orchestrator ---\n")
    agent_orchestrator = AgentOrchestrator(
        embedding_service=embedding_service,
        langchain_claude=langchain_claude,
        world_id=test_scenario["world_id"]
    )
    
    orchestrator_result = agent_orchestrator.process_decision(
        scenario_data=test_scenario,
        decision_text=decision_text,
        options=options
    )
    
    print("\nAgent Orchestrator Synthesis:")
    print("-" * 80)
    print(orchestrator_result["synthesis"])
    print("-" * 80)
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    main()
