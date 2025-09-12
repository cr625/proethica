"""
Actions Extractor - Extraction of performable actions from guidelines.

This implements the Actions component of the 9-concept formalism:
Actions (A) - Processes or interventions that role-bearers can initiate in fulfilling obligations.
"""

from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from models import ModelConfig

# LLM utils are optional at runtime; import guarded
try:
    from app.utils.llm_utils import get_llm_client
except Exception:  # pragma: no cover - environment without Flask/LLM
    get_llm_client = None  # type: ignore


class ActionsExtractor(Extractor):
    """Extract performable actions from guideline text with atomic concept splitting."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_actions_prompt_with_mcp(text)
    
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Extract actions with atomic concept splitting for compound actions."""
        if not text:
            return []

        # Try provider-backed extraction first
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('action') or i.get('name') or ''
                        if label:
                            # Split compound actions into atomic concepts
                            atomic_actions = self._split_compound_action(label)
                            for atomic_label in atomic_actions:
                                candidates.append(ConceptCandidate(
                                    label=atomic_label,
                                    description=i.get('description') or i.get('explanation') or None,
                                    primary_type='action',
                                    category='action',
                                    confidence=float(i.get('confidence', 0.6)) if isinstance(i.get('confidence', 0.6), (int, float, str)) else 0.6,
                                    debug={
                                        'source': 'provider', 
                                        'provider': self.provider,
                                        'original_compound': label if len(atomic_actions) > 1 else None
                                    }
                                ))
                    return candidates
            except Exception:
                pass
                
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction of action verbs and processes."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # Action verb patterns
        action_patterns = [
            r"\b(disclose|inform|notify|communicate|report)\b",
            r"\b(avoid|prevent|minimize|eliminate|reduce)\b", 
            r"\b(maintain|uphold|preserve|protect|safeguard)\b",
            r"\b(perform|execute|conduct|carry out|implement)\b",
            r"\b(evaluate|assess|analyze|review|examine)\b",
            r"\b(consult|collaborate|coordinate|cooperate)\b",
            r"\b(design|develop|create|build|construct)\b",
            r"\b(monitor|supervise|oversee|manage|control)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in action_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    # Capture broader action context
                    start = max(0, match.start() - 10)
                    end = min(len(sentence), match.end() + 40)
                    action_context = sentence[start:end].strip()
                    
                    # Extract clean action phrase
                    action_phrase = self._extract_action_phrase(match.group(0), action_context, sentence)
                    
                    # Split compound actions
                    atomic_actions = self._split_compound_action(action_phrase)
                    
                    for atomic_action in atomic_actions:
                        key = atomic_action.lower().strip()
                        if key in seen or len(key) < 5:
                            continue
                        seen.add(key)
                        
                        display_label = atomic_action if len(atomic_action) <= 80 else atomic_action[:77] + '…'
                        action_type = self._classify_action_type(atomic_action)
                        
                        results.append(ConceptCandidate(
                            label=display_label,
                            description=f"Action: {atomic_action}" if display_label != atomic_action else None,
                            primary_type='action',
                            category='action',
                            confidence=0.6,
                            debug={
                                'source': 'heuristic_patterns',
                                'action_type': action_type,
                                'pattern_matched': pattern,
                                'guideline_id': guideline_id,
                                'original_compound': action_phrase if len(atomic_actions) > 1 else None
                            }
                        ))
        
        return results

    def _extract_action_phrase(self, matched_verb: str, context: str, full_sentence: str) -> str:
        """Extract a complete action phrase from matched verb and context."""
        verb_pos = context.lower().find(matched_verb.lower())
        if verb_pos >= 0:
            # Get the action phrase starting from the verb
            action_start = verb_pos
            # Look for sentence boundaries or conjunctions
            action_end = len(context)
            for delimiter in [',', ';', ' and ', ' or ', ' but ']:
                delim_pos = context.find(delimiter, action_start)
                if delim_pos > action_start and delim_pos < action_end:
                    action_end = delim_pos
            
            action_phrase = context[action_start:action_end].strip()
            return action_phrase if len(action_phrase) <= 100 else action_phrase[:97] + '…'
        
        return matched_verb

    def _split_compound_action(self, action_text: str) -> List[str]:
        """Split compound actions into atomic concepts."""
        if not action_text or len(action_text.strip()) < 5:
            return [action_text]
            
        # Pattern 1: Comma-separated actions
        if ',' in action_text:
            parts = [part.strip() for part in action_text.split(',')]
            # Filter meaningful action parts
            parts = [part for part in parts if len(part) > 5 and re.search(r'\b(disclose|avoid|maintain|perform|evaluate|consult|design|monitor|inform|protect|prevent|analyze|review|conduct|implement|coordinate|develop|manage|communicate|report|notify|uphold|preserve|safeguard|execute|carry|build|construct|supervise|oversee|control|minimize|eliminate|reduce)\b', part, re.IGNORECASE)]
            if len(parts) > 1:
                return parts
        
        # Pattern 2: "X and Y" action constructions
        and_pattern = r'\b(\w+(?:\s+\w+)*)\s+and\s+(\w+(?:\s+\w+)*)'
        and_match = re.search(and_pattern, action_text, re.IGNORECASE)
        if and_match:
            first_action = and_match.group(1).strip()
            second_action = and_match.group(2).strip()
            
            # Check if both parts contain action verbs
            action_verbs = ['disclose', 'avoid', 'maintain', 'perform', 'evaluate', 'consult', 'inform', 'protect', 'prevent', 'analyze', 'review']
            if any(verb in first_action.lower() for verb in action_verbs) and any(verb in second_action.lower() for verb in action_verbs):
                return [first_action, second_action]
        
        return [action_text]

    def _classify_action_type(self, action_text: str) -> str:
        """Classify actions by type."""
        text_lower = action_text.lower()
        
        if any(word in text_lower for word in ['disclose', 'inform', 'notify', 'communicate', 'report']):
            return 'communication_action'
        elif any(word in text_lower for word in ['avoid', 'prevent', 'minimize', 'eliminate']):
            return 'prevention_action'
        elif any(word in text_lower for word in ['maintain', 'uphold', 'preserve', 'protect']):
            return 'maintenance_action'
        elif any(word in text_lower for word in ['perform', 'execute', 'conduct', 'implement']):
            return 'performance_action'
        elif any(word in text_lower for word in ['evaluate', 'assess', 'analyze', 'review']):
            return 'evaluation_action'
        elif any(word in text_lower for word in ['consult', 'collaborate', 'coordinate']):
            return 'collaboration_action'
        elif any(word in text_lower for word in ['design', 'develop', 'create', 'build']):
            return 'creation_action'
        else:
            return 'general_action'

    # Provider-backed methods (similar to other extractors)
    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Extract actions using LLM with atomic splitting guidance."""
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        prompt = f"""
Extract performable ACTIONS from this ethics guideline.

IMPORTANT: Extract atomic actions, not compound statements. Split complex actions.

EXAMPLES of GOOD atomic actions:
- "Disclose conflicts of interest"
- "Maintain professional competence" 
- "Protect confidential information"
- "Seek qualified assistance"

AVOID compound actions like:
- "Disclose and avoid conflicts of interest" (should be split)
- "Maintain competence and protect information" (should be split)

GUIDELINE TEXT:
{text}

Return STRICT JSON with array under key 'actions':
[{{"label": "action", "description": "what this action does", "confidence": 0.8}}]
"""

        # Use same LLM calling pattern as other extractors
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system="Extract atomic actions from text and output ONLY JSON with key 'actions'.",
                    messages=[{"role": "user", "content": prompt}],
                )
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='actions')
        except Exception:
            pass

        return []

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Parse JSON response for actions."""
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", s)
        try:
            if s.strip().startswith('['):
                arr = json.loads(s)
                return arr if isinstance(arr, list) else []
        except Exception:
            pass
        try:
            obj = json.loads(s)
            val = obj.get(root_key)
            if isinstance(val, list):
                return val
        except Exception:
            try:
                m = _re.search(r"\[(?:.|\n)*\]", s)
                if m:
                    return json.loads(m.group(0))
            except Exception:
                return []
        return []
    
    def _create_actions_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced actions prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching actions context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing actions from ontology (if available)
            try:
                existing_actions = external_client.get_all_action_entities()
            except AttributeError:
                # Method might not exist yet in MCP client
                existing_actions = []
                logger.warning("MCP client method get_all_action_entities() not found")
            
            # Build ontology context
            ontology_context = "EXISTING ACTIONS IN ONTOLOGY:\n"
            if existing_actions:
                ontology_context += f"Found {len(existing_actions)} existing action concepts:\n"
                for item in existing_actions[:20]:  # Show first 20
                    label = item.get('label', 'Unknown')
                    description = item.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
                if len(existing_actions) > 20:
                    ontology_context += f"... and {len(existing_actions) - 20} more\n"
            else:
                ontology_context += "No existing actions found in ontology (fresh setup or method not available)\n"
            
            logger.info(f"Retrieved {len(existing_actions)} existing actions from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract ACTIONS.

IMPORTANT: Consider the existing actions above when extracting. For each action you extract:
1. Check if it matches an existing action (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Extract performable actions from the professional ethics guideline.

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'actions':
[
  {{
    "label": "Action name",
    "description": "Description of the action", 
    "confidence": 0.8,
    "is_existing": false,
    "ontology_match_reasoning": "Reasoning for match or new classification"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous actions.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for actions: {e}")
            logger.info("Falling back to standard actions prompt")
            # Fall back to non-MCP prompt
            return f"""
Extract performable ACTIONS from this ethics guideline.

GUIDELINE TEXT:
{text}

Return STRICT JSON with array under key 'actions':
[{{"label": "action", "description": "what this action does", "confidence": 0.8}}]
"""


class SimpleActionMatcher:
    """URI matching for actions."""
    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'action')
            uri = f"urn:proethica:action:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.6},
                similarity=0.6,
                normalized_label=c.label,
                notes='derived: simple action matcher'
            ))
        return results
