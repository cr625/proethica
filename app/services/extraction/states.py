"""
States Extractor - Extraction of states, conditions, and circumstances from guidelines.

This implements Checkpoint 2 of the 9-component extraction plan:
States (S) - Relevant states and conditions that affect ethical decisions.
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


class StatesExtractor(Extractor):
    """Extract states and conditions that trigger or affect ethical considerations.
    
    States represent circumstances, situations, or conditions that influence
    what ethical obligations are relevant and how they should be applied.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        # provider hint: 'anthropic'|'openai'|'gemini'|'auto'|None
        self.provider = (provider or 'auto').lower()
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_states_prompt_with_mcp(text)
    
    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Extract states and conditions from guideline text.
        
        Args:
            text: Guideline content to extract from
            world_id: World context for ontology matching
            guideline_id: Guideline ID for tracking
            
        Returns:
            List of ConceptCandidate objects for states/conditions
        """
        if not text:
            return []

        # Try provider-backed extraction first when configured and client available
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    return [
                        ConceptCandidate(
                            label=i.get('label') or i.get('state') or i.get('name') or '',
                            description=i.get('description') or i.get('explanation') or None,
                            primary_type='state',
                            category='state',
                            confidence=float(i.get('confidence', 0.6)) if isinstance(i.get('confidence', 0.6), (int, float, str)) else 0.6,
                            debug={'source': 'provider', 'provider': self.provider}
                        )
                        for i in items
                        if (i.get('label') or i.get('state') or i.get('name'))
                    ]
            except Exception:
                # Fall through to heuristic if provider path fails
                pass
                
        # Heuristic extraction as fallback
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction based on state/condition keywords and patterns."""
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        
        # State/condition keywords and patterns
        state_patterns = [
            # Conditional states
            r"\b(when|if|in case of|during|under circumstances|in situations where)\b",
            # Conflict and interest patterns  
            r"\b(conflict of interest|potential conflict|competing interests|personal interest)\b",
            # Safety and risk patterns
            r"\b(public safety risk|danger|hazardous condition|unsafe situation|emergency)\b",
            # Information states
            r"\b(confidential information|proprietary data|sensitive information|trade secrets)\b",
            # Competence states
            r"\b(lack of competence|inadequate knowledge|outside expertise|unfamiliar territory)\b",
            # Professional states
            r"\b(professional relationship|client relationship|employment relationship)\b"
        ]
        
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for sentence in sentences:
            if not sentence:
                continue
                
            for pattern in state_patterns:
                matches = re.finditer(pattern, sentence, re.IGNORECASE)
                for match in matches:
                    # Extract the broader context around the match
                    start = max(0, match.start() - 30)
                    end = min(len(sentence), match.end() + 50)
                    context = sentence[start:end].strip()
                    
                    # Use the matched phrase as the primary state
                    matched_text = match.group(0)
                    
                    # Create a label based on the match and context
                    if len(context) > len(matched_text) + 10:
                        label = context
                    else:
                        label = matched_text
                        
                    # Normalize for deduplication
                    key = label.lower().strip()
                    if key in seen or len(key) < 5:
                        continue
                    seen.add(key)
                    
                    # Truncate overly long labels
                    display_label = label if len(label) <= 120 else label[:117] + '…'
                    
                    # Classify the type of state
                    state_type = self._classify_state_type(matched_text, context)
                    
                    results.append(ConceptCandidate(
                        label=display_label,
                        description=f"State/condition: {label}" if display_label != label else None,
                        primary_type='state',
                        category='state',
                        confidence=0.55,
                        debug={
                            'source': 'heuristic_patterns',
                            'state_type': state_type,
                            'pattern_matched': pattern,
                            'guideline_id': guideline_id
                        }
                    ))
        
        return results

    def _classify_state_type(self, matched_text: str, context: str) -> str:
        """Classify the type of state based on the matched text and context."""
        text_lower = (matched_text + " " + context).lower()
        
        if any(word in text_lower for word in ['conflict', 'interest', 'competing']):
            return 'conflict_state'
        elif any(word in text_lower for word in ['safety', 'danger', 'hazard', 'risk', 'emergency']):
            return 'safety_state'
        elif any(word in text_lower for word in ['confidential', 'proprietary', 'sensitive', 'secret']):
            return 'information_state'
        elif any(word in text_lower for word in ['competence', 'knowledge', 'expertise', 'skill']):
            return 'competence_state'
        elif any(word in text_lower for word in ['relationship', 'client', 'employer', 'professional']):
            return 'relationship_state'
        elif any(word in text_lower for word in ['when', 'if', 'case', 'during', 'under']):
            return 'conditional_state'
        else:
            return 'general_state'

    # ---- Provider-backed helpers ----

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Call configured LLM provider to extract states as JSON with optional MCP context.

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
            
        use_external_mcp = True== 'true'
        
        if use_external_mcp:
            prompt = self._create_states_prompt_with_mcp(text)
        else:
            prompt = self._create_states_prompt(text)

        # Try Google Gemini style first
        try:
            if hasattr(client, 'GenerativeModel'):
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = client.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                output = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else '')
                return self._parse_json_items(output, root_key='states')
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
                        "Extract states and conditions from text and output ONLY JSON with key 'states'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                # Newer SDK returns content list with .text
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='states')
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
                return self._parse_json_items(text_out, root_key='states')
        except Exception:
            pass

        return []

    def _create_states_prompt(self, text: str) -> str:
        """Create standard states extraction prompt."""
        return f"""
You are an ontology-aware extractor. From the guideline excerpt, list distinct states and conditions.

FOCUS: Extract states, conditions, and circumstances that affect ethical decisions.

STATE TYPES TO EXTRACT:
1. **Conflict States**: Situations involving conflicts of interest, competing loyalties
2. **Safety States**: Conditions involving public safety, danger, emergencies
3. **Information States**: Situations involving confidential, proprietary, or sensitive information
4. **Competence States**: Conditions related to professional competence, knowledge limitations
5. **Relationship States**: Professional relationships, client situations, employment contexts
6. **Conditional States**: "When/if" scenarios that trigger specific obligations

EXAMPLES:
- "Conflict of interest"
- "Public safety risk" 
- "Confidential information"
- "Outside area of competence"
- "Emergency situation"
- "Client relationship"

Return STRICT JSON with an array under key 'states'. Each item: {{label, description, confidence}}.

Guideline excerpt:
{text}
"""

    def _create_states_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced states prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching states context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing states from ontology (if available)
            try:
                existing_states = external_client.get_all_state_entities()
            except AttributeError:
                # Method might not exist yet, fall back to empty
                existing_states = []
            
            # Build ontology context
            ontology_context = "EXISTING STATES IN ONTOLOGY:\n"
            if existing_states:
                ontology_context += f"Found {len(existing_states)} existing state concepts:\n"
                for state in existing_states:  # Show all states
                    label = state.get('label', 'Unknown')
                    description = state.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
            else:
                ontology_context += "No existing states found in ontology (or method not available)\n"
            
            logger.info(f"Retrieved {len(existing_states)} existing states from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract STATES and CONDITIONS.

IMPORTANT: Consider the existing states above when extracting. For each state you extract:
1. Check if it matches an existing state (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Extract states, conditions, and circumstances that affect ethical decisions.

STATE TYPES TO EXTRACT:
1. **Conflict States**: Situations involving conflicts of interest, competing loyalties
2. **Safety States**: Conditions involving public safety, danger, emergencies  
3. **Information States**: Situations involving confidential, proprietary, or sensitive information
4. **Competence States**: Conditions related to professional competence, knowledge limitations
5. **Relationship States**: Professional relationships, client situations, employment contexts
6. **Conditional States**: "When/if" scenarios that trigger specific obligations

EXAMPLES:
- "Conflict of interest" - State where personal interests may compete with professional duties
- "Public safety risk" - Condition where public welfare may be endangered
- "Confidential information" - State involving sensitive or proprietary data
- "Outside area of competence" - Condition of lacking required expertise
- "Emergency situation" - Critical state requiring immediate response

GUIDELINES:
- Extract conditions and circumstances, not actions or principles
- Focus on situational contexts that affect ethical decision-making
- States should describe "when" or "under what conditions" ethics apply
- Include both explicit and implicit state descriptions

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'states':
[
  {{
    "label": "Conflict of interest",
    "description": "A situation where personal interests may compromise professional judgment", 
    "confidence": 0.8,
    "is_existing": false,
    "ontology_match_reasoning": "Similar to existing conflict states but more specific"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous states and conditions.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for states: {e}")
            logger.info("Falling back to standard states prompt")
            return self._create_states_prompt(text)

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Best-effort parse of JSON content possibly wrapped in code fences."""
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


class StatesLinker(Linker):
    """Link states to roles and other concepts based on contextual relevance."""

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        """Generate contextual links between states and other concepts."""
        triples: List[SemanticTriple] = []

        # Partition matched concepts by type
        states = [m for m in matches if (m.candidate.primary_type or '').lower() == 'state']
        roles = [m for m in matches if (m.candidate.primary_type or '').lower() in {'role', 'professionalrole', 'participantrole'}]
        obligations = [m for m in matches if (m.candidate.primary_type or '').lower() == 'obligation']

        # Link states to roles (contextualizes obligations)
        for state in states:
            state_uri = (state.ontology_match or {}).get('uri')
            if not state_uri:
                continue

            # Link to relevant roles based on state type
            state_type = state.candidate.debug.get('state_type', 'general_state')
            
            for role in roles:
                role_uri = (role.ontology_match or {}).get('uri')
                if not role_uri:
                    continue
                    
                # Create contextual relationship based on state type
                predicate_uri = self._get_state_role_predicate(state_type)
                
                if predicate_uri:
                    triples.append(
                        SemanticTriple(
                            subject_uri=role_uri,
                            predicate_uri=predicate_uri,
                            object_uri=state_uri,
                            context={'guideline_id': guideline_id, 'state_type': state_type} if guideline_id else {'state_type': state_type},
                            is_approved=False,
                        )
                    )

        return triples

    def _get_state_role_predicate(self, state_type: str) -> Optional[str]:
        """Get appropriate predicate for linking states to roles."""
        state_predicates = {
            'conflict_state': 'facesConflictIn',
            'safety_state': 'respondsToSafetyIn',
            'information_state': 'handlesInformationIn',
            'competence_state': 'requiresCompetenceFor',
            'relationship_state': 'engagedInRelationship',
            'conditional_state': 'applicableWhen',
            'general_state': 'operatesUnder'
        }
        return state_predicates.get(state_type, 'operatesUnder')


class SimpleStateMatcher:
    """Assigns stable derived URIs for states when no ontology match exists.

    URI scheme: urn:proethica:state:<slug>
    """

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'state')
            uri = f"urn:proethica:state:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.6},
                chosen_parent=None,
                similarity=0.6,
                normalized_label=c.label,
                notes='derived: simple state matcher'
            ))
        return results
