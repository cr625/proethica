# Interactive Scenario Exploration Design Spec

**Date:** 2026-03-15
**Status:** Implemented (merged to `development` 2026-03-20)
**Branch:** `feature/ht2026-scenario-branching` (merged, deleted)
**Target:** HT 2026 paper (April 17 deadline) + IRB evaluation study (April-May 2026)

---

## 1. Goal

Replace the current LLM-at-runtime interactive scenario exploration with a pre-computed, zero-latency interface. Users walk through a sequential series of decision points (one card at a time), choose options without knowing the board's choice, and then see a branching analysis view comparing their path to the board's path.

The interface serves two purposes: Section 4 of the HT 2026 paper (demonstrating agentic narrative traversal) and the "Decisions" view in the IRB evaluation study (measuring perceived utility of structured decision-point presentation).

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime LLM calls | None | Pre-compute all consequence data during Phase 4 extraction. Deterministic, reviewable, zero latency. |
| Traversal structure | Sequential (Approach C) | All users see all decisions in order (variable count per case). Enables inter-rater comparison in study. |
| Consequence display during traversal | Batched at end | Consequences stored per-decision but not shown during traversal. Displayed in analysis view. Supports future upgrade to per-decision reveal. |
| Board choice visibility | Hidden during traversal | IRB protocol withholds board conclusions until Part 2 alignment phase. Board reveal happens in analysis view. |
| Analysis structure | Branching exploration | Mini decision tree header + tabbed detail cards. Users explore all options' consequences at any decision point. |
| Stepper design | Decision-maker pills | Each step labeled with the actor (e.g., "Engineers", "Firm", "Board"). Communicates perspective shifts without revealing content. |
| Card transitions | View Transition API | CSS crossfade between decision cards. Falls back to instant swap. |

## 3. Architecture

### 3.1 Data Layer: Phase 4 Enhancement

A new sub-stage in the Phase 4 pipeline generates consequence narratives for every option at every decision point. The sub-stage runs once per case during extraction.

**New fields added to `scenario_seeds.branches[N].options[M]`:**

```json
{
  "option_id": "opt_0_1",
  "label": "Finalize Arrangements and Resign Simultaneously",
  "description": "...",
  "action_uris": ["case-102#Negotiate_With_Consulting_Firms_While_Employed"],
  "is_board_choice": false,
  "leads_to": "branch_1",
  "consequence_narrative": "By finalizing the joint venture contract while still employed at the agency, the engineers create a direct conflict of interest...",
  "consequence_obligations": [
    "Active-Employment Private Contract Conclusion Prohibition Obligation"
  ],
  "consequence_fluent_changes": {
    "initiated": ["Conflict_of_Interest_Active"],
    "terminated": ["Clean_Separation_Possible"]
  }
}
```

**New field added to `scenario_seeds.branches[N]`:**

```json
{
  "board_rationale": "The Board determined that concluding private arrangements prior to resignation violates the spirit of the Canons..."
}
```

**Input data for consequence generation:**
- The option's `action_uris` linked to extracted Action entities
- `timeline.causal_links` mapping actions to triggered obligations
- `timeline.event_trace` for fluent state changes
- `narrative_elements.resolution` for board rationale
- `narrative_elements.conflicts` for ethical tension context

**Output:** Each option receives a 2-3 sentence `consequence_narrative` describing what follows from that choice, plus structured `consequence_obligations` (list of obligation URIs) and `consequence_fluent_changes` (object with `initiated` and `terminated` arrays, as shown in the JSON example above).

**Storage strategy:** The consequence generator modifies the existing `phase4_narrative` JSON in-memory during the Phase 4 pipeline run, before the final `ExtractionPrompt` row is written. It is not a separate pipeline step that writes a second row -- it augments the `scenario_seeds.branches` data within the same `construct_phase4_narrative()` call chain. For existing cases that need consequence data, a batch re-run of the Phase 4 consequence sub-stage will update the existing `ExtractionPrompt.raw_response` row in place (load JSON, add consequence fields, save). Study cases (the 23 NSPE cases referenced in the IRB protocol) must have consequence data generated before the evaluation window.

**Obligation label resolution:** The existing `involved_obligation_uris` field on each branch contains URIs, not human-readable labels. The consequence generator also adds a `competing_obligation_labels` field (list of strings) resolved from the URIs via the case entity data. The traversal template reads `competing_obligation_labels` for display.

### 3.2 Session Model

