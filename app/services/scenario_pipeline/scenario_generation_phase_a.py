"""Scenario Generation Phase A Service.

Generates a minimal structured scenario timeline (events + decisions) directly from a Case (Document)
without requiring prior deconstruction. Saves versioned scenario data in Document.doc_metadata['scenario_versions'].

Enhanced Features (when enabled):
- LLM-driven semantic timeline extraction
- MCP ontology integration for rich entity mapping
- Evidence-based temporal ordering
- Contextual decision generation with NSPE references
"""
from __future__ import annotations
from typing import Dict, Any, List
from datetime import datetime, timezone
import hashlib
import os
import logging
import asyncio

from app.models import Document, db
from sqlalchemy.orm.attributes import flag_modified
from .segmenter import segment_sections
from .classifier import classify_sentences
from .temporal import extract_temporal
from .assembler import assemble_events
from .decisions import enrich_decisions
from .participant_extractor import extract_participants
from .ontology_summary import build_ontology_summary
from .question_based_decisions import extract_question_decisions, extract_question_decisions_from_metadata
from .ontology_mapper import map_events
from .ordering import build_ordering
from .llm_decision_refiner import refine_decisions_with_llm

# Import text preprocessing
try:
    from app.services.text_preprocessing_service import get_text_preprocessor
    TEXT_PREPROCESSING_AVAILABLE = True
except ImportError:
    TEXT_PREPROCESSING_AVAILABLE = False
    logging.getLogger(__name__).warning("Text preprocessing service not available")

# Enhanced components (optional imports)
ENHANCED_FEATURES_AVAILABLE = False
LLM_TEMPORAL_AVAILABLE = False

# Try individual imports to see which ones work
enhanced_services = {}

try:
    from .enhanced_llm_scenario_service import EnhancedLLMScenarioService
    enhanced_services['enhanced_llm'] = True
    logging.getLogger(__name__).info("✅ EnhancedLLMScenarioService imported successfully")
except ImportError as e:
    enhanced_services['enhanced_llm'] = False
    logging.getLogger(__name__).warning(f"❌ EnhancedLLMScenarioService import failed: {e}")

try:
    from .mcp_ontology_client import MCPOntologyClient, get_role_for_participant, enrich_decision_with_ontology
    enhanced_services['mcp_ontology'] = True
    logging.getLogger(__name__).info("✅ MCP Ontology Client imported successfully")
except ImportError as e:
    enhanced_services['mcp_ontology'] = False
    logging.getLogger(__name__).warning(f"❌ MCP Ontology Client import failed: {e}")

try:
    from .enhanced_scenario_model_generator import EnhancedScenarioModelGenerator
    enhanced_services['model_generator'] = True
    logging.getLogger(__name__).info("✅ EnhancedScenarioModelGenerator imported successfully")
except ImportError as e:
    enhanced_services['model_generator'] = False
    logging.getLogger(__name__).warning(f"❌ EnhancedScenarioModelGenerator import failed: {e}")

# Import LLM-mediated temporal reasoning
try:
    from app.services.llm_mediated_temporal_reasoning import LLMMediatedTemporalReasoningService
    enhanced_services['llm_temporal'] = True
    LLM_TEMPORAL_AVAILABLE = True
    logging.getLogger(__name__).info("✅ LLMMediatedTemporalReasoningService imported successfully")
except ImportError as e:
    enhanced_services['llm_temporal'] = False
    LLM_TEMPORAL_AVAILABLE = False
    logging.getLogger(__name__).warning(f"❌ LLMMediatedTemporalReasoningService import failed: {e}")

# Enable enhanced features if we have at least basic LLM service
if enhanced_services.get('enhanced_llm', False):
    ENHANCED_FEATURES_AVAILABLE = True
    logging.getLogger(__name__).info("Enhanced features enabled with available services")
else:
    logging.getLogger(__name__).warning("Enhanced features disabled - missing required services")

logging.getLogger(__name__).info(f"Enhanced services status: {enhanced_services}")

PIPELINE_VERSION = 'phase_a_v1'
ENHANCED_PIPELINE_VERSION = 'enhanced_llm_v1'

logger = logging.getLogger(__name__)

