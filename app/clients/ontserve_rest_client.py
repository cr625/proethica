"""
OntServe REST Client for ProEthica Integration

Simple REST API client for retrieving ontology data from OntServe.
This is the appropriate architecture for bulk data retrieval during
concept extraction index building (vs MCP which is for LLM tool access).
"""

import os
import aiohttp
import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class OntServeRestClient:
    """
    REST client for OntServe ontology data retrieval.
    Focused on efficient bulk data access for ProEthica's concept extraction needs.
    """
    
    # World to Domain mapping
    WORLD_DOMAIN_MAPPING = {
        1: 'engineering-ethics',      # Engineering World
        2: 'proethica-intermediate',  # Intermediate concepts  
        3: 'bfo',                     # Basic Formal Ontology
    }
    
    def __init__(self, base_url: str = None):
        """
        Initialize OntServe REST client.
        
        Args:
            base_url: OntServe web server URL (defaults to environment variable)
        """
        # Use web interface port (5003) for REST API, not MCP port (8083)
        self.base_url = base_url or os.environ.get('ONTSERVE_WEB_URL', 'http://localhost:5003')
        self.timeout = int(os.environ.get('ONTSERVE_TIMEOUT', 30))
        self.session = None
        self.cache = {}  # Simple in-memory cache
        self.cache_ttl = timedelta(hours=1)  # 1-hour TTL
        
        logger.info(f"OntServe REST client initialized: {self.base_url}")
    
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
    
    async def get_domain_entities(self, domain_name: str) -> List[Dict]:
        """
        Get all entities for a domain via REST API.
        
        Args:
            domain_name: Professional domain name
            
        Returns:
            List of entity dictionaries
        """
        cache_key = f"domain_{domain_name}"
        
        # Check cache first
        if cache_key in self.cache:
            cached_data, cached_time = self.cache[cache_key]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.debug(f"Cache hit for domain {domain_name}")
                return cached_data
        
        session = await self._get_session()
        
        try:
            # Try the editor API endpoint first (most likely to exist)
            url = f"{self.base_url}/editor/api/ontologies/{domain_name}/entities"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Extract entities from response format
                    entities = []
                    if isinstance(data, dict) and 'entities' in data:
                        # Standard format: {"entities": {"role": [...], "principle": [...]}}
                        for category, entity_list in data['entities'].items():
                            for entity in entity_list:
                                entity['category'] = category  # Ensure category is set
                                entities.append(entity)
                    elif isinstance(data, list):
                        # Direct list format
                        entities = data
                    
                    # Cache the result
                    self.cache[cache_key] = (entities, datetime.now())
                    
                    logger.info(f"Retrieved {len(entities)} entities from OntServe domain {domain_name}")
                    return entities
                
                elif response.status == 404:
                    # Try alternative endpoint
                    alt_url = f"{self.base_url}/api/domains/{domain_name}/entities"
                    async with session.get(alt_url) as alt_response:
                        if alt_response.status == 200:
                            data = await alt_response.json()
                            entities = data if isinstance(data, list) else []
                            self.cache[cache_key] = (entities, datetime.now())
                            logger.info(f"Retrieved {len(entities)} entities from OntServe domain {domain_name} (alt endpoint)")
                            return entities
                
                # If we get here, no endpoint worked
                logger.warning(f"Could not retrieve entities for domain {domain_name}: HTTP {response.status}")
                return []
                
        except Exception as e:
            logger.error(f"Failed to get entities from OntServe domain {domain_name}: {e}")
            return []
    
    async def get_entities_for_world(self, world) -> Dict[str, Any]:
        """
        Compatibility wrapper matching OntologyEntityService interface.
        Maps world.ontology_id to domain_name and organizes entities by category.
        
        Args:
            world: World model instance with ontology_id
            
        Returns:
            Dict containing entities organized by type, matching OntologyEntityService format
        """
        if not hasattr(world, 'ontology_id') or not world.ontology_id:
            logger.warning(f"World {getattr(world, 'id', '?')} has no ontology_id")
            return {"entities": {}, "is_mock": False, "source": "ontserve_rest"}
        
        # Map world to domain
        domain_name = self.WORLD_DOMAIN_MAPPING.get(world.ontology_id)
        if not domain_name:
            logger.warning(f"No domain mapping found for world.ontology_id {world.ontology_id}")
            # Fallback: try using ontology_id as domain name
            domain_name = f"world-{world.ontology_id}"
        
        logger.info(f"Getting entities for world {world.ontology_id} -> domain {domain_name}")
        
        try:
            # Get all entities for the domain
            all_entities = await self.get_domain_entities(domain_name)
            
            # Organize by category
            entities_by_category = {}
            total_entities = 0
            
            for entity in all_entities:
                category = entity.get('category', entity.get('type', 'unknown'))
                
                if category not in entities_by_category:
                    entities_by_category[category] = []
                
                # Format entity to match OntologyEntityService structure
                formatted_entity = {
                    "id": entity.get("uri", entity.get("id", "")),
                    "uri": entity.get("uri", entity.get("id", "")),
                    "label": entity.get("label", ""),
                    "description": entity.get("description", ""),
                    "type": category,
                    "from_base": entity.get("from_base", True),
                    "parent_class": entity.get("parent_class"),
                }
                
                # Add capabilities for roles
                if category == 'role' and "capabilities" in entity:
                    formatted_entity["capabilities"] = entity["capabilities"]
                
                entities_by_category[category].append(formatted_entity)
                total_entities += 1
            
            # Log summary
            for category, entity_list in entities_by_category.items():
                logger.info(f"Found {len(entity_list)} {category} entities")
            
            result = {
                "entities": entities_by_category,
                "is_mock": False,
                "source": "ontserve_rest",
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
                "source": "ontserve_rest",
                "error": str(e)
            }
    
    def invalidate_cache(self, domain_name: str = None):
        """
        Invalidate cache for specific domain or all domains.
        
        Args:
            domain_name: Domain to invalidate, or None for all
        """
        if domain_name:
            cache_key = f"domain_{domain_name}"
            if cache_key in self.cache:
                del self.cache[cache_key]
                logger.info(f"Invalidated cache for domain {domain_name}")
        else:
            self.cache.clear()
            logger.info("Invalidated all OntServe REST caches")
    
    async def create_draft_ontology(self, ontology_name: str, concepts: List[Dict], 
                                   base_imports: List[str] = None, 
                                   change_summary: str = None,
                                   created_by: str = "ProEthica") -> Dict:
        """
        Create a new draft ontology from extracted concepts.
        
        Args:
            ontology_name: Name of the draft ontology
            concepts: List of concept dictionaries with uri, label, type, etc.
            base_imports: List of base ontologies to import (e.g., ["prov-o-base"])
            change_summary: Description of what was extracted
            created_by: Who created this draft
            
        Returns:
            Dict with success status and version details
        """
        session = await self._get_session()
        
        try:
            url = f"{self.base_url}/editor/api/ontologies/{ontology_name}/draft"
            
            payload = {
                "concepts": concepts,
                "base_imports": base_imports or ["prov-o-base"],
                "change_summary": change_summary or f"Extracted concepts from ProEthica",
                "created_by": created_by
            }
            
            async with session.post(url, json=payload) as response:
                if response.status in [200, 201]:
                    data = await response.json()
                    logger.info(f"Created draft ontology {ontology_name} with {len(concepts)} concepts")
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to create draft ontology {ontology_name}: {response.status} - {error_text}")
                    return {"success": False, "error": f"HTTP {response.status}: {error_text}"}
                    
        except Exception as e:
            logger.error(f"Error creating draft ontology {ontology_name}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_draft_ontology(self, ontology_name: str) -> Optional[Dict]:
        """
        Get the current draft version of an ontology.
        
        Args:
            ontology_name: Name of the ontology
            
        Returns:
            Dict with draft details or None if no draft exists
        """
        session = await self._get_session()
        
        try:
            url = f"{self.base_url}/editor/api/ontologies/{ontology_name}/draft"
            
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.debug(f"Retrieved draft ontology {ontology_name}")
                    return data
                elif response.status == 404:
                    logger.debug(f"No draft found for ontology {ontology_name}")
                    return None
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to get draft ontology {ontology_name}: {response.status} - {error_text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Error getting draft ontology {ontology_name}: {e}")
            return None
    
    async def delete_draft_ontology(self, ontology_name: str) -> bool:
        """
        Delete the current draft version of an ontology.
        
        Args:
            ontology_name: Name of the ontology
            
        Returns:
            True if successfully deleted, False otherwise
        """
        session = await self._get_session()
        
        try:
            url = f"{self.base_url}/editor/api/ontologies/{ontology_name}/draft"
            
            async with session.delete(url) as response:
                if response.status in [200, 204]:
                    logger.info(f"Deleted draft ontology {ontology_name}")
                    return True
                elif response.status == 404:
                    logger.debug(f"No draft found to delete for ontology {ontology_name}")
                    return True  # Already gone, consider this success
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to delete draft ontology {ontology_name}: {response.status} - {error_text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error deleting draft ontology {ontology_name}: {e}")
            return False

    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None

# Singleton instance for easy access
_ontserve_rest_client_instance = None

def get_ontserve_rest_client() -> OntServeRestClient:
    """Get singleton OntServe REST client instance."""
    global _ontserve_rest_client_instance
    if _ontserve_rest_client_instance is None:
        _ontserve_rest_client_instance = OntServeRestClient()
    return _ontserve_rest_client_instance