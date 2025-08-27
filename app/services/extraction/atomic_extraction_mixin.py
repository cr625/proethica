"""
Unified atomic concept extraction mixin for all extractors.

This module provides a standardized way for all 9 concept extractors to apply
atomic concept splitting, eliminating the need for custom splitting logic in each extractor.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import os
import logging
from abc import ABC, abstractmethod

from .base import ConceptCandidate


class AtomicExtractionMixin:
    """
    Mixin class that provides unified atomic concept splitting for all extractors.
    
    Usage:
    ```python
    class MyExtractor(Extractor, AtomicExtractionMixin):
        def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
            # 1. Do initial extraction (LLM or heuristic)
            candidates = self._extract_initial_concepts(text, **kwargs)
            
            # 2. Apply unified atomic splitting
            return self._apply_atomic_splitting(candidates, self.concept_type)
    ```
    """
    
    # Abstract property that each extractor must define
    @property
    @abstractmethod 
    def concept_type(self) -> str:
        """The concept type this extractor handles (e.g., 'obligation', 'principle', 'role')."""
        pass
    
    def _apply_atomic_splitting(self, 
                               candidates: List[ConceptCandidate], 
                               concept_type: Optional[str] = None) -> List[ConceptCandidate]:
        """
        Apply unified atomic concept splitting to extracted candidates.
        
        Args:
            candidates: Initial concept candidates from extraction
            concept_type: Type of concept (defaults to self.concept_type)
            
        Returns:
            List of candidates with compound concepts split into atomic units and normalized labels
        """
        if not candidates:
            return candidates
        
        # Use provided concept_type or fall back to extractor's default
        target_concept_type = concept_type or self.concept_type
        
        # Check if atomic splitting is enabled
        if not self._is_atomic_splitting_enabled():
            # Even if splitting is disabled, still normalize labels
            return self._normalize_candidate_labels(candidates)
        
        try:
            from .concept_splitter import split_concepts_for_extractor
            
            logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            logger.info(f"Applying unified atomic splitting to {len(candidates)} {target_concept_type} candidates")
            
            # Apply the unified splitting logic
            enhanced_candidates = split_concepts_for_extractor(candidates, target_concept_type)
            
            # Normalize labels on all candidates (split and unsplit)
            normalized_candidates = self._normalize_candidate_labels(enhanced_candidates)
            
            # Log results
            if len(enhanced_candidates) != len(candidates):
                logger.info(f"Atomic splitting: {len(candidates)} → {len(enhanced_candidates)} concepts")
                compounds_found = sum(1 for c in enhanced_candidates if c.debug and c.debug.get('atomic_decomposition'))
                if compounds_found > 0:
                    logger.info(f"Split {compounds_found} compound {target_concept_type} concepts into atomic parts")
            
            return normalized_candidates
            
        except Exception as e:
            logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            logger.error(f"Unified atomic splitting failed for {target_concept_type}, using original candidates: {e}")
            return self._normalize_candidate_labels(candidates)
    
    def _is_atomic_splitting_enabled(self) -> bool:
        """Check if atomic splitting is enabled via environment variables."""
        return os.environ.get('ENABLE_CONCEPT_SPLITTING', 'false').lower() == 'true'
    
    def _normalize_candidate_labels(self, candidates: List[ConceptCandidate]) -> List[ConceptCandidate]:
        """
        Normalize concept candidate labels to ensure consistency.
        
        Removes leading/trailing whitespace, punctuation, and standardizes formatting.
        """
        import re
        
        normalized_candidates = []
        
        for candidate in candidates:
            if not candidate.label:
                continue
                
            # Normalize the label
            normalized_label = self._normalize_label(candidate.label)
            
            # Skip if label becomes empty after normalization
            if not normalized_label:
                continue
            
            # Create new candidate with normalized label
            normalized_candidate = ConceptCandidate(
                label=normalized_label,
                description=candidate.description,
                primary_type=candidate.primary_type,
                category=candidate.category,
                confidence=candidate.confidence,
                debug=candidate.debug
            )
            
            normalized_candidates.append(normalized_candidate)
        
        return normalized_candidates
    
    def _normalize_label(self, label: str) -> str:
        """
        Normalize a concept label by cleaning up punctuation and formatting.
        
        Args:
            label: Raw concept label
            
        Returns:
            Cleaned and normalized label
        """
        if not label:
            return ""
            
        import re
        
        # Start with the original label
        normalized = label
        
        # Remove leading/trailing whitespace
        normalized = normalized.strip()
        
        # Remove leading dashes, bullets, numbers
        normalized = re.sub(r'^[-•*\d+\.)\s]+', '', normalized)
        
        # Remove trailing punctuation (periods, semicolons, commas)
        normalized = re.sub(r'[\.;,]+$', '', normalized)
        
        # Clean up internal whitespace (multiple spaces become single)
        normalized = re.sub(r'\s+', ' ', normalized)
        
        # Remove quotes at beginning and end
        normalized = normalized.strip('\'"')
        
        # Handle common prefixes to remove
        prefixes_to_remove = [
            r'^Engineers?\s+(shall|must|should|will)\s+',
            r'^Professionals?\s+(shall|must|should|will)\s+',
            r'^Members?\s+(shall|must|should|will)\s+',
            r'^Practitioners?\s+(shall|must|should|will)\s+',
            r'^One\s+(shall|must|should|will)\s+',
            r'^They\s+(shall|must|should|will)\s+',
        ]
        
        for prefix_pattern in prefixes_to_remove:
            normalized = re.sub(prefix_pattern, '', normalized, flags=re.IGNORECASE)
        
        # Trim again after prefix removal
        normalized = normalized.strip()
        
        # Ensure proper capitalization for concepts (Title Case for multi-words, Capitalize for single words)
        if normalized:
            words = normalized.split()
            if len(words) == 1:
                # Single word - just capitalize first letter
                normalized = words[0].capitalize()
            else:
                # Multiple words - title case, but preserve certain lowercase words
                articles_and_prepositions = {'a', 'an', 'the', 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by', 'and', 'or'}
                
                normalized_words = []
                for i, word in enumerate(words):
                    if i == 0 or word.lower() not in articles_and_prepositions:
                        # Capitalize first word and non-articles/prepositions
                        normalized_words.append(word.capitalize())
                    else:
                        # Keep articles and prepositions lowercase (except first word)
                        normalized_words.append(word.lower())
                
                normalized = ' '.join(normalized_words)
        
        return normalized
    
    def _apply_orchestrated_extraction(self, 
                                     text: str, 
                                     initial_candidates: List[ConceptCandidate],
                                     concept_type: Optional[str] = None) -> List[ConceptCandidate]:
        """
        Apply full LangChain orchestrated extraction (splitting + validation + filtering).
        
        This is the most advanced extraction mode that includes:
        - Atomic concept splitting
        - Semantic validation
        - Quality filtering
        - Relationship inference
        
        Args:
            text: Original text being analyzed
            initial_candidates: Candidates from initial extraction
            concept_type: Type of concept (defaults to self.concept_type)
            
        Returns:
            Enhanced and validated concept candidates
        """
        if not initial_candidates:
            return []
        
        target_concept_type = concept_type or self.concept_type
        
        # Check if orchestration is enabled
        if not self._is_orchestration_enabled():
            # Fall back to just atomic splitting
            return self._apply_atomic_splitting(initial_candidates, target_concept_type)
        
        try:
            from .langchain_orchestrator import orchestrated_extraction
            import asyncio
            
            logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            logger.info(f"Applying full orchestrated extraction for {target_concept_type}")
            
            # Run the orchestrated extraction
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                enhanced_candidates = loop.run_until_complete(
                    orchestrated_extraction(text, target_concept_type, initial_candidates)
                )
                return enhanced_candidates
            finally:
                loop.close()
                
        except Exception as e:
            logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
            logger.error(f"Orchestrated extraction failed for {target_concept_type}, falling back to atomic splitting: {e}")
            return self._apply_atomic_splitting(initial_candidates, target_concept_type)
    
    def _is_orchestration_enabled(self) -> bool:
        """Check if full LangChain orchestration is enabled."""
        return os.environ.get('ENABLE_CONCEPT_ORCHESTRATION', 'false').lower() == 'true'


class AtomicExtractor(AtomicExtractionMixin):
    """
    Base class for extractors that want to use the unified atomic extraction framework.
    
    This is an optional base class that combines the mixin with common functionality.
    Extractors can either inherit from this or just use the mixin directly.
    """
    
    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()
    
    @property
    @abstractmethod
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        pass
    
    def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
        """
        Main extraction method that applies unified atomic splitting.
        
        Subclasses should override _extract_initial_concepts() instead of this method.
        """
        # Step 1: Initial extraction (implemented by subclass)
        initial_candidates = self._extract_initial_concepts(text, **kwargs)
        
        # Step 2: Apply unified atomic processing
        if self._is_orchestration_enabled():
            return self._apply_orchestrated_extraction(text, initial_candidates)
        else:
            return self._apply_atomic_splitting(initial_candidates)
    
    @abstractmethod
    def _extract_initial_concepts(self, text: str, **kwargs) -> List[ConceptCandidate]:
        """
        Perform initial concept extraction (LLM or heuristic).
        
        This method should be implemented by each specific extractor to do the 
        initial extraction work before atomic splitting is applied.
        """
        pass


# Utility functions for gradual migration

def enable_atomic_splitting_for_extractor(extractor_class):
    """
    Decorator to add atomic splitting capability to existing extractors.
    
    Usage:
    ```python
    @enable_atomic_splitting_for_extractor
    class MyLegacyExtractor(Extractor):
        concept_type = 'obligation'
        
        def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
            candidates = self._legacy_extract_logic(text, **kwargs)
            # Atomic splitting will be automatically applied
            return candidates
    ```
    """
    # Add the mixin to the class
    if not issubclass(extractor_class, AtomicExtractionMixin):
        class EnhancedExtractor(extractor_class, AtomicExtractionMixin):
            pass
        
        # Copy over class attributes
        for attr in dir(extractor_class):
            if not attr.startswith('_') and not hasattr(EnhancedExtractor, attr):
                setattr(EnhancedExtractor, attr, getattr(extractor_class, attr))
        
        # Wrap the extract method
        original_extract = extractor_class.extract
        
        def enhanced_extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
            # Call original extract
            candidates = original_extract(self, text, **kwargs)
            # Apply atomic splitting
            return self._apply_atomic_splitting(candidates)
        
        EnhancedExtractor.extract = enhanced_extract
        EnhancedExtractor.__name__ = extractor_class.__name__ + 'Enhanced'
        
        return EnhancedExtractor
    
    return extractor_class


def migrate_extractor_to_atomic_framework(extractor_class, concept_type: str):
    """
    Helper to migrate existing extractors to use the atomic framework.
    
    Args:
        extractor_class: The existing extractor class
        concept_type: The concept type for this extractor
        
    Returns:
        Enhanced extractor class with atomic splitting
    """
    
    class MigratedExtractor(extractor_class, AtomicExtractionMixin):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            
        @property
        def concept_type(self) -> str:
            return concept_type
        
        def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
            # Call the original extraction method  
            candidates = super().extract(text, **kwargs)
            # Apply unified atomic splitting
            return self._apply_atomic_splitting(candidates)
    
    MigratedExtractor.__name__ = f"Atomic{extractor_class.__name__}"
    return MigratedExtractor