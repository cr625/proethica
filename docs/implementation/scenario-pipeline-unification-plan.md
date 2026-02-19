# Scenario Pipeline Unification Plan

## A. Unification Plan — Numbered Task List

### Phase 1: Make Pipeline B consume synthesis output (no behavior change)

**Task 1. Create a SynthesisDataAdapter that loads all seven views from stored synthesis output**

File: `app/services/scenario_generation/synthesis_adapter.py` (new)

The core problem is that Pipeline B's `ScenarioDataCollector` re-queries `TemporaryRDFStorage` row by row instead of reading the already-synthesized output stored in `ExtractionPrompt`. This adapter becomes the single load point.

```
class SynthesisDataAdapter:
    def load(self, case_id: int) -> SynthesisViewData:
        # 1. Load Phase 3 decision points from ExtractionPrompt
        #    concept_type='phase3_decision_synthesis' → List[CanonicalDecisionPoint dict]
        #
        # 2. Load Phase 4 narrative from ExtractionPrompt
        #    concept_type='phase4_narrative' → Phase4NarrativeResult dict containing:
        #      - narrative_elements (characters, setting, events, conflicts, decisions, resolution)
        #      - timeline (EntityGroundedTimeline with fluents, causal links)
        #      - scenario_seeds (branches, options, canonical path)
        #      - insights (patterns, principles, takeaways)
        #
        # 3. Load CaseSynthesisModel metadata from ExtractionPrompt
        #    concept_type='unified_synthesis' → entity_foundation, provisions, questions,
        #      conclusions, causal_normative_links, question_emergence, resolution_patterns
        #
        # Returns a SynthesisViewData object that maps to the seven views:
        #   Entities   → entity_foundation (roles, states, resources, principles, obligations,
        #                 constraints, capabilities, actions, events)
        #   Flow       → causal_normative_links + timeline.causal_links
        #   Provisions → provisions list
        #   Questions  → questions + conclusions + question_emergence
        #   Analysis   → resolution_patterns + transformation
        #   Decisions  → canonical_decision_points + scenario_seeds.branches
        #   Narrative  → narrative_elements + timeline
```

This is 2 DB queries (ExtractionPrompt by concept_type) instead of the current N queries against TemporaryRDFStorage.

**Task 2. Replace ScenarioDataCollector.collect_all_data() internals**

File: `app/services/scenario_generation/data_collection.py`

Current state: `_load_temporary_entities()` (line ~80) queries all of TemporaryRDFStorage by case_id, `_load_synthesis_data()` returns empty SynthesisData (has a TODO comment), `_load_temporal_dynamics()` returns empty TemporalDynamicsData (has a TODO comment).

Changes:
- Import and call `SynthesisDataAdapter.load(case_id)` at the top of `collect_all_data()`
- Populate `ScenarioSourceData.merged_entities` from `entity_foundation` lists (converting EntitySummary dicts to RDFEntity objects)
- Populate `ScenarioSourceData.temporal_dynamics` from Phase 4 timeline (events, causal_links, fluents) — this replaces the empty placeholder
- Populate `ScenarioSourceData.synthesis_data` from provisions, questions, conclusions — this replaces the empty placeholder
- Keep `_load_temporary_entities()` as fallback only when synthesis output doesn't exist yet
- `check_eligibility()` stays unchanged (it correctly checks Pass 1-3 + Step 4 completion)

**Task 3. Wire TimelineConstructor (Stage 2) to Phase 4 timeline**

File: `app/services/scenario_generation/timeline_constructor.py`

Current state: `build_timeline()` queries TemporaryRDFStorage for Actions/Events and builds its own `ScenarioTimeline` with phases.

Changes:
- Add a `build_timeline_from_synthesis(phase4_timeline: dict) -> ScenarioTimeline` method
- Map Phase 4's `EntityGroundedTimeline` events (which already have sequence, phase, phase_label, event_type, fluent effects, causal_links) into `ScenarioTimeline.entries`
- Map Phase 4's timeline phases into `ScenarioTimeline.phases`
- The existing `build_timeline()` becomes the fallback path
- The orchestrator calls the synthesis-aware method first

