"""
Anthropic Claude Adapter

This module provides an adapter for Anthropic's Claude API to be used
with the hosted LLM MCP server for ontology enhancement.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

# Try importing Anthropic library
try:
    import anthropic
    from anthropic import Anthropic
except ImportError:
    logging.error("Anthropic package not found. Please install it with 'pip install anthropic'")
    raise

logger = logging.getLogger(__name__)

class AnthropicAdapter:
    """
    Adapter for Anthropic's Claude API.
    
    This class provides a standardized interface to interact with Claude models
    for ontology-related tasks, including concept analysis, relationship suggestion,
    and hierarchy expansion.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the Anthropic adapter.
        
        Args:
            api_key: The Anthropic API key. If not provided, it will be read from environment.
            model: The Claude model to use. If not provided, will use centralized config.
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.error("No Anthropic API key provided")
            raise ValueError("Anthropic API key is required")
        
        # Use centralized model configuration if model not specified
        if model is None:
            from config.models import ModelConfig
            model = ModelConfig.get_claude_model("default")
        self.model = model
        self.client = Anthropic(api_key=self.api_key)
        logger.info(f"Initialized Anthropic adapter with model: {model}")
        
        # System prompts for different tasks
        self.task_prompts = {
            "analyze_concept": """
            You are an ontology expert tasked with analyzing concepts for an ethical reasoning system.
            Extract key properties, relevant relationships, and provide a structured analysis.
            Focus on the conceptual characteristics that would be relevant in an ontology.
            For each concept, identify:
            1. Core properties and attributes
            2. Semantic relationships to other concepts
            3. Hierarchical positioning (what it's a subclass of, what subclasses it might have)
            4. Axioms or constraints that apply to this concept
            5. Any ambiguities or multiple interpretations that should be addressed

            Return your analysis in a structured JSON format with these fields.
            """,
            
            "expand_hierarchy": """
            You are an ontology expert tasked with expanding concept hierarchies for an ethical reasoning system.
            Given a parent concept, generate a well-structured hierarchy of sub-concepts that:
            1. Are distinct from each other
            2. Collectively cover the scope of the parent concept
            3. Follow ontological principles (clear boundaries, no overlaps, essential characteristics)
            4. Are relevant to the domain specified
            
            For each sub-concept, provide:
            - A clear name
            - A concise definition
            - Key properties that distinguish it from siblings
            - Potential further sub-concepts if appropriate

            Return a structured JSON with the hierarchical breakdown.
            """,
            
            "explain_concept": """
            You are an ontology expert tasked with explaining concepts from an ethical reasoning system.
            Provide a clear, precise explanation of the given concept that:
            1. Defines the concept in relation to its ontological position
            2. Explains its significance and role in the domain
            3. Highlights key relationships to other concepts
            4. Provides examples that illustrate the concept in practice
            
            Adjust your explanation based on the specified audience and level of detail.
            For expert audience: Use precise technical language and ontological terminology.
            For novice audience: Use accessible language while maintaining accuracy.
            
            Your explanation should be both technically correct and contextually meaningful.
            """
        }

    async def complete(self, 
                      task: str, 
                      content: str, 
                      **kwargs) -> Dict[str, Any]:
        """
        Generate a completion using Claude for a specific ontology task.
        
        Args:
            task: The ontology task (analyze_concept, expand_hierarchy, explain_concept)
            content: The main content for the prompt
            **kwargs: Additional arguments to pass to the Anthropic API
            
        Returns:
            A dictionary containing the model's response and metadata
        """
        # Get the appropriate system prompt for the task
        system_prompt = self.task_prompts.get(task, "You are an ontology expert.")
        
        try:
            # Call the Anthropic API
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": content}
                ],
                temperature=kwargs.get("temperature", 0.2),
                max_tokens=kwargs.get("max_tokens", 2000)
            )
            
            # Extract the text response
            result = response.content[0].text if response.content else ""
            
            # If the result appears to be JSON but is in string form, parse it
            if result.strip().startswith("{") and result.strip().endswith("}"):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    # If it looks like JSON but isn't valid, leave as string
                    pass
            
            # Return successful response
            return {
                "success": True,
                "result": result,
                "model": self.model,
                "task": task
            }
            
        except Exception as e:
            logger.error(f"Error calling Anthropic API for task {task}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "task": task
            }
