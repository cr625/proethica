# Interactive Scenario (Step 5)

Step 5 transforms a fully analyzed case (Steps 1-4 complete) into an interactive teaching scenario. Three integrated views present the case from different perspectives: a readable narrative, a chronological timeline of entities, and a guided walk through the ethical decision points the case raises.

Step 5 is open to all users. Authentication is not required to view a scenario.

## Access

Step 5 is reachable from the case detail page after the extraction pipeline (Steps 1-4) has completed for that case. The route is:

```
/scenario_pipeline/case/<case_id>/step5
```

The pipeline sidebar on a completed case shows Step 5 alongside Steps 1-4. If Steps 1-4 have not finished, Step 5 reports the missing prerequisites rather than rendering an incomplete scenario.

## The Three Views

Step 5 presents a single tabbed interface with three views over the same underlying case data.

### Narrative Overview

A re-presentation of the case as a readable narrative. Characters drawn from extracted Roles, situational context drawn from States, and the case progression drawn from the Actions and Events timeline are composed into prose that retells the case for a reader who has not seen the original NSPE document.

| Source data | Used for |
|-------------|----------|
| Roles (R) | Characters and stakeholders |
| States (S) | Situational context and conditions |
| Actions (A) and Events (E) | Narrative progression |
| Step 4 Causal-Normative Links | Cross-references between facts and norms |

### Entity Timeline

A chronological visualization of the case Actions and Events. Each timeline entry links to the entities involved (Roles, Resources, States) and shows the temporal relations extracted in Step 3 (Allen relations: before, meets, overlaps, etc.). Use this view to trace cause and effect through the case.

### Decision Wizard

A guided walk through the canonical decision points extracted in Step 4 Phase 3. For each decision point, the wizard presents:

- The factual situation that creates the decision
- The applicable obligations, principles, and constraints
- Available courses of action (Capabilities)
- The board's resolution pattern (where one was identified)
- Discovery prompts that surface considerations the original case discussion may not have made explicit

Users can step through the decision points in sequence or jump to a specific point. The wizard records exploration sessions in the database (`scenario_exploration_sessions` table) but does not require login. Anonymous explorations are stored without a user identifier.

## Underlying Data

Step 5 reads from data already produced by earlier pipeline steps. It does not perform new extraction or synthesis.

| Data | Produced by | Used in |
|------|-------------|---------|
| Nine-component entities | Steps 1-3 | All three views |
| Code Provisions, Precedent References | Step 4 Phase 2A-2B | Decision Wizard context |
| Ethical Questions and Conclusions | Step 4 Phase 2C | Decision Wizard prompts |
| Canonical Decision Points | Step 4 Phase 3 | Decision Wizard structure |
| Resolution Patterns, Causal-Normative Links | Step 4 Phase 2E | Decision Wizard reasoning paths |
| Narrative Construction outputs | Step 4 Phase 4 | Narrative Overview |
| Action and Event timeline | Step 3 | Entity Timeline |

## Eligibility

A case is eligible for Step 5 when Steps 1-4 are complete. The Step 5 page displays an eligibility report on entry and surfaces any missing data (for example, an empty Phase 4 narrative would prevent the Narrative Overview from rendering, while still permitting the Timeline and Decision Wizard views).

## Related Documentation

- [Viewing Extractions](viewing-extractions.md) - How extracted entities are displayed
- [Pipeline Terminology](../concepts/terminology.md) - Step, Pass, Phase definitions
- [Nine-Component Framework](../concepts/nine-components.md) - The entities Step 5 draws from
