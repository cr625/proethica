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


class PrinciplesExtractor(Extractor):
    """Lightweight heuristic extractor for principles.

    This is a placeholder baseline; replace with provider-backed extraction later.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        if not text:
            return []

        # Provider-backed attempt first if configured
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    return [
                        ConceptCandidate(
                            label=i.get('label') or i.get('principle') or i.get('name') or '',
                            description=i.get('description') or i.get('explanation') or None,
                            primary_type='principle',
                            category='principle',
                            confidence=float(i.get('confidence', 0.65)) if isinstance(i.get('confidence', 0.65), (int, float, str)) else 0.65,
                            debug={'source': 'provider', 'provider': self.provider}
                        )
                        for i in items
                        if (i.get('label') or i.get('principle') or i.get('name'))
                    ]
            except Exception:
                pass
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        # Common principle keywords in engineering ethics contexts
        kw = re.compile(r"\b(safety|welfare|integrity|honesty|objectivity|fairness|competence|confidentiality|public\s+welfare|responsibility|transparency|accountability|sustainability|respect|dignity|justice|equity|excellence|quality|trust|loyalty)\b", re.IGNORECASE)
        seen: Set[str] = set()
        out: List[ConceptCandidate] = []
        
        for s in sentences:
            if not s:
                continue
            if kw.search(s):
                # Extract atomic principles from the sentence
                atomic_items = self._ensure_atomic_principles([{'label': s.strip(), 'confidence': 0.45}])
                
                for item in atomic_items:
                    label = item.get('label', '')
                    key = label.lower()
                    if key in seen or not label:
                        continue
                    seen.add(key)
                    
                    out.append(ConceptCandidate(
                        label=label,
                        description=item.get('original_statement') if item.get('original_statement') else None,
                        primary_type='principle',
                        category='principle',
                        confidence=item.get('confidence', 0.45),
                        debug={'source': 'heuristic_keywords_atomic', 'guideline_id': guideline_id}
                    ))
        return out

    # ---- Provider-backed helpers ----
    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
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
            prompt = self._create_principles_prompt_with_mcp(text)
        else:
            prompt = self._create_principles_prompt(text)

        # Gemini
        try:
            if hasattr(client, 'GenerativeModel'):
                model_name = os.getenv('GEMINI_MODEL', 'gemini-1.5-pro')
                model = client.GenerativeModel(model_name)
                resp = model.generate_content(prompt)
                output = getattr(resp, 'text', None) or (resp.candidates[0].content.parts[0].text if getattr(resp, 'candidates', None) else '')
                principles = self._parse_json_items(output, root_key='principles')
                # Apply atomic splitting to ensure we get atomic concepts
                return self._ensure_atomic_principles(principles)
        except Exception:
            pass

        # Anthropic
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system=(
                        "Extract ethical principles from text and output ONLY JSON with key 'principles'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                principles = self._parse_json_items(text_out, root_key='principles')
                # Apply atomic splitting to ensure we get atomic concepts
                return self._ensure_atomic_principles(principles)
        except Exception:
            pass

        # OpenAI
        try:
            if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                model = os.getenv('OPENAI_CHAT_MODEL', 'gpt-4o-mini')
                resp = client.chat.completions.create(
                    model=model,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}],
                )
                text_out = resp.choices[0].message.content if getattr(resp, 'choices', None) else ''
                principles = self._parse_json_items(text_out, root_key='principles')
                # Apply atomic splitting to ensure we get atomic concepts
                return self._ensure_atomic_principles(principles)
        except Exception:
            pass

        return []
    
    def _apply_enhanced_splitting(self, candidates: List[Dict[str, Any]], concept_type: str) -> List[Dict[str, Any]]:
        """Apply enhanced concept splitting if enabled."""
        import os
        
        if os.environ.get('ENABLE_CONCEPT_SPLITTING', 'false').lower() != 'true':
            return candidates
            
        try:
            from .concept_splitter import split_concepts_for_extractor
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info(f"Applying enhanced splitting to {len(candidates)} {concept_type} candidates")
            
            # Convert dict candidates to ConceptCandidate objects for splitting
            from .base import ConceptCandidate
            concept_candidates = []
            
            for candidate in candidates:
                concept_candidates.append(ConceptCandidate(
                    label=candidate.get('label', ''),
                    description=candidate.get('description', ''),
                    confidence=candidate.get('confidence', 0.8),
                    primary_type=concept_type
                ))
            
            # Apply enhanced splitting
            enhanced_candidates = split_concepts_for_extractor(concept_candidates, concept_type)
            
            # Convert back to dict format
            result = []
            for candidate in enhanced_candidates:
                result.append({
                    'label': candidate.label,
                    'description': candidate.description,
                    'confidence': candidate.confidence
                })
            
            # Log splitting results
            if len(enhanced_candidates) != len(candidates):
                logger.info(f"Enhanced splitting: {len(candidates)} → {len(enhanced_candidates)} concepts")
                compounds_found = sum(1 for c in enhanced_candidates if hasattr(c, 'debug') and c.debug.get('atomic_decomposition'))
                if compounds_found > 0:
                    logger.info(f"Split {compounds_found} compound {concept_type} concepts into atomic parts")
            
            return result
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Enhanced splitting failed for {concept_type}, falling back to original: {e}")
            return candidates

    def _create_principles_prompt(self, text: str) -> str:
        """Create standard principles extraction prompt."""
        return (
            "You are an ontology-aware extractor. From the guideline excerpt, extract ATOMIC ethical principles.\n"
            "\n"
            "CRITICAL: Extract ATOMIC principles, not full statements:\n"
            "❌ WRONG: 'Engineers shall hold paramount the safety of the public'\n"
            "✓ RIGHT: 'Public Safety' (the core principle)\n"
            "\n"
            "❌ WRONG: 'Engineers shall maintain confidentiality'\n"
            "✓ RIGHT: 'Confidentiality' (the core principle)\n"
            "\n"
            "Examples of atomic principles:\n"
            "- Public Safety\n"
            "- Professional Integrity\n"
            "- Competence\n"
            "- Confidentiality\n"
            "- Objectivity\n"
            "- Sustainability\n"
            "- Transparency\n"
            "- Accountability\n"
            "- Fairness\n"
            "- Honesty\n"
            "\n"
            "Return STRICT JSON with an array under key 'principles'. Each item: {label, description, confidence}.\n"
            "Extract only the CORE PRINCIPLE NAME, not the full obligation statement.\n"
            "\n"
            "Guideline excerpt:\n" + text
        )

    def _create_principles_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced principles prompt with external MCP ontology context."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching principles context from external MCP server...")
            
            external_client = get_external_mcp_client()
            
            # Get existing principles from ontology
            existing_principles = external_client.get_all_principle_entities()
            
            # Build ontology context
            ontology_context = "EXISTING ATOMIC PRINCIPLES IN ONTOLOGY:\n"
            if existing_principles:
                ontology_context += f"Found {len(existing_principles)} existing atomic principle concepts:\n"
                
                # Group principles by type for better context
                atomic_examples = []
                for principle in existing_principles:
                    label = principle.get('label', 'Unknown')
                    # Only show truly atomic principles as examples
                    if len(label.split()) <= 3 and not any(word in label.lower() for word in ['shall', 'must', 'engineers']):
                        atomic_examples.append(label)
                
                # Show examples of atomic principles
                if atomic_examples:
                    ontology_context += "Examples of atomic principles in the ontology:\n"
                    for example in atomic_examples:  # Show all atomic examples
                        ontology_context += f"- {example}\n"
                
                # Add mapping guidance
                ontology_context += "\nPRINCIPLE MAPPING GUIDANCE:\n"
                ontology_context += "When you see statements like these, extract the atomic principle:\n"
                ontology_context += "- 'Hold paramount public safety' → 'Public Safety'\n"
                ontology_context += "- 'Act with professional integrity' → 'Professional Integrity'\n"
                ontology_context += "- 'Maintain competence' → 'Competence'\n"
                ontology_context += "- 'Ensure confidentiality' → 'Confidentiality'\n"
                ontology_context += "- 'Practice with honesty' → 'Honesty'\n"
                
                if len(existing_principles) > 15:
                    ontology_context += f"\n... and {len(existing_principles) - 15} more principles in the ontology\n"
            else:
                ontology_context += "No existing principles found in ontology (fresh setup)\n"
                ontology_context += "Focus on extracting atomic principle names like:\n"
                ontology_context += "- Public Safety\n- Integrity\n- Competence\n- Confidentiality\n- Honesty\n"
            
            logger.info(f"Retrieved {len(existing_principles)} existing principles from external MCP for context")
            
            # Create enhanced prompt with ontology context
            enhanced_prompt = f"""
{ontology_context}

