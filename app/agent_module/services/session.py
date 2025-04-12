"""
Session management services for agent module.
"""

from typing import Dict, Any, Optional, Union
import json
from flask import session

from app.agent_module.interfaces.base import SessionInterface
from app.agent_module.models.conversation import Conversation


class FlaskSessionManager(SessionInterface):
    """
    Session manager using Flask's session.
    """
    
    def __init__(self, session_key: str = 'conversation'):
        """
        Initialize the session manager.
        
        Args:
            session_key: Key to use for storing the conversation in session
        """
        self.session_key = session_key
    
    def get_conversation(self) -> Optional[Dict[str, Any]]:
        """
        Get the current conversation from the session.
        
        Returns:
            Conversation dictionary
        """
        conversation_json = session.get(self.session_key)
        if conversation_json is None:
            return None
        
        try:
            if isinstance(conversation_json, str):
                return json.loads(conversation_json)
            return conversation_json
        except json.JSONDecodeError:
            # Return a default conversation if the stored value is invalid
            return None
    
    def set_conversation(self, conversation: Dict[str, Any]) -> None:
        """
        Store the conversation in the session.
        
        Args:
            conversation: Conversation dictionary
        """
        if isinstance(conversation, Conversation):
            conversation = conversation.to_dict()
        
        session[self.session_key] = conversation
    
    def reset_conversation(self, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Reset the conversation.
        
        Args:
            source_id: Optional source ID to associate with the new conversation
            
        Returns:
            New conversation dictionary
        """
        # Create a new conversation with a welcome message
        new_conversation = {
            'messages': [
                {
                    'content': 'Hello! I am your assistant. How can I help you today?',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {}
        }
        
        # Add source_id to metadata if provided
        if source_id is not None:
            new_conversation['metadata']['source_id'] = source_id
        
        # Store in session
        session[self.session_key] = new_conversation
        
        return new_conversation


class MemorySessionManager(SessionInterface):
    """
    Session manager using in-memory storage.
    
    This is useful for testing or for applications that don't use Flask.
    """
    
    def __init__(self):
        """
        Initialize the memory session manager.
        """
        self.conversation = None
    
    def get_conversation(self) -> Optional[Dict[str, Any]]:
        """
        Get the current conversation from memory.
        
        Returns:
            Conversation dictionary
        """
        return self.conversation
    
    def set_conversation(self, conversation: Dict[str, Any]) -> None:
        """
        Store the conversation in memory.
        
        Args:
            conversation: Conversation dictionary
        """
        if isinstance(conversation, Conversation):
            conversation = conversation.to_dict()
            
        self.conversation = conversation
    
    def reset_conversation(self, source_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """
        Reset the conversation.
        
        Args:
            source_id: Optional source ID to associate with the new conversation
            
        Returns:
            New conversation dictionary
        """
        # Create a new conversation with a welcome message
        new_conversation = {
            'messages': [
                {
                    'content': 'Hello! I am your assistant. How can I help you today?',
                    'role': 'assistant',
                    'timestamp': None
                }
            ],
            'metadata': {}
        }
        
        # Add source_id to metadata if provided
        if source_id is not None:
            new_conversation['metadata']['source_id'] = source_id
        
        # Store in memory
        self.conversation = new_conversation
        
        return new_conversation
