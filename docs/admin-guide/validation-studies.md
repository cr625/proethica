# Validation Study Admin Dashboard

The validation study admin dashboard at `/validation/admin/dashboard` provides operational monitoring and data export for the view-utility study conducted under IRB Protocol 2603011709. Admin authentication is required in production.

The study collected perceived-utility ratings for five synthesis views (Provisions, Q&C, Decisions, Timeline, Narrative) from engineering-trained participants. Data collection was conducted via Prolific. The dashboard filters to verified recruitment sources by default; preview and Drexel-student dormant-channel sessions are excluded from dashboard aggregations but remain accessible via the export endpoint.

## Dashboard Sections

### Enrollment Statistics

Four summary cards at the top of the page display:

| Metric | Description |
|--------|-------------|
| Enrolled | Total participants from real recruitment channels |
| Completed | Participants who submitted the retrospective reflection |
| In Progress | Enrolled but not yet finished |
| Total Evaluations | Completed per-case rating forms across all participants |

### Case Coverage

A table lists all 23 cases in the study pool with the count of distinct raters per case. Cases meeting or exceeding the Krippendorff floor of n=5 raters are marked as threshold-met; cases below the floor are listed in a separate under-threshold section. This view is the primary tool for monitoring whether each case has received sufficient coverage for inter-rater reliability analysis.

### Data Quality Flags

Two quality indicators are shown:

| Flag | Derivation |
|------|------------|
| Attention check pass rate | Percentage of evaluations where `overall_surfaced_considerations` (a reverse-coded item) was answered as 1 |
| Low-effort flags | Count of evaluations where `low_effort_flag` is set |

### Recent Sessions

A table of the ten most recent enrolled sessions from real recruitment channels, ordered by enrollment time descending. Columns include participant code (truncated), source channel, progress, and completion status.

### Results Visualizations

The bottom section aggregates collected data into three views:

**Per-view mean utility scores.** For each of the five views and the Overall row, the dashboard reports the mean, standard deviation, and rater count across all completed evaluations. Scores are on the 1–7 Likert scale; `overall_surfaced_considerations` is reverse-coded before the mean is computed.

**Retrospective view rankings.** A stacked count showing, for each view, how many participants assigned it each rank from 1 (most valuable) to 5 (least). Data source: `RetrospectiveReflection.rank_*_view` columns.

**Per-case means.** Mean overall utility score per case, sorted descending, restricted to cases with at least one completed evaluation from a real channel.

## Admin Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/validation/admin/dashboard` | GET | Dashboard described above |
| `/validation/admin/export` | GET | Download per-item or per-view-mean data |
| `/validation/admin/summary` | GET | JSON comparison summary |
| `/validation/admin/evaluator-progress` | GET | JSON per-evaluator progress |

### Export Parameters

`/validation/admin/export` accepts the following query parameters:

| Parameter | Default | Values |
|-----------|---------|--------|
| `format` | `csv` | `csv`, `json` |
| `domain` | `engineering` | `engineering`, `all` |
| `level` | `means` | `means` (per-view averages), `items` (per-item rows for Krippendorff) |

`level=items` returns one row per evaluator per case with all 18 individual Likert responses. `level=means` returns per-view aggregated means and is the default for general inspection.

## Access Control

All admin endpoints are protected by `@admin_required_production`. In development mode, the restriction is relaxed. See [Settings](settings.md#security-settings) for authentication configuration.

## Related Documentation

- [Validation Participant Flow](validation-participant-flow.md) - Participant experience and data model
- [Service Health](health-dashboard.md) - Operational monitoring
- [Settings](settings.md) - Environment configuration
