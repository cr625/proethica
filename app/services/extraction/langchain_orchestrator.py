"""
LangChain Orchestration Architecture for Multi-Step Concept Processing.

This module implements a sophisticated multi-step filtering and validation process
using LangChain to orchestrate the concept extraction and splitting pipeline.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional, Set
import logging
import asyncio
from dataclasses import dataclass
from enum import Enum

# LangChain imports
try:
    from langchain_classic.chains import LLMChain, SequentialChain
    from langchain_classic.prompts import PromptTemplate, ChatPromptTemplate
    from langchain_core.output_parsers import BaseOutputParser
    from langchain_core.exceptions import OutputParserException
    from langchain_classic.callbacks import get_openai_callback
    from langchain_classic.memory import ConversationBufferWindowMemory
except ImportError:
    # Graceful fallback
    LLMChain = SequentialChain = PromptTemplate = None
    ChatPromptTemplate = BaseOutputParser = OutputParserException = None

# ProEthica imports
from .base import ConceptCandidate
from .concept_splitter import GeneralizedConceptSplitter, SplitResult
from models import ModelConfig

try:
    from app.utils.llm_utils import get_llm_client
except Exception:
    get_llm_client = None


class ProcessingStage(Enum):
    """Stages in the concept processing pipeline."""
    INITIAL_EXTRACTION = "initial_extraction"
    COMPOUND_DETECTION = "compound_detection" 
    ATOMIC_SPLITTING = "atomic_splitting"
    SEMANTIC_VALIDATION = "semantic_validation"
    QUALITY_FILTERING = "quality_filtering"
    RELATIONSHIP_INFERENCE = "relationship_inference"


@dataclass
class ProcessingResult:
    """Result of orchestrated processing pipeline."""
    stage: ProcessingStage
    concepts: List[ConceptCandidate]
    metadata: Dict[str, Any]
    processing_time: float
    success: bool
    error_message: Optional[str] = None


class ConceptValidationParser(BaseOutputParser[Dict[str, Any]]):
    """Custom parser for concept validation responses."""
    
    def parse(self, text: str) -> Dict[str, Any]:
        """Parse LLM validation response."""
        try:
            # Look for structured response patterns
            result = {
                'valid': True,
                'confidence': 0.7,
                'reasoning': text,
                'suggestions': []
            }
            
            lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
            
            for line in lines:
                if line.lower().startswith('valid:'):
                    result['valid'] = 'yes' in line.lower() or 'true' in line.lower()
                elif line.lower().startswith('confidence:'):
                    try:
                        result['confidence'] = float(line.split(':', 1)[1].strip())
                    except:
                        pass
                elif line.lower().startswith('reasoning:'):
                    result['reasoning'] = line.split(':', 1)[1].strip()
                elif line.lower().startswith('suggestions:'):
                    suggestions = line.split(':', 1)[1].strip()
                    result['suggestions'] = [s.strip() for s in suggestions.split(',') if s.strip()]
            
            return result
            
        except Exception as e:
            raise OutputParserException(f"Failed to parse validation response: {e}")


class LangChainConceptOrchestrator:
    """
    LangChain-based orchestrator for multi-step concept processing.
    
    Provides a comprehensive pipeline that can:
    1. Extract initial concepts
    2. Detect and split compound concepts
    3. Validate semantic coherence
    4. Filter for quality
    5. Infer relationships between concepts
    """
    
    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or 'auto').lower()
        self.logger = logging.getLogger(__name__)
        self.splitter = GeneralizedConceptSplitter(provider)
        
        # Initialize LangChain components if available
        self.chains = self._initialize_chains() if LLMChain else {}
        
    def _initialize_chains(self) -> Dict[str, Any]:
        """Initialize LangChain chains for different processing stages."""
        chains = {}
        
        try:
            # 1. Compound Detection Chain
            compound_prompt = PromptTemplate(
                input_variables=["concept_type", "concept_text", "examples"],
                template="""
You are analyzing a {concept_type} concept to determine if it's compound or atomic.