You are an ontology-aware extractor analyzing an ethics guideline to extract PRINCIPLES.

IMPORTANT: Consider the existing principles above when extracting. For each principle you extract:
1. Check if it matches an existing principle (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

FOCUS: Fundamental ethical principles and values that guide professional behavior.

CRITICAL INSTRUCTION: Extract ATOMIC principles, not full statements!

When you see text like:
- "Engineers shall hold paramount the safety, health, and welfare of the public"
  → Extract: "Public Safety", "Public Health", "Public Welfare"
- "Engineers shall perform services only in areas of their competence"
  → Extract: "Competence"
- "Engineers shall act for each employer or client as faithful agents or trustees"
  → Extract: "Fidelity", "Trustworthiness"
- "Engineers shall avoid deceptive acts"
  → Extract: "Honesty", "Truthfulness"
- "Engineers shall maintain confidentiality"
  → Extract: "Confidentiality"

PRINCIPLE TYPES:
1. **Core Ethical Values**: integrity, honesty, justice, fairness, respect
2. **Professional Standards**: competence, diligence, excellence, quality
3. **Social Responsibilities**: public safety, public welfare, sustainability, environmental protection
4. **Information Ethics**: confidentiality, transparency, accuracy, objectivity
5. **Relationship Values**: fidelity, trustworthiness, loyalty, collaboration

EXAMPLES OF ATOMIC PRINCIPLES:
- "Public Safety" - NOT "hold paramount the safety of the public"
- "Competence" - NOT "perform services only in areas of competence"
- "Confidentiality" - NOT "maintain confidentiality of client information"
- "Integrity" - NOT "act with integrity in all professional matters"
- "Objectivity" - NOT "make objective and unbiased decisions"

GUIDELINES:
- Extract high-level guiding values and principles
- Focus on abstract concepts rather than specific actions
- Principles should be enduring values, not situational rules
- Each principle should represent a fundamental ethical commitment

GUIDELINE TEXT:
{text}

OUTPUT FORMAT:
Return STRICT JSON with an array under key 'principles':
[
  {{
    "label": "Public Safety",
    "description": "The fundamental principle that public welfare and safety must be prioritized", 
    "confidence": 0.9,
    "is_existing": false,
    "ontology_match_reasoning": "Similar to existing safety principles but more specific"
  }}
]

Focus on accuracy over quantity. Extract only clear, unambiguous principles.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for principles: {e}")
            logger.info("Falling back to standard principles prompt")
            return self._create_principles_prompt(text)

    def _ensure_atomic_principles(self, principles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure principles are atomic concepts, not full statements.
        
        This method processes extracted principles to ensure they are atomic concepts
        like "Public Safety" rather than full statements like "Hold paramount the safety of the public".
        """
        atomic_principles = []
        
        for principle in principles:
            label = principle.get('label', '')
            
            # Skip empty labels
            if not label:
                continue
                
            # Check if this looks like a full statement rather than an atomic principle
            if self._is_compound_principle(label):
                # Extract atomic principles from the statement
                atomic_labels = self._extract_atomic_from_statement(label)
                for atomic_label in atomic_labels:
                    atomic_principle = principle.copy()
                    atomic_principle['label'] = atomic_label
                    atomic_principle['original_statement'] = label
                    atomic_principles.append(atomic_principle)
            else:
                # Already atomic, just clean it up
                clean_label = self._clean_principle_label(label)
                if clean_label:
                    principle['label'] = clean_label
                    atomic_principles.append(principle)
        
        return atomic_principles
    
    def _is_compound_principle(self, label: str) -> bool:
        """Check if a principle label is a compound statement rather than atomic."""
        label_lower = label.lower()
        
        # Indicators of compound/statement principles
        compound_indicators = [
            'shall', 'must', 'should', 'will', 'engineers',
            'professionals', 'practitioners', 'members',
            'hold paramount', 'maintain', 'ensure', 'perform',
            'act with', 'act in', 'avoid', 'disclose'
        ]
        
        # Check for sentence-like structures
        has_subject_verb = any(indicator in label_lower for indicator in compound_indicators)
        is_long = len(label.split()) > 5  # Atomic principles are usually 1-3 words
        
        return has_subject_verb or is_long
    
    def _extract_atomic_from_statement(self, statement: str) -> List[str]:
        """Extract atomic principle concepts from a full statement."""
        statement_lower = statement.lower()
        atomic_principles = []
        
        # Key principle mappings
        principle_mappings = {
            'safety': 'Public Safety',
            'health': 'Public Health', 
            'welfare': 'Public Welfare',
            'confidential': 'Confidentiality',
            'competenc': 'Competence',
            'integrity': 'Integrity',
            'honest': 'Honesty',
            'truthful': 'Truthfulness',
            'objective': 'Objectivity',
            'objectivity': 'Objectivity',
            'fair': 'Fairness',
            'sustain': 'Sustainability',
            'environment': 'Environmental Protection',
            'transparen': 'Transparency',
            'accountab': 'Accountability',
            'respect': 'Respect',
            'dignit': 'Human Dignity',
            'justice': 'Justice',
            'equity': 'Equity',
            'diligen': 'Diligence',
            'excellence': 'Excellence',
            'quality': 'Quality',
            'faithful': 'Fidelity',
            'trust': 'Trustworthiness',
            'loyal': 'Loyalty'
        }
        
        # Check for each principle keyword in the statement
        for keyword, principle in principle_mappings.items():
            if keyword in statement_lower and principle not in atomic_principles:
                atomic_principles.append(principle)
        
        # If no principles found, try to extract the core concept
        if not atomic_principles:
            # Remove common prefixes
            clean = statement
            for prefix in ['Engineers shall', 'Engineers must', 'Members shall', 'Professionals must', 
                          'Practitioners should', 'One must', 'They shall']:
                if clean.startswith(prefix):
                    clean = clean[len(prefix):].strip()
                    break
            
            # Look for verb-object patterns
            verb_patterns = [
                ('maintain', 'Maintenance'),
                ('ensure', 'Assurance'),
                ('protect', 'Protection'),
                ('promote', 'Promotion'),
                ('uphold', 'Upholding'),
                ('preserve', 'Preservation')
            ]
            
            for verb, nominal in verb_patterns:
                if clean.lower().startswith(verb):
                    # Extract the object of the verb
                    obj = clean[len(verb):].strip()
                    if obj:
                        # Clean up the object
                        obj = obj.strip('.,;')
                        if len(obj.split()) <= 3:
                            atomic_principles.append(obj.title())
                        
        # If still no principles, and it's a short phrase, use it as-is
        if not atomic_principles and len(statement.split()) <= 3:
            atomic_principles.append(self._clean_principle_label(statement))
        
        return atomic_principles if atomic_principles else []
    
    def _clean_principle_label(self, label: str) -> str:
        """Clean up a principle label to be more atomic."""
        # Remove articles and common words
        stopwords = {'the', 'a', 'an', 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'by'}
        words = label.split()
        
        # Filter out stopwords except when they're essential (like "of" in "Code of Ethics")
        cleaned_words = []
        for i, word in enumerate(words):
            if word.lower() not in stopwords or (i > 0 and i < len(words) - 1):
                cleaned_words.append(word)
        
        cleaned = ' '.join(cleaned_words)
        
        # Ensure proper capitalization
        if cleaned:
            # Title case for multi-word principles
            if ' ' in cleaned:
                cleaned = ' '.join(word.capitalize() for word in cleaned.split())
            else:
                # Single words - capitalize first letter
                cleaned = cleaned[0].upper() + cleaned[1:] if len(cleaned) > 1 else cleaned.upper()
        
        return cleaned

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


class SimplePrincipleMatcher:
    """Assigns stable derived URIs for principles when unmatched.

    URI scheme: urn:proethica:principle:<slug>
    """

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or 'principle')
            uri = f"urn:proethica:principle:{slug}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={'uri': uri, 'label': c.label, 'score': 0.45},
                similarity=0.45,
                normalized_label=c.label,
                notes='derived: simple matcher'
            ))
        return results


class PrinciplesLinker(Linker):
    """Generates Role→adheresToPrinciple→Principle links with policy gating."""

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        triples: List[SemanticTriple] = []
        roles = [m for m in matches if (m.candidate.primary_type or '').lower() in {'role', 'professionalrole', 'participantrole'}]
        principles = [m for m in matches if (m.candidate.primary_type or '').lower() == 'principle']

        for role in roles:
            subj_uri = (role.ontology_match or {}).get('uri')
            subj_type = (role.candidate.primary_type or '')
            if not subj_uri:
                continue
            for pr in principles:
                obj_uri = (pr.ontology_match or {}).get('uri')
                if not obj_uri:
                    continue
                obj_type = (pr.candidate.primary_type or '')
                if not self.gate.can_link_adheres_to_principle(subj_type, obj_type):
                    continue
                triples.append(
                    SemanticTriple(
                        subject_uri=subj_uri,
                        predicate_uri='adheresToPrinciple',
                        object_uri=obj_uri,
                        context={'guideline_id': guideline_id} if guideline_id else {},
                        is_approved=False,
                    )
                )
        return triples
