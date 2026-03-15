# Interactive Scenario Exploration Design Spec

**Date:** 2026-03-15
**Status:** Approved
**Branch:** `feature/ht2026-scenario-branching`
**Target:** HT 2026 paper (April 17 deadline) + IRB evaluation study (April-May 2026)

---

## 1. Goal

Replace the current LLM-at-runtime interactive scenario exploration with a pre-computed, zero-latency interface. Users walk through a sequential series of decision points (one card at a time), choose options without knowing the board's choice, and then see a branching analysis view comparing their path to the board's path.

The interface serves two purposes: Section 4 of the HT 2026 paper (demonstrating agentic narrative traversal) and the "Decisions" view in the IRB evaluation study (measuring perceived utility of structured decision-point presentation).

## 2. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Runtime LLM calls | None | Pre-compute all consequence data during Phase 4 extraction. Deterministic, reviewable, zero latency. |
| Traversal structure | Sequential (Approach C) | All users see all 5 decisions in order. Enables inter-rater comparison in study. |
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

**Output:** Each option receives a 2-3 sentence `consequence_narrative` describing what follows from that choice, plus structured `consequence_obligations` and `consequence_fluent_changes`.

### 3.2 Session Model

`ScenarioExplorationChoice` stores only:
- `decision_point_index`
- `chosen_option_index`
- `chosen_option_label`
- `time_spent_seconds`

The `consequences_narrative`, `fluents_initiated`, `fluents_terminated`, and `context_provided` columns become unused for new sessions (retained for backward compatibility with any existing session data). Consequence data is read from Phase 4 output, not stored per-session.

`ScenarioExplorationSession` retains `case_id`, `session_uuid`, `status`, `current_decision_index`. The `active_fluents`, `terminated_fluents`, and `final_analysis` JSON columns become unused. No fluent tracking at runtime.

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
- `get_current_decision()` -- returns decision point data from Phase 4 (question, options without consequence data, competing obligations)
- `process_choice()` -- records choice index only, advances session, no LLM call
- `_load_decision_points()` -- unchanged, reads from Phase 4 data

**Add:**
- `get_analysis_data()` -- loads full Phase 4 branch data including all consequence narratives, board rationale, resolution, and builds the comparison structure (user path vs board path with divergence markers)

### 3.4 Route Changes

**`make_choice`:** Remove LLM call and provenance tracking for consequence generation. Record choice index, redirect to next decision or summary.

**`interactive_analysis`:** Load Phase 4 data directly via `get_analysis_data()`. No call to `generate_final_analysis()`. Pass pre-computed comparison data to template.

**New route: `interactive_summary`** (optional intermediate page between last decision and analysis): Shows the 5 choices the user made (labels only, no consequences, no board comparison). Serves as a pause point before the board reveal.

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
3. **Competing obligations:** Small muted badges showing the ethical tension this decision navigates. Two badges per decision, drawn from `competing_obligations`.
4. **Option buttons:** 2-3 option buttons, each showing the option label. Styled as selectable cards (border highlight on hover/select, similar to current option-card pattern). No descriptions during traversal to keep cards compact.
5. **Action button:** "Make This Choice" to confirm and advance.

**No consequence display.** No board choice indicator. No fluent state display.

### 4.3 Transitions

When the user confirms a choice:
1. The choice is recorded via POST (no LLM call).
2. `document.startViewTransition()` wraps the DOM update.
3. The current card crossfades to the next decision card.
4. The stepper updates: previous step dims with check, next step activates.
5. Fallback: instant DOM swap for browsers without View Transition API support.

### 4.4 Summary Card

After the last decision, a summary card appears:
- "You have completed all 5 decisions."
- List of the 5 decision labels and the option the user chose at each (plain text, no color coding).
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

- Each node is a circle or rounded rectangle.
- Color coding: green for match, amber for diverge.
- Nodes are clickable: clicking scrolls the page to the corresponding detail card below.
- The tree is not a full branching graph (since traversal is sequential). It visualizes the alignment pattern across the 5 decisions.
- Pure CSS: flexbox layout, `::before`/`::after` pseudo-elements for connector lines, no D3.

### 5.2 Summary Stats Bar

Single row below the tree:
- Match count: "3 of 5 aligned with board" with green/amber coloring.
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

A new function in the scenario generation orchestrator, called after the existing branch/decision-point generation stage. Runs as part of Phase 4, not as a separate pipeline step.

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
- `consequence_obligations` (list of obligation URIs activated by this choice)
- `consequence_fluent_changes` (initiated/terminated fluent lists)

Per decision point:
- `board_rationale` (2-3 sentences drawn from resolution/conclusions data)

### 6.4 LLM Prompt Strategy

One LLM call per decision point (not per option) to generate consequences for all options simultaneously. The prompt provides the full decision context, all options, the causal links and fluent data, and asks for consequence narratives for each option plus the board rationale. This keeps the call count manageable (5 calls per case).

## 7. Study Compatibility

| Study Element | Interface Mapping |
|---------------|-------------------|
| Part 1: Rate Decisions view | Traversal view (sequential card walkthrough) |
| Likert item 1: "decision points helped me understand choices" | Each card presents one decision with clear options |
| Likert item 2: "alternatives helped me evaluate choices" | Analysis view tabbed exploration of all options |
| Likert item 3: "trace actions to obligations" | Competing obligation badges on each card + consequence obligation badges in analysis |
| Part 2: Comprehension questions | Answered after traversal, before analysis view |
| Part 2: Board reveal + alignment | Analysis view entry point |
| Part 3: Retrospective reflection | After analysis view |
| Board conclusions withheld | No board choice indicator during traversal |
| Pre-generated output | All consequence data from Phase 4 |
| 3-4 cases per participant, ~1 hour | No LLM latency; traversal is fast (5 clicks per case) |

## 8. Files to Create or Modify

### New Files
- `app/services/scenario_generation/consequence_generator.py` -- Phase 4 consequence generation sub-stage
- `app/templates/scenarios/step5_traversal.html` -- new traversal template (replaces step5_interactive.html usage)
- `app/templates/scenarios/step5_branching_analysis.html` -- new analysis template (replaces step5_analysis.html usage)
- `app/static/css/scenario-traversal.css` -- stepper, card transitions, decision tree styles

### Modified Files
- `app/services/interactive_scenario_service.py` -- refactor to pure data reader
- `app/services/scenario_generation/orchestrator.py` -- add consequence generation stage
- `app/routes/scenario_pipeline/step5_interactive.py` -- simplify routes, remove LLM calls
- `app/models/scenario_exploration.py` -- no schema changes needed; existing columns retained for backward compatibility

### Retained Unchanged
- `app/templates/scenarios/base_step.html` -- base template
- `app/templates/scenarios/step5_sessions.html` -- session list page
- Phase 4 stages 1-3 and existing stage 4 output (consequence generation appends to existing data)

## 9. Future Upgrade Path

The architecture supports upgrading to Approach B (true branching traversal) with these changes only:
- Fix `leads_to` fields in Phase 4 data to route to different branches based on choice
- Make the stepper a path indicator instead of a linear progress bar
- Change `get_current_decision()` to follow `leads_to` routing instead of incrementing index
- No template, model, or route architecture changes needed
