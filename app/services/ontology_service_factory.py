"""
Ontology Service Factory for ProEthica

Factory pattern for ontology service selection, enabling seamless switching
between ProEthica's internal OntologyEntityService and OntServe backend.
"""

import os
import asyncio
import logging
from typing import Union, Dict, Any

logger = logging.getLogger(__name__)

class OntologyServiceWrapper:
    """
    Wrapper that provides a unified interface for both OntologyEntityService
    and OntServeClient, handling the async/sync interface differences.
    """
    
    def __init__(self, use_ontserve: bool = False):
        """
        Initialize the service wrapper.
        
        Args:
            use_ontserve: If True, use OntServe client; otherwise use OntologyEntityService
        """
        self.use_ontserve = use_ontserve
        self._ontology_entity_service = None
        self._ontserve_client = None
        
        logger.info(f"OntologyServiceWrapper initialized: use_ontserve={use_ontserve}")
    
    def _get_ontology_entity_service(self):
        """Get or create OntologyEntityService instance."""
        if self._ontology_entity_service is None:
            from app.services.ontology_entity_service import OntologyEntityService
            self._ontology_entity_service = OntologyEntityService.get_instance()
        return self._ontology_entity_service
    
    def _get_ontserve_client(self):
        """Get or create OntServe REST client instance."""
        if self._ontserve_client is None:
            from app.clients.ontserve_rest_client import get_ontserve_rest_client
            self._ontserve_client = get_ontserve_rest_client()
        return self._ontserve_client
    
    def get_entities_for_world(self, world) -> Dict[str, Any]:
        """
        Get entities for a world, using appropriate backend.
        
        Args:
            world: World model instance
            
        Returns:
            Dict containing entities organized by type
        """
        if self.use_ontserve:
            return self._get_entities_for_world_ontserve(world)
        else:
            return self._get_entities_for_world_legacy(world)
    
    def _get_entities_for_world_legacy(self, world) -> Dict[str, Any]:
        """Get entities using legacy OntologyEntityService."""
        try:
            service = self._get_ontology_entity_service()
            result = service.get_entities_for_world(world)
            
            # Add source metadata
            if isinstance(result, dict):
                result["source"] = "proethica"
            
            logger.debug(f"Retrieved entities using OntologyEntityService for world {getattr(world, 'id', '?')}")
            return result
            
        except Exception as e:
            logger.error(f"Error getting entities from OntologyEntityService: {e}")
            return {"entities": {}, "is_mock": False, "source": "proethica", "error": str(e)}
    
    def _get_entities_for_world_ontserve(self, world) -> Dict[str, Any]:
        """Get entities using OntServe client with fallback."""
        try:
            # Try OntServe first
            client = self._get_ontserve_client()
            
            # Run async method in sync context
            loop = None
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, but need to run sync
                    # Create a new thread to run the async operation
                    import concurrent.futures
                    import threading
                    
                    def run_async():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(client.get_entities_for_world(world))
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_async)
                        result = future.result(timeout=30)  # 30 second timeout
                else:
                    # Loop exists but not running
                    result = loop.run_until_complete(client.get_entities_for_world(world))
            except RuntimeError:
                # No event loop, create one
                result = asyncio.run(client.get_entities_for_world(world))
            
            logger.info(f"Successfully retrieved entities from OntServe for world {getattr(world, 'id', '?')}")
            return result
            
        except Exception as e:
            logger.warning(f"OntServe request failed, falling back to legacy service: {e}")
            # Fallback to legacy service
            return self._get_entities_for_world_legacy(world)
    
    def get_roles_across_world(self, world):
        """
        Get roles across world, using appropriate backend.
        
        Args:
            world: World model instance
            
        Returns:
            List of role dictionaries
        """
        if self.use_ontserve:
            # For OntServe, get roles from the standard entities call
            entities_result = self._get_entities_for_world_ontserve(world)
            roles = entities_result.get("entities", {}).get("role", [])
            logger.info(f"Retrieved {len(roles)} roles from OntServe for world {getattr(world, 'id', '?')}")
            return roles
        else:
            # Use legacy service
            service = self._get_ontology_entity_service()
            return service.get_roles_across_world(world)
    
    def invalidate_cache(self, ontology_id: int = None):
        """
        Invalidate cache for specific ontology or all ontologies.
        
        Args:
            ontology_id: ID of ontology to invalidate, or None for all
        """
        if self.use_ontserve:
            client = self._get_ontserve_client()
            if ontology_id:
                # Map ontology_id to domain name
                from config.ontserve_config import get_domain_for_world
                domain_name = get_domain_for_world(ontology_id)
                if domain_name:
                    client.invalidate_cache(domain_name)
                else:
                    logger.warning(f"No domain mapping for ontology_id {ontology_id}")
            else:
                client.invalidate_cache()
        else:
            service = self._get_ontology_entity_service()
            service.invalidate_cache(ontology_id)

class OntologyServiceFactory:
    """
    Factory for creating ontology service instances.
    Enables seamless switching between ProEthica and OntServe backends.
    """
    
    _instance = None
    
    @classmethod
    def get_service(cls) -> OntologyServiceWrapper:
        """
        Get ontology service instance based on configuration.
        
        Returns:
            OntologyServiceWrapper configured for current environment
        """
        # Check environment configuration
        use_ontserve = os.environ.get('USE_ONTSERVE', 'false').lower() in ('true', '1', 'yes')
        
        # For now, return a new instance each time to avoid caching issues
        # In production, might want to implement singleton pattern
        return OntologyServiceWrapper(use_ontserve=use_ontserve)
    
    @classmethod
    def get_legacy_service(cls):
        """Get legacy OntologyEntityService directly."""
        from app.services.ontology_entity_service import OntologyEntityService
        return OntologyEntityService.get_instance()
    
    @classmethod
    def get_ontserve_service(cls) -> OntologyServiceWrapper:
        """Get OntServe-backed service directly."""
        return OntologyServiceWrapper(use_ontserve=True)
    
    @classmethod
    def is_ontserve_enabled(cls) -> bool:
        """Check if OntServe is currently enabled."""
        return os.environ.get('USE_ONTSERVE', 'false').lower() in ('true', '1', 'yes')

# Convenience function for quick access
def get_ontology_service() -> OntologyServiceWrapper:
    """Get ontology service instance."""
    return OntologyServiceFactory.get_service()