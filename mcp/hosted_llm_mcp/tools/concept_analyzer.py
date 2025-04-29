"""
Concept Analyzer

This module provides tools for analyzing and explaining ontology concepts
using LLM capabilities.
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union

from mcp.hosted_llm_mcp.adapters.model_router import ModelRouter
from mcp.hosted_llm_mcp.integration.ontology_connector import OntologyConnector

logger = logging.getLogger(__name__)

class ConceptAnalyzer:
    """
    Tools for analyzing and explaining ontology concepts.
    
    This class provides:
    1. Concept analysis to extract properties and relationships
    2. Natural language explanations of ontology concepts
    3. Integration with existing ontology structures
    """

    def __init__(self, model_router: ModelRouter, ontology_connector: OntologyConnector):
        """
        Initialize the concept analyzer.
        
        Args:
            model_router: The model router for directing tasks to appropriate LLMs
            ontology_connector: The ontology connector for retrieving ontology data
        """
        self.model_router = model_router
        self.ontology_connector = ontology_connector
        logger.info("Concept analyzer initialized")

    async def analyze(self, concept: str, context: str = "") -> Dict[str, Any]:
        """
        Analyze an ontology concept to extract its properties and relationships.
        
        Args:
            concept: The concept to analyze
            context: Additional context about the domain (optional)
            
        Returns:
            A dictionary containing the analysis results
        """
        # First, try to get information about the concept from the ontology
        ontology_data = {}
        try:
            # Search the ontology for the concept
            search_result = await self.ontology_connector.search_ontology(concept)
            
            if search_result.get("success", False):
                # If found, get detailed information
                entities = search_result.get("entities", [])
                
                if entities:
                    # Use the first match (most relevant)
                    entity_uri = entities[0].get("uri")
                    entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    
                    if entity_data.get("success", False):
                        ontology_data = entity_data.get("entity", {})
                        
                        # Get relationships
                        rel_data = await self.ontology_connector.get_relationships(entity_uri)
                        if rel_data.get("success", False):
                            ontology_data["relationships"] = rel_data.get("relationships", [])
        
        except Exception as e:
            logger.warning(f"Error retrieving ontology data for concept '{concept}': {str(e)}")
        
        # Prepare prompt with ontology context if available
        prompt = f"Analyze the ontology concept: {concept}\n\n"
        
        if context:
            prompt += f"Domain context: {context}\n\n"
            
        if ontology_data:
            prompt += "Existing ontology information:\n"
            prompt += json.dumps(ontology_data, indent=2)
            prompt += "\n\nPlease analyze this concept, extending and refining the existing information."
        else:
            prompt += "Please analyze this concept, providing a structured ontological analysis."
        
        # Route to the appropriate model (likely Claude)
        result = await self.model_router.route("analyze_concept", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        concept_analysis = result.get("result", {})
        
        # If the result is a string (raw text), try to extract structured data
        if isinstance(concept_analysis, str):
            try:
                # Try to parse as JSON if it looks like JSON
                if concept_analysis.strip().startswith("{") and concept_analysis.strip().endswith("}"):
                    concept_analysis = json.loads(concept_analysis)
                else:
                    # Otherwise return as text analysis
                    concept_analysis = {"text_analysis": concept_analysis}
            except json.JSONDecodeError:
                concept_analysis = {"text_analysis": concept_analysis}
        
        # Combine with ontology data
        if ontology_data:
            if isinstance(concept_analysis, dict):
                concept_analysis["ontology_data"] = ontology_data
        
        return {
            "success": True,
            "concept": concept,
            "analysis": concept_analysis,
            "model_used": result.get("model", "unknown")
        }

    async def explain(self, concept: str, audience: str = "expert", detail_level: str = "moderate") -> Dict[str, Any]:
        """
        Generate a natural language explanation of an ontology concept.
        
        Args:
            concept: The concept to explain
            audience: The target audience (expert, novice, student)
            detail_level: The level of detail (brief, moderate, detailed)
            
        Returns:
            A dictionary containing the explanation
        """
        # First, try to get information about the concept from the ontology
        ontology_data = {}
        try:
            # Search the ontology for the concept
            search_result = await self.ontology_connector.search_ontology(concept)
            
            if search_result.get("success", False):
                # If found, get detailed information
                entities = search_result.get("entities", [])
                
                if entities:
                    # Use the first match (most relevant)
                    entity_uri = entities[0].get("uri")
                    entity_data = await self.ontology_connector.get_entity_by_uri(entity_uri)
                    
                    if entity_data.get("success", False):
                        ontology_data = entity_data.get("entity", {})
                        
                        # Get relationships
                        rel_data = await self.ontology_connector.get_relationships(entity_uri)
                        if rel_data.get("success", False):
                            ontology_data["relationships"] = rel_data.get("relationships", [])
        
        except Exception as e:
            logger.warning(f"Error retrieving ontology data for concept '{concept}': {str(e)}")
        
        # Prepare prompt with ontology context if available
        prompt = f"Explain the ontology concept: {concept}\n\n"
        prompt += f"Target audience: {audience}\n"
        prompt += f"Level of detail: {detail_level}\n\n"
            
        if ontology_data:
            prompt += "Existing ontology information:\n"
            prompt += json.dumps(ontology_data, indent=2)
            prompt += "\n\nPlease explain this concept based on the above information, adapting your explanation for the specified audience and detail level."
        else:
            prompt += "Please explain this concept, adapting your explanation for the specified audience and detail level."
        
        # Route to the appropriate model (likely Claude)
        result = await self.model_router.route("explain_concept", prompt)
        
        if not result.get("success", False):
            return {
                "success": False,
                "error": result.get("error", "Unknown error")
            }
        
        # Process the result
        explanation = result.get("result", "")
        
        # If the result is a dictionary, extract the explanation text
        if isinstance(explanation, dict):
            if "explanation" in explanation:
                explanation_text = explanation["explanation"]
            else:
                # Use the first field found as the explanation
                for key, value in explanation.items():
                    if isinstance(value, str):
                        explanation_text = value
                        break
                else:
                    explanation_text = json.dumps(explanation)
        else:
            explanation_text = explanation
        
        return {
            "success": True,
            "concept": concept,
            "audience": audience,
            "detail_level": detail_level,
            "explanation": explanation_text,
            "model_used": result.get("model", "unknown")
        }
