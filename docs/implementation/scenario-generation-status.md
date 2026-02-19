# Phase 3 / Step 4→5 Scenario Generation: Status Report

## 1. Status Table

| Feature | Status | Primary File(s) | Notes |
|---------|--------|-----------------|-------|
| **Data Collection (Stage 1)** | **Implemented** | `services/scenario_generation/data_collection.py` | Loads entities from both TemporaryRDFStorage and committed ontology. Merges dual sources. Checks Pass 1-3 + Step 4 eligibility. |
| **Timeline Construction (Stage 2)** | **Implemented** | `services/scenario_generation/timeline_constructor.py`, `services/narrative/timeline_constructor.py` | Two implementations — the `scenario_generation/` one builds `ScenarioTimeline` with phases, Allen relations, temporal markers. The `narrative/` one builds `EntityGroundedTimeline` with Event Calculus fluents. Both work. |
| **Participant Mapping (Stage 3)** | **Implemented** | `services/scenario_generation/participant_mapper.py`, `models/scenario_participant.py` | LLM-enhanced character profiles from Role entities. 22-column `ScenarioParticipant` model with expertise, qualifications, goals, obligations, constraints, relationships. Stored in DB. |
| **Decision Point Identification (Stage 4)** | **Placeholder** | `services/scenario_generation/orchestrator.py:218-237` | Counts actions and questions but does no actual identification. Comment: `"Stage 4: Decision Identification (TODO)"`. The real decision work lives in `decision_point_synthesizer.py` (Phase 3 of synthesis), which produces `CanonicalDecisionPoint` objects — but the orchestrator doesn't consume them. |
| **Causal Chain Integration (Stage 5)** | **Placeholder** | `orchestrator.py:239-249` | Reads `data.temporal_dynamics.causal_chains` count, reports it, does nothing with it. |
| **Normative Framework Integration (Stage 6)** | **Placeholder** | `orchestrator.py:251-268` | Counts principles, obligations, provisions. No integration logic. |
| **Scenario Assembly (Stage 7)** | **Placeholder** | `orchestrator.py:270-279` | Returns `{'status': 'placeholder'}`. |
| **Interactive Model Generation (Stage 8)** | **Placeholder** | `orchestrator.py:281-290` | Returns `{'status': 'placeholder'}`. |
| **Validation (Stage 9)** | **Placeholder** | `orchestrator.py:292-301` | Returns hardcoded `{'quality_score': 85, 'status': 'placeholder'}`. |
| **Narrative Element Extraction (4.1)** | **Implemented** | `services/narrative/narrative_element_extractor.py` | Produces `NarrativeCharacter`, `NarrativeSetting`, `NarrativeEvent`, `NarrativeConflict`. LLM-enhanced characters and tensions. Connected to foundation. |
| **Scenario Seed Generation (4.3)** | **Implemented** | `services/narrative/scenario_seed_generator.py` | Produces `ScenarioBranch` with `ScenarioOption` objects, `AlternativePath`, protagonist identification. Each branch grounded to decision_point_uri, obligation_uris. |
| **Insight Derivation (4.4)** | **Implemented** | `services/narrative/insight_deriver.py` | Produces `CaseInsights` — patterns, principles applied, novel aspects. |
| **Interactive Exploration Session** | **Implemented** | `routes/scenario_pipeline/step5_interactive.py`, `services/interactive_scenario_service.py`, `models/scenario_exploration.py` | Full workflow: start session → present decision → user chooses → LLM generates consequences → next decision → final analysis. Event Calculus fluent tracking (active/terminated). Provenance-tracked. |
| **SSE Progress Streaming** | **Implemented (scaffolding)** | `routes/scenario_pipeline/generate_scenario.py` | SSE endpoint streams stage progress. Stages 1-2 execute real work; stages 3-9 emit placeholder events. |
| **Scenario Population** | **Implemented** | `services/scenario_population_service.py` | Maps all 8 ontology categories to DB models: Roles→Characters, Actions→Actions, Events→Events, Capabilities→Character attributes, etc. |
| **Case-to-Scenario Conversion** | **Implemented** | `services/case_to_scenario_service.py` | Domain-specific adapters (Engineering). Confidence thresholds for stakeholders (0.8), decision points (0.75). |
| **Scenario Template System** | **Implemented** | `models/scenario_template.py` | Templates with difficulty_level, complexity_score, usage tracking. |
| **Clickable Decision Points** | **Functional** | `step5_interactive.py:147` `/choose` endpoint | Users click options, POST to `/choose`, get LLM-generated consequences back. |
| **Timeline Navigation** | **Functional** | `step5.py:111` `/timeline` route | Dedicated timeline viewer with phases and expandable details. |
| **Participant Perspective Switching** | **Not started** | — | NarrativeCharacter has motivations/ethical_stance but no UI to switch perspective. |
| **Links to Precedent Cases** | **Not started** | — | No cross-case linking in scenario views. |
| **Relationship Network Visualization** | **Partial** | `models/scenario_participant.py` has `relationships` JSONB column | Data structure exists but no graph/network UI. |

