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
from langchain_classic.chains import LLMChain
from langchain_classic.prompts import PromptTemplate
from flask import current_app
from app.config import Config

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
            from models import ModelConfig
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
    
    def create_chain(self, template: str, input_variables: List[str]) -> LLMChain:
        """
        Create a LangChain with the specified template.
        
        Args:
            template: Prompt template string
            input_variables: List of input variable names
            
        Returns:
            LangChain instance
        """
        try:
            prompt = PromptTemplate(
                template=template,
                input_variables=input_variables
            )
            return LLMChain(llm=self.llm, prompt=prompt)
        except Exception as e:
            logger.error(f"Error creating LangChain: {str(e)}")
            raise
    
    def run_chain(self, chain: LLMChain, **kwargs) -> str:
        """
        Run a chain with the specified inputs.
        
        Args:
            chain: LangChain instance
            **kwargs: Input variables for the chain
            
        Returns:
            Chain output
        """
        # Check if we should use Claude or return a mock response
        # Use Flask app config if available, fall back to Config class
        use_claude = True
        try:
            use_claude = current_app.config.get('USE_CLAUDE', True)
            logger.info(f"Using USE_CLAUDE setting from app config: {use_claude}")
        except RuntimeError:
            # We're outside of application context, use Config class instead
            use_claude = Config.USE_CLAUDE
            logger.info(f"Using USE_CLAUDE setting from Config class: {use_claude}")
        
        if use_claude:
            try:
                logger.info("Running actual LangChain with Claude for response")
                return chain.run(**kwargs)
            except Exception as e:
                logger.error(f"Error running LangChain: {str(e)}")
                # Return a default response in case of error
                return "I encountered an error processing your request. Please try again or ask a different question."
        else:
            # Generate a mock response when USE_CLAUDE is False
            logger.info("Using mock response instead of running LangChain with Claude")
            # Create a summary of the input parameters to include in the mock response
            input_summary = ", ".join([f"{k}: {str(v)[:50]}..." for k, v in kwargs.items()])
            return f"This is a mock LangChain response.\n\nRequest parameters: {input_summary}\n\nMock responses are being used because USE_CLAUDE is set to false in the environment configuration."
    
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
