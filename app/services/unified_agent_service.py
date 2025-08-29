"""
Unified Agent Service

A service that integrates the new unified LLM orchestration system with ProEthica's 
agent functionality, providing seamless LLM interactions with ontological context.
"""

import os
import sys
import asyncio
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add the shared directory to the path so we can import our unified orchestration
project_root = Path(__file__).parent.parent.parent.parent
shared_path = project_root / "shared"
sys.path.insert(0, str(shared_path))

try:
    from llm_orchestration import (
        get_llm_orchestrator, 
        LLMOrchestrator, 
        OrchestratorConfig,
        Conversation as UnifiedConversation,
        Message as UnifiedMessage
    )
    UNIFIED_ORCHESTRATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Unified LLM orchestration not available: {e}")
    UNIFIED_ORCHESTRATION_AVAILABLE = False

# Fallback imports for existing ProEthica services
from app.services.llm_service import LLMService, Conversation, Message
from app.services.claude_service import ClaudeService
from app.services.application_context_service import ApplicationContextService
from app.models.world import World

logger = logging.getLogger(__name__)


class UnifiedAgentService:
    """
    Unified agent service that provides a seamless interface to the new LLM orchestration
    system while maintaining compatibility with existing ProEthica patterns.
    """
    
    def __init__(self):
        """Initialize the unified agent service."""
        self.app_context_service = ApplicationContextService.get_instance()
        
        # Initialize fallback attributes first
        self.has_claude = False
        self.llm_service = None
        self.claude_service = None
        
        # Initialize the unified orchestrator if available
        if UNIFIED_ORCHESTRATION_AVAILABLE:
            try:
                # Configure the orchestrator for ProEthica
                config = OrchestratorConfig(
                    provider_priority=["claude", "openai"],  # Prefer Claude
                    enable_fallback=True,                    # Enable fallback
                    enable_mock_fallback=True,               # Enable mock for development
                    enable_caching=True,                     # Enable response caching
                    mcp_server_url=os.environ.get("ONTSERVE_MCP_URL", "http://localhost:8082")
                )
                
                self.orchestrator = LLMOrchestrator(config)
                self.use_unified = True
                logger.info("Unified agent service initialized with LLM orchestrator")
                
            except Exception as e:
                logger.error(f"Failed to initialize unified orchestrator: {e}")
                self.use_unified = False
                self._init_fallback_services()
        else:
            self.use_unified = False
            self._init_fallback_services()
    
    def _init_fallback_services(self):
        """Initialize fallback services if unified orchestrator is not available."""
        logger.info("Initializing fallback LLM services")
        
        # Initialize existing services as fallback
        self.llm_service = LLMService()
        
        # Initialize Claude service if API key is available
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            try:
                self.claude_service = ClaudeService(api_key=api_key)
                self.has_claude = True
            except Exception as e:
                logger.warning(f"Failed to initialize Claude service: {e}")
                self.has_claude = False
        else:
            self.has_claude = False
            logger.warning("No Claude API key found")
        
        self.orchestrator = None
    
    def _convert_to_unified_conversation(self, proethica_conversation: Conversation) -> UnifiedConversation:
        """Convert ProEthica conversation to unified conversation format."""
        if not UNIFIED_ORCHESTRATION_AVAILABLE:
            return None
            
        # Create unified messages
        unified_messages = []
        for msg in proethica_conversation.messages:
            unified_msg = UnifiedMessage(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.metadata if hasattr(msg, 'metadata') else None
            )
            unified_messages.append(unified_msg)
        
        # Create unified conversation
        unified_conversation = UnifiedConversation(
            messages=unified_messages,
            context=proethica_conversation.metadata if hasattr(proethica_conversation, 'metadata') else None
        )
        
        return unified_conversation
    
    def _convert_from_unified_message(self, unified_message: Any) -> Message:
        """Convert unified message back to ProEthica message format."""
        return Message(
            role=unified_message.role,
            content=unified_message.content,
            timestamp=unified_message.timestamp
        )
    
    async def send_message_async(self, 
                                message: str,
                                conversation: Conversation = None,
                                world_id: Optional[int] = None,
                                scenario_id: Optional[int] = None,
                                service: str = "claude") -> Message:
        """
        Send a message using the unified orchestration system (async version).
        
        Args:
            message: User message to send
            conversation: ProEthica conversation object
            world_id: World ID for context
            scenario_id: Scenario ID for context
            service: Service preference (maintained for compatibility)
            
        Returns:
            Generated response message
        """
        if self.use_unified and self.orchestrator:
            try:
                # Get application context
                context = self.app_context_service.get_full_context(
                    world_id=world_id,
                    scenario_id=scenario_id,
                    query=message
                )
                formatted_context = self.app_context_service.format_context_for_llm(context)
                
                # Convert conversation format
                unified_conversation = None
                if conversation:
                    unified_conversation = self._convert_to_unified_conversation(conversation)
                
                # Send message using unified orchestrator
                response = await self.orchestrator.send_message_with_conversation(
                    message=message,
                    conversation=unified_conversation,
                    world_id=world_id,
                    application_context=formatted_context,
                    preferred_provider=service if service != "langchain" else "openai"
                )
                
                # Convert back to ProEthica format
                return Message(
                    role="assistant",
                    content=response.content,
                    timestamp=None
                )
                
            except Exception as e:
                logger.error(f"Unified orchestration failed: {e}")
                # Fall back to legacy services
                return self._send_message_fallback(message, conversation, world_id, scenario_id, service)
        else:
            # Use fallback services
            return self._send_message_fallback(message, conversation, world_id, scenario_id, service)
    
    def send_message(self, 
                    message: str,
                    conversation: Conversation = None,
                    world_id: Optional[int] = None,
                    scenario_id: Optional[int] = None,
                    service: str = "claude") -> Message:
        """
        Synchronous wrapper for send_message_async.
        
        This maintains compatibility with existing ProEthica code that expects
        synchronous message sending.
        """
        # Run the async function in a new event loop or existing one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If there's already a running loop, we need to run in a thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.send_message_async(message, conversation, world_id, scenario_id, service)
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.send_message_async(message, conversation, world_id, scenario_id, service)
                )
        except RuntimeError:
            # No event loop, create a new one
            return asyncio.run(
                self.send_message_async(message, conversation, world_id, scenario_id, service)
            )
    
    def _send_message_fallback(self, 
                              message: str,
                              conversation: Conversation,
                              world_id: Optional[int],
                              scenario_id: Optional[int],
                              service: str) -> Message:
        """Fallback message sending using legacy services."""
        # Get application context
        context = self.app_context_service.get_full_context(
            world_id=world_id,
            scenario_id=scenario_id,
            query=message
        )
        formatted_context = self.app_context_service.format_context_for_llm(context)
        
        # Send message using legacy services
        if service == "claude" and self.has_claude:
            response = self.claude_service.send_message_with_context(
                message=message,
                conversation=conversation,
                application_context=formatted_context,
                world_id=world_id
            )
        else:
            response = self.llm_service.send_message_with_context(
                message=message,
                conversation=conversation,
                application_context=formatted_context,
                world_id=world_id
            )
        
        return response
    
    def get_prompt_options(self, 
                          conversation: Conversation = None,
                          world_id: Optional[int] = None,
                          service: str = "claude") -> List[Dict[str, Any]]:
        """
        Get prompt options for the conversation.
        
        Args:
            conversation: Current conversation
            world_id: World ID for context
            service: Service preference
            
        Returns:
            List of prompt option dictionaries
        """
        if self.use_unified and self.orchestrator:
            try:
                # Use unified orchestrator for prompt options
                options = self.orchestrator.get_prompt_options(
                    conversation=self._convert_to_unified_conversation(conversation) if conversation else None,
                    world_id=world_id,
                    preferred_provider=service if service != "langchain" else "openai"
                )
                return options
                
            except Exception as e:
                logger.error(f"Unified orchestration prompt options failed: {e}")
                # Fall back to legacy services
                return self._get_prompt_options_fallback(conversation, world_id, service)
        else:
            # Use fallback services
            return self._get_prompt_options_fallback(conversation, world_id, service)
    
    def _get_prompt_options_fallback(self, 
                                    conversation: Conversation,
                                    world_id: Optional[int],
                                    service: str) -> List[Dict[str, Any]]:
        """Fallback prompt options using legacy services."""
        if service == "claude" and self.has_claude:
            return self.claude_service.get_prompt_options(
                conversation=conversation,
                world_id=world_id
            )
        else:
            return self.llm_service.get_prompt_options(
                conversation=conversation,
                world_id=world_id
            )
    
    def get_guidelines_for_world(self, world_id: Optional[int] = None) -> Optional[str]:
        """
        Get guidelines for a specific world.
        
        Args:
            world_id: World ID to get guidelines for
            
        Returns:
            Guidelines text or None
        """
        if self.use_unified and self.orchestrator:
            try:
                # Use unified orchestrator's MCP integration for guidelines
                if hasattr(self.orchestrator, 'mcp_client') and self.orchestrator.mcp_client:
                    # Run async method synchronously
                    return asyncio.run(
                        self.orchestrator.mcp_client.get_guidelines(world_id=world_id)
                    )
            except Exception as e:
                logger.error(f"Unified guidelines retrieval failed: {e}")
        
        # Fallback to legacy services
        if hasattr(self, 'has_claude') and self.has_claude:
            return self.claude_service.get_guidelines_for_world(world_id=world_id)
        elif hasattr(self, 'llm_service'):
            return self.llm_service.get_guidelines_for_world(world_id=world_id)
        else:
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the unified agent service.
        
        Returns:
            Health status information
        """
        health_data = {
            "unified_agent_service": "ok",
            "using_unified_orchestration": self.use_unified,
            "unified_orchestration_available": UNIFIED_ORCHESTRATION_AVAILABLE
        }
        
        if self.use_unified and self.orchestrator:
            try:
                orchestrator_health = await self.orchestrator.health_check()
                health_data["orchestrator"] = orchestrator_health
            except Exception as e:
                health_data["orchestrator_error"] = str(e)
        
        if not self.use_unified:
            health_data["fallback_services"] = {
                "has_claude": self.has_claude,
                "has_llm_service": hasattr(self, 'llm_service')
            }
        
        return health_data
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the current service configuration."""
        info = {
            "service_type": "unified" if self.use_unified else "fallback",
            "unified_available": UNIFIED_ORCHESTRATION_AVAILABLE,
            "using_orchestrator": self.use_unified
        }
        
        if self.use_unified and self.orchestrator:
            stats = self.orchestrator.get_statistics()
            info["orchestrator_stats"] = stats
        
        return info


# Global instance for easy access
_unified_agent_service = None


def get_unified_agent_service() -> UnifiedAgentService:
    """Get the global unified agent service instance."""
    global _unified_agent_service
    if _unified_agent_service is None:
        _unified_agent_service = UnifiedAgentService()
    return _unified_agent_service
