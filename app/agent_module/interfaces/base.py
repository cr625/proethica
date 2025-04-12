"""
Base interfaces for agent module integration.

This module defines the abstract interfaces that must be implemented
by applications that want to use the agent module.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Callable


class SourceInterface(ABC):
    """
    Interface for providing context sources to the agent.
    
    In ProEthica, this would be the World model.
    """
    
    @abstractmethod
    def get_all_sources(self) -> List[Dict[str, Any]]:
        """
        Get all available sources.
        
        Returns:
            List of source objects with at least 'id' and 'name' keys
        """
        raise NotImplementedError("Subclasses must implement get_all_sources")
    
    @abstractmethod
    def get_source_by_id(self, source_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        Get a specific source by ID.
        
        Args:
            source_id: ID of the source to retrieve
            
        Returns:
            Source object or None if not found
        """
        raise NotImplementedError("Subclasses must implement get_source_by_id")


class ContextProviderInterface(ABC):
    """
    Interface for providing context to the agent.
    
    In ProEthica, this would use the ApplicationContextService.
    """
    
    @abstractmethod
    def get_context(self, source_id: Union[int, str], query: Optional[str] = None, 
                   additional_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get context for a specific source and query.
        
        Args:
            source_id: ID of the source to get context for
            query: Optional query to focus the context
            additional_params: Optional additional parameters for the context
            
        Returns:
            Dictionary containing context information
        """
        raise NotImplementedError("Subclasses must implement get_context")
    
    @abstractmethod
    def format_context(self, context: Dict[str, Any], max_tokens: Optional[int] = None) -> str:
        """
        Format context for LLM consumption.
        
        Args:
            context: Context dictionary from get_context
            max_tokens: Maximum number of tokens to include
            
        Returns:
            Formatted context string
        """
        raise NotImplementedError("Subclasses must implement format_context")
    
    def get_guidelines(self, source_id: Union[int, str]) -> str:
        """
        Get guidelines for a specific source.
        
        Args:
            source_id: ID of the source to get guidelines for
            
        Returns:
            Guidelines text for the source
        """
        # Default implementation returns empty string
        return ""


class LLMInterface(ABC):
    """
    Interface for language model services.
    
    In ProEthica, this would be the ClaudeService or LLMService.
    """
    
    @abstractmethod
    def send_message(self, message: str, conversation: Dict[str, Any], 
                     context: Optional[str] = None, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Send a message to the language model.
        
        Args:
            message: User message
            conversation: Conversation history
            context: Optional context information
            source_id: Optional source ID
            
        Returns:
            Message response object
        """
        raise NotImplementedError("Subclasses must implement send_message")
    
    @abstractmethod
    def get_suggestions(self, conversation: Dict[str, Any], 
                        source_id: Optional[Union[int, str]] = None) -> List[Dict[str, Any]]:
        """
        Get suggested prompts based on conversation history.
        
        Args:
            conversation: Conversation history
            source_id: Optional source ID
            
        Returns:
            List of suggestion objects with 'id' and 'text' keys
        """
        raise NotImplementedError("Subclasses must implement get_suggestions")


class AuthInterface(ABC):
    """
    Interface for authentication.
    
    This interface is responsible for providing authentication
    functionality to the agent module.
    """
    
    @abstractmethod
    def login_required(self, func: Callable) -> Callable:
        """
        Decorator to require login for a route.
        
        Args:
            func: Function to decorate
            
        Returns:
            Decorated function
        """
        raise NotImplementedError("Subclasses must implement login_required")
    
    @abstractmethod
    def get_current_user(self):
        """
        Get the current user.
        
        Returns:
            Current user object or None if not authenticated
        """
        raise NotImplementedError("Subclasses must implement get_current_user")


class SessionInterface(ABC):
    """
    Interface for session management.
    
    This interface is responsible for storing and retrieving
    conversation data from the session.
    """
    
    @abstractmethod
    def get_conversation(self) -> Optional[Dict[str, Any]]:
        """
        Get the current conversation from the session.
        
        Returns:
            Conversation dictionary
        """
        raise NotImplementedError("Subclasses must implement get_conversation")
    
    @abstractmethod
    def set_conversation(self, conversation: Dict[str, Any]) -> None:
        """
        Store the conversation in the session.
        
        Args:
            conversation: Conversation dictionary
        """
        raise NotImplementedError("Subclasses must implement set_conversation")
    
    @abstractmethod
    def reset_conversation(self, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Reset the conversation.
        
        Args:
            source_id: Optional source ID to associate with the new conversation
            
        Returns:
            New conversation dictionary
        """
        raise NotImplementedError("Subclasses must implement reset_conversation")


class AgentInterface(ABC):
    """
    Interface for agents that can process queries with context.
    """
    
    @abstractmethod
    def process(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a query with given context.
        
        Args:
            query: The user's query
            context: Context information
            
        Returns:
            Processing result
        """
        raise NotImplementedError("Subclasses must implement process")


class AgentChainInterface(ABC):
    """
    Interface for agent chains that coordinate multiple agents.
    """
    
    @abstractmethod
    def add_agent(self, name: str, agent: AgentInterface) -> None:
        """
        Add an agent to the chain.
        
        Args:
            name: Name to identify the agent
            agent: Agent implementation
        """
        raise NotImplementedError("Subclasses must implement add_agent")
    
    @abstractmethod
    def process(self, query: str, initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a query through the agent chain.
        
        Args:
            query: User query
            initial_context: Optional initial context
            
        Returns:
            Processing result
        """
        raise NotImplementedError("Subclasses must implement process")
