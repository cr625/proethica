# Fix: Integrate Capabilities (Ca) into Analytical Synthesis Stages

## Problem Statement

The nine-component formal model D = (R, P, O, S, Rs, A, E, Ca, Cs) defines Capabilities as "dispositions or competencies required to perform role-appropriate actions" — they bound what agents CAN do. However, Ca is loaded in Phase 1 (`EntityFoundation.capabilities`) but never referenced in:

1. **Four extraction sub-methods** in `case_synthesizer.py`:
   - `_analyze_causal_normative_links()` (line 1674) — formats actions, obligations, principles, constraints, roles. **Not capabilities.**
   - `_analyze_question_emergence()` / `_analyze_question_batch()` (line 1812/1844) — formats events, actions, roles, obligations. **Not capabilities.**
   - `_analyze_resolution_patterns()` — similar omission.
2. **Two LLM enhancement prompts** in `narrative_element_extractor.py`:
   - `_enhance_characters_with_llm()` (line 678) — prompt references ROLES + OBLIGATIONS only.
   - `_enhance_tensions_with_llm()` (line 765) — prompt references OBLIGATIONS + CONSTRAINTS + ROLES only.
3. **Three analytical services** (E1/E2/E3):
   - `ObligationCoverageAnalyzer` (E1) — loads Obligations, Constraints, Roles. Not Capabilities.
   - `ActionOptionMapper` (E2) — loads Actions, Events, Causal Chains. Not Capabilities.
   - `DecisionPointComposer` (E3) — consumes E1+E2 output. No capability grounding.
4. **NarrativeCharacter dataclass** — has `obligation_uris` and `principle_uris` but no `capability_uris`.

This is an accidental gap — no comments or TODOs explain the omission, and the formal model explicitly positions Ca as bounding Actions/Events.

---

## Architecture Context

### How capabilities are currently stored and loaded

**Extraction:** Capabilities are extracted in Pass 2 (Normative Requirements) by `CapabilitiesExtractor` and stored in `TemporaryRDFStorage` with `extraction_type='capabilities'`.

**Loading:** In `case_synthesizer.py` `_build_entity_foundation()` (line 818), capabilities are loaded into `EntityFoundation.capabilities` (line 94) as `List[EntitySummary]` objects via the standard query pattern:

```python
TemporaryRDFStorage.query.filter_by(case_id=case_id, extraction_type='capabilities').all()
```

**EntitySummary** (line 73-79): `uri`, `label`, `definition`, `entity_type`

**EntityFoundation** (line 82-102): Has `capabilities: List[EntitySummary]` at line 94.

### How the E1/E2/E3 services load entities

All three use the same pattern (e.g., `action_option_mapper.py:228-233`):
```python
def _load_entities(self, case_id: int, entity_type: str) -> List[TemporaryRDFStorage]:
    return TemporaryRDFStorage.query.filter_by(
        case_id=case_id,
        entity_type=entity_type
    ).all()
```

To add capabilities, just call `self._load_entities(case_id, 'Capabilities')`.

---

## Changes Required

### Change 1: CausalNormativeLink — add `enabled_by_capabilities` field

**File:** `app/services/case_synthesizer.py`
**Location:** `CausalNormativeLink` dataclass (line 226-239)

Add a new field:
```python
enabled_by_capabilities: List[str] = field(default_factory=list)  # Capability URIs
```

**Rationale:** The causal-normative analysis asks "which obligations does this action fulfill/violate?" It should also ask "which capabilities enable this action?"

### Change 2: Causal-normative LLM prompt — add CAPABILITIES section

**File:** `app/services/case_synthesizer.py`
**Location:** `_analyze_causal_normative_links()` (line 1674)

After the roles_text formatting (line 1717-1720), add:
```python
# Format capabilities
capabilities_text = "\n".join([
    f"- {ca.label}: {ca.definition or 'No definition'} (URI: {ca.uri})"
    for ca in foundation.capabilities
]) if foundation.capabilities else "No capabilities extracted"
```

In the prompt (line 1722), add a new section after ROLES:
```
## CAPABILITIES (competencies that enable actions)
{capabilities_text}
```

In the prompt instructions (line 1739), add item 6 (renumber existing 6 to 7):
```
6. Which capabilities ENABLE it? (competencies required to perform this action)
```

