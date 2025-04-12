"""
Adapters for ProEthica's existing services.
"""

from typing import Dict, List, Any, Optional, Union

from app.models.world import World
from app.services.application_context_service import ApplicationContextService
from app.services.claude_service import ClaudeService
from app.services.llm_service import LLMService, Conversation as LegacyConversation

from app.agent_module.interfaces.base import (
    SourceInterface,
    ContextProviderInterface,
    LLMInterface
)
from app.agent_module.models.conversation import Conversation


class WorldSourceAdapter(SourceInterface):
    """
    Adapter for ProEthica's World model.
    """
    
    def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Get all available worlds.
        
        Returns:
            List of world objects
        """
        worlds = World.query.all()
        return [
            {
                'id': world.id,
                'name': world.name,
                'description': world.description,
                'ontology_source': world.ontology_source
            }
            for world in worlds
        ]
    
    def get_source_by_id(self, source_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get a specific world by ID.
        
        Args:
            source_id: ID of the world to retrieve
            
        Returns:
            World object or None if not found
        """
        world = World.query.get(source_id)
        if world is None:
            return None
            
        return {
            'id': world.id,
            'name': world.name,
            'description': world.description,
            'ontology_source': world.ontology_source
        }


class ApplicationContextAdapter(ContextProviderInterface):
    """
    Adapter for ProEthica's ApplicationContextService.
    """
    
    def __init__(self):
        """
        Initialize the ApplicationContextAdapter.
        """
        self.app_context_service = ApplicationContextService.get_instance()
    
    def get_context(self, source_id: Union[int, str], query: Optional[str] = None,
                    additional_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get context for a specific world and query.
        
        Args:
            source_id: ID of the world to get context for
            query: Optional query to focus the context
            additional_params: Optional additional parameters for the context
            
        Returns:
            Dictionary containing context information
        """
        params = additional_params or {}
        context = self.app_context_service.get_full_context(
            world_id=source_id,
            scenario_id=params.get('scenario_id'),
            query=query
        )
        
        return context
    
    def format_context(self, context: Dict[str, Any], max_tokens: Optional[int] = None) -> str:
        """
        Format context for LLM consumption.
        
        Args:
            context: Context dictionary from get_context
            max_tokens: Maximum number of tokens to include
            
        Returns:
            Formatted context string
        """
        return self.app_context_service.format_context_for_llm(context, max_tokens)
    
    def get_guidelines(self, source_id: Union[int, str]) -> str:
        """
        Get guidelines for a specific world.
        
        Args:
            source_id: ID of the world to get guidelines for
            
        Returns:
            Guidelines text for the world
        """
        world = World.query.get(source_id)
        if world is None:
            return ""
        
        # Extract guidelines from the world
        guidelines = ""
        
        if hasattr(world, 'guidelines') and world.guidelines:
            guidelines = world.guidelines
        
        # If no direct guidelines attribute, use the world description as a fallback
        if not guidelines and world.description:
            guidelines = f"# Guidelines for {world.name}\n\n{world.description}"
        
        return guidelines


class ClaudeServiceAdapter(LLMInterface):
    """
    Adapter for ProEthica's ClaudeService.
    """
    
    def __init__(self, claude_service: Optional[ClaudeService] = None, api_key: Optional[str] = None):
        """
        Initialize the ClaudeServiceAdapter.
        
        Args:
            claude_service: Optional ClaudeService instance to use
            api_key: Optional API key for Claude
        """
        import os
        
        # Use provided service or create a new one
        if claude_service:
            self.claude_service = claude_service
        else:
            # Use provided API key or get from environment
            api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            self.claude_service = ClaudeService(api_key=api_key)
    
    def send_message(self, message: str, conversation: Dict[str, Any], 
                     context: Optional[str] = None, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Send a message to Claude.
        
        Args:
            message: User message
            conversation: Conversation dictionary
            context: Optional context information
            source_id: Optional world ID
            
        Returns:
            Message response object
        """
        # Convert our conversation format to legacy format
        if isinstance(conversation, Conversation):
            conversation_dict = conversation.to_dict()
        else:
            conversation_dict = conversation
            
        legacy_conversation = LegacyConversation.from_dict(conversation_dict)
        
        # Send message to Claude service
        response = self.claude_service.send_message_with_context(
            message=message,
            conversation=legacy_conversation,
            application_context=context,
            world_id=source_id or legacy_conversation.metadata.get('world_id')
        )
        
        # Return response as a dictionary
        return response.to_dict()
    
    def get_suggestions(self, conversation: Dict[str, Any], 
                        source_id: Optional[Union[int, str]] = None) -> List[Dict[str, Any]]:
        """
        Get suggested prompts based on conversation history.
        
        Args:
            conversation: Conversation dictionary 
            source_id: Optional world ID
            
        Returns:
            List of suggestion objects
        """
        # Convert our conversation format to legacy format if needed
        if isinstance(conversation, Conversation):
            conversation_dict = conversation.to_dict()
        else:
            conversation_dict = conversation
            
        legacy_conversation = LegacyConversation.from_dict(conversation_dict)
        
        # Get suggestions from Claude service
        world_id = source_id or legacy_conversation.metadata.get('world_id')
        
        # Use the prompt options method
        options = self.claude_service.get_prompt_options(
            conversation=legacy_conversation,
            world_id=world_id
        )
        
        # Convert options to standard format
        return [
            {
                'id': i,
                'text': option
            } 
            for i, option in enumerate(options)
        ]


class LLMServiceAdapter(LLMInterface):
    """
    Adapter for ProEthica's LLMService.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """
        Initialize the LLMServiceAdapter.
        
        Args:
            llm_service: Optional LLMService instance to use
        """
        # Use provided service or create a new one
        self.llm_service = llm_service or LLMService()
    
    def send_message(self, message: str, conversation: Dict[str, Any], 
                     context: Optional[str] = None, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Send a message to the language model.
        
        Args:
            message: User message
            conversation: Conversation dictionary
            context: Optional context information
            source_id: Optional world ID
            
        Returns:
            Message response object
        """
        # Convert our conversation format to legacy format
        if isinstance(conversation, Conversation):
            conversation_dict = conversation.to_dict()
        else:
            conversation_dict = conversation
            
        legacy_conversation = LegacyConversation.from_dict(conversation_dict)
        
        # Send message to LLM service
        response = self.llm_service.send_message_with_context(
            message=message,
            conversation=legacy_conversation,
            application_context=context,
            world_id=source_id or legacy_conversation.metadata.get('world_id')
        )
        
        # Return response as a dictionary
        return response.to_dict()
    
    def get_suggestions(self, conversation: Dict[str, Any], 
                        source_id: Optional[Union[int, str]] = None) -> List[Dict[str, Any]]:
        """
        Get suggested prompts based on conversation history.
        
        Args:
            conversation: Conversation dictionary
            source_id: Optional world ID
            
        Returns:
            List of suggestion objects
        """
        # Convert our conversation format to legacy format if needed
        if isinstance(conversation, Conversation):
            conversation_dict = conversation.to_dict()
        else:
            conversation_dict = conversation
            
        legacy_conversation = LegacyConversation.from_dict(conversation_dict)
        
        # Get suggestions from LLM service
        world_id = source_id or legacy_conversation.metadata.get('world_id')
        
        # Use the prompt options method
        options = self.llm_service.get_prompt_options(
            conversation=legacy_conversation,
            world_id=world_id
        )
        
        # Convert options to standard format
        return [
            {
                'id': i,
                'text': option
            } 
            for i, option in enumerate(options)
        ]
