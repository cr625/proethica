"""
Section-specific processors for case analysis
Implements specialized extraction logic for each case section type
"""

from typing import Dict, List, Optional, Any
import logging
from abc import ABC, abstractmethod

from .case_pipeline import BaseSectionProcessor

logger = logging.getLogger(__name__)


class FactsProcessor(BaseSectionProcessor):
    """
    Processes facts section - primary source for states, events, and contextual roles
    Focus: Environmental conditions, temporal sequence, key actors
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process facts section with emphasis on contextual elements"""
        
        logger.info("Processing facts section")
        
        # Facts section primarily establishes context
        extraction_weights = {
            'states': 0.4,      # Primary focus - environmental conditions
            'roles': 0.25,      # Key actors and their relationships
            'events': 0.25,     # Temporal sequence and occurrences
            'resources': 0.1    # Referenced documents/standards
        }
        
        # Build extraction prompt focusing on factual elements
        factual_prompt = self._build_factual_extraction_prompt(text, extraction_weights)
        
        return {
            'section_type': 'facts',
            'extraction_approach': 'contextual_foundation',
            'primary_focus': ['states', 'roles', 'events'],
            'extraction_prompt': factual_prompt,
            'processing_notes': [
                'Establishes environmental context',
                'Identifies key stakeholder roles',
                'Maps temporal sequence of events',
                'Provides foundation for normative analysis'
            ],
            'entities': []  # Will be populated by actual extraction
        }
    
    def _build_factual_extraction_prompt(self, text: str, weights: Dict[str, float]) -> str:
        """Build extraction prompt optimized for factual analysis"""
        return f"""
        ## FACTS SECTION ANALYSIS
        
        Extract contextual foundation elements from this factual description:
        
        {text}
        
        **EXTRACTION PRIORITIES** (weighted by relevance):
        - States ({weights['states']:.1f}): Environmental conditions, risk situations, conflict states
        - Roles ({weights['roles']:.1f}): Key actors and their professional relationships
        - Events ({weights['events']:.1f}): Temporal occurrences and triggering incidents
        - Resources ({weights['resources']:.1f}): Referenced standards, codes, documents
        
        **FOCUS**: Establish the contextual framework - WHO is involved, WHAT conditions exist, WHEN things occurred.
        """


