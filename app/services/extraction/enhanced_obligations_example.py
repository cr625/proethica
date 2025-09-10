"""
Enhanced Obligations Extractor - Example Integration

This shows how to integrate the generalized concept splitting and LangChain 
orchestration into your existing obligations extractor.
"""

from __future__ import annotations

from typing import List, Optional, Set, Any, Dict
import os
import re
import asyncio
from slugify import slugify

from .base import ConceptCandidate, MatchedConcept, SemanticTriple, Extractor, Linker
from .policy_gatekeeper import RelationshipPolicyGatekeeper
from .concept_splitter import split_concepts_for_extractor
from .langchain_orchestrator import orchestrated_extraction
from models import ModelConfig

# LLM utils are optional at runtime; import guarded
try:
    from app.utils.llm_utils import get_llm_client
except Exception:  # pragma: no cover - environment without Flask/LLM
    get_llm_client = None  # type: ignore


class EnhancedObligationsExtractor(Extractor):
    """
    Enhanced obligations extractor with generalized concept splitting.
    
    This demonstrates the integration pattern for upgrading existing extractors
    to use the new LLM-based atomic concept splitting and orchestration.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Enhanced extraction with intelligent concept splitting and validation.
        
        New Architecture:
        1. Initial extraction (existing logic)
        2. Generalized concept splitting 
        3. Optional LangChain orchestration for validation/filtering
        """
        if not text:
            return []

        # Step 1: Initial extraction (existing logic)
        initial_candidates = self._extract_initial_concepts(text, world_id, guideline_id)
        
        if not initial_candidates:
            return []

        # Step 2: Apply generalized concept splitting
        split_candidates = split_concepts_for_extractor(
            initial_candidates, 
            concept_type='obligation',
            provider=self.provider
        )

        # Step 3: Optional orchestrated processing
        use_orchestration = os.environ.get('ENABLE_CONCEPT_ORCHESTRATION', 'false').lower() == 'true'
        
        if use_orchestration:
            # Run async orchestration
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            final_candidates = loop.run_until_complete(
                orchestrated_extraction(
                    text=text,
                    concept_type='obligation',
                    initial_candidates=split_candidates,
                    pipeline_config={
                        'enable_splitting': False,  # Already done
                        'enable_validation': True,
                        'enable_filtering': True,
                        'max_concepts': 15
                    }
                )
            )
            return final_candidates
        else:
            return split_candidates

    def _extract_initial_concepts(self, 
                                text: str, 
                                world_id: Optional[int] = None, 
                                guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Initial concept extraction - this is your existing extraction logic.
        The key insight is that we can keep all existing extraction logic 
        and just add the splitting/orchestration as post-processing steps.
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
                                label=label,
                                description=i.get('description') or i.get('explanation') or None,
                                primary_type='obligation',
                                category='obligation',
                                confidence=float(i.get('confidence', 0.7)) if isinstance(i.get('confidence', 0.7), (int, float, str)) else 0.7,
                                debug={
                                    'source': 'provider', 
                                    'provider': self.provider,
                                    'extraction_method': 'initial_llm'
                                }
                            ))
                    return candidates
            except Exception:
                # Fall through to heuristic if provider path fails
                pass
                
        # Heuristic extraction fallback
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """Heuristic extraction - your existing pattern-based logic."""
        # Split into sentences conservatively
        sentences = re.split(r"(?<=[\.!?])\s+", text.strip())
        modals = re.compile(r"\b(must|shall|should|required to|responsible for|obliged to|obligation to)\b", re.IGNORECASE)
        seen: Set[str] = set()
        results: List[ConceptCandidate] = []
        
        for s in sentences:
            if not s:
                continue
            if modals.search(s):
                # NOTE: No compound splitting here anymore - that's handled by the splitter
                atomic_label = s.strip()
                
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
                        'source': 'heuristic_modals',
                        'guideline_id': guideline_id,
                        'extraction_method': 'initial_heuristic'
                    }
                ))
        return results

    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """
        LLM extraction with enhanced prompt for atomic concepts.
        
        Note: The prompt now emphasizes atomic extraction, knowing that
        any compound concepts will be handled by the post-processing splitter.
        """
        client = get_llm_client() if get_llm_client else None
        if client is None:
            return []

        # Check for external MCP integration
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
            
        use_external_mcp = os.environ.get('ENABLE_EXTERNAL_MCP_ACCESS', 'false').lower() == 'true'
        
        if use_external_mcp:
            prompt = self._create_enhanced_obligations_prompt_with_mcp(text)
        else:
            prompt = self._create_enhanced_obligations_prompt(text)

        # Try Anthropic messages API
        try:
            if hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                model = ModelConfig.get_default_model()
                resp = client.messages.create(
                    model=model,
                    max_tokens=800,
                    temperature=0,
                    system=(
                        "Extract professional obligations from text. "
                        "Focus on clear, actionable duties. Output ONLY JSON with key 'obligations'."
                    ),
                    messages=[{"role": "user", "content": prompt}],
                )
                content = getattr(resp, 'content', None)
                if content and isinstance(content, list) and len(content) > 0:
                    text_out = getattr(content[0], 'text', None) or str(content[0])
                else:
                    text_out = getattr(resp, 'text', None) or str(resp)
                return self._parse_json_items(text_out, root_key='obligations')
        except Exception:
            pass

        return []

    def _create_enhanced_obligations_prompt(self, text: str) -> str:
        """Enhanced prompt that works well with post-processing splitting."""
        return f"""
Extract professional OBLIGATIONS from this ethics guideline.

FOCUS ON:
1. Statements with modal verbs (must, shall, should, required to)
2. Professional duties and requirements
3. Prohibitive obligations (must not, shall not)
4. Conditional obligations (when X, then must Y)

EXTRACT CLEARLY STATED OBLIGATIONS - the post-processing will handle any compound concepts.

EXAMPLES OF GOOD OBLIGATIONS:
- "Engineers shall hold paramount the safety of the public"
- "Avoid conflicts of interest" 
- "Disclose potential conflicts to clients"
- "Maintain competence in their field"
- "Act as faithful agents for clients"

GUIDELINE TEXT:
{text}

Return STRICT JSON with array under key 'obligations':
[{{"label": "obligation text", "description": "explanation", "confidence": 0.8}}]

Focus on accuracy and completeness. The system will handle splitting compound statements automatically.
"""

    def _create_enhanced_obligations_prompt_with_mcp(self, text: str) -> str:
        """Enhanced MCP-aware prompt."""
        try:
            # Import external MCP client
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info("Fetching obligations context from external MCP server...")
            
            external_client = get_external_mcp_client()
            existing_obligations = external_client.get_all_obligation_entities()
            
            # Build ontology context
            ontology_context = "EXISTING OBLIGATIONS IN ONTOLOGY:\n"
            if existing_obligations:
                ontology_context += f"Found {len(existing_obligations)} existing obligation concepts:\n"
                for obligation in existing_obligations:  # Show all obligations
                    label = obligation.get('label', 'Unknown')
                    description = obligation.get('description', 'No description')
                    ontology_context += f"- {label}: {description}\n"
            else:
                ontology_context += "No existing obligations found in ontology (fresh setup)\n"
            
            logger.info(f"Retrieved {len(existing_obligations)} existing obligations from external MCP for context")
            
            enhanced_prompt = f"""
{ontology_context}

Extract professional OBLIGATIONS from this ethics guideline.

ENHANCED EXTRACTION STRATEGY:
1. Consider existing obligations above for context and consistency
2. Extract new obligations that complement the existing set
3. Focus on clear, actionable professional duties
4. The system will automatically handle compound statement splitting

OBLIGATION TYPES TO EXTRACT:
1. **Direct Obligations**: Specific duties (shall, must, required to)
2. **Prohibitive Obligations**: Things forbidden (must not, shall not)
3. **Conditional Obligations**: Context-dependent duties (when X, then Y)
4. **Disclosure Obligations**: Information sharing requirements

GUIDELINE TEXT:
{text}

Return STRICT JSON with array under key 'obligations':
[{{
  "label": "clear obligation statement",
  "description": "detailed explanation of the obligation", 
  "confidence": 0.9,
  "is_new": true,
  "relationship_to_existing": "how this relates to existing obligations"
}}]

Focus on professional ethics obligations. The post-processing will ensure atomic granularity.
"""
            
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for obligations: {e}")
            logger.info("Falling back to standard enhanced obligations prompt")
            return self._create_enhanced_obligations_prompt(text)

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Parse JSON response - same as existing logic."""
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


# Integration instructions for existing extractors
"""
UPGRADE PATH FOR EXISTING EXTRACTORS:

