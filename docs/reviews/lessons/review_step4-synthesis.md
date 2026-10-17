# Review of the step4-synthesis lessons (brief 2)

Branch reviewed: `review/case8-lessons/step4-synthesis` (three commits 1108e13, 1016cdb, 0e7421e on a7261ba7), as merged into `review/case8-lessons/integration` at dc8f961 with the follow-up fbad9ed. Fixes and the tests behind them are on `review/case8-lessons/step4-synthesis-review`. Written 2026-10-17 in a cloud session; no database, no model API.

## Question 1. Do the tests reproduce the case 8 failures, fail on the base and pass on the branch

The five new test files (66 tests) import the modules and functions the branch adds (`grounding.py`, `qc_prompt_rows.py`, `analysis_literals.py`, `board_resolution_for`, `resolve_normative_slots`, `validate_against_extracted`, `load_step3_causal_chains`, `quote_appears_in`, `attributes_to_board`, `truncate_at_boundary`), so on a7261ba7 every file errors at collection with an ImportError; none of the 66 can run there. All pass at the branch tip (82 with the three suites the branch changed) and on the integration branch (82, after the provider-double fix fbad9ed).

The fixtures carry the case 8 observations of the review log, section 4.4:

| Lesson | Test file | Observation reproduced |
|---|---|---|
| L1 actions by category | `test_step4_lessons_decision_points.py`, `test_l1_*` | Label-minted URIs (`case-8#Work_Suspension_Request`) that the `#Action_` prefix test discarded (D-38, empty involved_action_uris); an echoed State URI still rejected. |
| L2 board resolution | `test_l2_*` | A Board text over 800 characters kept whole, the generated Conclusion_101 kept out, an empty field when only a generated conclusion answers (D-38, concatenated and truncated resolutions). |
| L3 analytical extension | `test_l3_*` | A point aligned to Question_103 carries no board choice; the verifier sees Board conclusions only and clears the DP5 flag (D-38, the fabricated board choice); II.1.f dropped from the backing (D-38, uncited provisions). |
| L4 slots and competing pair | `test_l4_*` | Faithful Agent Duty in the constraint slot becomes a second involvesObligation; the committed competesWith edges pick the competitor of DP2 (D-38, mis-slotted competitors, D-41). |
| L5 prompt assembly | `test_step4_lessons_prompt_assembly.py` | Generated rows leave the Board headings of the refine, resolution-pattern and transformation prompts; the emergence prompt carries the facts; implicit questions need a facts quote (D-35, D-36); Board-attributed extensions need a quoted span (D-37); determinative principles are a closed list (D-36, ResolutionPattern_12). |
| L6 linker row | `test_step4_lessons_persistence.py` | The qc_link row exists and no save site slices prompt text (section 4.6, rows 8616 and 8617). |
| L7 narrative | `test_step4_lessons_narrative.py` | Storage order against the stored sequence; enables links only from CausalChain rows; board_rationale only with a Board conclusion (D-38, the phase 4 narrative). |
| L8 commit and provisions | `test_step4_lessons_commit.py` | Replaced literals, the stale-row gate, contradictory resolution conditions (D-37, ResolutionPattern_16), the linker context and actor rule (D-39), one verdict per multi-code sentence (D-39). |

One gap: the stale-row gate of L8 was exercised on hand-built graphs only. `tests/unit/test_step4_lessons_review.py` now runs it against the TTL the append-path emitter writes, twice, and checks that a replaced board resolution is accepted and a literal the graph never received is reported. It passes without changes to the gate.

## Question 2. Behaviour the rules do not name

### Fixed on the review branch

1. **Stored decision points lost their alignment and competition fields on reload.** `app/routes/scenario_pipeline/step4/helpers.py` (`load_canonical_points_for_phase4`, line 252) and `app/services/case_synthesizer/synthesizer.py` (`CaseSynthesizer.load_canonical_points`, line 661) rebuilt `CanonicalDecisionPoint` from a fixed subset of the stored `rdf_json_ld`. The route loader dropped `aligned_conclusion_uri`, `aligned_question_uri`, `board_resolution`, `addresses_questions` and `synthesis_method`; both loaders dropped `competing_obligation_uri`, `competing_obligation_label`, `additional_obligation_uris` and `additional_obligation_labels`. Scenario: a phase 4 run from the stored rows (the Step 4 Phase 4 route and `_run_narrative` in the synthesis service, that is every run outside the in-memory `CaseSynthesizer.synthesize`). Through the route, every decision moment read `has_board_conclusion` False and `board_choice` None, so the consequence generator asked for no board rationale and showed no Board choice for the Board-resolved points either. Through both loaders, the L4 pair never reached `_extract_conflicts`: a point whose constraint slot the parser emptied (case 8 DP1 and DP5) produced no tension at all, where the base produced a mistyped one. Fix: `CanonicalDecisionPoint.from_storage` restores every stored field (the Toulmin dict stays unrestored, as before), and both loaders call it. Tests: `test_from_storage_restores_alignment_and_competition_fields`, `test_route_loader_carries_every_stored_field`, `test_service_loader_carries_every_stored_field_and_keeps_the_row_label`, `test_reloaded_points_drive_the_narrative_board_flags_and_tensions`.