In the JSON output template (line 1748), add:
```
"enabled_by_capabilities": ["<capability_uri>", ...],
```

In the parsing section (line 1792), add:
```python
enabled_by_capabilities=[self._normalize_uri(u, uri_lookup) for u in link.get('enabled_by_capabilities', [])],
```

### Change 3: Question emergence LLM prompt — add CAPABILITIES section

**File:** `app/services/case_synthesizer.py`
**Location:** `_analyze_question_batch()` (line 1844)

After obligations_text formatting (line 1880-1883), add:
```python
# Format capabilities
capabilities_text = "\n".join([
    f"- {ca.label}: {ca.definition or 'No definition'} (URI: {ca.uri})"
    for ca in foundation.capabilities
]) if foundation.capabilities else "No capabilities extracted"
```

In the prompt (line 1892), add a new section after ROLES:
```
## CAPABILITIES (what the agent is competent to do)
{capabilities_text}
```

In the JSON output template, add:
```
"capability_gaps": ["capability_uri that would be needed but may be lacking"],
```

Update `QuestionEmergenceAnalysis` dataclass (line 242) to include:
```python
capability_gaps: List[str] = field(default_factory=list)
```

### Change 4: ObligationCoverageAnalyzer (E1) — capability-obligation feasibility

**File:** `app/services/entity_analysis/obligation_coverage_analyzer.py`

**4a. Add to ObligationAnalysis dataclass** (line 24-40):
```python
required_capabilities: List[str] = field(default_factory=list)  # Capability URIs needed to fulfill
capability_feasible: bool = True  # Whether required capabilities exist
```

**4b. Load capabilities in `analyze_coverage()`** (after line 168):
```python
capabilities_raw = self._load_entities(case_id, 'Capabilities')
```

**4c. In `_analyze_obligation()`** (line 279): Accept capabilities parameter, extract any capability requirements mentioned in the obligation definition. Simple keyword matching is sufficient (pattern: "competence", "qualified", "expertise", "ability to", "capable of").

**4d. In the LLM fallback prompt** (line 596-623): Add a CAPABILITIES section so the LLM can factor capability constraints into its decision-relevance assessment. Obligations that require capabilities the agent may lack are more decision-relevant.

### Change 5: ActionOptionMapper (E2) — capability feasibility filter

**File:** `app/services/entity_analysis/action_option_mapper.py`

**5a. Add to ActionOption dataclass** (line 69-91):
```python
required_capabilities: List[str] = field(default_factory=list)  # Capability labels
capability_feasible: bool = True  # Whether agent has needed capabilities
```

**5b. Load capabilities in `map_action_options()`** (after line 182):
```python
capabilities_raw = self._load_entities(case_id, 'Capabilities')
capability_labels = {e.entity_label.lower() for e in capabilities_raw}
```

**5c. In `_create_action_set()`** (line 261): After creating the ActionOption, check whether the action's label/definition references competencies that exist in the capability set. Set `capability_feasible=False` if the action requires expertise not present in extracted capabilities.

**5d. Update `to_dict()`** (line 81) to include the new fields.

### Change 6: DecisionPointComposer (E3) — capability grounding

**File:** `app/services/entity_analysis/decision_point_composer.py`

**6a. Add to DecisionPointGrounding dataclass** (line 35-46):
```python
capability_uris: List[str] = field(default_factory=list)
capability_labels: List[str] = field(default_factory=list)
```

**6b. Add to DecisionPointOption dataclass** (line 49-62):
```python
required_capability_labels: List[str] = field(default_factory=list)
capability_feasible: bool = True
```

**6c. In `_compose_from_obligation()`** (line 439): When building the DecisionPointOption from an ActionOption, carry forward the `required_capabilities` and `capability_feasible` fields.

**6d. In `_compose_from_constraint()`** (line 515): Same as 6c.

### Change 7: NarrativeCharacter — add capability_uris

**File:** `app/services/narrative/narrative_element_extractor.py`

**7a. Add to NarrativeCharacter dataclass** (line 33-56):
```python
capability_uris: List[str] = field(default_factory=list)  # After principle_uris (line 46)
```

**7b. In `_extract_characters()`** (line 316): Build a capability map (like obligation_map on line 327):
```python
capability_map = self._build_capability_map(foundation)
```