## 2. False Starts and Abandoned Attempts

| Location | What It Is | Why It Appears Incomplete |
|----------|-----------|--------------------------|
| `models/decision.py` (34 lines) | Legacy `Decision` model with `options` JSON, `selected_option`, `decision_time` | Superseded by `Action` model's `is_decision=True` flag in `event.py`. Kept for backward compatibility but no new code writes to it. |
| `services/scenario_pipeline/wizard_scenario_generator.py` | `WizardScenarioGenerator` — step-by-step wizard-driven scenario creation | Alternative approach to the 9-stage orchestrator. Appears to be from an earlier iteration before the unified pipeline was designed. |
| `services/scenario_pipeline/enhanced_llm_scenario_service.py` | `EnhancedLLMScenarioService` — LLM-driven scenario generation | Another parallel attempt. Uses a different entry point than the orchestrator. |
| `services/scenario_pipeline/scenario_generation_phase_a.py` | `DirectScenarioPipelineService` — direct pipeline without SSE | Third parallel approach, bypassing the SSE streaming architecture. |
| `orchestrator.py:316-325` `next_steps` list | Lists "Implement Stage 2-9" but Stages 2-3 are already implemented in the same file | The `next_steps` metadata wasn't updated after Stages 2-3 were built. The `status: 'complete_placeholder'` on line 314 is also stale. |
| `generate_scenario.py:128-148` Stage 3 in SSE | SSE endpoint shows Stage 3 as "placeholder" with just role names | But the orchestrator's `generate_complete_scenario()` actually calls `participant_mapper.create_participants()`. The SSE route pre-fetches data before the generator and doesn't call the orchestrator — it runs Stages 1-2 directly, then emits placeholders for 3-9. **The SSE route and orchestrator are out of sync.** |

## 3. Current Entry Points

**User trigger:** Navigate to `/scenario_pipeline/case/<id>/step5` which renders `templates/scenarios/step5.html`. This page has three tabs:
- **Narrative Overview** — loaded from Phase 4 data via `_load_narrative_elements()`
- **Event Timeline** — loaded via `_load_timeline_data()`
- **Decision Wizard** — loaded via `_load_scenario_seeds()`

**Scenario generation:** A button on Step 5 hits the SSE endpoint `/case/<id>/generate_scenario` which streams progress events. But this is the scaffolding pipeline — the real synthesis data comes from Phase 4 (`construct_phase4_narrative()`) which runs as part of `CaseSynthesizer.synthesize_complete()` back in Step 4.

**Interactive exploration:** POST to `/case/<id>/step5/interactive/start` creates a `ScenarioExplorationSession`, then redirects to `/step5/interactive/<session_uuid>` which presents decision points one at a time.

## 4. How It Consumes Synthesis Output

| Scenario Generation Component | Reads From | Synthesis View Connection |
|-------------------------------|-----------|--------------------------|
| `ScenarioDataCollector` (Stage 1) | `TemporaryRDFStorage` directly + committed ontology via OntServe | **Re-queries DB independently.** Does not read `CaseSynthesisModel` or the seven views. Builds its own `ScenarioSourceData` with merged entity sets. |
| `TimelineConstructor` (Stage 2) | `TemporaryRDFStorage` for Actions/Events with temporal data | **Re-queries DB.** Parallel to but independent of the `EntityGroundedTimeline` in the narrative module. |
| `ParticipantMapper` (Stage 3) | Role entities from Stage 1's `ScenarioSourceData` | **Consumes Stage 1 output**, not synthesis views. |
| `step5.py` view loading | `ExtractionPrompt` table where `concept_type='phase4_narrative'` | **Reads Phase 4 output from DB.** The `_load_phase4_data()` function loads the stored `Phase4NarrativeResult` which contains narrative elements, timeline, scenario seeds, and insights. This is the **only path** that reads synthesis view output. |
| `interactive_scenario_service` | `ExtractionPrompt` for canonical decision points + `TemporaryRDFStorage` for entities | **Reads Phase 3 decision points** (the Decisions view) and entity data. Consumes the `CanonicalDecisionPoint` list to drive the interactive flow. |

