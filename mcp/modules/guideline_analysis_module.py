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
import re
import uuid

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
        # Define Claude tools for ontology operations first so they're available when _register_tools is called
        self.claude_tools = [
            {
                "name": "query_ontology",
                "description": "Query the ontology for existing concepts",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Query string for searching ontology entities"
                        },
                        "entity_type": {
                            "type": "string",
                            "description": "Optional entity type to filter by",
                            "enum": ["principle", "obligation", "role", "action", "resource", "capability", "event", "all"]
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "search_similar_concepts",
                "description": "Find concepts in the ontology similar to an extracted concept",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "concept_label": {
                            "type": "string",
                            "description": "Label of the concept to find similar entities for"
                        },
                        "concept_description": {
                            "type": "string",
                            "description": "Description of the concept to aid similarity matching"
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Similarity threshold (0.0-1.0)",
                            "default": 0.7
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 5
                        }
                    },
                    "required": ["concept_label"]
                }
            },
            {
                "name": "get_ontology_structure",
                "description": "Get the structure of the ontology to better understand how concepts relate",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "description": "Entity type to get structure for",
                            "enum": ["principle", "obligation", "role", "action", "resource", "capability", "event", "all"]
                        },
                        "include_relationships": {
                            "type": "boolean",
                            "description": "Whether to include relationship information",
                            "default": True
                        }
                    },
                    "required": []
                }
            }
        ]
        
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
        
        # Register tools
        self._register_tools()
        
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
                        "enum": ["turtle", "jsonld", "ntriples", "json"],
                        "default": "json"
                    }
                },
                "required": ["concepts", "selected_indices"],
                "additionalProperties": False
            }
        )
        
        # Register Claude tool handlers
        self.register_tool(
            name="query_ontology",
            handler=self.handle_query_ontology,
            description="Query the ontology for existing concepts",
            input_schema=self.get_claude_tools()[0]["input_schema"]
        )
        
        self.register_tool(
            name="search_similar_concepts",
            handler=self.handle_search_similar_concepts,
            description="Find concepts in the ontology similar to an extracted concept",
            input_schema=self.get_claude_tools()[1]["input_schema"]
        )
        
        self.register_tool(
            name="get_ontology_structure",
            handler=self.handle_get_ontology_structure,
            description="Get the structure of the ontology to better understand how concepts relate",
            input_schema=self.get_claude_tools()[2]["input_schema"]
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
    
    def get_claude_tools(self):
        """
        Get the Claude tools definitions.
        
        Returns:
            List of tool definitions for Claude API
        """
        return self.claude_tools
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to a URL-friendly slug format.
        
        Args:
            text: Input text to convert
            
        Returns:
            Slugified string
        """
        # Remove special characters
        text = re.sub(r'[^\w\s-]', '', text.lower())
        # Replace whitespace with hyphens
        text = re.sub(r'[\s_]+', '-', text)
        # Remove duplicate hyphens
        text = re.sub(r'-+', '-', text)
        # Remove leading and trailing hyphens
        text = text.strip('-')
        return text
    
    def _capitalize(self, text: str) -> str:
        """
        Capitalize the first letter of each word.
        
        Args:
            text: Input text to capitalize
            
        Returns:
            Capitalized string
        """
        if not text:
            return ""
        return text.title()
    
    def _clean_json_text(self, text: str) -> str:
        """
        Clean a JSON text to ensure it's valid.
        
        Args:
            text: JSON string to clean
            
        Returns:
            Cleaned JSON string
        """
        # Remove comments (//...)
        text = re.sub(r'//.*$', '', text, flags=re.MULTILINE)
        # Remove trailing commas
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)
        return text
    
    async def _get_entities_from_ontology(self, ontology_source: str) -> List[Dict[str, Any]]:
        """
        Get entities from the specified ontology source.
        
        Args:
            ontology_source: Ontology source ID
            
        Returns:
            List of entity dictionaries
        """
        try:
            if not self.ontology_client:
                return []
            
            # Query the ontology client for entities
            entities_data = await self.ontology_client.get_ontology_entities(ontology_source)
            
            if not entities_data or "entities" not in entities_data:
                return []
                
            # Flatten the entity structure for easier processing
            all_entities = []
            for category, entities in entities_data["entities"].items():
                for entity in entities:
                    # Add the category to the entity
                    entity["category"] = category
                    all_entities.append(entity)
            
            return all_entities
        except Exception as e:
            logger.error(f"Error getting entities from ontology: {str(e)}")
            return []
    
    async def _get_default_entities(self) -> List[Dict[str, Any]]:
        """
        Get entities from the default ontology.
        
        Returns:
            List of entity dictionaries
        """
        try:
            if not self.ontology_client:
                return []
            
            # Get available ontology sources
            sources = await self.ontology_client.get_ontology_sources()
            
            if not sources or "sources" not in sources or not sources["sources"]:
                return []
                
            # Use the first source as default
            default_source = sources["sources"][0]["id"]
            
            return await self._get_entities_from_ontology(default_source)
        except Exception as e:
            logger.error(f"Error getting default entities: {str(e)}")
            return []
    
    async def handle_query_ontology(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the query_ontology Claude tool.
        
        Args:
            arguments: Tool arguments
                - query: Query string
                - entity_type: Optional entity type filter
                - limit: Maximum number of results
        
        Returns:
            Query results
        """
        try:
            query = arguments.get("query", "")
            entity_type = arguments.get("entity_type", "all")
            limit = int(arguments.get("limit", 10))
            
            if not query:
                return {"error": "No query provided", "results": []}
            
            # Get entities from the ontology
            entities = await self._get_default_entities()
            
            if not entities:
                return {"error": "No ontology entities available", "results": []}
            
            # Filter by entity type if specified
            if entity_type != "all":
                entities = [e for e in entities if e.get("category", "").lower() == entity_type.lower()]
            
            # Search for matching entities
            # This is a simplified implementation - in reality, would use vector search or similar
            matching_entities = []
            for entity in entities:
                label = entity.get("label", "").lower()
                description = entity.get("description", "").lower()
                
                if query.lower() in label or query.lower() in description:
                    matching_entities.append(entity)
            
            # Limit the number of results
            matching_entities = matching_entities[:limit]
            
            return {
                "query": query,
                "entity_type": entity_type,
                "result_count": len(matching_entities),
                "results": matching_entities
            }
        except Exception as e:
            logger.error(f"Error handling query_ontology: {str(e)}")
            return {"error": str(e), "results": []}
    
    async def handle_search_similar_concepts(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the search_similar_concepts Claude tool.
        
        Args:
            arguments: Tool arguments
                - concept_label: Concept label to search for
                - concept_description: Optional concept description
                - threshold: Similarity threshold
                - limit: Maximum number of results
        
        Returns:
            Similar concepts
        """
        try:
            concept_label = arguments.get("concept_label", "")
            concept_description = arguments.get("concept_description", "")
            threshold = float(arguments.get("threshold", 0.7))
            limit = int(arguments.get("limit", 5))
            
            if not concept_label:
                return {"error": "No concept label provided", "results": []}
            
            # Get entities from the ontology
            entities = await self._get_default_entities()
            
            if not entities:
                return {"error": "No ontology entities available", "results": []}
            
            # If embeddings client is available, use it for similarity
            if self.embedding_client:
                query_text = concept_label
                if concept_description:
                    query_text += ": " + concept_description
                
                entity_texts = [e.get("label", "") for e in entities]
                
                # Calculate similarities
                similarities = await self.embedding_client.calculate_similarities([query_text], entity_texts)
                
                # Get the similarity scores for the first (and only) query
                similarity_scores = similarities[0]
                
                # Combine entities with their similarity scores
                entity_similarities = list(zip(entities, similarity_scores))
                
                # Filter by threshold and sort by similarity
                matching_entities = [
                    {"entity": e, "similarity": s} 
                    for e, s in entity_similarities 
                    if s >= threshold
                ]
                matching_entities.sort(key=lambda x: x["similarity"], reverse=True)
                
                # Limit the number of results
                matching_entities = matching_entities[:limit]
                
                return {
                    "concept_label": concept_label,
                    "result_count": len(matching_entities),
                    "results": [
                        {
                            "entity": e["entity"],
                            "similarity": e["similarity"]
                        } for e in matching_entities
                    ]
                }
            else:
                # Fallback to simple string matching
                matching_entities = []
                for entity in entities:
                    label = entity.get("label", "").lower()
                    description = entity.get("description", "").lower()
                    
                    # Simple similarity check
                    if (concept_label.lower() in label or 
                        label in concept_label.lower() or
                        concept_label.lower() in description):
                        matching_entities.append({
                            "entity": entity,
                            "similarity": 0.8  # Arbitrary fallback similarity
                        })
                
                # Limit the number of results
                matching_entities = matching_entities[:limit]
                
                return {
                    "concept_label": concept_label,
                    "result_count": len(matching_entities),
                    "results": [
                        {
                            "entity": e["entity"],
                            "similarity": e["similarity"]
                        } for e in matching_entities
                    ]
                }
        except Exception as e:
            logger.error(f"Error handling search_similar_concepts: {str(e)}")
            return {"error": str(e), "results": []}
    
    async def handle_get_ontology_structure(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle the get_ontology_structure Claude tool.
        
        Args:
            arguments: Tool arguments
                - entity_type: Entity type to get structure for
                - include_relationships: Whether to include relationships
        
        Returns:
            Ontology structure
        """
        try:
            entity_type = arguments.get("entity_type", "all")
            include_relationships = arguments.get("include_relationships", True)
            
            # Get entities from the ontology
            entities = await self._get_default_entities()
            
            if not entities:
                return {"error": "No ontology entities available", "structure": {}, "entity_count": 0}
            
            # Group entities by category
            structure = {}
            for entity in entities:
                category = entity.get("category", "unknown")
                if category not in structure:
                    structure[category] = []
                structure[category].append(entity)
            
            # Filter by entity type if specified
            if entity_type != "all":
                structure = {k: v for k, v in structure.items() if k.lower() == entity_type.lower()}
            
            # Include relationships if requested
            if include_relationships:
                # This is a placeholder - in reality, would query the ontology for relationships
                # For now, just return the structure as is
                pass
            
            return {
                "entity_type": entity_type,
                "entity_count": len(entities),
                "structure": structure
            }
        except Exception as e:
            logger.error(f"Error handling get_ontology_structure: {str(e)}")
            return {"error": str(e), "structure": {}, "entity_count": 0}
    
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
            
            # Get ontology context for tool use
            ontology_context = {"structure": {}, "entity_count": 0}
            if ontology_source:
                try:
                    # Load a summary of the ontology structure to provide as context
                    ontology_context = await self.handle_get_ontology_structure({"entity_type": "all", "include_relationships": True})
                except Exception as e:
                    logger.warning(f"Error getting ontology context: {str(e)}")
            
            # Create system prompt for Claude with tool use
            system_prompt = """
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
            - The type it falls under (one of: "principle", "obligation", "role", "action", "resource", "capability", "event")
            - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
            
            First use the available tools to understand the ontology structure and find similar concepts that may already exist.
            Then use this knowledge to extract and categorize concepts from the guidelines in a way that aligns with the existing ontology.
            """
            
            # Create user message with the guideline content
            user_message = f"""
            Please analyze the following guidelines and extract key ethical concepts:
            
            {content[:10000]}  # Limit to first 10k chars to avoid token limits
            
            Use the available tools to check if similar concepts already exist in the ontology, then extract concepts that align with the ontology structure.
            """
            
            # Call Anthropic API with tool use
            try:
                # Use Claude 3 Sonnet model with updated version and tool use
                response = await self.llm_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    tools=self.claude_tools,
                    tool_choice="auto",
                    temperature=0.2,
                    max_tokens=4000
                )
                
                # Process the response
                result_text = None
                tool_calls = []
                
                # Process tool calls if present
                for content_item in response.content:
                    if content_item.type == "text":
                        result_text = content_item.text
                    elif content_item.type == "tool_use":
                        tool_calls.append({
                            "name": content_item.tool_use.name,
                            "arguments": content_item.tool_use.arguments
                        })
                
                # Process all tool calls
                tool_results = []
                for tool_call in tool_calls:
                    try:
                        tool_name = tool_call["name"]
                        tool_args = tool_call["arguments"]
                        
                        # Execute the tool
                        if tool_name == "query_ontology":
                            result = await self.handle_query_ontology(tool_args)
                        elif tool_name == "search_similar_concepts":
                            result = await self.handle_search_similar_concepts(tool_args)
                        elif tool_name == "get_ontology_structure":
                            result = await self.handle_get_ontology_structure(tool_args)
                        else:
                            result = {"error": f"Unknown tool: {tool_name}"}
                        
                        tool_results.append({
                            "tool": tool_name,
                            "arguments": tool_args,
                            "result": result
                        })
                        
                    except Exception as e:
                        logger.error(f"Error executing tool call '{tool_call}': {str(e)}")
                        tool_results.append({
                            "tool": tool_call["name"],
                            "arguments": tool_call["arguments"],
                            "error": str(e)
                        })
                
                # Process the final response text
                concepts_data = {"concepts": []}
                if result_text:
                    try:
                        # Extract and parse JSON
                        json_text = result_text
                        if "```json" in result_text:
                            json_parts = result_text.split("```json")
                            if len(json_parts) > 1:
                                json_text = json_parts[1].split("```")[0].strip()
                        elif "```" in result_text:
                            json_parts = result_text.split("```")
                            if len(json_parts) > 1:
                                json_text = json_parts[1].strip()
                        
                        # Clean the JSON text to handle potential inconsistencies
                        json_text = self._clean_json_text(json_text)
                        
                        # Parse the JSON
                        try:
                            parsed_data = json.loads(json_text)
                            
                            # Make sure it has a concepts array
                            if "concepts" in parsed_data and isinstance(parsed_data["concepts"], list):
                                concepts_data = parsed_data
                                
                                # Add unique IDs to each concept if they don't have them
                                for i, concept in enumerate(concepts_data["concepts"]):
                                    if "id" not in concept:
                                        concept["id"] = i
                                        
                                logger.info(f"Successfully extracted {len(concepts_data['concepts'])} concepts")
                            else:
                                # Wrap the data in a concepts array if it's not already
                                if isinstance(parsed_data, list):
                                    concepts_data = {"concepts": parsed_data}
                                    
                                    # Add unique IDs to each concept
                                    for i, concept in enumerate(concepts_data["concepts"]):
                                        if "id" not in concept:
                                            concept["id"] = i
                                else:
                                    logger.warning("Expected concepts array in response, but none found")
                                    concepts_data = {"concepts": [], "error": "Expected concepts array in response"}
                        except json.JSONDecodeError as je:
                            logger.error(f"Error parsing JSON: {str(je)}")
                            logger.error(f"JSON text: {json_text}")
                            concepts_data = {"concepts": [], "error": f"Error parsing JSON: {str(je)}"}
                    except Exception as e:
                        logger.error(f"Error processing LLM response: {str(e)}")
                        concepts_data = {"concepts": [], "error": f"Error processing LLM response: {str(e)}"}
                
                # Add tool results to the response
                concepts_data["tool_results"] = tool_results
                
                # Add debug information
                concepts_data["debug"] = {
                    "model": "claude-3-7-sonnet-20250219",
                    "prompt_length": len(user_message),
                    "response_length": len(result_text) if result_text else 0,
                    "tool_calls_count": len(tool_calls)
                }
                
                return concepts_data
            except Exception as e:
                logger.error(f"Error calling Anthropic API: {str(e)}")
                return {"concepts": [], "error": f"Error calling Anthropic API: {str(e)}"}
        except Exception as e:
            logger.error(f"Error in extract_guideline_concepts: {str(e)}")
            return {"concepts": [], "error": str(e)}
    
    async def match_concepts_to_ontology(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match extracted concepts to ontology entities.
        
        Args:
            arguments: Dictionary with the following keys:
                - concepts: Array of extracted concepts
                - ontology_source: Optional ontology source ID
                - match_threshold: Optional matching threshold (0.0-1.0)
            
        Returns:
            Dictionary with matched concepts
        """
        try:
            concepts = arguments.get("concepts", [])
            ontology_source = arguments.get("ontology_source")
            match_threshold = float(arguments.get("match_threshold", 0.5))
            
            if not concepts:
                return {"error": "No concepts provided", "matches": []}
            
            # Get ontology entities for matching
            entities = []
            if ontology_source:
                entities = await self._get_entities_from_ontology(ontology_source)
            else:
                entities = await self._get_default_entities()
            
            if not entities:
                return {"error": "No ontology entities available", "matches": []}
            
            # If using mock mode, generate mock matches
            if self.use_mock_responses:
                logger.info("Using mock matches response (development mode)")
                mock_matches = []
                
                # Generate a match for each concept (up to 5)
                for i, concept in enumerate(concepts[:5]):
                    label = concept.get("label", f"Concept {i}")
                    category = concept.get("category", "principle")
                    
                    # Find a matching entity with similar category if possible
                    matching_entities = [e for e in entities if e.get("category", "").lower() == category.lower()]
                    
                    if matching_entities:
                        # Use the first matching entity
                        entity = matching_entities[0]
                        entity_label = entity.get("label", "Unknown Entity")
                        
                        mock_matches.append({
                            "concept_label": label,
                            "ontology_entity": entity_label,
                            "match_type": "similar",
                            "confidence": 0.75,
                            "explanation": f"Both {label} and {entity_label} are related to {category} concepts"
                        })
                
                return {"matches": mock_matches, "concepts": concepts, "entities": entities[:5]}
            
            # Use LLM to match concepts with entities
            if not self.llm_client:
                return {"error": "LLM client not available", "matches": []}
            
            # Create formatted lists for the prompt
            concept_texts = []
            for i, c in enumerate(concepts):
                concept_texts.append(f"{i+1}. {c.get('label', '')}: {c.get('description', '')}")
            
            entity_texts = []
            for i, e in enumerate(entities[:50]):  # Limit to 50 entities to avoid token limits
                cat = e.get("category", "unknown")
                entity_texts.append(f"{i+1}. {e.get('label', '')}: {e.get('description', '')} (Category: {cat})")
            
            # Fill in the template
            prompt = self.concept_matching_template.format(
                concepts="\n".join(concept_texts),
                ontology_entities="\n".join(entity_texts)
            )
            
            # Call LLM for matching
            try:
                response = await self.llm_client.completions.create(
                    model="claude-3-7-sonnet-20250219",
                    prompt=prompt,
                    max_tokens=3000,
                    temperature=0.2
                )
                
                result_text = response.completion
                
                # Extract and parse JSON
                json_text = result_text
                if "```json" in result_text:
                    json_parts = result_text.split("```json")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].split("```")[0].strip()
                elif "```" in result_text:
                    json_parts = result_text.split("```")
                    if len(json_parts) > 1:
                        json_text = json_parts[1].strip()
                
                # Clean the JSON text
                json_text = self._clean_json_text(json_text)
                
                # Parse the JSON
                try:
                    matches_data = json.loads(json_text)
                    
                    # Make sure it has a matches array
                    if "matches" in matches_data and isinstance(matches_data["matches"], list):
                        logger.info(f"Successfully matched {len(matches_data['matches'])} concepts")
                        matches_data["concepts"] = concepts
                        matches_data["entities"] = entities[:10]  # Include a sample of entities for reference
                        return matches_data
                    else:
                        logger.warning("Expected matches array in response, but none found")
                        return {"matches": [], "error": "Expected matches array in response"}
                except json.JSONDecodeError as je:
                    logger.error(f"Error parsing JSON: {str(je)}")
                    return {"matches": [], "error": f"Error parsing JSON: {str(je)}"}
            except Exception as e:
                logger.error(f"Error calling LLM API: {str(e)}")
                return {"matches": [], "error": f"Error calling LLM API: {str(e)}"}
        except Exception as e:
            logger.error(f"Error in match_concepts_to_ontology: {str(e)}")
            return {"matches": [], "error": str(e)}
    
    async def generate_concept_triples(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate RDF triples for selected concepts.
        
        This function creates RDF triples for the selected concepts, which can be
        saved to the ontology database. It uses the selected indices to identify
        which concepts from the provided list should be converted to triples.
        
        Args:
            arguments: Dictionary with the following keys:
                - concepts: List of concepts
                - selected_indices: Indices of selected concepts
                - ontology_source: Optional ontology source ID
                - namespace: Optional namespace for generated entities
                - output_format: Optional output format
            
        Returns:
            Dictionary with generated triples
        """
        try:
            concepts = arguments.get("concepts", [])
            selected_indices = arguments.get("selected_indices", [])
            ontology_source = arguments.get("ontology_source")
            namespace = arguments.get("namespace", "http://proethica.org/guidelines/")
            output_format = arguments.get("output_format", "json")
            
            if not concepts:
                return {"error": "No concepts provided"}
                
            if not selected_indices:
                return {"error": "No concepts selected"}
            
            # Create a unique identifier for the guideline
            guideline_id = str(uuid.uuid4())
            
            # Convert selected_indices to integers if they're strings
            try:
                selected_indices = [int(i) for i in selected_indices]
            except ValueError:
                return {"error": "Invalid selected_indices, must be integers"}
            
            # Normalize namespace to ensure it ends with a slash or #
            if not namespace.endswith("/") and not namespace.endswith("#"):
                namespace += "/"
            
            # Filter the selected concepts
            selected_concepts = []
            for i in selected_indices:
                if i < len(concepts):
                    selected_concepts.append(concepts[i])
                else:
                    logger.warning(f"Selected index {i} is out of range")
            
            # Generate triples
            all_triples = []
            entities = {}
            
            # Generate a triple for the guideline entity itself
            guideline_uri = f"{namespace}guideline/{guideline_id}"
            all_triples.append({
                "subject": guideline_uri,
                "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                "object": "http://proethica.org/ontology/Guideline"
            })
            
            # Add triples for each selected concept
            for concept in selected_concepts:
                # Generate a slug for the concept
                label = concept.get("label", "")
                if not label:
                    continue
                    
                slug = self._slugify(label)
                concept_uri = f"{namespace}concept/{slug}"
                
                # Store the entity for the response
                entities[slug] = {
                    "uri": concept_uri,
                    "label": label,
                    "description": concept.get("description", ""),
                    "type": concept.get("category", "concept")
                }
                
                # Add type triple
                category = concept.get("category", "concept").lower()
                if category == "principle":
                    type_uri = "http://proethica.org/ontology/Principle"
                elif category == "obligation":
                    type_uri = "http://proethica.org/ontology/Obligation"
                elif category == "stakeholder" or category == "role":
                    type_uri = "http://proethica.org/ontology/Role"
                elif category == "action":
                    type_uri = "http://proethica.org/ontology/Action"
                elif category == "value":
                    type_uri = "http://proethica.org/ontology/Value"
                elif category == "constraint":
                    type_uri = "http://proethica.org/ontology/Constraint"
                else:
                    type_uri = "http://proethica.org/ontology/Concept"
                
                all_triples.append({
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "object": type_uri
                })
                
                # Add label triple
                all_triples.append({
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
                    "object": label,
                    "datatype": "http://www.w3.org/2001/XMLSchema#string"
                })
                
                # Add description triple if available
                if "description" in concept and concept["description"]:
                    all_triples.append({
                        "subject": concept_uri,
                        "predicate": "http://www.w3.org/2000/01/rdf-schema#comment",
                        "object": concept["description"],
                        "datatype": "http://www.w3.org/2001/XMLSchema#string"
                    })
                
                # Add relationship to guideline
                all_triples.append({
                    "subject": concept_uri,
                    "predicate": "http://proethica.org/ontology/isDefinedIn",
                    "object": guideline_uri
                })
                
                # Add related concepts triples if available
                if "related_concepts" in concept and isinstance(concept["related_concepts"], list):
                    for related in concept["related_concepts"]:
                        if not related:
                            continue
                            
                        related_slug = self._slugify(related)
                        related_uri = f"{namespace}concept/{related_slug}"
                        
                        all_triples.append({
                            "subject": concept_uri,
                            "predicate": "http://proethica.org/ontology/relatedTo",
                            "object": related_uri
                        })
                        
                        # Add a triple for the related concept label
                        all_triples.append({
                            "subject": related_uri,
                            "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
                            "object": related,
                            "datatype": "http://www.w3.org/2001/XMLSchema#string"
                        })
            
            # Format triples based on requested output format
            formatted_output = ""
            if output_format == "turtle":
                # Basic Turtle formatting - a more complete implementation would use a library
                prefixes = f"""
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
                @prefix pro: <http://proethica.org/ontology/> .
                @prefix gl: <{namespace}> .
                
                """
                
                turtle_triples = []
                for triple in all_triples:
                    subj = triple["subject"]
                    pred = triple["predicate"]
                    obj = triple["object"]
                    
                    if "datatype" in triple:
                        turtle_triples.append(f'<{subj}> <{pred}> "{obj}"^^<{triple["datatype"]}> .')
                    elif pred == "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" or obj.startswith("http://"):
                        turtle_triples.append(f'<{subj}> <{pred}> <{obj}> .')
                    else:
                        turtle_triples.append(f'<{subj}> <{pred}> "{obj}" .')
                
                formatted_output = prefixes + "\n".join(turtle_triples)
                
                # Save to file if needed
                if output_format == "turtle":
                    try:
                        output_path = os.path.join(project_root, "guideline_triples.ttl")
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(formatted_output)
                        logger.info(f"Saved Turtle triples to {output_path}")
                    except Exception as e:
                        logger.error(f"Error saving Turtle file: {str(e)}")
            
            # Save JSON format 
            try:
                output_path = os.path.join(project_root, "guideline_triples.json")
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump({"triples": all_triples}, f, indent=2)
                logger.info(f"Saved JSON triples to {output_path}")
            except Exception as e:
                logger.error(f"Error saving JSON file: {str(e)}")
            
            # Return the triples
            result = {
                "triples": all_triples,
                "entities": entities,
                "selected_count": len(selected_concepts),
                "total_triples": len(all_triples)
            }
            
            if formatted_output:
                result["formatted_output"] = formatted_output
                
            return result
        except Exception as e:
            logger.error(f"Error generating concept triples: {str(e)}")
            return {"error": f"Error generating concept triples: {str(e)}"}
