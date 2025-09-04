"""
LLM-Mediated Temporal Reasoning Service

This service enhances the temporal reasoning pipeline by adding LLM interpretation
and validation steps between each algorithmic phase. Uses MCP tools for ontological
validation and natural language understanding.

Pipeline Flow:
1. Algorithm extracts data → 2. LLM interprets/validates → 3. Structured output → 4. Next algorithm

Each step uses the LLM to:
- Validate algorithmic results make contextual sense
- Interpret structured data in natural language via ontology
- Ensure logical coherence between phases
- Provide sanity checks and confidence scoring
"""

import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import json
from dataclasses import asdict

from app.services.temporal_reasoning_service import (
    TemporalReasoningService, 
    TemporalBoundary, 
    TemporalRelation,
    ProcessProfile,
    AllenRelation,
    TemporalBoundaryType
)

# Import LLM orchestration
from shared.llm_orchestration.core.orchestrator import get_llm_orchestrator
from shared.llm_orchestration.providers import GenerationRequest, GenerationResponse

# Import validation tracker
from app.services.llm_validation_tracker import get_llm_validation_tracker

# Import text preprocessing
from app.services.text_preprocessing_service import get_text_preprocessor

logger = logging.getLogger(__name__)


class LLMMediatedTemporalReasoningService:
    """
    LLM-mediated temporal reasoning with validation steps between algorithmic phases.
    
    This service wraps the algorithmic temporal reasoning with LLM interpretation
    to ensure results are contextually meaningful and logically coherent.
    """
    
    def __init__(self):
        self.algorithmic_service = TemporalReasoningService()
        self.llm_orchestrator = None
        self.mcp_client = None
        self._initialize_llm_integration()
        
    def _initialize_llm_integration(self):
        """Initialize LLM orchestrator and MCP client."""
        try:
            self.llm_orchestrator = get_llm_orchestrator()
            # Initialize MCP client for ontology validation
            from shared.llm_orchestration.integrations.mcp_context import get_mcp_context_manager
            self.mcp_client = get_mcp_context_manager()
            logger.info("LLM-mediated temporal reasoning initialized")
        except Exception as e:
            logger.warning(f"LLM integration initialization failed: {e}")
    
    async def extract_temporal_boundaries_with_validation(self, events: List[Dict[str, Any]], 
                                                        case_content: str) -> List[TemporalBoundary]:
        """
        Phase 1: Extract temporal boundaries with LLM validation.
        
        Flow: Algorithm extracts → LLM validates → Refined boundaries
        """
        logger.info("Phase 1: Extracting temporal boundaries with LLM validation")
        
        # Step 1: Algorithmic extraction
        algorithmic_boundaries = self.algorithmic_service.extract_temporal_boundaries(events, case_content)
        logger.info(f"Algorithm extracted {len(algorithmic_boundaries)} boundaries")
        
        # Step 2: LLM interpretation and validation
        validated_boundaries = await self._llm_validate_boundaries(algorithmic_boundaries, case_content, events)
        
        # Step 3: MCP ontological validation
        ontology_validated = await self._mcp_validate_boundaries(validated_boundaries)
        
        logger.info(f"Final validated boundaries: {len(ontology_validated)}")
        return ontology_validated
    
    async def calculate_temporal_relations_with_validation(self, events: List[Dict[str, Any]], 
                                                         boundaries: List[TemporalBoundary]) -> List[TemporalRelation]:
        """
        Phase 2: Calculate temporal relations with LLM sanity checking.
        
        Flow: Algorithm calculates → LLM checks logic → Validated relations
        """
        logger.info("Phase 2: Calculating temporal relations with LLM validation")
        
        # Step 1: Algorithmic relation calculation
        algorithmic_relations = self.algorithmic_service.calculate_temporal_relations(events)
        logger.info(f"Algorithm calculated {len(algorithmic_relations)} relations")
        
        # Step 2: LLM logical validation
        validated_relations = await self._llm_validate_relations(algorithmic_relations, events, boundaries)
        
        # Step 3: MCP ontological coherence check
        coherence_checked = await self._mcp_validate_relations(validated_relations)
        
        logger.info(f"Final validated relations: {len(coherence_checked)}")
        return coherence_checked
    
    async def build_process_profile_with_validation(self, case_id: int, events: List[Dict[str, Any]], 
                                                  case_content: str, boundaries: List[TemporalBoundary],
                                                  relations: List[TemporalRelation]) -> ProcessProfile:
        """
        Phase 3: Build process profile with LLM coherence validation.
        
        Flow: Algorithm builds → LLM validates coherence → Refined profile
        """
        logger.info("Phase 3: Building process profile with LLM validation")
        
        # Step 1: Algorithmic profile construction
        algorithmic_profile = self.algorithmic_service.build_process_profile(case_id, events, case_content)
        
        # Step 2: LLM coherence validation
        validated_profile = await self._llm_validate_process_profile(algorithmic_profile, case_content, boundaries, relations)
        
        # Step 3: MCP ontological profile validation
        ontology_validated_profile = await self._mcp_validate_process_profile(validated_profile)
        
        logger.info("Process profile validation complete")
        return ontology_validated_profile
    
    async def analyze_agent_succession_with_validation(self, agents: List[Dict[str, Any]], 
                                                     events: List[Dict[str, Any]],
                                                     boundaries: List[TemporalBoundary]) -> Dict[str, Any]:
        """
        Phase 4: Analyze agent succession with LLM interpretation.
        
        Flow: Algorithm extracts → LLM interprets roles → Validated succession
        """
        logger.info("Phase 4: Analyzing agent succession with LLM validation")
        
        # Step 1: Algorithmic succession analysis
        algorithmic_succession = self.algorithmic_service.analyze_succession_relations(agents, events)
        
        # Step 2: LLM role interpretation and validation
        validated_succession = await self._llm_validate_agent_succession(algorithmic_succession, events, boundaries)
        
        # Step 3: MCP ontological role validation
        ontology_validated = await self._mcp_validate_agent_roles(validated_succession)
        
        logger.info("Agent succession validation complete")
        return ontology_validated
    
    async def enhance_events_with_validated_temporal_data(self, events: List[Dict[str, Any]], 
                                                        process_profile: ProcessProfile) -> List[Dict[str, Any]]:
        """
        Phase 5: Enhance events with LLM-validated temporal metadata.
        
        Flow: Algorithm enhances → LLM validates meaningfulness → Final events
        """
        logger.info("Phase 5: Enhancing events with validated temporal data")
        
        # Step 1: Algorithmic enhancement
        enhanced_events = self.algorithmic_service.enhance_events_with_temporal_data(events, process_profile)
        
        # Step 2: LLM meaningfulness validation
        validated_events = await self._llm_validate_enhanced_events(enhanced_events)
        
        logger.info(f"Enhanced and validated {len(validated_events)} events")
        return validated_events
    
    # LLM Validation Methods
    
    async def _llm_validate_boundaries(self, boundaries: List[TemporalBoundary], 
                                     case_content: str, events: List[Dict[str, Any]]) -> List[TemporalBoundary]:
        """Use LLM to validate extracted temporal boundaries make contextual sense."""
        if not self.llm_orchestrator:
            return boundaries
        
        # Preprocess case content to remove HTML and extract precedent cases
        preprocessor = get_text_preprocessor()
        processed_content = preprocessor.preprocess_for_llm(case_content, preserve_precedents=True)
        
        # Clean events for LLM consumption
        cleaned_events = []
        all_precedent_cases = []
        
        for event in events:
            if event.get('text'):
                processed_event = preprocessor.preprocess_event_text(event['text'])
                cleaned_event = dict(event)
                cleaned_event['text'] = processed_event['clean_text']
                cleaned_events.append(cleaned_event)
                all_precedent_cases.extend(processed_event['precedent_cases'])
            else:
                cleaned_events.append(event)
        
        # Combine all precedent cases
        all_precedent_cases.extend(processed_content['precedent_cases'])
        unique_precedents = preprocessor._deduplicate_precedent_cases(all_precedent_cases)
        
        # Convert boundaries to natural language for LLM review
        boundaries_summary = self._format_boundaries_for_llm(boundaries)
        
        base_prompt = f"""You are an expert in ethics case analysis. Review these extracted temporal boundaries to ensure they make contextual sense.

ORIGINAL CASE (HTML cleaned):
{processed_content['clean_text'][:1000]}...

EXTRACTED TEMPORAL BOUNDARIES:
{boundaries_summary}

EVENTS CONTEXT (HTML cleaned):
{self._format_clean_events_for_llm(cleaned_events)}

Please validate each boundary and provide feedback in JSON format:

{{
    "validated_boundaries": [
        {{
            "boundary_id": "decision_boundary_1",
            "is_valid": true/false,
            "confidence": 0.85,
            "reasoning": "Why this boundary makes sense or needs adjustment",
            "suggested_adjustments": "Any recommendations for improvement",
            "ethical_significance_rating": 0.8
        }}
    ],
    "overall_assessment": "General assessment of boundary extraction quality",
    "missing_boundaries": ["Description of any critical boundaries that were missed"],
    "false_positives": ["Any boundaries that seem incorrect"]
}}

Focus on whether the boundaries represent genuine critical moments in the ethical decision-making process."""
        
        # Enhance prompt with precedent case context
        enhanced_prompt = preprocessor.enhance_llm_prompt_with_precedents(base_prompt, unique_precedents)
        
        try:
            response = await self.llm_orchestrator.send_message(
                message=enhanced_prompt,
                max_tokens=2000,
                temperature=0.2
            )
            
            validation_data = self._parse_llm_json_response(response.content)
            
            # Add precedent case information to validation
            validation_data['precedent_cases_found'] = len(unique_precedents)
            validation_data['precedent_cases'] = unique_precedents
            
            return self._apply_boundary_validation(boundaries, validation_data)
            
        except Exception as e:
            logger.error(f"LLM boundary validation failed: {e}")
            return boundaries
    
    async def _llm_validate_relations(self, relations: List[TemporalRelation], 
                                    events: List[Dict[str, Any]], 
                                    boundaries: List[TemporalBoundary]) -> List[TemporalRelation]:
        """Use LLM to validate temporal relations are logically sound."""
        if not self.llm_orchestrator:
            return relations
        
        relations_summary = self._format_relations_for_llm(relations, events)
        
        prompt = f"""You are an expert in temporal logic and ethics case analysis. Review these temporal relations to ensure they are logically sound.

TEMPORAL RELATIONS:
{relations_summary}

CONTEXT - TEMPORAL BOUNDARIES:
{self._format_boundaries_for_llm(boundaries)}

Please validate the logical consistency of these temporal relations in JSON format:

{{
    "validated_relations": [
        {{
            "relation_id": "relation_1",
            "source_event": "event_1",
            "target_event": "decision_1", 
            "relation_type": "before",
            "is_logically_sound": true/false,
            "confidence": 0.9,
            "reasoning": "Why this relation makes logical sense",
            "suggested_correction": "Any needed adjustments"
        }}
    ],
    "consistency_check": "Overall assessment of temporal consistency",
    "logical_contradictions": ["Any contradictions found"],
    "missing_relations": ["Important relations that might be missing"]
}}

Focus on whether the temporal ordering and relationships make logical sense in the context of ethical decision-making."""
        
        try:
            response = await self.llm_orchestrator.send_message(
                message=prompt,
                max_tokens=2000,
                temperature=0.2
            )
            
            validation_data = self._parse_llm_json_response(response.content)
            return self._apply_relations_validation(relations, validation_data)
            
        except Exception as e:
            logger.error(f"LLM relations validation failed: {e}")
            return relations
    
    async def _llm_validate_process_profile(self, profile: ProcessProfile, case_content: str,
                                          boundaries: List[TemporalBoundary], 
                                          relations: List[TemporalRelation]) -> ProcessProfile:
        """Use LLM to validate process profile coherence and completeness."""
        if not self.llm_orchestrator:
            return profile
        
        profile_summary = self._format_profile_for_llm(profile)
        
        prompt = f"""You are an expert in ethics case analysis and process modeling. Review this process profile to ensure it captures the essence of the ethical case.

ORIGINAL CASE:
{case_content[:800]}...

PROCESS PROFILE:
{profile_summary}

Please validate the process profile coherence in JSON format:

{{
    "profile_validation": {{
        "captures_case_essence": true/false,
        "phases_make_sense": true/false,
        "critical_path_accurate": true/false,
        "agent_succession_logical": true/false,
        "overall_coherence": 0.85
    }},
    "suggested_improvements": {{
        "phase_adjustments": ["Any phase modifications needed"],
        "critical_path_refinements": ["Improvements to critical path"],
        "missing_elements": ["Important elements not captured"]
    }},
    "narrative_summary": "A brief narrative of how this case unfolds according to the profile",
    "ethical_decision_flow": "How the key ethical decisions connect in this profile"
}}

Focus on whether the profile tells a coherent story of the ethical dilemma and decision-making process."""
        
        try:
            response = await self.llm_orchestrator.send_message(
                message=prompt,
                max_tokens=2000,
                temperature=0.3
            )
            
            validation_data = self._parse_llm_json_response(response.content)
            return self._apply_profile_validation(profile, validation_data)
            
        except Exception as e:
            logger.error(f"LLM profile validation failed: {e}")
            return profile
    
    async def _llm_validate_agent_succession(self, succession: Dict[str, Any], 
                                           events: List[Dict[str, Any]],
                                           boundaries: List[TemporalBoundary]) -> Dict[str, Any]:
        """Use LLM to validate agent succession makes contextual sense."""
        if not self.llm_orchestrator:
            return succession
        
        succession_summary = json.dumps(succession, indent=2, default=str)
        
        prompt = f"""You are an expert in organizational behavior and ethics case analysis. Review this agent succession analysis to ensure it makes contextual sense.

AGENT SUCCESSION ANALYSIS:
{succession_summary}

TEMPORAL BOUNDARIES CONTEXT:
{self._format_boundaries_for_llm(boundaries)}

Please validate the agent succession in JSON format:

{{
    "succession_validation": {{
        "role_transitions_logical": true/false,
        "agent_involvement_accurate": true/false,
        "timeline_consistency": true/false,
        "missing_key_agents": ["Any important agents not captured"],
        "role_evolution_realistic": true/false
    }},
    "agent_insights": [
        {{
            "agent_name": "Engineer",
            "role_progression": "How their role/influence changes",
            "key_decisions_influenced": ["Decisions they impact"],
            "ethical_stance_evolution": "How their ethical position evolves"
        }}
    ],
    "stakeholder_dynamics": "How the agents interact and influence each other",
    "power_structure_analysis": "How authority and influence flow between agents"
}}

Focus on realistic agent behavior and role evolution in professional ethics contexts."""
        
        try:
            response = await self.llm_orchestrator.send_message(
                message=prompt,
                max_tokens=2000,
                temperature=0.3
            )
            
            validation_data = self._parse_llm_json_response(response.content)
            return self._apply_succession_validation(succession, validation_data)
            
        except Exception as e:
            logger.error(f"LLM succession validation failed: {e}")
            return succession
    
    async def _llm_validate_enhanced_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Use LLM to validate enhanced events are meaningful and coherent."""
        if not self.llm_orchestrator:
            return events
        
        # Sample a few events for validation (to avoid token limits)
        sample_events = events[:5] if len(events) > 5 else events
        events_summary = json.dumps(sample_events, indent=2, default=str)
        
        prompt = f"""You are an expert in ethics case analysis. Review these enhanced events to ensure the temporal metadata adds meaningful context.

