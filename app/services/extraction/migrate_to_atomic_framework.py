"""
Migration script to update all 9 extractors to use the unified atomic extraction framework.

This script provides both automated migration utilities and manual migration templates.
"""

from typing import Dict, List, Tuple
import re
import os


# Mapping of extractors to their concept types
EXTRACTOR_CONCEPT_MAPPING = {
    'actions.py': 'action',
    'capabilities.py': 'capability', 
    'constraints.py': 'constraint',
    'events.py': 'event',
    'obligations.py': 'obligation',
    'principles.py': 'principle',
    'resources.py': 'resource',
    'roles.py': 'role',
    'states.py': 'state'
}


def create_migration_template(extractor_name: str, concept_type: str) -> str:
    """Create a migration template for an extractor."""
    
    class_name = f"{concept_type.title()}sExtractor"
    
    return f'''"""
Enhanced {concept_type} extractor with unified atomic concept splitting.

Migrated to use the unified atomic extraction framework for consistent
concept granularity across all extraction types.
"""

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
except Exception:
    get_llm_client = None


class {class_name}(Extractor, AtomicExtractionMixin):
    """
    {concept_type.title()} extractor with unified atomic concept splitting.
    
    This extractor now uses the standardized atomic extraction framework,
    eliminating custom splitting logic in favor of the unified approach.
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        self.provider = (provider or 'auto').lower()

    @property
    def concept_type(self) -> str:
        """The concept type this extractor handles."""
        return '{concept_type}'

    def extract(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Extract {concept_type} concepts with unified atomic splitting.
        
        This method now follows the unified pattern:
        1. Initial extraction (LLM or heuristic)
        2. Unified atomic splitting (via mixin)
        """
        if not text:
            return []

        # Step 1: Initial extraction
        initial_candidates = self._extract_initial_concepts(text, world_id=world_id, guideline_id=guideline_id)
        
        # Step 2: Apply unified atomic splitting
        return self._apply_atomic_splitting(initial_candidates)

    def _extract_initial_concepts(self, text: str, *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Perform initial {concept_type} extraction without atomic splitting.
        
        This method contains the core extraction logic, with atomic splitting
        handled separately by the unified framework.
        """
        # Provider-backed attempt first if configured
        if self.provider != 'heuristic' and get_llm_client is not None:
            try:
                items = self._extract_with_llm(text)
                if items:
                    return [
                        ConceptCandidate(
                            label=i.get('label') or i.get('{concept_type}') or i.get('name') or '',
                            description=i.get('description') or i.get('explanation') or None,
                            primary_type='{concept_type}',
                            category='{concept_type}',
                            confidence=float(i.get('confidence', 0.65)) if isinstance(i.get('confidence', 0.65), (int, float, str)) else 0.65,
                            debug={{'source': 'provider', 'provider': self.provider}}
                        )
                        for i in items
                        if (i.get('label') or i.get('{concept_type}') or i.get('name'))
                    ]
            except Exception:
                pass
        
        # Fallback to heuristic extraction
        return self._extract_heuristic(text, guideline_id)

    def _extract_heuristic(self, text: str, guideline_id: Optional[int] = None) -> List[ConceptCandidate]:
        """
        Heuristic extraction for {concept_type} concepts.
        
        This method should extract concepts without doing atomic splitting - 
        that will be handled by the unified framework.
        """
        # TODO: Implement heuristic extraction specific to {concept_type}s
        # This is where you'd move the core extraction logic from the original extractor
        
        sentences = re.split(r"(?<=[\.!?])\\s+", text.strip())
        # Example keywords - customize for {concept_type}s
        kw = re.compile(r"\\b(keyword1|keyword2|keyword3)\\b", re.IGNORECASE)
        seen: Set[str] = set()
        candidates: List[ConceptCandidate] = []
        
        for s in sentences:
            if not s:
                continue
            if kw.search(s):
                label = s.strip()
                key = label.lower()
                if key in seen:
                    continue
                seen.add(key)
                display = label if len(label) <= 120 else label[:117] + '…'
                candidates.append(ConceptCandidate(
                    label=display,
                    description=label if display != label else None,
                    primary_type='{concept_type}',
                    category='{concept_type}',
                    confidence=0.45,
                    debug={{'source': 'heuristic_keywords', 'guideline_id': guideline_id}}
                ))
        return candidates

    # ---- Provider-backed helpers ----
    def _extract_with_llm(self, text: str) -> List[Dict[str, Any]]:
        """Call configured LLM provider to extract {concept_type}s as JSON with optional MCP context."""
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
            prompt = self._create_{concept_type}_prompt_with_mcp(text)
        else:
            prompt = self._create_{concept_type}_prompt(text)

        # Try different LLM providers (Gemini, Anthropic, OpenAI)
        # Implementation follows standard pattern...
        # TODO: Copy from original extractor and modify for unified approach
        
        return []

    def _create_{concept_type}_prompt(self, text: str) -> str:
        """Create standard {concept_type} extraction prompt."""
        return (
            f"You are an ontology-aware extractor. From the guideline excerpt, extract distinct {concept_type} concepts.\\n"
            f"Return STRICT JSON with an array under key '{concept_type}s'. Each item: {{label, description, confidence}}.\\n"
            f"Extract atomic {concept_type} concepts that can be used in formal reasoning.\\n\\n"
            f"Guideline excerpt:\\n" + text
        )

    def _create_{concept_type}_prompt_with_mcp(self, text: str) -> str:
        """Create enhanced {concept_type} prompt with external MCP ontology context."""
        try:
            from app.services.external_mcp_client import get_external_mcp_client
            import logging
            
            logger = logging.getLogger(__name__)
            logger.info(f"Fetching {concept_type} context from external MCP server...")
            
            external_client = get_external_mcp_client()
            existing_concepts = external_client.get_all_{concept_type}_entities()
            
            # Build ontology context
            ontology_context = f"EXISTING {concept_type.upper()} CONCEPTS IN ONTOLOGY:\\n"
            if existing_concepts:
                ontology_context += f"Found {{len(existing_concepts)}} existing {concept_type} concepts:\\n"
                for concept in existing_concepts[:10]:
                    label = concept.get('label', 'Unknown')
                    description = concept.get('description', 'No description')[:80]
                    ontology_context += f"- {{label}}: {{description}}\\n"
                if len(existing_concepts) > 10:
                    ontology_context += f"... and {{len(existing_concepts) - 10}} more {concept_type}s\\n"
            else:
                ontology_context += f"No existing {concept_type}s found in ontology (fresh setup)\\n"
            
            # Create enhanced prompt
            enhanced_prompt = f"""
{{ontology_context}}

You are an ontology-aware extractor analyzing an ethics guideline to extract {concept_type.upper()}S.

IMPORTANT: Consider the existing {concept_type}s above when extracting. For each {concept_type} you extract:
1. Check if it matches an existing {concept_type} (mark as existing)
2. If it's genuinely new, mark as new
3. Provide clear reasoning for why it's new vs existing

Focus on extracting atomic {concept_type} concepts suitable for formal ethical reasoning.

GUIDELINE TEXT:
{{text}}

OUTPUT FORMAT:
Return STRICT JSON with an array under key '{concept_type}s':
[
  {{{{
    "label": "Example {concept_type.title()}",
    "description": "Clear description of the {concept_type}",
    "confidence": 0.9,
    "is_existing": false,
    "ontology_match_reasoning": "Reasoning about ontology match"
  }}}}
]

Focus on accuracy over quantity. Extract only clear, unambiguous {concept_type}s.
"""
            return enhanced_prompt
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get external MCP context for {concept_type}s: {{e}}")
            logger.info(f"Falling back to standard {concept_type} prompt")
            return self._create_{concept_type}_prompt(text)

    @staticmethod
    def _parse_json_items(raw: Optional[str], root_key: str) -> List[Dict[str, Any]]:
        """Parse JSON response from LLM."""
        if not raw:
            return []
        import json, re as _re
        s = raw.strip()
        if s.startswith('```'):
            s = _re.sub(r"^```[a-zA-Z0-9]*\\n|\\n```$", "", s)
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
                m = _re.search(r"\\[(?:.|\\n)*\\]", s)
                if m:
                    return json.loads(m.group(0))
            except Exception:
                return []
        return []


class Simple{concept_type.title()}Matcher:
    """Assigns stable derived URIs for {concept_type}s when unmatched."""

    def match(self, candidates: List[ConceptCandidate], *, world_id: Optional[int] = None) -> List[MatchedConcept]:
        results: List[MatchedConcept] = []
        for c in candidates:
            slug = slugify(c.label or '{concept_type}')
            uri = f"urn:proethica:{concept_type}:{{slug}}"
            results.append(MatchedConcept(
                candidate=c,
                ontology_match={{'uri': uri, 'label': c.label, 'score': 0.45}},
                similarity=0.45,
                normalized_label=c.label,
                notes='derived: simple matcher'
            ))
        return results


class {concept_type.title()}sLinker(Linker):
    """Generates semantic triples for {concept_type} relationships with policy gating."""

    def __init__(self, gatekeeper: Optional[RelationshipPolicyGatekeeper] = None) -> None:
        self.gate = gatekeeper or RelationshipPolicyGatekeeper()

    def link(self, matches: List[MatchedConcept], *, world_id: Optional[int] = None, guideline_id: Optional[int] = None) -> List[SemanticTriple]:
        # TODO: Implement relationship linking logic specific to {concept_type}s
        triples: List[SemanticTriple] = []
        
        # Example relationship pattern - customize for {concept_type}s
        for match in matches:
            subj_uri = (match.ontology_match or {{}}).get('uri')
            if not subj_uri:
                continue
                
            # Add relationships based on {concept_type} semantics
            # This is where you'd implement domain-specific relationship logic
            
        return triples
'''