class DiscussionProcessor(BaseSectionProcessor):
    """
    Processes discussion section with dual analysis approach
    Implements independent + contextual analysis for comprehensive understanding
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process discussion with dual analysis approach"""
        
        logger.info("Processing discussion section with dual analysis")
        
        # Phase 1: Independent extraction
        independent_entities = self._extract_independent(text)
        
        # Phase 2: Context-aware extraction (if facts context provided)
        contextual_entities = None
        if context and 'facts' in context:
            contextual_entities = self._extract_with_facts_context(text, context['facts'])
        
        # Phase 3: Consolidation and insight synthesis
        consolidated_results = self._consolidate_discussion_extractions(
            independent_entities, 
            contextual_entities
        )
        
        return {
            'section_type': 'discussion',
            'extraction_approach': 'dual_analysis',
            'independent_results': independent_entities,
            'contextual_results': contextual_entities,
            'consolidated_results': consolidated_results,
            'processing_notes': [
                'Independent analysis captures discussion-specific insights',
                'Contextual analysis reveals fact-discussion relationships',
                'Consolidation identifies tensions and elaborations'
            ]
        }
    
    def _extract_independent(self, text: str) -> Dict[str, Any]:
        """Extract entities from discussion independently of other sections"""
        
        # Discussion typically reveals professional reasoning
        extraction_weights = {
            'principles': 0.3,    # Ethical foundations and reasoning
            'obligations': 0.3,   # Professional duties identified
            'constraints': 0.2,   # Limitations and boundaries revealed
            'roles': 0.2         # Professional identities in ethical reasoning
        }
        
        independent_prompt = f"""
        ## INDEPENDENT DISCUSSION ANALYSIS
        
        Analyze this professional ethics discussion independently:
        
        {text}
        
        **FOCUS**: Extract the ethical reasoning, professional judgments, and normative insights 
        that emerge from the discussion itself, without reference to other sections.
        
        **EXTRACTION PRIORITIES**:
        - Principles ({extraction_weights['principles']:.1f}): Ethical foundations and values invoked
        - Obligations ({extraction_weights['obligations']:.1f}): Professional duties identified
        - Constraints ({extraction_weights['constraints']:.1f}): Limitations and ethical boundaries
        - Roles ({extraction_weights['roles']:.1f}): Professional identities in ethical context
        
        **KEY QUESTION**: What new ethical insights does this discussion contribute?
        """
        
        return {
            'extraction_type': 'independent',
            'primary_focus': ['principles', 'obligations', 'constraints', 'roles'],
            'extraction_prompt': independent_prompt,
            'entities': []  # Will be populated by actual extraction
        }
    
    def _extract_with_facts_context(self, text: str, facts_context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract entities with awareness of established factual context"""
        
        contextual_prompt = f"""
        ## CONTEXTUAL DISCUSSION ANALYSIS
        
        **ESTABLISHED FACTUAL CONTEXT:**
        {facts_context}
        
        **DISCUSSION TO ANALYZE:**
        {text}
        
        **CONTEXTUAL ANALYSIS OBJECTIVES**:
        1. **Elaboration**: How does the discussion elaborate on factual obligations?
        2. **Extension**: What new ethical considerations does the discussion introduce?
        3. **Tension**: What tensions between principles does the discussion reveal?
        4. **Resolution**: How does the discussion resolve conflicts identified in facts?
        
        **FOCUS**: Identify the relationship between factual circumstances and ethical reasoning.
        Extract entities that show how professional judgment applies to specific situations.
        """
        
        return {
            'extraction_type': 'contextual',
            'facts_context': facts_context,
            'analysis_objectives': ['elaboration', 'extension', 'tension', 'resolution'],
            'extraction_prompt': contextual_prompt,
            'entities': []  # Will be populated by actual extraction
        }
    
    def _consolidate_discussion_extractions(self, independent: Dict[str, Any], 
                                          contextual: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Consolidate independent and contextual extractions"""
        
        if not contextual:
            return independent
            
        consolidation_strategy = {
            'merge_approach': 'enrichment',  # Contextual enriches independent
            'conflict_resolution': 'preserve_both',  # Keep conflicting interpretations
            'insight_synthesis': 'layered_understanding'  # Build layered insights
        }
        
        return {
            'consolidation_strategy': consolidation_strategy,
            'independent_insights': independent.get('entities', []),
            'contextual_insights': contextual.get('entities', []),
            'enriched_entities': [],  # Merged and enriched entities
            'identified_tensions': [],  # Conflicts between perspectives
            'synthesis_notes': [
                'Discussion provides professional reasoning framework',
                'Context reveals application to specific circumstances',
                'Tensions highlight ethical complexity'
            ]
        }


class QuestionsProcessor(BaseSectionProcessor):
    """
    Processes questions section - focuses on capabilities and decision points
    Reveals required competencies and action-oriented considerations
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process questions section focusing on capabilities and actions"""
        
        logger.info("Processing questions section")
        
        # Questions reveal decision points and capability requirements
        extraction_weights = {
            'capabilities': 0.4,  # Required competencies for decisions
            'actions': 0.3,       # Potential courses of action
            'constraints': 0.2,   # Decision limitations
            'obligations': 0.1    # Questioned duties
        }
        
        # Build context-aware prompt if dependencies available
        context_summary = self._build_context_summary(context)
        
        questions_prompt = f"""
        ## QUESTIONS SECTION ANALYSIS
        
        {context_summary}
        
        **QUESTIONS TO ANALYZE:**
        {text}
        
        **EXTRACTION FOCUS**:
        - Capabilities ({extraction_weights['capabilities']:.1f}): What competencies are required?
        - Actions ({extraction_weights['actions']:.1f}): What decisions must be made?
        - Constraints ({extraction_weights['constraints']:.1f}): What limits exist on decisions?
        - Obligations ({extraction_weights['obligations']:.1f}): What duties are being questioned?
        
        **KEY INSIGHT**: Questions reveal decision points and required professional competencies.
        """
        
        return {
            'section_type': 'questions',
            'extraction_approach': 'capability_focused',
            'primary_focus': ['capabilities', 'actions', 'constraints'],
            'extraction_prompt': questions_prompt,
            'processing_notes': [
                'Questions highlight required professional competencies',
                'Reveals decision points and action alternatives',
                'Identifies constraints on professional judgment'
            ],
            'entities': []
        }
    
    def _build_context_summary(self, context: Dict[str, Any]) -> str:
        """Build summary of available context from previous sections"""
        if not context:
            return "**CONTEXT**: Analyzing questions independently."
            
        context_parts = []
        if 'facts' in context:
            context_parts.append("FACTS: Factual context established")
        if 'discussion' in context:
            context_parts.append("DISCUSSION: Ethical reasoning available")
            
        if context_parts:
            return f"**AVAILABLE CONTEXT**: {', '.join(context_parts)}"
        return "**CONTEXT**: Analyzing questions independently."


class ReferencesProcessor(BaseSectionProcessor):
    """
    Processes NSPE references and other code citations
    Focus: Resources and codified principles
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process references section focusing on resources and principles"""
        
        logger.info("Processing references section")
        
        # References primarily provide normative resources
        extraction_weights = {
            'resources': 0.6,     # Primary focus - codes, standards, precedents
            'principles': 0.4     # Codified ethical principles
        }
        
        references_prompt = f"""
        ## REFERENCES SECTION ANALYSIS
        
        Extract normative resources and principles from these references:
        
        {text}
        
        **EXTRACTION PRIORITIES**:
        - Resources ({extraction_weights['resources']:.1f}): Professional codes, standards, precedents
        - Principles ({extraction_weights['principles']:.1f}): Codified ethical foundations
        
        **FOCUS**: Identify authoritative sources and their specific provisions that guide professional conduct.
        """
        
        return {
            'section_type': 'nspe_references', 
            'extraction_approach': 'normative_authority',
            'primary_focus': ['resources', 'principles'],
            'extraction_prompt': references_prompt,
            'processing_notes': [
                'References provide authoritative normative guidance',
                'Codes and standards offer concrete ethical provisions',
                'Establishes hierarchy of normative authority'
            ],
            'entities': []
        }


class ConclusionProcessor(BaseSectionProcessor):
    """
    Processes conclusion section - synthesis of actions and final judgments
    Focus: Recommended actions, final obligations, outcome events
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process conclusion section focusing on final judgments and actions"""
        
        logger.info("Processing conclusion section")
        
        # Conclusion synthesizes analysis into actionable recommendations
        extraction_weights = {
            'actions': 0.4,       # Recommended courses of action
            'obligations': 0.3,   # Final duty determinations
            'events': 0.2,        # Anticipated outcomes
            'principles': 0.1     # Conclusive ethical foundations
        }
        
        # Build comprehensive context if available
        context_summary = self._build_comprehensive_context(context)
        
        conclusion_prompt = f"""
        ## CONCLUSION SECTION ANALYSIS
        
        {context_summary}
        
        **CONCLUSION TO ANALYZE:**
        {text}
        
        **EXTRACTION PRIORITIES**:
        - Actions ({extraction_weights['actions']:.1f}): What should be done?
        - Obligations ({extraction_weights['obligations']:.1f}): What duties are conclusively established?
        - Events ({extraction_weights['events']:.1f}): What outcomes are anticipated?
        - Principles ({extraction_weights['principles']:.1f}): What ethical foundations are conclusive?
        
        **SYNTHESIS FOCUS**: How does the conclusion integrate facts, discussion, and questions into actionable recommendations?
        """
        
        return {
            'section_type': 'conclusion',
            'extraction_approach': 'synthesis_and_recommendation',
            'primary_focus': ['actions', 'obligations', 'events'],
            'extraction_prompt': conclusion_prompt,
            'processing_notes': [
                'Conclusion synthesizes case analysis',
                'Provides actionable recommendations',
                'Establishes final ethical judgments',
                'Anticipates consequences of recommended actions'
            ],
            'entities': []
        }
    
    def _build_comprehensive_context(self, context: Dict[str, Any]) -> str:
        """Build comprehensive summary of all available context"""
        if not context:
            return "**CONTEXT**: Analyzing conclusion independently."
            
        context_summary = "**COMPREHENSIVE CONTEXT AVAILABLE:**\n"
        
        if 'facts' in context:
            context_summary += "- FACTS: Established factual circumstances and context\n"
        if 'discussion' in context:
            context_summary += "- DISCUSSION: Professional ethics analysis and reasoning\n"
        if 'questions' in context:
            context_summary += "- QUESTIONS: Decision points and capability requirements\n"
            
        return context_summary


class GenericSectionProcessor(BaseSectionProcessor):
    """
    Generic processor for unrecognized section types
    Provides basic extraction capabilities
    """
    
    def process(self, text: str, context: Dict[str, Any] = None, 
                extraction_focus: List[str] = None) -> Dict[str, Any]:
        """Process generic section with balanced extraction approach"""
        
        logger.info("Processing generic section")
        
        # Use balanced weights for unknown sections
        extraction_weights = {
            entity_type: 1.0/len(extraction_focus) 
            for entity_type in (extraction_focus or [])
        }
        
        generic_prompt = f"""
        ## GENERIC SECTION ANALYSIS
        
        Extract relevant ethical entities from this section:
        
        {text}
        
        **EXTRACTION FOCUS**: {', '.join(extraction_focus or [])}
        
        **BALANCED APPROACH**: Equal weighting for all entity types in extraction focus.
        """
        
        return {
            'section_type': 'generic',
            'extraction_approach': 'balanced',
            'primary_focus': extraction_focus or [],
            'extraction_prompt': generic_prompt,
            'processing_notes': [
                'Generic section processing with balanced approach',
                'Equal attention to all specified entity types'
            ],
            'entities': []
        }


# Import all processor classes into the case_pipeline module  
def get_processor_classes():
    """Return all available processor classes for dynamic instantiation"""
    return {
        'facts': FactsProcessor,
        'discussion': DiscussionProcessor,
        'questions': QuestionsProcessor,
        'nspe_references': ReferencesProcessor,
        'conclusion': ConclusionProcessor,
        'generic': GenericSectionProcessor
    }
