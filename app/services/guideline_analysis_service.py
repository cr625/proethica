"""
Service for analyzing guidelines and extracting ontological concepts.
"""

import os
import json
import threading
import time
from typing import Dict, Any, List, Tuple, Set, Optional
from flask import current_app
import requests

from app import db
from app.models.document import Document
from app.models.triple import Triple
from app.services.ontology_entity_service import OntologyEntityService
from app.services.mcp_client import MCPClient
from app.utils.llm_utils import get_llm_client

# Thread-local storage for cached analysis results
_local_storage = threading.local()

class GuidelineAnalysisService:
    """Service for analyzing guidelines and extracting ontological concepts."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get the singleton instance of GuidelineAnalysisService."""
        if cls._instance is None:
            cls._instance = GuidelineAnalysisService()
        return cls._instance
    
    def __init__(self):
        """Initialize the service."""
        self.ontology_entity_service = OntologyEntityService.get_instance()
        self.mcp_client = MCPClient.get_instance()
        self.cache_timeout = 600  # 10 minutes
        self.cache = {}
        self.cache_timestamps = {}
    
    def analyze_guideline(self, document_id: int) -> Dict[str, Any]:
        """
        Analyze a guideline document and extract ontology concepts.
        
        Args:
            document_id: The ID of the document to analyze
            
        Returns:
            A dictionary containing the analysis results
        """
        # Check cache first
        cache_key = f"analyze_guideline_{document_id}"
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            return cached_result
        
        try:
            # Get the document
            document = Document.query.get(document_id)
            if not document:
                return {"success": False, "error": f"Document with ID {document_id} not found"}
            
            # Get the document's content
            content = document.content
            if not content:
                return {"success": False, "error": "Document has no content"}
            
            # Get the world's ontology entities
            world = document.world
            entities_result = self.ontology_entity_service.get_entities_for_world(world)
            if not entities_result or "entities" not in entities_result:
                return {"success": False, "error": "Failed to get ontology entities"}
            
            # Extract concepts using LLM
            extracted_concepts = self._extract_concepts_with_llm(content, entities_result["entities"])
            
            result = {
                "success": True,
                "document_id": document_id,
                "extracted_concepts": extracted_concepts,
                "matched_entities": self._match_concepts_to_ontology(extracted_concepts, entities_result["entities"])
            }
            
            # Cache the result
            self._add_to_cache(cache_key, result)
            
            return result
        except Exception as e:
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    def create_triples_for_concepts(self, document_id: int, concepts: List[Dict], 
                                  selected_indices: List[int]) -> List[Triple]:
        """
        Create RDF triples for selected concepts extracted from guidelines.
        
        Args:
            document_id: The ID of the document
            concepts: List of extracted concepts
            selected_indices: List of indices of selected concepts
            
        Returns:
            List of created Triple objects
        """
        document = Document.query.get(document_id)
        if not document:
            return []
            
        world_id = document.world_id
        created_triples = []
        
        # Select only the concepts that were chosen by the user
        selected_concepts = [concepts[idx] for idx in selected_indices if idx < len(concepts)]
        
        for concept in selected_concepts:
            # Create a triple for each concept
            triple = self._create_triple_for_concept(concept, document_id, world_id)
            if triple:
                created_triples.append(triple)
                
            # If the concept has matched entities, create relationship triples
            if "matched_entities" in concept and concept["matched_entities"]:
                for entity in concept["matched_entities"]:
                    relation_triple = self._create_relation_triple(concept, entity, document_id, world_id)
                    if relation_triple:
                        created_triples.append(relation_triple)
        
        # Commit all triples to the database
        db.session.commit()
        return created_triples
    
    def _extract_concepts_with_llm(self, content: str, ontology_entities: Dict) -> List[Dict]:
        """
        Extract ontological concepts from guideline content using LLM.
        
        Args:
            content: The guideline content
            ontology_entities: Dictionary of ontology entities
            
        Returns:
            List of extracted concepts with metadata
        """
        llm = get_llm_client()
        max_content_length = 15000  # Limit content length to avoid token limits
        
        # Truncate content if needed
        truncated_content = content[:max_content_length]
        if len(content) > max_content_length:
            truncated_content += "... [content truncated for processing]"
        
        # Prepare a summary of ontology entities for context
        entity_summary = self._prepare_entity_summary(ontology_entities)
            
        # Prepare the prompt
        prompt = f"""
        You are an expert in ethics and ontology analysis. Your task is to analyze the following ethical guidelines 
        and identify key concepts that can be represented in our ontology.

        The guideline content is:
        ```
        {truncated_content}
        ```
        
        The engineering ethics ontology includes the following entity types:
        {entity_summary}
        
        Extract key concepts from the guidelines and categorize them according to the ontology structure.
        For each concept, provide:
        
        1. concept_name: A concise name for the concept
        2. concept_type: The type of concept (principle, obligation, role, action, resource, or condition)
        3. description: A clear description of the concept
        4. guideline_text: The exact text from the guidelines that relates to this concept
        5. relevance: Why this concept is important for ethical engineering
        
        IMPORTANT: 
        1. The concept_type MUST be one of: principle, obligation, role, action, resource, or condition (all lowercase).
        2. Respond ONLY with a JSON array, with NO additional text before or after.
        
        Return the results STRICTLY as a JSON array matching this structure:
        [
          {{
            "concept_name": "string",
            "concept_type": "string",
            "description": "string",
            "guideline_text": "string",
            "relevance": "string"
          }}
        ]
        
        Identify at least 3 and up to 15 distinct concepts. Focus on concepts that are clearly represented in the text.
        
        DO NOT include any explanatory text or headings - respond ONLY with the JSON array.
        """
        
        try:
            # Check which LLM we're using (Anthropic or OpenAI)
            if hasattr(llm, 'messages'):  # Anthropic
                try:
                    # Try with modern Claude models using messages API
                    model_names = [
                        "claude-3-7-sonnet-latest",  # Latest model version
                        "claude-3-7-sonnet-20250219", # Specific version
                        "claude-3-5-sonnet-20241022",
                        "claude-3-sonnet-20240229",
                        "claude-3-opus-20240229", 
                        "claude-3-haiku-20240307",
                        "claude-3-sonnet",
                        "claude-3-opus",
                        "claude-3-haiku"
                    ]
                    
                    prompt_with_json_hint = prompt + "\n\nPlease respond in JSON format with an array of concepts."
                    result_text = None
                    last_error = None
                    
                    # Try each model until one works
                    for model_name in model_names:
                        try:
                            print(f"Trying Anthropic model: {model_name}")
                            response = llm.messages.create(
                                model=model_name,
                                messages=[{"role": "user", "content": prompt_with_json_hint}],
                                temperature=0.2,
                                max_tokens=4000
                            )
                            result_text = response.content[0].text
                            print(f"Successfully used Anthropic model: {model_name}")
                            break
                        except Exception as e:
                            last_error = e
                            print(f"Error with Anthropic model {model_name}: {str(e)}")
                            continue
                    
                    # If all modern models failed, try OpenAI
                    if not result_text:
                        # Let's try OpenAI as a fallback
                        print("All Anthropic models failed, trying OpenAI fallback")
                        try:
                            import openai
                            api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
                            if api_key:
                                client = openai.OpenAI(api_key=api_key)
                                response = client.chat.completions.create(
                                    model="gpt-3.5-turbo",
                                    messages=[{"role": "user", "content": prompt}],
                                    temperature=0.2,
                                    max_tokens=4000
                                )
                                result_text = response.choices[0].message.content
                                print("Successfully used OpenAI fallback")
                            else:
                                raise ValueError("No OpenAI API key available")
                        except Exception as e3:
                            print(f"OpenAI fallback also failed: {str(e3)}")
                            # Return empty result that will be handled gracefully
                            print(f"All LLM API attempts failed. Last error: {str(last_error)}")
                            return [
                                {
                                    "concept_name": "API Compatibility Error",
                                    "concept_type": "principle",
                                    "description": f"Failed to access LLM API: {str(last_error)}",
                                    "guideline_text": "",
                                    "confidence": 0.1
                                }
                            ]
                except Exception as e_outer:
                    print(f"Outer Anthropic API error: {str(e_outer)}")
                    # Return error in a structured way
                    return [
                        {
                            "concept_name": "API Error",
                            "concept_type": "principle",
                            "description": f"Anthropic API Error: {str(e_outer)}",
                            "guideline_text": "",
                            "confidence": 0.1
                        }
                    ]
                    
            elif hasattr(llm, 'chat'):  # OpenAI
                response = llm.chat.completions.create(
                    model=current_app.config.get('LLM_MODEL', 'gpt-4'),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=4000,
                    response_format={"type": "json_object"}
                )
                result_text = response.choices[0].message.content
            else:
                raise ValueError("Unsupported LLM client type")
            
            # Try to extract JSON from the text response
            result_text = result_text.strip()
            # If the response starts with ```json or similar, extract just the JSON part
            if "```" in result_text:
                import re
                json_content = re.search(r'```(?:json)?(.*?)```', result_text, re.DOTALL)
                if json_content:
                    result_text = json_content.group(1).strip()
            
            try:
                # Extract the concepts from the response
                result = json.loads(result_text)
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract structured data manually
                print("JSON parsing failed, trying to extract structured data manually")
                concepts = []
                # Return minimal data with error info
                return [
                    {
                        "concept_name": "Error in JSON Parsing",
                        "concept_type": "principle",
                        "description": "Failed to parse LLM response as JSON. Please check API version compatibility.",
                        "guideline_text": result_text[:100] + "...",
                        "confidence": 0.1
                    }
                ]
            # Extract concepts - be case insensitive with keys
            concepts = []
            if isinstance(result, list):
                concepts = result
            elif isinstance(result, dict):
                # Check for 'concepts' key with case insensitivity
                for key in result:
                    if key.lower() == 'concepts':
                        concepts = result[key]
                        break
                
                # If no concepts found yet, try to find any array
                if not concepts:
                    for key, value in result.items():
                        if isinstance(value, list) and len(value) > 0:
                            concepts = value
                            break
            
            # Log what we found for debugging
            print(f"JSON parsing result: found {len(concepts)} concepts")
            
            # Add confidence scores based on text overlap
            for concept in concepts:
                if "guideline_text" in concept and concept["guideline_text"]:
                    # Simple confidence score based on text presence
                    if concept["guideline_text"] in content:
                        concept["confidence"] = 0.95
                    else:
                        # Try to find a close match
                        confidence = self._calculate_text_similarity(concept["guideline_text"], content)
                        concept["confidence"] = max(0.5, confidence)
                else:
                    concept["confidence"] = 0.7
            
            return concepts
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Error in extracting concepts with LLM: {e}")
            # Return a basic placeholder if LLM extraction fails
            return [
                {
                    "concept_name": "Error in Concept Extraction",
                    "concept_type": "principle",
                    "description": f"Failed to extract concepts: {str(e)}",
                    "guideline_text": truncated_content[:200] + "...",
                    "confidence": 0.1
                }
            ]
    
    def _prepare_entity_summary(self, ontology_entities: Dict) -> str:
        """Prepare a summary of ontology entities for the LLM prompt."""
        summary_parts = []
        
        entity_types = {
            "principles": "Ethical principles that guide decision-making",
            "obligations": "Duties or responsibilities that must be fulfilled",
            "roles": "Professional roles or positions with specific responsibilities",
            "actions": "Activities or decisions taken by agents",
            "resources": "Physical or information assets",
            "conditions": "Contextual factors or situations"
        }
        
        for entity_type, description in entity_types.items():
            if entity_type in ontology_entities:
                entities = ontology_entities[entity_type]
                entity_names = [e.get("label", "Unnamed entity") for e in entities[:5]]
                summary = f"- {entity_type.capitalize()}: {description}. Examples: {', '.join(entity_names)}"
                if len(entities) > 5:
                    summary += f" and {len(entities) - 5} more"
                summary_parts.append(summary)
        
        return "\n".join(summary_parts)
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """Calculate a simple similarity score between two text strings."""
        # This is a very basic similarity check
        text1_words = set(text1.lower().split())
        text2_words = set(text2.lower().split())
        
        if not text1_words or not text2_words:
            return 0.0
            
        common_words = text1_words.intersection(text2_words)
        return len(common_words) / len(text1_words)
    
    def _match_concepts_to_ontology(self, concepts: List[Dict], 
                                   ontology_entities: Dict) -> Dict[str, List]:
        """
        Match extracted concepts to existing ontology entities.
        
        Args:
            concepts: List of extracted concepts
            ontology_entities: Dictionary of ontology entities
            
        Returns:
            Dictionary mapping concept indices to matched entities
        """
        matches = {}
        
        # Create mappings for entity types to their plural forms
        type_mappings = {
            "principle": "principles",
            "obligation": "obligations",
            "role": "roles",
            "action": "actions",
            "resource": "resources",
            "condition": "conditions"
        }
        
        for i, concept in enumerate(concepts):
            concept_type = concept.get("concept_type", "")
            concept_name = concept.get("concept_name", "")
            concept_description = concept.get("description", "")
            
            # Get the plural form of the concept type
            entity_type_key = type_mappings.get(concept_type.lower(), None)
            if not entity_type_key or entity_type_key not in ontology_entities:
                continue
                
            # Get entities of this type
            entities = ontology_entities[entity_type_key]
            matched_entities = []
            
            # Find matching entities
            for entity in entities:
                # Calculate a match score based on label and description similarity
                label_similarity = self._calculate_text_similarity(concept_name, entity.get("label", ""))
                desc_similarity = self._calculate_text_similarity(
                    concept_description, entity.get("description", ""))
                
                # Weight label matches more highly than description matches
                match_score = (label_similarity * 0.7) + (desc_similarity * 0.3)
                
                # If good enough match, add to matched entities
                if match_score > 0.3:  # Threshold for considering a match
                    matched_entities.append({
                        "id": entity.get("id"),
                        "label": entity.get("label"),
                        "description": entity.get("description", ""),
                        "match_score": match_score
                    })
            
            # Sort by match score and keep top 3
            if matched_entities:
                matched_entities.sort(key=lambda x: x.get("match_score", 0), reverse=True)
                top_matches = matched_entities[:3]
                concept["matched_entities"] = top_matches
                matches[str(i)] = top_matches
        
        return matches
    
    def _create_triple_for_concept(self, concept: Dict, document_id: int, world_id: int) -> Optional[Triple]:
        """Create a new RDF triple for a concept."""
        try:
            # Create a unique identifier for this concept
            concept_name = concept.get("concept_name", "").strip()
            if not concept_name:
                return None
                
            concept_type = concept.get("concept_type", "").lower()
            if concept_type not in ["principle", "obligation", "role", "action", "resource", "condition"]:
                concept_type = "principle"  # Default to principle
            
            # Create an IRI for the concept
            concept_slug = concept_name.lower().replace(" ", "_")
            concept_iri = f"http://example.org/ethics/{concept_type}/{concept_slug}"
            
            # Create a new triple
            triple = Triple(
                subject=concept_iri,
                predicate="http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
                object=f"http://example.org/ethics/{concept_type.capitalize()}",
                subject_label=concept_name,
                object_label=f"{concept_type.capitalize()}",
                subject_type="IRI",
                object_type="IRI",
                predicate_label="is a",
                document_id=document_id,
                world_id=world_id,
                provenance=f"Extracted from guidelines document {document_id}"
            )
            
            db.session.add(triple)
            
            # Also create a triple for the description if available
            description = concept.get("description", "").strip()
            if description:
                description_triple = Triple(
                    subject=concept_iri,
                    predicate="http://www.w3.org/2000/01/rdf-schema#comment",
                    object=description,
                    subject_label=concept_name,
                    object_label=description[:50] + ("..." if len(description) > 50 else ""),
                    subject_type="IRI",
                    object_type="LITERAL",
                    predicate_label="description",
                    document_id=document_id,
                    world_id=world_id,
                    provenance=f"Extracted from guidelines document {document_id}"
                )
                db.session.add(description_triple)
            
            return triple
        except Exception as e:
            print(f"Error creating triple for concept: {e}")
            return None
    
    def _create_relation_triple(self, concept: Dict, entity: Dict, 
                               document_id: int, world_id: int) -> Optional[Triple]:
        """Create a relationship triple between a concept and an ontology entity."""
        try:
            concept_name = concept.get("concept_name", "").strip()
            concept_type = concept.get("concept_type", "").lower()
            if not concept_name or concept_type not in ["principle", "obligation", "role", "action", "resource", "condition"]:
                return None
                
            # Create IRIs
            concept_slug = concept_name.lower().replace(" ", "_")
            concept_iri = f"http://example.org/ethics/{concept_type}/{concept_slug}"
            
            entity_id = entity.get("id")
            if not entity_id:
                return None
                
            # Create a relation triple
            relation_triple = Triple(
                subject=concept_iri,
                predicate="http://example.org/ethics/relatedTo",
                object=entity_id,
                subject_label=concept_name,
                object_label=entity.get("label", "Unnamed entity"),
                subject_type="IRI",
                object_type="IRI",
                predicate_label="related to",
                document_id=document_id,
                world_id=world_id,
                provenance=f"Extracted from guidelines document {document_id}, matched with existing ontology"
            )
            
            db.session.add(relation_triple)
            return relation_triple
        except Exception as e:
            print(f"Error creating relation triple: {e}")
            return None
        
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get a value from the cache if it exists and is not expired."""
        if key in self.cache:
            timestamp = self.cache_timestamps.get(key)
            if timestamp and time.time() - timestamp < self.cache_timeout:
                return self.cache[key]
        return None
        
    def _add_to_cache(self, key: str, value: Any) -> None:
        """Add a value to the cache with the current timestamp."""
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
