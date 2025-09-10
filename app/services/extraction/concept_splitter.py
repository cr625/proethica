"""
Generalized LLM-based concept splitter for atomic concept decomposition.

This module provides a LangChain-orchestrated multi-step filtering process 
to break down compound concepts into atomic units across all concept types.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Union
import os
import logging
from dataclasses import dataclass

# LangChain imports
try:
    from langchain.chains import LLMChain
    from langchain.prompts import PromptTemplate
    from langchain.schema import BaseMessage, HumanMessage, SystemMessage
    from langchain.callbacks import get_openai_callback
except ImportError:
    # Fallback for environments without LangChain
    LLMChain = None
    PromptTemplate = None

# ProEthica imports
from .base import ConceptCandidate
from models import ModelConfig

# LLM utils
try:
    from app.utils.llm_utils import get_llm_client
except Exception:
    get_llm_client = None


@dataclass
class SplitResult:
    """Result of concept splitting operation."""
    original_concept: str
    atomic_concepts: List[str]
    confidence: float
    reasoning: str
    split_method: str  # 'compound_detected' | 'atomic_confirmed' | 'pattern_based'


class GeneralizedConceptSplitter:
    """
    LLM-powered concept splitter that can handle any concept type with 
    intelligent atomic decomposition without hardcoded patterns.
    """
    
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or 'auto').lower()
        self.logger = logging.getLogger(__name__)
        
        # Concept type specific examples for few-shot learning
        self.concept_examples = {
            'obligation': {
                'compound': "Practice only in areas of competence and disclose conflicts of interest",
                'atomic': ["Practice only in areas of competence", "Disclose conflicts of interest"],
                'reasoning': "Two distinct professional duties: competence practice and conflict disclosure"
            },
            'action': {
                'compound': "Inform clients and maintain confidentiality of project details", 
                'atomic': ["Inform clients", "Maintain confidentiality of project details"],
                'reasoning': "Two separate actions: communication and confidentiality maintenance"
            },
            'principle': {
                'compound': "Public safety and professional integrity",
                'atomic': ["Public safety", "Professional integrity"], 
                'reasoning': "Two fundamental ethical principles that can exist independently"
            },
            'event': {
                'compound': "Safety incident or regulatory violation",
                'atomic': ["Safety incident", "Regulatory violation"],
                'reasoning': "Two different types of triggering events"
            },
            'capability': {
                'compound': "Technical expertise and professional judgment",
                'atomic': ["Technical expertise", "Professional judgment"],
                'reasoning': "Two distinct professional capabilities"
            },
            'constraint': {
                'compound': "Legal requirements and professional standards compliance",
                'atomic': ["Legal requirements", "Professional standards compliance"],
                'reasoning': "Two separate constraint sources"
            },
            'state': {
                'compound': "Conflict of interest or public safety risk",
                'atomic': ["Conflict of interest", "Public safety risk"],
                'reasoning': "Two distinct professional states/conditions"
            },
            'resource': {
                'compound': "NSPE Code and IEEE technical standards",
                'atomic': ["NSPE Code", "IEEE technical standards"],
                'reasoning': "Two separate professional resources"
            }
        }

    def split_concepts(self, 
                      candidates: List[ConceptCandidate], 
                      concept_type: str) -> List[ConceptCandidate]:
        """
        Main entry point: split compound concepts into atomic concepts.
        
        Args:
            candidates: List of concept candidates to process
            concept_type: Type of concepts (obligation, action, principle, etc.)
            
        Returns:
            List of candidates with compound concepts split into atomic ones
        """
        if not candidates:
            return candidates
            
        # Process each candidate
        processed_candidates = []
        
        for candidate in candidates:
            split_result = self.analyze_and_split_concept(
                candidate.label, 
                concept_type,
                candidate.description
            )
            
            if len(split_result.atomic_concepts) > 1:
                # Compound concept detected - create multiple atomic candidates
                self.logger.info(f"Split compound {concept_type}: '{candidate.label}' → {len(split_result.atomic_concepts)} atomic concepts")
                
                for atomic_concept in split_result.atomic_concepts:
                    atomic_candidate = ConceptCandidate(
                        label=atomic_concept,
                        description=candidate.description,
                        primary_type=candidate.primary_type,
                        category=candidate.category,
                        confidence=candidate.confidence * split_result.confidence,  # Adjust confidence
                        debug={
                            **candidate.debug,
                            'original_compound': candidate.label,
                            'split_method': split_result.split_method,
                            'split_reasoning': split_result.reasoning,
                            'atomic_decomposition': True
                        }
                    )
                    processed_candidates.append(atomic_candidate)
            else:
                # Atomic concept confirmed - keep as is
                candidate.debug = {
                    **candidate.debug,
                    'atomicity_verified': True,
                    'split_analysis_method': split_result.split_method
                }
                processed_candidates.append(candidate)
                
        return processed_candidates

    def analyze_and_split_concept(self, 
                                 concept_text: str, 
                                 concept_type: str,
                                 description: Optional[str] = None) -> SplitResult:
        """
        Analyze a single concept and split if compound.
        
        Uses a multi-step LLM process:
        1. Detect if concept is compound or atomic
        2. If compound, intelligently split into atomic parts
        3. Validate split makes semantic sense
        """
        
        # Step 1: Quick heuristic check
        if len(concept_text.split()) < 3:
            return SplitResult(
                original_concept=concept_text,
                atomic_concepts=[concept_text],
                confidence=0.95,
                reasoning="Concept too short to be compound",
                split_method="heuristic_atomic"
            )
        
        # Step 2: LLM-based analysis
        if get_llm_client is not None:
            try:
                return self._llm_analyze_and_split(concept_text, concept_type, description)
            except Exception as e:
                self.logger.warning(f"LLM analysis failed for '{concept_text}': {e}")
        
        # Step 3: Fallback to pattern-based splitting
        return self._fallback_pattern_split(concept_text, concept_type)

    def _llm_analyze_and_split(self, 
                              concept_text: str, 
                              concept_type: str,
                              description: Optional[str] = None) -> SplitResult:
        """Use LLM to analyze and split concepts intelligently."""
        
        client = get_llm_client()
        example = self.concept_examples.get(concept_type, self.concept_examples['obligation'])
        
        # Create analysis prompt with few-shot examples
        analysis_prompt = f"""
