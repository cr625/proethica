# Case & Scenario Analysis Implementation Plan

**Created:** November 16, 2025
**Approach:** Hybrid - Build LLM manager while implementing business value features
**Goal:** Enable meaningful case analysis and scenario generation

---

## Current State vs CLAUDE.md

**CLAUDE.md is a PLAN, not reality.** Here's what actually exists:

### ✅ Implemented
1. **Step 5 Stage 1-2**: Data collection, timeline construction
2. **Basic extraction**: Passes 1-3 (9-concept extraction from cases)
3. **Infrastructure**: Database, routes, SSE streaming

### ❌ NOT Implemented (described in CLAUDE.md as "complete")
1. **Step 4 Parts D-F**: Institutional rule analysis, action-rule mapping, transformation classification
2. **Step 5 Stages 3-9**: All participant/decision/assembly stages are placeholders

---

## Implementation Strategy: Hybrid Approach

### Week 1: Minimal LLM Manager + First Feature

**Day 1-2: Build Minimal LLM Manager**
- Create `app/services/llm/manager.py` (core only, ~300 lines)
- Support Anthropic (Sonnet 4) with timeout handling
- Unified response format
- **No migration of existing services yet**

**Day 3-5: Implement Step 5 Stage 3 (Participant Mapping)**
- Create `app/services/scenario_generation/participant_mapper.py`
- Use new LLM manager
- LLM-enhanced participant extraction from roles
- Database: `scenario_participants` table (create migration 013)
- Integrate with orchestrator

**Deliverable:** Working participant mapping with real LLM analysis

### Week 2: Decision Points + Causal Analysis

