"""
Hierarchy Tools

This module provides tools for expanding concept hierarchies and classifying entities
within the ontology using LLM capabilities.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

from mcp.hosted_llm_mcp.adapters.model_router import ModelRouter
from mcp.hosted_llm_mcp.integration.ontology_connector import OntologyConnector

logger = logging.getLogger(__name__)

class HierarchyTools:
    """
    Tools for expanding concept hierarchies and classifying entities.
    
    This class provides:
    1. Hierarchy expansion to generate sub-concepts
    2. Entity classification within the ontology
    3. Integration with existing ontology hierarchies
    """

    def __init__(self, model_router: ModelRouter, ontology_connector: OntologyConnector):
        """
        Initialize the hierarchy tools.
        
        Args:
            model_router: The model router for directing tasks to appropriate LLMs
            ontology_connector: The ontology connector for retrieving ontology data
        """
        self.model_router = model_router
        self.ontology_connector = ontology_connector
        logger.info("Hierarchy tools initialized")

    async def expand(self, 
                    concept: str, 
                    domain: str = "", 
                    depth: int = 1) -> Dict[str, Any]:
        """
        Generate potential sub-concepts for a given concept.
        
        Args:
            concept: The parent concept
            domain: The domain of the ontology
            depth: The depth of hierarchy to generate (1-3)
            
        Returns:
            A dictionary containing the hierarchy expansion
        """
        # Validate and constrain depth
        depth = max(1, min(3, depth))  # Limit between 1-3 to avoid excessive generation
        
        # Get information about the concept from the ontology
        concept_data = {}
        try:
            search_result = await self.ontology_connector.search_ontology(concept)
            if search_result.get("success", False):
                entities = search_result.get("entities", [])
                if entities:
                    entity_uri = entities[0].get("uri")
                    entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    if entity_data.get("success", False):
                        concept_data = entity_data.get("entity", {})
                        
                        # Try to get the class hierarchy
                        if "uri" in concept_data:
                            hierarchy_data = await self.ontology_connector.get_class_hierarchy(concept_data["uri"])
                            if hierarchy_data.get("success", False):
                                concept_data["hierarchy"] = hierarchy_data.get("hierarchy", {})
        except Exception as e:
            logger.warning(f"Error retrieving ontology data for concept '{concept}': {str(e)}")
        
        # Prepare prompt with ontology context
        prompt = f"Expand the hierarchy for the ontology concept: {concept}\n\n"
        
        if domain:
            prompt += f"Domain: {domain}\n\n"
            
        if concept_data:
            prompt += "Existing ontology information:\n"
            prompt += json.dumps(concept_data, indent=2)
            prompt += "\n\nPlease expand this concept hierarchy, generating additional sub-concepts."
        else:
            prompt += "Please generate a hierarchy of sub-concepts for this concept."
        
        prompt += f"\n\nGenerate a hierarchy with depth {depth}, where:"
        prompt += "\n- Depth 1: Direct sub-concepts of the main concept"
        if depth >= 2:
            prompt += "\n- Depth 2: Sub-concepts of each direct sub-concept"
        if depth >= 3:
            prompt += "\n- Depth 3: Further sub-concepts of depth 2 concepts"
        
        prompt += "\n\nFor each sub-concept, provide:"
        prompt += "\n- A clear name"
        prompt += "\n- A concise definition"
        prompt += "\n- Key properties that distinguish it from siblings"
        
        # Route to the appropriate model (likely Claude for this task)
        result = await self.model_router.route("expand_hierarchy", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        hierarchy_expansion = result.get("result", {})
        
        return {
            "success": True,
            "concept": concept,
            "domain": domain,
            "depth": depth,
            "expansion": hierarchy_expansion,
            "existing_data": concept_data if concept_data else None,
            "model_used": result.get("model", "unknown")
        }

    async def classify(self, 
                      entity: str,
                      description: str = "",
                      ontology_context: str = "") -> Dict[str, Any]:
        """
        Classify an entity within the ontology hierarchy.
        
        Args:
            entity: The entity to classify
            description: Description of the entity
            ontology_context: Context from the ontology to guide classification
            
        Returns:
            A dictionary containing the classification results
        """
        # If ontology context isn't provided, try to get relevant context
        if not ontology_context:
            try:
                # Get the class hierarchy to provide context
                hierarchy_data = await self.ontology_connector.get_class_hierarchy()
                if hierarchy_data.get("success", False):
                    ontology_context = json.dumps(hierarchy_data.get("hierarchy", {}), indent=2)
            except Exception as e:
                logger.warning(f"Error retrieving ontology hierarchy: {str(e)}")
        
        # Try to find if the entity already exists in the ontology
        entity_data = None
        try:
            search_result = await self.ontology_connector.search_ontology(entity)
            if search_result.get("success", False):
                entities = search_result.get("entities", [])
                if entities:
                    entity_uri = entities[0].get("uri")
                    entity_result = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    if entity_result.get("success", False):
                        entity_data = entity_result.get("entity", {})
        except Exception as e:
            logger.warning(f"Error searching for entity '{entity}': {str(e)}")
        
        # Prepare prompt
        prompt = f"Classify the following entity within an ontology hierarchy:\n\n"
        prompt += f"Entity: {entity}\n"
        
        if description:
            prompt += f"Description: {description}\n\n"
        
        if entity_data:
            prompt += "Existing entity information from ontology:\n"
            prompt += json.dumps(entity_data, indent=2)
            prompt += "\n\nPlease verify and refine the classification of this entity."
        else:
            prompt += "Please classify this entity within the ontology hierarchy."
        
        if ontology_context:
            prompt += "\n\nOntology context:\n"
            prompt += ontology_context
        
        prompt += "\n\nFor this entity, provide:"
        prompt += "\n1. The most specific concept class it belongs to"
        prompt += "\n2. Alternative classifications if multiple are reasonable"
        prompt += "\n3. Key properties that justify this classification"
        prompt += "\n4. Confidence score for the classification (0-1)"
        prompt += "\n5. Potential relationships to other parts of the ontology"
        
        # Route to the appropriate model (likely OpenAI)
        result = await self.model_router.route("classify_entity", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        classification = result.get("result", {})
        
        return {
            "success": True,
            "entity": entity,
            "classification": classification,
            "existing_data": entity_data if entity_data else None,
            "model_used": result.get("model", "unknown")
        }
