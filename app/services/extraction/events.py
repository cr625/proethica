"""
Events Extractor - Extraction of triggering events from guidelines.

This implements the Events component of the 9-concept formalism:
Events (E) - Events or situations that give rise to ethical relevance or require decision-making.
"""

from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from models import ModelConfig

try:
    from app.utils.llm_utils import get_llm_client
except Exception:
    get_llm_client = None  # type: ignore


class EventsExtractor(Extractor):
    """Extract triggering events that create ethical considerations."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_events_prompt_with_mcp(text)
    
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Extract events with atomic concept splitting."""
        if not text:
            return []

        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('event') or i.get('name') or ''
                        if label:
                            atomic_events = self._split_compound_event(label)
                            for atomic_label in atomic_events:
                                candidates.append(ConceptCandidate(
                                    label=atomic_label,
                                    description=i.get('description') or i.get('explanation') or None,
                                    primary_type='event',
                                    category='event',
                                    confidence=float(i.get('confidence', 0.55)) if isinstance(i.get('confidence', 0.55), (int, float, str)) else 0.55,
                                    debug={
                                        'source': 'provider',
                                        'provider': self.provider,
                                        'original_compound': label if len(atomic_events) > 1 else None
                                    }
                                ))
                    return candidates
            except Exception:
                pass
                
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction of triggering events."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # Event trigger patterns
        event_patterns = [
            r"\b(failure|accident|incident|emergency|crisis|disaster)\b",
            r"\b(violation|breach|non-compliance|misconduct|error)\b",
            r"\b(conflict|dispute|disagreement|controversy|issue)\b", 
            r"\b(deadline|milestone|completion|delivery|launch)\b",
            r"\b(inspection|audit|review|assessment|evaluation)\b",
            r"\b(injury|harm|damage|loss|threat|risk)\b",
            r"\b(discovery|finding|identification|detection|report)\b",
            r"\b(change|modification|alteration|update|revision)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in event_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    # Capture event context
                    start = max(0, match.start() - 20)
                    end = min(len(sentence), match.end() + 30)
                    event_context = sentence[start:end].strip()
                    
                    # Extract event phrase
                    event_phrase = self._extract_event_phrase(match.group(0), event_context, sentence)
                    
                    # Split compound events
                    atomic_events = self._split_compound_event(event_phrase)
                    
                    for atomic_event in atomic_events:
                        key = atomic_event.lower().strip()
                        if key in seen or len(key) < 6:
                            continue
                        seen.add(key)
                        
                        display_label = atomic_event if len(atomic_event) <= 90 else atomic_event[:87] + '…'
                        event_type = self._classify_event_type(atomic_event)
                        
                        results.append(ConceptCandidate(
                            label=display_label,
                            description=f"Event: {atomic_event}" if display_label != atomic_event else None,
                            primary_type='event',
                            category='event',
                            confidence=0.55,
                            debug={
                                'source': 'heuristic_patterns',
                                'event_type': event_type,
                                'pattern_matched': pattern,
                                'guideline_id': guideline_id,
                                'original_compound': event_phrase if len(atomic_events) > 1 else None
                            }
                        ))
        
        return results

    def _extract_event_phrase(self, matched_word: str, context: str, full_sentence: str) -> str:
        """Extract complete event phrase."""
        # Look for descriptive words before and after the match
        word_pos = context.lower().find(matched_word.lower())
        if word_pos >= 0:
            start = max(0, word_pos - 15)
            end = min(len(context), word_pos + len(matched_word) + 15)
            event_phrase = context[start:end].strip()
            return event_phrase if len(event_phrase) <= 80 else event_phrase[:77] + '…'
        return matched_word

    def _split_compound_event(self, event_text: str) -> List[str]:
        """Split compound events into atomic concepts."""
        if not event_text or len(event_text.strip()) < 5:
            return [event_text]
            
        # Simple comma and 'and' splitting
        if ',' in event_text or ' and ' in event_text:
            parts = re.split(r'[,]|\s+and\s+', event_text)
            parts = [part.strip() for part in parts if len(part.strip()) > 5]
            if len(parts) > 1:
                return parts
        
        return [event_text]

    def _classify_event_type(self, event_text: str) -> str:
        """Classify events by type."""
        text_lower = event_text.lower()
        
        if any(word in text_lower for word in ['failure', 'accident', 'emergency', 'crisis', 'disaster']):
            return 'crisis_event'
        elif any(word in text_lower for word in ['violation', 'breach', 'misconduct', 'error']):
            return 'compliance_event'
        elif any(word in text_lower for word in ['conflict', 'dispute', 'disagreement']):
            return 'conflict_event'
        elif any(word in text_lower for word in ['deadline', 'milestone', 'completion', 'delivery']):
            return 'project_event'
        elif any(word in text_lower for word in ['inspection', 'audit', 'review', 'assessment']):
            return 'evaluation_event'
        elif any(word in text_lower for word in ['injury', 'harm', 'damage', 'threat']):
            return 'safety_event'
        else:
            return 'general_event'

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """LLM-based extraction with atomic event guidance."""
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        prompt = f"""
Extract triggering EVENTS from this ethics guideline.

FOCUS: Events that create ethical considerations or trigger obligations.

EVENT TYPES:
- Crisis events: failures, accidents, emergencies
- Compliance events: violations, breaches, misconduct  
- Conflict events: disputes, disagreements, controversies
- Project events: deadlines, milestones, deliveries
- Safety events: injuries, harm, threats, risks

EXAMPLES:
- "Project failure"
- "Safety incident" 
- "Conflict of interest discovery"
- "Emergency situation"
- "Deadline pressure"

Extract atomic events, not compound descriptions.

GUIDELINE TEXT:
{text}

Return JSON: [{{"label": "event", "description": "description", "confidence": 0.7}}]
"""

        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=600,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='events')
        except Exception:
            pass
        return []

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", s)
        try:
            if s.strip().startswith('['):
                return json.loads(s)
        except Exception:
            pass
        try:
            obj = json.loads(s)
            return obj.get(root_key, [])
        except Exception:
            return []
    
    def _create_events_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced events prompt with external MCP ontology context."""
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching events context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            try:
                existing_events = external_client.get_all_event_entities()
            except AttributeError:
                existing_events = []
                logger.warning("MCP client method get_all_event_entities() not found")
            
            ontology_context = "EXISTING EVENTS IN ONTOLOGY:\n"
            if existing_events:
                ontology_context += f"Found {len(existing_events)} existing event concepts:\n"
                for item in existing_events[:20]:
                    label = item.get('label', 'Unknown')
                    description = item.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
            else:
                ontology_context += "No existing events found in ontology\n"
            
            logger.info(f"Retrieved {len(existing_events)} existing events from external MCP for context")
            
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract EVENTS.

FOCUS: Extract events that trigger ethical considerations.

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'events':
[{{"label": "Event name", "description": "Description", "confidence": 0.8}}]
"""
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for events: {e}")
            return f"Extract events from: {text}"


class SimpleEventMatcher:
    """URI matching for events."""
    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'event')
            uri = f"urn:proethica:event:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.55},
                similarity=0.55,
                normalized_label=c.label,
                notes='derived: simple event matcher'
            ))
        return results