EXAMPLES OF COMPOUND {concept_type}S:
{examples}

CONCEPT TO ANALYZE: "{concept_text}"

Respond with:
COMPOUND: [yes/no]
CONFIDENCE: [0.0-1.0]
REASONING: [brief explanation]

If COMPOUND, also provide:
SPLIT_SUGGESTION: [how it should be split]
"""
            )
            
            # 2. Semantic Validation Chain
            validation_prompt = PromptTemplate(
                input_variables=["concept_type", "concept_text", "context"],
                template="""
Validate this {concept_type} concept for semantic coherence and professional relevance.

CONCEPT: "{concept_text}"
CONTEXT: {context}

Evaluate:
1. Does it represent a clear, professional {concept_type}?
2. Is it semantically coherent and well-defined?
3. Is it relevant to professional ethics?
4. Is it at the appropriate level of granularity?

VALID: [yes/no]
CONFIDENCE: [0.0-1.0] 
REASONING: [explanation]
SUGGESTIONS: [improvements if needed]
"""
            )
            
            # 3. Quality Filtering Chain
            quality_prompt = PromptTemplate(
                input_variables=["concepts", "concept_type", "max_concepts"],
                template="""
You have {len(concepts)} extracted {concept_type}s. Select the top {max_concepts} most important and distinct ones.

CONCEPTS:
{concepts}

Rank by:
1. Importance to professional ethics
2. Clarity and specificity  
3. Distinctiveness (avoid duplicates)
4. Actionability/applicability