`ScenarioExplorationChoice` stores:
- `decision_point_index`
- `chosen_option_index`
- `chosen_option_label`
- `decision_point_label` (populated from `decision_maker_label` in Phase 4 data)
- `board_choice_index` (populated from Phase 4 `is_board_choice` flag at write time)
- `board_choice_label` (populated from Phase 4 data at write time)
- `matches_board_choice` (computed at write time: `chosen_option_index == board_choice_index`)
- `time_spent_seconds`

Board comparison fields continue to be populated at write time (from Phase 4 data, not LLM). This preserves `get_choices_summary()` compatibility and avoids conditional code paths for old vs. new sessions.

The `consequences_narrative`, `fluents_initiated`, `fluents_terminated`, and `context_provided` columns become unused for new sessions (retained in the schema for backward compatibility with existing session data). Consequence data is read from Phase 4 output, not stored per-session.

`ScenarioExplorationSession` retains `case_id`, `session_uuid`, `status`, `current_decision_index`. The `active_fluents` and `terminated_fluents` JSON columns become unused (no fluent tracking at runtime). The `final_analysis` column becomes unused for new sessions; `get_analysis_data()` reads Phase 4 data instead. Code paths that display existing completed sessions must check `session.final_analysis` first (old path) and fall back to `get_analysis_data()` (new path).

### 3.3 Service Refactor

`InteractiveScenarioService` becomes a pure data reader:

**Remove:**
- `_generate_consequences()` -- consequences are pre-computed
- `_generate_analysis_narrative()` -- analysis uses extracted resolution data
- `_generate_option_label()` -- option labels pre-computed in Phase 4
- `_generate_default_options()` -- same
- `_ensure_option_labels()` -- same
- `_load_event_calculus_rules()` -- not needed at runtime
- All LLM client initialization (`_get_llm_client()`, `self.llm_client`)

**Retain and simplify:**
- `start_session()` -- creates session, loads decision point count
- `get_session()` -- unchanged
- `get_current_decision()` -- returns decision point data from Phase 4 (question, options without consequence data, `competing_obligation_labels`)
- `process_choice()` -- records choice index only, advances session, no LLM call
- `_load_decision_points()` -- unchanged, reads from Phase 4 data

**Add:**
- `get_analysis_data()` -- loads full Phase 4 branch data including all consequence narratives, board rationale, resolution, and builds the comparison structure (user path vs board path with divergence markers)

### 3.4 Route Changes

**All interactive routes (`start_interactive_exploration`, `start_interactive_exploration_ajax`, `make_choice`):** Change decorator from `@auth_required_for_llm` to `@auth_required_for_write`, since none of these routes invoke LLM after the refactor.

**`make_choice`:** Remove LLM call (study participants will need write access to record choices; if they are unauthenticated, this becomes `@auth_optional` with CSRF protection only). Record choice index plus board comparison fields (from Phase 4 data), redirect to next decision or summary. Retain interaction provenance tracking (`prov.track_activity(activity_type='interaction', ...)`) for study auditing -- this records which option was chosen and time spent, independent of LLM calls. Remove only the consequence-generation provenance block.

**`interactive_analysis`:** Load Phase 4 data directly via `get_analysis_data()`. No call to `generate_final_analysis()`. For existing sessions with `final_analysis` already populated, use the stored data. For new sessions, build analysis from Phase 4 data. Pass pre-computed comparison data to template.

**New route: `interactive_summary`:** Required intermediate page between last decision and analysis. Shows all choices the user made (labels only, no consequences, no board comparison). In the study workflow, this is where participants answer the four comprehension questions (Part 2) before the board reveal. If comprehension questions are collected via an external survey instrument (e.g., Qualtrics embedded iframe or linked form), this page displays the summary and a link to the survey, with a "View Analysis" button that becomes active after survey completion. If comprehension questions are in-app, this page includes the question form. The exact mechanism depends on study infrastructure decisions (to be finalized during IRB preparation in April).

## 4. Traversal View

### 4.1 Stepper Bar

Horizontal row of Bootstrap nav-pills anchored at the top of the card area.

```
[ Engineers (1) ] --- [ Engineers (2) ] --- [ Firm (3) ] --- [ Venture (4) ] --- [ Board (5) ]
    [filled]            [dimmed+check]      [current]         [outline]          [outline]
```

- **Current step:** Filled pill with prominent color, labeled with decision-maker name and step number.
- **Completed steps:** Dimmed pill with check icon. Label retained.
- **Future steps:** Outlined/muted pill. Label visible but subdued.
- Pills are not clickable during traversal (no going back during the study).
- Responsive: on narrow screens, pills collapse to numbered dots with the current decision-maker label shown separately.

