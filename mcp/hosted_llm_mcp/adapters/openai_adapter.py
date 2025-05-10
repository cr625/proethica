"""
OpenAI API Adapter

This module provides an adapter for OpenAI's API to be used
with the hosted LLM MCP server for ontology enhancement.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

# Try importing OpenAI library
try:
    from openai import OpenAI
    import openai
except ImportError:
    logging.error("OpenAI package not found. Please install it with 'pip install openai'")
    raise

logger = logging.getLogger(__name__)

class OpenAIAdapter:
    """
    Adapter for OpenAI's API.
    
    This class provides a standardized interface to interact with OpenAI models
    for ontology-related tasks, including relationship suggestion, ontology validation,
    and entity classification.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize the OpenAI adapter.
        
        Args:
            api_key: The OpenAI API key. If not provided, it will be read from environment.
            model: The OpenAI model to use.
        """
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            logger.error("No OpenAI API key provided")
            raise ValueError("OpenAI API key is required")
            
        self.model = model
        self.client = OpenAI(api_key=self.api_key)
        logger.info(f"Initialized OpenAI adapter with model: {model}")
        
        # System prompts for different tasks
        self.task_prompts = {
            "suggest_relationships": """
            You are an ontology expert tasked with suggesting relationships between concepts for an ethical reasoning system.
            Identify meaningful, precise semantic relationships between the provided concepts.
            For each relationship, provide:
            1. The relationship type (e.g., 'is-a', 'has-part', 'influences', 'depends-on', etc.)
            2. The direction of the relationship
            3. A precise description of how the concepts relate
            4. A confidence score (0-1) for each suggested relationship
            5. An explanation of the reasoning behind this relationship

            Consider the domain context when suggesting relationships.
            Focus on relationships that would be most valuable in an ethical reasoning ontology.
            Return your suggestions in a structured JSON format.
            """,
            
            "validate_ontology": """
            You are an ontology validation expert tasked with checking the consistency and coherence of ontology concepts.
            Analyze the provided ontology elements to identify:
            1. Inconsistencies or contradictions
            2. Missing essential relationships
            3. Ambiguous concepts that need clarification
            4. Redundant or overlapping concepts
            5. Structural issues with the hierarchy

            For each issue found, provide:
            - A clear description of the problem
            - The specific concepts or relationships involved
            - A suggested resolution
            - The severity level (high, medium, low)

            If no issues are found, confirm the ontology section is valid.
            Return a structured JSON with your validation results.
            """,
            
            "classify_entity": """
            You are an ontology expert tasked with classifying entities within an ethical reasoning system.
            Analyze the provided entity and determine where it fits within the ontology hierarchy.
            
            For the entity, provide:
            1. The most specific concept class it belongs to
            2. Alternative classifications if multiple are reasonable
            3. Key properties that justify this classification
            4. Confidence score for the classification (0-1)
            5. Potential relationships to other parts of the ontology
            
            Consider the provided ontology context in your analysis.
            Return a structured JSON with your classification results.
            """
        }

    async def complete(self, 
                      task: str, 
                      content: str, 
                      **kwargs) -> Dict[str, Any]:
        """
        Generate a completion using OpenAI for a specific ontology task.
        
        Args:
            task: The ontology task (suggest_relationships, validate_ontology, classify_entity)
            content: The main content for the prompt
            **kwargs: Additional arguments to pass to the OpenAI API
            
        Returns:
            A dictionary containing the model's response and metadata
        """
        # Get the appropriate system prompt for the task
        system_prompt = self.task_prompts.get(task, "You are an ontology expert.")
        
        try:
            # Call the OpenAI API with Response Format JSON
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content}
                ],
                temperature=kwargs.get("temperature", 0.2),
                max_tokens=kwargs.get("max_tokens", 2000),
                response_format={"type": "json_object"}
            )
            
            # Extract the text response
            result = response.choices[0].message.content if response.choices else ""
            
            # Parse the JSON response
            try:
                result = json.loads(result)
            except json.JSONDecodeError as e:
                logger.warning(f"Error parsing JSON response: {str(e)}. Returning raw string.")
            
            # Return successful response
            return {
                "success": True,
                "result": result,
                "model": self.model,
                "task": task
            }
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API for task {task}: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "task": task
            }
