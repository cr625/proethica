"""
Intelligent Annotation Service

Provides semantic analysis and context-aware matching for guideline annotations
using LLM capabilities and ontological reasoning.
"""

import logging
import re
import asyncio
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.services.ontserve_annotation_service import OntServeAnnotationService
from app.services.section_embedding_service import SectionEmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class SemanticMatch:
    """Represents a semantic match between text and concept."""
    text: str
    concept_uri: str
    concept_label: str
    similarity_score: float
    match_type: str  # 'exact', 'semantic', 'partial', 'contextual'
    context_window: str
    explanation: str


@dataclass
class ConceptContext:
    """Context information for a concept."""
    concept_uri: str
    concept_label: str
    related_concepts: List[str] = field(default_factory=list)
    parent_concepts: List[str] = field(default_factory=list)
    child_concepts: List[str] = field(default_factory=list)
    domain_relevance: float = 1.0


class IntelligentAnnotationService:
    """
    Provides intelligent annotation capabilities using semantic analysis,
    context-aware matching, and LLM-based reasoning.
    """
    
    def __init__(self):
        """Initialize the intelligent annotation service."""
        self.ontserve_service = OntServeAnnotationService()
        self.embedding_service = SectionEmbeddingService()
        
        # Configuration
        self.semantic_threshold = 0.75
        self.partial_match_threshold = 0.6
        self.context_window_size = 100  # characters around match
        
        # Cache for concept embeddings
        self._concept_embeddings: Dict[str, np.ndarray] = {}
        self._concept_contexts: Dict[str, ConceptContext] = {}
        
        logger.info("Intelligent Annotation Service initialized")
    
    async def annotate_section(self,
                              section_text: str,
                              section_code: str,
                              ontology_concepts: List[Dict[str, Any]],
                              domain: str = "engineering-ethics") -> List[Dict[str, Any]]:
        """
        Perform intelligent annotation of a guideline section.
        
        Args:
            section_text: Text content of the section
            section_code: Section identifier (e.g., "I.1", "II.3.c")
            ontology_concepts: List of relevant ontology concepts
            domain: Professional domain context
            
        Returns:
            List of intelligent annotations with explanations
        """
        annotations = []
        
        try:
            # Step 1: Generate section embedding
            section_embedding = self.embedding_service.get_embedding(section_text)
            
            # Step 2: Prepare concept embeddings and contexts
            await self._prepare_concept_data(ontology_concepts)
            
            # Step 3: Find semantic matches
            semantic_matches = self._find_semantic_matches(
                section_text, section_embedding, ontology_concepts
            )
            
            # Step 4: Find contextual matches
            contextual_matches = self._find_contextual_matches(
                section_text, ontology_concepts, domain
            )
            
            # Step 5: Combine and rank matches
            all_matches = self._combine_and_rank_matches(
                semantic_matches, contextual_matches
            )
            
            # Step 6: Generate annotations with explanations
            for match in all_matches:
                annotation = self._create_annotation(
                    match, section_text, section_code
                )
                annotations.append(annotation)
            
            logger.info(f"Created {len(annotations)} intelligent annotations for section {section_code}")
            
        except Exception as e:
            logger.error(f"Error in intelligent annotation: {e}")
        
        return annotations
    
    async def _prepare_concept_data(self, concepts: List[Dict[str, Any]]):
        """
        Prepare concept embeddings and context information.
        
        Args:
            concepts: List of ontology concepts
        """
        for concept in concepts:
            uri = concept.get('uri')
            if not uri:
                continue
            
            # Generate embedding if not cached
            if uri not in self._concept_embeddings:
                label = concept.get('label', '')
                definition = concept.get('definition', '')
                text = f"{label}. {definition}" if definition else label
                
                try:
                    embedding = self.embedding_service.get_embedding(text)
                    self._concept_embeddings[uri] = embedding
                except Exception as e:
                    logger.debug(f"Could not generate embedding for {uri}: {e}")
            
            # Build concept context if not cached
            if uri not in self._concept_contexts:
                context = ConceptContext(
                    concept_uri=uri,
                    concept_label=concept.get('label', ''),
                    related_concepts=concept.get('related', []),
                    parent_concepts=concept.get('parents', []),
                    child_concepts=concept.get('children', []),
                    domain_relevance=self._calculate_domain_relevance(concept)
                )
                self._concept_contexts[uri] = context
    
    def _find_semantic_matches(self,
                              text: str,
                              text_embedding: np.ndarray,
                              concepts: List[Dict[str, Any]]) -> List[SemanticMatch]:
        """
        Find semantic matches using embeddings.
        
        Args:
            text: Section text
            text_embedding: Embedding of the text
            concepts: List of concepts to match
            
        Returns:
            List of semantic matches
        """
        matches = []
        
        # Split text into sentences for granular matching
        sentences = self._split_into_sentences(text)
        
        for concept in concepts:
            uri = concept.get('uri')
            if uri not in self._concept_embeddings:
                continue
            
            concept_embedding = self._concept_embeddings[uri]
            
            # Calculate similarity with full text
            similarity = cosine_similarity(
                text_embedding.reshape(1, -1),
                concept_embedding.reshape(1, -1)
            )[0, 0]
            
            if similarity >= self.semantic_threshold:
                # Find best matching sentence
                best_sentence, best_score = self._find_best_sentence_match(
                    sentences, concept_embedding
                )
                
                if best_sentence:
                    match = SemanticMatch(
                        text=best_sentence,
                        concept_uri=uri,
                        concept_label=concept.get('label', ''),
                        similarity_score=float(similarity),
                        match_type='semantic',
                        context_window=self._get_context_window(text, best_sentence),
                        explanation=f"Semantic similarity: {similarity:.2%}"
                    )
                    matches.append(match)
        
        return matches
    
    def _find_contextual_matches(self,
                                text: str,
                                concepts: List[Dict[str, Any]],
                                domain: str) -> List[SemanticMatch]:
        """
        Find contextual matches based on domain knowledge.
        
        Args:
            text: Section text
            concepts: List of concepts
            domain: Professional domain
            
        Returns:
            List of contextual matches
        """
        matches = []
        text_lower = text.lower()
        
        for concept in concepts:
            uri = concept.get('uri')
            label = concept.get('label', '')
            
            # Check for contextual indicators
            context_indicators = self._get_context_indicators(label, domain)
            
            for indicator in context_indicators:
                if indicator.lower() in text_lower:
                    # Find the actual text segment
                    segment = self._extract_segment_around_indicator(
                        text, indicator
                    )
                    
                    if segment:
                        match = SemanticMatch(
                            text=segment,
                            concept_uri=uri,
                            concept_label=label,
                            similarity_score=0.8,  # Contextual match confidence
                            match_type='contextual',
                            context_window=self._get_context_window(text, segment),
                            explanation=f"Contextual indicator: '{indicator}'"
                        )
                        matches.append(match)
                        break
        
        return matches
    
    def _combine_and_rank_matches(self,
                                 semantic_matches: List[SemanticMatch],
                                 contextual_matches: List[SemanticMatch]) -> List[SemanticMatch]:
        """
        Combine and rank different types of matches.
        
        Args:
            semantic_matches: Matches from semantic analysis
            contextual_matches: Matches from contextual analysis
            
        Returns:
            Combined and ranked list of matches
        """
        all_matches = semantic_matches + contextual_matches
        
        # Remove duplicates (same concept, overlapping text)
        unique_matches = self._remove_duplicate_matches(all_matches)
        
        # Rank by similarity score and match type
        ranked_matches = sorted(
            unique_matches,
            key=lambda x: (x.similarity_score, x.match_type == 'semantic'),
            reverse=True
        )
        
        return ranked_matches
    
    def _create_annotation(self,
                         match: SemanticMatch,
                         full_text: str,
                         section_code: str) -> Dict[str, Any]:
        """
        Create an annotation from a semantic match.
        
        Args:
            match: Semantic match
            full_text: Full section text
            section_code: Section identifier
            
        Returns:
            Annotation dictionary
        """
        # Find offsets in full text
        start_offset = full_text.find(match.text)
        if start_offset == -1:
            # Try case-insensitive search
            start_offset = full_text.lower().find(match.text.lower())
        
        if start_offset == -1:
            logger.warning(f"Could not find match text in full text for {match.concept_label}")
            return None
        
        end_offset = start_offset + len(match.text)
        
        # Get concept details from cache
        context = self._concept_contexts.get(match.concept_uri, None)
        
        annotation = {
            'text_segment': match.text,
            'start_offset': start_offset,
            'end_offset': end_offset,
            'concept_uri': match.concept_uri,
            'concept_label': match.concept_label,
            'confidence': match.similarity_score,
            'match_type': match.match_type,
            'explanation': match.explanation,
            'section_code': section_code,
            'context_window': match.context_window,
            'metadata': {
                'annotation_method': 'intelligent',
                'match_type': match.match_type,
                'domain_relevance': context.domain_relevance if context else 1.0
            }
        }
        
        return annotation
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Simple sentence splitting - can be enhanced with NLP
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _find_best_sentence_match(self,
                                 sentences: List[str],
                                 concept_embedding: np.ndarray) -> Tuple[str, float]:
        """
        Find the best matching sentence for a concept.
        
        Args:
            sentences: List of sentences
            concept_embedding: Concept embedding vector
            
        Returns:
            Tuple of (best sentence, similarity score)
        """
        best_sentence = None
        best_score = 0.0
        
        for sentence in sentences:
            if len(sentence) < 10:  # Skip very short sentences
                continue
            
            try:
                sentence_embedding = self.embedding_service.get_embedding(sentence)
                similarity = cosine_similarity(
                    sentence_embedding.reshape(1, -1),
                    concept_embedding.reshape(1, -1)
                )[0, 0]
                
                if similarity > best_score:
                    best_score = similarity
                    best_sentence = sentence
            except:
                continue
        
        return best_sentence, best_score
    
    def _get_context_window(self, full_text: str, segment: str) -> str:
        """
        Get context window around a text segment.
        
        Args:
            full_text: Full text
            segment: Text segment
            
        Returns:
            Context window string
        """
        pos = full_text.find(segment)
        if pos == -1:
            return segment
        
        start = max(0, pos - self.context_window_size)
        end = min(len(full_text), pos + len(segment) + self.context_window_size)
        
        context = full_text[start:end]
        
        # Add ellipsis if truncated
        if start > 0:
            context = "..." + context
        if end < len(full_text):
            context = context + "..."
        
        return context
    
    def _get_context_indicators(self, concept_label: str, domain: str) -> List[str]:
        """
        Get contextual indicators for a concept.
        
        Args:
            concept_label: Concept label
            domain: Professional domain
            
        Returns:
            List of contextual indicators
        """
        indicators = []
        
        # Extract key terms from concept label
        words = concept_label.lower().split()
        indicators.extend([w for w in words if len(w) > 4])
        
        # Add domain-specific indicators
        if domain == "engineering-ethics":
            if "safety" in concept_label.lower():
                indicators.extend(["public safety", "health and welfare", "protect"])
            elif "obligation" in concept_label.lower():
                indicators.extend(["shall", "must", "required", "duty"])
            elif "principle" in concept_label.lower():
                indicators.extend(["fundamental", "canon", "ethical"])
        
        return indicators
    
    def _extract_segment_around_indicator(self,
                                         text: str,
                                         indicator: str) -> Optional[str]:
        """
        Extract text segment around an indicator.
        
        Args:
            text: Full text
            indicator: Indicator word/phrase
            
        Returns:
            Text segment or None
        """
        pattern = re.compile(r'\b' + re.escape(indicator) + r'\b', re.IGNORECASE)
        match = pattern.search(text)
        
        if match:
            # Extract sentence or clause containing the indicator
            start = match.start()
            
            # Find sentence boundaries
            sentence_start = max(0, text.rfind('.', 0, start) + 1)
            sentence_end = text.find('.', start)
            if sentence_end == -1:
                sentence_end = len(text)
            else:
                sentence_end += 1
            
            return text[sentence_start:sentence_end].strip()
        
        return None
    
    def _remove_duplicate_matches(self, matches: List[SemanticMatch]) -> List[SemanticMatch]:
        """
        Remove duplicate matches.
        
        Args:
            matches: List of matches
            
        Returns:
            List without duplicates
        """
        seen: Set[Tuple[str, str]] = set()
        unique = []
        
        for match in matches:
            # Use concept URI and approximate text position as key
            key = (match.concept_uri, match.text[:50])
            if key not in seen:
                seen.add(key)
                unique.append(match)
        
        return unique
    
    def _calculate_domain_relevance(self, concept: Dict[str, Any]) -> float:
        """
        Calculate domain relevance score for a concept.
        
        Args:
            concept: Concept dictionary
            
        Returns:
            Relevance score (0-1)
        """
        # Simple heuristic - can be enhanced
        label = concept.get('label', '').lower()
        ontology = concept.get('ontology', '').lower()
        
        # Higher relevance for domain-specific ontologies
        if 'engineering' in ontology or 'proethica' in ontology:
            return 1.0
        elif 'ethics' in ontology:
            return 0.9
        else:
            return 0.7
    
    def calculate_annotation_confidence(self,
                                       annotation: Dict[str, Any],
                                       context: Dict[str, Any]) -> float:
        """
        Calculate confidence score for an annotation.
        
        Args:
            annotation: Annotation data
            context: Additional context
            
        Returns:
            Confidence score (0-1)
        """
        base_confidence = annotation.get('confidence', 0.5)
        
        # Adjust based on match type
        match_type = annotation.get('match_type', 'unknown')
        if match_type == 'exact':
            confidence = base_confidence * 1.0
        elif match_type == 'semantic':
            confidence = base_confidence * 0.9
        elif match_type == 'contextual':
            confidence = base_confidence * 0.8
        else:
            confidence = base_confidence * 0.7
        
        # Adjust based on domain relevance
        domain_relevance = annotation.get('metadata', {}).get('domain_relevance', 1.0)
        confidence *= domain_relevance
        
        return min(1.0, confidence)
    
    def generate_explanation(self,
                            annotation: Dict[str, Any],
                            section_context: str) -> str:
        """
        Generate human-readable explanation for an annotation.
        
        Args:
            annotation: Annotation data
            section_context: Section context
            
        Returns:
            Explanation string
        """
        concept_label = annotation.get('concept_label', 'concept')
        match_type = annotation.get('match_type', 'unknown')
        confidence = annotation.get('confidence', 0)
        
        explanation_parts = []
        
        # Base explanation
        if match_type == 'semantic':
            explanation_parts.append(
                f"The text semantically relates to '{concept_label}' "
                f"with {confidence:.1%} confidence."
            )
        elif match_type == 'contextual':
            explanation_parts.append(
                f"The context suggests this relates to '{concept_label}'."
            )
        else:
            explanation_parts.append(
                f"This text matches the concept '{concept_label}'."
            )
        
        # Add context if available
        if annotation.get('explanation'):
            explanation_parts.append(annotation['explanation'])
        
        return " ".join(explanation_parts)
    
    def clear_cache(self):
        """Clear cached embeddings and contexts."""
        self._concept_embeddings.clear()
        self._concept_contexts.clear()
        logger.info("Intelligent annotation cache cleared")