**Task 4. Wire ParticipantMapper (Stage 3) to Phase 4 NarrativeCharacters**

File: `app/services/scenario_generation/participant_mapper.py`

Current state: `create_participants()` takes raw Role entities and calls the LLM to generate character profiles from scratch. Phase 4's `NarrativeElementExtractor` already did this same work, producing `NarrativeCharacter` objects with motivations, ethical_stance, relationships, obligation_uris, principle_uris.

Changes:
- Add a `create_participants_from_narrative(case_id, narrative_elements: dict) -> List[Dict]` method
- Map NarrativeCharacter fields to the participant output format:
  - `label` → `name`, `role_type` → used as-is
  - `professional_position` → `title`
  - `motivations` → `motivations` (already a list)
  - `ethical_stance` → derives `ethical_tensions`
  - `relationships` → `key_relationships` (reformat from [relation, target_uri] tuples)
  - `obligation_uris`, `principle_uris` → preserved as grounding
- Still call LLM for `character_arc` and `background` enrichment (NarrativeCharacter doesn't have these), but the prompt is much smaller — it's enhancement, not generation
- Still write to `ScenarioParticipant` DB model via `save_participants_to_db()`
- The existing `create_participants()` becomes the fallback for cases without Phase 4 data

### Phase 2: Connect Stages 4-6 to existing synthesis output

**Task 5. Replace Stage 4 placeholder with CanonicalDecisionPoint consumption**

File: `app/services/scenario_generation/orchestrator.py` (lines 218-237)

Current state: Counts actions and questions, returns `{'status': 'placeholder'}`.

The work is already done. Phase 3's `DecisionPointSynthesizer` produces `CanonicalDecisionPoint` objects stored in ExtractionPrompt (concept_type='phase3_decision_synthesis') and TemporaryRDFStorage (extraction_type='canonical_decision_point'). Phase 4's scenario seed generator transforms these into `ScenarioBranch` objects with options, obligation grounding, and board choices.

Changes:
- Load canonical decision points from `SynthesisDataAdapter` (Task 1)
- Load scenario branches from Phase 4 scenario_seeds
- Build a `DecisionGraph` structure: ordered list of decision nodes, each with:
  - The `CanonicalDecisionPoint` (question, role, obligations in tension, Toulmin structure)
  - The `ScenarioBranch` (options with action_uris, is_board_choice, leads_to)
  - Causal links forward to subsequent decisions (from Phase 4 timeline causal_links)
- Report actual decision count and structure in progress callback
- No new LLM calls needed — this is pure assembly

**Task 6. Replace Stage 5 placeholder with causal chain integration from Analysis view**

File: `app/services/scenario_generation/orchestrator.py` (lines 239-249)

Current state: Reads `data.temporal_dynamics.causal_chains` count (which is 0 because temporal_dynamics is empty).

Changes:
- Read `causal_normative_links` from synthesis data (the Flow + Analysis views)
- Read `causal_links` from Phase 4 timeline
- For each decision point in the DecisionGraph (from Task 5), attach:
  - Which obligations each option fulfills/violates (from CausalNormativeLink)
  - What downstream fluent changes each option causes (from timeline causal_links)
  - What subsequent decision points become reachable/unreachable (from ScenarioBranch.leads_to)
- This produces a `DecisionConsequenceMap`: decision_uri → option_index → {fulfills, violates, initiates, terminates, enables_decisions, blocks_decisions}
- Report consequence map summary in progress callback

**Task 7. Replace Stage 6 placeholder with normative framework from Provisions view**

File: `app/services/scenario_generation/orchestrator.py` (lines 251-268)

Current state: Counts principles, obligations, provisions.

Changes:
- Read provisions from synthesis data (the Provisions view)
- Read resolution_patterns from synthesis data (the Analysis view)
- Read question_emergence from synthesis data (the Questions view)
- For each decision point, attach:
  - Relevant code provisions (matched by obligation_uri → provision applies_to)
  - The board's weighing process for that decision (from resolution_patterns)
  - Competing warrants from question_emergence (the Toulmin data-warrant tensions)
- This produces a `NormativeContext` per decision point: provisions, weighing, warrants
- Report normative coverage in progress callback

### Phase 3: Unify Stages 7-9 with Pipeline A's interactive exploration

**Task 8. Replace Stage 7 (Scenario Assembly) with unified scenario model construction**

File: `app/services/scenario_generation/orchestrator.py` (lines 270-279)

Changes:
- Assemble the complete scenario model from Stages 1-6 output:
  - `ScenarioSourceData` entities → the world (via existing `scenario_population_service.py` mapping)
  - `ScenarioTimeline` → event sequence
  - Participants → characters with relationships
  - `DecisionGraph` with `DecisionConsequenceMap` and `NormativeContext` → the interactive navigation structure
- Store the assembled scenario. Two options:
  - Option A: Write to existing Scenario/World/Character/Action/Event DB models (the `scenario_population_service` path)
  - Option B: Store as a single JSON document in ExtractionPrompt (concept_type='scenario_assembled') for the interactive service to consume
  - **Recommend Option B** for now — it's what `interactive_scenario_service` already reads, and avoids the complexity of populating the full Scenario model graph. Option A becomes a future enhancement for when scenarios need to be independently browsable.

**Task 9. Replace Stage 8 (Interactive Model Generation) with handoff to interactive_scenario_service**

File: `app/services/scenario_generation/orchestrator.py` (lines 281-290)

Current state: Placeholder.

The interactive model already exists — it's the `ScenarioExplorationSession` workflow driven by `interactive_scenario_service`. What Stage 8 needs to do is prepare the data in the format that service expects.

Changes:
- `interactive_scenario_service.start_session()` currently calls `_load_decision_points()` which re-queries ExtractionPrompt and TemporaryRDFStorage. Instead:
- Add `interactive_scenario_service.start_session_from_assembled(case_id, assembled_scenario)` method that accepts the Stage 7 output directly
- The assembled scenario already contains decision points with options, consequence maps, normative context, and initial fluents — no re-querying needed
- Stage 8 calls this method (or just validates the assembled scenario is ready for interactive use)
- The existing `start_session()` remains as the standalone entry point (for cases where the user goes directly to interactive exploration without running the pipeline)

**Task 10. Replace Stage 9 (Validation) with actual quality checks**

File: `app/services/scenario_generation/orchestrator.py` (lines 292-301)

Current state: Returns hardcoded `{'quality_score': 85}`.

Changes:
- Check structural completeness:
  - Every decision point has >= 2 options
  - Every option has obligation grounding (fulfills or violates at least one obligation)
  - The board's actual choice is identified for each decision point
  - Initial fluents are defined
  - At least one character is the protagonist
- Check normative coverage:
  - Every extracted obligation appears in at least one decision point's normative context
  - Every code provision is linked to at least one decision point
- Check narrative coherence:
  - Timeline events are sequenced (no gaps in sequence numbers)
  - Causal links don't reference nonexistent entities
- Return validation report with pass/fail per check and overall quality score
- No LLM calls — this is pure structural validation

### Phase 4: Fix the SSE route

**Task 11. Make the SSE endpoint call the unified orchestrator**

File: `app/routes/scenario_pipeline/generate_scenario.py`

Current state: The SSE route pre-fetches data and builds timeline before the generator function, then emits placeholder events for stages 3-9. It doesn't call the orchestrator's `generate_complete_scenario()`.

Changes:
- Remove the inline data collection and timeline building (lines 64-73)
- Create the orchestrator with a progress callback that yields SSE events
- Call `orchestrator.generate_complete_scenario(case_id)` inside the generator
- The orchestrator's `_report_progress()` calls feed directly into SSE `yield` statements
- Each stage's progress data includes the actual results (entity counts, timeline structure, participant profiles, decision graph, etc.)
- The final SSE event includes the assembled scenario ID or reference for the UI to load

**Task 12. Update Step 5 UI to consume unified pipeline output**

File: `app/routes/scenario_pipeline/step5.py`

Changes:
- Keep `_load_phase4_data()` and related helpers as-is — they load from ExtractionPrompt which the unified pipeline also writes to
- Add loading of the assembled scenario from Stage 7 output (if it exists)
- The three-tab UI (Narrative, Timeline, Decision Wizard) already works with Phase 4 data — the unified pipeline just ensures that data is richer (with consequence maps and normative context attached to each decision)
- Add a "Generate Scenario" button that triggers the SSE endpoint (already exists) and shows progress through all 9 stages with real results

### Phase 5: Deprecate abandoned code

**Task 13. Deprecate the three abandoned alternatives**

Files to deprecate:
- `app/services/scenario_pipeline/wizard_scenario_generator.py`
- `app/services/scenario_pipeline/enhanced_llm_scenario_service.py`
- `app/services/scenario_pipeline/scenario_generation_phase_a.py`

Assessment of salvageable code:

| File | Unique Value | Action |
|------|-------------|--------|
| `wizard_scenario_generator.py` | Decision option generation with NSPE code mapping (lines 256-332). Creates contextual options based on specific question types (AI disclosure, reporting accuracy, etc.) | **Extract** the NSPE option mapping logic into a utility function that the scenario seed generator can use. Deprecate the rest. |
| `enhanced_llm_scenario_service.py` | Temporal marker confidence scoring (lines 121-213). Pattern-based extraction of sequence markers (after, before, then, subsequently) with typed classification. | **Not needed** — Phase 4's timeline constructor already handles temporal ordering through Event Calculus, which is more rigorous. Deprecate entirely. |
| `scenario_generation_phase_a.py` | Dual pipeline fallback pattern (lines 134-174) and reasoning trace capture. | **Not needed** — the unified pipeline has its own fallback (synthesis data → raw TemporaryRDFStorage) and LLMTrace recording. Deprecate entirely. |

For each file: add a deprecation notice at the top referencing the unified pipeline, but don't delete yet. Remove from imports in `__init__.py` files. The existing `interactive_scenario_service.py` and `scenario_population_service.py` stay — they're part of the unified pipeline.

**Task 14. Clean up orchestrator's stale metadata**

File: `app/services/scenario_generation/orchestrator.py`

- Line 314: Change `'status': 'complete_placeholder'` to `'status': 'complete'`
- Lines 316-325: Remove the `next_steps` list that says "Implement Stage 2-9" (they'll all be implemented)
- Line 52-54: Remove the commented-out future stage imports; replace with actual imports

---

## B. Dependency Diagram

```
                         SYNTHESIS VIEWS (stored in ExtractionPrompt)
                         ============================================

  ┌──────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐  ┌───────────┐  ┌───────────┐
  │ Entities │  │   Flow   │  │Provisions │  │ Questions │  │ Analysis │  │ Decisions │  │ Narrative │
  │          │  │          │  │           │  │           │  │          │  │           │  │           │
  │R,P,O,S, │  │Causal-   │  │Code       │  │Questions, │  │Question  │  │Canonical  │  │Characters,│
  │Rs,A,E,  │  │Normative │  │provisions,│  │Conclusions│  │Emergence,│  │Decision   │  │Setting,   │
  │Ca,Cs    │  │Links     │  │excerpts   │  │Q&C links  │  │Resolution│  │Points,    │  │Events,    │
  │          │  │          │  │           │  │           │  │Patterns  │  │Options    │  │Timeline,  │
  │          │  │          │  │           │  │           │  │          │  │           │  │Seeds      │
  └────┬─────┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬─────┘  └─────┬─────┘  └─────┬─────┘
       │              │              │              │              │              │              │
       │              │              │              │              │              │              │
       ▼              │              │              │              │              │              │
  ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                          TASK 1: SynthesisDataAdapter.load()                                       │
  │                    (Single load point — 2 DB queries on ExtractionPrompt)                           │
  └──────────────────────────────────────┬──────────────────────────────────────────────────────────────┘
                                         │
       ┌────────────────┬────────────────┼────────────────┬────────────────┐
       ▼                ▼                ▼                ▼                ▼
  ┌──────────┐   ┌──────────┐   ┌──────────────┐  ┌──────────┐   ┌──────────┐
  │ STAGE 1  │   │ STAGE 2  │   │   STAGE 3    │  │ STAGE 4  │   │ STAGE 5  │
  │ Data     │   │ Timeline │   │ Participant  │  │ Decision │   │ Causal   │
  │Collection│   │ Construc.│   │   Mapping    │  │  Graph   │   │  Chain   │
  │          │   │          │   │              │  │          │   │ Integr.  │
  │ Entities │   │ Narrative│   │  Narrative   │  │ Decisions│   │Flow +    │
  │ view  ───┼──►│ view  ───┼──►│  view     ───┼─►│ view  ───┼──►│Analysis  │
  │          │   │          │   │              │  │          │   │views     │
  │Builds    │   │Builds    │   │Maps Narrative│  │Loads     │   │Attaches  │
  │entity set│   │Scenario  │   │Characters to │  │Canonical │   │obligation│
  │from found│   │Timeline  │   │Scenario      │  │Points +  │   │fulfill/  │
  │-ation    │   │from Phase│   │Participants  │  │Scenario  │   │violate + │
  │          │   │4 timeline│   │with LLM arc  │  │Branches  │   │fluent    │
  │          │   │          │   │enrichment    │  │into graph│   │changes   │
  └────┬─────┘   └────┬─────┘   └──────┬───────┘  └────┬─────┘   └────┬─────┘
       │              │                │               │              │
       │              │                │               │              │
       │              │                │               ▼              │
       │              │                │         ┌──────────┐         │
       │              │                │         │ STAGE 6  │◄────────┘
       │              │                │         │Normative │
       │              │                │         │Framework │
       │              │                │         │          │
       │              │                │         │Provisions│
       │              │                │         │+ Analysis│
       │              │                │         │views     │
       │              │                │         │          │
       │              │                │         │Attaches  │
       │              │                │         │provisions│
       │              │                │         │+ weighing│
       │              │                │         │per point │
       │              │                │         └────┬─────┘
       │              │                │              │
       ▼              ▼                ▼              ▼
  ┌──────────────────────────────────────────────────────────┐
  │                    STAGE 7: Assembly                      │
  │                                                          │
  │  Combines: entity set + timeline + participants +        │
  │  decision graph + consequence map + normative context    │
  │  → Assembled Scenario (stored in ExtractionPrompt)       │
  └────────────────────────────┬─────────────────────────────┘
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │              STAGE 8: Interactive Model                   │
  │                                                          │
  │  Validates assembled scenario is ready for exploration.  │
  │  Prepares initial fluents, option labels, board choices. │
  │  Hands off to interactive_scenario_service.              │
  └────────────────────────────┬─────────────────────────────┘
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │              STAGE 9: Validation                          │
  │                                                          │
  │  Structural checks: options ≥2, obligation grounding,    │
  │  board choice identified, fluents defined, timeline      │
  │  sequenced. Returns quality report.                      │
  └────────────────────────────┬─────────────────────────────┘
                               │
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │              STEP 5 UI (Three Tabs)                       │
  │                                                          │
  │  ┌────────────┐  ┌────────────┐  ┌─────────────────┐    │
  │  │ Narrative  │  │  Timeline  │  │ Decision Wizard │    │
  │  │ Overview   │  │  Viewer    │  │ (Interactive)   │    │
  │  │            │  │            │  │                 │    │
  │  │Characters, │  │Phase-based │  │Choose → LLM    │    │
  │  │setting,    │  │chronology  │  │consequences →  │    │
  │  │conflicts   │  │w/ fluents  │  │next decision → │    │
  │  │            │  │            │  │final analysis  │    │
  │  └────────────┘  └────────────┘  └─────────────────┘    │
  └──────────────────────────────────────────────────────────┘
```

---

## C. Migration Risk Assessment

### Principle: Wrap Pipeline A, incrementally connect Pipeline B

Pipeline A works end-to-end. The unification must never break it. The strategy:

1. **Tasks 1-4 (Phase 1) are additive.** They add new methods (`build_timeline_from_synthesis`, `create_participants_from_narrative`, `SynthesisDataAdapter`) alongside existing ones. The existing methods become fallbacks. No behavioral change until the orchestrator switches to calling the new methods. **Risk: Zero** — no existing code changes.

2. **Tasks 5-7 (Phase 2) replace placeholders.** The current stages 4-6 do nothing (they count entities and report). Replacing them with real logic cannot break existing behavior because there is no existing behavior. **Risk: Low** — the only risk is if the orchestrator is called from somewhere that depends on the placeholder output format, but inspection shows it's only called from the SSE route which already treats stages 4-9 as placeholders.

3. **Tasks 8-10 (Phase 3) are the critical path.** Stage 7 (Assembly) creates a new artifact. Stage 8 adds a new entry point to `interactive_scenario_service`. Stage 9 adds validation. The key risk: Stage 8 must not break the existing `start_session()` path.
   - **Mitigation:** `start_session_from_assembled()` is a new method. `start_session()` is unchanged. The UI continues to call `start_session()` directly. The orchestrator calls `start_session_from_assembled()` when it runs. Both paths produce the same `ScenarioExplorationSession`. **Risk: Low.**

4. **Task 11 (SSE route) is the switchover.** This is where the SSE endpoint starts calling the real orchestrator instead of inlining stages 1-2 and faking 3-9.
   - **Mitigation:** Add a feature flag (`USE_UNIFIED_PIPELINE=true/false`). When false, the current inline behavior runs. When true, the orchestrator runs. Default to false, flip to true after testing. **Risk: Medium, mitigated by feature flag.**

5. **Tasks 12-14 (UI and cleanup) are safe.** Step 5 UI already loads from ExtractionPrompt. Deprecation notices don't change behavior.

### Recommended execution order:

```
Task 1  → Task 2  → Task 3  → Task 4     (Phase 1: additive, zero risk)
  ↓
Task 5  → Task 6  → Task 7               (Phase 2: replace placeholders, low risk)
  ↓
Task 8  → Task 9  → Task 10              (Phase 3: new assembly + validation, low risk)
  ↓
Task 11 (with feature flag)               (Phase 4: switchover, medium risk)
  ↓
Task 12 → Task 13 → Task 14              (Phase 5: UI update + cleanup, safe)
```

### Rollback plan

If anything breaks after Task 11:
- Set `USE_UNIFIED_PIPELINE=false` → SSE route reverts to inline behavior
- Pipeline A (direct Phase 4 → Step 5 UI → interactive exploration) continues working exactly as before
- All new code exists in new methods/files and doesn't touch Pipeline A's path

---

## D. Missing Pieces for Paper Claims

### 1. Perspective Switching (viewing scenario from different character viewpoints)

**What data exists:**
- `NarrativeCharacter` has `motivations`, `ethical_stance`, `obligation_uris`, `principle_uris`, `relationships` — everything needed to define a character's viewpoint
- `ScenarioParticipant` has `goals` (JSONB), `obligations` (JSONB), `constraints` (JSONB), `relationships` (JSONB) — richer DB-persisted version
- Each `CanonicalDecisionPoint` has `role_uri` and `role_label` identifying the decision-maker
- Each `ScenarioBranch` has `decision_maker_uri` and `decision_maker_label`

**What service logic is needed:**
- A `PerspectiveFilter` that, given a character URI:
  - Filters decision points to only those where the character is the decision-maker or is affected (referenced in obligation_uris or relationship targets)
  - Rewrites the decision context to foreground that character's obligations and ethical stance
  - Adjusts the consequence narrative to emphasize effects on that character
- In `interactive_scenario_service`, the `_build_decision_context()` method (which assembles context for the LLM consequence generation) would need a `perspective_uri` parameter that shifts the framing

**What UI work is needed:**
- A character selector (dropdown or card-based) on the Step 5 Decision Wizard tab
- When a character is selected, the decision presentation reframes: "As [Character], you face..." instead of generic framing
- Previous choices panel shows how this character experienced the choices

**Complexity: Medium.** Data exists. Service logic is a filtering/rewriting layer over existing structures. UI is a selector + template variation. The LLM consequence generation prompt already takes context — adding perspective is a prompt change, not an architectural one.

### 2. Cross-Case Precedent Links at Decision Points

**What data exists:**
- `CaseInsights.patterns` has `similar_cases_hint` (string) and `generalizability` rating — but this is a text hint, not a structured link
- `CaseInsights.precedent_features` (Dict) — exists in the dataclass but not consistently populated
- The `World` model groups cases by domain/ontology, so cases in the same world share entity types
- Obligation and Principle URIs are ontology-grounded, meaning the same obligation URI appears in multiple cases if they reference the same professional code

**What service logic is needed:**
- A `PrecedentMatcher` service that, given a decision point:
  - Queries other cases in the same World that have CanonicalDecisionPoints with overlapping obligation_uris
  - Ranks by overlap count and obligation similarity
  - Returns: case_id, case_title, decision_point_focus_id, board_resolution summary, and which obligations overlap
- This requires an index: obligation_uri → list of (case_id, decision_point_id) pairs. Can be built at synthesis time and stored as a materialized lookup table, or computed on-demand from TemporaryRDFStorage (slower but simpler)
- A `get_precedents(decision_point_uri, case_id, limit=3)` method that returns the top N matching decision points from other cases

**What UI work is needed:**
- A "Similar Decisions in Other Cases" expandable panel on each decision point in the Decision Wizard
- Each precedent shows: case title, the similar decision question, what the board decided, and which obligations overlap (highlighted)
- Click-through to the other case's Step 5 page

**Complexity: Large.** The matching logic is straightforward but requires either a new index table or cross-case queries. The real challenge is that not all cases will have completed synthesis, so precedent coverage will be sparse initially. The UI is a panel with links — moderate effort. The service layer needs to handle the case where no precedents exist gracefully.

### 3. Relationship Network Visualization

**What data exists:**
- `ScenarioParticipant.relationships` (JSONB) stores structured relationship data: `[{participant_id, relationship, description}]`
- `NarrativeCharacter.relationships` stores `[[relation, target_uri], ...]` tuples
- `NarrativeConflict` has `entity1_uri`, `entity2_uri`, `affected_role_uris` — defines tension edges
- `CausalNormativeLink` has `agent_role` → action → obligation chains — defines normative edges
- `EntityFoundation.role_obligation_bindings` has `[{role_label, obligation_label, obligation_uri}]` — defines duty edges

**What service logic is needed:**
- A `RelationshipGraphBuilder` that constructs a graph (nodes + edges) from:
  - Nodes: Characters (from NarrativeCharacter or ScenarioParticipant)
  - Edges type 1: Interpersonal relationships (from relationships JSONB)
  - Edges type 2: Shared obligations (from role_obligation_bindings)
  - Edges type 3: Conflicts/tensions (from NarrativeConflict)
  - Edges type 4: Causal responsibility (from CausalNormativeLink where agent_role is one character and affected party is another)
- Returns a JSON graph structure: `{nodes: [{id, label, role_type, ...}], edges: [{source, target, type, label, ...}]}`

**What UI work is needed:**
- A network graph visualization component (D3.js force-directed graph or similar)
- Nodes colored by role_type (protagonist=blue, authority=red, stakeholder=green)
- Edges styled by type (interpersonal=solid, obligation=dashed, conflict=red, causal=arrow)
- Interactive: click a node to see that character's profile, click an edge to see the relationship detail
- Could be a fourth tab on Step 5, or an overlay on the Narrative tab

**Complexity: Medium.** The data is scattered across multiple structures but all exists. The graph builder is assembly logic, not AI. The main effort is the D3.js visualization component, which is a frontend task. The backend API endpoint to serve the graph JSON is straightforward.

### Summary Table

| Paper Claim | Data Exists? | Service Needed | UI Needed | Complexity |
|-------------|-------------|---------------|-----------|------------|
| Perspective switching | Yes (NarrativeCharacter, ScenarioParticipant, decision_maker_uri) | PerspectiveFilter: filtering + LLM prompt rewrite | Character selector + reframed decision cards | **Medium** |
| Cross-case precedent links | Partial (obligation URIs shared across cases, but no index) | PrecedentMatcher: cross-case obligation overlap query + ranking | Expandable precedent panel per decision point | **Large** |
| Relationship network | Yes (relationships JSONB, NarrativeConflict, CausalNormativeLink, role_obligation_bindings) | RelationshipGraphBuilder: graph assembly from multiple sources | D3.js force-directed graph component | **Medium** |
