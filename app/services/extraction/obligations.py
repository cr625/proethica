from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from config.models import ModelConfig

# LLM utils are optional at runtime; import guarded
try:
    from app.utils.llm_utils import get_llm_client
except Exception:  # pragma: no cover - environment without Flask/LLM
    get_llm_client = None  # type: ignore


class ObligationsExtractor(Extractor):
    """Minimal scaffold for obligations extraction.

    Current behavior: placeholder heuristic that returns no items.
    TODO: implement provider-backed extraction (Gemini/OpenAI/MCP) per plan.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        # provider hint: 'anthropic'|'openai'|'gemini'|'auto'|None
        self.provider = (provider or 'auto').lower()

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Enhanced extraction with atomic concept splitting for compound obligations.

        This addresses the compound concept issue where complex obligations like:
        "Practice only within areas of competence, Avoid and disclose conflicts of interest"
        should be split into atomic concepts.
        """
        if not text:
            return []

        # Try provider-backed extraction first when configured and client available
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('obligation') or i.get('name') or ''
                        if label:
                            # Split compound obligations into atomic concepts
                            atomic_obligations = self._split_compound_obligation(label)
                            for atomic_label in atomic_obligations:
                                candidates.append(ConceptCandidate(
                                    label=atomic_label,
                                    description=i.get('description') or i.get('explanation') or None,
                                    primary_type='obligation',
                                    category='obligation',
                                    confidence=float(i.get('confidence', 0.7)) if isinstance(i.get('confidence', 0.7), (int, float, str)) else 0.7,
                                    debug={
                                        'source': 'provider', 
                                        'provider': self.provider,
                                        'original_compound': label if len(atomic_obligations) > 1 else None
                                    }
                                ))
                    return candidates
            except Exception:
                # Fall through to heuristic if provider path fails
                pass
                
        # Heuristic extraction with atomic splitting
        return self._extract_heuristic_with_atomic_splitting(text, guideline_id)

    def _extract_heuristic_with_atomic_splitting(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction with compound obligation splitting."""
        # Split into sentences conservatively
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        modals = re.compile(r"\b(must|shall|should|required to|responsible for|obliged to|obligation to)\b", re.IGNORECASE)
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for s in sentences:
            if not s:
                continue
            if modals.search(s):
                # Split compound obligations into atomic parts
                atomic_obligations = self._split_compound_obligation(s.strip())
                
                for atomic_label in atomic_obligations:
                    # Normalize and dedupe on lowercase label
                    key = atomic_label.lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    # Truncate overly long labels for display; keep full text in description
                    display = atomic_label if len(atomic_label) <= 160 else atomic_label[:157] + '…'
                    
                    results.append(ConceptCandidate(
                        label=display,
                        description=atomic_label if display != atomic_label else None,
                        primary_type='obligation',
                        category='obligation',
                        confidence=0.5,
                        debug={
                            'source': 'heuristic_modals_atomic',
                            'guideline_id': guideline_id,
                            'original_sentence': s.strip() if len(atomic_obligations) > 1 else None
                        }
                    ))
        return results

    def _split_compound_obligation(self, obligation_text: str) -> List[str]:
        """Split compound obligations into atomic concepts.
        
        Examples:
        - "Practice only within areas of competence, avoid conflicts of interest"
          -> ["Practice only within areas of competence", "Avoid conflicts of interest"]
        - "Disclose and avoid conflicts of interest"  
          -> ["Disclose conflicts of interest", "Avoid conflicts of interest"]
        """
        if not obligation_text or len(obligation_text.strip()) < 10:
            return [obligation_text]
            
        # Pattern 1: Simple comma-separated obligations
        if ',' in obligation_text:
            parts = [part.strip() for part in obligation_text.split(',')]
            # Filter out very short parts (likely conjunctions)
            parts = [part for part in parts if len(part) > 8 and any(modal in part.lower() for modal in ['shall', 'must', 'should', 'avoid', 'disclose', 'maintain', 'ensure', 'perform', 'provide'])]
            if len(parts) > 1:
                return parts
        
        # Pattern 2: "X and Y" constructions with obligation verbs
        and_pattern = r'\b(shall|must|should)\s+([^,]+)\s+and\s+([^,.]+)'
        and_match = re.search(and_pattern, obligation_text, re.IGNORECASE)
        if and_match:
            modal = and_match.group(1)
            first_action = and_match.group(2).strip()
            second_action = and_match.group(3).strip()
            
            # Create two separate atomic obligations
            return [
                f"{modal} {first_action}",
                f"{modal} {second_action}"
            ]
        
        # Pattern 3: "Disclose and avoid" type constructions  
        verb_and_verb_pattern = r'\b(\w+)\s+and\s+(\w+)\s+([^,.]+)'
        verb_match = re.search(verb_and_verb_pattern, obligation_text, re.IGNORECASE)
        if verb_match and any(verb.lower() in ['disclose', 'avoid', 'maintain', 'ensure', 'protect'] for verb in [verb_match.group(1), verb_match.group(2)]):
            verb1 = verb_match.group(1)
            verb2 = verb_match.group(2)
            object_phrase = verb_match.group(3).strip()
            
            return [
                f"{verb1} {object_phrase}",
                f"{verb2} {object_phrase}"
            ]
        
        # Pattern 4: Multiple modal verbs in one sentence
        multi_modal_pattern = r'(shall [^,]+),?\s*(?:and\s+)?(shall|must|should) ([^,.]+)'
        multi_match = re.search(multi_modal_pattern, obligation_text, re.IGNORECASE)
        if multi_match:
            first_obligation = multi_match.group(1).strip()
            second_modal = multi_match.group(2)
            second_action = multi_match.group(3).strip()
            
            return [
                first_obligation,
                f"{second_modal} {second_action}"
            ]
        
        # If no compound patterns found, return as single obligation
        return [obligation_text]

    # ---- Provider-backed helpers ----

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Call configured LLM provider to extract obligations as JSON with optional MCP context.

        Returns a list of dicts with keys like label, description, confidence.
        """
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        # Check for external MCP integration
        import os
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        use_external_mcp = os.environ.get('ENABLE_EXTERNAL_MCP_ACCESS', 'false').lower() == 'true'
        
        if use_external_mcp:
            prompt = self._create_obligations_prompt_with_mcp(text)
        else:
            prompt = self._create_obligations_prompt(text)

        # Try Google Gemini style first (client is a module with GenerativeModel)
        try:
            if hasattr(client, 'GenerativeModel'):
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = client.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                output = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else '')
                return self._parse_json_items(output, root_key='obligations')
        except Exception:
            pass

        # Try Anthropic messages API
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system=(
                        "Extract professional obligations from text and output ONLY JSON with key 'obligations'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                # Newer SDK returns content list with .text
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='obligations')
        except Exception:
            pass

        # Try OpenAI Chat Completions
        try:
            if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_out = resp.choices[0].message.content if getattr(resp, 'choices', None) else ''
                return self._parse_json_items(text_out, root_key='obligations')
        except Exception:
            pass

        return []

    def _create_obligations_prompt(self, text: str) -> str:
        """Create standard obligations extraction prompt."""
        return (
            "You are an ontology-aware extractor. From the guideline excerpt, list distinct professional obligations.\n"
            "Return STRICT JSON with an array under key 'obligations'. Each item: {label, description, confidence}.\n"
            "Guideline excerpt:\n" + text
        )

    def _create_obligations_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced obligations prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching obligations context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing obligations from ontology
            existing_obligations = external_client.get_all_obligation_entities()
            
            # Build ontology context
            ontology_context = "EXISTING OBLIGATIONS IN ONTOLOGY:\n"
            if existing_obligations:
                ontology_context += f"Found {len(existing_obligations)} existing obligation concepts:\n"
                for obligation in existing_obligations[:10]:  # Show first 10 examples
                    label = obligation.get('label', 'Unknown')
                    description = obligation.get('description', 'No description')[:80]
                    ontology_context += f"- {label}: {description}\n"
                if len(existing_obligations) > 10:
                    ontology_context += f"... and {len(existing_obligations) - 10} more obligations\n"
            else:
                ontology_context += "No existing obligations found in ontology (fresh setup)\n"
            
            logger.info(f"Retrieved {len(existing_obligations)} existing obligations from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract OBLIGATIONS.

IMPORTANT: Consider the existing obligations above when extracting. For each obligation you extract:
1. Check if it matches an existing obligation (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Professional obligations, duties, and requirements that roles must fulfill.

OBLIGATION TYPES:
1. **Direct Obligations**: Specific duties that must be performed
2. **Prohibitive Obligations**: Things that must not be done
3. **Conditional Obligations**: Duties that apply in specific circumstances
4. **Disclosure Obligations**: Requirements to inform or reveal information

EXAMPLES:
- "Engineers shall hold paramount the safety of the public"
- "Avoid conflicts of interest"
- "Disclose potential conflicts to clients"
- "Maintain competence in their field"

GUIDELINES:
- Extract statements that describe what someone MUST, SHALL, or SHOULD do
- Include obligations that contain modal verbs (must, shall, should, required to)
- Focus on professional duties, not general principles
- Each obligation should be actionable and specific

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'obligations':
[
  {{
    "label": "Hold paramount public safety",
    "description": "Engineers must prioritize public safety above all other considerations", 
    "confidence": 0.9,
    "is_existing": false,
    "ontology_match_reasoning": "Similar to existing safety obligations but more specific"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous obligations.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for obligations: {e}")
            logger.info("Falling back to standard obligations prompt")
            return self._create_obligations_prompt(text)
    
    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Best-effort parse of JSON content possibly wrapped in code fences.

        Returns list under the given root_key, or tries to interpret raw as array directly.
        """
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        # Strip markdown fences
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\n|\n```$", "", s)
        # If it's a bare array, wrap into object
        try:
            if s.strip().startswith('['):
                arr = json.loads(s)
                return arr if isinstance(arr, list) else []
        except Exception:
            pass
        # Try as object with root_key
        try:
            obj = json.loads(s)
            val = obj.get(root_key)
            if isinstance(val, list):
                return val
        except Exception:
            # last resort: find first [...] block
            try:
                m = _re.search(r"\[(?:.|\n)*\]", s)
                if m:
                    return json.loads(m.group(0))
            except Exception:
                return []
        return []


class ObligationsLinker(Linker):
    """Minimal linker for Role→hasObligation→Obligation.

    Expects matches to include candidate.primary_type for both subject (role) and object (obligation),
    and ontology_match with 'uri'. The actual role matches are expected to come from the roles pass.
    """

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        triples: List[SemanticTriple] = []

        # Partition matched concepts by type
        roles = [m for m in matches if (m.candidate.primary_type or '').lower() in {'role', 'professionalrole', 'participantrole'}]
        obligations = [m for m in matches if (m.candidate.primary_type or '').lower() == 'obligation']

        for role in roles:
            subj_uri = (role.ontology_match or {}).get('uri')
            subj_type = (role.candidate.primary_type or '')
            if not subj_uri:
                continue

            for ob in obligations:
                obj_uri = (ob.ontology_match or {}).get('uri')
                if not obj_uri:
                    continue

                obj_type = (ob.candidate.primary_type or '')
                if not self.gate.can_link_has_obligation(subj_type, obj_type):
                    continue

                triples.append(
                    SemanticTriple(
                        subject_uri=subj_uri,
                        predicate_uri='hasObligation',  # resolved later to canonical URI in persistence/formatter
                        object_uri=obj_uri,
                        context={'guideline_id': guideline_id} if guideline_id else {},
                        is_approved=False,
                    )
                )

        return triples


class SimpleObligationMatcher:
    """Assigns a stable derived URI for obligations when no ontology match exists.

    URI scheme (temporary derived): urn:proethica:obligation:<slug>
    """

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'obligation')
            uri = f"urn:proethica:obligation:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.5},
                chosen_parent=None,
                similarity=0.5,
                normalized_label=c.label,
                notes='derived: simple matcher'
            ))
        return results
