from typing import Dict, List, Any, Optional, Union
from langchain.prompts import PromptTemplate
from langchain.llms.base import BaseLLM
from langchain_community.llms.fake import FakeListLLM
from langchain.schema.runnable import RunnableSequence
import os
import json
import time
from datetime import datetime
from app.services.mcp_client import MCPClient

class Message:
    """Class representing a message in a conversation."""
    
    def __init__(self, content: str, role: str = "user", timestamp: Optional[float] = None):
        """
        Initialize a message.
        
        Args:
            content: Message content
            role: Message role (user, assistant, system)
            timestamp: Message timestamp (optional)
        """
        self.content = content
        self.role = role
        self.timestamp = timestamp or time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "content": self.content,
            "role": self.role,
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary."""
        return cls(
            content=data["content"],
            role=data.get("role", "user"),
            timestamp=data.get("timestamp")
        )

class Conversation:
    """Class representing a conversation with an LLM."""
    
    def __init__(self, messages: Optional[List[Message]] = None, metadata: Optional[Dict[str, Any]] = None):
        """
        Initialize a conversation.
        
        Args:
            messages: List of messages (optional)
            metadata: Conversation metadata (optional)
        """
        self.messages = messages or []
        self.metadata = metadata or {}
    
    def add_message(self, message: Union[Message, str], role: str = "user") -> Message:
        """
        Add a message to the conversation.
        
        Args:
            message: Message to add (can be a Message object or a string)
            role: Message role if message is a string (user, assistant, system)
            
        Returns:
            The added message
        """
        if isinstance(message, str):
            message = Message(content=message, role=role)
        
        self.messages.append(message)
        return message
    
    def get_messages(self, roles: Optional[List[str]] = None) -> List[Message]:
        """
        Get messages with specific roles.
        
        Args:
            roles: List of roles to filter by (optional)
            
        Returns:
            List of messages
        """
        if roles is None:
            return self.messages
        
        return [m for m in self.messages if m.role in roles]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            "messages": [m.to_dict() for m in self.messages],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        """Create conversation from dictionary."""
        return cls(
            messages=[Message.from_dict(m) for m in data.get("messages", [])],
            metadata=data.get("metadata", {})
        )
    
    def get_context_string(self) -> str:
        """
        Get conversation context as a string.
        
        Returns:
            String representation of the conversation
        """
        context = ""
        for message in self.messages:
            prefix = f"{message.role.capitalize()}: "
            context += f"{prefix}{message.content}\n\n"
        
        return context.strip()

class LLMService:
    """Service for interacting with language models."""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo", llm: Optional[BaseLLM] = None):
        """
        Initialize the LLM service.
        
        Args:
            model_name: Name of the language model to use
            llm: Language model instance (optional)
        """
        self.model_name = model_name
        self.llm = llm or self._create_mock_llm()
        
        # Get MCP client for accessing guidelines
        self.mcp_client = MCPClient.get_instance()
        
        # Setup prompt templates
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
        
        # Set default responses for testing
        self._default_options = [
            {"id": 1, "text": "Tell me more about this scenario"},
            {"id": 2, "text": "What ethical principles apply here?"},
            {"id": 3, "text": "How should I approach this decision?"}
        ]
    
    def _create_mock_llm(self) -> BaseLLM:
        """Create a mock LLM for development and testing."""
        responses = [
            # Chat responses
            "I understand you're looking at an engineering ethics scenario. This appears to involve questions about professional responsibility, design integrity, and public safety. Engineers must balance technical constraints, economic pressures, and ethical obligations to ensure public welfare. In this case, the key question appears to be how to properly acknowledge and address design errors while maintaining professional integrity. Would you like me to explain how the NSPE Code of Ethics applies to this situation?",
            "Based on the engineering ethics scenario you're viewing, there are several important considerations at play. The primary ethical frameworks relevant here are utilitarianism (maximizing overall benefit), deontology (following professional duties and codes), and virtue ethics (acting with integrity and honesty). In engineering specifically, professionals must follow the NSPE Code of Ethics which emphasizes public safety, honesty, and professional competence. The key question appears to be how to properly handle acknowledgment of design errors while maintaining professional standards. Would you like me to analyze this specific scenario in more detail?",
            "Looking at the engineering ethics scenario you're viewing, I can see this involves potential conflicts between professional responsibilities and business interests. Engineers have ethical obligations to prioritize public safety, be honest about limitations, and maintain professional integrity. In this case, the key question appears to be whether the design meets safety standards despite cost pressures. Would you like me to discuss how professional engineering codes of ethics would apply here?",
            
            # Options responses (as JSON strings)
            '[{"id": 1, "text": "Explain the ethical principles in this scenario"}, {"id": 2, "text": "What would be the most ethical decision here?"}, {"id": 3, "text": "Show me similar cases"}, {"id": 4, "text": "What guidelines apply to this situation?"}]',
            '[{"id": 1, "text": "Analyze this from a utilitarian perspective"}, {"id": 2, "text": "What rights might be violated here?"}, {"id": 3, "text": "How would virtue ethics approach this?"}, {"id": 4, "text": "What are the professional obligations in this case?"}]',
            '[{"id": 1, "text": "What are the key facts I should consider?"}, {"id": 2, "text": "How do I balance competing interests here?"}, {"id": 3, "text": "What precedents exist for this situation?"}, {"id": 4, "text": "What would be the consequences of each option?"}]'
        ]
        return FakeListLLM(responses=responses)
    
    def get_guidelines_for_world(self, world_id: Optional[int] = None, world_name: Optional[str] = None) -> str:
        """
        Get guidelines for a specific world.
        
        Args:
            world_id: ID of the world (optional)
            world_name: Name of the world (optional)
            
        Returns:
            String containing the guidelines
        """
        if world_id is None and world_name is None:
            return "No specific guidelines available."
        
        try:
            # If world_id is provided, get the world from the database
            if world_id is not None:
                from app.models.world import World
                world = World.query.get(world_id)
                if world:
                    world_name = world.name.lower().replace(' ', '-')
                    
                    # If the world has an ontology source, use it
                    if world.ontology_source:
                        # Try to get entities from MCP server
                        entities = self.mcp_client.get_world_entities(world.ontology_source)
                        
                        # If no entities returned, use mock entities
                        if not entities or 'entities' not in entities or not entities['entities']:
                            entities = self.mcp_client.get_mock_entities(world.ontology_source)
                        
                        if entities and 'entities' in entities:
                            return self._format_entities_as_guidelines(entities['entities'])
            
            # If world_name is provided or derived from world_id, get guidelines from MCP
            if world_name:
                # Try to get guidelines from MCP server
                guidelines_data = self.mcp_client.get_guidelines(world_name)
                
                # If no guidelines returned, use mock guidelines
                if not guidelines_data or 'guidelines' not in guidelines_data or not guidelines_data['guidelines']:
                    guidelines_data = self.mcp_client.get_mock_guidelines(world_name)
                
                if guidelines_data and 'guidelines' in guidelines_data:
                    return self._format_guidelines(guidelines_data['guidelines'])
        
        except Exception as e:
            print(f"Error retrieving guidelines: {str(e)}")
            
            # Fallback to mock data in case of error
            try:
                if world_id is not None:
                    from app.models.world import World
                    world = World.query.get(world_id)
                    if world:
                        world_name = world.name.lower().replace(' ', '-')
                        
                        # If the world has an ontology source, use mock entities
                        if world.ontology_source:
                            entities = self.mcp_client.get_mock_entities(world.ontology_source)
                            if entities and 'entities' in entities:
                                return self._format_entities_as_guidelines(entities['entities'])
                
                # Use mock guidelines
                if world_name:
                    guidelines_data = self.mcp_client.get_mock_guidelines(world_name)
                    if guidelines_data and 'guidelines' in guidelines_data:
                        return self._format_guidelines(guidelines_data['guidelines'])
            
            except Exception as inner_e:
                return f"Error retrieving guidelines: {str(e)}, Fallback error: {str(inner_e)}"
        
        return "No specific guidelines available."
    
    def _format_entities_as_guidelines(self, entities: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Format entities from ontology as guidelines text.
        
        Args:
            entities: Dictionary containing entities from ontology
            
        Returns:
            Formatted guidelines text
        """
        text = ""
        
        # Add roles
        if 'roles' in entities and entities['roles']:
            text += "## Roles\n\n"
            for role in entities['roles']:
                text += f"- {role.get('label', 'Unnamed role')}: {role.get('description', '')}\n"
            text += "\n"
        
        # Add conditions
        if 'conditions' in entities and entities['conditions']:
            text += "## Conditions\n\n"
            for condition in entities['conditions']:
                text += f"- {condition.get('label', 'Unnamed condition')}: {condition.get('description', '')}\n"
            text += "\n"
        
        # Add resources
        if 'resources' in entities and entities['resources']:
            text += "## Resources\n\n"
            for resource in entities['resources']:
                text += f"- {resource.get('label', 'Unnamed resource')}: {resource.get('description', '')}\n"
            text += "\n"
        
        # Add actions
        if 'actions' in entities and entities['actions']:
            text += "## Actions\n\n"
            for action in entities['actions']:
                text += f"- {action.get('label', 'Unnamed action')}: {action.get('description', '')}\n"
            text += "\n"
        
        return text
    
    def _format_guidelines(self, guidelines: List[Dict[str, Any]]) -> str:
        """
        Format guidelines data as text for LLM input.
        
        Args:
            guidelines: List of guidelines
            
        Returns:
            Formatted guidelines text
        """
        text = ""
        
        # Format guidelines
        for guideline in guidelines:
            text += f"## {guideline.get('name', 'Unnamed guideline')}\n\n"
            text += f"{guideline.get('description', '')}\n\n"
            
            # Add categories if present
            if 'categories' in guideline and guideline['categories']:
                text += "### Categories\n\n"
                for category in guideline['categories']:
                    text += f"- {category.get('name', 'Unnamed')}: {category.get('description', '')}\n"
                text += "\n"
            
            # Add factors if present
            if 'factors' in guideline and guideline['factors']:
                text += "### Factors\n\n"
                for factor in guideline['factors']:
                    text += f"- {factor}\n"
                text += "\n"
            
            # Add principles if present
            if 'principles' in guideline and guideline['principles']:
                text += "### Principles\n\n"
                for principle in guideline['principles']:
                    text += f"- {principle}\n"
                text += "\n"
            
            # Add steps if present
            if 'steps' in guideline and guideline['steps']:
                text += "### Steps\n\n"
                for step in guideline['steps']:
                    text += f"- {step}\n"
                text += "\n"
            
            # Add considerations if present
            if 'considerations' in guideline and guideline['considerations']:
                text += "### Considerations\n\n"
                for consideration in guideline['considerations']:
                    text += f"- {consideration}\n"
                text += "\n"
        
        return text
    
    def send_message(self, message: str, conversation: Optional[Conversation] = None, 
                    world_id: Optional[int] = None) -> Message:
        """
        Send a message to the language model.
        
        Args:
            message: Message to send
            conversation: Conversation object (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            Response message
        """
        # For backward compatibility, delegate to send_message_with_context
        return self.send_message_with_context(message, conversation, None, world_id)
    
    def send_message_with_context(self, message: str, conversation: Optional[Conversation] = None, 
                                application_context: Optional[str] = None, world_id: Optional[int] = None) -> Message:
        """
        Send a message to the language model with enhanced application context.
        
        Args:
            message: Message to send
            conversation: Conversation object (optional)
            application_context: Enhanced application context (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            Response message
        """
        # Create conversation if not provided
        if conversation is None:
            conversation = Conversation()
        
        # Add user message to conversation
        conversation.add_message(message, role="user")
        
        try:
            # Get guidelines for the world
            guidelines = self.get_guidelines_for_world(world_id=world_id)
            
            # Get conversation context
            context = conversation.get_context_string()
            
            if application_context:
                # Create enhanced prompt with application context
                enhanced_prompt = f"""
                You are an AI assistant helping users with ethical decision-making scenarios.
                
                APPLICATION INFORMATION:
                {application_context}
                
                Conversation history:
                {context}
                
                Guidelines for reference:
                {guidelines}
                
                User message: {message}
                
                Respond to the user's message, taking into account the application context, conversation history, and the guidelines provided.
                """
                
                # Process with LLM directly
                response = self.llm.invoke(enhanced_prompt)
            else:
                # Use the standard chat chain when no application context is provided
                response = self.chat_chain.invoke({
                    "context": context,
                    "message": message,
                    "guidelines": guidelines
                })
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            # Use a default response in case of error
            response = "I'm sorry, I encountered an error processing your request. Please try again or ask a different question."
        
        # Add assistant response to conversation
        return conversation.add_message(response, role="assistant")
    
    def get_prompt_options(self, conversation: Optional[Conversation] = None,
                          world_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get suggested prompt options based on the conversation and world context.
        
        Args:
            conversation: Conversation object (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            List of prompt options
        """
        # For now, return default options to avoid LangChain issues
        # When we switch to using the LLM for options, we'll use this code:
        # try:
        #     # Get guidelines for the world
        #     guidelines = self.get_guidelines_for_world(world_id=world_id)
        #     
        #     # Get conversation context
        #     context = conversation.get_context_string() if conversation else ""
        #     
        #     # Run the chain using the new RunnableSequence API
        #     json_response = self.options_chain.invoke({
        #         "context": context,
        #         "guidelines": guidelines
        #     })
        #     
        #     # Parse JSON response
        #     options = json.loads(json_response)
        #     return options
        # except Exception as e:
        #     print(f"Error generating options: {str(e)}")
        
        # In the meantime, return default options
        return self._default_options