### 4.2 Decision Card

Single Bootstrap card centered below the stepper.

**Content, top to bottom:**
1. **Context block** (muted background): Opening narrative context (first decision) or brief transitional sentence (subsequent decisions). 2-3 sentences max.
2. **Question text:** The decision question in a visually distinct block (larger text, slight background).
3. **Competing obligations:** Small muted badges showing the ethical tension this decision navigates. Typically two badges per decision, drawn from `competing_obligation_labels` (resolved labels added by the consequence generator; source field is `involved_obligation_uris`).
4. **Option buttons:** 2-3 option buttons, each showing the option label. Styled as selectable cards (border highlight on hover/select, similar to current option-card pattern). No descriptions during traversal to keep cards compact.
5. **Action button:** "Make This Choice" to confirm and advance.

**No consequence display.** No board choice indicator. No fluent state display.

### 4.3 Transitions

When the user confirms a choice:
1. The choice is recorded via POST (no LLM call).
2. `document.startViewTransition()` wraps the DOM update (Chrome 111+, Edge 111+).
3. The current card crossfades to the next decision card.
4. The stepper updates: previous step dims with check, next step activates.
5. Fallback for browsers without View Transition API (Firefox, Safari as of early 2026): instant DOM swap with a subtle CSS opacity transition (0.15s fade) so the change is not jarring. The `scenario-traversal.css` file includes a `.no-view-transitions` fallback class applied via feature detection (`if (!document.startViewTransition)`).

### 4.4 Summary Card

After the last decision, the user is redirected to the summary page (see `interactive_summary` route in Section 3.4):
- "You have completed all decisions." (Dynamic count, not hardcoded.)
- List of all decision labels and the option the user chose at each (plain text, no color coding).
- Study comprehension question integration point (see Section 3.4).
- "View Analysis" button to proceed to the analysis view (board reveal).

## 5. Analysis View

### 5.1 Mini Decision Tree (Header)

A compact horizontal tree rendered with CSS flexbox and pseudo-element connector lines.

```
  [DP1] ---- [DP2] ---- [DP3] ---- [DP4] ---- [DP5]
   |           |           |           |           |
  You: A     You: B     You: A     You: C     You: A
  Brd: A     Brd: A     Brd: A     Brd: B     Brd: A
   [match]    [diverge]   [match]    [diverge]   [match]
```

(Example shows 5 nodes; actual count varies per case.)

- Each node is a circle or rounded rectangle.
- Color coding: green for match, amber for diverge.
- Nodes are clickable: clicking scrolls the page to the corresponding detail card below.
- The tree is not a full branching graph (since traversal is sequential). It visualizes the alignment pattern across all decisions for the case.
- Pure CSS: flexbox layout, `::before`/`::after` pseudo-elements for connector lines, no D3.
- Responsive: on narrow screens (< 576px), the horizontal tree collapses to a vertical stack of nodes. Each node becomes a horizontal row: `[icon] Decision-maker -- match/diverge badge`. This avoids horizontal overflow on mobile devices.

### 5.2 Summary Stats Bar

Single row below the tree:
- Match count: "N of M aligned with board" (dynamic) with green/amber coloring.
- Compact -- one line, not the large percentage banner from the current template.

### 5.3 Tabbed Detail Cards

One card per decision, vertically stacked. Each card:

**Header:**
- Decision-maker label + decision number
- Match/diverge badge (green check or amber icon)

