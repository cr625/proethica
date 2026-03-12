"""Tests for bulk pipeline progress (Phase 6a)."""

import pytest
from unittest.mock import patch, MagicMock
from app.services.pipeline_state_manager import (
    get_bulk_progress,
    _check_substep_bulk,
    WORKFLOW_DEFINITION,
    CheckType,
)

# Patch targets: db and PipelineRun are imported locally inside get_bulk_progress
DB_PATCH = 'app.db'
RUN_PATCH = 'app.models.pipeline_run.PipelineRun'


def _mock_execute_sequence(mock_db, *query_results):
    """Set up mock_db to return sequential query results."""
    call_count = [0]

    def side_effect(*args, **kwargs):
        mock_result = MagicMock()
        idx = min(call_count[0], len(query_results) - 1)
        mock_result.fetchall.return_value = query_results[idx]
        call_count[0] += 1
        return mock_result

    mock_db.session.execute.side_effect = side_effect


class TestGetBulkProgress:
    """Tests for the get_bulk_progress function."""

    def test_empty_case_ids_returns_empty(self):
        """Empty input returns empty dict without querying."""
        result = get_bulk_progress([])
        assert result == {}

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_returns_expected_keys(self, mock_db, mock_run_cls):
        """Each entry has the required keys."""
        mock_db.session.execute.return_value.fetchall.return_value = []
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([1, 2])

        for case_id in [1, 2]:
            assert case_id in result
            entry = result[case_id]
            assert 'complete' in entry
            assert 'total' in entry
            assert 'pct' in entry
            assert 'status' in entry
            assert 'active_run' in entry

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_total_is_always_15(self, mock_db, mock_run_cls):
        """Total substeps should always be 15 (matching WORKFLOW_DEFINITION)."""
        mock_db.session.execute.return_value.fetchall.return_value = []
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([42])
        assert result[42]['total'] == 15
        assert result[42]['total'] == len(WORKFLOW_DEFINITION)

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_no_artifacts_gives_not_started(self, mock_db, mock_run_cls):
        """Case with no data should be 'not_started' with 0 complete."""
        mock_db.session.execute.return_value.fetchall.return_value = []
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([10])
        assert result[10]['status'] == 'not_started'
        assert result[10]['complete'] == 0
        assert result[10]['pct'] == 0
        assert result[10]['active_run'] is None

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_some_artifacts_gives_extracted(self, mock_db, mock_run_cls):
        """Case with extraction artifacts but no phase4 prompts -> 'extracted'."""
        _mock_execute_sequence(
            mock_db,
            # Query 1: artifact counts
            [(5, 'roles', 10), (5, 'states', 4), (5, 'resources', 6)],
            # Query 2: section prompts
            [(5, 'roles', 'facts'), (5, 'states', 'facts'), (5, 'resources', 'facts')],
            # Query 3: reconciliation
            [],
            # Query 4: published
            [],
        )
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([5])
        assert result[5]['status'] == 'extracted'
        assert result[5]['complete'] >= 1

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_phase4_prompts_gives_synthesized(self, mock_db, mock_run_cls):
        """Case with phase4 prompts -> 'synthesized'."""
        _mock_execute_sequence(
            mock_db,
            [(7, 'roles', 5)],
            [(7, 'roles', 'facts'), (7, 'phase4_narrative', None)],
            [],
            [],
        )
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([7])
        assert result[7]['status'] == 'synthesized'

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_active_run_overlay(self, mock_db, mock_run_cls):
        """Active PipelineRun appears in the progress dict."""
        mock_db.session.execute.return_value.fetchall.return_value = []

        mock_run = MagicMock()
        mock_run.case_id = 3
        mock_run.id = 99
        mock_run.status = 'running'
        mock_run.current_step = 'step4_qc'
        mock_run.created_at = None
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = [mock_run]

        result = get_bulk_progress([3])
        assert result[3]['active_run'] is not None
        assert result[3]['active_run']['id'] == 99
        assert result[3]['active_run']['status'] == 'running'
        assert result[3]['active_run']['current_step'] == 'step4_qc'
        assert result[3]['active_run']['current_step_display'] == 'Questions & Conclusions'

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_db_error_returns_defaults(self, mock_db, mock_run_cls):
        """Database error returns default entries for all case_ids."""
        mock_db.session.execute.side_effect = Exception("connection lost")

        result = get_bulk_progress([1, 2])
        assert len(result) == 2
        for cid in [1, 2]:
            assert result[cid]['complete'] == 0
            assert result[cid]['total'] == 15
            assert result[cid]['status'] == 'not_started'

    @patch(RUN_PATCH)
    @patch(DB_PATCH)
    def test_multiple_cases_independent(self, mock_db, mock_run_cls):
        """Different cases get independent progress counts."""
        _mock_execute_sequence(
            mock_db,
            # Query 1: only case 1 has artifacts
            [(1, 'roles', 5), (1, 'states', 3), (1, 'resources', 2)],
            # Query 2: only case 1 has section prompts
            [(1, 'roles', 'facts'), (1, 'states', 'facts'), (1, 'resources', 'facts')],
            [],
            [],
        )
        mock_run_cls.query.filter.return_value.order_by.return_value.all.return_value = []

        result = get_bulk_progress([1, 2])
        assert result[1]['complete'] > result[2]['complete']
        assert result[2]['complete'] == 0


