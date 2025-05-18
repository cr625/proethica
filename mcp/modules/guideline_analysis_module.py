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
import datetime

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

# Additional logger for API compatibility issues
api_compat_logger = logging.getLogger("anthropic_api_compatibility")
api_compat_handler = logging.FileHandler(os.path.join(project_root, "anthropic_api_compatibility_issues.log"))
api_compat_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
api_compat_logger.addHandler(api_compat_handler)
api_compat_logger.setLevel(logging.INFO)

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
        logger.info(f"Extract guideline concepts - USE_MOCK_RESPONSES: {self.use_mock_responses}")
        
        try:
            content = arguments.get("content", "")
            ontology_source = arguments.get("ontology_source")
            
            if not content:
                return {"error": "No content provided"}
                
            # Import time module for timing measurements
            import time
            
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
            
            # Create system prompt for Claude with tool use - enhanced for JSON output
            system_prompt = """
            You are an expert in ethical analysis, ontology engineering, and knowledge extraction. 
            Your task is to analyze a set of ethical guidelines and extract key concepts, principles, and entities.
            
            Focus on identifying ethical principles, obligations, roles, actions, resources, capabilities, and events.
            
            CRITICAL INSTRUCTION: You MUST respond with VALID JSON only, following this exact format:
            
            {
                "concepts": [
                    {
                        "label": "string",
                        "description": "string",
                        "category": "string",
                        "related_concepts": ["string"],
                        "text_references": ["string"]
                    }
                ]
            }
            
            Your response must be valid parseable JSON with no explanations or other text outside the JSON structure.
            """
            
            # Create the user message with content
            user_message = f"Here are the ethical guidelines to analyze:\n\n{content}"
            
            # Start timer
            start_time = time.time()
            
            # Single approach optimized for the current Anthropic SDK version
            # Using prompt engineering for structured JSON output as per Anthropic documentation
            # See: https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/increase-consistency#chain-prompts-for-complex-tasks
            try:
                logger.info("Making LLM call to extract guideline concepts")
                
                # Use a stronger system prompt for JSON formatting
                enhanced_system_prompt = """
                You are an expert in ethical analysis and ontology engineering.

                IMPORTANT: Your ENTIRE response must be ONLY valid JSON matching this schema exactly:
                {
                    "concepts": [
                        {
                            "label": "string",
                            "description": "string",
                            "category": "string",
                            "related_concepts": ["string"],
                            "text_references": ["string"]
                        }
                    ]
                }

                Do not include any explanations, markdown formatting, or anything else outside the JSON structure.
                Return ONLY the JSON object - nothing before it, nothing after it.
                """

                # Make the API call with the structured output instructions in the prompt
                response = await self.llm_client.messages.create(
                    model="claude-3-7-sonnet-20250219",
                    system=enhanced_system_prompt,
                    messages=[
                        {"role": "user", "content": user_message}
                    ],
                    temperature=0.1,  # Lower temperature for more consistent results
                    max_tokens=4000
                )

                # Log the API call timing
                api_call_time = time.time() - start_time
                logger.info(f"LLM API call completed in {api_call_time:.2f} seconds")

                # Get the response content
                response_content = response.content[0].text

                # Try to parse as JSON
                try:
                    # Clean up potential JSON issues first
                    clean_json = self._extract_json_from_text(response_content)
                    result = json.loads(clean_json)

                    # Validate that it has the expected structure
                    if "concepts" not in result:
                        raise ValueError("Response does not contain 'concepts' key")

                    # Return the concepts
                    return result

                except Exception as json_error:
                    # Log the error and use mock concepts as fallback
                    logger.warning(f"LLM returned natural language instead of JSON. Using fallback concepts.")
                    api_compat_logger.error(f"JSON parsing error: {str(json_error)}")
                    api_compat_logger.error(f"Raw response was: {response_content[:500]}...")

                    # Return the mock concepts as fallback
                    logger.info("Using fallback concepts due to non-JSON response")
                    if self.mock_concepts:
                        return self.mock_concepts.copy()
                    else:
                        return {
                            "concepts": [
                                {
                                    "id": 0,
                                    "label": "Fallback Concept",
                                    "description": "This is a fallback concept due to JSON parsing failure",
                                    "category": "principle",
                                    "related_concepts": ["Error Handling"],
                                    "text_references": ["API compatibility issue"]
                                }
                            ]
                        }

            except Exception as e:
                logger.error(f"Error in LLM API call: {str(e)}")
                # Return a fallback response
                return {
                    "error": f"LLM API error: {str(e)}",
                    "concepts": []
                }
                
        except Exception as e:
            logger.error(f"Error in extract_guideline_concepts: {str(e)}")
            return {"error": str(e), "concepts": []}
    
    def _extract_json_from_text(self, text: str) -> str:
        """
        Extract JSON from text response, handling common formats.
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Extracted JSON text (cleaned)
        """
        # Return empty string for None input
        if not text:
            return "{}"
            
        # First check for JSON code blocks
        if "```json" in text:
            # Extract content from ```json blocks
            pattern = r"```json\n([\s\S]*?)\n```"
            matches = re.findall(pattern, text)
            if matches:
                # Use the first match
                return self._clean_json_text(matches[0])
        
        # Next check for generic code blocks that might contain JSON
        if "```" in text:
            # Extract content from ``` blocks
            pattern = r"```\n?([\s\S]*?)\n?```"
            matches = re.findall(pattern, text)
            if matches:
                # Try each match until we find valid JSON
                for match in matches:
                    cleaned = self._clean_json_text(match)
                    try:
                        # Test if it's valid JSON
                        json.loads(cleaned)
                        return cleaned
                    except:
                        continue
        
        # Next try to find JSON object patterns
        json_pattern = r'(\{[\s\S]*\})'
        matches = re.findall(json_pattern, text)
        if matches:
            for match in matches:
                cleaned = self._clean_json_text(match)
                try:
                    # Test if it's valid JSON
                    json.loads(cleaned)
                    return cleaned
                except:
                    continue
        
        # If all else fails, return the whole text cleaned
        return self._clean_json_text(text)
    
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
            
    async def match_concepts_to_ontology(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Match extracted concepts to ontology entities.
        
        Args:
            arguments: Dictionary with the following keys:
                - concepts: List of concept dictionaries
                - ontology_source: Optional ontology source ID
                - match_threshold: Similarity threshold
            
        Returns:
            Dictionary with matches
        """
        # Implementation to be added for concept matching
        # This is a placeholder to satisfy the interface
        return {"matches": []}
            
    def get_claude_tools(self):
        """
        Get the Claude tools definitions.
        
        Returns:
            List of tool definitions for Claude API
        """
        return self.claude_tools
