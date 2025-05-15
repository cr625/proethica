#!/usr/bin/env python3
"""
Guideline Analysis Module

This module provides functionality for analyzing ethical guidelines and 
extracting concepts that can be linked to ontology entities. It leverages 
LLM capabilities to perform semantic analysis and concept matching.
"""

import os
import json
import asyncio
import logging
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Import base module class
from mcp.modules.base_module import MCPBaseModule

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GuidelineAnalysisModule(MCPBaseModule):
    """
    Module for analyzing ethical guidelines and extracting concepts.
    
    This module leverages LLM capabilities to:
    1. Extract concepts from text guidelines
    2. Match those concepts to existing ontology entities
    3. Generate RDF triples for the guidelines
    """
    
    def __init__(self, llm_client=None, ontology_client=None, embedding_client=None):
        """
        Initialize the module.
        
        Args:
            llm_client: Client for LLM API (Anthropic, OpenAI, etc.)
            ontology_client: Client for ontology operations
            embedding_client: Client for embedding calculations
        """
        # Initialize base module
        super().__init__(name="guideline_analysis")
        
        self.llm_client = llm_client
        self.ontology_client = ontology_client
        self.embedding_client = embedding_client
        
        # Development mode for faster testing without LLM calls
        self.use_mock_responses = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "false").lower() == "true"
        
        # Load mock concepts data if available
        self.mock_concepts = self._load_mock_concepts()
        
        logger.info(f"GuidelineAnalysisModule initialized with mock mode: {self.use_mock_responses}")
        
        # Set up default prompt templates
        self.concept_extraction_template = """
        You are an expert in ethical analysis, ontology engineering, and knowledge extraction. 
        Your task is to analyze a set of ethical guidelines and extract key concepts, principles, and entities.
        
        Focus on identifying:
        1. Ethical principles (e.g., honesty, integrity, responsibility)
        2. Professional obligations
        3. Stakeholders mentioned
        4. Actions and behaviors described
        5. Values emphasized
        6. Constraints or limitations
        7. Context-specific considerations
        
        For each concept you identify, provide:
        - A short label or name for the concept
        - A more detailed description of the concept
        - The category it falls under (principle, obligation, stakeholder, action, value, constraint, or other)
        - Key related concepts
        - Specific quotes or references from the text that support this concept
        
        Your output should be well-structured and comprehensive. The goal is to identify concepts that can later be linked to an engineering ethics ontology.
        
        Here are the guidelines to analyze:
        
        {content}
        
        Return your analysis in valid JSON format using the following schema:
        {{
            "concepts": [
                {{
                    "label": "string", // short name or label for the concept
                    "description": "string", // detailed description
                    "category": "string", // e.g., "principle", "obligation", "stakeholder"
                    "related_concepts": ["string"], // array of related concept labels
                    "text_references": ["string"] // quotes or section references
                }}
            ]
        }}
        """
        
        self.concept_matching_template = """
        You are an expert in ontology mapping and semantic integration. Your task is to match extracted concepts from ethical guidelines to entities in an existing ontology.
        
        For each extracted concept, determine if it matches or relates to any of the provided ontology entities. Consider synonyms, hyponyms, hypernyms, and semantic relationships.
        
        Extracted concepts:
        {concepts}
        
        Ontology entities:
        {ontology_entities}
        
        For each match, provide:
        - The concept label
        - The matched ontology entity
        - The type of match (exact, similar, broader, narrower, related)
        - A confidence score (0-1)
        - A brief explanation of why they match
        
        Return your analysis in valid JSON format using the following schema:
        {{
            "matches": [
                {{
                    "concept_label": "string",
                    "ontology_entity": "string",
                    "match_type": "string", // "exact", "similar", "broader", "narrower", or "related"
                    "confidence": float, // 0-1 value
                    "explanation": "string"
                }}
            ]
        }}
        """
    
    def _register_tools(self):
        """Register this module's tools."""
        self.register_tool(
            name="extract_guideline_concepts",
            handler=self.extract_guideline_concepts,
            description="Extract concepts from guideline content",
            input_schema={
                "type": "object",
                "properties": {
                    "content": {
                        "type": "string", 
                        "description": "Guideline content to analyze"
                    },
                    "ontology_source": {
                        "type": "string",
                        "description": "Optional ontology source ID"
                    }
                },
                "required": ["content"],
                "additionalProperties": False
            }
        )
        
        self.register_tool(
            name="match_concepts_to_ontology",
            handler=self.match_concepts_to_ontology,
            description="Match extracted concepts to ontology entities",
            input_schema={
                "type": "object", 
                "properties": {
                    "concepts": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "Extracted concepts"
                    },
                    "ontology_source": {
                        "type": "string",
                        "description": "Ontology source ID"
                    },
                    "match_threshold": {
                        "type": "number",
                        "description": "Matching threshold (0.0-1.0)",
                        "minimum": 0,
                        "maximum": 1,
                        "default": 0.5
                    }
                },
                "required": ["concepts"],
                "additionalProperties": False
            }
        )
        
        self.register_tool(
            name="generate_concept_triples",
            handler=self.generate_concept_triples,
            description="Generate RDF triples for selected concepts",
            input_schema={
                "type": "object",
                "properties": {
                    "concepts": {
                        "type": "array", 
                        "items": {"type": "object"},
                        "description": "List of concepts"
                    },
                    "selected_indices": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Indices of selected concepts"
                    },
                    "ontology_source": {
                        "type": "string",
                        "description": "Ontology source ID"
                    },
                    "namespace": {
                        "type": "string",
                        "description": "Namespace for generated entities",
                        "default": "http://proethica.org/guidelines/"
                    },
                    "output_format": {
                        "type": "string",
                        "description": "Output format (turtle, jsonld, etc.)",
                        "enum": ["turtle", "jsonld", "ntriples"],
                        "default": "turtle"
                    }
                },
                "required": ["concepts", "selected_indices"],
                "additionalProperties": False
            }
        )
    
    def _load_mock_concepts(self) -> Dict[str, Any]:
        """
        Load mock concept data from guideline_concepts.json file.
        
        Returns:
            Dictionary with mock concepts data
        """
        try:
            # Check if we have a guideline_concepts.json file in the project root
            mock_file_path = os.path.join(project_root, "guideline_concepts.json")
            
            if os.path.exists(mock_file_path):
                logger.info(f"Loading mock concepts from {mock_file_path}")
                with open(mock_file_path, 'r', encoding='utf-8') as f:
                    concepts_data = json.load(f)
                    
                # If it's just an array, wrap it in the expected format
                if isinstance(concepts_data, list):
                    concepts_data = {"concepts": concepts_data}
                    
                logger.info(f"Successfully loaded {len(concepts_data.get('concepts', []))} mock concepts")
                return concepts_data
            else:
                # If no file exists, also check test_concepts_output.json
                alt_file_path = os.path.join(project_root, "test_concepts_output.json")
                if os.path.exists(alt_file_path):
                    logger.info(f"Loading mock concepts from {alt_file_path}")
                    with open(alt_file_path, 'r', encoding='utf-8') as f:
                        concepts_data = json.load(f)
                        
                    # If it's just an array, wrap it in the expected format
                    if isinstance(concepts_data, list):
                        concepts_data = {"concepts": concepts_data}
                        
                    logger.info(f"Successfully loaded {len(concepts_data.get('concepts', []))} mock concepts")
                    return concepts_data
            
            # If no files exist, return empty mock data
            logger.warning("No mock concept data files found, using empty mock data")
            return {"concepts": []}
            
        except Exception as e:
            logger.error(f"Error loading mock concepts: {str(e)}")
            return {"concepts": []}
    
    async def extract_guideline_concepts(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract concepts from guideline content.
        
        Args:
            arguments: Dictionary with the following keys:
                - content: The guideline content to analyze
                - ontology_source: Optional ontology source ID
            
        Returns:
            Dictionary with extracted concepts
        """
        # DEBUGGING BREAKPOINT - This line is for manual debugging
        import inspect
        current_frame = inspect.currentframe()
        frame_info = inspect.getframeinfo(current_frame)
        logger.debug(f"BREAKPOINT: Hit extract_guideline_concepts at {frame_info.filename}:{frame_info.lineno}")
        logger.debug(f"BREAKPOINT: Arguments: {arguments}")
        
        try:
            content = arguments.get("content", "")
            ontology_source = arguments.get("ontology_source")
            
            if not content:
                return {"error": "No content provided"}
                
            # Check if we should use mock responses for faster development
            if self.use_mock_responses:
                logger.info("Using mock concepts response (development mode)")
                # Clone the mock concepts data to avoid modifying the original
                if self.mock_concepts:
                    return self.mock_concepts.copy()
                else:
                    # Generate simple mock concepts if no mock data is available
                    return {
                        "concepts": [
                            {
                                "id": 0,
                                "label": "Public Safety",
                                "description": "The paramount obligation of engineers to prioritize public safety",
                                "category": "principle",
                                "related_concepts": ["Ethical Responsibility", "Risk Management"],
                                "text_references": ["Engineers shall hold paramount the safety of the public"]
                            },
                            {
                                "id": 1,
                                "label": "Professional Competence",
                                "description": "The obligation to only perform work within one's area of competence",
                                "category": "obligation",
                                "related_concepts": ["Professional Development", "Technical Expertise"],
                                "text_references": ["Engineers shall perform services only in areas of their competence"]
                            }
                        ]
                    }
                
            # If not using mock mode, check if LLM client is available
            if not self.llm_client:
                return {"error": "LLM client not available"}
            
            # Format the prompt with the content
            prompt = self.concept_extraction_template.format(content=content[:50000])
            
            # Call Anthropic API (assumed to be async)
            if hasattr(self.llm_client, 'messages'):  # Anthropic Claude
                # Use Claude 3 Sonnet model with updated version
                response = await self.llm_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=4000
                )
                result_text = response.content[0].text
                
            else:  # Generic fallback
                response = await self.llm_client.complete(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=4000
                )
                result_text = response.content
            
            # Extract and parse the JSON from the response
            try:
                # Simple JSON extraction - in a real implementation, use a more robust extraction
                json_text = result_text
                if "```json" in result_text:
                    json_parts = result_text.split("```json")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].split("```")[0].strip()
                elif "```" in result_text:
                    json_parts = result_text.split("```")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].strip()
                
                # Parse the JSON
                concepts_data = json.loads(json_text)
                
                # Add indexing to the concepts
                for i, concept in enumerate(concepts_data.get("concepts", [])):
                    concept["id"] = i
                
                return concepts_data
                
            except Exception as e:
                return {
                    "error": f"Failed to parse LLM response as JSON: {str(e)}",
                    "raw_response": result_text
                }
            
        except Exception as e:
            logger.error(f"Error extracting concepts: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to extract concepts: {str(e)}"}
    
    async def match_concepts_to_ontology(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match extracted concepts to ontology entities.
        
        Args:
            arguments: Dictionary with the following keys:
                - concepts: List of extracted concepts
                - ontology_source: Ontology source ID
                - match_threshold: Matching threshold (0.0-1.0)
            
        Returns:
            Dictionary with matched entities
        """
        try:
            concepts = arguments.get("concepts", [])
            ontology_source = arguments.get("ontology_source")
            match_threshold = float(arguments.get("match_threshold", 0.5))
            
            if not concepts:
                return {"error": "No concepts provided"}
                
            if not self.ontology_client:
                return {"error": "Ontology client not available"}
            
            # Get ontology entities
            if ontology_source:
                # Query specific ontology source
                entities = await self._get_entities_from_ontology(ontology_source)
            else:
                # Use default ontology
                entities = await self._get_default_entities()
            
            # Format concepts and entities for the prompt
            concepts_str = json.dumps(concepts, indent=2)
            entities_str = json.dumps(entities, indent=2)
            
            # Format the prompt
            prompt = self.concept_matching_template.format(
                concepts=concepts_str,
                ontology_entities=entities_str[:20000] # Limit size for API calls
            )
            
            # Call Anthropic API (assumed to be async)
            if hasattr(self.llm_client, 'messages'):  # Anthropic Claude
                # Use Claude 3 Sonnet model
                response = await self.llm_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=4000
                )
                result_text = response.content[0].text
                
            else:  # Generic fallback
                response = await self.llm_client.complete(
                    prompt=prompt,
                    temperature=0.2,
                    max_tokens=4000
                )
                result_text = response.content
            
            # Extract and parse the JSON from the response
            try:
                # Simple JSON extraction
                json_text = result_text
                if "```json" in result_text:
                    json_parts = result_text.split("```json")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].split("```")[0].strip()
                elif "```" in result_text:
                    json_parts = result_text.split("```")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].strip()
                
                # Parse the JSON
                matches_data = json.loads(json_text)
                
                # Filter matches based on threshold
                if "matches" in matches_data:
                    matches_data["matches"] = [
                        m for m in matches_data["matches"] if m.get("confidence", 0) >= match_threshold
                    ]
                
                return matches_data
                
            except Exception as e:
                return {
                    "error": f"Failed to parse LLM response as JSON: {str(e)}",
                    "raw_response": result_text
                }
            
        except Exception as e:
            logger.error(f"Error matching concepts: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to match concepts: {str(e)}"}
    
    async def generate_concept_triples(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate RDF triples for selected concepts.
        
        Args:
            arguments: Dictionary with the following keys:
                - concepts: List of concepts
                - selected_indices: Indices of selected concepts
                - ontology_source: Ontology source ID
                - namespace: Namespace for generated entities
                - output_format: Output format (turtle, jsonld, etc.)
            
        Returns:
            Dictionary with generated triples
        """
        try:
            concepts = arguments.get("concepts", [])
            selected_indices = arguments.get("selected_indices", [])
            ontology_source = arguments.get("ontology_source")
            namespace = arguments.get("namespace", "http://proethica.org/guidelines/")
            output_format = arguments.get("output_format", "turtle")
            
            if not selected_indices:
                return {"triples": [], "triple_count": 0}
            
            # Filter concepts by selected indices
            selected_concepts = [
                concepts[i] for i in selected_indices 
                if i >= 0 and i < len(concepts)
            ]
            
            if not selected_concepts:
                return {"triples": [], "triple_count": 0}
            
            # Generate triples in the requested format
            # This is a simplified implementation - in reality, would use an RDF library
            
            triples = []
            for concept in selected_concepts:
                # Generate URI for the concept
                concept_uri = f"{namespace}{self._slugify(concept.get('label', 'concept'))}"
                
                # Add basic triples
                triples.append({
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "object": "http://proethica.org/ontology/EthicalConcept",
                    "subject_label": concept.get("label"),
                    "predicate_label": "type",
                    "object_label": "Ethical Concept"
                })
                
                # Add label triple
                triples.append({
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
                    "object": concept.get("label", "Unnamed Concept"),
                    "subject_label": concept.get("label"),
                    "predicate_label": "label",
                    "object_label": concept.get("label")
                })
                
                # Add description triple
                if "description" in concept:
                    triples.append({
                        "subject": concept_uri,
                        "predicate": "http://purl.org/dc/elements/1.1/description",
                        "object": concept.get("description"),
                        "subject_label": concept.get("label"),
                        "predicate_label": "description",
                        "object_label": None
                    })
                
                # Add category triple
                if "category" in concept:
                    triples.append({
                        "subject": concept_uri,
                        "predicate": "http://proethica.org/ontology/hasCategory",
                        "object": concept.get("category"),
                        "subject_label": concept.get("label"),
                        "predicate_label": "has category",
                        "object_label": concept.get("category")
                    })
                    
                    # Add as a type triple as well
                    category_uri = f"http://proethica.org/ontology/{self._capitalize(concept.get('category', 'Concept'))}"
                    triples.append({
                        "subject": concept_uri,
                        "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                        "object": category_uri,
                        "subject_label": concept.get("label"),
                        "predicate_label": "type",
                        "object_label": self._capitalize(concept.get("category", "Concept"))
                    })
                
                # Add references
                if "text_references" in concept and concept["text_references"]:
                    for i, ref in enumerate(concept["text_references"]):
                        ref_uri = f"{concept_uri}/reference/{i+1}"
                        
                        # Add reference instance
                        triples.append({
                            "subject": concept_uri,
                            "predicate": "http://proethica.org/ontology/hasReference",
                            "object": ref_uri,
                            "subject_label": concept.get("label"),
                            "predicate_label": "has reference",
                            "object_label": f"Reference {i+1}"
                        })
                        
                        # Add reference text
                        triples.append({
                            "subject": ref_uri,
                            "predicate": "http://proethica.org/ontology/referenceText",
                            "object": ref,
                            "subject_label": f"Reference {i+1}",
                            "predicate_label": "reference text",
                            "object_label": None
                        })
                
                # Add related concepts
                if "related_concepts" in concept and concept["related_concepts"]:
                    for rel_concept in concept["related_concepts"]:
                        rel_uri = f"{namespace}{self._slugify(rel_concept)}"
                        
                        triples.append({
                            "subject": concept_uri,
                            "predicate": "http://proethica.org/ontology/relatedTo",
                            "object": rel_uri,
                            "subject_label": concept.get("label"),
                            "predicate_label": "related to",
                            "object_label": rel_concept
                        })
            
            # Format the triples according to the requested format
            # For now, just return the triple objects
            
            return {
                "triples": triples,
                "triple_count": len(triples),
                "format": output_format
            }
            
        except Exception as e:
            logger.error(f"Error generating triples: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"error": f"Failed to generate triples: {str(e)}"}
    
    async def _get_entities_from_ontology(self, ontology_source: str) -> List[Dict[str, Any]]:
        """
        Get entities from the specified ontology source.
        
        Args:
            ontology_source: Ontology source ID
            
        Returns:
            List of ontology entities
        """
        if not self.ontology_client:
            logger.warning("No ontology client available, returning mock entities")
            return self._get_mock_entities(ontology_source)
        
        try:
            logger.info(f"Getting ontology entities from source: {ontology_source}")
            
            # Try to get entities from the ontology client with improved error handling
            try:
                # Direct call to ontology client
                entities_result = await self.ontology_client.get_entities(ontology_source)
                
                if not entities_result:
                    logger.warning(f"No entities returned for ontology source: {ontology_source}")
                    return self._get_mock_entities(ontology_source)
                
                # Process the entities result
                all_entities = []
                
                # Check if the result is structured by entity type
                if isinstance(entities_result, dict) and "entities" in entities_result:
                    # Extract entities from categorized structure
                    for entity_type, entities in entities_result["entities"].items():
                        for entity in entities:
                            all_entities.append({
                                "uri": entity.get("uri", ""),
                                "label": entity.get("label", ""),
                                "description": entity.get("description", ""),
                                "category": entity_type
                            })
                # Check if the result is a flat list
                elif isinstance(entities_result, list):
                    all_entities = entities_result
                
                logger.info(f"Successfully retrieved {len(all_entities)} entities from ontology client")
                return all_entities
            
            except Exception as e:
                logger.error(f"Error calling ontology client: {str(e)}")
                logger.info("Falling back to mock entities")
                return self._get_mock_entities(ontology_source)
                
        except Exception as e:
            logger.exception(f"Error getting entities from ontology: {str(e)}")
            return self._get_mock_entities(ontology_source)
    
    def _get_mock_entities(self, ontology_source: str) -> List[Dict[str, Any]]:
        """
        Get mock entities when the ontology client is unavailable.
        
        Args:
            ontology_source: Ontology source ID
            
        Returns:
            List of mock ontology entities
        """
        # Provide different mock entities based on the ontology source
        if ontology_source and "engineering" in ontology_source.lower():
            return [
                {
                    "uri": "http://proethica.org/engineering/Honesty",
                    "label": "Honesty",
                    "description": "The ethical principle of being truthful and sincere in professional conduct",
                    "category": "principle"
                },
                {
                    "uri": "http://proethica.org/engineering/Integrity",
                    "label": "Integrity",
                    "description": "Adherence to moral and ethical principles in engineering practice",
                    "category": "principle"
                },
                {
                    "uri": "http://proethica.org/engineering/PublicSafety",
                    "label": "Public Safety",
                    "description": "The paramount concern for the safety, health, and welfare of the public",
                    "category": "obligation"
                },
                {
                    "uri": "http://proethica.org/engineering/Competence",
                    "label": "Professional Competence",
                    "description": "Maintaining and improving technical skills and knowledge",
                    "category": "obligation"
                },
                {
                    "uri": "http://proethica.org/engineering/ProfessionalDevelopment",
                    "label": "Professional Development",
                    "description": "Continuous learning and improvement of skills and knowledge",
                    "category": "obligation"
                },
                {
                    "uri": "http://proethica.org/engineering/Confidentiality",
                    "label": "Confidentiality",
                    "description": "Protection of sensitive information entrusted by clients or employers",
                    "category": "obligation"
                },
                {
                    "uri": "http://proethica.org/engineering/ConflictOfInterest",
                    "label": "Conflict of Interest",
                    "description": "Situations where personal interests might compromise professional judgment",
                    "category": "condition"
                },
                {
                    "uri": "http://proethica.org/engineering/Responsibility",
                    "label": "Professional Responsibility",
                    "description": "Acceptance of the consequences of engineering decisions and actions",
                    "category": "principle"
                },
                {
                    "uri": "http://proethica.org/engineering/Engineer",
                    "label": "Engineer",
                    "description": "Professional who applies scientific knowledge to solve technical problems",
                    "category": "role"
                },
                {
                    "uri": "http://proethica.org/engineering/Client",
                    "label": "Client",
                    "description": "Person or entity that commissions engineering services",
                    "category": "role"
                },
                {
                    "uri": "http://proethica.org/engineering/Employer",
                    "label": "Employer",
                    "description": "Organization that employs engineers",
                    "category": "role"
                },
                {
                    "uri": "http://proethica.org/engineering/Public",
                    "label": "Public",
                    "description": "General population affected by engineering work",
                    "category": "role"
                }
            ]
        else:
            # Default generic entities
            return [
                {
                    "uri": "http://proethica.org/ontology/EthicalPrinciple",
                    "label": "Ethical Principle",
                    "description": "A foundational belief that guides ethical reasoning and judgment",
                    "category": "principle"
                },
                {
                    "uri": "http://proethica.org/ontology/ProfessionalObligation",
                    "label": "Professional Obligation",
                    "description": "A duty or responsibility arising from professional standards",
                    "category": "obligation"
                },
                {
                    "uri": "http://proethica.org/ontology/Stakeholder",
                    "label": "Stakeholder",
                    "description": "Individual or group affected by or capable of affecting a decision or action",
                    "category": "role"
                },
                {
                    "uri": "http://proethica.org/ontology/EthicalValue",
                    "label": "Ethical Value", 
                    "description": "A moral principle or standard that guides behavior",
                    "category": "principle"
                },
                {
                    "uri": "http://proethica.org/ontology/Resource",
                    "label": "Resource", 
                    "description": "Asset or material that can be utilized in professional practice",
                    "category": "resource"
                },
                {
                    "uri": "http://proethica.org/ontology/Action",
                    "label": "Action", 
                    "description": "Something done or performed by a professional",
                    "category": "action"
                },
                {
                    "uri": "http://proethica.org/ontology/Event",
                    "label": "Event", 
                    "description": "Occurrence or happening in a professional context",
                    "category": "event"
                },
                {
                    "uri": "http://proethica.org/ontology/Capability",
                    "label": "Capability", 
                    "description": "Ability or competence to perform specific professional tasks",
                    "category": "capability"
                }
            ]
    
    async def _get_default_entities(self) -> List[Dict[str, Any]]:
        """
        Get default ontology entities.
        
        Returns:
            List of default ontology entities
        """
        try:
            # Try to get entities from the engineering ethics ontology first
            if self.ontology_client:
                try:
                    # Check for available ontology sources
                    available_sources = await self.ontology_client.get_available_sources()
                    
                    if available_sources:
                        # Look for engineering-related sources
                        engineering_sources = [s for s in available_sources 
                                              if 'engineering' in s.lower() or 'ethics' in s.lower()]
                        
                        if engineering_sources:
                            # Use the first matching source
                            source = engineering_sources[0]
                            logger.info(f"Using default ontology source: {source}")
                            return await self._get_entities_from_ontology(source)
                except Exception as e:
                    logger.warning(f"Error getting available ontology sources: {str(e)}")
            
            # Fall back to a mix of engineering ethics and general ontology entities
            entities_eng = await self._get_entities_from_ontology("engineering_ethics")
            entities_gen = await self._get_entities_from_ontology("general")
            
            # Combine and return unique entities by URI
            all_entities = entities_eng + entities_gen
            unique_entities = {}
            for entity in all_entities:
                if entity.get("uri") not in unique_entities:
                    unique_entities[entity.get("uri")] = entity
                    
            return list(unique_entities.values())
            
        except Exception as e:
            logger.exception(f"Error getting default entities: {str(e)}")
            return self._get_mock_entities("general")
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to a URL-friendly slug.
        
        Args:
            text: String to convert
            
        Returns:
            URL-friendly slug
        """
        if not text:
            return "unnamed"
        
        import re
        # Convert to lowercase
        slug = str(text).lower()
        # Replace spaces with underscores
        slug = re.sub(r'\s+', '_', slug)
        # Remove non-alphanumeric characters except underscores
        slug = re.sub(r'[^a-z0-9_]', '', slug)
        # Replace multiple underscores with a single one
        slug = re.sub(r'_+', '_', slug)
        # Remove leading and trailing underscores
        slug = slug.strip('_')
        
        return slug if slug else "unnamed"
    
    def _capitalize(self, text: str) -> str:
        """
        Capitalize a string and remove spaces.
        
        Args:
            text: String to capitalize
            
        Returns:
            Capitalized string without spaces
        """
        if not text:
            return "Unnamed"
        
        words = text.split()
        return ''.join(word.capitalize() for word in words)