def print_migration_summary():
    """Print a summary of the migration approach and next steps."""
    
    summary = """
🚀 UNIFIED ATOMIC EXTRACTION FRAMEWORK MIGRATION

## Current State Analysis
✅ GeneralizedConceptSplitter - Advanced LLM-based splitting
✅ AtomicExtractionMixin - Unified framework for all extractors  
✅ Concept examples for all 9 types in concept_splitter.py

## Migration Strategy

### Phase 1: Immediate (Recommended)
Enable unified splitting for all extractors via environment variable:
```bash
export ENABLE_CONCEPT_SPLITTING=true
```

This immediately gives all extractors atomic splitting without code changes.

### Phase 2: Gradual Refactoring
For each extractor, migrate to unified pattern:

1. **Current Custom Splitting** → **Unified Framework**
   - Remove custom `_split_compound_[TYPE]` methods
   - Add AtomicExtractionMixin inheritance  
   - Use `_apply_atomic_splitting()` method

2. **Benefits of Migration**:
   - ✅ Consistent atomic concept granularity
   - ✅ LLM-powered intelligent splitting (not just patterns)
   - ✅ Concept-type aware few-shot learning
   - ✅ Rich metadata and debugging info
   - ✅ Confidence scoring and validation
   - ✅ Environment variable controls

### Phase 3: Advanced Features (Optional)
```bash
export ENABLE_CONCEPT_ORCHESTRATION=true  # Full LangChain pipeline
```

## Migration Options

### Option A: Environment Variable Only (Zero Code Change)
```bash
# Enables atomic splitting for all extractors immediately
export ENABLE_CONCEPT_SPLITTING=true
```

### Option B: Gradual Code Refactoring
```python
# For each extractor:
class MyExtractor(Extractor, AtomicExtractionMixin):
    @property
    def concept_type(self) -> str:
        return 'my_concept_type'
    
    def extract(self, text: str, **kwargs) -> List[ConceptCandidate]:
        initial = self._extract_initial_concepts(text, **kwargs)
        return self._apply_atomic_splitting(initial)
```

### Option C: Full Framework Adoption
```python
# Complete migration to unified framework
class MyExtractor(AtomicExtractor):
    @property
    def concept_type(self) -> str:
        return 'my_concept_type'
        
    def _extract_initial_concepts(self, text: str, **kwargs) -> List[ConceptCandidate]:
        # Core extraction logic only
        return self._extract_with_llm_or_heuristic(text, **kwargs)
```

## Immediate Next Steps

1. **Test Current Capability**: 
   ```bash
   export ENABLE_CONCEPT_SPLITTING=true
   # Test extraction with existing extractors
   ```

2. **Choose Migration Path**:
   - **Quick Win**: Use Option A (env var only)  
   - **Long Term**: Gradually apply Option B or C

3. **Validate Results**:
   - Verify atomic concepts vs compound statements
   - Check concept quality and granularity
   - Monitor extraction performance

## Expected Results

**Before (compound concepts)**:
- "Engineers shall maintain confidentiality and disclose conflicts"
- "Public safety, health, and welfare"
- "Technical competence and professional judgment"

**After (atomic concepts)**:
- "Confidentiality", "Conflict Disclosure"  
- "Public Safety", "Public Health", "Public Welfare"
- "Technical Competence", "Professional Judgment"

This provides the foundation for formal ethical reasoning with proper concept granularity.
"""
    
    print(summary)


if __name__ == "__main__":
    print_migration_summary()