2. **The grounding context read the Step 3 rows only when no committed graph existed.** `app/services/decision_point_synthesizer/strategies.py` (`_dp_grounding_context`, line 855). Scenario: a graph committed before the current Step 3 run (Step 3 rerun from the UI without a recommit, or a commit that left the temporal rows unselected), or a model echo of the extraction-time `@id` form `cases/N#Action_X` for an action outside the candidate options. `is_timeline_individual` found no category and dropped the action, the symptom L1 removes, where the base kept any `#Action_` URI. Fix: the rows are registered in every path; registration keeps the graph's category for a URI both sources know, and the source stays `committed_graph`. Test: `test_grounding_context_reads_the_stored_rows_beside_a_committed_graph`.

### Reported, not changed

3. **Unattributed rows are never the Board's.** `app/services/step4_synthesis/qc_refs.py`, `is_board_explicit` (line 107). The route-path dicts carry `number` only (`question_refs`), so a legacy row without `questionNumber` or `conclusionNumber` counts as generated: the refine prompt lists it under GENERATED ANALYSIS, `board_resolution_for` never aligns it, a point aligned to it becomes an `analytical_extension` with its board choices cleared, and the verifier returns without checking when no Board text remains. `transformation_classifier._is_generated` takes the opposite default for the same rows. The decision is documented in the code (findings B, C, E). Proposed: one default in both places; if the strict reading stands, rerun the Q&C stage for cases whose rows carry no numbers before Phase 3 runs on them.

4. **Several committed competitors.** `strategies.py`, `resolve_normative_slots` (the block after `committed = [...]`). When the primary obligation carries competesWith or prevailsOver edges to more than one obligation, the first URI in sorted order wins unless the model named one of them. Deterministic, not chosen. Proposed: prefer the competitor joined to the primary by `prevailsOver`, then the model's.

5. **Possessive openings.** `app/services/step4_synthesis/conclusion_analyzer.py`, `attributes_to_board` (line 85). "The Board's finding leaves open ..." opens with the Board and is dropped without a discussion quote, although it is the analyst's sentence about the Board. Proposed: decide whether the possessive form needs a quote; if not, exclude `the board's` from the pattern.

6. **Step 3 references with no matching Pass 2 entity are dropped.** `app/services/step4_synthesis/rich_analysis.py`, `_build_grounded_links` (line 357). The former fallback kept the Step 3 label for exactly this spelling gap (the removed comment named "Professional Obligation III.7.a."); the reference is now dropped and logged at INFO. In scope of finding E, but it reaches every case whose Step 3 labels differ from the Pass 2 labels. Proposed: keep the drop and log the count per link at WARNING, so a run with many drops is visible.

7. **No CausalChain rows, no enables links.** `app/services/narrative/timeline_constructor.py`, `_build_causal_links` (line 529). A case whose Step 3 run stored no CausalChain rows now has no enables links at all, where the base linked each action to the next stored event. This is the rule; it is noted because the older cases in the corpus may carry no chains.

### Checked and found consistent

- The production dict shapes carry what the new predicates read: the service path merges `rdf_json_ld` (questionType, conclusionType, answersQuestions, citedProvisions) with the reference keys; the route path carries `number`, `answersQuestions` and `cited_provisions`.
- `_run_qc_unified` passes the discussion to the conclusion analyzer and persists the qc_link row; the Step 4 save sites carry no slice.
- The batch pipeline commits the extraction before Step 4, so the committed graph the grounding context reads exists; finding 2 concerns the manual flows.
- `analysis_edges.build_expectations` emits the second involvesObligation and rejects a target that is not a committed Obligation.
- The stale-row gate reads the case TTL after `_commit_individuals_to_case_ontology` wrote it, and the URI minting in `analysis_individual_uri` matches the commit path (focus_id, Question_N, Conclusion_N, else the safe label).

## Test counts on the review branch

`tests/unit/test_step4_lessons_review.py`: 6 passed. The step4 lesson suites with the neighbouring synthesizer, narrative and commit golden suites: 135 passed. The whole of `tests/unit` and `tests/extraction` match the integration tip apart from the six new tests (the 25 PostgreSQL-backed tests and the untracked docs-internal script fail as before).
