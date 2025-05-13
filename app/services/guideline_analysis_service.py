"""
Service for analyzing guidelines and extracting ontology concepts.
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
import logging

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
        Extract concepts from guideline content.
        
        Args:
            content: The text content of the guideline document
            ontology_source: Optional ontology source identifier to give context for extraction
            
        Returns:
            Dict containing the extracted concepts or error information
        """
        try:
            logger.info(f"Extracting concepts from guideline content with ontology source: {ontology_source}")
            
            # Get relevant ontology terms if an ontology source is provided
            ontology_context = ""
            entity_names = []
            
            if ontology_source:
                try:
                    # Get ontology entities from MCP service
                    entities_data = self.mcp_client.get_ontology_entities(ontology_source)
                    
                    # Format entity information as context
                    if entities_data and "entities" in entities_data:
                        for category, entities in entities_data["entities"].items():
                            if entities:
                                entity_names.extend([e.get("label") for e in entities if e.get("label")])
                                
                        if entity_names:
                            ontology_context = f"The following are ethical and engineering concepts from the ontology: {', '.join(entity_names)}.\n\n"
                except Exception as e:
                    logger.warning(f"Error getting ontology entities for concept extraction: {str(e)}")
            
            # Prepare input for the LLM
            llm_client = get_llm_client()
            system_prompt = """
            You are an expert in ethical engineering and ontology analysis. Your task is to extract key ethical concepts
            from engineering guidelines and standards. Focus on identifying:
            
            1. Ethical principles (e.g., honesty, integrity, responsibility)
            2. Professional obligations (e.g., public safety, confidentiality)
            3. Values (e.g., transparency, fairness, sustainability)
            4. Key engineering concepts (e.g., safety factors, risk assessment)
            5. Ethical considerations (e.g., conflicts of interest, intellectual property)
            
            For each concept, provide:
            - A label (short name for the concept)
            - A description (brief explanation of what it means in this context)
            - Type (principle, obligation, value, concept, consideration)
            
            Format your output as a JSON list of concept objects.
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
                    "type": "principle|obligation|value|concept|consideration",
                    "confidence": 0.9  # A number between 0-1 indicating how clearly this concept appears in the text
                }}
            ]
            ```
            
            Only include concepts that are directly referenced or implied in the guidelines. Focus on quality over quantity.
            """
            
            # Get response from LLM
            response = llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="gpt-4-turbo" if "gpt-4" in llm_client.available_models else "claude-3-haiku-20240307",
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2
            )
            
            # Extract JSON from the response
            try:
                response_text = response.choices[0].message.content
                response_json = json.loads(response_text)
                
                # Check if response has concepts key or is a direct array
                if isinstance(response_json, dict) and "concepts" in response_json:
                    concepts = response_json["concepts"]
                elif isinstance(response_json, list):
                    concepts = response_json
                else:
                    # Try to find a JSON array in the response
                    concepts = []
                    import re
                    json_match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
                    if json_match:
                        try:
                            concepts = json.loads(json_match.group(0))
                        except:
                            logger.error("Failed to parse JSON array from LLM response")
                
                # Validate concepts format
                validated_concepts = []
                for concept in concepts:
                    if isinstance(concept, dict) and "label" in concept and "description" in concept:
                        # Ensure type defaults to "concept" if missing
                        if "type" not in concept:
                            concept["type"] = "concept"
                        # Ensure confidence defaults to 0.8 if missing
                        if "confidence" not in concept:
                            concept["confidence"] = 0.8
                        validated_concepts.append(concept)
                
                logger.info(f"Successfully extracted {len(validated_concepts)} concepts from guideline content")
                return {"concepts": validated_concepts}
            
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from LLM response")
                return {"error": "Failed to parse concept data from AI response", "concepts": []}
                
        except Exception as e:
            logger.exception(f"Error extracting concepts from guideline: {str(e)}")
            return {"error": str(e), "concepts": []}
    
    def match_concepts(self, concepts: List[Dict[str, Any]], ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Match extracted concepts to ontology entities.
        
        Args:
            concepts: List of concept dictionaries extracted from the guideline
            ontology_source: Optional ontology source identifier for matching
            
        Returns:
            Dict containing matched entities and confidence scores
        """
        try:
            logger.info(f"Matching {len(concepts)} concepts to ontology entities")
            
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
            entities_json = json.dumps(all_entities, indent=2)
            
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
            response = llm_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model="gpt-4-turbo" if "gpt-4" in llm_client.available_models else "claude-3-haiku-20240307",
                response_format={"type": "json_object"},
                max_tokens=4000,
                temperature=0.2
            )
            
            # Extract matches from response
            try:
                response_text = response.choices[0].message.content
                matches = json.loads(response_text)
                
                logger.info(f"Successfully matched concepts to ontology entities: {len(matches)} concept mappings")
                return {"matches": matches}
            
            except json.JSONDecodeError:
                logger.error("Failed to parse JSON from LLM response for concept matching")
                return {"matches": {}, "error": "Failed to parse entity matches from AI response"}
                
        except Exception as e:
            logger.exception(f"Error matching concepts to ontology entities: {str(e)}")
            return {"matches": {}, "error": str(e)}
    
    def generate_triples(self, 
                         concepts: List[Dict[str, Any]], 
                         selected_indices: List[int],
                         ontology_source: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate RDF triples for selected concepts.
        
        Args:
            concepts: List of all extracted concepts
            selected_indices: Indices of concepts that the user selected
            ontology_source: Optional ontology source identifier for context
            
        Returns:
            Dict containing generated triples
        """
        try:
            logger.info(f"Generating triples for {len(selected_indices)} selected concepts")
            
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
                base_uri = "http://proethica.ai/engineering-ethics/concept/"
                concept_uri = f"{base_uri}{concept_label.lower().replace(' ', '-')}"
                
                # Basic type triple
                type_triple = {
                    "subject": concept_uri,
                    "subject_label": concept_label,
                    "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                    "predicate_label": "type",
                    "object": f"http://proethica.ai/engineering-ethics/{concept_type.lower()}",
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
            
            logger.info(f"Generated {len(all_triples)} triples for {len(selected_concepts)} concepts")
            return {"triples": all_triples, "triple_count": len(all_triples)}
                
        except Exception as e:
            logger.exception(f"Error generating triples for concepts: {str(e)}")
            return {"error": str(e), "triples": [], "triple_count": 0}
