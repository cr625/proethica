#!/usr/bin/env python3
"""
SectionTripleAssociator - Associates document sections with ontology concepts.

This module implements a two-phase matching algorithm to associate document 
sections with relevant ontology concepts, combining vector similarity with
semantic property matching and section context awareness.
"""

import logging
import re
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Set
from collections import Counter

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SectionTripleAssociator:
    """
    Associates document sections with relevant ontology concepts.
    
    This class handles the two-phase matching process:
    1. Coarse matching with vector similarity
    2. Fine-grained matching with semantic properties and section context
    """
    
    def __init__(self, ontology_loader, embedding_service, 
                similarity_threshold=0.6, max_matches=10):
        """
        Initialize the associator with components and parameters.
        
        Args:
            ontology_loader: Loaded OntologyTripleLoader instance
            embedding_service: EmbeddingService instance
            similarity_threshold: Minimum similarity score for matches (0-1)
            max_matches: Maximum number of matches to return per section
        """
        self.ontology_loader = ontology_loader
        self.embedding_service = embedding_service
        self.similarity_threshold = similarity_threshold
        self.max_matches = max_matches
        
        # Ensure ontology is loaded
        if not hasattr(self.ontology_loader, 'concepts') or not self.ontology_loader.concepts:
            logger.info("Ontology not loaded, loading now...")
            self.ontology_loader.load()
            
        # Generate concept embeddings
        logger.info("Generating concept embeddings...")
        self.concept_embeddings = self.ontology_loader.generate_concept_embeddings(embedding_service)
        logger.info(f"Generated embeddings for {len(self.concept_embeddings)} concepts")
        
    def associate_section(self, section_embedding: np.ndarray, 
                         section_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Associate a section with relevant ontology concepts.
        
        Args:
            section_embedding: Vector embedding of the section
            section_metadata: Metadata about the section including:
                - section_type: Type of section (facts, discussion, etc.)
                - content: Text content of the section
                - title: Section title (optional)
                
        Returns:
            List of match dictionaries with scores and metadata
        """
        if section_embedding is None:
            logger.warning("No embedding provided for section")
            return []
            
        # Phase 1: Coarse matching with vector similarity
        coarse_matches = self._perform_coarse_matching(section_embedding)
        
        if not coarse_matches:
            logger.info("No coarse matches found with similarity threshold")
            return []
            
        logger.info(f"Found {len(coarse_matches)} coarse matches above threshold {self.similarity_threshold}")
        
        # Phase 2: Fine-grained matching with semantic properties
        fine_matches = self._perform_fine_matching(coarse_matches, section_metadata)
        
        # Sort by combined score (descending) and limit to max_matches
        fine_matches.sort(key=lambda x: x["combined_score"], reverse=True)
        top_matches = fine_matches[:self.max_matches]
        
        logger.info(f"Returning {len(top_matches)} refined matches")
        return top_matches
        
    def _perform_coarse_matching(self, section_embedding: np.ndarray) -> List[Tuple[str, float]]:
        """
        First phase: Find candidate concepts using vector similarity.
        
        Args:
            section_embedding: Vector embedding of the section
            
        Returns:
            List of (concept_uri, similarity_score) tuples above threshold
        """
        matches = []
        
        # Prioritize role concepts first (high priority)
        role_concepts = self.ontology_loader.get_role_concepts()
        role_related_concepts = self.ontology_loader.get_role_related_concepts()
        principle_concepts = self.ontology_loader.get_principle_concepts()
        
        # Check role concepts first (high priority)
        for uri in role_concepts:
            if uri in self.concept_embeddings:
                similarity = self.embedding_service.compute_similarity(
                    section_embedding, self.concept_embeddings[uri]
                )
                
                if similarity >= self.similarity_threshold:
                    matches.append((uri, similarity))
                    
        # Then check role-related concepts (high priority)
        for uri in role_related_concepts:
            if uri in self.concept_embeddings and uri not in [m[0] for m in matches]:
                similarity = self.embedding_service.compute_similarity(
                    section_embedding, self.concept_embeddings[uri]
                )
                
                if similarity >= self.similarity_threshold:
                    matches.append((uri, similarity))
        
        # Then check principle concepts (medium priority)
        for uri in principle_concepts:
            if uri in self.concept_embeddings and uri not in [m[0] for m in matches]:
                similarity = self.embedding_service.compute_similarity(
                    section_embedding, self.concept_embeddings[uri]
                )
                
                if similarity >= self.similarity_threshold:
                    matches.append((uri, similarity))
                    
        # Finally check all other concepts
        checked_uris = set([m[0] for m in matches])
        for uri, embedding in self.concept_embeddings.items():
            if uri not in checked_uris:
                similarity = self.embedding_service.compute_similarity(
                    section_embedding, embedding
                )
                
                if similarity >= self.similarity_threshold:
                    matches.append((uri, similarity))
                    
        # Sort by similarity score (descending)
        matches.sort(key=lambda x: x[1], reverse=True)
        
        return matches
        
    def _perform_fine_matching(self, coarse_matches: List[Tuple[str, float]], 
                              section_metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Second phase: Refine matches using semantic properties and section context.
        
        Args:
            coarse_matches: List of (concept_uri, similarity_score) tuples
            section_metadata: Metadata about the section
            
        Returns:
            List of match dictionaries with combined scores and metadata
        """
        fine_matches = []
        
        # Get section context for relevance boosting
        section_context = self._get_section_context(section_metadata)
        
        # Extract keywords from section content
        section_content = section_metadata.get("content", "")
        section_title = section_metadata.get("title", "")
        combined_text = f"{section_title} {section_content}" if section_title else section_content
        keywords = self._extract_keywords(combined_text)
        
        for concept_uri, similarity_score in coarse_matches:
            concept = self.ontology_loader.concepts.get(concept_uri, {})
            if not concept:
                continue
            
            # Calculate term match score
            term_match_score = self._calculate_term_match_score(
                keywords, concept.get("matching_terms", [])
            )
            
            # Apply context-based boosting
            match_type = "unknown"
            context_score = 0.0
            
            # Check if it's a role-related concept
            if concept_uri in self.ontology_loader.role_concepts:
                match_type = "role"
                context_score = section_context["role_boost"]
            elif concept_uri in self.ontology_loader.role_related_concepts:
                match_type = "role_related"
                context_score = section_context["role_boost"] * 0.7  # Slightly lower boost
            elif concept_uri in self.ontology_loader.principle_concepts:
                match_type = "principle"
                context_score = section_context["principle_boost"]
            else:
                match_type = "other_concept"
                
            # Calculate text reference match if available
            text_ref_score = 0.0
            if section_content and concept.get("text_references"):
                text_ref_score = self._calculate_text_reference_match(
                    section_content, concept.get("text_references", [])
                )
                
            # Use concept's own relevance score if available
            relevance_score = concept.get("relevance_score", 0.5)
                
            # Calculate combined score 
            # Weight vector similarity more heavily, but consider other signals
            combined_score = (
                (0.55 * similarity_score) +       # Vector similarity (main signal)
                (0.20 * term_match_score) +       # Term matching
                (0.15 * context_score) +          # Section context relevance
                (0.10 * text_ref_score) +         # Text reference matching
                (0.00 * relevance_score)          # Concept's own relevance score (Optional)
            )
            
            # Create match record
            match = {
                "concept_uri": concept_uri,
                "concept_label": concept.get("label", ""),
                "concept_description": concept.get("description", ""),
                "vector_similarity": similarity_score,
                "term_match_score": term_match_score,
                "text_ref_score": text_ref_score,
                "context_score": context_score,
                "combined_score": combined_score,
                "match_type": match_type,
                "category": concept.get("categories", [""])[0] if concept.get("categories") else ""
            }
            
            fine_matches.append(match)
            
        return fine_matches
        
    def _get_section_context(self, section_metadata: Dict[str, Any]) -> Dict[str, float]:
        """
        Extract contextual information about the section from section type.
        
        This determines appropriate boosting factors based on section type.
        
        Args:
            section_metadata: Section metadata including section_type
            
        Returns:
            Dictionary with context-based boosting factors
        """
        section_type = section_metadata.get("section_type", "").lower()
        
        # Default boosts (no special treatment)
        context = {
            "role_boost": 0.0,
            "principle_boost": 0.0,
            "action_boost": 0.0,
            "obligation_boost": 0.0
        }
        
        # Apply boosts based on section type
        if section_type == "facts":
            # Facts sections are more relevant to roles and entities
            context["role_boost"] = 0.3
            
        elif section_type == "discussion":
            # Discussion sections are more relevant to principles and obligations
            context["principle_boost"] = 0.3
            context["obligation_boost"] = 0.2
            
        elif section_type == "conclusion":
            # Conclusion sections are more relevant to action recommendations
            context["action_boost"] = 0.3
            context["obligation_boost"] = 0.2
            
        elif section_type == "questions":
            # Questions often involve principles and obligations
            context["principle_boost"] = 0.2
            
        return context
        
    def _extract_keywords(self, text: str) -> List[str]:
        """
        Extract keywords from text for term matching.
        
        Args:
            text: Input text
            
        Returns:
            List of keywords extracted from the text
        """
        if not text:
            return []
            
        # Clean and normalize text
        text = text.lower()
        # Remove punctuation and special characters
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Split into words
        words = text.split()
        
        # Remove common stop words
        stop_words = {"a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", 
                     "with", "by", "is", "are", "was", "were", "be", "been", "being", 
                     "have", "has", "had", "do", "does", "did", "of", "this", "that"}
        words = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Count occurrences
        word_counts = Counter(words)
        
        # Return most frequent keywords
        return [word for word, count in word_counts.most_common(30)]
        
    def _calculate_term_match_score(self, keywords: List[str], matching_terms: List[str]) -> float:
        """
        Calculate a score based on overlap between keywords and matching terms.
        
        Args:
            keywords: List of keywords from section
            matching_terms: List of matching terms from concept
            
        Returns:
            Score between 0 and 1
        """
        if not keywords or not matching_terms:
            return 0.0
            
        # Normalize terms for comparison
        normalized_keywords = [k.lower() for k in keywords]
        normalized_terms = [t.lower() for t in matching_terms]
        
        # Count matches using different approaches
        exact_matches = 0
        partial_matches = 0
        
        # Check for exact matches
        for keyword in normalized_keywords:
            for term in normalized_terms:
                if keyword == term:
                    exact_matches += 1
                    break
        
        # Check for partial/contained matches
        for keyword in normalized_keywords:
            for term in normalized_terms:
                if keyword in term or term in keyword:
                    if len(keyword) >= 4 and len(term) >= 4:  # Only count meaningful partials
                        partial_matches += 1
                        break
        
        # Calculate score, weighting exact matches more heavily
        total_score = (exact_matches * 1.0) + (partial_matches * 0.5)
        max_possible = len(normalized_keywords)
        
        # Calculate normalized score (0 to 1)
        if max_possible == 0:
            return 0.0
            
        score = min(1.0, total_score / max_possible)
        return score
        
    def _calculate_text_reference_match(self, text: str, text_references: List[str]) -> float:
        """
        Calculate score based on text reference matches in section content.
        
        Args:
            text: Section text content
            text_references: List of text reference patterns
            
        Returns:
            Score between 0 and 1
        """
        if not text or not text_references:
            return 0.0
            
        text_lower = text.lower()
        matches = 0
        
        for ref in text_references:
            ref_lower = ref.lower()
            if ref_lower in text_lower:
                matches += 1
                
        # Calculate score based on number of matches
        score = min(1.0, matches / len(text_references))
        return score