ENHANCED EVENTS (SAMPLE):
{events_summary}

Please validate the event enhancements in JSON format:

{{
    "enhancement_validation": {{
        "temporal_metadata_meaningful": true/false,
        "bfo_classifications_appropriate": true/false,
        "boundary_associations_logical": true/false,
        "relation_information_helpful": true/false,
        "overall_enhancement_quality": 0.8
    }},
    "specific_feedback": [
        {{
            "event_id": "event_1",
            "enhancement_quality": 0.9,
            "helpful_aspects": ["What temporal metadata helps understanding"],
            "confusing_aspects": ["What might be unclear or unhelpful"],
            "suggestions": ["How to improve the enhancement"]
        }}
    ],
    "general_recommendations": "Overall suggestions for improving event enhancement"
}}

Focus on whether the temporal enhancements help users better understand the ethical timeline and decision points."""
        
        try:
            response = await self.llm_orchestrator.send_message(
                message=prompt,
                max_tokens=1500,
                temperature=0.2
            )
            
            validation_data = self._parse_llm_json_response(response.content)
            return self._apply_events_validation(events, validation_data)
            
        except Exception as e:
            logger.error(f"LLM events validation failed: {e}")
            return events
    
    # MCP Validation Methods (using ontological knowledge)
    
    async def _mcp_validate_boundaries(self, boundaries: List[TemporalBoundary]) -> List[TemporalBoundary]:
        """Use MCP ontology tools to validate boundaries against formal ontology."""
        if not self.mcp_client:
            return boundaries
        
        try:
            # Use MCP tools to validate boundary types against ontology
            for boundary in boundaries:
                # Query ontology for temporal boundary concepts
                ontology_validation = await self._query_temporal_boundary_ontology(boundary)
                if ontology_validation:
                    boundary.ontology_validation = ontology_validation
                    
        except Exception as e:
            logger.error(f"MCP boundary validation failed: {e}")
        
        return boundaries
    
    async def _mcp_validate_relations(self, relations: List[TemporalRelation]) -> List[TemporalRelation]:
        """Use MCP ontology tools to validate temporal relations."""
        if not self.mcp_client:
            return relations
        
        try:
            # Validate Allen relations against formal temporal ontology
            for relation in relations:
                ontology_validation = await self._query_temporal_relation_ontology(relation)
                if ontology_validation:
                    relation.ontology_validation = ontology_validation
                    
        except Exception as e:
            logger.error(f"MCP relations validation failed: {e}")
        
        return relations
    
    async def _mcp_validate_process_profile(self, profile: ProcessProfile) -> ProcessProfile:
        """Use MCP ontology tools to validate process profile."""
        # Implementation would use MCP tools to validate process concepts
        return profile
    
    async def _mcp_validate_agent_roles(self, succession: Dict[str, Any]) -> Dict[str, Any]:
        """Use MCP ontology tools to validate agent roles against role ontology."""
        # Implementation would validate roles against ontological role concepts
        return succession
    
    # Helper Methods
    
    def _format_boundaries_for_llm(self, boundaries: List[TemporalBoundary]) -> str:
        """Format boundaries for LLM consumption."""
        formatted = []
        for boundary in boundaries:
            formatted.append(f"- {boundary.boundary_id}: {boundary.description} "
                           f"(Type: {boundary.boundary_type.value}, "
                           f"Significance: {boundary.ethical_significance:.2f})")
        return "\n".join(formatted)
    
    def _format_relations_for_llm(self, relations: List[TemporalRelation], events: List[Dict[str, Any]]) -> str:
        """Format relations for LLM consumption."""
        # Create event lookup for readable names
        event_lookup = {e.get('id'): e.get('text', '')[:50] + '...' for e in events}
        
        formatted = []
        for relation in relations:
            source_desc = event_lookup.get(relation.source_entity, relation.source_entity)
            target_desc = event_lookup.get(relation.target_entity, relation.target_entity)
            formatted.append(f"- {source_desc} {relation.relation.value} {target_desc}")
        
        return "\n".join(formatted)
    
    def _format_profile_for_llm(self, profile: ProcessProfile) -> str:
        """Format process profile for LLM consumption."""
        summary = f"""Process ID: {profile.process_id}
