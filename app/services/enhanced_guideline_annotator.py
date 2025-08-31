"""
Enhanced Guideline Annotator Service

Provides advanced annotation capabilities for guidelines using
multi-agent orchestration, context engineering, and dynamic
ontology matching through the MCP integration.
"""

import logging
import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import aiohttp

from app.models import db
from app.models.guideline import Guideline
from app.models.document import Document
from app.models.guideline_section import GuidelineSection
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.services.multi_agent_coordinator import MultiAgentCoordinator
from app.services.proethica_orchestrator_service import ProEthicaOrchestratorService

logger = logging.getLogger(__name__)


@dataclass
class ContextWindow:
    """Represents a context window for annotation."""
    section_id: int
    section_code: str
    current_text: str
    previous_text: Optional[str] = None
    next_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    semantic_features: Dict[str, Any] = field(default_factory=dict)


@dataclass
class OntologyMatch:
    """Represents a match between text and ontology concept."""
    text_segment: str
    concept_uri: str
    concept_label: str
    concept_type: str
    ontology_name: str
    similarity_score: float
    hierarchical_level: int = 0
    related_concepts: List[str] = field(default_factory=list)
    context_relevance: float = 0.0


@dataclass
class AnnotationCandidate:
    """Enhanced annotation candidate with rich metadata."""
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
    agent_sources: List[str] = field(default_factory=list)
    context_window: Optional[ContextWindow] = None
    ontology_match: Optional[OntologyMatch] = None
    consensus_score: float = 0.0
    validation_status: str = "pending"