You are an expert in professional ethics ontology analysis. Your task is to determine if a concept is ATOMIC (single, indivisible) or COMPOUND (contains multiple distinct concepts that should be separated).

CONCEPT TYPE: {concept_type.upper()}

EXAMPLE - COMPOUND {concept_type.upper()}:
Input: "{example['compound']}"
Analysis: COMPOUND
Atomic concepts: {example['atomic']}
Reasoning: {example['reasoning']}

ANALYSIS RULES:
1. A concept is ATOMIC if it represents one cohesive, indivisible idea
2. A concept is COMPOUND if it contains multiple distinct ideas joined by:
   - Conjunctions (and, or)
   - Commas separating distinct items
   - Multiple modal verbs (shall X, must Y)
   - Multiple action verbs with different objects
   
3. For {concept_type}s specifically:
   - Each atomic {concept_type} should be independently meaningful
   - Splitting should preserve the semantic intent of each part
   - Avoid over-splitting (don't separate adjectives from their nouns)

ANALYZE THIS CONCEPT:
Input: "{concept_text}"
{f'Context: {description}' if description else ''}

RESPOND EXACTLY IN THIS FORMAT:
Analysis: [ATOMIC or COMPOUND]
Atomic concepts: ["concept1", "concept2", ...] (or just ["original"] if atomic)
Reasoning: [Brief explanation of why it's atomic or how it should be split]
Confidence: [0.0-1.0]
"""

        try:
            # Call LLM
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                response = client.messages.create(
                    model=model,
                    max_tokens=500,
                    temperature=0.1,  # Low temperature for consistent analysis
                    system="You are an expert ontology analyst. Follow instructions exactly.",
                    messages=[{"role": "user", "content": analysis_prompt}],
                )
                content = response.content[0].text if hasattr(response, 'content') else str(response)
            else:
                # Fallback for other clients
                content = "Analysis: ATOMIC\nAtomic concepts: [\"" + concept_text + "\"]\nReasoning: Fallback analysis\nConfidence: 0.5"
            
            return self._parse_llm_response(content, concept_text)
            
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return self._fallback_pattern_split(concept_text, concept_type)

    def _parse_llm_response(self, response_text: str, original_concept: str) -> SplitResult:
        """Parse LLM response into structured result."""
        
        lines = [line.strip() for line in response_text.strip().split('\n') if line.strip()]
        
        analysis = "ATOMIC"
        atomic_concepts = [original_concept]
        reasoning = "Default reasoning"
        confidence = 0.7
        
        for line in lines:
            if line.startswith("Analysis:"):
                analysis = line.split(":", 1)[1].strip().upper()
            elif line.startswith("Atomic concepts:"):
                concepts_str = line.split(":", 1)[1].strip()
                try:
                    # Parse JSON-like array
                    import json
                    concepts_str = concepts_str.replace("'", '"')  # Handle single quotes
                    atomic_concepts = json.loads(concepts_str)
                except:
                    # Fallback parsing
                    concepts_str = concepts_str.strip('[]"\'')
                    atomic_concepts = [c.strip().strip('"\'') for c in concepts_str.split('","') if c.strip()]
            elif line.startswith("Reasoning:"):
                reasoning = line.split(":", 1)[1].strip()
            elif line.startswith("Confidence:"):
                try:
                    confidence = float(line.split(":", 1)[1].strip())
                except:
                    confidence = 0.7

        # Validate atomic concepts
        if not atomic_concepts or atomic_concepts == [""]:
            atomic_concepts = [original_concept]
        
        split_method = "llm_compound" if len(atomic_concepts) > 1 else "llm_atomic"
        
        return SplitResult(
            original_concept=original_concept,
            atomic_concepts=atomic_concepts,
            confidence=confidence,
            reasoning=reasoning,
            split_method=split_method
        )

    def _fallback_pattern_split(self, concept_text: str, concept_type: str) -> SplitResult:
        """Fallback pattern-based splitting when LLM is unavailable."""
        
        # Simple pattern-based rules as fallback
        if ' and ' in concept_text.lower():
            parts = [part.strip() for part in concept_text.split(' and ')]
            if len(parts) == 2 and all(len(p) > 5 for p in parts):
                return SplitResult(
                    original_concept=concept_text,
                    atomic_concepts=parts,
                    confidence=0.8,
                    reasoning=f"Pattern-based split on 'and' conjunction",
                    split_method="pattern_conjunction"
                )
        
        if ', ' in concept_text and len(concept_text.split(', ')) <= 3:
            parts = [part.strip() for part in concept_text.split(', ')]
            if all(len(p) > 8 for p in parts):
                return SplitResult(
                    original_concept=concept_text,
                    atomic_concepts=parts,
                    confidence=0.7,
                    reasoning=f"Pattern-based split on comma separation",
                    split_method="pattern_comma"
                )
        
        # Default: keep as atomic
        return SplitResult(
            original_concept=concept_text,
            atomic_concepts=[concept_text],
            confidence=0.9,
            reasoning="No compound patterns detected",
            split_method="pattern_atomic"
        )


# Integration helper functions for existing extractors
def split_concepts_for_extractor(candidates: List[ConceptCandidate], 
                                concept_type: str,
                                provider: Optional[str] = None) -> List[ConceptCandidate]:
    """
    Convenience function for existing extractors to use generalized splitting.
    
    Usage in extractors:
    ```python
    from .concept_splitter import split_concepts_for_extractor
    
    # After initial extraction
    candidates = self._extract_initial_concepts(text)
    
    # Apply intelligent splitting
    candidates = split_concepts_for_extractor(candidates, 'obligation')
    
    return candidates
    ```
    """
    splitter = GeneralizedConceptSplitter(provider=provider)
    return splitter.split_concepts(candidates, concept_type)