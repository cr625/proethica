"""
LangChain Claude Service for the AI Ethical Decision-Making Simulator.

This module provides integration with Claude via LangChain, allowing
for structured prompting and chain-based workflows.
"""

import os
from typing import Dict, List, Any, Optional
import logging
import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import PromptTemplate
from flask import current_app

# Set up logging
logger = logging.getLogger(__name__)

class LangChainClaudeService:
    """Service for using Claude via LangChain."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'LangChainClaudeService':
        """Get singleton instance of LangChainClaudeService."""
        if cls._instance is None:
            cls._instance = LangChainClaudeService()
        return cls._instance
    
    def __init__(self, api_key=None, model=None):
        """
        Initialize the LangChain Claude service.
        
        Args:
            api_key: Anthropic API key (optional, will use env var if not provided)
            model: Claude model to use (optional, will use centralized config if not provided)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
        
        # Use centralized model configuration if model not specified
        if model is None:
            from model_config import ModelConfig
            model = ModelConfig.get_claude_model("default")
        self.model = model
        
        try:
            # Initialize direct Anthropic client for fallback
            self.anthropic_client = anthropic.Anthropic(api_key=self.api_key)
            
            # Initialize LangChain integration
            self.llm = ChatAnthropic(
                model=model,
                anthropic_api_key=self.api_key,
                temperature=0.2  # Lower temperature for more deterministic responses
            )
            logger.info(f"Initialized LangChain Claude service with model: {model}")
        except Exception as e:
            logger.error(f"Error initializing LangChain Claude service: {str(e)}")
            logger.error(f"Consider checking compatibility between langchain-anthropic and anthropic package versions")
            raise
    
    def create_chain(self, template: str, input_variables: List[str]):
        """
        Create a runnable chain with the specified template.

        Args:
            template: Prompt template string
            input_variables: List of input variable names

        Returns:
            Runnable chain (prompt | llm)
        """
        try:
            prompt = PromptTemplate(
                template=template,
                input_variables=input_variables
            )
            return prompt | self.llm
        except Exception as e:
            logger.error(f"Error creating chain: {str(e)}")
            raise

    def run_chain(self, chain, **kwargs) -> str:
        """
        Run a chain with the specified inputs.

        Args:
            chain: Runnable chain
            **kwargs: Input variables for the chain

        Returns:
            Chain output as string
        """
        # Check if we should use Claude or return a mock response
        use_claude = True
        try:
            use_claude = current_app.config.get('USE_CLAUDE', True)
        except RuntimeError:
            use_claude = os.environ.get('USE_CLAUDE', 'true').lower() == 'true'

        if use_claude:
            try:
                logger.info("Running chain with Claude for response")
                result = chain.invoke(kwargs)
                if hasattr(result, 'content'):
                    return result.content
                return str(result)
            except Exception as e:
                logger.error(f"Error running chain: {str(e)}")
                return "I encountered an error processing your request. Please try again or ask a different question."
        else:
            logger.info("Using mock response instead of running chain with Claude")
            input_summary = ", ".join([f"{k}: {str(v)[:50]}..." for k, v in kwargs.items()])
            return f"This is a mock response.\n\nRequest parameters: {input_summary}\n\nMock responses are being used because USE_CLAUDE is set to false in the environment configuration."
    
    def get_guidelines_for_world(self, world_id: Optional[int] = None) -> str:
        """
        Get guidelines for a specific world.
        This reuses the same method from ClaudeService to maintain consistency.
        
        Args:
            world_id: ID of the world (optional)
            
        Returns:
            String containing the guidelines
        """
        # Import here to avoid circular imports
        from app.services.claude_service import ClaudeService
        try:
            claude_service = ClaudeService()
            return claude_service.get_guidelines_for_world(world_id=world_id)
        except Exception as e:
            logger.error(f"Error getting guidelines: {str(e)}")
            return "No specific guidelines available."