class TestCheckSubstepBulk:
    """Tests for the _check_substep_bulk helper."""

    def test_artifacts_check_complete(self):
        """Substep with all artifact types present is complete."""
        step_def = WORKFLOW_DEFINITION['pass3']
        artifacts = {'temporal_dynamics_enhanced': 10}
        assert _check_substep_bulk(step_def, artifacts, {}, False, set()) is True

    def test_artifacts_check_missing(self):
        """Substep with missing artifact types is not complete."""
        step_def = WORKFLOW_DEFINITION['pass3']
        assert _check_substep_bulk(step_def, {}, {}, False, set()) is False

    def test_section_aware_facts(self):
        """Section-aware substep requires matching section_type in prompts."""
        step_def = WORKFLOW_DEFINITION['pass1_facts']
        artifacts = {'roles': 5, 'states': 3, 'resources': 2}

        # Without section prompts -> not complete
        assert _check_substep_bulk(step_def, artifacts, {}, False, set()) is False

        # With facts section prompts -> complete
        prompts = {
            'roles': {'facts'},
            'states': {'facts'},
            'resources': {'facts'},
        }
        assert _check_substep_bulk(step_def, artifacts, prompts, False, set()) is True

    def test_section_aware_discussion(self):
        """Discussion substep requires 'discussion' section type."""
        step_def = WORKFLOW_DEFINITION['pass1_discussion']
        artifacts = {'roles': 5, 'states': 3, 'resources': 2}

        # Only facts prompts -> discussion not complete
        prompts_facts = {'roles': {'facts'}, 'states': {'facts'}, 'resources': {'facts'}}
        assert _check_substep_bulk(step_def, artifacts, prompts_facts, False, set()) is False

        # With discussion prompts -> complete
        prompts_both = {
            'roles': {'facts', 'discussion'},
            'states': {'facts', 'discussion'},
            'resources': {'facts', 'discussion'},
        }
        assert _check_substep_bulk(step_def, artifacts, prompts_both, False, set()) is True

    def test_reconciliation_check(self):
        """Reconciliation substep checks reconciliation_run OR published."""
        step_def = WORKFLOW_DEFINITION['reconcile']

        assert _check_substep_bulk(step_def, {}, {}, False, set()) is False
        assert _check_substep_bulk(step_def, {}, {}, True, set()) is True
        assert _check_substep_bulk(step_def, {}, {}, False, {'roles'}) is True

    def test_published_entities_check(self):
        """Published entities substep checks is_published flag."""
        step_def = WORKFLOW_DEFINITION['commit_extraction']

        assert _check_substep_bulk(step_def, {}, {}, False, set()) is False
        assert _check_substep_bulk(step_def, {}, {}, False, {'roles'}) is True

    def test_published_with_specific_types(self):
        """commit_synthesis checks specific published types."""
        step_def = WORKFLOW_DEFINITION['commit_synthesis']

        # Wrong type published -> not complete
        assert _check_substep_bulk(step_def, {}, {}, False, {'roles'}) is False

        # Right type published -> complete
        assert _check_substep_bulk(
            step_def, {}, {}, False, {'code_provision_reference'}
        ) is True

    def test_extraction_prompts_check(self):
        """Prompt-based substeps check extraction_prompts existence."""
        step_def = WORKFLOW_DEFINITION['step4_transformation']

        assert _check_substep_bulk(step_def, {}, {}, False, set()) is False

        prompts = {'transformation_classification': {None}}
        assert _check_substep_bulk(step_def, {}, prompts, False, set()) is True

    def test_phase4_like_pattern(self):
        """step4_phase4 uses startswith('phase4') check."""
        step_def = WORKFLOW_DEFINITION['step4_phase4']

        assert _check_substep_bulk(step_def, {}, {}, False, set()) is False

        prompts = {'phase4_narrative': {None}}
        assert _check_substep_bulk(step_def, {}, prompts, False, set()) is True

        prompts2 = {'phase4_temporal_dynamics': {None}}
        assert _check_substep_bulk(step_def, {}, prompts2, False, set()) is True

    def test_multi_task_substep_all_required(self):
        """Substep with multiple tasks requires ALL tasks complete."""
        step_def = WORKFLOW_DEFINITION['step4_qc']

        # Only ethical_question -> not complete (missing ethical_conclusion)
        artifacts = {'ethical_question': 5}
        assert _check_substep_bulk(step_def, artifacts, {}, False, set()) is False

        # Both present -> complete
        artifacts = {'ethical_question': 5, 'ethical_conclusion': 3}
        assert _check_substep_bulk(step_def, artifacts, {}, False, set()) is True
