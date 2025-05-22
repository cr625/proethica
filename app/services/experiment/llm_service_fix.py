"""
Fixed version of the LLM service with proper engineering ethics examples and fixes.

This file contains a modified version of the LLM initialization to:
1. Ensure we're using live Claude calls instead of mock data
2. Replace military medical triage examples with appropriate engineering ethics examples
"""

import logging
import os
from typing import Dict, List, Any, Optional
from langchain.llms.base import BaseLLM
from langchain_community.llms.fake import FakeListLLM
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)

def create_fixed_mock_llm() -> BaseLLM:
    """
    Create a mock LLM with engineering ethics examples for development and testing.
    
    Returns:
        A fake LLM with engineering ethics-focused responses
    """
    responses = [
        # Chat responses with engineering ethics focus
        "I understand you're looking at an engineering ethics case study. This appears to be related to professional responsibility in engineering practice. In such scenarios, engineers must make decisions that balance technical considerations with their ethical responsibilities to public safety, professional integrity, and corporate obligations. Would you like me to explain the key ethical principles involved in engineering ethical decision-making?",
        
        "Based on the scenario you're viewing, there are several ethical considerations at play. The primary ethical frameworks relevant to engineering ethics include the NSPE Code of Ethics, which emphasizes public safety, professional integrity, and responsibility to employers/clients. In this engineering scenario specifically, the key question appears to be whether the engineer's actions upheld these professional standards. Would you like me to analyze this specific scenario in more detail?",
        
        "Looking at the engineering ethics scenario you're viewing, I can see this involves potential conflicts between professional responsibilities and business interests. Engineers have ethical obligations to prioritize public safety, be honest about limitations, and maintain professional integrity. In this case, the key question appears to be whether the design meets safety standards despite cost pressures. Would you like me to discuss how professional engineering codes of ethics would apply here?",
        
        # Options responses (as JSON strings)
        '[{"id": 1, "text": "Explain the engineering ethics principles in this case"}, {"id": 2, "text": "What would be the most ethical decision here?"}, {"id": 3, "text": "Show me similar engineering cases"}, {"id": 4, "text": "What NSPE guidelines apply to this situation?"}]',
        
        '[{"id": 1, "text": "Analyze this from a public safety perspective"}, {"id": 2, "text": "How might professional integrity be at stake?"}, {"id": 3, "text": "What are the competing obligations here?"}, {"id": 4, "text": "How do risk assessment principles apply in this case?"}]',
        
        '[{"id": 1, "text": "What are the key facts I should consider?"}, {"id": 2, "text": "How do I balance technical and ethical considerations?"}, {"id": 3, "text": "What precedents exist in similar engineering cases?"}, {"id": 4, "text": "What would be the consequences of each option?"}]'
    ]
    return FakeListLLM(responses=responses)

def get_real_llm(model_name: str = None) -> Optional[BaseLLM]:
    """
    Attempt to initialize a real LLM connection based on environment variables.
    
    Args:
        model_name: Optional model name to use
        
    Returns:
        LLM instance if successful, None if not
    """
    try:
        # Check for Anthropic/Claude configuration
        if 'ANTHROPIC_API_KEY' in os.environ or model_name and 'claude' in model_name.lower():
            logger.info("Initializing Claude LLM")
            try:
                from langchain_anthropic import ChatAnthropic
                
                # Get the API key
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                if not api_key:
                    logger.warning("No ANTHROPIC_API_KEY found in environment variables")
                    return None
                
                # Determine model to use
                if not model_name:
                    # Try to get from environment, or use a fallback list of models
                    model_name = os.environ.get('ANTHROPIC_MODEL')
                    
                    # If model not specified, try these models in order
                    if not model_name:
                        for possible_model in [
                            'claude-3-7-sonnet-20250219',  # The one mentioned in logs
                            'claude-3-opus-20240229',
                            'claude-3-sonnet-20240229',
                            'claude-3-haiku-20240307',
                            'claude-2.1',
                            'claude-2.0'
                        ]:
                            try:
                                # Try to create with this model
                                logger.info(f"Trying model: {possible_model}")
                                llm = ChatAnthropic(
                                    anthropic_api_key=api_key,
                                    model_name=possible_model,
                                    temperature=0.2,
                                    max_tokens=4000
                                )
                                # Test the model with a simple prompt
                                llm.invoke("Hello")
                                logger.info(f"Successfully connected to model: {possible_model}")
                                return llm
                            except Exception as e:
                                logger.warning(f"Model {possible_model} not available: {str(e)}")
                                continue
                        
                        # If we get here, none of the models worked
                        logger.error("All Claude models failed, falling back to mock LLM")
                        return None
                
                # Create the LLM with the specified model
                logger.info(f"Creating ChatAnthropic with model: {model_name}")
                return ChatAnthropic(
                    anthropic_api_key=api_key, 
                    model_name=model_name,
                    temperature=0.2,
                    max_tokens=4000
                )
            except ImportError:
                logger.warning("langchain_anthropic not available, cannot initialize Claude")
                return None
            except Exception as e:
                logger.exception(f"Error initializing Claude: {str(e)}")
                return None
        
        # Check for OpenAI configuration
        elif 'OPENAI_API_KEY' in os.environ:
            logger.info("Initializing OpenAI LLM")
            try:
                from langchain_openai import ChatOpenAI
                
                # Create the LLM
                return ChatOpenAI(
                    model_name=model_name or os.environ.get('OPENAI_MODEL', 'gpt-4'),
                    temperature=0.2,
                    max_tokens=2000
                )
            except ImportError:
                logger.warning("langchain_openai not available, cannot initialize OpenAI")
                return None
            except Exception as e:
                logger.exception(f"Error initializing OpenAI: {str(e)}")
                return None
                
        return None
                
    except Exception as e:
        logger.exception(f"Error initializing real LLM: {str(e)}")
        return None

