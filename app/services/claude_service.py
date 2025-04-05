from typing import Dict, List, Any, Optional, Union
from anthropic import Anthropic
from app.services.llm_service import Message, Conversation
from app.services.mcp_client import MCPClient
from app.config import Config
import os
import time
import json
import re

class ClaudeService:
    """Service for interacting with Anthropic's Claude models."""
    
    def __init__(self, api_key=None, model="claude-3-opus-20240229"):
        """
        Initialize the Claude service.
        
        Args:
            api_key: Anthropic API key (optional, will use env var if not provided)
            model: Claude model to use (default: claude-3-opus-20240229)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("Anthropic API key is required")
            
        self.model = model
        self.client = Anthropic(api_key=self.api_key)
        
        # Get MCP client for accessing guidelines (same as LLMService)
        self.mcp_client = MCPClient.get_instance()
        
        # Default system prompt (used when no world is selected)
        self.general_system_prompt = """
        You are an AI assistant helping users with ethical decision-making scenarios.
        Provide thoughtful, nuanced responses that consider multiple ethical perspectives.
        When appropriate, reference relevant ethical frameworks and principles.
        """
        
        # General testing options (used when no world is selected)
        self._general_options = [
            {"id": 1, "text": "Tell me more about ethical decision-making"},
            {"id": 2, "text": "What are some key ethical frameworks?"},
            {"id": 3, "text": "How can I apply ethics to everyday decisions?"}
        ]
        
        # Default options for when a world is selected but no conversation history exists
        self._default_world_options = [
            {"id": 1, "text": "Tell me more about this scenario"},
            {"id": 2, "text": "What ethical principles apply in this world?"},
            {"id": 3, "text": "How should I approach decisions in this context?"}
        ]
    
    def get_guidelines_for_world(self, world_id=None, world_name=None):
        """
        Get guidelines for a specific world.
        This reuses the same method from LLMService to maintain consistency.
        
        Args:
            world_id: ID of the world (optional)
            world_name: Name of the world (optional)
            
        Returns:
            String containing the guidelines
        """
        # Import here to avoid circular imports
        from app.services.llm_service import LLMService
        llm_service = LLMService()
        return llm_service.get_guidelines_for_world(world_id, world_name)
    
    def _format_messages_for_claude(self, conversation, message=None):
        """
        Format conversation history for Claude API.
        
        Args:
            conversation: Conversation object
            message: New message to add (optional)
            
        Returns:
            Dictionary with system and messages for Claude API
        """
        # Initialize with empty messages array (no system message in the array)
        claude_messages = []
        
        # Add conversation history
        for msg in conversation.messages:
            # Map 'user' and 'assistant' roles directly
            # Any other roles will be added as user messages with a prefix
            if msg.role in ['user', 'assistant']:
                claude_messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            else:
                claude_messages.append({
                    "role": "user",
                    "content": f"[{msg.role}]: {msg.content}"
                })
        
        # Add new message if provided
        if message and not any(m.get('content') == message and m.get('role') == 'user' 
                              for m in claude_messages):
            claude_messages.append({
                "role": "user",
                "content": message
            })
            
        return claude_messages
    
    def get_world_entities(self, world_id):
        """
        Get entities for a specific world from the MCP server.
        
        Args:
            world_id: ID of the world
            
        Returns:
            Dictionary of entities or empty dict if error occurs
        """
        if not world_id:
            return {}
            
        try:
            # Import here to avoid circular imports
            from app.models.world import World
            
            # Get the world by ID
            world = World.query.get(world_id)
            if not world or not world.ontology_source:
                return {}
                
            # Get entities from MCP client
            print(f"Getting entities for world {world_id} with ontology source: {world.ontology_source}")
            # The correct way to get entities from MCP client
            entities = self.mcp_client.make_request(f"/api/ontology/{world.ontology_source}/entities")
            return entities
        except Exception as e:
            print(f"Error getting world entities: {str(e)}")
            return {}
    
    def build_system_prompt(self, world_id=None):
        """
        Build a system prompt based on the world context.
        
        Args:
            world_id: ID of the world for context (optional)
            
        Returns:
            String containing the system prompt
        """
        if not world_id:
            return self.general_system_prompt
            
        # Get guidelines and entities for the world
        guidelines = self.get_guidelines_for_world(world_id=world_id)
        entities = self.get_world_entities(world_id)
        
        # Start with the general system prompt
        system_prompt = self.general_system_prompt
        
        # Add world-specific constraints
        system_prompt += "\n\nIMPORTANT: You are currently operating within a specific ethical world context."
        system_prompt += "\nYou must constrain your responses to be relevant to this context."
        
        # Add guidelines if available
        if guidelines:
            system_prompt += f"\n\nGuidelines for this world:\n{guidelines}"
        
        # Add key entities if available
        if entities and 'entities' in entities:
            # Get the top entities (limit to avoid token issues)
            top_entities = list(entities['entities'].keys())[:15]
            if top_entities:
                system_prompt += "\n\nKey concepts in this world:"
                for entity in top_entities:
                    # Clean up URI format if needed
                    entity_name = entity.split('/')[-1].replace('_', ' ')
                    system_prompt += f"\n- {entity_name}"
        
        return system_prompt
        
    def send_message(self, message, conversation=None, world_id=None):
        """
        Send a message to Claude.
        
        Args:
            message: Message to send
            conversation: Conversation object (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            Response message
        """
        # Create conversation if not provided
        if conversation is None:
            conversation = Conversation()
        
        # Add user message to conversation
        conversation.add_message(message, role="user")
        
        # Always attempt to use the Claude API since this service was explicitly selected
        try:
            # Format messages for Claude
            claude_messages = self._format_messages_for_claude(conversation)
            
            # Build appropriate system prompt based on world context
            system_prompt = self.build_system_prompt(world_id)
            
            # Call Claude API with system parameter
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=claude_messages,
                max_tokens=1024
            )
            
            # Extract response content
            content = response.content[0].text
            
        except Exception as e:
            print(f"Error generating response from Claude: {str(e)}")
            # Use a default response in case of error
            content = "I'm sorry, I encountered an error processing your request. Please try again or ask a different question."
        
        # Add assistant response to conversation
        return conversation.add_message(content, role="assistant")
    
    def get_prompt_options(self, conversation=None, world_id=None):
        """
        Get suggested prompt options based on the conversation and world context.
        
        Args:
            conversation: Conversation object (optional)
            world_id: ID of the world for context (optional)
            
        Returns:
            List of prompt options
        """
        # If no conversation or empty conversation, return appropriate default options
        if conversation is None or len(conversation.messages) == 0:
            if world_id:
                return self._default_world_options  # World-specific default options
            else:
                return self._general_options  # General default options for no world
        
        # Always attempt to use the Claude API since this service was explicitly selected
        try:
            # Format messages for Claude
            claude_messages = self._format_messages_for_claude(conversation)
            
            # Add world context to the prompt option generation
            instruction = "Generate 3-5 suggested prompt options that would be helpful for the user to select based on our conversation."
            
            if world_id:
                # Get world info to enhance the instruction
                from app.models.world import World
                world = World.query.get(world_id)
                if world and world.name:
                    instruction = f"Generate 3-5 suggested prompt options related to the '{world.name}' world that would be helpful for the user based on our conversation."
            
            # Add the instruction for format
            instruction += " Format your response as a JSON array of objects with 'id' and 'text' fields. Example: [{\"id\": 1, \"text\": \"Tell me more about this scenario\"}, {\"id\": 2, \"text\": \"What ethical principles apply here?\"}]"
            
            # Add the instruction to the messages
            claude_messages.append({
                "role": "user",
                "content": instruction
            })
            
            # Build appropriate system prompt based on world context
            system_prompt = self.build_system_prompt(world_id)
            
            # Call Claude API with system parameter
            response = self.client.messages.create(
                model=self.model,
                system=system_prompt,
                messages=claude_messages,
                max_tokens=512
            )
            
            # Extract response content and parse JSON
            content = response.content[0].text
            
            # Try to extract JSON from the response
            # First, look for JSON array pattern
            json_match = re.search(r'\[\s*\{.*\}\s*\]', content, re.DOTALL)
            if json_match:
                options_json = json_match.group(0)
                options = json.loads(options_json)
                return options
                
            # If that fails, try to parse the entire response as JSON
            try:
                options = json.loads(content)
                if isinstance(options, list) and all('id' in opt and 'text' in opt for opt in options):
                    return options
            except:
                pass
                
            # If all parsing fails, return appropriate default options
            if world_id:
                return self._default_world_options
            else:
                return self._general_options
            
        except Exception as e:
            print(f"Error generating prompt options from Claude: {str(e)}")
            # Return appropriate default options based on world context
            if world_id:
                return self._default_world_options
            else:
                return self._general_options
