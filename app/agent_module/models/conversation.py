"""
Conversation model classes for agent module.
"""

import time
from typing import Dict, List, Any, Optional


class Message:
    """
    Class representing a message in a conversation.
    
    This is based on the Message class in app.services.llm_service.
    """
    
    def __init__(self, content: str, role: str = "user", timestamp: Optional[float] = None):
        """
        Initialize a new message.
        
        Args:
            content: Message content
            role: Message role (user or assistant)
            timestamp: Message timestamp (defaults to current time)
        """
        self.content = content
        self.role = role
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert message to dictionary.
        
        Returns:
            Dictionary representation of the message
        """
        return {
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """
        Create message from dictionary.
        
        Args:
            data: Dictionary representation of the message
            
        Returns:
            Message instance
        """
        return cls(
            content=data["content"],
            role=data.get("role", "user"),
            timestamp=data.get("timestamp")
        )


class Conversation:
    """
    Class representing a conversation with an LLM.
    
    This is based on the Conversation class in app.services.llm_service.
    """
    
    def __init__(self, messages: Optional[List[Message]] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a new conversation.
        
        Args:
            messages: List of messages in the conversation
            metadata: Metadata dictionary
        """
        self.messages = messages or []
        self.metadata = metadata or {}
    
    def add_message(self, message: Message) -> None:
        """
        Add a message to the conversation.
        
        Args:
            message: Message to add
        """
        self.messages.append(message)
    
    def add_user_message(self, content: str) -> Message:
        """
        Add a user message to the conversation.
        
        Args:
            content: Message content
            
        Returns:
            Created message
        """
        message = Message(content=content, role="user")
        self.add_message(message)
        return message
    
    def add_assistant_message(self, content: str) -> Message:
        """
        Add an assistant message to the conversation.
        
        Args:
            content: Message content
            
        Returns:
            Created message
        """
        message = Message(content=content, role="assistant")
        self.add_message(message)
        return message
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert conversation to dictionary.
        
        Returns:
            Dictionary representation of the conversation
        """
        return {
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        """
        Create conversation from dictionary.
        
        Args:
            data: Dictionary representation of the conversation
            
        Returns:
            Conversation instance
        """
        if not data:
            return cls()
        
        messages = [Message.from_dict(m) for m in data.get("messages", [])]
        metadata = data.get("metadata", {})
        
        return cls(messages=messages, metadata=metadata)
    
    def get_history_as_text(self, include_last_n: Optional[int] = None) -> str:
        """
        Get conversation history as formatted text.
        
        Args:
            include_last_n: Only include the last N messages
            
        Returns:
            Formatted conversation history
        """
        messages = self.messages
        if include_last_n is not None:
            messages = messages[-include_last_n:]
        
        history = []
        for message in messages:
            prefix = "User: " if message.role == "user" else "Assistant: "
            history.append(f"{prefix}{message.content}")
        
        return "\n\n".join(history)
    
    def get_latest_message(self, role: Optional[str] = None) -> Optional[Message]:
        """
        Get the latest message with the specified role.
        
        Args:
            role: Message role filter (optional)
            
        Returns:
            Latest message or None if no messages match
        """
        for message in reversed(self.messages):
            if role is None or message.role == role:
                return message
        return None
