"""
Constraints Extractor - Extraction of constraints from guidelines.

This implements the Constraints component of the 9-concept formalism:
Constraints (Cs) - Rules, regulations, or contextual constraints that limit actions or obligations.
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


class ConstraintsExtractor(Extractor):
    """Extract constraints that limit or govern professional actions."""

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_constraints_prompt_with_mcp(text)
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Extract constraints with atomic concept splitting."""
        if not text:
            return []

        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('constraint') or i.get('name') or ''
                        if label:
                            atomic_constraints = self._split_compound_constraint(label)
                            for atomic_label in atomic_constraints:
                                candidates.append(ConceptCandidate(
                                    label=atomic_label,
                                    description=i.get('description') or i.get('explanation') or None,
                                    primary_type='constraint',
                                    category='constraint',
                                    confidence=float(i.get('confidence', 0.65)) if isinstance(i.get('confidence', 0.65), (int, float, str)) else 0.65,
                                    debug={
                                        'source': 'provider',
                                        'provider': self.provider,
                                        'original_compound': label if len(atomic_constraints) > 1 else None
                                    }
                                ))
                    return candidates
            except Exception:
                pass
                
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction of constraints and limitations."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # Constraint patterns
        constraint_patterns = [
            r"\b(limitation|limit|restriction|constraint|boundary)\b",
            r"\b(prohibition|forbidden|not permitted|cannot|may not)\b",
            r"\b(requirement|prerequisite|condition|stipulation)\b",
            r"\b(regulation|law|rule|policy|standard|code)\b",
            r"\b(legal requirement|regulatory constraint|professional standard)\b",
            r"\b(time constraint|budget constraint|resource limitation)\b",
            r"\b(confidentiality agreement|non-disclosure|contract terms)\b",
            r"\b(licensing requirement|certification requirement|qualification standard)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in constraint_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    # Capture constraint context
                    start = max(0, match.start() - 20)
                    end = min(len(sentence), match.end() + 30)
                    constraint_context = sentence[start:end].strip()
                    
                    # Extract constraint phrase
                    constraint_phrase = self._extract_constraint_phrase(match.group(0), constraint_context, sentence)
                    
                    # Split compound constraints
                    atomic_constraints = self._split_compound_constraint(constraint_phrase)
                    
                    for atomic_constraint in atomic_constraints:
                        key = atomic_constraint.lower().strip()
                        if key in seen or len(key) < 6:
                            continue
                        seen.add(key)
                        
                        display_label = atomic_constraint if len(atomic_constraint) <= 90 else atomic_constraint[:87] + '…'
                        constraint_type = self._classify_constraint_type(atomic_constraint)
                        
                        results.append(ConceptCandidate(
                            label=display_label,
                            description=f"Constraint: {atomic_constraint}" if display_label != atomic_constraint else None,
                            primary_type='constraint',
                            category='constraint',
                            confidence=0.65,
                            debug={
                                'source': 'heuristic_patterns',
                                'constraint_type': constraint_type,
                                'pattern_matched': pattern,
                                'guideline_id': guideline_id,
                                'original_compound': constraint_phrase if len(atomic_constraints) > 1 else None
                            }
                        ))
        
        return results

    def _extract_constraint_phrase(self, matched_word: str, context: str, full_sentence: str) -> str:
        """Extract complete constraint phrase."""
        word_pos = context.lower().find(matched_word.lower())
        if word_pos >= 0:
            start = max(0, word_pos - 15)
            end = min(len(context), word_pos + len(matched_word) + 25)
            constraint_phrase = context[start:end].strip()
            return constraint_phrase if len(constraint_phrase) <= 80 else constraint_phrase[:77] + '…'
        return matched_word

    def _split_compound_constraint(self, constraint_text: str) -> List[str]:
        """Split compound constraints into atomic concepts."""
        if not constraint_text or len(constraint_text.strip()) < 5:
            return [constraint_text]
            
        # Split on commas and 'and'
        if ',' in constraint_text or ' and ' in constraint_text:
            parts = re.split(r'[,]|\s+and\s+', constraint_text)
            parts = [part.strip() for part in parts if len(part.strip()) > 5]
            if len(parts) > 1:
                return parts
        
        return [constraint_text]

    def _classify_constraint_type(self, constraint_text: str) -> str:
        """Classify constraints by type."""
        text_lower = constraint_text.lower()
        
        if any(word in text_lower for word in ['legal', 'law', 'regulation', 'statute']):
            return 'legal_constraint'
        elif any(word in text_lower for word in ['professional', 'code', 'ethics', 'standard']):
            return 'professional_constraint'
        elif any(word in text_lower for word in ['time', 'deadline', 'schedule', 'timing']):
            return 'temporal_constraint'
        elif any(word in text_lower for word in ['budget', 'cost', 'financial', 'resource']):
            return 'resource_constraint'
        elif any(word in text_lower for word in ['confidentiality', 'non-disclosure', 'privacy']):
            return 'information_constraint'
        elif any(word in text_lower for word in ['competence', 'qualification', 'certification']):
            return 'competence_constraint'
        else:
            return 'general_constraint'

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """LLM extraction with atomic splitting."""
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        prompt = f"""
Extract CONSTRAINTS from this ethics guideline.

FOCUS: Rules, regulations, limitations that constrain actions or obligations.

CONSTRAINT TYPES:
- Legal constraints: laws, regulations, statutes
- Professional constraints: codes, standards, policies
- Resource constraints: budget, time, material limitations
- Information constraints: confidentiality, non-disclosure
- Competence constraints: qualification requirements

EXAMPLES:
- "Licensing requirements"
- "Confidentiality agreements"
- "Professional standards"
- "Legal prohibitions"
- "Resource limitations"

Extract atomic constraints, not compound statements.

GUIDELINE TEXT:
{text}

Return JSON: [{{"label": "constraint", "description": "description", "confidence": 0.7}}]
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
                return self._parse_json_items(text_out, root_key='constraints')
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
    
    def _create_constraints_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced constraints prompt with external MCP ontology context."""
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching constraints context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            try:
                existing_constraints = external_client.get_all_constraint_entities()
            except AttributeError:
                existing_constraints = []
                logger.warning("MCP client method get_all_constraint_entities() not found")
            
            ontology_context = "EXISTING CONSTRAINTS IN ONTOLOGY:\n"
            if existing_constraints:
                ontology_context += f"Found {len(existing_constraints)} existing constraint concepts:\n"
                for item in existing_constraints[:20]:
                    label = item.get('label', 'Unknown')
                    description = item.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
            else:
                ontology_context += "No existing constraints found in ontology\n"
            
            logger.info(f"Retrieved {len(existing_constraints)} existing constraints from external MCP for context")
            
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract CONSTRAINTS.

FOCUS: Extract limitations, boundaries, and restrictions on professional behavior.

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'constraints':
[{{"label": "Constraint name", "description": "Description", "confidence": 0.8}}]
"""
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for constraints: {e}")
            return f"Extract constraints from: {text}"


class SimpleConstraintMatcher:
    """URI matching for constraints."""
    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'constraint')
            uri = f"urn:proethica:constraint:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.65},
                similarity=0.65,
                normalized_label=c.label,
                notes='derived: simple constraint matcher'
            ))
        return results
