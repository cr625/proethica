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
from app.services.guideline_concept_type_mapper import GuidelineConceptTypeMapper
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
        
        # Initialize type mapper for intelligent type mapping
        self.type_mapper = GuidelineConceptTypeMapper()
        logger.info("GuidelineAnalysisService initialized with intelligent type mapping")
        
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
            
            logger.info(f"MCP server response status: {response.status_code}")
            
            if response.status_code != 200:
                raise RuntimeError(f"MCP server returned status {response.status_code}")
                
            result = response.json()
            logger.info(f"MCP server response keys: {list(result.keys())}")
            
            if "error" in result:
                raise RuntimeError(f"MCP server error: {result['error']}")
                
            if "result" not in result or "bindings" not in result["result"]:
                logger.error(f"Invalid MCP response structure: {result}")
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
                            # Validate and map concept types using intelligent type mapper
                            valid_types = set(concept_types.keys())
                            for concept in concepts:
                                # MCP server returns "category" field, map it to "type" for consistency
                                original_type = concept.get("type") or concept.get("category")
                                concept["type"] = original_type  # Ensure type field is set
                                if original_type not in valid_types:
                                    logger.info(f"Mapping invalid type '{original_type}' for concept '{concept.get('label', 'Unknown')}'")
                                    
                                    # Use type mapper to get better mapping
                                    mapping_result = self.type_mapper.map_concept_type(
                                        llm_type=original_type,
                                        concept_description=concept.get("description", ""),
                                        concept_name=concept.get("label", "")
                                    )
                                    
                                    # Store original type and mapping metadata (two-tier approach)
                                    concept["original_llm_type"] = original_type
                                    concept["type"] = mapping_result.mapped_type
                                    concept["type_mapping_confidence"] = mapping_result.confidence
                                    concept["needs_type_review"] = mapping_result.needs_review
                                    concept["mapping_justification"] = mapping_result.justification
                                    concept["semantic_label"] = mapping_result.semantic_label
                                    concept["mapping_source"] = mapping_result.mapping_source
                                    
                                    logger.info(f"Mapped '{original_type}' → '{mapping_result.mapped_type}' (confidence: {mapping_result.confidence:.2f})")
                                else:
                                    # Type is already valid - add exact match metadata
                                    concept["original_llm_type"] = original_type
                                    concept["type_mapping_confidence"] = 1.0
                                    concept["needs_type_review"] = False
                                    concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                                    concept["semantic_label"] = original_type
                                    concept["mapping_source"] = "exact_match"
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
            model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
            
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
        """Parse and validate concepts from LLM response using intelligent type mapping."""
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
                        logger.warning(f"Skipping concept missing required fields: {concept}")
                        continue
                    
                    original_type = concept["type"]
                    
                    # Validate and map concept type
                    if original_type not in valid_types:
                        logger.info(f"Mapping invalid type '{original_type}' for concept '{concept['label']}'")
                        
                        # Use type mapper to get better mapping
                        mapping_result = self.type_mapper.map_concept_type(
                            llm_type=original_type,
                            concept_description=concept.get("description", ""),
                            concept_name=concept.get("label", "")
                        )
                        
                        # Store original type and mapping metadata
                        concept["original_llm_type"] = original_type
                        concept["type"] = mapping_result.mapped_type
                        concept["type_mapping_confidence"] = mapping_result.confidence
                        concept["needs_type_review"] = mapping_result.needs_review
                        concept["mapping_justification"] = mapping_result.justification
                        
                        logger.info(f"Mapped '{original_type}' → '{mapping_result.mapped_type}' (confidence: {mapping_result.confidence:.2f})")
                    else:
                        # Type is already valid - no mapping needed
                        concept["original_llm_type"] = original_type
                        concept["type_mapping_confidence"] = 1.0  # Perfect confidence for exact match
                        concept["needs_type_review"] = False
                        concept["mapping_justification"] = f"Exact match to ontology type '{original_type}'"
                    
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
    
    def extract_ontology_terms_from_text(self,
                                        guideline_text: str,
                                        world_id: int,
                                        guideline_id: int,
                                        ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract ontology terms directly from guideline text.
        This finds mentions of engineering-ethics ontology terms in the text itself.
        
        Args:
            guideline_text: The full text of the guideline
            world_id: World ID for context
            guideline_id: Guideline ID for triple association
            ontology_source: Ontology to search for terms (default: 'engineering-ethics')
            
        Returns:
            Dict with extracted term triples and metadata
        """
        try:
            logger.info(f"Extracting ontology terms from guideline text")
            
            # Set default ontology source
            if not ontology_source:
                ontology_source = 'engineering-ethics'
            
            # If mock responses are enabled, return mock triples
            if self.use_mock_responses:
                logger.info("Using mock ontology term extraction")
                mock_triples = self._generate_mock_ontology_triples(guideline_text, world_id, guideline_id)
                return {
                    'success': True,
                    'triples': mock_triples,
                    'triple_count': len(mock_triples),
                    'mock': True,
                    'message': "Using mock guideline responses"
                }
            
            # Try MCP server for ontology term extraction
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Using MCP server for ontology term extraction")
                    
                    # First extract concepts from the text
                    extract_response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "extract_guideline_concepts",
                                "arguments": {
                                    "content": guideline_text[:50000],  # Limit content length
                                    "ontology_source": ontology_source
                                }
                            },
                            "id": 1
                        },
                        timeout=60
                    )
                    
                    if extract_response.status_code == 200:
                        extract_result = extract_response.json()
                        if "result" in extract_result and "concepts" in extract_result["result"]:
                            concepts = extract_result["result"]["concepts"]
                            
                            # Select all concepts (you could be more selective here)
                            selected_indices = list(range(len(concepts)))
                            
                            # Now generate triples for these concepts
                            response = requests.post(
                                f"{mcp_url}/jsonrpc",
                                json={
                                    "jsonrpc": "2.0",
                                    "method": "call_tool",
                                    "params": {
                                        "name": "generate_concept_triples",
                                        "arguments": {
                                            "concepts": concepts,
                                            "selected_indices": selected_indices,
                                            "ontology_source": ontology_source,
                                            "namespace": f"http://proethica.org/guidelines/guideline_{guideline_id}/",
                                            "output_format": "json"
                                        }
                                    },
                                    "id": 2
                                },
                                timeout=60
                            )
                    
                            if response and response.status_code == 200:
                                result = response.json()
                                if "result" in result and "triples" in result["result"]:
                                    triples = result["result"]["triples"]
                                    logger.info(f"MCP server extracted {len(triples)} ontology term triples")
                                    return {
                                        'success': True,
                                        'triples': triples,
                                        'triple_count': len(triples)
                                    }
                                elif "error" in result:
                                    logger.error(f"MCP server error: {result['error']}")
                        else:
                            logger.warning("Failed to extract concepts from text")
                            
            except Exception as e:
                logger.warning(f"MCP server error, falling back to mock: {str(e)}")
            
            # Fall back to mock triples if MCP fails
            logger.info("Falling back to mock ontology term extraction")
            mock_triples = self._generate_mock_ontology_triples(guideline_text, world_id, guideline_id)
            return {
                'success': True,
                'triples': mock_triples,
                'triple_count': len(mock_triples),
                'fallback': True,
                'message': "MCP server unavailable, using mock data"
            }
                
        except Exception as e:
            logger.error(f"Error in extract_ontology_terms_from_text: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'triples': [],
                'triple_count': 0
            }
    
    def _generate_mock_ontology_triples(self, guideline_text: str, world_id: int, guideline_id: int) -> List[Dict[str, Any]]:
        """Generate mock ontology term triples for testing."""
        mock_triples = []
        
        namespace = "http://proethica.org/guidelines/"
        ontology_namespace = "http://proethica.org/ontology/"
        guideline_uri = f"{namespace}guideline_{guideline_id}"
        
        # Mock some common ontology terms that might be found in engineering ethics text
        mock_terms = [
            {"term": "Engineer", "category": "role", "uri": f"{ontology_namespace}Engineer"},
            {"term": "Public Safety", "category": "principle", "uri": f"{ontology_namespace}PublicSafety"},
            {"term": "Professional Competence", "category": "capability", "uri": f"{ontology_namespace}ProfessionalCompetence"},
            {"term": "Conflict of Interest", "category": "condition", "uri": f"{ontology_namespace}ConflictOfInterest"},
            {"term": "Ethical Decision", "category": "action", "uri": f"{ontology_namespace}EthicalDecision"}
        ]
        
        # Add mock triples for terms that might appear in the text
        for i, term_info in enumerate(mock_terms):
            if i >= 3:  # Limit to 3 mock terms
                break
                
            # Add mention triple
            mention_triple = {
                'subject': guideline_uri,
                'subject_label': f'Guideline {guideline_id}',
                'predicate': f"{ontology_namespace}mentionsTerm",
                'predicate_label': 'mentions term',
                'object_uri': term_info['uri'],
                'object_label': term_info['term'],
                'triple_metadata': {
                    'confidence': 0.8,
                    'text_snippet': f"...{term_info['term'].lower()}...",
                    'category': term_info['category'],
                    'mock': True
                }
            }
            mock_triples.append(mention_triple)
            
            # Add category-specific relationship
            category = term_info['category']
            if category == 'role':
                rel_triple = {
                    'subject': guideline_uri,
                    'subject_label': f'Guideline {guideline_id}',
                    'predicate': f"{ontology_namespace}definesRole",
                    'predicate_label': 'defines role',
                    'object_uri': term_info['uri'],
                    'object_label': term_info['term']
                }
                mock_triples.append(rel_triple)
            elif category == 'principle':
                rel_triple = {
                    'subject': guideline_uri,
                    'subject_label': f'Guideline {guideline_id}',
                    'predicate': f"{ontology_namespace}embodiesPrinciple",
                    'predicate_label': 'embodies principle',
                    'object_uri': term_info['uri'],
                    'object_label': term_info['term']
                }
                mock_triples.append(rel_triple)
        
        return mock_triples
    
    def generate_triples_for_concepts(self, concepts: List[Dict[str, Any]], 
                                    world_id: int, 
                                    guideline_id: Optional[int] = None,
                                    ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate RDF triples for the given saved concepts.
        Skips concept extraction and goes directly to triple generation.
        
        Args:
            concepts: List of saved concept dictionaries with 'label', 'type', 'description'
            world_id: World ID for context
            guideline_id: Guideline ID for triple association
            ontology_source: Ontology to align with (default: 'engineering-ethics')
            
        Returns:
            Dict with generated triples and metadata
        """
        try:
            logger.info(f"Generating triples for {len(concepts)} saved concepts")
            
            # Set default ontology source
            if not ontology_source:
                ontology_source = 'engineering-ethics'
            
            # Convert saved concepts to the format expected by MCP server
            mcp_concepts = []
            for i, concept in enumerate(concepts):
                mcp_concept = {
                    'id': f'concept_{i}',
                    'label': concept.get('label', 'Unknown Concept'),
                    'description': concept.get('description', ''),
                    'category': concept.get('type', 'concept').lower()
                }
                mcp_concepts.append(mcp_concept)
            
            # If mock responses are enabled, return mock triples
            if self.use_mock_responses:
                logger.info("Using mock triple generation for saved concepts")
                mock_triples = self._generate_mock_ontology_triples("", world_id, guideline_id or 0)
                return {
                    'success': True,
                    'triples': mock_triples,
                    'triple_count': len(mock_triples),
                    'mock': True,
                    'message': "Using mock guideline responses"
                }
            
            # Try MCP server for triple generation
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Using MCP server for triple generation from saved concepts")
                    
                    # Generate triples for saved concepts - select all concepts
                    selected_indices = list(range(len(mcp_concepts)))
                    
                    response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "generate_concept_triples",
                                "arguments": {
                                    "concepts": mcp_concepts,
                                    "selected_indices": selected_indices,
                                    "ontology_source": ontology_source,
                                    "namespace": f"http://proethica.org/guidelines/guideline_{guideline_id}/",
                                    "output_format": "json"
                                }
                            },
                            "id": 1
                        },
                        timeout=60
                    )
            
                    if response and response.status_code == 200:
                        result = response.json()
                        if "result" in result and "triples" in result["result"]:
                            triples = result["result"]["triples"]
                            logger.info(f"MCP server generated {len(triples)} triples from saved concepts")
                            return {
                                'success': True,
                                'triples': triples,
                                'triple_count': len(triples),
                                'term_count': len(concepts)
                            }
                        elif "error" in result:
                            logger.error(f"MCP server error: {result['error']}")
                    else:
                        logger.warning(f"MCP server returned status {response.status_code}")
                        
            except Exception as e:
                logger.warning(f"MCP server error, falling back to mock: {str(e)}")
            
            # Fall back to mock triples if MCP fails
            logger.info("Falling back to mock triple generation for saved concepts")
            mock_triples = self._generate_mock_ontology_triples("", world_id, guideline_id or 0)
            return {
                'success': True,
                'triples': mock_triples,
                'triple_count': len(mock_triples),
                'term_count': len(concepts),
                'fallback': True,
                'message': "MCP server unavailable, using mock data"
            }
                
        except Exception as e:
            logger.error(f"Error in generate_triples_for_concepts: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'triples': [],
                'triple_count': 0
            }