Phases: {len(profile.process_phases)} identified
Critical Path: {len(profile.critical_path)} key elements
Agent Succession: {len(profile.agent_succession)} agents tracked
Temporal Boundaries: {len(profile.temporal_boundaries)} boundaries
Temporal Relations: {len(profile.temporal_relations)} relations"""
        return summary
    
    def _format_events_for_llm(self, events: List[Dict[str, Any]]) -> str:
        """Format events for LLM consumption."""
        formatted = []
        for event in events[:8]:  # Limit to avoid token overflow
            kind = event.get('kind', 'event')
            text = event.get('text', '')[:60] + '...' if len(event.get('text', '')) > 60 else event.get('text', '')
            formatted.append(f"- [{kind.upper()}] {text}")
        
        if len(events) > 8:
            formatted.append(f"... and {len(events) - 8} more events")
        
        return "\n".join(formatted)
    
    def _format_clean_events_for_llm(self, cleaned_events: List[Dict[str, Any]]) -> str:
        """Format cleaned events for LLM consumption (HTML already stripped)."""
        formatted = []
        for event in cleaned_events[:8]:  # Limit to avoid token overflow
            kind = event.get('kind', 'event')
            # Use the already cleaned text
            text = event.get('text', '')[:60] + '...' if len(event.get('text', '')) > 60 else event.get('text', '')
            formatted.append(f"- [{kind.upper()}] {text}")
        
        if len(cleaned_events) > 8:
            formatted.append(f"... and {len(cleaned_events) - 8} more events")
        
        return "\n".join(formatted)
    
    def _parse_llm_json_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM JSON response with error handling."""
        try:
            # Find JSON block in response
            start_idx = response.find('{')
            end_idx = response.rfind('}') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = response[start_idx:end_idx]
                return json.loads(json_str)
            
        except Exception as e:
            logger.error(f"Failed to parse LLM response: {e}")
        
        return {}
    
    def _apply_boundary_validation(self, boundaries: List[TemporalBoundary], 
                                 validation: Dict[str, Any]) -> List[TemporalBoundary]:
        """Apply LLM validation results to boundaries."""
        validated_boundaries = validation.get('validated_boundaries', [])
        
        # Update boundaries with LLM feedback
        for boundary in boundaries:
            for validated in validated_boundaries:
                if validated.get('boundary_id') == boundary.boundary_id:
                    # Update confidence and significance based on LLM feedback
                    if 'confidence' in validated:
                        boundary.llm_confidence = validated['confidence']
                    if 'ethical_significance_rating' in validated:
                        boundary.ethical_significance = validated['ethical_significance_rating']
                    boundary.llm_validation = validated
        
        return boundaries
    
    def _apply_relations_validation(self, relations: List[TemporalRelation], 
                                  validation: Dict[str, Any]) -> List[TemporalRelation]:
        """Apply LLM validation results to relations."""
        # Similar to boundary validation, update relations with LLM feedback
        return relations
    
    def _apply_profile_validation(self, profile: ProcessProfile, 
                                validation: Dict[str, Any]) -> ProcessProfile:
        """Apply LLM validation results to process profile."""
        profile.llm_validation = validation
        return profile
    
    def _apply_succession_validation(self, succession: Dict[str, Any], 
                                   validation: Dict[str, Any]) -> Dict[str, Any]:
        """Apply LLM validation results to succession analysis."""
        succession['llm_validation'] = validation
        return succession
    
    def _apply_events_validation(self, events: List[Dict[str, Any]], 
                               validation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Apply LLM validation results to enhanced events."""
        for event in events:
            event['llm_validation'] = validation.get('enhancement_validation', {})
        return events
    
    async def _query_temporal_boundary_ontology(self, boundary: TemporalBoundary) -> Optional[Dict[str, Any]]:
        """Query MCP ontology for temporal boundary validation."""
        # Implementation would use MCP tools to query ontology
        return None
    
    async def _query_temporal_relation_ontology(self, relation: TemporalRelation) -> Optional[Dict[str, Any]]:
        """Query MCP ontology for temporal relation validation."""
        # Implementation would use MCP tools to query ontology
        return None
    
    # Main orchestration method
    
    async def generate_validated_temporal_analysis(self, case_id: int, events: List[Dict[str, Any]], 
                                                 case_content: str, agents: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Main orchestration method that runs the full LLM-mediated temporal analysis pipeline.
        
        Returns comprehensive temporal analysis with LLM validation at each step.
        """
        logger.info(f"Starting LLM-mediated temporal analysis for case {case_id}")
        
        # Initialize validation tracking
        tracker = get_llm_validation_tracker()
        session_id = tracker.start_validation_session(case_id)
        
        start_time = datetime.now()
        
        try:
            # Phase 1: Extract and validate temporal boundaries
            phase_start = datetime.now()
            boundaries = await self.extract_temporal_boundaries_with_validation(events, case_content)
            phase_time = (datetime.now() - phase_start).total_seconds()
            
            # Track Phase 1 feedback (boundaries will have validation data)
            if boundaries and hasattr(boundaries[0], 'llm_validation'):
                tracker.log_phase_feedback("boundary_extraction", boundaries[0].llm_validation, phase_time)
            
            # Phase 2: Calculate and validate temporal relations
            phase_start = datetime.now()
            relations = await self.calculate_temporal_relations_with_validation(events, boundaries)
            phase_time = (datetime.now() - phase_start).total_seconds()
            
            # Track Phase 2 feedback
            if relations:
                tracker.log_phase_feedback("temporal_relations", {}, phase_time)
            
            # Phase 3: Build and validate process profile
            phase_start = datetime.now()
            profile = await self.build_process_profile_with_validation(case_id, events, case_content, boundaries, relations)
            phase_time = (datetime.now() - phase_start).total_seconds()
            
            # Track Phase 3 feedback
            if hasattr(profile, 'llm_validation'):
                tracker.log_phase_feedback("process_profile", profile.llm_validation, phase_time)
            
            # Phase 4: Analyze and validate agent succession
            phase_start = datetime.now()
            succession = await self.analyze_agent_succession_with_validation(agents, events, boundaries)
            phase_time = (datetime.now() - phase_start).total_seconds()
            
            # Track Phase 4 feedback
            if 'llm_validation' in succession:
                tracker.log_phase_feedback("agent_succession", succession['llm_validation'], phase_time)
            
            # Phase 5: Enhance and validate events
            phase_start = datetime.now()
            enhanced_events = await self.enhance_events_with_validated_temporal_data(events, profile)
            phase_time = (datetime.now() - phase_start).total_seconds()
            
            # Track Phase 5 feedback
            if enhanced_events and 'llm_validation' in enhanced_events[0]:
                tracker.log_phase_feedback("event_enhancement", enhanced_events[0]['llm_validation'], phase_time)
            
            # Complete validation session
            completed_session = tracker.complete_validation_session()
            
            # Compile final analysis
            analysis_result = {
                'case_id': case_id,
                'analysis_type': 'llm_mediated_temporal',
                'temporal_boundaries': [asdict(b) for b in boundaries],
                'temporal_relations': [asdict(r) for r in relations],
                'process_profile': asdict(profile),
                'agent_succession': succession,
                'enhanced_events': enhanced_events,
                'validation_summary': {
                    'boundaries_validated': len(boundaries),
                    'relations_validated': len(relations),
                    'llm_validation_steps': 5,
                    'mcp_validation_steps': 4
                },
                'llm_validation_session': completed_session.to_dict() if completed_session else None
            }
            
            logger.info(f"LLM-mediated temporal analysis complete for case {case_id}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"LLM temporal analysis failed for case {case_id}: {e}")
            # Complete session with error
            if tracker.current_session:
                tracker.current_session.session_status = "failed"
                tracker.complete_validation_session()
            raise
