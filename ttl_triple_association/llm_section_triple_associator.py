#!/usr/bin/env python3
"""
LLMSectionTripleAssociator - Associates document sections with ontology concepts using LLM.

This module implements an LLM-based approach to identify relevant ontology concepts
for document sections, combining vector similarity with term overlap, structural
relevance, and LLM-based semantic analysis.
"""

import logging
import re
import json
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import Counter
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
import nltk

from app.utils.llm_utils import get_llm_client
from app.utils.nltk_verification import verify_nltk_resources

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMSectionTripleAssociator:
    """
    Associates document sections with relevant ontology concepts using LLM.
    
    This class uses a multi-metric approach combining:
    1. Term overlap between section and concept
    2. Structural relevance based on section type and concept type
    3. LLM-based semantic analysis
    4. Optional vector similarity if embeddings are available
    """
    
    def __init__(self, ontology_loader, embedding_service=None, max_matches=10):
        """
        Initialize the associator with components and parameters.
        
        Args:
            ontology_loader: Loaded OntologyTripleLoader instance
            embedding_service: Optional EmbeddingService instance
            max_matches: Maximum number of matches to return per section
        """
        self.ontology_loader = ontology_loader
        self.embedding_service = embedding_service
        self.max_matches = max_matches
        
        # Ensure ontology is loaded
        if not hasattr(self.ontology_loader, 'concepts') or not self.ontology_loader.concepts:
            logger.info("Ontology not loaded, loading now...")
            self.ontology_loader.load()
            
        # Initialize NLTK resources if embedding_service is available
        if self.embedding_service:
            try:
                # Ensure NLTK resources are available
                verify_nltk_resources(['punkt', 'stopwords'])
                self.stop_words = set(stopwords.words('english'))
            except Exception as e:
                logger.warning(f"Error initializing NLTK resources: {str(e)}")
                # Fallback stopwords if NLTK fails
                self.stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", 
                                 "with", "by", "is", "are", "was", "were", "be", "been", "being", 
                                 "have", "has", "had", "do", "does", "did", "of", "this", "that"}
        else:
            # Fallback stopwords if embedding_service not available
            self.stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", 
                             "with", "by", "is", "are", "was", "were", "be", "been", "being", 
                             "have", "has", "had", "do", "does", "did", "of", "this", "that"}
    
    def associate_section(self, section_content: str, 
                         section_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Associate a section with relevant ontology concepts using LLM.
        
        Args:
            section_content: Text content of the section
            section_metadata: Metadata about the section including:
                - section_type: Type of section (facts, discussion, etc.)
                - title: Section title (optional)
                - section_id: ID of the section
                - embedding: Vector embedding of the section (optional)
                
        Returns:
            List of match dictionaries with scores and metadata
        """
        logger.info(f"Processing section with LLM associator: {section_metadata.get('section_id', 'Unknown ID')}")
        
        # Get all concepts from the ontology
        concepts = self.ontology_loader.get_all_concepts()
        
        if not concepts:
            logger.warning("No concepts available in ontology")
            return []
            
        # Filter concepts based on priority - start with role and principle concepts
        role_concepts = self.ontology_loader.get_role_concepts()
        role_related_concepts = self.ontology_loader.get_role_related_concepts()
        principle_concepts = self.ontology_loader.get_principle_concepts()
        
        # Combine prioritized concepts
        priority_concepts = {}
        priority_concepts.update(role_concepts)
        priority_concepts.update(role_related_concepts)
        priority_concepts.update(principle_concepts)
        
        # If we have too many concepts, limit to priority ones plus a sample of others
        if len(concepts) > 30:
            # Start with priority concepts
            filtered_concepts = dict(priority_concepts)
            
            # Add some non-priority concepts if needed
            remaining_slots = 30 - len(filtered_concepts)
            if remaining_slots > 0:
                other_concepts = {uri: concept for uri, concept in concepts.items() 
                                 if uri not in filtered_concepts}
                
                # Get a sample of other concepts
                import random
                sample_uris = random.sample(list(other_concepts.keys()), 
                                           min(remaining_slots, len(other_concepts)))
                
                # Add sampled concepts
                for uri in sample_uris:
                    filtered_concepts[uri] = other_concepts[uri]
                    
            concepts_to_process = filtered_concepts
            logger.info(f"Limited to {len(concepts_to_process)} concepts ({len(priority_concepts)} priority, {len(concepts_to_process) - len(priority_concepts)} other)")
        else:
            concepts_to_process = concepts
        
        # Process each concept with multi-metric approach
        matches = []
        
        for concept_uri, concept in concepts_to_process.items():
            # Calculate base metrics
            metrics = self._calculate_base_metrics(section_content, section_metadata, concept)
            
            # If base metrics show promise, perform deeper LLM analysis
            if metrics['combined_score'] > 0.3:
                # Get LLM analysis
                llm_analysis = self._analyze_relevance_with_llm(section_content, section_metadata, concept)
                
                # Calculate final relevance with full reasoning
                final_result = self._calculate_final_relevance(metrics, llm_analysis)
                
                # If final score is high enough, add to matches
                if final_result['score'] > 0.5:
                    match = {
                        "concept_uri": concept_uri,
                        "concept_label": concept.get("label", ""),
                        "concept_description": concept.get("description", ""),
                        "vector_similarity": metrics.get('vector_similarity', 0.0),
                        "term_match_score": metrics.get('term_match_score', 0.0),
                        "context_score": metrics.get('structural_relevance', 0.0),
                        "combined_score": final_result['score'],
                        "match_type": "llm_semantic",
                        "category": concept.get("categories", [""])[0] if concept.get("categories") else "",
                        "metadata": {
                            "explanation": final_result['llm_reasoning'],
                            "patterns": final_result['llm_patterns'],
                            "shared_terms": metrics.get('shared_terms', []),
                            "relationship": final_result['relationship']
                        }
                    }
                    
                    matches.append(match)
        
        # Sort by combined score (descending) and limit to max_matches
        matches.sort(key=lambda x: x["combined_score"], reverse=True)
        top_matches = matches[:self.max_matches]
        
        logger.info(f"Found {len(top_matches)} relevant concepts using LLM associator")
        return top_matches
    
    def _calculate_base_metrics(self, section_content: str, 
                               section_metadata: Dict[str, Any],
                               concept: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate base metrics for relevance between section and concept.
        
        Args:
            section_content: Content of the section
            section_metadata: Metadata about the section
            concept: Concept dictionary
            
        Returns:
            Dictionary with base metrics
        """
        # Convert concept to text for comparison
        concept_text = self._concept_to_text(concept)
        
        # Initialize metrics
        metrics = {
            'vector_similarity': 0.0,
            'term_match_score': 0.0,
            'shared_terms': [],
            'structural_relevance': 0.0
        }
        
        # 1. Calculate vector similarity if embeddings are available
        if self.embedding_service and 'embedding' in section_metadata:
            section_embedding = section_metadata['embedding']
            
            # Generate embedding for concept text
            concept_embedding = self.embedding_service.generate_embedding(concept_text)
            
            if concept_embedding is not None and section_embedding is not None:
                # Calculate similarity
                metrics['vector_similarity'] = self.embedding_service.compute_similarity(
                    section_embedding, concept_embedding
                )
        
        # 2. Calculate term overlap
        metrics['term_match_score'], metrics['shared_terms'] = self._calculate_term_overlap(
            section_content, concept_text
        )
        
        # 3. Calculate structural relevance
        metrics['structural_relevance'] = self._get_structural_relevance(
            section_metadata.get('section_type', ''),
            concept.get('entity_type', 'concept')
        )
        
        # Calculate preliminary combined score
        metrics['combined_score'] = (
            0.40 * metrics['term_match_score'] + 
            0.20 * metrics['structural_relevance'] +
            0.40 * metrics['vector_similarity']
        )
        
        return metrics
    
    def _concept_to_text(self, concept: Dict[str, Any]) -> str:
        """
        Convert a concept to text for comparison.
        
        Args:
            concept: Concept dictionary
            
        Returns:
            Text representation of the concept
        """
        parts = []
        
        # Add label
        if concept.get("label"):
            parts.append(concept["label"])
            
        # Add description
        if concept.get("description"):
            parts.append(concept["description"])
            
        # Add matching terms
        if concept.get("matching_terms"):
            parts.append("Keywords: " + ", ".join(concept["matching_terms"]))
            
        # Add categories
        if concept.get("categories"):
            parts.append("Categories: " + ", ".join(concept["categories"]))
            
        return " ".join(parts)
    
    def _calculate_term_overlap(self, section_content: str, concept_text: str) -> Tuple[float, List[str]]:
        """
        Calculate term overlap between section content and concept text.
        
        Args:
            section_content: Content of the document section
            concept_text: Text representation of the concept
            
        Returns:
            Tuple of (overlap score, list of shared terms)
        """
        try:
            # Normalize and tokenize section content and concept text
            section_tokens = word_tokenize(section_content.lower())
            concept_tokens = word_tokenize(concept_text.lower())
            
            # Remove stopwords and short words
            section_terms = {w for w in section_tokens if w not in self.stop_words and len(w) > 2}
            concept_terms = {w for w in concept_tokens if w not in self.stop_words and len(w) > 2}
            
            # Find intersection and calculate Jaccard similarity
            intersection = section_terms.intersection(concept_terms)
            union = section_terms.union(concept_terms)
            
            # Calculate Jaccard similarity
            if union:
                jaccard = len(intersection) / len(union)
            else:
                jaccard = 0.0
                
            # Return the score and shared terms
            return jaccard, list(intersection)
            
        except Exception as e:
            logger.exception(f"Error calculating term overlap: {str(e)}")
            return 0.0, []
    
    def _get_structural_relevance(self, section_type: str, entity_type: str) -> float:
        """
        Calculate structural relevance based on section type and entity type.
        
        Args:
            section_type: Type of the document section
            entity_type: Type of the entity in the concept
            
        Returns:
            float: Structural relevance score (0-1)
        """
        # Define relevance matrix for different combinations
        relevance_matrix = {
            'facts': {
                'condition': 0.9,
                'resource': 0.7,
                'action': 0.6,
                'role': 0.8,
                'concept': 0.6,
                'principle': 0.5
            },
            'discussion': {
                'condition': 0.7,
                'resource': 0.5,
                'action': 0.8,
                'role': 0.7,
                'concept': 0.6,
                'principle': 0.8
            },
            'conclusion': {
                'condition': 0.6,
                'resource': 0.4,
                'action': 0.7,
                'role': 0.6,
                'concept': 0.5,
                'principle': 0.9
            },
            'question': {
                'condition': 0.8,
                'resource': 0.6,
                'action': 0.7,
                'role': 0.6,
                'concept': 0.5,
                'principle': 0.7
            }
        }
        
        # Normalize section_type and entity_type
        normalized_section_type = section_type.lower().split('_')[0]  # handle types like "discussion_1"
        normalized_entity_type = entity_type.lower()
        
        # Get relevance score from matrix or use default
        if normalized_section_type in relevance_matrix:
            if normalized_entity_type in relevance_matrix[normalized_section_type]:
                return relevance_matrix[normalized_section_type][normalized_entity_type]
        
        # Default relevance score
        return 0.5
    
    def _analyze_relevance_with_llm(self, section_content: str, 
                                  section_metadata: Dict[str, Any],
                                  concept: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use LLM to analyze relevance between section and concept.
        
        Args:
            section_content: Content of the document section
            section_metadata: Metadata about the section
            concept: Concept dictionary
            
        Returns:
            Dictionary with LLM analysis results
        """
        try:
            # Get the LLM client
            client = get_llm_client()
            if not client:
                logger.warning("LLM client unavailable for concept relevance analysis")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': "LLM analysis unavailable",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM unavailable
                }
            
            # Prepare section content (limit length to avoid token limits)
            max_content_length = 1000
            if len(section_content) > max_content_length:
                section_content = section_content[:max_content_length] + "..."
            
            # Convert concept to text
            concept_text = self._concept_to_text(concept)
            
            # Construct the prompt
            prompt = f"""
            Analyze the relevance between this document section and ontology concept:
            
            DOCUMENT SECTION TYPE: {section_metadata.get('section_type', 'Unknown')}
            DOCUMENT SECTION CONTENT:
            {section_content}
            
            ONTOLOGY CONCEPT:
            {concept_text}
            
            Is there a clear semantic relationship between the section content and the ontology concept? Provide:
            1. A yes/no determination if there's a meaningful relationship
            2. Brief reasoning for your assessment (1-2 sentences)
            3. Specific patterns or key terms that connect them, if any

            Format your response as JSON:
            {{
              "is_relevant": true/false,
              "reasoning": "Brief explanation of the relationship",
              "patterns_identified": ["pattern1", "pattern2"]
            }}
            """
            
            # Send to LLM based on API version
            result = ""
            try:
                # If new API (v2)
                if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                    response = client.chat.completions.create(
                        model=client.available_models[0],  # Use latest available model
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,  # Low temperature for more consistent results
                        max_tokens=500
                    )
                    result = response.choices[0].message.content
                    
                # If messages API (v1.5)
                elif hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                    response = client.messages.create(
                        model=client.available_models[0],
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.1,
                        max_tokens=500
                    )
                    result = response.content[0].text
                    
                # If old API (v1)
                else:
                    response = client.completion(
                        prompt=f"Human: {prompt}\n\nAssistant:",
                        model=client.available_models[0],
                        temperature=0.1,
                        max_tokens_to_sample=500
                    )
                    result = response.completion
            except Exception as api_error:
                logger.warning(f"Error using LLM API: {str(api_error)}")
                return {
                    'llm_is_relevant': None,
                    'llm_reasoning': f"LLM API error: {str(api_error)}",
                    'llm_patterns': [],
                    'agreement_score': 0.5  # Neutral score if LLM fails
                }
                
            # Parse JSON response
            try:
                # Clean up the result to ensure it's valid JSON
                # Sometimes LLM responses include markdown code blocks or additional text
                json_start = result.find('{')
                json_end = result.rfind('}')
                if json_start >= 0 and json_end >= 0:
                    json_str = result[json_start:json_end+1]
                    analysis = json.loads(json_str)
                else:
                    # If no JSON found, create default response
                    analysis = {
                        'is_relevant': False,
                        'reasoning': "Could not reliably determine relevance",
                        'patterns_identified': []
                    }
            except json.JSONDecodeError:
                # If JSON parsing fails, create a default response
                logger.warning(f"Failed to parse LLM response as JSON: {result}")
                analysis = {
                    'is_relevant': False,
                    'reasoning': "Could not parse LLM response",
                    'patterns_identified': []
                }
            
            # Calculate agreement score - how well does the LLM assessment match the base metrics?
            # We'll use a placeholder value here as we don't have a single combined score yet
            llm_score = 1.0 if analysis.get('is_relevant', False) else 0.0
            agreement_score = 0.5  # Neutral value for now
            
            return {
                'llm_is_relevant': analysis.get('is_relevant', False),
                'llm_reasoning': analysis.get('reasoning', ''),
                'llm_patterns': analysis.get('patterns_identified', []),
                'agreement_score': agreement_score
            }
            
        except Exception as e:
            logger.exception(f"Error in LLM analysis: {str(e)}")
            return {
                'llm_is_relevant': False,
                'llm_reasoning': f"Error in LLM analysis: {str(e)}",
                'llm_patterns': [],
                'agreement_score': 0.5  # Neutral score if error
            }
    
    def _calculate_final_relevance(self, base_metrics: Dict[str, Any], 
                                 llm_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate final relevance score with comprehensive reasoning chain.
        
        Args:
            base_metrics: Initial metrics from _calculate_base_metrics
            llm_analysis: Results from LLM analysis
            
        Returns:
            Dictionary with final relevance metrics and reasoning
        """
        try:
            # Extract base metrics
            vector_similarity = base_metrics.get('vector_similarity', 0.0)
            term_match_score = base_metrics.get('term_match_score', 0.0)
            structural_relevance = base_metrics.get('structural_relevance', 0.0)
            
            # Extract LLM metrics
            llm_is_relevant = llm_analysis.get('llm_is_relevant', False)
            
            # Convert LLM boolean to score
            llm_relevance_score = 1.0 if llm_is_relevant else 0.0
            
            # Calculate weighted final score
            # Weight components based on confidence and reliability
            final_score = (
                0.25 * vector_similarity +
                0.20 * term_match_score +
                0.10 * structural_relevance +
                0.45 * llm_relevance_score  # LLM gets highest weight
            )
            
            # Determine relationship type based on final score
            relationship = "related_to"  # Default
            
            # If score is very high, suggest stronger relationship
            if final_score > 0.8:
                relationship = "strongly_related_to"
            elif final_score > 0.95:
                relationship = "directly_implements"
            
            # Calculate explanatory string for the score calculation
            calculation = (
                f"Final score {final_score:.2f} calculated from: "
                f"Vector similarity ({vector_similarity:.2f} × 0.25) + "
                f"Term overlap ({term_match_score:.2f} × 0.20) + "
                f"Structural relevance ({structural_relevance:.2f} × 0.10) + "
                f"LLM assessment ({llm_relevance_score:.1f} × 0.45)"
            )
            
            # Return complete result
            return {
                'score': min(1.0, max(0.0, final_score)),  # Clamp to 0-1 range
                'relationship': relationship,
                'vector_similarity': vector_similarity,
                'term_overlap': term_match_score,
                'structural_relevance': structural_relevance,
                'llm_reasoning': llm_analysis.get('llm_reasoning', ''),
                'llm_patterns': llm_analysis.get('llm_patterns', []),
                'calculation': calculation
            }
            
        except Exception as e:
            logger.exception(f"Error calculating final relevance: {str(e)}")
            # Return default result with error information
            return {
                'score': 0.0,
                'relationship': 'related_to',
                'vector_similarity': base_metrics.get('vector_similarity', 0.0),
                'term_overlap': base_metrics.get('term_match_score', 0.0),
                'structural_relevance': base_metrics.get('structural_relevance', 0.0),
                'llm_reasoning': f"Error calculating final relevance: {str(e)}",
                'llm_patterns': [],
                'calculation': f"Calculation failed: {str(e)}"
            }
