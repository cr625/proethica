# Archived Tests

Tests in this directory are for deprecated or legacy features that are no longer part of the main application workflow.

## Archived Files

### test_scenarios_routes.py (archived 2026-01-03)
Tests for the deprecated `/scenarios/` routes. The standalone scenario feature was replaced by case-derived scenarios via `/scenario_pipeline/case/<id>/step5`.

See `app/routes/scenarios.py` deprecation notice for details.

## Restoring Tests

To restore a test file:
1. Move it back to `tests/integration/`
2. Ensure the corresponding feature is also restored
3. Run `pytest tests/integration/<file>` to verify
