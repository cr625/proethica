"""
Service for analyzing guidelines and extracting ontology concepts.
Clean version without backward compatibility - requires proper ontology structure.
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
    This service requires GuidelineConceptTypes to be defined in the ontology.
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
        Retrieve GuidelineConceptTypes from the ontology.
        Raises RuntimeError if types cannot be retrieved.
        """
        if self._guideline_concept_types is not None:
            return self._guideline_concept_types
            
        logger.info("Querying ontology for GuidelineConceptTypes")
        
        # Query the ontology for GuidelineConceptTypes
        mcp_url = self.mcp_client.mcp_url
        if not mcp_url:
            raise RuntimeError("MCP server URL not configured")
            
        try:
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
                                ORDER BY ?label
                            """
                        }
                    },
                    "id": 1
                },
                timeout=30
            )
            
            if response.status_code != 200:
                raise RuntimeError(f"MCP server returned status {response.status_code}")
                
            result = response.json()
            if "error" in result:
                raise RuntimeError(f"MCP server error: {result['error']}")
                
            if "result" not in result or "bindings" not in result["result"]:
                raise RuntimeError("Invalid response from MCP server")
                
            concept_types = {}
            for binding in result["result"]["bindings"]:
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
            
            if not concept_types:
                raise RuntimeError("No GuidelineConceptTypes found in ontology")
                
            # Validate we have the expected 9 types (including constraint)
            expected_types = {"role", "principle", "obligation", "state", "resource", "action", "event", "capability", "constraint"}
            found_types = set(concept_types.keys())
            
            if found_types != expected_types:
                missing = expected_types - found_types
                extra = found_types - expected_types
                error_msg = "Ontology GuidelineConceptTypes mismatch."
                if missing:
                    error_msg += f" Missing: {missing}."
                if extra:
                    error_msg += f" Unexpected: {extra}."
                raise RuntimeError(error_msg)
            
            self._guideline_concept_types = concept_types
            logger.info(f"Successfully loaded {len(concept_types)} GuidelineConceptTypes from ontology")
            return concept_types
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to query MCP server: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error retrieving GuidelineConceptTypes: {str(e)}")
    
    def _extract_examples_from_comment(self, comment: str) -> List[str]:
        """Extract examples from a comment string."""
        if not comment or "Examples include" not in comment:
            return []
        
        # Extract the part after "Examples include"
        examples_part = comment.split("Examples include")[-1]
        # Remove trailing period and split by comma
        examples = [ex.strip() for ex in examples_part.rstrip(".").split(",")]
        return examples
        
    def extract_concepts(self, content: str, ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract concepts from guideline content using ontology-defined types.
        
        Args:
            content: The text content of the guideline document
            ontology_source: Optional ontology source identifier
            
        Returns:
            Dict containing the extracted concepts or error information
        """
        try:
            logger.info(f"Extracting concepts from guideline content")
            
            # Get concept types from ontology (will raise error if not available)
            try:
                concept_types = self._get_guideline_concept_types()
            except RuntimeError as e:
                logger.error(f"Cannot extract concepts without ontology types: {str(e)}")
                return {"error": f"Ontology configuration error: {str(e)}"}
            
            # If mock responses are enabled, return mock concepts
            if self.use_mock_responses:
                logger.info("Using mock concept response mode")
                mock_concepts = self._generate_mock_concepts(content, concept_types)
                return {
                    "concepts": mock_concepts,
                    "mock": True,
                    "message": "Using mock guideline responses"
                }
            
            # Try MCP server first
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Using MCP server for concept extraction")
                    
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
                                    "concept_types": list(concept_types.keys())
                                }
                            },
                            "id": 1
                        },
                        timeout=60
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "result" in result and "concepts" in result["result"]:
                            concepts = result["result"]["concepts"]
                            # Validate all concepts have valid types
                            valid_types = set(concept_types.keys())
                            for concept in concepts:
                                if concept.get("type") not in valid_types:
                                    logger.warning(f"Invalid concept type: {concept.get('type')}")
                                    concept["type"] = "state"  # Default to state
                            return result["result"]
            except Exception as e:
                logger.warning(f"MCP server error, falling back to LLM: {str(e)}")
            
            # Fall back to direct LLM processing
            return self._extract_concepts_with_llm(content, concept_types)
                
        except Exception as e:
            logger.error(f"Error in extract_concepts: {str(e)}")
            return {"error": str(e)}
    
    def _extract_concepts_with_llm(self, content: str, concept_types: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
        """Extract concepts using direct LLM calls."""
        # Get LLM client
        try:
            llm_client = get_llm_client()
        except RuntimeError as e:
            logger.error(f"LLM client not available: {str(e)}")
            return {"error": f"LLM client not available: {str(e)}"}
        
        # Build dynamic prompt
        type_descriptions = []
        for type_name, type_info in concept_types.items():
            examples = ", ".join(type_info.get("examples", []))
            if examples:
                type_descriptions.append(
                    f"- {type_info['label']}: {type_info['description']} (e.g., {examples})"
                )
            else:
                type_descriptions.append(
                    f"- {type_info['label']}: {type_info['description']}"
                )
        
        type_list = "\n".join(type_descriptions)
        valid_types = "|".join(concept_types.keys())
        
        system_prompt = f"""You are an expert in ethical engineering and ontology analysis. 
Extract key ethical concepts from engineering guidelines.

Concept types to identify:
{type_list}

For each concept, provide:
- label: Short name for the concept
- description: Brief explanation in this context
- type: One of {valid_types}
- confidence: 0.0-1.0 indicating clarity in the text"""
        
        user_prompt = f"""Extract ethical and engineering concepts from these guidelines:

{content[:10000]}

Return a JSON array of concepts:
[
    {{
        "label": "Concept Name",
        "description": "Explanation",
        "type": "{valid_types}",
        "confidence": 0.9
    }}
]

Focus on quality over quantity. Only include directly referenced or clearly implied concepts."""
        
        try:
            # Get response from LLM
            response_text = self._call_llm(llm_client, system_prompt, user_prompt)
            
            if response_text:
                concepts = self._parse_llm_response(response_text, set(concept_types.keys()))
                if concepts:
                    logger.info(f"Extracted {len(concepts)} concepts using LLM")
                    return {"concepts": concepts}
                else:
                    return {"error": "Failed to parse LLM response", "concepts": []}
            else:
                return {"error": "No response from LLM", "concepts": []}
                
        except Exception as e:
            logger.error(f"LLM extraction error: {str(e)}")
            return {"error": f"LLM error: {str(e)}", "concepts": []}
    
    def _call_llm(self, llm_client, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Make LLM API call."""
        try:
            model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-sonnet-4-6')
            
            # Modern Claude API
            if hasattr(llm_client, 'messages'):
                response = llm_client.messages.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=4000,
                    temperature=0.7
                )
                
                if hasattr(response, 'content') and len(response.content) > 0:
                    return response.content[0].text
                    
        except Exception as e:
            logger.error(f"LLM API error: {str(e)}")
            
        return None
    
    def _parse_llm_response(self, response: str, valid_types: set) -> List[Dict[str, Any]]:
        """Parse and validate concepts from LLM response."""
        try:
            # Extract JSON array from response
            json_match = re.search(r'\[.*\]', response, re.DOTALL)
            if json_match:
                concepts = json.loads(json_match.group())
                
                # Validate each concept
                validated_concepts = []
                for concept in concepts:
                    # Ensure required fields
                    if not all(field in concept for field in ["label", "description", "type"]):
                        continue
                        
                    # Validate type
                    if concept["type"] not in valid_types:
                        logger.warning(f"Invalid type '{concept['type']}' for concept '{concept['label']}'")
                        continue
                    
                    # Add default confidence if missing
                    if "confidence" not in concept:
                        concept["confidence"] = 0.7
                        
                    validated_concepts.append(concept)
                
                return validated_concepts
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
        except Exception as e:
            logger.error(f"Error parsing concepts: {e}")
            
        return []
    
    def _generate_mock_concepts(self, content: str, concept_types: Dict[str, Dict[str, str]]) -> List[Dict[str, Any]]:
        """Generate mock concepts for testing."""
        mock_concepts = []
        
        # Add one concept of each type for testing
        if "engineer" in content.lower():
            mock_concepts.append({
                "label": "Professional Engineer",
                "description": "A licensed engineer responsible for public safety",
                "type": "role",
                "confidence": 0.9
            })
            
        if "safety" in content.lower():
            mock_concepts.append({
                "label": "Public Safety",
                "description": "The paramount duty to protect public health, safety, and welfare",
                "type": "principle",
                "confidence": 0.95
            })
            
        if "confidential" in content.lower():
            mock_concepts.append({
                "label": "Maintain Confidentiality",
                "description": "The obligation to protect client confidential information",
                "type": "obligation",
                "confidence": 0.85
            })
            
        # Add at least one of each type if content is long enough
        if len(content) > 100:
            mock_concepts.extend([
                {
                    "label": "Budget Constraints",
                    "description": "Financial limitations affecting project decisions",
                    "type": "state",
                    "confidence": 0.7
                },
                {
                    "label": "Technical Standards",
                    "description": "Engineering codes and specifications",
                    "type": "resource",
                    "confidence": 0.8
                },
                {
                    "label": "Design Review",
                    "description": "Systematic evaluation of engineering designs",
                    "type": "action",
                    "confidence": 0.75
                },
                {
                    "label": "Project Completion",
                    "description": "The finalization of an engineering project",
                    "type": "event",
                    "confidence": 0.7
                },
                {
                    "label": "Risk Assessment",
                    "description": "The ability to identify and evaluate potential hazards",
                    "type": "capability",
                    "confidence": 0.8
                }
            ])
            
        return mock_concepts
    
    def generate_triples_for_concepts(self, concepts: List[Dict[str, Any]], 
                                    world_id: int, 
                                    guideline_id: Optional[int] = None,
                                    ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate RDF triples for the given concepts.
        """
        # This method would remain largely the same as the original
        # Implementation details for triple generation...
        pass