class ContextEngine:
    """
    Builds rich context windows for annotation processing.
    """
    
    def __init__(self):
        self.window_size = 3  # Number of sections to include
        self.feature_extractors = {
            'entities': self._extract_entities,
            'keywords': self._extract_keywords,
            'sentiment': self._extract_sentiment,
            'structure': self._extract_structure
        }
    
    def build_contexts(self, sections: List[GuidelineSection]) -> List[ContextWindow]:
        """
        Build context windows from guideline sections.
        
        Args:
            sections: List of guideline sections
            
        Returns:
            List of context windows
        """
        contexts = []
        
        for i, section in enumerate(sections):
            # Get surrounding sections
            previous_text = sections[i-1].section_text if i > 0 else None
            next_text = sections[i+1].section_text if i < len(sections)-1 else None
            
            # Extract metadata
            metadata = self._extract_metadata(section)
            
            # Extract semantic features
            semantic_features = self._extract_features(section.section_text)
            
            # Create context window
            context = ContextWindow(
                section_id=section.id,
                section_code=section.section_code,
                current_text=section.section_text,
                previous_text=previous_text,
                next_text=next_text,
                metadata=metadata,
                semantic_features=semantic_features
            )
            
            contexts.append(context)
        
        return contexts
    
    def _extract_metadata(self, section: GuidelineSection) -> Dict[str, Any]:
        """Extract metadata from a section."""
        return {
            'section_number': section.section_code,
            'section_type': self._determine_section_type(section.section_code),
            'length': len(section.section_text),
            'position': section.section_order
        }
    
    def _determine_section_type(self, section_code: str) -> str:
        """Determine the type of section based on its code."""
        code_lower = section_code.lower()
        if 'intro' in code_lower or code_lower == '1':
            return 'introduction'
        elif 'conclu' in code_lower:
            return 'conclusion'
        elif 'defin' in code_lower:
            return 'definitions'
        elif 'oblig' in code_lower or 'duty' in code_lower:
            return 'obligations'
        elif 'princ' in code_lower:
            return 'principles'
        else:
            return 'general'
    
    def _extract_features(self, text: str) -> Dict[str, Any]:
        """Extract semantic features from text."""
        features = {}
        for feature_name, extractor in self.feature_extractors.items():
            try:
                features[feature_name] = extractor(text)
            except Exception as e:
                logger.warning(f"Failed to extract {feature_name}: {e}")
                features[feature_name] = None
        return features
    
    def _extract_entities(self, text: str) -> List[str]:
        """Extract named entities from text."""
        # Simplified entity extraction - in production, use NLP
        import re
        # Look for capitalized words that might be entities
        entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        return list(set(entities))[:10]  # Limit to top 10
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text."""
        # Simplified keyword extraction
        keywords = []
        ethical_terms = [
            'obligation', 'duty', 'responsibility', 'principle',
            'must', 'shall', 'should', 'required', 'prohibited',
            'ethical', 'professional', 'safety', 'integrity'
        ]
        
        text_lower = text.lower()
        for term in ethical_terms:
            if term in text_lower:
                keywords.append(term)
        
        return keywords
    
    def _extract_sentiment(self, text: str) -> Dict[str, float]:
        """Extract sentiment from text."""
        # Simplified sentiment analysis
        positive_words = ['good', 'excellent', 'important', 'beneficial', 'positive']
        negative_words = ['bad', 'harmful', 'dangerous', 'prohibited', 'negative']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        if total == 0:
            return {'positive': 0.5, 'negative': 0.5, 'neutral': 0.0}
        
        return {
            'positive': positive_count / total,
            'negative': negative_count / total,
            'neutral': 0.0
        }
    
    def _extract_structure(self, text: str) -> Dict[str, Any]:
        """Extract structural features from text."""
        import re
        return {
            'has_list': bool(re.search(r'^\s*[-•*]\s+', text, re.MULTILINE)),
            'has_numbering': bool(re.search(r'^\s*\d+[.)]\s+', text, re.MULTILINE)),
            'paragraph_count': len(re.split(r'\n\s*\n', text)),
            'sentence_count': len(re.split(r'[.!?]+', text))
        }


class OntologyMatcher:
    """
    Matches text segments to ontology concepts using MCP integration.
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8082"):
        self.mcp_server_url = mcp_server_url
        self.similarity_threshold = 0.75
        self.max_candidates = 10
        
    async def match_concepts(self, 
                            text_segment: str,
                            component_type: str,
                            context: Optional[ContextWindow] = None,
                            domain: str = "engineering-ethics") -> List[OntologyMatch]:
        """
        Match text segment to ontology concepts.
        
        Args:
            text_segment: Text to match
            component_type: Type of component to match
            context: Optional context window
            domain: Professional domain
            
        Returns:
            List of ontology matches
        """
        matches = []
        
        try:
            # Get candidate concepts from MCP
            candidates = await self._get_candidates_from_mcp(component_type, domain)
            
            if not candidates:
                logger.warning(f"No candidates found for {component_type} in {domain}")
                return matches
            
            # Calculate similarity scores
            for candidate in candidates[:self.max_candidates]:
                similarity = self._calculate_similarity(text_segment, candidate)
                
                if similarity >= self.similarity_threshold:
                    # Apply context-aware adjustments
                    if context:
                        context_relevance = self._calculate_context_relevance(
                            candidate, context
                        )
                    else:
                        context_relevance = 0.5
                    
                    # Create match
                    match = OntologyMatch(
                        text_segment=text_segment,
                        concept_uri=candidate.get('uri', ''),
                        concept_label=candidate.get('label', ''),
                        concept_type=component_type,
                        ontology_name=candidate.get('ontology', 'proethica-core'),
                        similarity_score=similarity,
                        context_relevance=context_relevance
                    )
                    
                    matches.append(match)
            
            # Sort by combined score
            matches.sort(
                key=lambda m: (m.similarity_score + m.context_relevance) / 2,
                reverse=True
            )
            
        except Exception as e:
            logger.error(f"Error matching concepts: {e}")
        
        return matches
    
    async def _get_candidates_from_mcp(self, 
                                      category: str,
                                      domain: str) -> List[Dict[str, Any]]:
        """Get candidate concepts from MCP server."""
        url = f"{self.mcp_server_url}/jsonrpc"
        payload = {
            "jsonrpc": "2.0",
            "method": "call_tool",
            "params": {
                "name": "get_entities_by_category",
                "arguments": {
                    "category": category,
                    "domain_id": domain,
                    "status": "approved"
                }
            },
            "id": 1
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = json.loads(data['result']['content'][0]['text'])
                        return result.get('entities', [])
        except Exception as e:
            logger.error(f"Failed to get candidates from MCP: {e}")
        
        return []
    
    def _calculate_similarity(self, text: str, candidate: Dict[str, Any]) -> float:
        """Calculate semantic similarity between text and candidate."""
        # Simplified similarity calculation
        # In production, use embeddings or more sophisticated methods
        text_lower = text.lower()
        label_lower = candidate.get('label', '').lower()
        description_lower = candidate.get('description', '').lower()
        
        score = 0.0
        
        # Check label match
        if label_lower in text_lower:
            score += 0.5
        
        # Check for key words from label
        label_words = label_lower.split()
        matching_words = sum(1 for word in label_words if word in text_lower)
        if label_words:
            score += 0.3 * (matching_words / len(label_words))
        
        # Check description relevance
        if description_lower:
            desc_words = description_lower.split()[:10]  # First 10 words
            desc_matches = sum(1 for word in desc_words if word in text_lower)
            if desc_words:
                score += 0.2 * (desc_matches / len(desc_words))
        
        return min(score, 1.0)
    
    def _calculate_context_relevance(self, 
                                    candidate: Dict[str, Any],
                                    context: ContextWindow) -> float:
        """Calculate relevance based on context."""
        relevance = 0.5  # Base relevance
        
        # Check section type alignment
        section_type = context.metadata.get('section_type', 'general')
        label_lower = candidate.get('label', '').lower()
        
        if section_type == 'obligations' and 'obligation' in label_lower:
            relevance += 0.2
        elif section_type == 'principles' and 'principle' in label_lower:
            relevance += 0.2
        
        # Check keyword alignment
        keywords = context.semantic_features.get('keywords', [])
        for keyword in keywords:
            if keyword in label_lower:
                relevance += 0.1
                break
        
        # Check surrounding context
        if context.previous_text:
            if candidate.get('label', '') in context.previous_text:
                relevance += 0.1
        
        if context.next_text:
            if candidate.get('label', '') in context.next_text:
                relevance += 0.1
        
        return min(relevance, 1.0)


class EnhancedGuidelineAnnotator:
    """
    Enhanced annotator with better ontology integration and context awareness.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the enhanced annotator.
        
        Args:
            config: Optional configuration dictionary
        """
        self.config = config or self._get_default_config()
        
        # Initialize components
        self.context_engine = ContextEngine()
        self.ontology_matcher = OntologyMatcher(
            mcp_server_url=self.config.get('mcp_server_url', 'http://localhost:8082')
        )
        self.multi_agent = MultiAgentCoordinator()
        self.orchestrator = ProEthicaOrchestratorService()
        
        # Configuration parameters
        self.min_confidence = self.config.get('min_confidence', 0.6)
        self.max_annotations_per_section = self.config.get('max_annotations_per_section', 5)
        self.enable_conflict_resolution = self.config.get('enable_conflict_resolution', True)
        
        logger.info("Enhanced Guideline Annotator initialized")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            'mcp_server_url': 'http://localhost:8082',
            'min_confidence': 0.6,
            'max_annotations_per_section': 5,
            'enable_conflict_resolution': True,
            'domain': 'engineering-ethics',
            'use_cache': True,
            'batch_size': 10
        }
    
    async def annotate_guideline(self, 
                                guideline_id: int,
                                force_refresh: bool = False) -> Dict[str, Any]:
        """
        Annotate a guideline with enhanced pipeline.
        
        Args:
            guideline_id: ID of the guideline
            force_refresh: Force re-annotation
            
        Returns:
            Annotation results
        """
        start_time = time.time()
        
        try:
            # Load guideline
            guideline = await self._load_guideline(guideline_id)
            if not guideline:
                return {
                    'success': False,
                    'error': f'Guideline {guideline_id} not found'
                }
            
            # Check existing annotations
            if not force_refresh:
                existing = await self._check_existing_annotations(guideline_id)
                if existing and len(existing) > 0:
                    return {
                        'success': True,
                        'message': 'Using existing annotations',
                        'annotations': existing,
                        'count': len(existing)
                    }
            
            # Extract sections
            sections = await self._extract_sections(guideline)
            if not sections:
                return {
                    'success': False,
                    'error': 'No sections extracted from guideline'
                }
            
            # Build context windows
            contexts = self.context_engine.build_contexts(sections)
            
            # Multi-agent analysis
            analyses = await self._multi_agent_analysis(contexts)
            
            # Ontology matching
            matches = await self._match_to_ontology(analyses, contexts)
            
            # Generate annotation candidates
            candidates = self._generate_candidates(matches, guideline.content)
            
            # Validate and rank
            validated = self._validate_and_rank(candidates)
            
            # Store annotations
            stored = await self._store_annotations(validated, guideline_id, guideline.world_id)
            
            # Calculate metrics
            processing_time = int((time.time() - start_time) * 1000)
            
            return {
                'success': True,
                'guideline_id': guideline_id,
                'total_sections': len(sections),
                'sections_analyzed': len(contexts),
                'annotations_created': len(stored),
                'processing_time_ms': processing_time,
                'annotations': [self._serialize_annotation(a) for a in stored]
            }
            
        except Exception as e:
            logger.exception(f"Error annotating guideline {guideline_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _load_guideline(self, guideline_id: int):
        """Load guideline from database."""
        # Check both Guideline and Document tables
        guideline = Guideline.query.filter_by(id=guideline_id).first()
        if not guideline:
            guideline = Document.query.filter_by(
                id=guideline_id, 
                document_type='guideline'
            ).first()
        return guideline
    
    async def _check_existing_annotations(self, guideline_id: int):
        """Check for existing annotations."""
        return DocumentConceptAnnotation.get_annotations_for_document(
            'guideline', guideline_id
        )
    
    async def _extract_sections(self, guideline):
        """Extract sections from guideline."""
        sections = GuidelineSection.query.filter_by(
            guideline_id=guideline.id
        ).order_by(GuidelineSection.section_order).all()
        return sections
    
    async def _multi_agent_analysis(self, contexts: List[ContextWindow]) -> List[Dict[str, Any]]:
        """Perform multi-agent analysis on contexts."""
        analyses = []
        
        for context in contexts:
            try:
                # Build query from context
                query = context.current_text
                
                # Get orchestrated analysis
                response = await self.orchestrator.process_query(
                    query=query,
                    domain=self.config.get('domain', 'engineering-ethics'),
                    use_cache=self.config.get('use_cache', True)
                )
                
                # Extract components
                components = {}
                for comp in response.ontology_context.query_analysis.identified_components:
                    comp_type = comp.type.value
                    if comp_type not in components:
                        components[comp_type] = []
                    components[comp_type].append(comp.text)
                
                # Get multi-agent analysis
                agent_result = await self.multi_agent.process(
                    query=query,
                    components=components,
                    ontology_context=response.ontology_context.retrieved_entities,
                    domain=self.config.get('domain', 'engineering-ethics')
                )
                
                analyses.append({
                    'context': context,
                    'orchestrator_response': response,
                    'agent_result': agent_result
                })
                
            except Exception as e:
                logger.error(f"Error in multi-agent analysis: {e}")
                continue
        
        return analyses
    
    async def _match_to_ontology(self, 
                                analyses: List[Dict[str, Any]],
                                contexts: List[ContextWindow]) -> List[Dict[str, Any]]:
        """Match analyses to ontology concepts."""
        all_matches = []
        
        for analysis in analyses:
            context = analysis['context']
            agent_result = analysis['agent_result']
            
            # Extract identified components
            for agent_analysis in agent_result.get('agent_analyses', []):
                for concept in agent_analysis.get('concepts_identified', []):
                    # Find relevant text segment
                    text_segment = self._find_text_segment(
                        context.current_text,
                        concept.get('label', '')
                    )
                    
                    if text_segment:
                        # Match to ontology
                        matches = await self.ontology_matcher.match_concepts(
                            text_segment=text_segment,
                            component_type=concept.get('type', 'Unknown'),
                            context=context,
                            domain=self.config.get('domain', 'engineering-ethics')
                        )
                        
                        for match in matches:
                            all_matches.append({
                                'match': match,
                                'context': context,
                                'agent_source': agent_analysis.get('agent_type', 'unknown')
                            })
        
        return all_matches
    
    def _find_text_segment(self, text: str, concept_label: str) -> Optional[str]:
        """Find relevant text segment for a concept."""
        import re
        
        # Try to find concept words in text
        words = concept_label.lower().split()
        
        for word in words:
            if len(word) > 3:  # Skip short words
                pattern = r'\b' + re.escape(word) + r'\b'
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    # Return a window around the match
                    start = max(0, match.start() - 30)
                    end = min(len(text), match.end() + 30)
                    return text[start:end].strip()
        
        return None
    
    def _generate_candidates(self, 
                           matches: List[Dict[str, Any]],
                           full_content: str) -> List[AnnotationCandidate]:
        """Generate annotation candidates from matches."""
        candidates = []
        
        for match_data in matches:
            match = match_data['match']
            context = match_data['context']
            agent_source = match_data['agent_source']
            
            # Calculate offsets
            start_offset = full_content.find(match.text_segment)
            if start_offset == -1:
                continue
            end_offset = start_offset + len(match.text_segment)
            
            # Create candidate
            candidate = AnnotationCandidate(
                text_segment=match.text_segment,
                start_offset=start_offset,
                end_offset=end_offset,
                concept_uri=match.concept_uri,
                concept_label=match.concept_label,
                concept_definition="",  # Will be filled from ontology
                concept_type=match.concept_type,
                ontology_name=match.ontology_name,
                confidence=(match.similarity_score + match.context_relevance) / 2,
                reasoning=f"Matched by {agent_source} agent with similarity {match.similarity_score:.2f}",
                agent_sources=[agent_source],
                context_window=context,
                ontology_match=match,
                consensus_score=match.similarity_score
            )
            
            candidates.append(candidate)
        
        return candidates
    
    def _validate_and_rank(self, candidates: List[AnnotationCandidate]) -> List[AnnotationCandidate]:
        """Validate and rank annotation candidates."""
        # Filter by confidence
        validated = [c for c in candidates if c.confidence >= self.min_confidence]
        
        # Remove duplicates
        seen = set()
        unique = []
        for candidate in validated:
            key = (candidate.concept_uri, candidate.text_segment)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        
        # Sort by confidence
        unique.sort(key=lambda c: c.confidence, reverse=True)
        
        # Apply per-section limit
        section_counts = {}
        final = []
        
        for candidate in unique:
            section = candidate.context_window.section_code if candidate.context_window else 'unknown'
            if section not in section_counts:
                section_counts[section] = 0
            
            if section_counts[section] < self.max_annotations_per_section:
                final.append(candidate)
                section_counts[section] += 1
        
        return final
    
    async def _store_annotations(self, 
                                candidates: List[AnnotationCandidate],
                                guideline_id: int,
                                world_id: int) -> List[DocumentConceptAnnotation]:
        """Store annotations in database."""
        stored = []
        
        try:
            # Mark existing as superseded
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
                    llm_model='enhanced-multi-agent',
                    llm_reasoning=candidate.reasoning,
                    validation_status=candidate.validation_status,
                    is_current=True
                )
                
                db.session.add(annotation)
                stored.append(annotation)
            
            db.session.commit()
            logger.info(f"Stored {len(stored)} annotations for guideline {guideline_id}")
            
        except Exception as e:
            logger.error(f"Error storing annotations: {e}")
            db.session.rollback()
            stored = []
        
        return stored
    
    def _serialize_annotation(self, annotation: DocumentConceptAnnotation) -> Dict[str, Any]:
        """Serialize annotation for response."""
        return {
            'id': annotation.id,
            'text_segment': annotation.text_segment,
            'start_offset': annotation.start_offset,
            'end_offset': annotation.end_offset,
            'concept_uri': annotation.concept_uri,
            'concept_label': annotation.concept_label,
            'concept_type': annotation.concept_type,
            'confidence': annotation.confidence,
            'created_at': annotation.created_at.isoformat() if annotation.created_at else None
        }
