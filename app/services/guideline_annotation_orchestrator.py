"""
Guideline Annotation Orchestrator Service

Coordinates the multi-stage pipeline for intelligent guideline annotation
using LLM orchestration and MCP integration.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from app.models import db
from app.models.guideline import Guideline
from app.models import Document
from app.models.guideline_section import GuidelineSection
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.services.guideline_structure_annotation_step import GuidelineStructureAnnotationStep
from app.services.proethica_orchestrator_service import (
    ProEthicaOrchestratorService,
    OntologyContext
)
from app.services.multi_agent_coordinator import MultiAgentCoordinator

logger = logging.getLogger(__name__)


class AnnotationStage(Enum):
    """Stages in the annotation pipeline."""
    SECTION_EXTRACTION = "section_extraction"
    SEMANTIC_ANALYSIS = "semantic_analysis"
    MULTI_AGENT_PROCESSING = "multi_agent_processing"
    VALIDATION_RANKING = "validation_ranking"
    STORAGE = "storage"


@dataclass
class SectionAnalysis:
    """Analysis results for a guideline section."""
    section_code: str
    section_text: str
    identified_components: List[Dict[str, Any]] = field(default_factory=list)
    ontology_matches: List[Dict[str, Any]] = field(default_factory=list)
    agent_analyses: List[Dict[str, Any]] = field(default_factory=list)
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    confidence_score: float = 0.0
    processing_time_ms: int = 0


@dataclass
class AnnotationCandidate:
    """Candidate annotation with metadata."""
    text_segment: str
    start_offset: int
    end_offset: int
    concept_uri: str
    concept_label: str
    concept_definition: str
    concept_type: str
    ontology_name: str
    confidence: float
    reasoning: str
    agent_source: Optional[str] = None
    section_code: Optional[str] = None
    validation_status: str = "pending"


@dataclass
class PipelineResult:
    """Result of the annotation pipeline."""
    guideline_id: int
    total_sections: int
    sections_analyzed: int
    annotations_created: int
    conflicts_resolved: int
    processing_time_ms: int
    errors: List[str] = field(default_factory=list)
    stage_timings: Dict[str, int] = field(default_factory=dict)


class GuidelineAnnotationOrchestrator:
    """
    Orchestrates the intelligent annotation of guidelines using
    multi-agent reasoning and ontological grounding.
    """
    
    def __init__(self, mcp_server_url: Optional[str] = None):
        """
        Initialize the orchestrator.
        
        Args:
            mcp_server_url: URL of the OntServe MCP server
        """
        # Initialize core services
        self.structure_annotator = GuidelineStructureAnnotationStep()
        self.proethica_orchestrator = ProEthicaOrchestratorService(mcp_server_url)
        self.multi_agent_coordinator = MultiAgentCoordinator()
        
        # Configuration
        self.min_confidence_threshold = 0.7
        self.max_annotations_per_section = 10
        self.enable_conflict_resolution = True
        self.enable_validation = True
        
        # Cache for processed sections
        self._section_cache: Dict[str, SectionAnalysis] = {}
        
        logger.info("Guideline Annotation Orchestrator initialized")
    
    async def annotate_guideline(self, 
                                guideline_id: int,
                                force_refresh: bool = False,
                                domain: str = "engineering-ethics") -> PipelineResult:
        """
        Run the complete annotation pipeline for a guideline.
        
        Args:
            guideline_id: ID of the guideline to annotate
            force_refresh: Force re-annotation even if annotations exist
            domain: Professional domain context
            
        Returns:
            Pipeline execution result
        """
        start_time = time.time()
        result = PipelineResult(
            guideline_id=guideline_id,
            total_sections=0,
            sections_analyzed=0,
            annotations_created=0,
            conflicts_resolved=0,
            processing_time_ms=0
        )
        
        try:
            # Load guideline - check both Guideline and Document tables
            guideline = Guideline.query.filter_by(id=guideline_id).first()
            if not guideline:
                # Check Document table for guidelines stored there
                guideline = Document.query.filter_by(id=guideline_id, document_type='guideline').first()
            if not guideline:
                result.errors.append(f"Guideline {guideline_id} not found")
                return result
            
            logger.info(f"Starting intelligent annotation for guideline {guideline_id}")
            
            # Check existing annotations
            if not force_refresh:
                existing = DocumentConceptAnnotation.get_annotations_for_document(
                    'guideline', guideline_id
                )
                if existing and len(existing) > 0:
                    logger.info(f"Guideline {guideline_id} already has {len(existing)} annotations")
                    if not self._should_re_annotate(existing):
                        result.annotations_created = len(existing)
                        return result
            
            # Stage 1: Extract sections
            stage_start = time.time()
            sections = await self._extract_sections(guideline)
            result.total_sections = len(sections)
            result.stage_timings[AnnotationStage.SECTION_EXTRACTION.value] = int(
                (time.time() - stage_start) * 1000
            )
            
            if not sections:
                result.errors.append("No sections extracted from guideline")
                return result
            
            # Stage 2: Semantic analysis per section
            stage_start = time.time()
            section_analyses = await self._analyze_sections(sections, domain)
            result.sections_analyzed = len(section_analyses)
            result.stage_timings[AnnotationStage.SEMANTIC_ANALYSIS.value] = int(
                (time.time() - stage_start) * 1000
            )
            
            # Stage 3: Multi-agent processing
            stage_start = time.time()
            annotation_candidates = await self._multi_agent_processing(
                section_analyses, guideline, domain
            )
            result.stage_timings[AnnotationStage.MULTI_AGENT_PROCESSING.value] = int(
                (time.time() - stage_start) * 1000
            )
            
            # Stage 4: Validation and ranking
            stage_start = time.time()
            validated_annotations, conflicts_resolved = await self._validate_and_rank(
                annotation_candidates
            )
            result.conflicts_resolved = conflicts_resolved
            result.stage_timings[AnnotationStage.VALIDATION_RANKING.value] = int(
                (time.time() - stage_start) * 1000
            )
            
            # Stage 5: Store annotations
            stage_start = time.time()
            stored_annotations = await self._store_annotations(
                validated_annotations, guideline_id, guideline.world_id
            )
            result.annotations_created = len(stored_annotations)
            result.stage_timings[AnnotationStage.STORAGE.value] = int(
                (time.time() - stage_start) * 1000
            )
            
            # Calculate total processing time
            result.processing_time_ms = int((time.time() - start_time) * 1000)
            
            logger.info(
                f"Completed annotation pipeline for guideline {guideline_id}: "
                f"{result.annotations_created} annotations created in {result.processing_time_ms}ms"
            )
            
        except Exception as e:
            logger.exception(f"Error in annotation pipeline: {e}")
            result.errors.append(str(e))
        
        return result
    
    async def _extract_sections(self, guideline: Guideline) -> List[GuidelineSection]:
        """
        Extract structured sections from the guideline.
        
        Args:
            guideline: Guideline model instance
            
        Returns:
            List of extracted sections
        """
        try:
            # Use existing structure annotation service
            result = self.structure_annotator.process(guideline)
            
            if result.get('success'):
                # Load sections from database
                sections = GuidelineSection.query.filter_by(
                    guideline_id=guideline.id
                ).order_by(GuidelineSection.section_order).all()
                
                logger.info(f"Extracted {len(sections)} sections from guideline")
                return sections
            else:
                logger.error(f"Section extraction failed: {result.get('error')}")
                return []
                
        except Exception as e:
            logger.error(f"Error extracting sections: {e}")
            return []
    
    async def _analyze_sections(self, 
                               sections: List[GuidelineSection],
                               domain: str) -> List[SectionAnalysis]:
        """
        Perform semantic analysis on each section.
        
        Args:
            sections: List of guideline sections
            domain: Professional domain
            
        Returns:
            List of section analyses
        """
        analyses = []
        
        for section in sections:
            try:
                # Check cache
                cache_key = f"{section.guideline_id}:{section.section_code}"
                if cache_key in self._section_cache:
                    analyses.append(self._section_cache[cache_key])
                    continue
                
                # Analyze section with ProEthica orchestrator
                start_time = time.time()
                
                # Build query from section text
                query = f"Analyze this guideline section for ethical concepts: {section.section_text}"
                
                # Get orchestrated response
                response = await self.proethica_orchestrator.process_query(
                    query=query,
                    domain=domain,
                    use_cache=True
                )
                
                # Extract components and matches
                analysis = SectionAnalysis(
                    section_code=section.section_code,
                    section_text=section.section_text,
                    identified_components=[
                        {
                            'type': comp.type.value,
                            'text': comp.text,
                            'confidence': comp.confidence
                        }
                        for comp in response.ontology_context.query_analysis.identified_components
                    ],
                    ontology_matches=self._extract_ontology_matches(response.ontology_context),
                    confidence_score=response.confidence,
                    processing_time_ms=int((time.time() - start_time) * 1000)
                )
                
                # Cache the analysis
                self._section_cache[cache_key] = analysis
                analyses.append(analysis)
                
                logger.debug(f"Analyzed section {section.section_code}: {len(analysis.ontology_matches)} matches")
                
            except Exception as e:
                logger.error(f"Error analyzing section {section.section_code}: {e}")
                continue
        
        return analyses
    
    def _extract_ontology_matches(self, context: OntologyContext) -> List[Dict[str, Any]]:
        """
        Extract ontology matches from context.
        
        Args:
            context: Ontology context from orchestrator
            
        Returns:
            List of ontology matches
        """
        matches = []
        
        for category, entities in context.retrieved_entities.items():
            for entity in entities:
                matches.append({
                    'category': category,
                    'uri': entity.get('uri'),
                    'label': entity.get('label'),
                    'description': entity.get('description', ''),
                    'ontology': entity.get('ontology', 'unknown')
                })
        
        return matches
    
    async def _multi_agent_processing(self,
                                     section_analyses: List[SectionAnalysis],
                                     guideline: Guideline,
                                     domain: str) -> List[AnnotationCandidate]:
        """
        Process sections through multi-agent coordinator.
        
        Args:
            section_analyses: Analyzed sections
            guideline: Guideline instance
            domain: Professional domain
            
        Returns:
            List of annotation candidates
        """
        all_candidates = []
        
        for analysis in section_analyses:
            try:
                # Build components dictionary for multi-agent processing
                components = {}
                for comp in analysis.identified_components:
                    comp_type = comp['type'].lower()
                    if comp_type not in components:
                        components[comp_type] = []
                    components[comp_type].append(comp['text'])
                
                # Build ontology context
                ontology_context = {
                    category: [
                        {
                            'uri': match['uri'],
                            'label': match['label'],
                            'description': match['description']
                        }
                        for match in analysis.ontology_matches
                        if match['category'] == category
                    ]
                    for category in set(match['category'] for match in analysis.ontology_matches)
                }
                
                # Process with multi-agent coordinator
                agent_result = await self.multi_agent_coordinator.process(
                    query=analysis.section_text,
                    components=components,
                    ontology_context=ontology_context,
                    domain=domain
                )
                
                # Store agent analyses
                analysis.agent_analyses = agent_result.get('agent_analyses', [])
                analysis.conflicts = agent_result.get('conflicts_identified', [])
                
                # Extract annotation candidates from agent results
                candidates = self._extract_candidates_from_agents(
                    agent_result,
                    analysis,
                    guideline.content
                )
                
                all_candidates.extend(candidates)
                
                logger.debug(
                    f"Multi-agent processing for section {analysis.section_code}: "
                    f"{len(candidates)} candidates"
                )
                
            except Exception as e:
                logger.error(f"Error in multi-agent processing for section {analysis.section_code}: {e}")
                continue
        
        return all_candidates
    
    def _extract_candidates_from_agents(self,
                                       agent_result: Dict[str, Any],
                                       section_analysis: SectionAnalysis,
                                       full_content: str) -> List[AnnotationCandidate]:
        """
        Extract annotation candidates from agent results.
        
        Args:
            agent_result: Result from multi-agent processing
            section_analysis: Section analysis data
            full_content: Full guideline content for offset calculation
            
        Returns:
            List of annotation candidates
        """
        candidates = []
        
        # Process each agent's analysis
        for agent_analysis in agent_result.get('agent_analyses', []):
            agent_type = agent_analysis.get('agent_type', 'unknown')
            
            for concept in agent_analysis.get('concepts_identified', []):
                try:
                    # Find text segment in section
                    text_segment = self._find_text_segment(
                        section_analysis.section_text,
                        concept.get('label', '')
                    )
                    
                    if not text_segment:
                        continue
                    
                    # Calculate offsets in full content
                    start_offset = full_content.find(text_segment)
                    if start_offset == -1:
                        continue
                    
                    end_offset = start_offset + len(text_segment)
                    
                    # Create annotation candidate
                    candidate = AnnotationCandidate(
                        text_segment=text_segment,
                        start_offset=start_offset,
                        end_offset=end_offset,
                        concept_uri=concept.get('uri', ''),
                        concept_label=concept.get('label', ''),
                        concept_definition=concept.get('description', ''),
                        concept_type=concept.get('type', 'Unknown'),
                        ontology_name='proethica-core',  # Default, should be extracted
                        confidence=agent_analysis.get('confidence', 0.5),
                        reasoning=agent_analysis.get('interpretation', ''),
                        agent_source=agent_type,
                        section_code=section_analysis.section_code
                    )
                    
                    candidates.append(candidate)
                    
                except Exception as e:
                    logger.debug(f"Error extracting candidate from concept: {e}")
                    continue
        
        return candidates
    
    def _find_text_segment(self, section_text: str, concept_label: str) -> Optional[str]:
        """
        Find relevant text segment for a concept in section text.
        
        Args:
            section_text: Text of the section
            concept_label: Label of the concept
            
        Returns:
            Matching text segment or None
        """
        # Simple implementation - can be enhanced with NLP
        import re
        
        # Try to find concept words in text
        words = concept_label.lower().split()
        
        for word in words:
            if len(word) > 3:  # Skip short words
                pattern = r'\b' + re.escape(word) + r'\b'
                match = re.search(pattern, section_text, re.IGNORECASE)
                if match:
                    # Return a window around the match
                    start = max(0, match.start() - 20)
                    end = min(len(section_text), match.end() + 20)
                    return section_text[start:end].strip()
        
        return None
    
    async def _validate_and_rank(self,
                                candidates: List[AnnotationCandidate]) -> Tuple[List[AnnotationCandidate], int]:
        """
        Validate and rank annotation candidates.
        
        Args:
            candidates: List of annotation candidates
            
        Returns:
            Tuple of (validated candidates, conflicts resolved count)
        """
        conflicts_resolved = 0
        
        # Remove duplicates based on URI and text segment
        seen = set()
        unique_candidates = []
        
        for candidate in candidates:
            key = (candidate.concept_uri, candidate.text_segment, candidate.start_offset)
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)
            else:
                conflicts_resolved += 1
        
        # Filter by confidence threshold
        validated = [
            c for c in unique_candidates 
            if c.confidence >= self.min_confidence_threshold
        ]
        
        # Sort by confidence (highest first)
        validated.sort(key=lambda x: x.confidence, reverse=True)
        
        # Apply max annotations per section limit
        section_counts = {}
        final_candidates = []
        
        for candidate in validated:
            section = candidate.section_code
            if section not in section_counts:
                section_counts[section] = 0
            
            if section_counts[section] < self.max_annotations_per_section:
                final_candidates.append(candidate)
                section_counts[section] += 1
        
        logger.info(f"Validated {len(final_candidates)} annotations, resolved {conflicts_resolved} conflicts")
        return final_candidates, conflicts_resolved
    
    async def _store_annotations(self,
                                candidates: List[AnnotationCandidate],
                                guideline_id: int,
                                world_id: int) -> List[DocumentConceptAnnotation]:
        """
        Store annotation candidates in the database.
        
        Args:
            candidates: Validated annotation candidates
            guideline_id: ID of the guideline
            world_id: ID of the world
            
        Returns:
            List of stored annotations
        """
        stored = []
        
        try:
            # Mark existing annotations as superseded
            existing = DocumentConceptAnnotation.get_annotations_for_document(
                'guideline', guideline_id
            )
            for ann in existing:
                ann.is_current = False
            
            # Create new annotations
            for candidate in candidates:
                annotation = DocumentConceptAnnotation(
                    document_type='guideline',
                    document_id=guideline_id,
                    world_id=world_id,
                    text_segment=candidate.text_segment,
                    start_offset=candidate.start_offset,
                    end_offset=candidate.end_offset,
                    ontology_name=candidate.ontology_name,
                    concept_uri=candidate.concept_uri,
                    concept_label=candidate.concept_label,
                    concept_definition=candidate.concept_definition,
                    concept_type=candidate.concept_type,
                    confidence=candidate.confidence,
                    llm_model='multi-agent-orchestrator',
                    llm_reasoning=candidate.reasoning,
                    validation_status=candidate.validation_status,
                    is_current=True
                )
                
                # Add section metadata
                if hasattr(annotation, 'metadata'):
                    annotation.metadata = {
                        'section_code': candidate.section_code,
                        'agent_source': candidate.agent_source
                    }
                
                db.session.add(annotation)
                stored.append(annotation)
            
            db.session.commit()
            logger.info(f"Stored {len(stored)} annotations for guideline {guideline_id}")
            
        except Exception as e:
            logger.error(f"Error storing annotations: {e}")
            db.session.rollback()
            stored = []
        
        return stored
    
    def _should_re_annotate(self, existing_annotations: List[DocumentConceptAnnotation]) -> bool:
        """
        Check if re-annotation is needed.
        
        Args:
            existing_annotations: Existing annotations
            
        Returns:
            True if re-annotation should proceed
        """
        # Check if annotations are from old model
        for ann in existing_annotations:
            if ann.llm_model in ['keyword_matching', 'simple']:
                return True
        
        # Check if annotations are old (e.g., > 30 days)
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(days=30)
        for ann in existing_annotations:
            if ann.created_at < cutoff:
                return True
        
        return False
    
    def clear_cache(self):
        """Clear the section analysis cache."""
        self._section_cache.clear()
        logger.info("Section cache cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            'cache_size': len(self._section_cache),
            'min_confidence_threshold': self.min_confidence_threshold,
            'max_annotations_per_section': self.max_annotations_per_section,
            'enable_conflict_resolution': self.enable_conflict_resolution,
            'enable_validation': self.enable_validation
        }
