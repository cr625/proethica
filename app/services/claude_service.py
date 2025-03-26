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
        
        # Default system prompt
        self.system_prompt = """
        You are an AI assistant helping users with ethical decision-making scenarios.
        Provide thoughtful, nuanced responses that consider multiple ethical perspectives.
        When appropriate, reference relevant ethical frameworks and principles.
        """
        
        # Default options for testing
        self._default_options = [
            {"id": 1, "text": "Tell me more about this scenario"},
            {"id": 2, "text": "What ethical principles apply here?"},
            {"id": 3, "text": "How should I approach this decision?"}
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
        
        # Check if we should use Claude or return a mock response
        if Config.USE_CLAUDE:
            try:
                # Get guidelines for the world
                guidelines = self.get_guidelines_for_world(world_id=world_id)
                
                # Format messages for Claude
                claude_messages = self._format_messages_for_claude(conversation)
                
                # Prepare system prompt with guidelines if available
                system_prompt = self.system_prompt
                if guidelines:
                    system_prompt = f"{self.system_prompt}\n\nGuidelines for reference:\n{guidelines}"
                
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
        else:
            # Return a mock response when USE_CLAUDE is False
            print("Using mock response instead of calling Claude API")
            # Get last user message to include in mock response for context
            last_message = message if message else "your request"
            content = f"This is a mock response to: {last_message}\n\nMock responses are being used because USE_CLAUDE is set to false in the environment configuration."
        
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
        if conversation is None or len(conversation.messages) == 0:
            return self._default_options
        
        # Check if we should use Claude or return mock options
        if Config.USE_CLAUDE:
            try:
                # Get guidelines for the world
                guidelines = self.get_guidelines_for_world(world_id=world_id)
                
                # Format messages for Claude
                claude_messages = self._format_messages_for_claude(conversation)
                
                # Add a specific instruction for generating options
                claude_messages.append({
                    "role": "user",
                    "content": "Generate 3-5 suggested prompt options that would be helpful for the user to select based on our conversation. Format your response as a JSON array of objects with 'id' and 'text' fields. Example: [{\"id\": 1, \"text\": \"Tell me more about this scenario\"}, {\"id\": 2, \"text\": \"What ethical principles apply here?\"}]"
                })
                
                # Prepare system prompt with guidelines if available
                system_prompt = self.system_prompt
                if guidelines:
                    system_prompt = f"{self.system_prompt}\n\nGuidelines for reference:\n{guidelines}"
                
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
                    
                # If all parsing fails, return default options
                return self._default_options
                
            except Exception as e:
                print(f"Error generating prompt options from Claude: {str(e)}")
                return self._default_options
        else:
            # Return mock prompt options when USE_CLAUDE is False
            print("Using mock prompt options instead of calling Claude API")
            # Return standard mock options with context that they are mock responses
            return [
                {"id": 1, "text": "Mock option 1: Tell me more about this scenario"},
                {"id": 2, "text": "Mock option 2: What ethical principles apply here?"},
                {"id": 3, "text": "Mock option 3: How should I approach this decision?"},
                {"id": 4, "text": "Mock option 4: What considerations should I keep in mind?"}
            ]
