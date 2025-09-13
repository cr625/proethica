from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .atomic_extraction_mixin import AtomicExtractionMixin
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from models import ModelConfig

# LLM utils are optional at runtime; import guarded
try:
    from app.utils.llm_utils import get_llm_client
except Exception:  # pragma: no cover - environment without Flask/LLM
    get_llm_client = None  # type: ignore


class ObligationsExtractor(Extractor, AtomicExtractionMixin):
    """Minimal scaffold for obligations extraction.

    Current behavior: placeholder heuristic that returns no items.
    TODO: implement provider-backed extraction (Gemini/OpenAI/MCP) per plan.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        # provider hint: 'anthropic'|'openai'|'gemini'|'auto'|None
        self.provider = (provider or 'auto').lower()
    
    @property
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        return 'obligation'
    
    def _get_prompt_for_preview(self, text: str) -> str:
        """Get the actual prompt that will be sent to the LLM, including MCP context."""
        # Always use external MCP (required for system to function)
        return self._create_obligations_prompt_with_mcp(text)

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Extract obligation concepts with unified atomic splitting and label normalization.
        
        This uses the standardized atomic extraction framework to handle compound obligations.
        """
        if not text:
            return []

        # Step 1: Initial extraction (without custom atomic splitting)
        initial_candidates = self._extract_initial_concepts(text, world_id=world_id, guideline_id=guideline_id)
        
        # Step 2: Apply unified atomic splitting and normalization
        return self._apply_atomic_splitting(initial_candidates)
    
    def _extract_initial_concepts(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Initial obligation extraction without atomic splitting.
        
        This preserves the original extraction logic but removes custom splitting.
        """
        # Try provider-backed extraction first when configured and client available
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    candidates = []
                    for i in items:
                        label = i.get('label') or i.get('obligation') or i.get('name') or ''
                        if label:
                            candidates.append(ConceptCandidate(
                                label=label,  # No custom splitting here
                                description=i.get('description') or i.get('explanation') or None,
                                primary_type='obligation',
                                category='obligation',
                                confidence=float(i.get('confidence', 0.7)) if isinstance(i.get('confidence', 0.7), (int, float, str)) else 0.7,
                                debug={'source': 'provider', 'provider': self.provider}
                            ))
                    return candidates
            except Exception:
                # Fall through to heuristic if provider path fails
                pass
                
        # Heuristic extraction as fallback
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Heuristic extraction for obligation concepts.
        
        Extracts concepts without custom atomic splitting - that's handled by the unified framework.
        """
        # Split into sentences conservatively
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        modals = re.compile(r"\b(must|shall|should|required to|responsible for|obliged to|obligation to)\b", re.IGNORECASE)
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for s in sentences:
            if not s:
                continue
            if modals.search(s):
                # Extract the raw sentence - unified framework will handle splitting
                label = s.strip()
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                
                # Truncate overly long labels for display; keep full text in description
                display = label if len(label) <= 160 else label[:157] + '…'
                
                results.append(ConceptCandidate(
                    label=display,
                    description=label if display != label else None,
                    primary_type='obligation',
                    category='obligation',
                    confidence=0.5,
                    debug={
                        'source': 'heuristic_modals',
                        'guideline_id': guideline_id
                    }
                ))
        return results


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
            
        use_external_mcp = True== 'true'
        
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
        """Create enhanced obligations prompt with Pass 2 integration and MCP context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching obligations context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing obligations AND principles for Pass 2 relationship
            existing_obligations = external_client.get_all_obligation_entities()
            existing_principles = external_client.get_all_principle_entities()
            
            # Build hierarchical ontology context
            mcp_context = ""
            
            # Organize obligations hierarchically
            base_obligation = None
            specific_obligations = []
            
            # De-duplicate and organize
            seen_labels = set()
            for obligation in existing_obligations:
                label = obligation.get('label', '')
                if label in seen_labels:
                    continue
                seen_labels.add(label)
                
                description = obligation.get('description', obligation.get('definition', ''))
                
                # Organize by hierarchy
                if label == 'Obligation':
                    if not base_obligation:
                        base_obligation = {'label': label, 'definition': description}
                else:
                    specific_obligations.append({'label': label, 'definition': description})
            
            # Build hierarchical context
            mcp_context = f"""
EXISTING OBLIGATIONS IN ONTOLOGY (Hierarchical View):
Found {len(seen_labels)} obligation concepts organized by hierarchy:

**BASE CLASS:**
- **{base_obligation['label'] if base_obligation else 'Obligation'}**: {base_obligation['definition'] if base_obligation else 'Concrete professional duties that must be performed, derived from principles and activated by role-state combinations.'}
  (This is the parent class for all obligation concepts)

**SPECIFIC OBLIGATIONS (Direct instances):**
"""
            for spec in sorted(specific_obligations, key=lambda x: x['label']):
                mcp_context += f"- **{spec['label']}**: {spec['definition']}\n"
            
            # Add Pass 2 integration context
            mcp_context += f"""

**PASS 2 INTEGRATION (Normative Requirements):**
You are extracting OBLIGATIONS as part of Pass 2, which transforms abstract principles into concrete requirements:
- **Principles** (WHY): Abstract ethical foundations - {len(existing_principles)} principles available
- **Obligations** (WHAT): Concrete duties derived from principles
- **Constraints** (HOW LIMITED): Boundaries on obligation fulfillment
- **Capabilities** (WHO CAN): Required competencies to fulfill obligations

**RELATIONSHIP TO PRINCIPLES:**
Each obligation should trace back to one or more principles:
"""
            # Show principle-obligation relationships
            principle_names = [p.get('label', '') for p in existing_principles if p.get('label')]
            for principle in principle_names[:5]:  # Show first 5 principles
                mcp_context += f"- {principle} → Specific obligations\n"
            
            logger.info(f"Retrieved {len(existing_obligations)} obligations and {len(existing_principles)} principles from MCP")
            
            # Create enhanced prompt with full Pass 2 context
            enhanced_prompt = f"""{mcp_context}

Extract professional obligations and duties from the following discussion/analysis text.

THEORETICAL FRAMEWORK:
Obligations operationalize abstract principles into concrete duties (Hallamaa & Kalliokoski 2022). They carry deontic force through modal operators (Wooldridge & Jennings 1995) and activate based on professional roles and contexts (Dennis et al. 2016).

OBLIGATION CATEGORIES:
1. **Mandatory professional duties** - MUST/SHALL requirements
2. **Role-specific obligations** - Duties tied to specific professional roles
3. **Legal vs ethical obligations** - Distinguish regulatory from moral requirements  
4. **Obligation conflicts and prioritization** - When duties conflict

EXTRACTION FOCUS:
- Statements with deontic operators (must, shall, should, required to, obligated to)
- Professional duties implied by the situation
- Obligations from multiple stakeholder perspectives
- Context-specific duties beyond general principles
- Obligations that may conflict with each other

Text:
{text}

Return as JSON array of obligation objects with these fields:
[
  {{
    "label": "Report safety hazards",
    "description": "Engineer must report safety hazards to appropriate authorities",
    "obligation_type": "mandatory_duty",  // mandatory_duty, role_specific, legal, ethical
    "enforcement_level": "mandatory",  // mandatory, strongly_recommended, recommended
    "derived_from_principle": "Public Welfare Principle",  // Which principle(s) justify this
    "stakeholders_affected": ["public", "client", "regulatory authorities"],
    "potential_conflicts": ["Client confidentiality"],  // Other obligations this might conflict with
    "confidence": 0.9,
    "is_existing": false,  // true if matches existing ontology obligation
    "ontology_match_reasoning": "New specific obligation not in existing ontology"
  }}
]

Focus on concrete, actionable obligations that professionals must fulfill.
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
