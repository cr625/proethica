#!/usr/bin/env python
"""
Test script for ApplicationContextService.

This script tests the ApplicationContextService to verify it collects and formats
context correctly.
"""

import sys
import os
import json

# Add the parent directory to the path to allow importing app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.services.application_context_service import ApplicationContextService
from app.models.world import World
from app.models.scenario import Scenario

def test_context_collection():
    """Test collection of context from ApplicationContextService."""
    print("Testing ApplicationContextService context collection...")
    
    # Initialize the application
    app = create_app()
    with app.app_context():
        # Get service instance
        app_context_service = ApplicationContextService.get_instance()
        
        # Get the first world and scenario for testing
        world = World.query.first()
        world_id = world.id if world else None
        
        scenario = Scenario.query.first()
        scenario_id = scenario.id if scenario else None
        
        print(f"Using world_id={world_id}, scenario_id={scenario_id}")
        
        # Test context collection
        context = app_context_service.get_full_context(
            world_id=world_id,
            scenario_id=scenario_id,
            query="Tell me about this world."
        )
        
        # Print context structure
        print("\nContext structure:")
        for key, value in context.items():
            if isinstance(value, dict):
                print(f"{key}: {len(value)} items")
            else:
                print(f"{key}: {type(value)}")
        
        # Test context formatting
        formatted_context = app_context_service.format_context_for_llm(context)
        
        # Print the beginning of the formatted context
        print("\nFormatted context (first 500 chars):")
        print(formatted_context[:500] + "...")
        
        print("\nEstimated token count:", app_context_service._estimate_tokens(formatted_context))
        
        return context, formatted_context

def test_documentation_generation():
    """Test generation of schema documentation."""
    print("\nTesting documentation generation...")
    
    # Initialize the application
    app = create_app()
    with app.app_context():
        # Get service instance
        app_context_service = ApplicationContextService.get_instance()
        
        # Generate documentation
        docs = app_context_service.generate_schema_documentation()
        
        # Print the beginning of the documentation
        print("\nGenerated documentation (first 500 chars):")
        print(docs[:500] + "...")
        
        return docs

if __name__ == "__main__":
    # Run tests
    context, formatted_context = test_context_collection()
    docs = test_documentation_generation()
    
    # Save outputs to files for inspection
    with open('context_output.json', 'w') as f:
        json.dump(context, f, indent=2, default=str)
    
    with open('formatted_context.txt', 'w') as f:
        f.write(formatted_context)
    
    with open('schema_documentation.md', 'w') as f:
        f.write(docs)
    
    print("\nTest completed. Output files generated:")
    print("- context_output.json: Raw context structure")
    print("- formatted_context.txt: Formatted context for LLM")
    print("- schema_documentation.md: Generated schema documentation")
