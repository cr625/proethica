"""
OntServe Client for ProEthica Integration

Provides transparent interface to OntServe MCP server that matches the existing
OntologyEntityService API, enabling seamless migration from ProEthica's internal
ontology serving to OntServe.
"""

import os
import json
import asyncio
import aiohttp
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OntServeClient:
    """
    ProEthica client for OntServe MCP server.
    Provides transparent interface matching existing OntologyEntityService API.
    """
    
    # World to Domain mapping
    WORLD_DOMAIN_MAPPING = {
        1: 'engineering-ethics',      # Engineering World
        2: 'proethica-intermediate',  # Intermediate concepts  
        3: 'bfo',                     # Basic Formal Ontology
    }
    
    def __init__(self, base_url: str = None):
        """
        Initialize OntServe client.
        
        Args:
            base_url: OntServe MCP server URL (defaults to environment variable)
        """
        self.base_url = base_url or os.environ.get('ONTSERVE_URL', 'http://localhost:8083')
        self.timeout = int(os.environ.get('ONTSERVE_TIMEOUT', 30))
        self.session = None
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = timedelta(hours=1)  # 1-hour TTL
        
        logger.info(f"OntServe client initialized: {self.base_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            connector = aiohttp.TCPConnector(
                limit=20,           # Total connection pool size
                limit_per_host=10,  # Per-host connection limit
                keepalive_timeout=60
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        return self.session
    
    async def _make_mcp_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make MCP JSON-RPC 2.0 request to OntServe.
        
        Args:
            method: MCP method name
            params: Method parameters
            
        Returns:
            Response data
        """
        session = await self._get_session()
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params
        }
        
        try:
            async with session.post(f"{self.base_url}/jsonrpc", json=payload) as response:
                if response.status != 200:
                    raise aiohttp.ClientError(f"HTTP {response.status}: {await response.text()}")
                
                result = await response.json()
                
                if "error" in result:
                    raise Exception(f"MCP Error: {result['error']}")
                
                return result.get("result", {})
                
        except Exception as e:
            logger.error(f"OntServe MCP request failed ({method}): {e}")
            raise
    
    async def get_entities_by_category(self, domain_name: str, category: str, limit: int = 1000) -> List[Dict]:
        """
        Get entities by category from OntServe.
        
        Args:
            domain_name: Professional domain name
            category: Entity category (role, principle, obligation, etc.)
            limit: Maximum number of entities to return
            
        Returns:
            List of entity dictionaries
        """
        cache_key = f"{domain_name}:{category}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
        
        try:
            result = await self._make_mcp_request("call_tool", {
                "name": "get_entities_by_category",
                "arguments": {
                    "domain_name": domain_name,
                    "category": category,
                    "limit": limit
                }
            })
            
            entities = result.get("content", [])
            if isinstance(entities, list) and entities:
                # Extract actual data if wrapped
                if isinstance(entities[0], dict) and "text" in entities[0]:
                    entities = json.loads(entities[0]["text"])
            
            # Cache the result
            self.cache[cache_key] = (entities, datetime.now())
            
            logger.info(f"Retrieved {len(entities)} {category} entities from OntServe domain {domain_name}")
            return entities
            
        except Exception as e:
            logger.error(f"Failed to get entities from OntServe: {e}")
            return []
    
    async def get_entities_for_world(self, world) -> Dict[str, Any]:
        """
        Compatibility wrapper matching OntologyEntityService interface.
        Maps world.ontology_id to domain_name and aggregates all categories.
        
        Args:
            world: World model instance with ontology_id
            
        Returns:
            Dict containing entities organized by type, matching OntologyEntityService format
        """
        if not hasattr(world, 'ontology_id') or not world.ontology_id:
            logger.warning(f"World {getattr(world, 'id', '?')} has no ontology_id")
            return {"entities": {}, "is_mock": False, "source": "ontserve"}
        
        # Map world to domain
        domain_name = self.WORLD_DOMAIN_MAPPING.get(world.ontology_id)
        if not domain_name:
            logger.warning(f"No domain mapping found for world.ontology_id {world.ontology_id}")
            # Fallback: try using ontology_id as domain name
            domain_name = f"world-{world.ontology_id}"
        
        logger.info(f"Getting entities for world {world.ontology_id} -> domain {domain_name}")
        
        # Categories to retrieve (ProEthica's 9-category system)
        categories = [
            'role', 'principle', 'obligation', 'state', 
            'resource', 'action', 'event', 'capability', 'constraint'
        ]
        
        entities = {}
        total_entities = 0
        
        try:
            # Retrieve entities for each category
            for category in categories:
                category_entities = await self.get_entities_by_category(domain_name, category)
                if category_entities:
                    # Format entities to match OntologyEntityService structure
                    formatted_entities = []
                    for entity in category_entities:
                        formatted_entity = {
                            "id": entity.get("uri", entity.get("id", "")),
                            "uri": entity.get("uri", entity.get("id", "")),
                            "label": entity.get("label", ""),
                            "description": entity.get("description", ""),
                            "type": category,
                            "from_base": entity.get("from_base", True),  # Assume from base unless specified
                            "parent_class": entity.get("parent_class"),
                        }
                        
                        # Add capabilities for roles
                        if category == 'role' and "capabilities" in entity:
                            formatted_entity["capabilities"] = entity["capabilities"]
                        
                        formatted_entities.append(formatted_entity)
                    
                    entities[category] = formatted_entities
                    total_entities += len(formatted_entities)
                    logger.info(f"Found {len(formatted_entities)} {category} entities")
            
            result = {
                "entities": entities,
                "is_mock": False,
                "source": "ontserve",
                "domain_name": domain_name,
                "total_entities": total_entities,
                "retrieved_at": datetime.now().isoformat()
            }
            
            logger.info(f"Retrieved {total_entities} total entities from OntServe for world {world.ontology_id}")
            return result
            
        except Exception as e:
            logger.error(f"Error retrieving entities from OntServe for world {world.ontology_id}: {e}")
            return {
                "entities": {}, 
                "is_mock": False, 
                "source": "ontserve",
                "error": str(e)
            }
    
    def invalidate_cache(self, domain_name: str = None):
        """
        Invalidate cache for specific domain or all domains.
        
        Args:
            domain_name: Domain to invalidate, or None for all
        """
        if domain_name:
            keys_to_remove = [key for key in self.cache.keys() if key.startswith(f"{domain_name}:")]
            for key in keys_to_remove:
                del self.cache[key]
            logger.info(f"Invalidated cache for domain {domain_name}")
        else:
            self.cache.clear()
            logger.info("Invalidated all OntServe caches")
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

# Singleton instance for easy access
_ontserve_client_instance = None

def get_ontserve_client() -> OntServeClient:
    """Get singleton OntServe client instance."""
    global _ontserve_client_instance
    if _ontserve_client_instance is None:
        _ontserve_client_instance = OntServeClient()
    return _ontserve_client_instance