**7c. Add `_build_capability_map()` method** (after `_build_principle_map` at line 438):
```python
def _build_capability_map(self, foundation) -> Dict[str, List[str]]:
    """Build mapping of role URIs to their capability URIs."""
    cap_map: Dict[str, List[str]] = {}
    # Associate capabilities with roles based on role-capability bindings
    # or by matching capability possessed_by fields to role labels
    for cap in foundation.capabilities:
        # Default: associate with first (protagonist) role if no explicit binding
        if foundation.roles:
            role_uri = foundation.roles[0].uri
            cap_map.setdefault(role_uri, []).append(cap.uri)
    return cap_map
```

**7d. In the NarrativeCharacter constructor call** (line 360-370), add:
```python
capability_uris=capability_map.get(role.uri, [])[:5],
```

**7e. Update `to_dict()`** (line 51-55) to include `capability_uris`.

### Change 8: LLM character enhancement prompt — add CAPABILITIES

**File:** `app/services/narrative/narrative_element_extractor.py`
**Location:** `_enhance_characters_with_llm()` (line 678-763)

In the prompt (line 699-713), after the OBLIGATIONS section, add:
```
CAPABILITIES IN THE CASE:
{capabilities_list}
```

Where `capabilities_list` is built from `foundation.capabilities` (same pattern as obligations at line 694-697).

### Change 9: LLM tension enhancement prompt — add CAPABILITIES

**File:** `app/services/narrative/narrative_element_extractor.py`
**Location:** `_enhance_tensions_with_llm()` (line 765-946)

In the prompt (line 811-849), after CONSTRAINTS section, add:
```
CAPABILITIES (competencies the agent has):
{capabilities_list}
```

This allows the LLM to identify tensions where an obligation demands a capability the agent may lack — a common source of ethical dilemmas in professional ethics.

---

## Verification Plan

After making the changes:

1. **Run existing tests** to ensure nothing breaks:
   ```
   python -m pytest tests/unit/services/entity_analysis/ -v
   python -m pytest tests/unit/services/narrative/ -v
   python -m pytest tests/ -k "synthesizer" -v
   ```

2. **Run a full case synthesis** on a case known to have capabilities extracted (check TemporaryRDFStorage for cases with `extraction_type='capabilities'`):
   ```python
   from app.services.case_synthesizer import CaseSynthesizer
   synth = CaseSynthesizer(domain='engineering')
   result = synth.synthesize_complete(case_id=<ID>)
   # Check result for capability references in:
   # - causal_normative_links[*].enabled_by_capabilities
   # - decision_points[*].options[*].required_capability_labels
   # - narrative.characters[*].capability_uris
   ```

3. **Verify JSON serialization** — all new fields should appear in `to_dict()` output.

4. **Check the views** — the four presentation views (Entities, Flow, Provisions, Questions) already display capabilities. Verify the three analytical views (Analysis, Decisions, Narrative) now include Ca references.

---

## File Summary

| File | Changes |
|------|---------|
| `app/services/case_synthesizer.py` | Changes 1, 2, 3 — CausalNormativeLink field, two LLM prompts, QuestionEmergenceAnalysis field |
| `app/services/entity_analysis/obligation_coverage_analyzer.py` | Change 4 — ObligationAnalysis fields, load capabilities, LLM prompt |
| `app/services/entity_analysis/action_option_mapper.py` | Change 5 — ActionOption fields, load capabilities, feasibility check |
| `app/services/entity_analysis/decision_point_composer.py` | Change 6 — DecisionPointGrounding/Option fields, carry forward from E2 |
| `app/services/narrative/narrative_element_extractor.py` | Changes 7, 8, 9 — NarrativeCharacter field, capability map, two LLM prompts |

## Priority Order

1. **Change 2** (causal-normative prompt) — highest conceptual impact, easiest to implement
2. **Change 7** (NarrativeCharacter) — simple dataclass addition
3. **Change 5** (ActionOptionMapper E2) — core feasibility concept
4. **Change 4** (ObligationCoverageAnalyzer E1) — capability-obligation link
5. **Change 6** (DecisionPointComposer E3) — carries forward E2 data
6. **Changes 1, 3** (dataclass fields + question emergence) — supporting changes
7. **Changes 8, 9** (LLM enhancement prompts) — narrative enrichment
