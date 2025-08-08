"""MCP Ontology Client for real-time ontology integration.

This client provides an interface to the MCP server for ontology queries,
entity mapping, and semantic enrichment of scenario generation.

Key Features:
- Real-time ontology entity queries
- ProEthica 9-category mapping
- Semantic concept matching
- Role-based participant labeling
- Graceful fallback to local ontology data
"""

import os
import json
import logging
import asyncio
import aiohttp
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)

class ProEthicaCategory(Enum):
    """9 core ProEthica ontology categories."""
    ROLE = "Role"
    PRINCIPLE = "Principle" 
    OBLIGATION = "Obligation"
    STATE = "State"
    RESOURCE = "Resource"
    ACTION = "Action"
    EVENT = "Event"
    CAPABILITY = "Capability"
    CONSTRAINT = "Constraint"

@dataclass
class OntologyEntity:
    """Ontology entity with metadata."""
    uri: str
    label: str
    category: str
    description: Optional[str] = None
    confidence: float = 1.0
    source: str = "mcp_server"

@dataclass
class ConceptMapping:
    """Mapping of text concept to ontology entity."""
    text_concept: str
    ontology_entity: OntologyEntity
    similarity_score: float
    mapping_method: str

class MCPOntologyClient:
    """Client for MCP ontology server integration."""
    
    def __init__(self, server_url: Optional[str] = None, timeout: int = 10):
        """Initialize MCP client.
        
        Args:
            server_url: MCP server URL (default from env or localhost:5001)
            timeout: Request timeout in seconds
        """
        self.server_url = server_url or os.environ.get('MCP_SERVER_URL', 'http://localhost:5001')
        self.timeout = timeout
        self.fallback_enabled = False  # No fallbacks - fail explicitly when MCP is unavailable
        self._session = None
        self._entity_cache = {}  # Cache for frequently requested entities
        
        logger.info(f"MCP Ontology Client initialized, server_url={self.server_url}, fallback_enabled={self.fallback_enabled}")

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def get_entities_by_category(self, category: ProEthicaCategory, domain: str = "engineering-ethics") -> List[OntologyEntity]:
        """Get ontology entities for a specific ProEthica category.
        
        Args:
            category: ProEthica category enum
            domain: Ontology domain to query
            
        Returns:
            List of ontology entities in the category
        """
        cache_key = f"{category.value}_{domain}"
        if cache_key in self._entity_cache:
            logger.debug(f"Returning cached entities for {category.value}")
            return self._entity_cache[cache_key]
            
        try:
            entities = await self._query_mcp_entities(category.value, domain)
            
            if not entities and self.fallback_enabled:
                logger.info(f"MCP query failed, using fallback for {category.value}")
                entities = self._get_fallback_entities(category)
            
            # Cache successful results
            self._entity_cache[cache_key] = entities
            return entities
            
        except Exception as e:
            logger.error(f"Error getting entities for category {category.value}: {e}")
            if self.fallback_enabled:
                return self._get_fallback_entities(category)
            return []

    async def map_text_to_ontology(self, text_concept: str, preferred_categories: Optional[List[ProEthicaCategory]] = None) -> Optional[ConceptMapping]:
        """Map text concept to best matching ontology entity.
        
        Args:
            text_concept: Text to map to ontology
            preferred_categories: Preferred categories to search first
            
        Returns:
            Best concept mapping or None if no good match
        """
        if not text_concept.strip():
            return None
            
        try:
            # Try MCP server mapping first
            mapping = await self._query_mcp_concept_mapping(text_concept, preferred_categories)
            
            if not mapping and self.fallback_enabled:
                logger.debug(f"MCP mapping failed, using fallback for '{text_concept}'")
                mapping = self._get_fallback_mapping(text_concept, preferred_categories)
                
            return mapping
            
        except Exception as e:
            logger.error(f"Error mapping concept '{text_concept}': {e}")
            if self.fallback_enabled:
                return self._get_fallback_mapping(text_concept, preferred_categories)
            return None

    async def get_role_entities(self, domain: str = "engineering-ethics") -> List[OntologyEntity]:
        """Get all Role entities from ontology.
        
        Args:
            domain: Ontology domain
            
        Returns:
            List of Role entities
        """
        return await self.get_entities_by_category(ProEthicaCategory.ROLE, domain)

    async def map_participant_to_role(self, participant_name: str, context: Optional[str] = None) -> Optional[OntologyEntity]:
        """Map participant name to ontological role.
        
        Args:
            participant_name: Name/description of participant
            context: Additional context for mapping
            
        Returns:
            Best matching Role entity or None
        """
        mapping = await self.map_text_to_ontology(
            participant_name, 
            preferred_categories=[ProEthicaCategory.ROLE]
        )
        
        return mapping.ontology_entity if mapping else None

    async def enrich_decision_with_ontology(self, decision_text: str, context: Optional[str] = None) -> Dict[str, Any]:
        """Enrich decision with relevant ontology entities.
        
        Args:
            decision_text: Decision question or description
            context: Additional context
            
        Returns:
            Dictionary with mapped ontology categories
        """
        enrichment = {category.value.lower(): [] for category in ProEthicaCategory}
        enrichment["mapping_metadata"] = []
        
        try:
            # Map decision text to multiple categories
            for category in ProEthicaCategory:
                mapping = await self.map_text_to_ontology(decision_text, [category])
                if mapping and mapping.similarity_score > 0.6:  # Confidence threshold
                    enrichment[category.value.lower()].append(asdict(mapping.ontology_entity))
                    enrichment["mapping_metadata"].append({
                        "category": category.value,
                        "confidence": mapping.similarity_score,
                        "method": mapping.mapping_method
                    })
            
            return enrichment
            
        except Exception as e:
            logger.error(f"Error enriching decision with ontology: {e}")
            return enrichment

    async def _query_mcp_entities(self, category: str, domain: str) -> List[OntologyEntity]:
        """Query MCP server for entities in category."""
        if not self._session:
            raise RuntimeError("MCP client session not initialized - use async context manager")
            
        try:
            # MCP server entity query endpoint
            url = f"{self.server_url}/ontology/entities/{domain}"
            params = {"category": category}
            
            async with self._session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    entities = []
                    
                    # Parse MCP response format
                    entity_data = data.get("entities", {}).get(category.lower(), [])
                    for entity_info in entity_data:
                        entities.append(OntologyEntity(
                            uri=entity_info.get("uri", ""),
                            label=entity_info.get("label", ""),
                            category=category,
                            description=entity_info.get("description", ""),
                            confidence=entity_info.get("confidence", 1.0),
                            source="mcp_server"
                        ))
                    
                    logger.debug(f"Retrieved {len(entities)} entities for {category} from MCP server")
                    return entities
                else:
                    logger.warning(f"MCP server returned status {response.status} for category {category}")
                    return []
                    
        except aiohttp.ClientError as e:
            logger.error(f"MCP server connection error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error querying MCP server: {e}")
            raise

    async def _query_mcp_concept_mapping(self, text_concept: str, preferred_categories: Optional[List[ProEthicaCategory]] = None) -> Optional[ConceptMapping]:
        """Query MCP server for concept mapping."""
        if not self._session:
            raise RuntimeError("MCP client session not initialized - use async context manager")
            
        try:
            url = f"{self.server_url}/ontology/map_concept"
            payload = {
                "concept": text_concept,
                "preferred_categories": [cat.value for cat in preferred_categories] if preferred_categories else None
            }
            
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data.get("success") and data.get("mapping"):
                        mapping_data = data["mapping"]
                        entity_data = mapping_data["entity"]
                        
                        return ConceptMapping(
                            text_concept=text_concept,
                            ontology_entity=OntologyEntity(
                                uri=entity_data["uri"],
                                label=entity_data["label"], 
                                category=entity_data["category"],
                                description=entity_data.get("description", ""),
                                confidence=entity_data.get("confidence", 1.0),
                                source="mcp_server"
                            ),
                            similarity_score=mapping_data["similarity_score"],
                            mapping_method="mcp_semantic"
                        )
                    return None
                else:
                    logger.debug(f"MCP server mapping returned status {response.status} for '{text_concept}'")
                    return None
                    
        except Exception as e:
            logger.debug(f"MCP concept mapping error for '{text_concept}': {e}")
            raise

    def _get_fallback_entities(self, category: ProEthicaCategory) -> List[OntologyEntity]:
        """Get fallback entities when MCP server is unavailable."""
        # Static fallback data for core entities
        fallback_data = {
            ProEthicaCategory.ROLE: [
                OntologyEntity("http://proethica.org/engineering#ProfessionalEngineer", "Professional Engineer", "Role", "Licensed engineering professional", source="fallback"),
                OntologyEntity("http://proethica.org/engineering#EngineeringManager", "Engineering Manager", "Role", "Engineering project manager", source="fallback"),
                OntologyEntity("http://proethica.org/engineering#Client", "Client", "Role", "Client or customer", source="fallback"),
                OntologyEntity("http://proethica.org/engineering#Supervisor", "Supervisor", "Role", "Direct supervisor", source="fallback")
            ],
            ProEthicaCategory.PRINCIPLE: [
                OntologyEntity("http://proethica.org/ethics#PublicSafety", "Public Safety", "Principle", "Protection of public safety and welfare", source="fallback"),
                OntologyEntity("http://proethica.org/ethics#Honesty", "Honesty", "Principle", "Truthfulness and integrity", source="fallback"),
                OntologyEntity("http://proethica.org/ethics#Competence", "Competence", "Principle", "Professional competence", source="fallback")
            ],
            ProEthicaCategory.OBLIGATION: [
                OntologyEntity("http://proethica.org/ethics#Disclosure", "Disclosure", "Obligation", "Duty to disclose conflicts", source="fallback"),
                OntologyEntity("http://proethica.org/ethics#Confidentiality", "Confidentiality", "Obligation", "Maintain client confidentiality", source="fallback"),
                OntologyEntity("http://proethica.org/ethics#CompetentPractice", "Competent Practice", "Obligation", "Practice within competence", source="fallback")
            ],
            ProEthicaCategory.ACTION: [
                OntologyEntity("http://proethica.org/actions#Report", "Report", "Action", "Report issues or concerns", source="fallback"),
                OntologyEntity("http://proethica.org/actions#Disclose", "Disclose", "Action", "Disclose conflicts or information", source="fallback"),
                OntologyEntity("http://proethica.org/actions#Consult", "Consult", "Action", "Seek consultation", source="fallback")
            ]
        }
        
        return fallback_data.get(category, [])

    def _get_fallback_mapping(self, text_concept: str, preferred_categories: Optional[List[ProEthicaCategory]] = None) -> Optional[ConceptMapping]:
        """Get fallback concept mapping using simple text matching."""
        text_lower = text_concept.lower()
        
        # Simple keyword-based mapping
        mappings = {
            "engineer": (ProEthicaCategory.ROLE, "Professional Engineer"),
            "manager": (ProEthicaCategory.ROLE, "Engineering Manager"),
            "client": (ProEthicaCategory.ROLE, "Client"),
            "safety": (ProEthicaCategory.PRINCIPLE, "Public Safety"),
            "honest": (ProEthicaCategory.PRINCIPLE, "Honesty"),
            "competent": (ProEthicaCategory.PRINCIPLE, "Competence"),
            "disclose": (ProEthicaCategory.OBLIGATION, "Disclosure"),
            "report": (ProEthicaCategory.ACTION, "Report"),
            "consult": (ProEthicaCategory.ACTION, "Consult")
        }
        
        best_match = None
        best_score = 0.0
        
        for keyword, (category, label) in mappings.items():
            if keyword in text_lower:
                score = 0.7 if keyword == text_lower else 0.5
                
                # Prefer specified categories
                if preferred_categories and category in preferred_categories:
                    score += 0.2
                    
                if score > best_score:
                    best_score = score
                    best_match = (category, label)
        
        if best_match and best_score > 0.4:  # Minimum threshold
            category, label = best_match
            return ConceptMapping(
                text_concept=text_concept,
                ontology_entity=OntologyEntity(
                    uri=f"http://proethica.org/fallback#{label.replace(' ', '')}",
                    label=label,
                    category=category.value,
                    description=f"Fallback mapping for '{text_concept}'",
                    confidence=best_score,
                    source="fallback"
                ),
                similarity_score=best_score,
                mapping_method="fallback_keyword"
            )
            
        return None

    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of MCP client."""
        return {
            "server_url": self.server_url,
            "fallback_enabled": self.fallback_enabled,
            "cache_size": len(self._entity_cache),
            "session_active": self._session is not None
        }

# Convenience functions for common operations
async def get_role_for_participant(participant_name: str, context: Optional[str] = None) -> Optional[OntologyEntity]:
    """Get role entity for participant name."""
    async with MCPOntologyClient() as client:
        return await client.map_participant_to_role(participant_name, context)

async def enrich_decision_with_ontology(decision_text: str, context: Optional[str] = None) -> Dict[str, Any]:
    """Enrich decision with ontology categories."""
    async with MCPOntologyClient() as client:
        return await client.enrich_decision_with_ontology(decision_text, context)

async def get_entities_for_category(category: ProEthicaCategory, domain: str = "engineering-ethics") -> List[OntologyEntity]:
    """Get all entities in a ProEthica category."""
    async with MCPOntologyClient() as client:
        return await client.get_entities_by_category(category, domain)