"""
Service for analyzing guidelines and extracting ontology concepts.
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
        
    def extract_concepts(self, content: str, ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract concepts from guideline content with enhanced MCP integration.
        
        Args:
            content: The text content of the guideline document
            ontology_source: Optional ontology source identifier to give context for extraction
            
        Returns:
            Dict containing the extracted concepts or error information
        """
        try:
            logger.info(f"Extracting concepts from guideline content with ontology source: {ontology_source}")
            
            # First try using MCP server's guideline_analysis module (direct JSON-RPC call)
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
                                    "ontology_source": ontology_source
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
                    else:
                        logger.warning(f"MCP server returned status code {response.status_code}")
            except Exception as e:
                logger.warning(f"Error using MCP server for concept extraction: {str(e)}")
                logger.info("Falling back to direct LLM processing")
            
            # If MCP server failed or is unavailable, fall back to direct LLM processing
            
            # Get detailed ontology structure for better LLM context
            ontology_context = ""
            structured_entities = {}
            
            if ontology_source:
                try:
                    # Get ontology entities from MCP service
                    entities_data = self.mcp_client.get_ontology_entities(ontology_source)
                    
                    # Process the detailed ontology structure for LLM prompt
                    if entities_data and "entities" in entities_data:
                        structured_entities = entities_data["entities"]
                        ontology_context = self._format_ontology_context(structured_entities)
                except Exception as e:
                    logger.warning(f"Error getting ontology entities for concept extraction: {str(e)}")
            
            # Prepare input for the LLM
            llm_client = get_llm_client()
            system_prompt = """
            You are an expert in ethical engineering and ontology analysis. Your task is to extract key ethical concepts
            from engineering guidelines and standards. Focus on identifying specific types of entities:
            
            1. Roles (e.g., professional positions like Engineer, Manager)
            2. Principles (e.g., core ethical principles like Honesty, Integrity)
            3. Obligations (e.g., professional duties like Public Safety, Confidentiality)
            4. Conditions (e.g., contextual factors like Budget Constraints, Time Pressure)
            5. Resources (e.g., tools or standards like Technical Specifications)
            6. Actions (e.g., professional activities like Report Safety Concern)
            7. Events (e.g., occurrences like Project Milestone, Safety Incident)
            8. Capabilities (e.g., skills like Technical Design, Leadership)
            
            For each concept, provide:
            - A label (short name for the concept)
            - A description (brief explanation of what it means in this context)
            - Type (one of the categories above)
            - Confidence score (0.0-1.0) indicating how clearly this concept appears in the text
            """
            
            user_prompt = f"""
            {ontology_context}
            
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
                    "type": "role|principle|obligation|condition|resource|action|event|capability",
                    "confidence": 0.9  # A number between 0-1 indicating how clearly this concept appears in the text
                }}
            ]
            ```
            
            Only include concepts that are directly referenced or implied in the guidelines. Focus on quality over quantity.
            """
            
            # Get response from LLM
            try:
                # Try newer Anthropic API format (v2.0+)
                if hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        model="gpt-4-turbo" if hasattr(llm_client, 'available_models') and "gpt-4" in llm_client.available_models else "claude-3-haiku-20240307",
                        response_format={"type": "json_object"},
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.choices[0].message.content
                # Try OpenAI format
                elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        model="gpt-4-turbo",
                        response_format={"type": "json_object"},
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.choices[0].message.content
                # Try older Anthropic API format (v1.x)
                elif hasattr(llm_client, 'completion'):
                    prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
                    response = llm_client.completion(
                        prompt=prompt,
                        model="claude-2.0",
                        max_tokens_to_sample=4000,
                        temperature=0.2
                    )
                    response_text = response.completion
                # Try older Anthropic API format (v1.x, messages version)
                elif hasattr(llm_client, 'messages'):
                    response = llm_client.messages.create(
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_prompt}
                        ],
                        model="claude-3-haiku-20240307",
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.content[0].text
                else:
                    raise ValueError("Unsupported LLM client. Cannot generate concepts.")
                
                # Process and clean up the response
                cleaned_text = response_text
                logger.info(f"Received LLM response with {len(response_text)} characters")
                
                # Remove markdown code blocks if present
                code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
                code_block_match = re.search(code_block_pattern, cleaned_text)
                if code_block_match:
                    cleaned_text = code_block_match.group(1)
                    logger.info("Successfully extracted JSON from markdown code block")
                
                # Parse the JSON response
                response_json = json.loads(cleaned_text)
                
                # Check if response is array or has concepts key
                if isinstance(response_json, list):
                    concepts = response_json
                elif isinstance(response_json, dict) and "concepts" in response_json:
                    concepts = response_json["concepts"]
                else:
                    concepts = []
                
                # Add IDs to concepts
                for i, concept in enumerate(concepts):
                    concept["id"] = i
                
                logger.info(f"Successfully extracted {len(concepts)} concepts from guideline content")
                return {"concepts": concepts}
                
            except Exception as e:
                logger.error(f"Error extracting concepts with LLM: {str(e)}")
                return {"error": str(e), "concepts": []}
                
        except Exception as e:
            logger.exception(f"Error extracting concepts from guideline: {str(e)}")
            return {"error": str(e), "concepts": []}
    
    def _format_ontology_context(self, entities_data: Dict[str, List]) -> str:
        """
        Format ontology entities into a structured context for the LLM prompt.
        
        Args:
            entities_data: Dictionary of entity types and their entities
            
        Returns:
            Formatted ontology context string
        """
        context = "## Engineering Ethics Ontology Entities\n\n"
        
        # Format by entity type
        for category, entities in entities_data.items():
            if not entities:
                continue
                
            context += f"### {category.upper()}\n"
            for entity in entities:
                label = entity.get("label", "")
                desc = entity.get("description", "No description")
                
                context += f"- {label}: {desc}\n"
            
            context += "\n"
        
        return context
            
    def match_concepts(self, concepts: List[Dict[str, Any]], ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Match extracted concepts to ontology entities with improved MCP integration.
        
        Args:
            concepts: List of concept dictionaries extracted from the guideline
            ontology_source: Optional ontology source identifier for matching
            
        Returns:
            Dict containing matched entities and confidence scores
        """
        try:
            logger.info(f"Matching {len(concepts)} concepts to ontology entities")
            
            # Try to use the MCP server's match_concepts_to_ontology tool directly
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Attempting to use MCP server at {mcp_url} for concept matching")
                    
                    # Make JSON-RPC call to MCP server
                    response = requests.post(
                        f"{mcp_url}/jsonrpc",
                        json={
                            "jsonrpc": "2.0",
                            "method": "call_tool",
                            "params": {
                                "name": "match_concepts_to_ontology",
                                "arguments": {
                                    "concepts": concepts,
                                    "ontology_source": ontology_source,
                                    "match_threshold": 0.6
                                }
                            },
                            "id": 1
                        },
                        timeout=60  # Longer timeout for matching
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "result" in result and not "error" in result:
                            logger.info(f"Successfully matched concepts using MCP server")
                            return result["result"]
                        elif "error" in result:
                            logger.warning(f"MCP server returned error: {result['error']}")
                    else:
                        logger.warning(f"MCP server returned status code {response.status_code}")
            except Exception as e:
                logger.warning(f"Error using MCP server for concept matching: {str(e)}")
                logger.info("Falling back to direct LLM processing")
            
            # If MCP server failed or is unavailable, fall back to direct LLM processing
            
            # Get ontology entities if source is provided
            ontology_entities = {}
            if ontology_source:
                try:
                    entities_data = self.mcp_client.get_ontology_entities(ontology_source)
                    if entities_data and "entities" in entities_data:
                        ontology_entities = entities_data["entities"]
                except Exception as e:
                    logger.warning(f"Error getting ontology entities for matching: {str(e)}")
            
            # If no ontology entities could be retrieved, return empty matches
            if not ontology_entities:
                logger.warning("No ontology entities available for matching")
                return {"matches": {}, "error": "No ontology entities available for matching"}
            
            # Prepare entity list for matching
            all_entities = []
            for category, entities in ontology_entities.items():
                for entity in entities:
                    all_entities.append({
                        "uri": entity.get("uri", ""),
                        "label": entity.get("label", ""),
                        "description": entity.get("description", ""),
                        "category": category
                    })
            
            # If no entities found, return empty matches
            if not all_entities:
                logger.warning("No entities found in ontology for matching")
                return {"matches": {}}
            
            # Use LLM to match concepts to entities
            llm_client = get_llm_client()
            
            # Convert concepts and entities to JSON strings for prompt
            concepts_json = json.dumps(concepts, indent=2)
            entities_json = json.dumps(all_entities[:100], indent=2)  # Limit entities to avoid token limit
            
            system_prompt = """
            You are an expert in ontology mapping and knowledge representation. Your task is to map extracted concepts
            from a guideline document to formal ontology entities. For each extracted concept, determine if there are
            matching entities in the ontology.
            
            A match can be:
            1. Exact - The concept label directly matches an entity label
            2. Synonymous - The concept is semantically equivalent to an entity
            3. Related - The concept is closely related to an entity
            4. No match - No corresponding entity exists in the ontology
            
            For each match, provide:
            - Match type (exact, synonym, related, none)
            - Match confidence (0.0 to 1.0)
            - The URI of the matched entity
            
            Format your response as a JSON object where keys are concept labels and values are arrays of matching entities.
            """
            
            user_prompt = f"""
            EXTRACTED CONCEPTS:
            {concepts_json}
            
            ONTOLOGY ENTITIES:
            {entities_json}
            
            Map the extracted concepts to the ontology entities. Respond with a JSON object in the following format:
            ```json
            {{
                "ConceptLabel1": [
                    {{
                        "uri": "http://example.org/entity1",
                        "match_type": "exact|synonym|related",
                        "confidence": 0.95,
                        "label": "Original entity label"
                    }}
                ],
                "ConceptLabel2": [] // Empty array if no matches
            }}
            ```
            
            Only include high-quality matches (confidence > 0.7). If a concept has no good matches, include it with an empty array.
            """
            
            # Get response from LLM
            try:
                # Try newer Anthropic API format (v2.0+)
                if hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        model="gpt-4-turbo" if hasattr(llm_client, 'available_models') and "gpt-4" in llm_client.available_models else "claude-3-haiku-20240307",
                        response_format={"type": "json_object"},
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.choices[0].message.content
                # Try OpenAI format
                elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        model="gpt-4-turbo",
                        response_format={"type": "json_object"},
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.choices[0].message.content
                # Try older Anthropic API format (v1.x)
                elif hasattr(llm_client, 'completion'):
                    prompt = f"{system_prompt}\n\nHuman: {user_prompt}\n\nAssistant:"
                    response = llm_client.completion(
                        prompt=prompt,
                        model="claude-2.0",
                        max_tokens_to_sample=4000,
                        temperature=0.2
                    )
                    response_text = response.completion
                # Try older Anthropic API format (v1.x, messages version)
                elif hasattr(llm_client, 'messages'):
                    response = llm_client.messages.create(
                        system=system_prompt,
                        messages=[
                            {"role": "user", "content": user_prompt}
                        ],
                        model="claude-3-haiku-20240307",
                        max_tokens=4000,
                        temperature=0.2
                    )
                    response_text = response.content[0].text
                else:
                    raise ValueError("Unsupported LLM client. Cannot match concepts to entities.")
                
                # Extract and parse the JSON from the response
                cleaned_text = response_text
                
                # Remove markdown code blocks if present
                code_block_pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
                code_block_match = re.search(code_block_pattern, cleaned_text)
                if code_block_match:
                    cleaned_text = code_block_match.group(1)
                    
                # Try to parse the JSON
                matches = json.loads(cleaned_text)
                
                logger.info(f"Successfully matched concepts to ontology entities: {len(matches)} concept mappings")
                return {"matches": matches}
                
            except Exception as e:
                logger.error(f"Error matching concepts to ontology entities with LLM: {str(e)}")
                return {"matches": {}, "error": f"Failed to match concepts: {str(e)}"}
            
        except Exception as e:
            logger.exception(f"Error matching concepts to ontology entities: {str(e)}")
            return {"matches": {}, "error": str(e)}
    
    def generate_triples(self, 
                         concepts: List[Dict[str, Any]], 
                         selected_indices: List[int],
                         ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate RDF triples for selected concepts with improved MCP integration.
        
        Args:
            concepts: List of all extracted concepts
            selected_indices: Indices of concepts that the user selected
            ontology_source: Optional ontology source identifier for context
            
        Returns:
            Dict containing generated triples
        """
        try:
            logger.info(f"Generating triples for {len(selected_indices)} selected concepts")
            
            # Try to use the MCP server's generate_concept_triples tool directly
            try:
                mcp_url = self.mcp_client.mcp_url
                if mcp_url:
                    logger.info(f"Attempting to use MCP server at {mcp_url} for triple generation")
                    
                    # Make JSON-RPC call to MCP server
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
                                    "namespace": "http://proethica.org/guidelines/",
                                    "output_format": "json"
                                }
                            },
                            "id": 1
                        },
                        timeout=30  # Timeout for triple generation
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "result" in result and not "error" in result:
                            logger.info(f"Successfully generated triples using MCP server")
                            return result["result"]
                        elif "error" in result:
                            logger.warning(f"MCP server returned error: {result['error']}")
                    else:
                        logger.warning(f"MCP server returned status code {response.status_code}")
            except Exception as e:
                logger.warning(f"Error using MCP server for triple generation: {str(e)}")
                logger.info("Falling back to direct implementation")
            
            # Filter concepts to only those selected by the user
            selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
            
            if not selected_concepts:
                return {"triples": [], "triple_count": 0}
            
            # Prepare triples list
            all_triples = []
            
            # For each selected concept, create basic triples
            for concept in selected_concepts:
                # Get concept properties
                concept_label = concept.get("label", "Unknown Concept")
                concept_description = concept.get("description", "")
                concept_type = concept.get("type", "concept")
                
                # Create URIs
                # In a production system, these would be more sophisticated and use proper namespace management
                base_uri = "http://proethica.org/engineering-ethics/concept/"
                concept_uri = f"{base_uri}{self._slugify(concept_label)}"
                
                # Basic type triple
                type_triple = {
                    "subject": concept_uri,
                    "subject_label": concept_label,
                    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "predicate_label": "type",
                    "object": f"http://proethica.org/engineering-ethics/{self._slugify(concept_type)}",
                    "object_label": concept_type.capitalize(),
                    "is_literal": False
                }
                all_triples.append(type_triple)
                
                # Label triple
                label_triple = {
                    "subject": concept_uri,
                    "subject_label": concept_label,
                    "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
                    "predicate_label": "label",
                    "object": concept_label,
                    "is_literal": True
                }
                all_triples.append(label_triple)
                
                # Description triple (if available)
                if concept_description:
                    description_triple = {
                        "subject": concept_uri,
                        "subject_label": concept_label,
                        "predicate": "http://purl.org/dc/elements/1.1/description",
                        "predicate_label": "description",
                        "object": concept_description,
                        "is_literal": True
                    }
                    all_triples.append(description_triple)
                
                # Add category triple
                category_triple = {
                    "subject": concept_uri,
                    "subject_label": concept_label,
                    "predicate": "http://proethica.org/ontology/hasCategory",
                    "predicate_label": "has category",
                    "object": concept_type,
                    "is_literal": True
                }
                all_triples.append(category_triple)
                
                # Add confidence score triple if present
                if "confidence" in concept:
                    confidence_triple = {
                        "subject": concept_uri,
                        "subject_label": concept_label,
                        "predicate": "http://proethica.org/ontology/hasConfidence",
                        "predicate_label": "has confidence",
                        "object": str(concept.get("confidence", 1.0)),
                        "is_literal": True
                    }
                    all_triples.append(confidence_triple)
            
            logger.info(f"Generated {len(all_triples)} triples for {len(selected_concepts)} concepts")
            return {"triples": all_triples, "triple_count": len(all_triples)}
                
        except Exception as e:
            logger.exception(f"Error generating triples for concepts: {str(e)}")
            return {"error": str(e), "triples": [], "triple_count": 0}
    
    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug.
        
        Args:
            text: Text to convert
            
        Returns:
            Slug for use in URIs
        """
        if not text:
            return "unnamed"
            
        # Convert to lowercase
        slug = text.lower()
        # Replace spaces with underscores
        slug = re.sub(r'\s+', '_', slug)
        # Remove non-alphanumeric characters except underscores
        slug = re.sub(r'[^a-z0-9_]', '', slug)
        # Replace multiple underscores with a single one
        slug = re.sub(r'_+', '_', slug)
        # Remove leading and trailing underscores
        slug = slug.strip('_')
        
        return slug