**Tabs:**
- **"Your Choice"** (default active): Option label, pre-computed consequence narrative, activated obligations as colored entity badges.
- **"Board's Choice"**: Same structure. If the user's choice matched the board's, this tab shows "Same as your choice" with a check.
- **"Alternative: [option label]"** (one tab per remaining unchosen option): Same structure. These tabs enable the branching exploration -- users can see what would have happened at any decision point.
- **"Board's Rationale"** (collapsed section within the Board's Choice tab): The `board_rationale` text explaining why the board chose as they did.

### 5.4 Resolution Section

Below all detail cards:
- The board's full resolution text from `narrative_elements.resolution`.
- Resolution type badge (e.g., "stalemate", "violation").
- Board conclusions listed.

## 6. Phase 4 Sub-Stage: Consequence Generation

### 6.1 Pipeline Integration

A new function called within the Phase 4 narrative construction pipeline (`app/services/narrative/__init__.py`, specifically the `construct_phase4_narrative()` call chain). It runs after the existing branch/decision-point generation in `scenario_seed_generator.py` and before the final result is serialized to `ExtractionPrompt.raw_response`. It is not part of the scenario generation orchestrator at `app/services/scenario_generation/orchestrator.py` (which has a different scope). The consequence generator is a new module (`app/services/scenario_generation/consequence_generator.py`) called from within the narrative pipeline.

### 6.2 Input

For each option at each decision point:
- Option label and `action_uris`
- The full set of extracted entities for the case (Actions, Obligations, Principles, Constraints)
- `timeline.causal_links` for the action URIs
- `timeline.event_trace` for fluent context
- `narrative_elements.resolution` and `conclusions` for board rationale
- `narrative_elements.conflicts` for ethical tension framing

### 6.3 Output

Per option:
- `consequence_narrative` (2-3 sentences)
- `consequence_obligations` (list of resolved obligation labels activated by this choice)
- `consequence_fluent_changes` (object with `initiated` and `terminated` arrays, matching the JSON structure in Section 3.1)

Per decision point:
- `board_rationale` (2-3 sentences drawn from resolution/conclusions data)

### 6.4 LLM Prompt Strategy

One LLM call per decision point (not per option) to generate consequences for all options simultaneously. The prompt provides the full decision context, all options, the causal links and fluent data, and asks for consequence narratives for each option plus the board rationale. This keeps the call count manageable (typically 3-7 calls per case, depending on decision point count).

## 7. Study Compatibility

| Study Element | Interface Mapping |
|---------------|-------------------|
| Part 1: Rate Decisions view | Traversal view (sequential card walkthrough) |
| Likert item 1: "decision points helped me understand choices" | Each card presents one decision with clear options |
| Likert item 2: "alternatives helped me evaluate choices" | Analysis view tabbed exploration of all options |
| Likert item 3: "trace actions to obligations" | Competing obligation badges on each card + consequence obligation badges in analysis |
| Part 2: Comprehension questions | Answered on summary page (after traversal, before analysis view). Integration point for external survey or in-app form (see Section 3.4). |
| Part 2: Board reveal + alignment | Analysis view entry point |
| Part 3: Retrospective reflection | After analysis view |
| Board conclusions withheld | No board choice indicator during traversal |
| Pre-generated output | All consequence data from Phase 4 |
| 3-4 cases per participant, ~1 hour | No LLM latency; traversal is fast (one click per decision point per case). Time budget per case: ~5 min traversal + ~5 min comprehension questions + ~5 min analysis exploration = ~15 min, fitting 4 cases in 1 hour. |

## 8. Files to Create or Modify

### New Files
- `app/services/scenario_generation/consequence_generator.py` -- Phase 4 consequence generation sub-stage
- `app/templates/scenarios/step5_traversal.html` -- new traversal template (replaces step5_interactive.html usage)
- `app/templates/scenarios/step5_summary.html` -- summary page between traversal and analysis (comprehension question integration point)
- `app/templates/scenarios/step5_branching_analysis.html` -- new analysis template (replaces step5_analysis.html usage)
- `app/static/css/scenario-traversal.css` -- stepper, card transitions, decision tree styles

### Modified Files
- `app/services/interactive_scenario_service.py` -- refactor to pure data reader
- `app/services/narrative/__init__.py` -- call consequence generator within `construct_phase4_narrative()` chain
- `app/routes/scenario_pipeline/step5_interactive.py` -- simplify routes, remove LLM calls
- `app/models/scenario_exploration.py` -- no schema changes needed; existing columns retained for backward compatibility

### Retained Unchanged
- `app/templates/scenarios/base_step.html` -- base template
- `app/templates/scenarios/step5_sessions.html` -- session list page
- Phase 4 stages 1-3 and existing stage 4 output (consequence generation appends to existing data)

## 9. Future Upgrade Path

The architecture supports upgrading to Approach B (true branching traversal) with these changes only:
- Extend `leads_to` fields in Phase 4 data to route to different branches based on choice (currently all point to the next sequential branch)
- Make the stepper a path indicator instead of a linear progress bar
- Change `get_current_decision()` to follow `leads_to` routing instead of incrementing index
- No template, model, or route architecture changes needed

**Decision point count variability:** The number of decision points per case depends on the Phase 4 extraction output (`scenario_seeds.branches` length). Observed range across the 118 existing cases should be documented during the batch consequence-generation run. The study protocol references 23 cases; if any have fewer than 3 or more than 7 decision points, the study case selection should account for this to ensure reasonable traversal length.
