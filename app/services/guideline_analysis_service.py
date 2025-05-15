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
            
            # Generate mock concepts as a fallback
            mock_concepts = self._generate_mock_concepts_from_content(content)
            
            # Prepare input for the LLM
            try:
                llm_client = get_llm_client()
            except RuntimeError as e:
                logger.error(f"LLM client not available: {str(e)}")
                # Return mock concepts as fallback with a clear message
                logger.info(f"Falling back to generated mock concepts ({len(mock_concepts)} concepts)")
                return {"concepts": mock_concepts, "error": "LLM client not available - using generated concepts as fallback", "using_fallback": True}
            except Exception as e:
                logger.error(f"Error initializing LLM client: {str(e)}")
                # Return mock concepts as fallback
                logger.info(f"Falling back to generated mock concepts ({len(mock_concepts)} concepts)")
                return {"concepts": mock_concepts, "error": f"Error initializing LLM client: {str(e)} - using generated concepts as fallback", "using_fallback": True}
                
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
                # First log the LLM client type and available methods for debugging
                llm_client_type = type(llm_client).__name__
                logger.info(f"LLM client type: {llm_client_type}")
                
                # Try newer Anthropic API format (v2.0+)
                try:
                    if hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                        logger.info("Using Anthropic v2+ API format")
                        # Get preferred model from environment or config
                        preferred_model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
                        # Use preferred model if available, otherwise select best available model
                        if hasattr(llm_client, 'available_models'):
                            if preferred_model in llm_client.available_models:
                                model_name = preferred_model
                            elif "claude-3-7-sonnet-latest" in llm_client.available_models:
                                model_name = "claude-3-7-sonnet-latest"
                            elif len(llm_client.available_models) > 0:
                                model_name = llm_client.available_models[0]  # Use first available model
                            else:
                                model_name = preferred_model  # Fallback to preferred model
                        else:
                            model_name = preferred_model  # Fallback to preferred model
                        
                        logger.info(f"Using model: {model_name}")
                        
                        response = llm_client.chat.completions.create(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            model=model_name,
                            response_format={"type": "json_object"},
                            max_tokens=4000,
                            temperature=0.2
                        )
                        response_text = response.choices[0].message.content
                    # Try OpenAI format
                    elif hasattr(llm_client, 'chat') and hasattr(llm_client.chat, 'completions'):
                        logger.info("Using OpenAI API format")
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
                        logger.info("Using Anthropic v1 completion API format")
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
                        logger.info("Using Anthropic v1 messages API format")
                        response = llm_client.messages.create(
                            system=system_prompt,
                            messages=[
                                {"role": "user", "content": user_prompt}
                            ],
                            model="claude-3-7-sonnet-latest",
                            max_tokens=4000,
                            temperature=0.2
                        )
                        response_text = response.content[0].text
                    else:
                        logger.error("Unsupported LLM client type")
                        raise ValueError(f"Unsupported LLM client type: {llm_client_type}. Cannot generate concepts.")

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
                    
                except Exception as llm_error:
                    logger.error(f"Error using LLM for concept extraction: {str(llm_error)}")
                    logger.info("Falling back to mock concepts")
                    return {
                        "error": f"LLM error: {str(llm_error)}",
                        "concepts": mock_concepts
                    }
                
            except Exception as e:
                logger.error(f"Error extracting concepts with LLM: {str(e)}")
                return {"error": str(e), "concepts": mock_concepts}
                
        except Exception as e:
            logger.exception(f"Error extracting concepts from guideline: {str(e)}")
            # Always return some concepts even if everything fails
            mock_concepts = self._generate_mock_concepts_from_content(content)
            return {"error": str(e), "concepts": mock_concepts}
    
    def _generate_mock_concepts_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Generate mock concepts based on guideline content.
        Uses simple regex patterns to identify potential concepts.
        
        Args:
            content: The guideline content
            
        Returns:
            List of concept dictionaries
        """
        mock_concepts = []
        concept_id = 0
        
        # Convert content to lowercase for case-insensitive matching
        lowercase_content = content.lower()
        
        # Define common ethical engineering principles and their descriptions
        common_principles = {
            "public safety": "The paramount consideration for engineers to protect the public health, safety, and welfare",
            "integrity": "Upholding ethical standards and being honest in all professional activities",
            "accountability": "Taking responsibility for one's actions and decisions",
            "confidentiality": "Maintaining private or proprietary information as confidential",
            "competence": "Performing services only in areas of one's competence",
            "professional development": "Continuing to develop skills and knowledge throughout one's career",
            "honesty": "Being truthful and transparent in all professional interactions",
            "objectivity": "Making decisions and recommendations based on facts rather than personal bias",
            "sustainability": "Considering the environmental and social impact of engineering work",
            "fairness": "Treating all persons fairly and with respect"
        }
        
        # Check for common principles in the content
        for principle, description in common_principles.items():
            if principle in lowercase_content:
                mock_concepts.append({
                    "id": concept_id,
                    "label": principle.title(),
                    "description": description,
                    "type": "principle",
                    "confidence": 0.9
                })
                concept_id += 1
        
        # Define common engineering roles and their descriptions
        common_roles = {
            "engineer": "A professional who designs, builds, or maintains systems, structures, or processes",
            "manager": "Person responsible for planning, directing, and overseeing engineering projects or teams",
            "client": "The person or organization that commissions engineering services",
            "stakeholder": "Any person or organization with an interest in or affected by engineering decisions",
            "regulator": "Officials who enforce legal standards and compliance requirements",
            "technician": "Person who provides technical support and assistance in engineering projects"
        }
        
        # Check for common roles in the content
        for role, description in common_roles.items():
            if role in lowercase_content:
                mock_concepts.append({
                    "id": concept_id,
                    "label": role.title(),
                    "description": description,
                    "type": "role",
                    "confidence": 0.85
                })
                concept_id += 1
        
        # Look for capitalized phrases that might be important concepts
        capitalized_pattern = r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b'
        capitalized_matches = re.findall(capitalized_pattern, content)
        
        # Filter out common words and add unique capitalized phrases
        common_words = {"The", "This", "That", "These", "Those", "A", "An", "It", "They", "I", "We", "You"}
        added_phrases = set()
        
        for phrase in capitalized_matches:
            if (phrase not in common_words and phrase.lower() not in [c["label"].lower() for c in mock_concepts] 
                and phrase not in added_phrases and len(phrase) > 3):
                mock_concepts.append({
                    "id": concept_id,
                    "label": phrase,
                    "description": f"Concept identified from the guidelines",
                    "type": "concept",
                    "confidence": 0.7
                })
                added_phrases.add(phrase)
                concept_id += 1
                
                if len(mock_concepts) >= 10:
                    break
        
        # If we still have fewer than 5 concepts, add some general engineering ethical concepts
        if len(mock_concepts) < 5:
            additional_concepts = [
                {
                    "label": "Professional Responsibility",
                    "description": "The obligation of engineers to act in the best interest of their clients and the public",
                    "type": "obligation",
                    "confidence": 0.8
                },
                {
                    "label": "Ethical Decision Making",
                    "description": "The process of evaluating and choosing actions based on ethical principles",
                    "type": "capability",
                    "confidence": 0.8
                },
                {
                    "label": "Technical Standards",
                    "description": "Established norms and requirements for technical systems and processes",
                    "type": "resource",
                    "confidence": 0.75
                },
                {
                    "label": "Risk Assessment",
                    "description": "The process of identifying and evaluating potential hazards and their impacts",
                    "type": "action",
                    "confidence": 0.8
                },
                {
                    "label": "Conflict of Interest",
                    "description": "Situation where personal interests might compromise professional judgment",
                    "type": "condition",
                    "confidence": 0.85
                }
            ]
            
            for i, concept in enumerate(additional_concepts):
                if len(mock_concepts) >= 5:
                    break
                concept["id"] = concept_id + i
                mock_concepts.append(concept)
        
        logger.info(f"Generated {len(mock_concepts)} mock concepts based on content")
        return mock_concepts
    
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
            try:
                llm_client = get_llm_client()
            except RuntimeError as e:
                logger.error(f"LLM client not available: {str(e)}")
                return {"matches": {}, "error": "LLM client not available"}
            except Exception as e:
                logger.error(f"Error initializing LLM client: {str(e)}")
                return {"matches": {}, "error": f"Error initializing LLM client: {str(e)}"}
            
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
                    # Get preferred model from environment or config
                    preferred_model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
                    # Use preferred model if available, otherwise select best available model
                    if hasattr(llm_client, 'available_models'):
                        if preferred_model in llm_client.available_models:
                            model_name = preferred_model
                        elif "claude-3-7-sonnet-latest" in llm_client.available_models:
                            model_name = "claude-3-7-sonnet-latest"
                        elif len(llm_client.available_models) > 0:
                            model_name = llm_client.available_models[0]  # Use first available model
                        else:
                            model_name = preferred_model  # Fallback to preferred model
                    else:
                        model_name = preferred_model  # Fallback to preferred model
                    
                    logger.info(f"Using model for concept matching: {model_name}")
                    
                    response = llm_client.chat.completions.create(
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        model=model_name,
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
                        model="claude-3-7-sonnet-latest",
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
    
    def _slugify(self, text: str) -> str:
        """
        Convert a string to a URL-friendly slug format.
        
        Args:
            text: The text to slugify
            
        Returns:
            Slugified string
        """
        # Remove special characters and replace spaces with hyphens
        text = re.sub(r'[^\w\s-]', '', text.lower())
        # Replace spaces and consecutive hyphens with single hyphen
        text = re.sub(r'[\s_]+', '-', text)
        return text
    
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
                    
                    # Create proper filtered concepts list for the JSON-RPC call
                    selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
                    if not selected_concepts:
                        return {"triples": [], "triple_count": 0, "concept_count": 0}
                    
                    # Make JSON-RPC call to MCP server with better error handling
                    try:
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
                            timeout=60  # Longer timeout for triple generation
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            if "result" in result and not "error" in result:
                                logger.info(f"Successfully generated {result['result'].get('triple_count', 0)} triples using MCP server")
                                
                                # Enhance the response with ontology relationships
                                if ontology_source and "triples" in result["result"]:
                                    result["result"] = self._enhance_triples_with_ontology_relationships(
                                        result["result"], ontology_source
                                    )
                                return result["result"]
                            elif "error" in result:
                                logger.warning(f"MCP server returned error: {result['error']}")
                        else:
                            logger.warning(f"MCP server returned status code {response.status_code}")
                    except requests.Timeout:
                        logger.warning("Timeout occurred when calling MCP server for triple generation")
                    except requests.ConnectionError:
                        logger.warning("Connection error when calling MCP server for triple generation")
                    except Exception as e:
                        logger.warning(f"Error during MCP JSON-RPC call: {str(e)}")
            except Exception as e:
                logger.warning(f"Error using MCP server for triple generation: {str(e)}")
                logger.info("Falling back to direct implementation")
            
            # Filter concepts to only those selected by the user
            selected_concepts = [concepts[i] for i in selected_indices if i < len(concepts)]
            
            if not selected_concepts:
                return {"triples": [], "triple_count": 0, "concept_count": 0}
            
            logger.info(f"Generating triples directly for {len(selected_concepts)} concepts")
            
            # Prepare triples list
            all_triples = []
            namespace = "http://proethica.org/guidelines/"
            
            # For each selected concept, create basic triples
            for concept in selected_concepts:
                # Get concept properties
                concept_label = concept.get("label", "Unknown Concept")
                concept_description = concept.get("description", "")
                concept_type = concept.get("type", "concept")
                confidence = concept.get("confidence", 0.7)
                
                # Create URIs
                concept_uri = f"{namespace}{self._slugify(concept_label)}"
                
                # Basic type triple
                type_triple = {
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "object": f"http://proethica.org/ontology/{concept_type}",
                    "subject_label": concept_label,
                    "predicate_label": "is a",
                    "object_label": concept_type.title()
                }
                all_triples.append(type_triple)
                
                # Label triple
                label_triple = {
                    "subject": concept_uri,
                    "predicate": "http://www.w3.org/2000/01/rdf-schema#label",
                    "object": concept_label,
                    "subject_label": concept_label,
                    "predicate_label": "label",
                    "object_label": concept_label
                }
                all_triples.append(label_triple)
                
                # Description triple if provided
                if concept_description:
                    description_triple = {
                        "subject": concept_uri,
                        "predicate": "http://purl.org/dc/elements/1.1/description",
                        "object": concept_description,
                        "subject_label": concept_label,
                        "predicate_label": "has description",
                        "object_label": concept_description[:50] + "..." if len(concept_description) > 50 else concept_description
                    }
                    all_triples.append(description_triple)
                
                # Confidence triple
                confidence_triple = {
                    "subject": concept_uri,
                    "predicate": "http://proethica.org/ontology/hasConfidence",
                    "object": str(confidence),
                    "subject_label": concept_label,
                    "predicate_label": "has confidence score",
                    "object_label": str(confidence)
                }
                all_triples.append(confidence_triple)
                
                # Category triple
                category_triple = {
                    "subject": concept_uri,
                    "predicate": "http://proethica.org/ontology/hasCategory",
                    "object": concept_type,
                    "subject_label": concept_label,
                    "predicate_label": "has category",
                    "object_label": concept_type.title()
                }
                all_triples.append(category_triple)
                
                # Add relationship triples based on concept type
                if concept_type == "role":
                    # Roles typically have responsibilities
                    role_triple = {
                        "subject": concept_uri,
                        "predicate": "http://proethica.org/ontology/hasResponsibility",
                        "object": "http://proethica.org/ontology/EthicalBehavior",
                        "subject_label": concept_label,
                        "predicate_label": "has responsibility",
                        "object_label": "Ethical Behavior"
                    }
                    all_triples.append(role_triple)
                    
                elif concept_type == "principle":
                    # Principles guide actions
                    principle_triple = {
                        "subject": concept_uri,
                        "predicate": "http://proethica.org/ontology/guides",
                        "object": "http://proethica.org/ontology/ProfessionalBehavior",
                        "subject_label": concept_label,
                        "predicate_label": "guides",
                        "object_label": "Professional Behavior"
                    }
                    all_triples.append(principle_triple)
                    
                elif concept_type == "obligation":
                    # Obligations are required by roles
                    obligation_triple = {
                        "subject": concept_uri,
                        "predicate": "http://proethica.org/ontology/requiredBy",
                        "object": "http://proethica.org/ontology/ProfessionalRole",
                        "subject_label": concept_label,
                        "predicate_label": "required by",
                        "object_label": "Professional Role"
                    }
                    all_triples.append(obligation_triple)
                
                # Add related concepts if available
                if "related_concepts" in concept and isinstance(concept["related_concepts"], list):
                    for related in concept["related_concepts"]:
                        related_uri = f"{namespace}{self._slugify(related)}"
                        related_triple = {
                            "subject": concept_uri,
                            "predicate": "http://proethica.org/ontology/relatedTo",
                            "object": related_uri,
                            "subject_label": concept_label,
                            "predicate_label": "related to",
                            "object_label": related
                        }
                        all_triples.append(related_triple)
            
            # Try to enhance triples with ontology relationships if ontology source provided
            if ontology_source:
                try:
                    # Get relevant ontology entities
                    ontology_entities = self.mcp_client.get_ontology_entities(ontology_source)
                    if ontology_entities and "entities" in ontology_entities:
                        # Add ontology relationships here if needed
                        pass
                except Exception as e:
                    logger.warning(f"Could not enhance triples with ontology relationships: {str(e)}")
            
            # Save the final results
            result = {
                "triples": all_triples,
                "triple_count": len(all_triples),
                "concept_count": len(selected_concepts)
            }
            
            # Optionally save to JSON file for debugging
            try:
                with open('guideline_triples.json', 'w') as f:
                    json.dump(result, f, indent=2)
            except Exception as e:
                logger.warning(f"Could not save triples to debug file: {str(e)}")
                
            logger.info(f"Generated {len(all_triples)} triples for {len(selected_concepts)} concepts")
            return result
            
        except Exception as e:
            logger.exception(f"Error generating triples: {str(e)}")
            return {"error": str(e), "triples": [], "triple_count": 0}
    
    def _enhance_triples_with_ontology_relationships(self, triples_result: Dict, ontology_source: str) -> Dict:
        """
        Enhance triples with additional relationships to ontology entities if available.
        
        Args:
            triples_result: The triple generation result
            ontology_source: The ontology source identifier
            
        Returns:
            Enhanced triples result
        """
        try:
            # Get ontology entities
            entities_data = self.mcp_client.get_ontology_entities(ontology_source)
            if not entities_data or "entities" not in entities_data:
                return triples_result
                
            all_triples = triples_result.get("triples", [])
            
            # Extract subjects from existing triples
            subjects = {}
            for triple in all_triples:
                if "subject" in triple and "subject_label" in triple:
                    subjects[triple["subject"]] = triple["subject_label"]
            
            # For each subject, try to find matching ontology entities
            for subject_uri, subject_label in subjects.items():
                # Find matches in ontology entities
                matches = []
                
                for entity_type, entities in entities_data["entities"].items():
                    for entity in entities:
                        entity_label = entity.get("label", "")
                        if entity_label.lower() == subject_label.lower():
                            # Exact match by label
                            matches.append((entity, "exact", 0.95))
                        elif entity_label.lower() in subject_label.lower() or subject_label.lower() in entity_label.lower():
                            # Partial match
                            matches.append((entity, "partial", 0.75))
                
                # Sort matches by confidence
                matches.sort(key=lambda m: m[2], reverse=True)
                
                # Add relationship triple for top match if available
                if matches:
                    top_match = matches[0][0]
                    match_uri = top_match.get("uri", "")
                    match_label = top_match.get("label", "")
                    
                    if match_uri:
                        # Add equivalence or similarity relationship
                        relation_triple = {
                            "subject": subject_uri,
                            "predicate": "http://proethica.org/ontology/mappedToEntity",
                            "object": match_uri,
                            "subject_label": subject_label,
                            "predicate_label": "mapped to entity",
                            "object_label": match_label
                        }
                        all_triples.append(relation_triple)
            
            # Update the result
            triples_result["triples"] = all_triples
            triples_result["triple_count"] = len(all_triples)
            
            return triples_result
        except Exception as e:
            logger.warning(f"Error enhancing triples with ontology relationships: {str(e)}")
            return triples_result
