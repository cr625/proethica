# Validation Study Participant Flow

The validation study is accessible at `/validation/`. Participation does not require a ProEthica account; authentication is by possession of a randomly generated participant code only. The study was conducted under IRB Protocol 2603011709.

## Recruitment Channels

Two recruitment channels were used:

| Channel | Identifier | Notes |
|---------|-----------|-------|
| Prolific (engineering-trained) | `prolific_engineering_trained` | Primary channel; participants pre-screened for engineering background via Prolific prescreening |
| Drexel students | `drexel_student` | Opportunistic channel (senior-design cohort); dormant at time of main data collection |

Prolific participants arrive via a URL carrying `prolific_pid`, `study_id`, and `session_id` query parameters. The system stashes these in the browser session for later persistence and renders the HRP-506b information sheet for the adult-population channel. Drexel participants receive the HRP-506 information sheet.

## Participant Flow

### Step 1: Consent

The landing page (`/validation/`) displays the study information sheet (HRP-506 or HRP-506b, depending on channel). The participant must check a consent acknowledgement before proceeding. On submission to `/validation/enroll`, the system:

- Generates a random 8-character participant code from an ambiguity-stripped alphabet (no `0`/`O`, `1`/`I`/`L`).
- Assigns 3–4 cases from the 23-case study pool via `case_assignment_service.assign_cases`.
- Creates a `ValidationSession` record with `consent_acknowledged_at` and `info_sheet_version` stamped.
- Stores the participant code in the browser session cookie.

For Prolific participants, a SHA-256 hash of the Prolific PID is stored on the session record for duplicate-enrollment detection. The plain PID is never persisted.

### Step 2: Orientation

After consent, participants land at `/validation/orientation`. This screen describes the per-case workflow, explains the five synthesis views, and outlines the post-cases steps. On form submission, `orientation_completed_at` is stamped and the participant is redirected to the study dashboard. Returning participants (resuming by code) skip orientation if `orientation_completed_at` is already set.

### Step 3: Study Dashboard

The study dashboard (back at `/validation/`, with the code present) shows the assigned cases, completion status for each, and overall progress. From here, the participant navigates to each assigned case.

### Step 4: Case Evaluation

Each case evaluation (`/validation/case/<id>`) proceeds through four steps controlled by the `?step=` URL parameter:

| Step (URL) | Content | Gate |
|-----------|---------|------|
| `facts` | Case facts; Discussion and Conclusions withheld | None |
| `views` | Five synthesis views (Provisions, Q&C, Decisions, Timeline, Narrative) with inline 3-item Likert ratings per view (15 items total) | None |
| `comprehension` | Three Overall utility items, including the reverse-coded attention-check item | All 15 per-view items must be rated |
| `reveal` | Board Discussion and Conclusions revealed; alignment self-rating | All 18 items must be rated |

Each of the five views presents three 7-point Likert items (1 = Strongly Disagree, 7 = Strongly Agree). The Overall section adds three additional items; `overall_surfaced_considerations` is reverse-coded when computing view means. The server enforces step gates: navigating to `comprehension` without completing per-view ratings, or to `reveal` without completing the Overall items, redirects back to the preceding step.

Evaluation data is stored in `ViewUtilityEvaluation`. The record is created on first submit and updated on subsequent submits until `completed_at` is stamped.

### Step 5: Retrospective

After all assigned cases are completed, the participant proceeds to `/validation/retrospective`. This page collects:

- A drag-and-drop ranking of the five views from most valuable (rank 1) to least valuable (rank 5). The view list is shuffled on render to prevent order bias. Rankings must be a valid 1–5 permutation (no ties) before submission is accepted.
- An open-text field for missed considerations or general feedback.

Submission is one-shot. Once `completed_at` is stamped on the `ValidationSession`, further attempts to access the retrospective form are redirected to the completion screen.

Data is stored in `RetrospectiveReflection`.

### Step 6: Completion

The completion screen at `/validation/complete` presents the outcome by channel:

- **Prolific participants**: a "Return to Prolific" button that redirects to Prolific's submission URL with the study completion code as the `cc` parameter. A manual-paste fallback is shown in case the redirect fails.
- **Drexel-channel participants**: a per-session confirmation reference code.

The completion code (`ValidationSession.completion_code`) is distinct from the participant code. It is generated at the moment of completion and is what participants submit to the crowdsourcing platform; it is not the participant's identifying code.

## Session Resume

A participant who closes the browser mid-study can return by navigating to `/validation/` and entering their participant code. The code can also be supplied as a query parameter: `/validation/?code=XXXXXXXX`. Orientation is skipped on resume if already completed. The session resumes at the study dashboard, from which the participant continues with incomplete cases.

## Data Model

| Table | Rows | Contents |
|-------|------|----------|
| `validation_sessions` | One per participant | Consent timestamp, assigned cases, completion status, channel, Prolific PID hash |
| `view_utility_evaluations` | One per participant per case | 18 Likert items, 4 comprehension responses, alignment rating |
| `retrospective_reflections` | One per participant | Five-view ranking, open-text feedback |

## Related Documentation

- [Validation Study Admin Dashboard](validation-studies.md) - Monitoring, export, and results visualizations
