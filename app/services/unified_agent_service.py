"""
Unified Agent Service

Direct LLM connections to Claude, OpenAI, and Gemini with live API calls only.
No fallbacks, no mocks, no orchestration complexity.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional

from app.services.direct_llm_service import DirectLLMService
from app.services.llm_service import Conversation, Message
from app.services.application_context_service import ApplicationContextService
from app.models.world import World

logger = logging.getLogger(__name__)


class UnifiedAgentService:
    """
    Unified agent service with direct LLM connections.
    Supports Claude, OpenAI, and Gemini with live API calls only.
    """
    
    def __init__(self):
        """Initialize direct LLM connections."""
        self.app_context_service = ApplicationContextService.get_instance()
        self.direct_llm_service = DirectLLMService()
        
        # Log available services
        available = self.direct_llm_service.get_available_services()
        logger.info("Direct LLM Service initialized:")
        for service, status in available.items():
            status_icon = "✅" if status else "❌"
            logger.info(f"  {status_icon} {service.title()}: {'Available' if status else 'Not configured'}")
    
    def send_message(self, 
                    message: str,
                    conversation: Conversation = None,
                    world_id: Optional[int] = None,
                    scenario_id: Optional[int] = None,
                    service: str = "claude") -> Message:
        """
        Send message directly to the specified LLM service.
        
        Args:
            message: User message to send
            conversation: ProEthica conversation object
            world_id: World ID for context
            scenario_id: Scenario ID for context
            service: LLM service ('claude', 'openai', 'gemini')
            
        Returns:
            Generated response message
        """
        logger.info(f"Sending message to {service}")
        
        # Get application context
        context = self.app_context_service.get_full_context(
            world_id=world_id,
            scenario_id=scenario_id,
            query=message
        )
        formatted_context = self.app_context_service.format_context_for_llm(context)
        
        # Create conversation if none provided
        if conversation is None:
            conversation = Conversation()
        
        try:
            # Send message using direct LLM service
            response = self.direct_llm_service.send_message_with_context(
                message=message,
                conversation=conversation,
                application_context=formatted_context,
                world_id=world_id,
                service=service
            )
            
            logger.info(f"✅ {service.title()} response received: {len(response.content)} characters")
            return response
            
        except Exception as e:
            logger.error(f"❌ {service.title()} API call failed: {e}")
            # No fallback - let the error bubble up
            raise RuntimeError(f"{service.title()} service failed: {str(e)}")
    
    async def send_message_async(self, 
                                message: str,
                                conversation: Conversation = None,
                                world_id: Optional[int] = None,
                                scenario_id: Optional[int] = None,
                                service: str = "claude") -> Message:
        """
        Async wrapper for send_message - runs in thread to maintain compatibility.
        """
        # Run the synchronous call in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.send_message,
            message, conversation, world_id, scenario_id, service
        )
    
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
        # Use direct service to get prompt options
        if conversation is None:
            conversation = Conversation()
            
        return self.direct_llm_service.get_prompt_options(
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
        try:
            from app.models.world import World
            if world_id:
                world = World.query.get(world_id)
                if world and world.guidelines:
                    return world.guidelines
            return None
        except Exception as e:
            logger.error(f"Failed to get guidelines for world {world_id}: {e}")
            return None
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on the unified agent service.
        
        Returns:
            Health status information
        """
        available_services = self.direct_llm_service.get_available_services()
        
        health_data = {
            "unified_agent_service": "ok",
            "using_direct_llm_connections": True,
            "available_services": available_services,
            "total_available": sum(available_services.values())
        }
        
        return health_data
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the current service configuration."""
        available_services = self.direct_llm_service.get_available_services()
        
        info = {
            "service_type": "direct_llm",
            "using_direct_connections": True,
            "available_services": available_services,
            "total_available": sum(available_services.values())
        }
        
        return info
    
    def get_available_providers(self) -> List[Dict[str, Any]]:
        """Get list of available LLM providers with their status."""
        available_services = self.direct_llm_service.get_available_services()
        providers = []
        
        # Add Claude
        providers.append({
            'id': 'claude',
            'name': 'Claude (Anthropic)',
            'status': 'available' if available_services.get('claude') else 'unavailable',
            'available': available_services.get('claude', False),
            'description': 'Anthropic\'s Claude language model' + (' (API key required)' if not available_services.get('claude') else '')
        })
        
        # Add OpenAI
        providers.append({
            'id': 'openai',
            'name': 'OpenAI GPT',
            'status': 'available' if available_services.get('openai') else 'unavailable',
            'available': available_services.get('openai', False),
            'description': 'OpenAI\'s GPT language models' + (' (API key required)' if not available_services.get('openai') else '')
        })
        
        # Add Gemini
        providers.append({
            'id': 'gemini',
            'name': 'Google Gemini',
            'status': 'available' if available_services.get('gemini') else 'unavailable',
            'available': available_services.get('gemini', False),
            'description': 'Google\'s Gemini language model' + (' (API key required)' if not available_services.get('gemini') else '')
        })
        
        return providers

# Global instance for easy access
_unified_agent_service = None


def get_unified_agent_service() -> UnifiedAgentService:
    """Get the global unified agent service instance."""
    global _unified_agent_service
    if _unified_agent_service is None:
        _unified_agent_service = UnifiedAgentService()
    return _unified_agent_service