SELECTED: [list the selected concepts]
REASONING: [why these were chosen]
"""
            )
            
            chains['compound_detection'] = compound_prompt
            chains['semantic_validation'] = validation_prompt  
            chains['quality_filtering'] = quality_prompt
            
        except Exception as e:
            self.logger.error(f"Failed to initialize LangChain components: {e}")
            
        return chains
    
    async def process_concepts_pipeline(self, 
                                      text: str,
                                      concept_type: str,
                                      initial_candidates: List[ConceptCandidate],
                                      pipeline_config: Optional[Dict[str, Any]] = None) -> List[ProcessingResult]:
        """
        Run the complete multi-step processing pipeline.
        
        Args:
            text: Original text being processed
            concept_type: Type of concepts (obligation, action, etc.)  
            initial_candidates: Candidates from initial extraction
            pipeline_config: Configuration for pipeline stages
            
        Returns:
            List of processing results from each stage
        """
        config = pipeline_config or {}
        results = []
        current_candidates = initial_candidates.copy()
        
        # Stage 1: Compound Detection & Splitting
        if config.get('enable_splitting', True):
            split_result = await self._run_splitting_stage(
                current_candidates, concept_type
            )
            results.append(split_result)
            if split_result.success:
                current_candidates = split_result.concepts
        
        # Stage 2: Semantic Validation  
        if config.get('enable_validation', True):
            validation_result = await self._run_validation_stage(
                current_candidates, concept_type, text
            )
            results.append(validation_result)
            if validation_result.success:
                current_candidates = validation_result.concepts
        
        # Stage 3: Quality Filtering
        if config.get('enable_filtering', True):
            max_concepts = config.get('max_concepts', 20)
            filtering_result = await self._run_filtering_stage(
                current_candidates, concept_type, max_concepts
            )
            results.append(filtering_result)
            if filtering_result.success:
                current_candidates = filtering_result.concepts
        
        # Stage 4: Relationship Inference (optional)
        if config.get('enable_relationships', False):
            relationship_result = await self._run_relationship_stage(
                current_candidates, concept_type, text
            )
            results.append(relationship_result)
        
        return results
    
    async def _run_splitting_stage(self, 
                                  candidates: List[ConceptCandidate],
                                  concept_type: str) -> ProcessingResult:
        """Run the compound detection and atomic splitting stage."""
        import time
        start_time = time.time()
        
        try:
            # Use the GeneralizedConceptSplitter
            split_candidates = self.splitter.split_concepts(candidates, concept_type)
            
            # Count splits for metadata
            original_count = len(candidates)
            split_count = len(split_candidates)
            compounds_found = sum(1 for c in split_candidates if c.debug.get('atomic_decomposition', False))
            
            metadata = {
                'original_count': original_count,
                'final_count': split_count, 
                'compounds_detected': compounds_found,
                'split_ratio': split_count / original_count if original_count > 0 else 1.0
            }
            
            return ProcessingResult(
                stage=ProcessingStage.ATOMIC_SPLITTING,
                concepts=split_candidates,
                metadata=metadata,
                processing_time=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Splitting stage failed: {e}")
            return ProcessingResult(
                stage=ProcessingStage.ATOMIC_SPLITTING,
                concepts=candidates,  # Return originals on failure
                metadata={},
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _run_validation_stage(self,
                                  candidates: List[ConceptCandidate], 
                                  concept_type: str,
                                  context: str) -> ProcessingResult:
        """Run semantic validation of concepts."""
        import time
        start_time = time.time()
        
        try:
            validated_candidates = []
            validation_stats = {'passed': 0, 'failed': 0, 'total': len(candidates)}
            
            for candidate in candidates:
                is_valid = await self._validate_concept_semantics(
                    candidate, concept_type, context
                )
                
                if is_valid:
                    candidate.debug['validation_passed'] = True
                    validated_candidates.append(candidate)
                    validation_stats['passed'] += 1
                else:
                    candidate.debug['validation_failed'] = True
                    validation_stats['failed'] += 1
                    # Optionally keep failed ones with lower confidence
                    if candidate.confidence > 0.8:  # Keep high-confidence failures
                        candidate.confidence *= 0.5  # Reduce confidence
                        validated_candidates.append(candidate)
            
            return ProcessingResult(
                stage=ProcessingStage.SEMANTIC_VALIDATION,
                concepts=validated_candidates,
                metadata=validation_stats,
                processing_time=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Validation stage failed: {e}")
            return ProcessingResult(
                stage=ProcessingStage.SEMANTIC_VALIDATION,
                concepts=candidates,
                metadata={},
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _run_filtering_stage(self,
                                 candidates: List[ConceptCandidate],
                                 concept_type: str, 
                                 max_concepts: int) -> ProcessingResult:
        """Run quality filtering to select best concepts."""
        import time
        start_time = time.time()
        
        try:
            if len(candidates) <= max_concepts:
                # No filtering needed
                return ProcessingResult(
                    stage=ProcessingStage.QUALITY_FILTERING,
                    concepts=candidates,
                    metadata={'filtered_count': 0, 'kept_all': True},
                    processing_time=time.time() - start_time,
                    success=True
                )
            
            # Apply multi-criteria filtering
            filtered_candidates = self._apply_quality_filters(
                candidates, concept_type, max_concepts
            )
            
            metadata = {
                'original_count': len(candidates),
                'filtered_count': len(filtered_candidates),
                'filter_ratio': len(filtered_candidates) / len(candidates)
            }
            
            return ProcessingResult(
                stage=ProcessingStage.QUALITY_FILTERING,
                concepts=filtered_candidates,
                metadata=metadata,
                processing_time=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Filtering stage failed: {e}")
            return ProcessingResult(
                stage=ProcessingStage.QUALITY_FILTERING,
                concepts=candidates[:max_concepts],  # Simple truncation fallback
                metadata={},
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _run_relationship_stage(self,
                                    candidates: List[ConceptCandidate],
                                    concept_type: str,
                                    context: str) -> ProcessingResult:
        """Run relationship inference between concepts."""
        import time
        start_time = time.time()
        
        try:
            # This would be expanded to infer semantic relationships
            # For now, just add relationship metadata
            for candidate in candidates:
                candidate.debug['relationship_analysis'] = 'pending'
            
            metadata = {
                'concepts_analyzed': len(candidates),
                'relationships_found': 0  # Placeholder
            }
            
            return ProcessingResult(
                stage=ProcessingStage.RELATIONSHIP_INFERENCE,
                concepts=candidates,
                metadata=metadata,
                processing_time=time.time() - start_time,
                success=True
            )
            
        except Exception as e:
            return ProcessingResult(
                stage=ProcessingStage.RELATIONSHIP_INFERENCE,
                concepts=candidates,
                metadata={},
                processing_time=time.time() - start_time,
                success=False,
                error_message=str(e)
            )
    
    async def _validate_concept_semantics(self,
                                        candidate: ConceptCandidate,
                                        concept_type: str, 
                                        context: str) -> bool:
        """Validate individual concept semantics using LLM."""
        
        # Simple heuristic validation for now
        # In a full implementation, this would use LLM chains
        
        label = candidate.label.lower()
        
        # Basic semantic coherence checks
        if len(label.split()) < 2 and concept_type not in ['role', 'resource']:
            return False  # Too short for most concept types
        
        if len(label.split()) > 10:
            return False  # Probably too complex/compound
        
        # Type-specific validation
        if concept_type == 'obligation' and not any(word in label for word in ['shall', 'must', 'should', 'avoid', 'disclose', 'maintain', 'ensure']):
            return False
        
        if concept_type == 'action' and not any(word in label for word in ['disclose', 'avoid', 'maintain', 'perform', 'evaluate', 'consult', 'inform', 'protect']):
            return False
        
        return True
    
    def _apply_quality_filters(self,
                             candidates: List[ConceptCandidate],
                             concept_type: str,
                             max_concepts: int) -> List[ConceptCandidate]:
        """Apply quality-based filtering to select best candidates."""
        
        # Score candidates based on multiple criteria
        scored_candidates = []
        
        for candidate in candidates:
            score = self._calculate_quality_score(candidate, concept_type)
            scored_candidates.append((score, candidate))
        
        # Sort by score (descending) and take top N
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        
        return [candidate for _, candidate in scored_candidates[:max_concepts]]
    
    def _calculate_quality_score(self, 
                               candidate: ConceptCandidate,
                               concept_type: str) -> float:
        """Calculate quality score for a concept candidate."""
        score = candidate.confidence * 100  # Base score from confidence
        
        # Length penalty/bonus
        word_count = len(candidate.label.split())
        if 2 <= word_count <= 6:
            score += 10  # Optimal length
        elif word_count == 1:
            score -= 5   # Might be too generic
        elif word_count > 8:
            score -= 15  # Probably compound
        
        # Specificity bonus
        if candidate.description:
            score += 5
        
        # Source bonus
        if candidate.debug.get('source') == 'provider':
            score += 10  # LLM extraction is generally better
        
        # Atomic decomposition bonus
        if candidate.debug.get('atomic_decomposition'):
            score += 15  # Properly split concepts are valuable
        
        # Validation bonus
        if candidate.debug.get('validation_passed'):
            score += 20
        
        return score


# Integration helper for existing extractors
async def orchestrated_extraction(text: str,
                                concept_type: str, 
                                initial_candidates: List[ConceptCandidate],
                                pipeline_config: Optional[Dict[str, Any]] = None) -> List[ConceptCandidate]:
    """
    Main entry point for orchestrated concept processing.
    
    Usage in existing extractors:
    ```python
    from .langchain_orchestrator import orchestrated_extraction
    
    # After initial extraction
    initial_candidates = self._extract_initial_concepts(text)
    
    # Apply orchestrated processing
    final_candidates = await orchestrated_extraction(
        text, 'obligation', initial_candidates,
        pipeline_config={'enable_splitting': True, 'enable_validation': True}
    )
    
    return final_candidates
    ```
    """
    orchestrator = LangChainConceptOrchestrator()
    
    results = await orchestrator.process_concepts_pipeline(
        text, concept_type, initial_candidates, pipeline_config
    )
    
    # Return concepts from the last successful stage
    for result in reversed(results):
        if result.success:
            return result.concepts
    
    # Fallback to original candidates if all stages failed
    return initial_candidates