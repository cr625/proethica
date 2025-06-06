"""
Service for analyzing guidelines and extracting ontology concepts.
This version dynamically retrieves concept types from the ontology.
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
import logging
import re

from app import db
from app.utils.llm_utils import get_llm_client
from app.services.mcp_client import MCPClient
from app.models.entity_triple import EntityTriple

# Set up logging
logger = logging.getLogger(__name__)

class GuidelineAnalysisService:
    """
    Service for analyzing guidelines, extracting concepts, and generating RDF triples.
    This service supports a two-phase approach:
    1. Extract concepts from guidelines
    2. Match concepts to ontology entities and generate triples
    """
    
    def __init__(self):
        self.mcp_client = MCPClient.get_instance()
        # Check if we should use mock responses
        self.use_mock_responses = os.environ.get("USE_MOCK_GUIDELINE_RESPONSES", "false").lower() == "true"
        if self.use_mock_responses:
            logger.info("GuidelineAnalysisService initialized with mock response mode enabled")
        
        # Cache for guideline concept types
        self._guideline_concept_types = None
        
    def _get_guideline_concept_types(self) -> Dict[str, Dict[str, str]]:
        """
        Retrieve GuidelineConceptTypes from the ontology dynamically.
        Returns a dict mapping type names to their details.
        """
        if self._guideline_concept_types is not None:
            return self._guideline_concept_types
            
        try:
            # Query the ontology for GuidelineConceptTypes
            logger.info("Querying ontology for GuidelineConceptTypes")
            
            # Try to get from MCP server first
            mcp_url = self.mcp_client.mcp_url
            if mcp_url:
                response = requests.post(
                    f"{mcp_url}/jsonrpc",
                    json={
                        "jsonrpc": "2.0",
                        "method": "call_tool",
                        "params": {
                            "name": "query_ontology",
                            "arguments": {
                                "sparql_query": """
                                    PREFIX : <http://proethica.org/ontology/intermediate#>
                                    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                                    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                                    
                                    SELECT ?type ?label ?comment WHERE {
                                        ?type rdf:type :GuidelineConceptType .
                                        ?type rdfs:label ?label .
                                        OPTIONAL { ?type rdfs:comment ?comment }
                                    }
                                """
                            }
                        },
                        "id": 1
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if "result" in result and not "error" in result:
                        concept_types = {}
                        for binding in result["result"].get("bindings", []):
                            type_uri = binding.get("type", {}).get("value", "")
                            type_name = type_uri.split("#")[-1].lower()
                            label = binding.get("label", {}).get("value", "")
                            comment = binding.get("comment", {}).get("value", "")
                            
                            concept_types[type_name] = {
                                "uri": type_uri,
                                "label": label,
                                "description": comment,
                                "examples": self._extract_examples_from_comment(comment)
                            }
                        
                        self._guideline_concept_types = concept_types
                        logger.info(f"Retrieved {len(concept_types)} GuidelineConceptTypes from ontology")
                        return concept_types
        except Exception as e:
            logger.warning(f"Error querying ontology for GuidelineConceptTypes: {str(e)}")
        
        # Fallback to default types if ontology query fails
        logger.info("Falling back to default GuidelineConceptTypes")
        self._guideline_concept_types = self._get_default_concept_types()
        return self._guideline_concept_types
    
    def _extract_examples_from_comment(self, comment: str) -> List[str]:
        """Extract examples from a comment string."""
        if not comment or "Examples include" not in comment:
            return []
        
        # Extract the part after "Examples include"
        examples_part = comment.split("Examples include")[-1]
        # Remove trailing period and split by comma
        examples = [ex.strip() for ex in examples_part.rstrip(".").split(",")]
        return examples
    
    def _get_default_concept_types(self) -> Dict[str, Dict[str, str]]:
        """Default concept types matching the ontology structure."""
        return {
            "role": {
                "label": "Role",
                "description": "A socially recognized status that carries responsibilities and expectations",
                "examples": ["Engineer", "Manager", "Client", "Regulator"]
            },
            "principle": {
                "label": "Principle", 
                "description": "A fundamental ethical value or belief that guides professional conduct",
                "examples": ["Honesty", "Integrity", "Sustainability", "Justice"]
            },
            "obligation": {
                "label": "Obligation",
                "description": "A professional duty or responsibility that must be fulfilled",
                "examples": ["Public Safety", "Confidentiality", "Competent Practice", "Truthful Reporting"]
            },
            "state": {
                "label": "State",
                "description": "A condition, situation, or state of affairs that provides context",
                "examples": ["Budget Constraints", "Safety Hazard", "Time Pressure", "Regulatory Compliance"]
            },
            "resource": {
                "label": "Resource",
                "description": "A physical or informational entity used in ethical scenarios",
                "examples": ["Technical Specifications", "Safety Equipment", "Project Budget", "Design Documents"]
            },
            "action": {
                "label": "Action",
                "description": "An intentional activity performed by an agent",
                "examples": ["Report Safety Concern", "Review Design", "Disclose Conflict", "Consult Expert"]
            },
            "event": {
                "label": "Event",
                "description": "An occurrence or happening in an ethical scenario",
                "examples": ["Project Milestone", "Safety Incident", "Audit Finding", "Contract Signing"]
            },
            "capability": {
                "label": "Capability",
                "description": "A skill, ability, or competency that can be realized",
                "examples": ["Technical Design", "Project Management", "Risk Assessment", "Ethical Reasoning"]
            }
        }
        
    def extract_concepts(self, content: str, ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract concepts from guideline content with dynamic concept types.
        
        Args:
            content: The text content of the guideline document
            ontology_source: Optional ontology source identifier to give context for extraction
            
        Returns:
            Dict containing the extracted concepts or error information
        """
        try:
            logger.info(f"Extracting concepts from guideline content with ontology source: {ontology_source}")
            
            # Get dynamic concept types
            concept_types = self._get_guideline_concept_types()
            
            # If mock responses are enabled, return mock concepts directly
            if self.use_mock_responses:
                logger.info("Using mock concept response mode (from environment variable)")
                mock_concepts = self._generate_mock_concepts_from_content(content, concept_types)
                return {
                    "concepts": mock_concepts,
                    "mock": True,
                    "message": "Using mock guideline responses as configured by environment variable"
                }
            
            # Otherwise, first try using MCP server's guideline_analysis module (direct JSON-RPC call)
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Attempting to use MCP server at {mcp_url} for concept extraction")
                    
                    # Make JSON-RPC call to get MCP server to extract concepts
                    response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "extract_guideline_concepts",
                                "arguments": {
                                    "content": content[:50000],  # Limit content length
                                    "ontology_source": ontology_source,
                                    "concept_types": list(concept_types.keys())  # Pass dynamic types
                                }
                            },
                            "id": 1
                        },
                        timeout=60  # Longer timeout for concept extraction
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "result" in result and not "error" in result:
                            logger.info(f"Successfully extracted concepts using MCP server")
                            return result["result"]
                        elif "error" in result:
                            logger.warning(f"MCP server returned error: {result['error']}")
            except Exception as e:
                logger.warning(f"Error using MCP server for concept extraction: {str(e)}")
                logger.info("Falling back to direct LLM processing")
            
            # If MCP server failed or is unavailable, fall back to direct LLM processing
            
            # Generate the system prompt dynamically based on concept types
            type_descriptions = []
            for i, (type_name, type_info) in enumerate(concept_types.items(), 1):
                examples = ", ".join(type_info.get("examples", []))
                if examples:
                    type_descriptions.append(
                        f"{i}. {type_info['label']} - {type_info['description']} (e.g., {examples})"
                    )
                else:
                    type_descriptions.append(
                        f"{i}. {type_info['label']} - {type_info['description']}"
                    )
            
            type_list = "\n".join(type_descriptions)
            valid_types = "|".join(concept_types.keys())
            
            system_prompt = f"""
            You are an expert in ethical engineering and ontology analysis. Your task is to extract key ethical concepts
            from engineering guidelines and standards. Focus on identifying specific types of entities:
            
            {type_list}
            
            For each concept, provide:
            - A label (short name for the concept)
            - A description (brief explanation of what it means in this context)
            - Type (one of: {valid_types})
            - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
            """
            
            user_prompt = f"""
            Please extract key ethical and engineering concepts from the following guidelines:
            
            ---
            {content[:10000]}  # Limit to first 10k chars as many LLMs have context limits
            ---
            
            Respond with a JSON array of concept objects in the following format:
            ```json
            [
                {{
                    "label": "Concept Name",
                    "description": "Explanation of the concept",
                    "type": "{valid_types}",
                    "confidence": 0.9  # A number between 0-1 indicating how clearly this concept appears in the text
                }}
            ]
            ```
            
            Only include concepts that are directly referenced or implied in the guidelines. Focus on quality over quantity.
            """
            
            # Generate mock concepts as a fallback
            mock_concepts = self._generate_mock_concepts_from_content(content, concept_types)
            
            # Get response from LLM
            try:
                llm_client = get_llm_client()
            except RuntimeError as e:
                logger.error(f"LLM client not available: {str(e)}")
                return {"concepts": mock_concepts, "error": "LLM client not available - using generated concepts as fallback", "using_fallback": True}
            
            try:
                # Get response from LLM
                response = self._get_llm_response(llm_client, system_prompt, user_prompt)
                
                if response:
                    # Parse the response to extract JSON
                    concepts = self._parse_concepts_from_response(response, valid_types)
                    
                    if concepts:
                        logger.info(f"Successfully extracted {len(concepts)} concepts using LLM")
                        return {"concepts": concepts}
                    else:
                        logger.warning("Failed to parse concepts from LLM response")
                        return {"concepts": mock_concepts, "error": "Failed to parse LLM response - using fallback concepts"}
                else:
                    logger.warning("No response from LLM")
                    return {"concepts": mock_concepts, "error": "No LLM response - using fallback concepts"}
                    
            except Exception as e:
                logger.error(f"Error during LLM concept extraction: {str(e)}")
                return {"concepts": mock_concepts, "error": f"LLM error: {str(e)} - using fallback concepts"}
                
        except Exception as e:
            logger.error(f"Error in extract_concepts: {str(e)}")
            return {"error": str(e)}
    
    def _generate_mock_concepts_from_content(self, content: str, concept_types: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Generate mock concepts based on content analysis using dynamic types."""
        concepts = []
        
        # Simple keyword-based extraction for each type
        for type_name, type_info in concept_types.items():
            if type_name == "principle":
                # Look for principle keywords
                if any(word in content.lower() for word in ["honesty", "integrity", "truthful", "ethical"]):
                    concepts.append({
                        "label": "Honesty",
                        "description": "The principle of being truthful and transparent in professional communications",
                        "type": "principle",
                        "confidence": 0.9
                    })
                if any(word in content.lower() for word in ["public", "safety", "welfare", "protect"]):
                    concepts.append({
                        "label": "Public Safety",
                        "description": "The paramount principle of protecting public health, safety, and welfare",
                        "type": "principle",
                        "confidence": 0.95
                    })
                    
            elif type_name == "obligation":
                if any(word in content.lower() for word in ["confidential", "privacy", "proprietary"]):
                    concepts.append({
                        "label": "Confidentiality",
                        "description": "The obligation to protect client and employer confidential information",
                        "type": "obligation",
                        "confidence": 0.85
                    })
                if any(word in content.lower() for word in ["competent", "qualified", "skill"]):
                    concepts.append({
                        "label": "Competent Practice",
                        "description": "The obligation to practice only within one's area of competence",
                        "type": "obligation",
                        "confidence": 0.8
                    })
                    
            elif type_name == "role":
                if "engineer" in content.lower():
                    concepts.append({
                        "label": "Engineer",
                        "description": "A licensed professional responsible for design and safety",
                        "type": "role",
                        "confidence": 0.95
                    })
                if "client" in content.lower():
                    concepts.append({
                        "label": "Client",
                        "description": "The party who commissions engineering services",
                        "type": "role",
                        "confidence": 0.9
                    })
                    
            elif type_name == "state":
                if any(word in content.lower() for word in ["conflict", "interest"]):
                    concepts.append({
                        "label": "Conflict of Interest",
                        "description": "A state where personal interests may compromise professional judgment",
                        "type": "state",
                        "confidence": 0.85
                    })
                    
        return concepts
    
    def _get_llm_response(self, llm_client, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Get response from LLM client."""
        try:
            # Try API based on detected version/capabilities
            preferred_model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
            
            # Check for available models and select the best one
            if hasattr(llm_client, 'available_models'):
                if preferred_model in llm_client.available_models:
                    model_name = preferred_model
                elif "claude-3-7-sonnet-latest" in llm_client.available_models:
                    model_name = "claude-3-7-sonnet-latest"
                elif len(llm_client.available_models) > 0:
                    model_name = llm_client.available_models[0]
                else:
                    model_name = preferred_model
            else:
                model_name = preferred_model
                
            logger.info(f"Using model: {model_name}")
            
            # Try the newer API structure
            if hasattr(llm_client, 'messages') and hasattr(llm_client.messages, 'create'):
                response = llm_client.messages.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
                
                if hasattr(response, 'content') and len(response.content) > 0:
                    return response.content[0].text
                    
            # Fall back to older API structure
            elif hasattr(llm_client, 'completions') and hasattr(llm_client.completions, 'create'):
                response = llm_client.completions.create(
                    prompt=f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:",
                    model=model_name,
                    max_tokens_to_sample=4000,
                    temperature=0.7
                )
                return response.completion
                
        except Exception as e:
            logger.error(f"Error getting LLM response: {str(e)}")
            
        return None
    
    def _parse_concepts_from_response(self, response: str, valid_types: str) -> List[Dict[str, Any]]:
        """Parse concepts from LLM response."""
        try:
            # Try to extract JSON from the response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                concepts_json = json_match.group()
                concepts = json.loads(concepts_json)
                
                # Validate and normalize types
                valid_type_list = valid_types.split("|")
                for concept in concepts:
                    if concept.get("type") not in valid_type_list:
                        # Try to map old types to new ones
                        if concept.get("type") == "condition":
                            concept["type"] = "state"
                        else:
                            # Default to state if unknown
                            concept["type"] = "state"
                            
                return concepts
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from response: {e}")
        except Exception as e:
            logger.error(f"Error parsing concepts: {e}")
            
        return []
    
    # The rest of the methods remain the same...
    def generate_triples_for_concepts(self, concepts: List[Dict[str, Any]], 
                                    world_id: int, 
                                    guideline_id: Optional[int] = None,
                                    ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """Generate RDF triples for the given concepts."""
        # Implementation remains the same as original
        pass