**Days 6-8: Implement Step 5 Stage 4 (Decision Points)**
- Option A: Reference Step 4 Part D IF we implement it
- Option B: Direct LLM analysis from actions/questions
- **Choose Option B** (faster, doesn't block on Step 4)

**Days 9-10: Implement Step 5 Stage 5 (Causal Chains)**
- Use existing temporal dynamics (causal_chains)
- Link to decisions
- Simple visualization

**Deliverable:** Interactive decision points with consequences

### Week 3: Scenario Assembly (MVP)

**Days 11-13: Implement Step 5 Stage 7 (Assembly)**
- Skip Stage 6 (normative) for now
- Combine: timeline + participants + decisions + causal
- Generate coherent scenario narrative
- JSON structure for frontend

**Days 14-15: Implement Step 5 Stage 8 (Interactive Model)**
- Create interactive decision tree
- Discussion questions
- Consequence visualization
- Link to NSPE Code provisions

**Deliverable:** End-to-end scenario generation MVP

### Week 4: Polish + Case Analysis

**Days 16-18: Testing & Refinement**
- Test on Cases 8, 10, other complete cases
- Refine prompts
- Improve quality

**Days 19-20: Basic Step 4 Analysis (if time)**
- Implement simplified Part D (principle tensions, obligation conflicts)
- Store in database
- Make available to Stage 4

**Deliverable:** Production-ready scenario generation

---

## Technical Architecture

### LLM Manager Design (Minimal)

```python
# app/services/llm/manager.py

from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from httpx import Timeout
import anthropic

@dataclass
class LLMResponse:
    """Unified response format."""
    text: str
    model: str
    usage: Dict[str, int]  # input_tokens, output_tokens
    metadata: Dict[str, Any]

class LLMManager:
    """Minimal LLM manager for ProEthica."""

    def __init__(self, model: Optional[str] = None):
        """Initialize with optional model override."""
        from models import ModelConfig
        self.model = model or ModelConfig.get_claude_model("default")
        self.client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var
        self.timeout = Timeout(connect=10.0, read=180.0, write=180.0, pool=180.0)

    def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 1.0,
        metadata: Optional[Dict] = None
    ) -> LLMResponse:
        """
        Unified completion interface.

        Args:
            messages: List of {"role": "user"|"assistant", "content": str}
            system: Optional system prompt
            max_tokens: Maximum response tokens
            temperature: Sampling temperature
            metadata: Optional metadata for tracking

        Returns:
            LLMResponse with text, usage, metadata
        """
        response = self.client.messages.create(
            model=self.model,
            system=system or "",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=self.timeout
        )

        return LLMResponse(
            text=response.content[0].text,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.input_tokens + response.usage.output_tokens
            },
            metadata=metadata or {}
        )

# Singleton for easy access
_llm_manager = None

def get_llm_manager(model: Optional[str] = None) -> LLMManager:
    """Get or create singleton LLM manager."""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager(model)
    return _llm_manager
```

### Participant Mapper Design

```python
# app/services/scenario_generation/participant_mapper.py

from typing import List, Dict, Any
from app.services.llm.manager import get_llm_manager
import logging

logger = logging.getLogger(__name__)

class ParticipantMapper:
    """
    Maps role entities to scenario participants with LLM enhancement.

    Implements Step 5 Stage 3 as described in CLAUDE.md.
    """

    def __init__(self):
        self.llm = get_llm_manager()

    def create_participants(
        self,
        roles: List[Any],  # Role entities from extraction
        timeline: Any,  # Timeline with actions/events
        case_text: str  # For context
    ) -> List[Dict[str, Any]]:
        """
        Create enhanced participant profiles from role entities.

        Uses LLM to:
        - Identify participant motivations
        - Extract background from case text
        - Determine ethical tensions
        - Build character arcs

        Returns:
            List of participant dictionaries with rich metadata
        """
        logger.info(f"Creating participants from {len(roles)} roles")

        # Build prompt with roles and case context
        prompt = self._build_participant_prompt(roles, timeline, case_text)

        # Call LLM (uses Sonnet 4 by default)
        response = self.llm.complete(
            messages=[{"role": "user", "content": prompt}],
            system="You are analyzing an engineering ethics case to create detailed participant profiles.",
            max_tokens=4000,
            metadata={"stage": "participant_mapping"}
        )

        # Parse JSON response
        participants = self._parse_participant_response(response.text, roles)

        logger.info(f"Created {len(participants)} participant profiles")
        return participants

    def _build_participant_prompt(
        self,
        roles: List[Any],
        timeline: Any,
        case_text: str
    ) -> str:
        """Build LLM prompt for participant extraction."""

        # Use short IDs instead of URIs (lesson from CLAUDE.md)
        role_descriptions = []
        for idx, role in enumerate(roles[:12]):  # Limit to avoid bloat
            role_descriptions.append(
                f"  r{idx}: {role.label} - {getattr(role, 'definition', 'No description')}"
            )

        prompt = f"""
Analyze this engineering ethics case and create detailed participant profiles.

ROLES IDENTIFIED:
{chr(10).join(role_descriptions)}

CASE CONTEXT (excerpt):
{case_text[:2000]}

For each role, extract:
1. **Name/Identifier**: How they're referred to in the case
2. **Background**: Professional context, experience level
3. **Motivations**: What drives their decisions
4. **Ethical Tensions**: Competing obligations they face
5. **Character Arc**: How they change/develop through the case

OUTPUT FORMAT:
Return a JSON array:
[
  {{
    "role_id": "r0",
    "name": "Engineer A",
    "title": "Senior Structural Engineer",
    "background": "20 years experience in commercial construction",
    "motivations": ["Professional integrity", "Concern for public safety"],
    "ethical_tensions": ["Loyalty to employer vs public duty"],
    "character_arc": "Initially hesitant, grows more assertive about safety concerns",
    "key_relationships": ["r1: Client (tension)", "r2: Supervisor (reports to)"]
  }}
]

Focus on participants who make decisions or face ethical dilemmas.
"""
        return prompt

    def _parse_participant_response(
        self,
        response_text: str,
        roles: List[Any]
    ) -> List[Dict[str, Any]]:
        """Parse LLM response into participant data."""
        import json
        import re

        # Handle markdown-wrapped JSON (common issue per CLAUDE.md)
        code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
        if code_block_match:
            response_text = code_block_match.group(1).strip()

        try:
            participants = json.loads(response_text)

            # Map short IDs back to role objects
            role_map = {f"r{idx}": role for idx, role in enumerate(roles)}

            for participant in participants:
                role_id = participant.get("role_id")
                if role_id in role_map:
                    participant["role_entity"] = role_map[role_id]
                    participant["role_uri"] = getattr(role_map[role_id], 'uri', None)

            return participants

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse participant JSON: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            return []
```

---

## Database Schema

### Migration 013: Scenario Participants

```sql
-- db_migration/013_create_scenario_participants.sql

CREATE TABLE IF NOT EXISTS scenario_participants (
    id SERIAL PRIMARY KEY,
    case_id INTEGER NOT NULL REFERENCES documents(id),
    role_entity_uri TEXT,  -- Link to role entity
    name VARCHAR(200) NOT NULL,
    title VARCHAR(300),
    background TEXT,
    motivations TEXT[],  -- Array of motivation strings
    ethical_tensions TEXT[],
    character_arc TEXT,
    key_relationships JSONB,  -- Flexible relationship data
    metadata JSONB,  -- LLM usage, confidence, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_scenario_participants_case ON scenario_participants(case_id);
CREATE INDEX idx_scenario_participants_role ON scenario_participants(role_entity_uri);
```

---

## Success Metrics

### Week 1
- ✅ LLM manager handles Sonnet 4 calls with timeout
- ✅ Participant mapper generates 8-12 profiles per case
- ✅ Profiles include motivations, tensions, relationships

### Week 2
- ✅ Decision points identified from actions/questions
- ✅ Causal chains link decisions to consequences
- ✅ 3-5 decisions per case with alternatives

### Week 3
- ✅ Complete scenario JSON generated
- ✅ Interactive decision tree navigable
- ✅ Discussion questions generated
- ✅ Scenario renders in UI

### Week 4
- ✅ Tested on 3+ real cases
- ✅ Quality score >80% (human review)
- ✅ Token usage tracked and optimized

---

## Why This Approach Works

1. **Immediate Value**: Working participant mapping in Week 1
2. **Incremental Risk**: Each week adds one feature
3. **LLM Manager Proven**: Used in production from Day 3
4. **No Big Bang**: Old services keep working
5. **User Feedback**: Can test/adjust after each week

---

## Next Decision Point

**Should we start with:**
- **Option A**: Build LLM manager first (Days 1-2), then Stage 3 participant mapping
- **Option B**: Build participant mapping with inline Anthropic calls, refactor to LLM manager later
- **Option C**: Focus on Step 4 Parts D-F first (more foundational but slower to value)

**Recommendation**: **Option A** - LLM manager is small (2 days) and makes all subsequent work cleaner.

---

## Questions for User

1. Which cases should we test on? (Case 8, 10, others?)
2. What's most valuable: participant profiles, decision analysis, or full scenarios?
3. Any specific analysis features needed (e.g., pattern detection, precedent matching)?
4. Timeline pressure - do we need faster progress?