1. **Minimal Integration** (just splitting):
   ```python
   from .concept_splitter import split_concepts_for_extractor
   
   def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
       # Existing extraction logic
       candidates = self._existing_extract_logic(text, **kwargs)
       
       # Add generalized splitting
       return split_concepts_for_extractor(candidates, 'obligation')
   ```

2. **Full Integration** (splitting + orchestration):
   ```python
   from .langchain_orchestrator import orchestrated_extraction
   import asyncio
   
   def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
       # Existing extraction logic
       initial_candidates = self._existing_extract_logic(text, **kwargs)
       
       # Add orchestrated processing
       if os.environ.get('ENABLE_CONCEPT_ORCHESTRATION', 'false') == 'true':
           loop = asyncio.get_event_loop()
           return loop.run_until_complete(
               orchestrated_extraction(text, 'obligation', initial_candidates)
           )
       else:
           # Fallback to just splitting
           return split_concepts_for_extractor(initial_candidates, 'obligation')
   ```

3. **Environment Variable Control**:
   ```bash
   # Enable generalized splitting for all extractors
   ENABLE_CONCEPT_SPLITTING=true
   
   # Enable full LangChain orchestration (more advanced)
   ENABLE_CONCEPT_ORCHESTRATION=true
   
   # Control specific stages
   ENABLE_CONCEPT_VALIDATION=true
   ENABLE_CONCEPT_FILTERING=true
   MAX_CONCEPTS_PER_TYPE=15
   ```

This approach allows you to:
- Keep all existing extraction logic intact
- Add intelligent splitting as a post-processing step
- Gradually enable more advanced orchestration features
- Control the pipeline through environment variables
- Maintain backward compatibility
"""