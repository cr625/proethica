"""
Agent Conversation model for storing persistent agent-assisted case creation conversations.

This model captures complete conversation threads including ontology selections,
agent guidance, and metadata needed for case generation.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.models import db


class AgentConversation(db.Model):
    """
    Model for storing agent-assisted conversations with full context.
    
    This stores the complete interaction history between users and the 
    case creation agent, including ontology selections and metadata
    needed for generating NSPE-format cases.
    """
    
    __tablename__ = 'agent_conversations'
    
    id = Column(Integer, primary_key=True)
    
    # User and session information
    user_id = Column(String(255), nullable=True)  # Can be anonymous
    session_id = Column(String(255), nullable=False, index=True)
    
    # World and context
    world_id = Column(Integer, ForeignKey('worlds.id'), nullable=True)
    world = relationship("World", backref="agent_conversations")
    
    # Conversation metadata
    title = Column(String(500), nullable=True)  # Generated or user-provided title
    status = Column(String(50), default='active')  # active, completed, archived
    conversation_type = Column(String(50), default='case_creation')  # case_creation, general, etc.
    
    # Core conversation data
    messages = Column(JSON, nullable=False, default=list)  # Complete message thread
    ontology_selections = Column(JSON, nullable=False, default=dict)  # Selected concepts by category
    
    # Case generation metadata
    generated_case_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    generated_case = relationship("Document", backref="source_conversation", foreign_keys=[generated_case_id])
    case_generation_status = Column(String(50), nullable=True)  # pending, generated, failed
    
    # Extended metadata
    conv_metadata = Column(JSON, nullable=False, default=dict)  # Additional context and settings
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    def __init__(self, session_id, user_id=None, world_id=None, title=None, **kwargs):
        """Initialize a new agent conversation."""
        self.session_id = session_id
        self.user_id = user_id
        self.world_id = world_id
        self.title = title
        self.messages = []
        self.ontology_selections = {}
        self.conv_metadata = kwargs.get('conv_metadata', {})
        self.status = 'active'
        self.conversation_type = kwargs.get('conversation_type', 'case_creation')
    
    def add_message(self, content, role='user', metadata=None):
        """
        Add a message to the conversation thread.
        
        Args:
            content: Message content
            role: 'user', 'assistant', or 'system'
            metadata: Additional message metadata
        """
        message = {
            'content': content,
            'role': role,
            'timestamp': datetime.utcnow().isoformat(),
            'metadata': metadata or {}
        }
        
        if not self.messages:
            self.messages = []
        self.messages.append(message)
        
        # Update conversation timestamp
        self.updated_at = datetime.utcnow()
    
    def update_ontology_selections(self, category, concepts):
        """
        Update ontology concept selections for a category.
        
        Args:
            category: Ontology category name (e.g., 'Principle')
            concepts: List of selected concept names
        """
        if not self.ontology_selections:
            self.ontology_selections = {}
        
        self.ontology_selections[category] = concepts
        self.updated_at = datetime.utcnow()
    
    def get_selected_concepts_summary(self):
        """Get a summary of selected ontology concepts."""
        if not self.ontology_selections:
            return "No concepts selected"
        
        total_concepts = sum(len(concepts) for concepts in self.ontology_selections.values())
        categories = len([cat for cat, concepts in self.ontology_selections.items() if concepts])
        
        return f"{categories} categories, {total_concepts} concepts selected"
    
    def get_message_count(self):
        """Get total message count."""
        return len(self.messages) if self.messages else 0
    
    def get_last_message_time(self):
        """Get timestamp of last message."""
        if not self.messages:
            return self.created_at
        
        try:
            last_message = self.messages[-1]
            return datetime.fromisoformat(last_message['timestamp'])
        except (KeyError, ValueError):
            return self.updated_at
    
    def mark_completed(self):
        """Mark conversation as completed."""
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def can_generate_case(self):
        """Check if conversation has enough content to generate a case."""
        if not self.messages:
            return False
        
        # Need at least some back-and-forth conversation
        user_messages = [m for m in self.messages if m.get('role') == 'user']
        assistant_messages = [m for m in self.messages if m.get('role') == 'assistant']
        
        # Require at least 2 user messages and 1 assistant response
        return len(user_messages) >= 2 and len(assistant_messages) >= 1
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'world_id': self.world_id,
            'title': self.title,
            'status': self.status,
            'conversation_type': self.conversation_type,
            'messages': self.messages,
            'ontology_selections': self.ontology_selections,
            'generated_case_id': self.generated_case_id,
            'case_generation_status': self.case_generation_status,
            'conv_metadata': self.conv_metadata,
            'message_count': self.get_message_count(),
            'concepts_summary': self.get_selected_concepts_summary(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }
    
    def __repr__(self):
        return f'<AgentConversation {self.id}: {self.title or self.session_id[:8]}... ({self.status})>'