**Key finding:** The 9-stage orchestrator pipeline and the synthesis pipeline are **parallel paths that don't connect**. The orchestrator re-queries raw data from `TemporaryRDFStorage` independently. The Step 5 UI loads Phase 4 narrative output (which *is* connected to synthesis). The interactive exploration reads Phase 3 decision points. There is no single path that flows: synthesis views → scenario generation → interactive experience.

## 5. Interactive Features Status

| Feature | Status | How It Works |
|---------|--------|-------------|
| **Click to choose at decision points** | **Functional** | User sees options, clicks one, POST to `/choose`, LLM generates consequences narrative, fluents are updated (Event Calculus), next decision presented. |
| **Board choice comparison** | **Functional** | Each `ScenarioExplorationChoice` records `board_choice_index` and `matches_board_choice` boolean. Shown in final analysis. |
| **Final analysis generation** | **Functional** | Route at `/step5/interactive/<uuid>/analysis` shows comparison of user choices vs. board decisions across all decision points. |
| **Session persistence** | **Functional** | `ScenarioExplorationSession` stores `active_fluents`, `terminated_fluents`, `current_decision_index`. Sessions can be resumed. |
| **Timeline viewer** | **Functional** | Dedicated route `/case/<id>/timeline` with phase-based chronological display and expandable details. |
| **Narrative tab** | **Functional** | Characters with motivations/ethical stance, setting description, initial states displayed. |
| **Progress streaming** | **Scaffolding only** | SSE events fire for all 9 stages but stages 4-9 emit placeholder messages with no real computation. |
| **Perspective switching** | **Not implemented** | No UI to view scenario from different character viewpoints despite data support. |
| **Relationship network graph** | **Not implemented** | `ScenarioParticipant.relationships` JSONB exists but no visualization. |
| **Precedent case links** | **Not implemented** | No cross-case navigation. |

## 6. Narrative Summary

The scenario generation system has **two disconnected pipelines** built at different times:

**Pipeline A (Phase 3-4 Synthesis → Step 5 UI):** This is the working path. `CaseSynthesizer` runs Phases 1-4, producing `CanonicalDecisionPoint` objects (Phase 3) and `Phase4NarrativeResult` with narrative elements, entity-grounded timeline, scenario seeds, and case insights (Phase 4). These are stored in `ExtractionPrompt` rows. Step 5's UI loads them and renders three tabs. The interactive exploration service reads the canonical decision points and drives a choose-consequence-advance loop with Event Calculus fluent tracking. This pipeline is **functional end-to-end** for the core experience of walking through decision points.

**Pipeline B (9-Stage Orchestrator):** This was designed as the "proper" scenario generation architecture with data collection, timeline construction, participant mapping, and six unimplemented stages. Stages 1-3 work but don't consume Pipeline A's synthesis output — they re-query raw data independently. Stages 4-9 are placeholders that report progress events but compute nothing. The SSE endpoint is additionally out of sync with the orchestrator (it runs Stages 1-2 inline, then emits placeholder events for 3-9 without calling the orchestrator's Stage 3). This pipeline appears to be a **forward-looking architectural skeleton** that was never connected.

There are also **three abandoned alternatives** in `services/scenario_pipeline/` (wizard, enhanced LLM, direct) that represent earlier approaches before either pipeline was designed.

The practical state: a user can complete synthesis (Step 4), go to Step 5, see narrative/timeline/seeds, start an interactive exploration, click through decision points with LLM-generated consequences, and see a final analysis comparing their choices to the board's. The 9-stage pipeline and the three abandoned alternatives are not part of this working path.
