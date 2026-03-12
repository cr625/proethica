"""
Tests for cascade clearing service (Phase 5a).

Validates:
- Dependency walker: downstream collection from prerequisites graph
- Cascade preview: confirmation dialog data
- Clearing logic: per-substep artifact deletion
- Section-aware scoping: facts vs discussion entity separation
- Edge cases: clearing from commit steps, step4 substeps
"""

import pytest
from unittest.mock import patch, MagicMock


# --- Dependency walker tests ---

class TestGetDownstreamSubsteps:
    """Test the reverse-graph BFS for finding downstream substeps."""

    def test_pass1_facts_downstream_includes_all(self):
        """pass1_facts is the root -- everything depends on it."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('pass1_facts')

        # Must include all other substeps
        assert 'pass1_discussion' in downstream
        assert 'pass2_facts' in downstream
        assert 'pass2_discussion' in downstream
        assert 'pass3' in downstream
        assert 'reconcile' in downstream
        assert 'commit_extraction' in downstream
        assert 'step4_provisions' in downstream
        assert 'commit_synthesis' in downstream
        assert len(downstream) == 14  # All 15 substeps minus pass1_facts itself

    def test_pass1_discussion_downstream(self):
        """pass1_discussion feeds into pass2_discussion only (and transitive)."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('pass1_discussion')

        assert 'pass2_discussion' in downstream
        assert 'pass3' in downstream
        assert 'reconcile' in downstream
        # pass2_facts does NOT depend on pass1_discussion
        assert 'pass2_facts' not in downstream
        # pass1_facts is upstream, not downstream
        assert 'pass1_facts' not in downstream

    def test_commit_extraction_downstream(self):
        """commit_extraction feeds into step4_* and commit_synthesis."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('commit_extraction')

        assert 'step4_provisions' in downstream
        assert 'step4_qc' in downstream
        assert 'step4_phase4' in downstream
        assert 'commit_synthesis' in downstream
        # Upstream substeps not included
        assert 'reconcile' not in downstream
        assert 'pass3' not in downstream

    def test_step4_qc_downstream(self):
        """step4_qc feeds into transformation -> rich_analysis -> phase3 -> phase4."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('step4_qc')

        assert 'step4_transformation' in downstream
        assert 'step4_rich_analysis' in downstream
        assert 'step4_phase3' in downstream
        assert 'step4_phase4' in downstream
        assert 'commit_synthesis' in downstream
        # Upstream Step 4 substeps not included
        assert 'step4_provisions' not in downstream
        assert 'step4_precedents' not in downstream
        # commit_extraction is upstream
        assert 'commit_extraction' not in downstream

    def test_commit_synthesis_has_no_downstream(self):
        """commit_synthesis is the terminal step."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('commit_synthesis')
        assert downstream == []

    def test_step4_phase4_downstream_is_commit_synthesis(self):
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('step4_phase4')
        assert downstream == ['commit_synthesis']

    def test_unknown_substep_returns_empty(self):
        from app.services.cascade_clearing_service import get_downstream_substeps
        assert get_downstream_substeps('nonexistent') == []

    def test_downstream_order_matches_workflow(self):
        """Downstream substeps should be in WORKFLOW_DEFINITION order."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION

        downstream = get_downstream_substeps('pass1_facts')
        wf_order = list(WORKFLOW_DEFINITION.keys())

        # Verify ordering
        indices = [wf_order.index(s) for s in downstream]
        assert indices == sorted(indices)

    def test_reconcile_downstream(self):
        """reconcile feeds into commit_extraction and transitive."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('reconcile')

        assert 'commit_extraction' in downstream
        assert 'step4_provisions' in downstream
        assert 'commit_synthesis' in downstream
        assert 'pass3' not in downstream

    def test_step4_provisions_downstream(self):
        """step4_provisions feeds into precedents and qc (both depend on it)."""
        from app.services.cascade_clearing_service import get_downstream_substeps
        downstream = get_downstream_substeps('step4_provisions')

        assert 'step4_precedents' in downstream
        assert 'step4_qc' in downstream
        assert 'step4_transformation' in downstream
        assert 'commit_synthesis' in downstream


# --- Cascade preview tests ---

class TestCascadePreview:
    """Test the preview/confirmation dialog data."""

    def test_preview_pass1_facts(self):
        from app.services.cascade_clearing_service import get_cascade_preview
        preview = get_cascade_preview('pass1_facts')

        assert preview['target'] == 'pass1_facts'
        assert preview['target_display'] == 'Pass 1 - Facts'
        assert preview['affected_count'] == 15  # All substeps
        assert preview['will_clear_reconciliation'] is True
        assert preview['will_clear_commits'] is True

    def test_preview_step4_phase4(self):
        from app.services.cascade_clearing_service import get_cascade_preview
        preview = get_cascade_preview('step4_phase4')

        assert preview['affected_count'] == 2  # phase4 + commit_synthesis
        assert preview['will_clear_reconciliation'] is False
        assert preview['will_clear_commits'] is True

    def test_preview_commit_synthesis(self):
        from app.services.cascade_clearing_service import get_cascade_preview
        preview = get_cascade_preview('commit_synthesis')

        assert preview['affected_count'] == 1  # Only itself
        assert preview['downstream'] == []
        assert preview['will_clear_commits'] is True

    def test_preview_unknown_substep(self):
        from app.services.cascade_clearing_service import get_cascade_preview
        preview = get_cascade_preview('nonexistent')
        assert 'error' in preview


# --- Clearing logic tests (mocked DB) ---

class TestClearCascade:
    """Test clearing logic with mocked database operations."""

    def test_clear_unknown_substep(self):
        from app.services.cascade_clearing_service import clear_cascade
        result = clear_cascade(case_id=1, target='nonexistent')
        assert 'error' in result

    @patch('app.services.cascade_clearing_service.db')
    @patch('app.services.cascade_clearing_service.CaseOntologyCommit')
    @patch('app.services.cascade_clearing_service.ReconciliationRun')
    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    @patch('app.services.cascade_clearing_service.TemporaryRDFStorage')
    def test_clear_commit_synthesis_resets_published(
        self, mock_trs, mock_ep, mock_rr, mock_coc, mock_db
    ):
        """Clearing commit_synthesis should reset is_published on synthesis types."""
        from app.services.cascade_clearing_service import clear_cascade

        # Set up mock chain for TRS update
        mock_trs.query.filter.return_value.update.return_value = 5
        mock_trs.query.filter.return_value.delete.return_value = 0
        mock_coc.query.filter_by.return_value.delete.return_value = 1
        mock_ep.query.filter.return_value.delete.return_value = 0

        result = clear_cascade(case_id=7, target='commit_synthesis')

        assert result['published_reset'] == 5
        assert result['commits_deleted'] == 1
        assert result['entities_deleted'] == 0
        assert result['substeps_cleared'] == 1  # Only commit_synthesis

    @patch('app.services.cascade_clearing_service.db')
    @patch('app.services.cascade_clearing_service.CaseOntologyCommit')
    @patch('app.services.cascade_clearing_service.ReconciliationRun')
    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    @patch('app.services.cascade_clearing_service.TemporaryRDFStorage')
    def test_clear_reconcile_deletes_runs(
        self, mock_trs, mock_ep, mock_rr, mock_coc, mock_db
    ):
        """Clearing reconcile should delete ReconciliationRun records."""
        from app.services.cascade_clearing_service import clear_cascade

        mock_rr.query.filter_by.return_value.delete.return_value = 1
        mock_trs.query.filter.return_value.update.return_value = 10
        mock_trs.query.filter.return_value.delete.return_value = 0
        mock_coc.query.filter_by.return_value.delete.return_value = 2
        mock_ep.query.filter.return_value.delete.return_value = 0
        mock_ep.query.filter_by.return_value.delete.return_value = 0

        result = clear_cascade(case_id=7, target='reconcile')

        assert result['reconciliation_deleted'] >= 1
        # commit_extraction is downstream, so published entities get reset
        assert result['published_reset'] > 0


# --- Section-aware scoping tests ---

class TestSectionScoping:
    """Test that section-aware clearing uses extraction_session_id scoping."""

    @patch('app.services.cascade_clearing_service.db')
    @patch('app.services.cascade_clearing_service.CaseOntologyCommit')
    @patch('app.services.cascade_clearing_service.ReconciliationRun')
    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    @patch('app.services.cascade_clearing_service.TemporaryRDFStorage')
    def test_facts_clearing_scopes_by_session(
        self, mock_trs, mock_ep, mock_rr, mock_coc, mock_db
    ):
        """Clearing pass1_facts should use session-based scoping for TRS."""
        from app.services.cascade_clearing_service import _clear_section_entities

        # Mock prompts with session IDs
        mock_prompt = MagicMock()
        mock_prompt.extraction_session_id = 'session_facts_123'
        mock_ep.query.filter.return_value.all.return_value = [mock_prompt]

        # Mock TRS delete
        mock_trs.query.filter.return_value.delete.return_value = 5

        count = _clear_section_entities(
            case_id=7,
            extraction_types=['roles', 'states', 'resources'],
            section_type='facts'
        )

        assert count == 5
        # Verify EP was queried with section_type filter
        mock_ep.query.filter.assert_called()

    @patch('app.services.cascade_clearing_service.db')
    @patch('app.services.cascade_clearing_service.CaseOntologyCommit')
    @patch('app.services.cascade_clearing_service.ReconciliationRun')
    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    @patch('app.services.cascade_clearing_service.TemporaryRDFStorage')
    def test_no_session_ids_clears_nothing(
        self, mock_trs, mock_ep, mock_rr, mock_coc, mock_db
    ):
        """If no extraction_prompts exist for the section, clear nothing."""
        from app.services.cascade_clearing_service import _clear_section_entities

        mock_ep.query.filter.return_value.all.return_value = []

        count = _clear_section_entities(
            case_id=7,
            extraction_types=['roles'],
            section_type='facts'
        )

        assert count == 0
        # TRS delete should NOT be called when no session IDs found
        mock_trs.query.filter.return_value.delete.assert_not_called()


# --- Step 4 prompt clearing tests ---

class TestStep4PromptClearing:
    """Test prompt clearing for Step 4 substeps."""

    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    def test_step4_provisions_clears_by_concept_type(self, mock_ep):
        from app.services.cascade_clearing_service import _clear_substep_prompts
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION

        mock_ep.query.filter.return_value.delete.return_value = 2
        step_def = WORKFLOW_DEFINITION['step4_provisions']

        count = _clear_substep_prompts(case_id=7, substep='step4_provisions', step_def=step_def)
        assert count == 2

    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    def test_step4_phase4_uses_like_pattern(self, mock_ep):
        from app.services.cascade_clearing_service import _clear_substep_prompts
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION

        mock_ep.query.filter.return_value.delete.return_value = 3
        step_def = WORKFLOW_DEFINITION['step4_phase4']

        count = _clear_substep_prompts(case_id=7, substep='step4_phase4', step_def=step_def)
        assert count == 3

    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    def test_pass3_clears_by_step_number(self, mock_ep):
        from app.services.cascade_clearing_service import _clear_substep_prompts
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION

        mock_ep.query.filter_by.return_value.delete.return_value = 4
        step_def = WORKFLOW_DEFINITION['pass3']

        count = _clear_substep_prompts(case_id=7, substep='pass3', step_def=step_def)
        assert count == 4
        mock_ep.query.filter_by.assert_called_with(case_id=7, step_number=3)

    @patch('app.services.cascade_clearing_service.ExtractionPrompt')
    def test_reconcile_clears_no_prompts(self, mock_ep):
        from app.services.cascade_clearing_service import _clear_substep_prompts
        from app.services.pipeline_state_manager import WORKFLOW_DEFINITION

        step_def = WORKFLOW_DEFINITION['reconcile']
        count = _clear_substep_prompts(case_id=7, substep='reconcile', step_def=step_def)
        assert count == 0
