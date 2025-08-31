"""
Unified Agent Service

Hybrid architecture:
- Claude: Uses ProEthica orchestrator with MCP ontology integration
- OpenAI & Gemini: Direct LLM connections (unchanged)
"""

import os
import logging
import asyncio
import sys
from typing import Dict, List, Any, Optional

from app.services.direct_llm_service import DirectLLMService
from app.services.llm_service import Conversation, Message
from app.services.application_context_service import ApplicationContextService
from app.services.proethica_orchestrator_service import ProEthicaOrchestratorService
from app.models.world import World

logger = logging.getLogger(__name__)


class UnifiedAgentService:
    """
    Hybrid agent service:
    - Claude: Shared orchestrator with MCP ontology integration
    - OpenAI & Gemini: Direct LLM connections
    """
    
    def __init__(self):
        """Initialize hybrid LLM system."""
        self.app_context_service = ApplicationContextService.get_instance()
        self.direct_llm_service = DirectLLMService()
        
        # Initialize ProEthica orchestrator for ontology-aware reasoning
        self.proethica_orchestrator = None
        self._init_proethica_orchestrator()
        
        # Log available services
        available = self.direct_llm_service.get_available_services()
        logger.info("Hybrid LLM Service initialized:")
        for service, status in available.items():
            status_icon = "✅" if status else "❌"
            if service == "claude" and self.proethica_orchestrator:
                logger.info(f"  {status_icon} {service.title()}: Available with ProEthica MCP ontology integration")
            else:
                logger.info(f"  {status_icon} {service.title()}: {'Available (direct)' if status else 'Not configured'}")
    
    def _init_proethica_orchestrator(self):
        """Initialize the ProEthica orchestrator for ontology-aware reasoning."""
        try:
            # Initialize ProEthica orchestrator with MCP integration
            self.proethica_orchestrator = ProEthicaOrchestratorService()
            logger.info("✅ ProEthica orchestrator initialized with MCP ontology integration")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ProEthica orchestrator: {e}")
            logger.info("🔄 Claude will fallback to direct connection")
            self.proethica_orchestrator = None
    
    def send_message(self, 
                    message: str,
                    conversation: Conversation = None,
                    world_id: Optional[int] = None,
                    scenario_id: Optional[int] = None,
                    service: str = "claude") -> Message:
        """
        Hybrid message routing:
        - Claude: Uses shared orchestrator with MCP ontology integration
        - OpenAI & Gemini: Direct LLM connections
        
        Args:
            message: User message to send
            conversation: ProEthica conversation object
            world_id: World ID for context
            scenario_id: Scenario ID for context
            service: LLM service ('claude', 'openai', 'gemini')
            
        Returns:
            Generated response message
        """
        logger.info(f"Sending message to {service} (hybrid routing)")
        
        # Create conversation if none provided
        if conversation is None:
            conversation = Conversation()
        
        if service == "claude" and self.proethica_orchestrator:
            # Use ProEthica orchestrator for Claude with MCP integration
            return self._send_to_proethica_orchestrator(message, conversation, world_id, scenario_id)
        else:
            # Use direct LLM service for Gemini/OpenAI or Claude fallback
            return self._send_to_direct_service(message, conversation, world_id, scenario_id, service)
    
    def _send_to_proethica_orchestrator(self, message: str, conversation: Conversation, 
                                   world_id: Optional[int], scenario_id: Optional[int]) -> Message:
        """Send message to ProEthica orchestrator with MCP ontology integration."""
        try:
            # Determine domain based on world or default
            domain = "engineering-ethics"  # Default domain
            if world_id:
                try:
                    world = World.query.get(world_id)
                    if world and hasattr(world, 'domain'):
                        domain = world.domain
                except Exception as e:
                    logger.warning(f"Could not get domain for world {world_id}: {e}")
            
            # Process query through ProEthica orchestrator
            import asyncio
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Process with ProEthica orchestrator (includes MCP queries)
            orchestrated_response = loop.run_until_complete(
                self.proethica_orchestrator.process_query(
                    query=message,
                    domain=domain,
                    use_cache=True
                )
            )
            
            # Add user message to conversation
            conversation.add_message(message, "user")
            
            # Extract response content
            response_content = orchestrated_response.response_text
            
            # Add ontological context if available
            if orchestrated_response.ontology_context and orchestrated_response.ontology_context.retrieved_entities:
                response_content += "\n\n---\n**📚 Ontological Concepts from ProEthica:**\n"
                
                for category, entities in orchestrated_response.ontology_context.retrieved_entities.items():
                    if entities:
                        response_content += f"\n**{category}:**\n"
                        for entity in entities[:5]:  # Limit to top 5 per category
                            label = entity.get('label', 'Unknown')
                            desc = entity.get('description', '')
                            response_content += f"• **{label}**"
                            if desc:
                                response_content += f": {desc}"
                            response_content += "\n"
            
            # Add reasoning steps if available
            if orchestrated_response.reasoning_steps:
                logger.info(f"Reasoning steps: {orchestrated_response.reasoning_steps}")
            
            # Create response message
            response_message = Message(
                content=response_content,
                role="assistant",
                provider="proethica-mcp"  # Indicate ProEthica MCP integration
            )
            conversation.add_message(response_content, "assistant")
            
            # Log statistics
            entity_count = sum(len(e) for e in orchestrated_response.ontology_context.retrieved_entities.values()) if orchestrated_response.ontology_context else 0
            logger.info(f"✅ ProEthica (MCP) response: {len(response_content)} chars, {entity_count} entities")
            logger.info(f"   Processing time: {orchestrated_response.processing_time_ms}ms")
            
            return response_message
            
        except Exception as e:
            logger.error(f"❌ ProEthica orchestrator failed: {e}")
            logger.info("🔄 Falling back to direct Claude connection")
            return self._send_to_direct_service(message, conversation, world_id, scenario_id, "claude")
    
    def _send_to_direct_service(self, message: str, conversation: Conversation, 
                              world_id: Optional[int], scenario_id: Optional[int], service: str) -> Message:
        """Send message using direct LLM service (for Gemini/OpenAI or Claude fallback)."""
        try:
            # Get application context
            context = self.app_context_service.get_full_context(
                world_id=world_id,
                scenario_id=scenario_id,
                query=message
            )
            formatted_context = self.app_context_service.format_context_for_llm(context)
            
            # Send message using direct LLM service
            response = self.direct_llm_service.send_message_with_context(
                message=message,
                conversation=conversation,
                application_context=formatted_context,
                world_id=world_id,
                service=service
            )
            
            logger.info(f"✅ {service.title()} (direct) response received: {len(response.content)} characters")
            return response
            
        except Exception as e:
            logger.error(f"❌ {service.title()} direct API call failed: {e}")
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
            "architecture": "hybrid",
            "claude_integration": "proethica_orchestrator_with_mcp" if self.proethica_orchestrator else "direct",
            "direct_services": available_services,
            "proethica_orchestrator_available": self.proethica_orchestrator is not None,
            "mcp_integration": "enabled" if self.proethica_orchestrator else "disabled",
            "total_providers": sum(available_services.values())
        }
        
        # Get orchestrator health if available
        if self.proethica_orchestrator:
            try:
                health_data["orchestrator_health"] = {
                    "status": "healthy",
                    "mcp_available": self.proethica_orchestrator.mcp_available,
                    "cache_size": len(self.proethica_orchestrator.cache)
                }
            except Exception as e:
                health_data["orchestrator_health"] = {"error": str(e)}
        
        return health_data
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get information about the current service configuration."""
        available_services = self.direct_llm_service.get_available_services()
        
        info = {
            "service_type": "hybrid",
            "architecture": {
                "claude": "proethica_orchestrator_with_mcp" if self.proethica_orchestrator else "direct_connection",
                "openai": "direct_connection",
                "gemini": "direct_connection"
            },
            "direct_services": available_services,
            "proethica_orchestrator_enabled": self.proethica_orchestrator is not None,
            "mcp_ontology_access": self.proethica_orchestrator is not None,
            "total_providers": sum(available_services.values())
        }
        
        if self.proethica_orchestrator:
            try:
                info["orchestrator_stats"] = {
                    "mcp_available": self.proethica_orchestrator.mcp_available,
                    "cache_size": len(self.proethica_orchestrator.cache),
                    "cache_ttl": self.proethica_orchestrator.cache_ttl
                }
            except Exception as e:
                info["orchestrator_error"] = str(e)
        
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