class DirectScenarioPipelineService:
    def __init__(self):
        self.enhanced_enabled = (
            ENHANCED_FEATURES_AVAILABLE and 
            os.environ.get('ENHANCED_SCENARIO_GENERATION', 'false').lower() == 'true'
        )
        self.llm_temporal_enabled = (
            LLM_TEMPORAL_AVAILABLE and 
            self.enhanced_enabled
        )
        
        if self.enhanced_enabled:
            try:
                self.enhanced_service = EnhancedLLMScenarioService()
                self.model_generator = EnhancedScenarioModelGenerator()
                
                # Initialize LLM-mediated temporal reasoning if available
                if self.llm_temporal_enabled:
                    self.llm_temporal_service = LLMMediatedTemporalReasoningService()
                    logger.info("Enhanced LLM scenario generation with temporal reasoning enabled")
                else:
                    logger.info("Enhanced LLM scenario generation enabled (temporal reasoning unavailable)")
                    
            except ValueError as e:
                if "API key is required" in str(e):
                    logger.error("Enhanced generation requires ANTHROPIC_API_KEY environment variable")
                    raise ValueError(
                        "🔑 Enhanced scenario generation requires an API key!\n\n"
                        "Please set your Anthropic API key:\n"
                        "export ANTHROPIC_API_KEY=your_key_here\n\n"
                        "Or disable enhanced generation:\n"
                        "export ENHANCED_SCENARIO_GENERATION=false"
                    )
                else:
                    raise
        else:
            logger.info("Using legacy heuristic scenario generation")

    def generate(self, case: Document, overwrite: bool = False) -> Dict[str, Any]:
        metadata = case.doc_metadata or {}
        sections = metadata.get('sections') or metadata.get('document_structure', {}).get('sections', {}) or {}

        logger.info(f"Generate called for case {case.id}, enhanced_enabled: {self.enhanced_enabled}")
        logger.info(f"LLM temporal enabled: {getattr(self, 'llm_temporal_enabled', False)}")
        logger.info(f"Metadata keys: {list(metadata.keys())}")
        logger.info(f"Sections keys: {list(sections.keys())}")

        # Check if enhanced generation is enabled
        if self.enhanced_enabled:
            logger.info("Using enhanced generation")
            try:
                result = self._generate_enhanced(case, metadata, sections, overwrite)
                if result is None:
                    logger.error("Enhanced generation returned None - this should not happen")
                    logger.info("Falling back to legacy generation due to None result")
                    return self._generate_legacy(case, metadata, sections, overwrite)
                return result
            except Exception as e:
                logger.error(f"Enhanced generation failed with exception: {e}")
                logger.info("Falling back to legacy generation due to exception")
                return self._generate_legacy(case, metadata, sections, overwrite)
        else:
            logger.info("Using legacy generation")
            result = self._generate_legacy(case, metadata, sections, overwrite)
            if result is None:
                logger.error("Legacy generation returned None - this is a serious issue")
            return result

    def _generate_enhanced(self, case: Document, metadata: Dict[str, Any], sections: Dict[str, Any], overwrite: bool) -> Dict[str, Any]:
        """Enhanced LLM-driven scenario generation with ontology integration."""
        logger.info(f"Starting enhanced scenario generation for case {case.id}")
        
        try:
            # Extract semantic timeline using LLM service
            timeline_data = self.enhanced_service.extract_semantic_timeline(sections, metadata)
            
            if timeline_data.get('error'):
                logger.warning(f"Enhanced generation failed: {timeline_data['error']}, falling back to legacy")
                return self._generate_legacy(case, metadata, sections, overwrite)
            
            # Try to enrich with LLM-mediated temporal reasoning
            if self.llm_temporal_enabled:
                try:
                    logger.info("Applying LLM-mediated temporal reasoning...")
                    events = timeline_data.get('timeline_events', [])
                    participants = timeline_data.get('participants', [])
                    
                    # Run LLM-mediated temporal analysis
                    temporal_analysis = asyncio.run(
                        self.llm_temporal_service.generate_validated_temporal_analysis(
                            case.id, events, case.content, participants
                        )
                    )
                    
                    # Integrate temporal analysis into timeline
                    timeline_data['temporal_analysis'] = temporal_analysis
                    timeline_data['llm_temporal_validation'] = 'success'
                    
                    logger.info(f"LLM temporal analysis complete: {temporal_analysis['validation_summary']}")
                    
                except Exception as e:
                    logger.error(f"LLM temporal reasoning failed: {e}")
                    timeline_data['llm_temporal_validation'] = 'failed'
                    timeline_data['llm_temporal_error'] = str(e)
            
            # Try to enrich with MCP ontology integration (async)
            try:
                enhanced_timeline = asyncio.run(self._enrich_with_ontology(timeline_data))
            except Exception as e:
                logger.error(f"MCP ontology enrichment failed: {e}")
                logger.warning("⚠️  MCP server is not responding - continuing without ontology enrichment")
                logger.warning(f"⚠️  MCP URL: {os.environ.get('MCP_SERVER_URL', 'http://localhost:5001')}")
                logger.warning("⚠️  Please ensure MCP server is running for full ontology integration")
                enhanced_timeline = timeline_data
                enhanced_timeline['ontology_enrichment_status'] = 'failed'
                enhanced_timeline['ontology_enrichment_error'] = f"MCP server unavailable: {str(e)}"
            
            # Generate proper database models (Character, Resource, Event, Action)
            try:
                scenario_id = self.model_generator.create_scenario_from_enhanced_timeline(
                    case, enhanced_timeline
                )
                logger.info(f"Created enhanced scenario {scenario_id} with proper models")
                
                # Build scenario data structure for metadata
                scenario_data = self._build_enhanced_scenario_data(case, enhanced_timeline, metadata)
                scenario_data['scenario_id'] = scenario_id
                scenario_data['scenario_url'] = f"/scenarios/{scenario_id}"
                
            except Exception as e:
                logger.error(f"Failed to create enhanced scenario models: {e}")
                # Fall back to saving scenario data in case metadata
                scenario_data = self._build_enhanced_scenario_data(case, enhanced_timeline, metadata)
                scenario_data['model_creation_error'] = str(e)
            
            # Save scenario metadata to case
            self._save_enhanced_scenario(case, scenario_data, overwrite)
            
            logger.info(f"Enhanced scenario generation completed for case {case.id}")
            return scenario_data
            
        except Exception as e:
            logger.error(f"Enhanced generation failed for case {case.id}: {e}", exc_info=True)
            logger.info("Falling back to legacy generation")
            return self._generate_legacy(case, metadata, sections, overwrite)

    def _generate_legacy(self, case: Document, metadata: Dict[str, Any], sections: Dict[str, Any], overwrite: bool) -> Dict[str, Any]:
        """Original heuristic-based scenario generation (preserved for fallback)."""
        logger.info(f"Starting legacy scenario generation for case {case.id}")
        
        # 1. Segmentation & sentence-level annotations
        segmentation = segment_sections(sections)
        sentences = segmentation['sentences']
        classification = classify_sentences(sentences)
        temporal = extract_temporal(sentences)

        # 2. Assemble events
        events = assemble_events(sentences, classification)
        for ev in events:
            if ev['sentence_ids']:
                tinfo = temporal.get(ev['sentence_ids'][0])
                if tinfo:
                    ev['temporal'] = tinfo

        # 3. Participants extraction (optional enrich) then heuristic decision enrichment
        participant_meta = extract_participants(events) if os.environ.get('DIRECT_SCENARIO_INCLUDE_PARTICIPANTS', 'true').lower() != 'false' else {'unique_participants': []}
        enrich_decisions(events)

        # 3b. Question-derived decision injection (ensures high-quality decision questions)
        # Prefer metadata-based explicit questions list for higher fidelity
        q_decisions = extract_question_decisions_from_metadata(metadata, sections)
        if not q_decisions:  # fallback to section parsing
            q_decisions = extract_question_decisions(sections)
        if q_decisions:
            # Avoid duplicate text collisions (simple check)
            existing_texts = {e['text'] for e in events}
            new_q = [qd for qd in q_decisions if qd['text'] not in existing_texts]
            events.extend(new_q)

        # 4. Optional LLM refinement
        refine_decisions_with_llm(events)

        # 4b. Fill generic options if any refined decision lacks options
        for ev in events:
            if ev.get('kind') == 'decision' and not ev.get('options'):
                # minimal generic options fallback
                ev['options'] = [
                    {'label': 'Escalate', 'description': 'Escalate to appropriate oversight'},
                    {'label': 'Proceed Quietly', 'description': 'Continue without broader disclosure'},
                    {'label': 'Pause & Reassess', 'description': 'Delay action pending more information'}
                ]

        # 5. Ontology mapping & ordering
        map_events(events)
        ordering = build_ordering(events)

        # 6. Stats
        stats = {
            'event_count': len(events),
            'decision_count': sum(1 for e in events if e['kind'] == 'decision'),
            'sentence_count': len(sentences)
        }

        ontology_summary = build_ontology_summary(events, participant_meta.get('unique_participants'))
        scenario_data = {
            'pipeline_version': PIPELINE_VERSION,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'case_id': case.id,
            'events': events,
            'ordering': ordering,
            'stats': stats,
            'participants': participant_meta.get('unique_participants'),
            'ontology_summary': ontology_summary
        }

        versions = metadata.get('scenario_versions', [])
        content_hash = hashlib.sha256(str(stats).encode('utf-8')).hexdigest()[:12]
        scenario_data['hash'] = content_hash
        scenario_data['version_number'] = len(versions) + 1

        if overwrite:
            versions.append(scenario_data)
        else:
            if not versions or versions[-1].get('hash') != content_hash:
                versions.append(scenario_data)

        metadata['scenario_versions'] = versions
        metadata['latest_scenario'] = scenario_data
        case.doc_metadata = dict(metadata)
        flag_modified(case, 'doc_metadata')
        db.session.add(case)
        db.session.commit()
        
        logger.info(f"Legacy scenario generation completed for case {case.id}")
        return scenario_data

    async def _enrich_with_ontology(self, timeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich timeline data with MCP ontology integration."""
        try:
            async with MCPOntologyClient() as mcp_client:
                # Enrich participants with ontological roles
                for participant in timeline_data.get('participants', []):
                    role_entity = await mcp_client.map_participant_to_role(participant['name'])
                    if role_entity:
                        participant['ontology_role'] = {
                            'uri': role_entity.uri,
                            'label': role_entity.label,
                            'confidence': role_entity.confidence
                        }
                
                # Enrich decisions with ontological categories
                for decision in timeline_data.get('enhanced_decisions', []):
                    ontology_enrichment = await mcp_client.enrich_decision_with_ontology(
                        decision.question, 
                        decision.context
                    )
                    decision.ontology_categories = ontology_enrichment
                
                timeline_data['ontology_enrichment_status'] = 'success'
                
        except Exception as e:
            logger.error(f"MCP ontology enrichment failed: {e}")
            timeline_data['ontology_enrichment_status'] = 'failed'
            timeline_data['ontology_enrichment_error'] = str(e)
            
        return timeline_data

    def _build_enhanced_scenario_data(self, case: Document, enhanced_timeline: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced scenario data structure."""
        timeline_events = enhanced_timeline.get('timeline_events', [])
        enhanced_decisions = enhanced_timeline.get('enhanced_decisions', [])
        participants = enhanced_timeline.get('participants', [])
        temporal_evidence = enhanced_timeline.get('temporal_evidence', [])
        
        # Convert enhanced decisions to event format
        decision_events = []
        for decision in enhanced_decisions:
            decision_event = {
                'id': decision.id,
                'kind': 'decision',
                'title': decision.title,
                'text': decision.question,
                'question': decision.question,
                'context': decision.context,
                'section': decision.section_source,
                'ontology_categories': decision.ontology_categories,
                'temporal_triggers': decision.temporal_triggers,
                'options': self.enhanced_service.generate_decision_options(decision, metadata),
                'enhanced_decision': True
            }
            decision_events.append(decision_event)
        
        # Combine timeline events and decisions
        all_events = timeline_events + decision_events
        
        # Build ordering from temporal evidence
        ordering = self._build_evidence_based_ordering(all_events, temporal_evidence)
        
        # Calculate stats
        stats = {
            'event_count': len(all_events),
            'decision_count': len(decision_events),
            'timeline_events': len(timeline_events),
            'temporal_evidence_count': len(temporal_evidence),
            'participants_count': len(participants)
        }
        
        # Build enhanced ontology summary
        ontology_summary = self._build_enhanced_ontology_summary(enhanced_timeline)
        
        scenario_data = {
            'pipeline_version': ENHANCED_PIPELINE_VERSION,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'case_id': case.id,
            'events': all_events,
            'ordering': ordering,
            'stats': stats,
            'participants': [p['name'] for p in participants],
            'enhanced_participants': participants,
            'ontology_summary': ontology_summary,
            'temporal_evidence': temporal_evidence,
            'extraction_metadata': enhanced_timeline.get('extraction_metadata', {}),
            'ontology_enrichment_status': enhanced_timeline.get('ontology_enrichment_status', 'not_attempted')
        }
        
        return scenario_data

    def _build_evidence_based_ordering(self, events: List[Dict[str, Any]], temporal_evidence: List[Dict[str, Any]]) -> List[str]:
        """Build event ordering based on temporal evidence."""
        # Start with sequence numbers from timeline events
        ordered_events = []
        
        # Sort timeline events by sequence number
        timeline_events = [e for e in events if e.get('sequence_number')]
        timeline_events.sort(key=lambda x: x.get('sequence_number', 0))
        
        # Add decision events after their triggers
        decision_events = [e for e in events if e.get('kind') == 'decision']
        
        # Simple ordering: timeline events first, then decisions
        for event in timeline_events:
            ordered_events.append(event['id'])
            
        for event in decision_events:
            ordered_events.append(event['id'])
            
        return ordered_events

    def _build_enhanced_ontology_summary(self, enhanced_timeline: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced ontology summary from enriched data."""
        summary = {}
        
        # Extract ontology categories from participants
        participants = enhanced_timeline.get('participants', [])
        roles = []
        for participant in participants:
            if participant.get('ontology_role'):
                roles.append(participant['ontology_role']['label'])
        summary['Role'] = list(set(roles))
        
        # Extract categories from decisions
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        for category in ['Principle', 'Obligation', 'Action', 'State', 'Resource', 'Event', 'Capability', 'Constraint']:
            category_items = []
            for decision in decisions:
                ontology_cats = getattr(decision, 'ontology_categories', {})
                if isinstance(ontology_cats, dict) and category.lower() in ontology_cats:
                    category_items.extend([item['label'] for item in ontology_cats[category.lower()]])
            summary[category] = list(set(category_items))
        
        return summary

    def _save_enhanced_scenario(self, case: Document, scenario_data: Dict[str, Any], overwrite: bool):
        """Save enhanced scenario data to database."""
        metadata = case.doc_metadata or {}
        versions = metadata.get('scenario_versions', [])
        
        content_hash = hashlib.sha256(str(scenario_data['stats']).encode('utf-8')).hexdigest()[:12]
        scenario_data['hash'] = content_hash
        scenario_data['version_number'] = len(versions) + 1

        if overwrite:
            versions.append(scenario_data)
        else:
            if not versions or versions[-1].get('hash') != content_hash:
                versions.append(scenario_data)

        metadata['scenario_versions'] = versions
        metadata['latest_scenario'] = scenario_data
        case.doc_metadata = dict(metadata)
        flag_modified(case, 'doc_metadata')
        db.session.add(case)
        db.session.commit()
        return scenario_data

    async def _enrich_with_ontology(self, timeline_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich timeline data with MCP ontology integration."""
        try:
            async with MCPOntologyClient() as mcp_client:
                # Enrich participants with ontological roles
                for participant in timeline_data.get('participants', []):
                    role_entity = await mcp_client.map_participant_to_role(participant['name'])
                    if role_entity:
                        participant['ontology_role'] = {
                            'uri': role_entity.uri,
                            'label': role_entity.label,
                            'confidence': role_entity.confidence
                        }
                
                # Enrich decisions with ontological categories
                for decision in timeline_data.get('enhanced_decisions', []):
                    ontology_enrichment = await mcp_client.enrich_decision_with_ontology(
                        decision.question, 
                        decision.context
                    )
                    decision.ontology_categories = ontology_enrichment
                
                timeline_data['ontology_enrichment_status'] = 'success'
                
        except Exception as e:
            logger.error(f"MCP ontology enrichment failed: {e}")
            timeline_data['ontology_enrichment_status'] = 'failed'
            timeline_data['ontology_enrichment_error'] = str(e)
            
        return timeline_data

    def _build_enhanced_scenario_data(self, case: Document, enhanced_timeline: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced scenario data structure."""
        timeline_events = enhanced_timeline.get('timeline_events', [])
        enhanced_decisions = enhanced_timeline.get('enhanced_decisions', [])
        participants = enhanced_timeline.get('participants', [])
        temporal_evidence = enhanced_timeline.get('temporal_evidence', [])
        
        # Convert enhanced decisions to event format
        decision_events = []
        for decision in enhanced_decisions:
            decision_event = {
                'id': decision.id,
                'kind': 'decision',
                'title': decision.title,
                'text': decision.question,
                'question': decision.question,
                'context': decision.context,
                'section': decision.section_source,
                'ontology_categories': decision.ontology_categories,
                'temporal_triggers': decision.temporal_triggers,
                'options': self.enhanced_service.generate_decision_options(decision, metadata),
                'enhanced_decision': True
            }
            decision_events.append(decision_event)
        
        # Combine timeline events and decisions
        all_events = timeline_events + decision_events
        
        # Build ordering from temporal evidence
        ordering = self._build_evidence_based_ordering(all_events, temporal_evidence)
        
        # Calculate stats
        stats = {
            'event_count': len(all_events),
            'decision_count': len(decision_events),
            'timeline_events': len(timeline_events),
            'temporal_evidence_count': len(temporal_evidence),
            'participants_count': len(participants)
        }
        
        # Build enhanced ontology summary
        ontology_summary = self._build_enhanced_ontology_summary(enhanced_timeline)
        
        scenario_data = {
            'pipeline_version': ENHANCED_PIPELINE_VERSION,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'case_id': case.id,
            'events': all_events,
            'ordering': ordering,
            'stats': stats,
            'participants': [p['name'] for p in participants],
            'enhanced_participants': participants,
            'ontology_summary': ontology_summary,
            'temporal_evidence': temporal_evidence,
            'extraction_metadata': enhanced_timeline.get('extraction_metadata', {}),
            'ontology_enrichment_status': enhanced_timeline.get('ontology_enrichment_status', 'not_attempted')
        }
        
        return scenario_data

    def _build_evidence_based_ordering(self, events: List[Dict[str, Any]], temporal_evidence: List[Dict[str, Any]]) -> List[str]:
        """Build event ordering based on temporal evidence."""
        # Start with sequence numbers from timeline events
        ordered_events = []
        
        # Sort timeline events by sequence number
        timeline_events = [e for e in events if e.get('sequence_number')]
        timeline_events.sort(key=lambda x: x.get('sequence_number', 0))
        
        # Add decision events after their triggers
        decision_events = [e for e in events if e.get('kind') == 'decision']
        
        # Simple ordering: timeline events first, then decisions
        for event in timeline_events:
            ordered_events.append(event['id'])
            
        for event in decision_events:
            ordered_events.append(event['id'])
            
        return ordered_events

    def _build_enhanced_ontology_summary(self, enhanced_timeline: Dict[str, Any]) -> Dict[str, Any]:
        """Build enhanced ontology summary from enriched data."""
        summary = {}
        
        # Extract ontology categories from participants
        participants = enhanced_timeline.get('participants', [])
        roles = []
        for participant in participants:
            if participant.get('ontology_role'):
                roles.append(participant['ontology_role']['label'])
        summary['Role'] = list(set(roles))
        
        # Extract categories from decisions
        decisions = enhanced_timeline.get('enhanced_decisions', [])
        for category in ['Principle', 'Obligation', 'Action', 'State', 'Resource', 'Event', 'Capability', 'Constraint']:
            category_items = []
            for decision in decisions:
                ontology_cats = getattr(decision, 'ontology_categories', {})
                if isinstance(ontology_cats, dict) and category.lower() in ontology_cats:
                    category_items.extend([item['label'] for item in ontology_cats[category.lower()]])
            summary[category] = list(set(category_items))
        
        return summary

    def _save_enhanced_scenario(self, case: Document, scenario_data: Dict[str, Any], overwrite: bool):
        """Save enhanced scenario data to database."""
        metadata = case.doc_metadata or {}
        versions = metadata.get('scenario_versions', [])
        
        content_hash = hashlib.sha256(str(scenario_data['stats']).encode('utf-8')).hexdigest()[:12]
        scenario_data['hash'] = content_hash
        scenario_data['version_number'] = len(versions) + 1

        if overwrite:
            versions.append(scenario_data)
        else:
            if not versions or versions[-1].get('hash') != content_hash:
                versions.append(scenario_data)

        metadata['scenario_versions'] = versions
        metadata['latest_scenario'] = scenario_data
        case.doc_metadata = dict(metadata)
        flag_modified(case, 'doc_metadata')
        db.session.add(case)
        db.session.commit()
