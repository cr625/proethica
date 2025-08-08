"""Enhanced LLM Scenario Service for high-quality timeline generation.

This service extends the existing LangChainClaudeService to provide specialized
scenario generation capabilities with semantic understanding, temporal reasoning,
and ontology integration.

Key Features:
- Semantic timeline extraction from case sections
- Context-aware decision identification
- Evidence-based temporal ordering
- NSPE code reference generation
- Ontology-guided participant mapping
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from app.services.langchain_claude import LangChainClaudeService

logger = logging.getLogger(__name__)

@dataclass
class TemporalEvidence:
    """Evidence for event ordering based on textual markers."""
    event_id: str
    sequence_marker: str
    marker_type: str  # 'temporal', 'causal', 'explicit_sequence', 'section_structure'
    confidence: float
    context: str

@dataclass
class EnhancedDecision:
    """Rich decision structure with contextual information."""
    id: str
    title: str
    question: str
    context: str
    section_source: str
    temporal_triggers: List[str]
    ontology_categories: List[str]
    evidence_text: str

@dataclass
class ParticipantMapping:
    """Participant with ontological role mapping."""
    name: str
    role_type: str
    ontology_label: Optional[str]
    capabilities: List[str]
    obligations: List[str]
    context_mentions: List[str]

class EnhancedLLMScenarioService:
    """Enhanced scenario generation service using LLM for semantic analysis."""
    
    def __init__(self):
        """Initialize with existing LangChain service."""
        self.llm_service = LangChainClaudeService.get_instance()
        self.feature_enabled = os.environ.get('ENHANCED_SCENARIO_GENERATION', 'true').lower() == 'true'
        self.max_timeline_events = int(os.environ.get('ENHANCED_SCENARIO_MAX_EVENTS', '20'))
        self.max_decisions = int(os.environ.get('ENHANCED_SCENARIO_MAX_DECISIONS', '8'))
        logger.info(f"Enhanced LLM Scenario Service initialized, feature_enabled={self.feature_enabled}")

    def extract_semantic_timeline(self, case_sections: Dict[str, Any], case_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Extract semantic timeline using LLM analysis of case sections.
        
        Args:
            case_sections: Dictionary containing case sections (facts, discussion, etc.)
            case_metadata: Case metadata including questions_list, conclusion_items
            
        Returns:
            Dictionary containing timeline events, decisions, and temporal evidence
        """
        if not self.feature_enabled:
            logger.info("Enhanced scenario generation disabled, skipping LLM timeline extraction")
            return {"events": [], "decisions": [], "temporal_evidence": []}
            
        try:
            # Extract temporal evidence first (non-LLM basis)
            temporal_evidence = self._extract_temporal_evidence(case_sections)
            
            # Generate semantic timeline using LLM
            timeline_events = self._generate_timeline_events(case_sections, case_metadata)
            
            # Extract enhanced decisions from questions
            enhanced_decisions = self._extract_enhanced_decisions(case_sections, case_metadata)
            
            # Extract participant mappings
            participants = self._extract_participants(case_sections, timeline_events)
            
            logger.info(f"Extracted {len(timeline_events)} timeline events, {len(enhanced_decisions)} decisions")
            
            return {
                "timeline_events": timeline_events,
                "enhanced_decisions": enhanced_decisions,
                "temporal_evidence": [self._temporal_evidence_to_dict(te) for te in temporal_evidence],
                "participants": [self._participant_to_dict(p) for p in participants],
                "extraction_metadata": {
                    "generated_at": datetime.utcnow().isoformat(),
                    "llm_model": self.llm_service.model,
                    "evidence_sources": len(temporal_evidence),
                    "feature_flags": {
                        "enhanced_timeline": True,
                        "temporal_evidence": True,
                        "semantic_decisions": True
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error in semantic timeline extraction: {str(e)}", exc_info=True)
            return {"events": [], "decisions": [], "temporal_evidence": [], "error": str(e)}

    def _extract_temporal_evidence(self, sections: Dict[str, Any]) -> List[TemporalEvidence]:
        """Extract temporal evidence markers for event ordering (non-LLM basis)."""
        evidence = []
        
        # Temporal markers to look for
        temporal_patterns = {
            'temporal': [
                r'\b(after|before|then|subsequently|following|prior to|during|while)\b',
                r'\b(first|second|third|next|finally|lastly|meanwhile)\b',
                r'\b(initially|eventually|ultimately|later|earlier)\b'
            ],
            'causal': [
                r'\b(as a result|therefore|consequently|because|due to|caused by)\b',
                r'\b(this led to|resulting in|which prompted|in response to)\b'
            ],
            'explicit_sequence': [
                r'\b(step \d+|phase \d+|stage \d+)\b',
                r'\b(\d+\.|first,|second,|third,)\b'
            ]
        }
        
        event_id_counter = 1
        
        for section_name, content in sections.items():
            if not content:
                continue
                
            # Handle both string and dict content
            text_content = content
            if isinstance(content, dict):
                text_content = content.get('text', content.get('content', str(content)))
            
            # Clean HTML if present
            text_content = re.sub(r'<[^>]+>', ' ', str(text_content))
            
            # Look for temporal patterns
            for marker_type, patterns in temporal_patterns.items():
                for pattern in patterns:
                    matches = re.finditer(pattern, text_content, re.IGNORECASE)
                    for match in matches:
                        # Extract context around the match
                        start = max(0, match.start() - 50)
                        end = min(len(text_content), match.end() + 100)
                        context = text_content[start:end].strip()
                        
                        evidence.append(TemporalEvidence(
                            event_id=f"evidence_{event_id_counter}",
                            sequence_marker=match.group(),
                            marker_type=marker_type,
                            confidence=self._calculate_marker_confidence(match.group(), marker_type),
                            context=context
                        ))
                        event_id_counter += 1
        
        # Add section structure evidence
        section_order = ['facts', 'discussion', 'question', 'conclusion']
        for i, section_name in enumerate(section_order):
            if section_name in sections and sections[section_name]:
                evidence.append(TemporalEvidence(
                    event_id=f"section_{section_name}",
                    sequence_marker=f"section_order_{i}",
                    marker_type='section_structure',
                    confidence=0.9,
                    context=f"Section {section_name} in position {i}"
                ))
        
        logger.info(f"Extracted {len(evidence)} temporal evidence markers")
        return evidence

    def _calculate_marker_confidence(self, marker: str, marker_type: str) -> float:
        """Calculate confidence score for temporal markers."""
        confidence_map = {
            'temporal': {
                'after': 0.9, 'before': 0.9, 'then': 0.8, 'subsequently': 0.85,
                'following': 0.8, 'prior to': 0.85, 'first': 0.9, 'finally': 0.9
            },
            'causal': {
                'as a result': 0.9, 'therefore': 0.85, 'consequently': 0.85,
                'because': 0.8, 'due to': 0.8, 'this led to': 0.9
            },
            'explicit_sequence': {
                'step': 0.95, 'phase': 0.9, 'stage': 0.9, 'first,': 0.9
            }
        }
        
        marker_lower = marker.lower()
        if marker_type in confidence_map:
            for key, conf in confidence_map[marker_type].items():
                if key in marker_lower:
                    return conf
        
        # Default confidence by marker type
        return {'temporal': 0.7, 'causal': 0.75, 'explicit_sequence': 0.8}.get(marker_type, 0.6)

    def _generate_timeline_events(self, sections: Dict[str, Any], metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate timeline events using LLM semantic analysis."""
        
        # Prepare context for LLM
        context_sections = []
        for section_name, content in sections.items():
            if content and section_name in ['facts', 'discussion']:
                text_content = content
                if isinstance(content, dict):
                    text_content = content.get('text', content.get('content', str(content)))
                
                # Clean and truncate
                text_content = re.sub(r'<[^>]+>', ' ', str(text_content))[:1000]
                context_sections.append(f"[{section_name.upper()}]\n{text_content}")
        
        context_text = "\n\n".join(context_sections)
        
        # Create LLM prompt for timeline extraction
        timeline_prompt = """You are analyzing an engineering ethics case to extract a chronological timeline of events and identify all participants with their professional roles.

CONTEXT:
{context}

TASK: Extract key events that form the chronological backbone of this case. Focus on:
1. Concrete actions taken by participants
2. Key discoveries or realizations
3. External events that influenced the situation
4. Decision points or moments of choice
5. Outcomes or consequences

PARTICIPANT IDENTIFICATION: For each participant mentioned, identify their professional role from the context:
- Professional Engineer, Engineering Consultant, Engineering Manager
- County Client, Municipal Client, State Agency, Government Department
- Corporate Client, Private Client
- Regulatory Body, Professional Society, Ethics Committee
- Contractor, Vendor, Supplier
- Public, Community, Stakeholder

GUIDELINES:
- Extract 5-15 significant events
- Each event should be a concrete occurrence, not abstract concepts
- Maintain chronological order when evident
- Focus on events that advance the narrative
- Include the main ethical dilemma emergence
- Extract professional roles directly from case text, not generic labels

FORMAT: Return JSON only with structure:
- timeline_events: array of event objects
- participants: array of participant objects with name and professional_role
- Each event should have: id, title, description, participants, event_type, section_source, chronological_indicators
- Each participant should have: name, professional_role, role_evidence (brief quote showing role)

Return only valid JSON, no explanations."""

        try:
            # Create and run the chain
            chain = self.llm_service.create_chain(timeline_prompt, ["context"])
            response = self.llm_service.run_chain(chain, context=context_text)
            
            logger.info(f"LLM timeline response: {response[:200]}...")
            
            # Strip markdown code blocks if present
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]  # Remove ```json
            if response_clean.startswith('```'):
                response_clean = response_clean[3:]  # Remove ```
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]  # Remove closing ```
            response_clean = response_clean.strip()
            
            # Parse JSON response
            timeline_data = json.loads(response_clean)
            events = timeline_data.get("timeline_events", [])
            participants = timeline_data.get("participants", [])
            
            # Add sequence numbers and additional metadata to events
            for i, event in enumerate(events):
                event["sequence_number"] = i + 1
                event["extraction_method"] = "llm_semantic"
                event["confidence_score"] = 0.85  # Base confidence for LLM extraction
            
            # Store participants for later use
            self.extracted_participants = participants
            logger.info(f"Extracted {len(participants)} participants: {[p.get('name') for p in participants]}")
                
            return events[:self.max_timeline_events]
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM timeline response: {e}")
            logger.error(f"Raw response: '{response}'")
            return []
        except Exception as e:
            logger.error(f"Error generating timeline events: {e}")
            return []

    def _extract_enhanced_decisions(self, sections: Dict[str, Any], metadata: Dict[str, Any]) -> List[EnhancedDecision]:
        """Extract enhanced decision points with rich context."""
        decisions = []
        
        # Get questions from metadata (preferred) or sections
        questions = metadata.get('questions_list', [])
        if not questions:
            question_section = sections.get('question', sections.get('questions', ''))
            if question_section:
                text_content = question_section
                if isinstance(question_section, dict):
                    text_content = question_section.get('text', question_section.get('content', ''))
                questions = self._split_questions(str(text_content))
        
        # Create LLM prompt for decision enhancement
        decision_prompt = """You are analyzing ethical decision questions from an engineering case.

QUESTIONS:
{questions_text}

CASE CONTEXT:
{case_context}

TASK: For each question, create an enhanced decision point with:
1. Clear decision title
2. Neutral, actionable question
3. Contextual background
4. Relevant ethical considerations
5. Potential ontological categories (Role, Principle, Obligation, State, Resource, Action, Event, Capability, Constraint)

FORMAT: Return JSON only with structure:
- enhanced_decisions: array of decision objects
- Each decision should have: id, title, question, context, ethical_considerations, ontology_categories, temporal_triggers, section_source

Return only valid JSON."""
        
        if not questions:
            return []
            
        try:
            questions_text = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)])
            
            # Get case context
            case_context = ""
            for section in ['facts', 'discussion']:
                if section in sections and sections[section]:
                    content = sections[section]
                    if isinstance(content, dict):
                        content = content.get('text', content.get('content', ''))
                    case_context += f"[{section.upper()}]\n{str(content)[:500]}...\n\n"
            
            # Create and run chain
            chain = self.llm_service.create_chain(decision_prompt, ["questions_text", "case_context"])
            response = self.llm_service.run_chain(chain, questions_text=questions_text, case_context=case_context)
            
            # Strip markdown code blocks if present
            response_clean = response.strip()
            if response_clean.startswith('```json'):
                response_clean = response_clean[7:]  # Remove ```json
            if response_clean.startswith('```'):
                response_clean = response_clean[3:]  # Remove ```
            if response_clean.endswith('```'):
                response_clean = response_clean[:-3]  # Remove closing ```
            response_clean = response_clean.strip()
            
            # Parse response
            decision_data = json.loads(response_clean)
            enhanced_decisions_data = decision_data.get("enhanced_decisions", [])
            
            # Convert to EnhancedDecision objects
            for i, decision_data in enumerate(enhanced_decisions_data[:self.max_decisions]):
                decisions.append(EnhancedDecision(
                    id=decision_data.get("id", f"decision_{i+1}"),
                    title=decision_data.get("title", ""),
                    question=decision_data.get("question", ""),
                    context=decision_data.get("context", ""),
                    section_source=decision_data.get("section_source", "question"),
                    temporal_triggers=decision_data.get("temporal_triggers", []),
                    ontology_categories=decision_data.get("ontology_categories", []),
                    evidence_text=questions[i] if i < len(questions) else ""
                ))
                
            return decisions
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM decisions response: {e}")
            return []
        except Exception as e:
            logger.error(f"Error extracting enhanced decisions: {e}")
            return []

    def _extract_participants(self, sections: Dict[str, Any], timeline_events: List[Dict[str, Any]]) -> List[ParticipantMapping]:
        """Extract and map participants to ontological roles using LLM-extracted data."""
        participants = []
        
        # Use LLM-extracted participants if available (preferred method)
        if hasattr(self, 'extracted_participants') and self.extracted_participants:
            logger.info(f"Using LLM-extracted participants: {len(self.extracted_participants)}")
            
            for participant_data in self.extracted_participants:
                name = participant_data.get('name', '').strip()
                professional_role = participant_data.get('professional_role', '').strip()
                role_evidence = participant_data.get('role_evidence', '').strip()
                
                if name and professional_role:
                    participant = ParticipantMapping(
                        name=name,
                        role_type='stakeholder',
                        ontology_label=professional_role,
                        capabilities=[],  # Will be populated by MCP
                        obligations=[],   # Will be populated by MCP
                        context_mentions=[f"LLM extracted with evidence: {role_evidence}"]
                    )
                    participants.append(participant)
                    logger.info(f"LLM participant: {name} -> {professional_role}")
            
            # Limit to reasonable number
            return participants[:8]
        
        # Fallback: Extract from timeline events if LLM extraction failed
        logger.info("Falling back to timeline-based participant extraction")
        participant_mentions = {}
        
        for event in timeline_events:
            for participant in event.get("participants", []):
                if participant not in participant_mentions:
                    participant_mentions[participant] = []
                participant_mentions[participant].append(f"Event: {event.get('title', '')}")
        
        # Create basic participant mappings with minimal role inference
        for participant_name in participant_mentions.keys():
            participant = ParticipantMapping(
                name=participant_name,
                role_type='stakeholder',
                ontology_label='Stakeholder',  # Generic fallback role
                capabilities=[],
                obligations=[],
                context_mentions=participant_mentions[participant_name][:2]
            )
            participants.append(participant)
        
        return participants[:8]  # Limit to reasonable number

    def _split_questions(self, text: str) -> List[str]:
        """Split question text into individual questions."""
        # Clean HTML
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Split on question marks followed by capital letters or common question starters
        splits = re.split(r'\?(?=\s*(?:[A-Z]|Should|Would|Is|Was|Were|How|What|When|Where|Why))', text)
        
        questions = []
        for split in splits:
            split = split.strip()
            if split and len(split) > 10:  # Minimum question length
                if not split.endswith('?'):
                    split += '?'
                questions.append(split)
        
        return questions

    def _temporal_evidence_to_dict(self, evidence: TemporalEvidence) -> Dict[str, Any]:
        """Convert TemporalEvidence to dictionary."""
        return {
            "event_id": evidence.event_id,
            "sequence_marker": evidence.sequence_marker,
            "marker_type": evidence.marker_type,
            "confidence": evidence.confidence,
            "context": evidence.context
        }

    def _participant_to_dict(self, participant: ParticipantMapping) -> Dict[str, Any]:
        """Convert ParticipantMapping to dictionary."""
        return {
            "name": participant.name,
            "role_type": participant.role_type,
            "ontology_label": participant.ontology_label,
            "capabilities": participant.capabilities,
            "obligations": participant.obligations,
            "context_mentions": participant.context_mentions
        }

    def generate_decision_options(self, decision: EnhancedDecision, case_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate contextual decision options with NSPE references (placeholder for Phase 4)."""
        # This will be fully implemented in Phase 4
        # For now, return basic structure
        return [
            {
                "id": "option_1",
                "label": "Full Disclosure",
                "description": "Explicitly disclose all relevant information to stakeholders",
                "nspe_status": "nspe_positive",
                "color": "green",
                "confidence": 0.8
            },
            {
                "id": "option_2", 
                "label": "Seek Guidance",
                "description": "Consult with supervisor or ethics committee before proceeding",
                "nspe_status": "neutral",
                "color": "yellow",
                "confidence": 0.85
            },
            {
                "id": "option_3",
                "label": "Document and Monitor",
                "description": "Document concerns and monitor situation before taking action",
                "nspe_status": "neutral",
                "color": "yellow",
                "confidence": 0.75
            }
        ]