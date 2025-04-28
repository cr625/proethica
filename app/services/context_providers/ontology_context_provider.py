#!/usr/bin/env python3
"""
Ontology Context Provider

This context provider enriches LLM context with detailed ontology information,
leveraging the enhanced ontology MCP tools.
"""

from typing import Dict, List, Any, Optional
import json
import logging
from app.services.context_providers.base_provider import ContextProvider
from app.services.enhanced_mcp_client import get_enhanced_mcp_client

logger = logging.getLogger(__name__)

class OntologyContextProvider(ContextProvider):
    """
    Context provider that enriches LLM context with detailed ontology information.
    This provider leverages the enhanced ontology MCP server to provide:
    
    - In-depth entity information
    - Relationship context between entities
    - Ontology hierarchies and structures
    - Applicable guidelines and constraints
    """
    
    def __init__(self, app_context_service):
        """Initialize with the application context service."""
        super().__init__(app_context_service)
        self.mcp_client = get_enhanced_mcp_client()
        logger.info("OntologyContextProvider initialized")
        
    def get_context(self, request_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get ontology context for the request.
        
        Args:
            request_context: Dictionary with request parameters
                - world_id: ID of the world
                - scenario_id: Optional ID of the scenario
                - query: Optional user query
                
        Returns:
            Ontology context dictionary
        """
        # Initialize results
        context = {
            "world_entities": {},
            "relevant_entities": [],
            "relationships": [],
            "guidelines": [],
            "is_enhanced": True
        }
        
        # Get world ID
        world_id = request_context.get('world_id')
        if not world_id:
            return context
        
        # Get world to extract ontology source
        from app.models.world import World
        world = World.query.get(world_id)
        if not world or not world.ontology_source:
            return context
        
        ontology_source = world.ontology_source
        context["ontology_source"] = ontology_source
        
        # Get world entities (same as before, for compatibility)
        world_entities = self.mcp_client.get_world_entities(ontology_source)
        if world_entities and "entities" in world_entities:
            context["world_entities"] = world_entities["entities"]
        
        # If there's a query, find relevant entities based on keywords
        query = request_context.get('query')
        if query:
            # Extract potential keywords from the query
            keywords = self._extract_keywords(query)
            
            # Search for each keyword
            relevant_entities = []
            for keyword in keywords:
                search_result = self.mcp_client.search_entities(
                    ontology_source=ontology_source,
                    query=keyword
                )
                if search_result and "entities" in search_result:
                    # Add search results, but avoid duplicates
                    for entity in search_result["entities"]:
                        if not any(e["uri"] == entity["uri"] for e in relevant_entities):
                            entity["matched_keyword"] = keyword
                            relevant_entities.append(entity)
            
            # Limit to top 5 most relevant entities
            context["relevant_entities"] = relevant_entities[:5]
            
            # Get details for the most relevant entity
            if relevant_entities:
                most_relevant = relevant_entities[0]
                entity_details = self.mcp_client.get_entity_details(
                    ontology_source=ontology_source,
                    entity_uri=most_relevant["uri"]
                )
                
                # Only include if we got valid details
                if entity_details and "label" in entity_details:
                    context["primary_entity"] = entity_details
                    
                    # Also get relationships for this entity
                    relationships = self.mcp_client.get_entity_relationships(
                        ontology_source=ontology_source,
                        entity_uri=most_relevant["uri"]
                    )
                    
                    if relationships and "entity" in relationships:
                        context["primary_entity_relationships"] = relationships
        
        # Get guidelines
        guidelines = self.mcp_client.get_ontology_guidelines(ontology_source)
        if guidelines and "guidelines" in guidelines:
            context["guidelines"] = guidelines["guidelines"]
            
        return context
    
    def format_context(self, context: Dict[str, Any]) -> str:
        """
        Format the ontology context for inclusion in LLM prompts.
        
        Args:
            context: Ontology context dictionary from get_context
            
        Returns:
            Formatted ontology context string
        """
        if not context:
            return ""
        
        result = ["## ONTOLOGY CONTEXT"]
        
        # Add relevant entities if any
        relevant_entities = context.get("relevant_entities", [])
        if relevant_entities:
            result.append("\n### Relevant Entities")
            for entity in relevant_entities[:5]:  # Limit to top 5
                label = entity.get("label", "Unknown")
                entity_types = entity.get("types", [])
                
                # Convert full URIs to simpler type names
                simplified_types = []
                for t in entity_types:
                    # Extract the final part of the URI
                    type_parts = t.split("/")
                    if type_parts:
                        type_name = type_parts[-1].split("#")[-1]
                        simplified_types.append(type_name.replace("_", " "))
                
                type_str = ", ".join(simplified_types) if simplified_types else "Unknown type"
                matched_keyword = entity.get("matched_keyword", "")
                
                result.append(f"- **{label}** ({type_str}) [matched: '{matched_keyword}']")
        
        # Add primary entity details if available
        primary_entity = context.get("primary_entity")
        if primary_entity:
            result.append("\n### Primary Entity Details")
            result.append(self.mcp_client.format_entity_for_context(primary_entity))
            
            # Add relationships if available
            relationships = context.get("primary_entity_relationships")
            if relationships:
                result.append("\n### Entity Relationships")
                # Format a simplified version of relationships
                entity_label = relationships.get('entity', {}).get('label', 'Unknown')
                
                incoming = relationships.get('incoming_relationships', [])
                if incoming:
                    result.append("\nIncoming:")
                    for rel in incoming[:3]:  # Limit to top 3
                        subj_label = rel.get('subject', {}).get('label', 'Unknown')
                        pred_label = rel.get('predicate', {}).get('label', 'Unknown')
                        result.append(f"- {subj_label} {pred_label} {entity_label}")
                
                outgoing = relationships.get('outgoing_relationships', [])
                if outgoing:
                    result.append("\nOutgoing:")
                    for rel in outgoing[:3]:  # Limit to top 3
                        pred_label = rel.get('predicate', {}).get('label', 'Unknown')
                        
                        if rel.get('object', {}).get('is_literal', True):
                            obj_value = rel.get('object', {}).get('value', 'Unknown')
                            result.append(f"- {entity_label} {pred_label} {obj_value}")
                        else:
                            obj_label = rel.get('object', {}).get('label', 'Unknown')
                            result.append(f"- {entity_label} {pred_label} {obj_label}")
        
        # Add guidelines if available
        guidelines = context.get("guidelines", [])
        if guidelines:
            result.append("\n### Ontology Guidelines")
            for guideline in guidelines[:3]:  # Limit to top 3 guidelines
                label = guideline.get("label", "Unnamed Guideline")
                description = guideline.get("description", "")
                if len(description) > 100:
                    description = description[:100] + "..."
                
                result.append(f"- **{label}**: {description}")
        
        return "\n".join(result)
    
    def _extract_keywords(self, query: str) -> List[str]:
        """
        Extract potential entity-related keywords from a query.
        
        Args:
            query: User query string
            
        Returns:
            List of potential keywords
        """
        if not query:
            return []
        
        # Simple approach: split by spaces, filter out common words
        common_words = {
            "the", "a", "an", "and", "or", "but", "if", "of", "in", "on", 
            "for", "with", "by", "at", "to", "from", "as", "is", "are", "am",
            "was", "were", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "should", "could", "can", "may",
            "might", "must", "shall", "this", "that", "these", "those", "it",
            "its", "they", "them", "their", "we", "us", "our", "i", "me", "my",
            "you", "your"
        }
        
        words = query.lower().replace("?", "").replace("!", "").replace(".", "").replace(",", "").split()
        keywords = [word for word in words if word not in common_words and len(word) > 2]
        
        # Include multi-word phrases that might be entity names
        # This is a simple approach - could be improved with NLP
        phrases = []
        for i in range(len(words) - 1):
            if words[i] not in common_words and words[i+1] not in common_words:
                phrases.append(words[i] + " " + words[i+1])
        
        return keywords + phrases

# Register this provider with the application context service
def register_provider():
    """Register the ontology context provider with the application context service."""
    from app.services.application_context_service import ApplicationContextService
    
    service = ApplicationContextService.get_instance()
    provider = OntologyContextProvider(service)
    registered = service.register_context_provider(OntologyContextProvider)
    
    if registered:
        logger.info("OntologyContextProvider registered successfully")
    else:
        logger.error("Failed to register OntologyContextProvider")
        
    return registered
