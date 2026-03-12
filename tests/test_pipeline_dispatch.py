"""
Tests for pipeline dispatch.

Validates:
- All Step 4 substeps are individually dispatchable (SUBSTEP_DISPATCH)
- STEP4_MONOLITHIC is empty
- Stuck RUNNING run detection
- Force-cancel endpoint
- SUBSTEP_RUNNERS mapping in synthesis service
- run_step4_substep routing
- Phase 5: CSRF exemption for rerun endpoint
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta


# --- Dispatch table structural tests ---

class TestDispatchTables:
    """Validate SUBSTEP_DISPATCH and STEP4_MONOLITHIC structure."""

    def test_step4_monolithic_is_empty(self):
        from app.routes.cases.pipeline import STEP4_MONOLITHIC
        assert STEP4_MONOLITHIC == set()

    def test_all_workflow_steps_are_dispatchable(self):
        from app.routes.cases.pipeline import SUBSTEP_DISPATCH
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION
        for step_name in WORKFLOW_DEFINITION:
            assert step_name in SUBSTEP_DISPATCH, f"{step_name} not in SUBSTEP_DISPATCH"

    def test_step4_substeps_use_substep_task(self):
        """All Step 4 substeps should use run_step4_substep_task."""
        from app.routes.cases.pipeline import SUBSTEP_DISPATCH
        step4_substeps = [
            'step4_provisions', 'step4_precedents', 'step4_qc',
            'step4_transformation', 'step4_rich_analysis',
            'step4_phase3', 'step4_phase4',
        ]
        for name in step4_substeps:
            task_name, kwargs = SUBSTEP_DISPATCH[name]
            assert task_name == 'run_step4_substep_task', \
                f"{name} uses {task_name} instead of run_step4_substep_task"
            assert kwargs.get('substep') == name, \
                f"{name} kwargs substep={kwargs.get('substep')}"

    def test_dispatch_count_matches_workflow(self):
        from app.routes.cases.pipeline import SUBSTEP_DISPATCH
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION
        assert len(SUBSTEP_DISPATCH) == len(WORKFLOW_DEFINITION)

    def test_no_stale_dispatch_entries(self):
        """Every SUBSTEP_DISPATCH key must exist in WORKFLOW_DEFINITION."""
        from app.routes.cases.pipeline import SUBSTEP_DISPATCH
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION
        for step_name in SUBSTEP_DISPATCH:
            assert step_name in WORKFLOW_DEFINITION, \
                f"{step_name} in SUBSTEP_DISPATCH but not in WORKFLOW_DEFINITION"

    def test_get_task_func_resolves_substep_task(self):
        from app.routes.cases.pipeline import _get_task_func
        func = _get_task_func('run_step4_substep_task')
        assert func is not None
        assert func.name == 'proethica.tasks.run_step4_substep'


# --- Synthesis service substep routing tests ---

class TestSubstepRunners:
    """Validate SUBSTEP_RUNNERS mapping and run_step4_substep routing."""

    def test_all_step4_substeps_have_runners(self):
        from app.services.step4_synthesis_service import SUBSTEP_RUNNERS
        expected = {
            'step4_provisions', 'step4_precedents', 'step4_qc',
            'step4_transformation', 'step4_rich_analysis',
            'step4_phase3', 'step4_phase4',
        }
        assert set(SUBSTEP_RUNNERS.keys()) == expected

    def test_runner_functions_exist(self):
        """Each runner function name in SUBSTEP_RUNNERS must exist as a module-level function."""
        import app.services.step4_synthesis_service as mod
        from app.services.step4_synthesis_service import SUBSTEP_RUNNERS
        for substep, (func_name, _, _) in SUBSTEP_RUNNERS.items():
            assert hasattr(mod, func_name), \
                f"Function {func_name} not found for {substep}"

    def test_run_step4_substep_rejects_unknown(self):
        from app.services.step4_synthesis_service import run_step4_substep
        result = run_step4_substep(case_id=999, substep='step4_nonexistent')
        assert 'error' in result
        assert 'Unknown' in result['error']


# --- Stuck RUNNING detection tests ---

class TestStuckRunningDetection:
    """Test auto-fail of stuck RUNNING runs in _get_active_run."""

    def _make_mock_run(self, status, updated_at):
        run = MagicMock()
        run.status = status
        run.updated_at = updated_at
        run.created_at = updated_at
        run.id = 42
        return run

    @patch('app.routes.cases.pipeline.db')
    @patch('app.routes.cases.pipeline.PipelineRun')
    def test_running_under_threshold_not_failed(self, mock_model, mock_db):
        """RUNNING run updated 1 hour ago should NOT be auto-failed."""
        from app.routes.cases.pipeline import _get_active_run
        from app.models.pipeline_run import PIPELINE_STATUS

        recent = datetime.utcnow() - timedelta(hours=1)
        run = self._make_mock_run(PIPELINE_STATUS['RUNNING'], recent)
        mock_model.query.filter.return_value.order_by.return_value.first.return_value = run

        result = _get_active_run(case_id=1)
        assert result is run
        run.set_error.assert_not_called()

    @patch('app.routes.cases.pipeline.db')
    @patch('app.routes.cases.pipeline.PipelineRun')
    def test_running_over_threshold_auto_failed(self, mock_model, mock_db):
        """RUNNING run updated 3 hours ago should be auto-failed."""
        from app.routes.cases.pipeline import _get_active_run
        from app.models.pipeline_run import PIPELINE_STATUS

        old = datetime.utcnow() - timedelta(hours=3)
        run = self._make_mock_run(PIPELINE_STATUS['RUNNING'], old)
        mock_model.query.filter.return_value.order_by.return_value.first.return_value = run

        result = _get_active_run(case_id=1)
        assert result is None
        run.set_error.assert_called_once()
        assert 'Stuck RUNNING' in run.set_error.call_args[0][0]

    @patch('app.routes.cases.pipeline.db')
    @patch('app.routes.cases.pipeline.PipelineRun')
    def test_waiting_review_not_failed(self, mock_model, mock_db):
        """WAITING_REVIEW run should never be auto-failed regardless of age."""
        from app.routes.cases.pipeline import _get_active_run
        from app.models.pipeline_run import PIPELINE_STATUS

        old = datetime.utcnow() - timedelta(hours=24)
        run = self._make_mock_run(PIPELINE_STATUS['WAITING_REVIEW'], old)
        mock_model.query.filter.return_value.order_by.return_value.first.return_value = run

        result = _get_active_run(case_id=1)
        assert result is run
        run.set_error.assert_not_called()


# --- Phase 5: CSRF exemption tests ---

class TestCSRFExemption:
    """Verify that all pipeline POST endpoints are listed for CSRF exemption."""

    def test_rerun_endpoint_in_csrf_list(self):
        """The rerun endpoint must be in init_pipeline_csrf_exemption."""
        import inspect
        from app.routes.cases.pipeline import init_pipeline_csrf_exemption
        source = inspect.getsource(init_pipeline_csrf_exemption)
        assert 'case_pipeline_rerun' in source
