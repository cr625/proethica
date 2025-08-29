"""
Direct LLM Service - Live connections to Claude, OpenAI, and Gemini

No fallbacks, no mocks - direct API connections only.
"""

import os
import logging
import asyncio
from typing import Optional, Dict, Any
from app.services.llm_service import Message, Conversation

logger = logging.getLogger(__name__)


class DirectLLMService:
    """
    Direct LLM service with live connections to multiple providers.
    No fallbacks, no mocks - real API calls only.
    """
    
    def __init__(self):
        """Initialize direct connections to available LLM providers."""
        self.claude_client = None
        self.openai_client = None 
        self.gemini_client = None
        
        # Initialize Claude
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key and not anthropic_key.startswith("your-"):
            try:
                import anthropic
                self.claude_client = anthropic.Anthropic(api_key=anthropic_key)
                logger.info("✅ Claude client initialized successfully")
            except ImportError:
                logger.error("❌ Anthropic library not installed")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Claude client: {e}")
        else:
            logger.warning("⚠️ Claude API key not configured")
            
        # Initialize OpenAI
        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key and not openai_key.startswith("your-"):
            try:
                import openai
                self.openai_client = openai.OpenAI(api_key=openai_key)
                logger.info("✅ OpenAI client initialized successfully")
            except ImportError:
                logger.error("❌ OpenAI library not installed")
            except Exception as e:
                logger.error(f"❌ Failed to initialize OpenAI client: {e}")
        else:
            logger.warning("⚠️ OpenAI API key not configured")
            
        # Initialize Gemini
        google_key = os.environ.get("GOOGLE_API_KEY")
        if google_key and not google_key.startswith("your-"):
            try:
                import google.generativeai as genai
                genai.configure(api_key=google_key)
                self.gemini_client = genai.GenerativeModel('gemini-pro')
                logger.info("✅ Gemini client initialized successfully")
            except ImportError:
                logger.error("❌ Google GenerativeAI library not installed")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Gemini client: {e}")
        else:
            logger.warning("⚠️ Gemini API key not configured")
    
    def send_message_with_context(self, 
                                 message: str,
                                 conversation: Conversation,
                                 application_context: str,
                                 world_id: Optional[int] = None,
                                 service: str = "claude") -> Message:
        """
        Send message directly to the specified LLM provider.
        
        Args:
            message: User message
            conversation: Conversation history
            application_context: Application context
            world_id: World ID
            service: LLM service ('claude', 'openai', 'gemini')
            
        Returns:
            Message response from the LLM
        """
        if service == "claude":
            return self._send_to_claude(message, conversation, application_context)
        elif service == "openai":
            return self._send_to_openai(message, conversation, application_context)
        elif service == "gemini":
            return self._send_to_gemini(message, conversation, application_context)
        else:
            raise ValueError(f"Unsupported service: {service}")
    
    def _send_to_claude(self, message: str, conversation: Conversation, context: str) -> Message:
        """Send message directly to Claude API."""
        if not self.claude_client:
            raise RuntimeError("Claude client not initialized - check API key configuration")
        
        try:
            # Build message history for Claude
            messages = []
            for msg in conversation.messages[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Add current message
            messages.append({
                "role": "user", 
                "content": f"Context: {context}\n\nUser: {message}"
            })
            
            # Call Claude API
            response = self.claude_client.messages.create(
                model=os.environ.get("CLAUDE_DEFAULT_MODEL", "claude-3-5-sonnet-20241022"),
                max_tokens=4096,
                messages=messages
            )
            
            # Add user message to conversation
            conversation.add_message(message, "user")
            
            # Create and add response message
            response_content = response.content[0].text if response.content else ""
            response_message = Message(
                content=response_content,
                role="assistant",
                provider="claude"
            )
            conversation.add_message(response_content, "assistant")
            
            logger.info(f"✅ Claude response: {len(response_content)} characters")
            return response_message
            
        except Exception as e:
            logger.error(f"❌ Claude API error: {e}")
            raise RuntimeError(f"Claude API failed: {str(e)}")
    
    def _send_to_openai(self, message: str, conversation: Conversation, context: str) -> Message:
        """Send message directly to OpenAI API."""
        if not self.openai_client:
            raise RuntimeError("OpenAI client not initialized - check API key configuration")
        
        try:
            # Build message history for OpenAI
            messages = [
                {"role": "system", "content": f"Context: {context}"}
            ]
            for msg in conversation.messages[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
            
            # Add current message
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=os.environ.get("OPENAI_DEFAULT_MODEL", "gpt-4o-mini"),
                messages=messages,
                max_tokens=4096
            )
            
            # Add user message to conversation
            conversation.add_message(message, "user")
            
            # Create and add response message
            response_content = response.choices[0].message.content
            response_message = Message(
                content=response_content,
                role="assistant", 
                provider="openai"
            )
            conversation.add_message(response_content, "assistant")
            
            logger.info(f"✅ OpenAI response: {len(response_content)} characters")
            return response_message
            
        except Exception as e:
            logger.error(f"❌ OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API failed: {str(e)}")
    
    def _send_to_gemini(self, message: str, conversation: Conversation, context: str) -> Message:
        """Send message directly to Gemini API."""
        if not self.gemini_client:
            raise RuntimeError("Gemini client not initialized - check API key configuration")
        
        try:
            # Build message for Gemini
            full_message = f"Context: {context}\n\nUser: {message}"
            
            # Call Gemini API
            response = self.gemini_client.generate_content(full_message)
            
            # Add user message to conversation
            conversation.add_message(message, "user")
            
            # Create and add response message
            response_content = response.text
            response_message = Message(
                content=response_content,
                role="assistant",
                provider="gemini"
            )
            conversation.add_message(response_content, "assistant")
            
            logger.info(f"✅ Gemini response: {len(response_content)} characters")
            return response_message
            
        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}")
            raise RuntimeError(f"Gemini API failed: {str(e)}")
    
    def get_available_services(self) -> Dict[str, bool]:
        """Get status of available services."""
        return {
            "claude": self.claude_client is not None,
            "openai": self.openai_client is not None, 
            "gemini": self.gemini_client is not None
        }
    
    def get_prompt_options(self, conversation: Conversation, world_id: Optional[int] = None) -> list:
        """Get prompt options (placeholder for compatibility)."""
        return [
            "What ethical considerations should I evaluate?",
            "Help me analyze this scenario from different perspectives.",
            "What are the potential consequences of each option?",
            "How do professional standards apply to this situation?"
        ]