"""
Relationship Tools

This module provides tools for suggesting and validating relationships
between ontology concepts using LLM capabilities.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

from mcp.hosted_llm_mcp.adapters.model_router import ModelRouter
from mcp.hosted_llm_mcp.integration.ontology_connector import OntologyConnector

logger = logging.getLogger(__name__)

class RelationshipTools:
    """
    Tools for suggesting and validating relationships between ontology concepts.
    
    This class provides:
    1. Relationship suggestion between concepts
    2. Ontology consistency validation
    3. Integration with existing ontology relationships
    """

    def __init__(self, model_router: ModelRouter, ontology_connector: OntologyConnector):
        """
        Initialize the relationship tools.
        
        Args:
            model_router: The model router for directing tasks to appropriate LLMs
            ontology_connector: The ontology connector for retrieving ontology data
        """
        self.model_router = model_router
        self.ontology_connector = ontology_connector
        logger.info("Relationship tools initialized")

    async def suggest(self, 
                     source_concept: str, 
                     target_concept: str, 
                     domain: str = "") -> Dict[str, Any]:
        """
        Suggest potential relationships between ontology concepts.
        
        Args:
            source_concept: The source concept
            target_concept: The target concept
            domain: The domain of the ontology (e.g., ethics, engineering)
            
        Returns:
            A dictionary containing the suggested relationships
        """
        # Get information about the source concept
        source_data = {}
        try:
            search_result = await self.ontology_connector.search_ontology(source_concept)
            if search_result.get("success", False):
                entities = search_result.get("entities", [])
                if entities:
                    entity_uri = entities[0].get("uri")
                    entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    if entity_data.get("success", False):
                        source_data = entity_data.get("entity", {})
        except Exception as e:
            logger.warning(f"Error retrieving data for source concept '{source_concept}': {str(e)}")
        
        # Get information about the target concept
        target_data = {}
        try:
            search_result = await self.ontology_connector.search_ontology(target_concept)
            if search_result.get("success", False):
                entities = search_result.get("entities", [])
                if entities:
                    entity_uri = entities[0].get("uri")
                    entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    if entity_data.get("success", False):
                        target_data = entity_data.get("entity", {})
        except Exception as e:
            logger.warning(f"Error retrieving data for target concept '{target_concept}': {str(e)}")
        
        # Check if a relationship already exists
        existing_relationships = []
        try:
            if source_data and "uri" in source_data:
                rel_data = await self.ontology_connector.get_relationships(source_data["uri"])
                if rel_data.get("success", False):
                    all_rels = rel_data.get("relationships", [])
                    # Filter for relationships with the target concept
                    if target_data and "uri" in target_data:
                        existing_relationships = [
                            rel for rel in all_rels 
                            if rel.get("object") == target_data["uri"] or rel.get("subject") == target_data["uri"]
                        ]
        except Exception as e:
            logger.warning(f"Error checking existing relationships: {str(e)}")
        
        # Prepare prompt with ontology context
        prompt = f"Suggest relationships between the following ontology concepts:\n\n"
        prompt += f"Source concept: {source_concept}\n"
        prompt += f"Target concept: {target_concept}\n"
        
        if domain:
            prompt += f"Domain: {domain}\n\n"
        
        if source_data or target_data:
            prompt += "Ontology information:\n\n"
            
            if source_data:
                prompt += f"Source concept data:\n{json.dumps(source_data, indent=2)}\n\n"
                
            if target_data:
                prompt += f"Target concept data:\n{json.dumps(target_data, indent=2)}\n\n"
        
        if existing_relationships:
            prompt += f"Existing relationships between these concepts:\n{json.dumps(existing_relationships, indent=2)}\n\n"
            prompt += "Please suggest additional relationships or refinements to the existing ones.\n"
        else:
            prompt += "Please suggest possible semantic relationships between these concepts.\n"
            
        prompt += "For each suggested relationship, provide:\n"
        prompt += "1. The relationship type (e.g., 'is-a', 'has-part', 'influences', etc.)\n"
        prompt += "2. The direction of the relationship\n"
        prompt += "3. A description of how the concepts relate\n"
        prompt += "4. A confidence score (0-1)\n"
        prompt += "5. The reasoning behind this suggestion\n"
        
        # Route to the appropriate model (likely OpenAI)
        result = await self.model_router.route("suggest_relationships", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        suggestions = result.get("result", {})
        
        return {
            "success": True,
            "source_concept": source_concept,
            "target_concept": target_concept,
            "domain": domain,
            "suggestions": suggestions,
            "existing_relationships": existing_relationships if existing_relationships else None,
            "model_used": result.get("model", "unknown")
        }

    async def validate(self, 
                      concepts: List[str], 
                      relationships: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        Validate the consistency and coherence of ontology concepts and relationships.
        
        Args:
            concepts: The list of concepts to validate
            relationships: The relationships to validate
            
        Returns:
            A dictionary containing the validation results
        """
        # Get ontology data for the concepts
        concept_data = {}
        for concept in concepts:
            try:
                search_result = await self.ontology_connector.search_ontology(concept)
                if search_result.get("success", False):
                    entities = search_result.get("entities", [])
                    if entities:
                        entity_uri = entities[0].get("uri")
                        entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                        if entity_data.get("success", False):
                            concept_data[concept] = entity_data.get("entity", {})
            except Exception as e:
                logger.warning(f"Error retrieving data for concept '{concept}': {str(e)}")
        
        # Prepare relationships data
        relationship_data = []
        if relationships:
            # Use provided relationships
            relationship_data = relationships
        else:
            # Try to get relationships from the ontology
            for concept, data in concept_data.items():
                if "uri" in data:
                    try:
                        rel_data = await self.ontology_connector.get_relationships(data["uri"])
                        if rel_data.get("success", False):
                            rels = rel_data.get("relationships", [])
                            relationship_data.extend(rels)
                    except Exception as e:
                        logger.warning(f"Error retrieving relationships for '{concept}': {str(e)}")
        
        # Prepare prompt
        prompt = "Validate the consistency and coherence of the following ontology elements:\n\n"
        
        prompt += "Concepts:\n"
        for concept in concepts:
            prompt += f"- {concept}\n"
        
        prompt += "\nConcept Details:\n"
        prompt += json.dumps(concept_data, indent=2)
        
        if relationship_data:
            prompt += "\n\nRelationships:\n"
            prompt += json.dumps(relationship_data, indent=2)
        
        prompt += "\n\nPlease identify any inconsistencies, contradictions, missing relationships, "
        prompt += "ambiguous concepts, redundancies, or structural issues in this ontology section."
        prompt += "\nFor each issue found, provide:\n"
        prompt += "- A clear description of the problem\n"
        prompt += "- The specific concepts or relationships involved\n"
        prompt += "- A suggested resolution\n"
        prompt += "- The severity level (high, medium, low)\n\n"
        prompt += "If no issues are found, confirm the ontology section is valid.\n"
        
        # Route to the appropriate model (likely OpenAI)
        result = await self.model_router.route("validate_ontology", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        validation_result = result.get("result", {})
        
        return {
            "success": True,
            "validation": validation_result,
            "concepts_validated": len(concepts),
            "relationships_validated": len(relationship_data),
            "model_used": result.get("model", "unknown")
        }