def fixed_init(self, model_name: str = None, llm: Optional[BaseLLM] = None):
    """
    Fixed initialization method for LLMService to prioritize live LLM.
    
    Args:
        model_name: Name of the language model to use
        llm: Language model instance (optional)
    """
    # Use the model name from environment if exists, otherwise try the model that works in the environment
    if model_name is None:
        model_name = os.environ.get('ANTHROPIC_MODEL', 'claude-3-7-sonnet-20250219')
    
    # Store the model name
    self.model_name = model_name
    logger.info(f"LLMService initialized with model: {model_name}")
    
    # Try to use the provided LLM first
    if llm is not None:
        logger.info(f"Using provided LLM instance")
        self.llm = llm
    else:
        # Try to get a real LLM
        real_llm = get_real_llm(model_name)
        
        if real_llm is not None:
            logger.info(f"Using real LLM: {model_name}")
            self.llm = real_llm
        else:
            # Fall back to mock LLM with engineering ethics examples
            logger.warning(f"Failed to initialize real LLM, falling back to mock LLM with engineering ethics examples")
            self.llm = create_fixed_mock_llm()
    
    # Initialize MCP client
    from app.services.mcp_client import MCPClient
    self.mcp_client = MCPClient.get_instance()
    
    # Log MCP client status
    if hasattr(self.mcp_client, 'mcp_server_url'):
        logger.info(f"MCP client initialized with server URL: {self.mcp_client.mcp_server_url}")
    
    # Setup prompt templates - keeps the original templates from LLMService.__init__
    from langchain.prompts import PromptTemplate
    
    self.chat_prompt = PromptTemplate(
        input_variables=["context", "message", "guidelines"],
        template="""
        You are an AI assistant helping users with ethical decision-making scenarios.
        
        Conversation history:
        {context}
        
        Guidelines for reference:
        {guidelines}
        
        User message: {message}
        
        Respond to the user's message, taking into account the conversation history and the guidelines provided.
        """
    )
    
    self.options_prompt = PromptTemplate(
        input_variables=["context", "guidelines"],
        template="""
        You are an AI assistant helping users with ethical decision-making scenarios.
        
        Conversation history:
        {context}
        
        Guidelines for reference:
        {guidelines}
        
        Generate 3-5 suggested prompt options that would be helpful for the user to select based on the conversation history and guidelines.
        Format your response as a JSON array of objects with 'id' and 'text' fields.
        Example: [{"id": 1, "text": "Tell me more about this scenario"}, {"id": 2, "text": "What ethical principles apply here?"}]
        """
    )
    
    # Setup runnable sequences (replacing deprecated LLMChain)
    self.chat_chain = self.chat_prompt | self.llm
    self.options_chain = self.options_prompt | self.llm
    
    # Set default options for testing
    self._default_options = [
        {"id": 1, "text": "Tell me more about this engineering ethics scenario"},
        {"id": 2, "text": "What engineering principles apply here?"},
        {"id": 3, "text": "How should I approach this engineering decision?"}
    ]
