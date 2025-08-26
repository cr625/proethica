"""
Capabilities Extractor - Extraction of agent capabilities from guidelines.

This implements the Capabilities component of the 9-concept formalism:
Capabilities (Ca) - Dispositions or competencies required to perform role-appropriate actions.
"""

from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from config.models import ModelConfig

try:
    from app.utils.llm_utils import get_llm_client
except Exception:
    get_llm_client = None  # type: ignore


class CapabilitiesExtractor(Extractor):
    """Extract capabilities and competencies required for professional roles."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Extract capabilities with atomic concept splitting."""
        if not text:
            return []

        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('capability') or i.get('name') or ''
                        if label:
                            atomic_capabilities = self._split_compound_capability(label)
                            for atomic_label in atomic_capabilities:
                                candidates.append(ConceptCandidate(
                                    label=atomic_label,
                                    description=i.get('description') or i.get('explanation') or None,
                                    primary_type='capability',
                                    category='capability',
                                    confidence=float(i.get('confidence', 0.6)) if isinstance(i.get('confidence', 0.6), (int, float, str)) else 0.6,
                                    debug={
                                        'source': 'provider',
                                        'provider': self.provider,
                                        'original_compound': label if len(atomic_capabilities) > 1 else None
                                    }
                                ))
                    return candidates
            except Exception:
                pass
                
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction of capabilities and competencies."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # Capability patterns
        capability_patterns = [
            r"\b(competence|competency|expertise|proficiency|skill|ability)\b",
            r"\b(knowledge|understanding|experience|training|education)\b",
            r"\b(qualification|certification|license|accreditation)\b",
            r"\b(judgment|discretion|decision-making|problem-solving)\b",
            r"\b(technical competence|professional competence|specialized knowledge)\b",
            r"\b(communication skills|analytical skills|leadership skills)\b",
            r"\b(integrity|honesty|objectivity|reliability|trustworthiness)\b",
            r"\b(capacity|capability|aptitude|talent|proficiency)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in capability_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    # Capture capability context
                    start = max(0, match.start() - 15)
                    end = min(len(sentence), match.end() + 25)
                    capability_context = sentence[start:end].strip()
                    
                    # Extract capability phrase
                    capability_phrase = self._extract_capability_phrase(match.group(0), capability_context, sentence)
                    
                    # Split compound capabilities
                    atomic_capabilities = self._split_compound_capability(capability_phrase)
                    
                    for atomic_capability in atomic_capabilities:
                        key = atomic_capability.lower().strip()
                        if key in seen or len(key) < 5:
                            continue
                        seen.add(key)
                        
                        display_label = atomic_capability if len(atomic_capability) <= 85 else atomic_capability[:82] + '…'
                        capability_type = self._classify_capability_type(atomic_capability)
                        
                        results.append(ConceptCandidate(
                            label=display_label,
                            description=f"Capability: {atomic_capability}" if display_label != atomic_capability else None,
                            primary_type='capability',
                            category='capability',
                            confidence=0.6,
                            debug={
                                'source': 'heuristic_patterns',
                                'capability_type': capability_type,
                                'pattern_matched': pattern,
                                'guideline_id': guideline_id,
                                'original_compound': capability_phrase if len(atomic_capabilities) > 1 else None
                            }
                        ))
        
        return results

    def _extract_capability_phrase(self, matched_word: str, context: str, full_sentence: str) -> str:
        """Extract complete capability phrase."""
        word_pos = context.lower().find(matched_word.lower())
        if word_pos >= 0:
            # Look for descriptive modifiers
            start = max(0, word_pos - 10)
            end = min(len(context), word_pos + len(matched_word) + 20)
            capability_phrase = context[start:end].strip()
            return capability_phrase if len(capability_phrase) <= 70 else capability_phrase[:67] + '…'
        return matched_word

    def _split_compound_capability(self, capability_text: str) -> List[str]:
        """Split compound capabilities into atomic concepts."""
        if not capability_text or len(capability_text.strip()) < 5:
            return [capability_text]
            
        # Split on commas and 'and' 
        if ',' in capability_text or ' and ' in capability_text:
            parts = re.split(r'[,]|\s+and\s+', capability_text)
            parts = [part.strip() for part in parts if len(part.strip()) > 4]
            if len(parts) > 1:
                return parts
        
        return [capability_text]

    def _classify_capability_type(self, capability_text: str) -> str:
        """Classify capabilities by type."""
        text_lower = capability_text.lower()
        
        if any(word in text_lower for word in ['technical', 'engineering', 'specialized', 'expert']):
            return 'technical_capability'
        elif any(word in text_lower for word in ['professional', 'competence', 'competency']):
            return 'professional_capability'
        elif any(word in text_lower for word in ['communication', 'interpersonal', 'social']):
            return 'communication_capability'
        elif any(word in text_lower for word in ['analytical', 'problem-solving', 'decision-making']):
            return 'cognitive_capability'
        elif any(word in text_lower for word in ['leadership', 'management', 'supervisory']):
            return 'leadership_capability'
        elif any(word in text_lower for word in ['ethical', 'integrity', 'honesty', 'trustworthiness']):
            return 'ethical_capability'
        else:
            return 'general_capability'

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """LLM extraction with atomic splitting."""
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        prompt = f"""
Extract CAPABILITIES and competencies from this ethics guideline.

FOCUS: Skills, abilities, and competencies required for professional roles.

CAPABILITY TYPES:
- Technical capabilities: specialized knowledge, expertise
- Professional capabilities: competence, qualifications
- Communication capabilities: interpersonal skills
- Cognitive capabilities: judgment, problem-solving
- Ethical capabilities: integrity, honesty, objectivity

EXAMPLES:
- "Professional competence"
- "Technical expertise"
- "Ethical judgment"
- "Communication skills"

Extract atomic capabilities, not compound lists.

GUIDELINE TEXT:
{text}

Return JSON: [{{"label": "capability", "description": "description", "confidence": 0.7}}]
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
                return self._parse_json_items(text_out, root_key='capabilities')
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


class SimpleCapabilityMatcher:
    """URI matching for capabilities."""
    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'capability')
            uri = f"urn:proethica:capability:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.6},
                similarity=0.6,
                normalized_label=c.label,
                notes='derived: simple capability matcher'
            ))
        return results
