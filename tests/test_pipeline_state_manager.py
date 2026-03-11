"""
Tests for PipelineStateManager -- validates the 15-substep workflow definition,
completion checks, prerequisite enforcement, and cross-validates against
PipelineStatusService (the battle-tested oracle).
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.pipeline_state_manager import (
    PipelineStateManager,
    PipelineState,
    WORKFLOW_DEFINITION,
    STEP_GROUPS,
    TaskStatus,
    CheckType,
    get_pipeline_state,
)


# --- Structural tests (no DB needed) ---

class TestWorkflowDefinition:
    """Validate the WORKFLOW_DEFINITION structure without touching the DB."""

    def test_has_15_substeps(self):
        assert len(WORKFLOW_DEFINITION) == 15

    def test_all_substep_names(self):
        expected = {
            'pass1_facts', 'pass1_discussion',
            'pass2_facts', 'pass2_discussion',
            'pass3',
            'reconcile', 'commit_extraction',
            'step4_provisions', 'step4_precedents', 'step4_qc',
            'step4_transformation', 'step4_rich_analysis',
            'step4_phase3', 'step4_phase4',
            'commit_synthesis',
        }
        assert set(WORKFLOW_DEFINITION.keys()) == expected

    def test_no_step5(self):
        assert 'step5' not in WORKFLOW_DEFINITION

    def test_every_step_has_group(self):
        for name, defn in WORKFLOW_DEFINITION.items():
            assert defn.step_group, f"{name} has no step_group"

    def test_all_groups_are_valid(self):
        for name, defn in WORKFLOW_DEFINITION.items():
            assert defn.step_group in STEP_GROUPS, (
                f"{name} has invalid step_group '{defn.step_group}'"
            )

    def test_prerequisites_reference_existing_steps(self):
        all_steps = set(WORKFLOW_DEFINITION.keys())
        for name, defn in WORKFLOW_DEFINITION.items():
            for prereq in defn.prerequisites:
                assert prereq in all_steps, (
                    f"{name} has prerequisite '{prereq}' which doesn't exist"
                )

    def test_no_circular_prerequisites(self):
        """Verify the prerequisite graph is a DAG (no cycles)."""
        visited = set()
        path = set()

        def visit(step_name):
            if step_name in path:
                raise AssertionError(f"Cycle detected involving {step_name}")
            if step_name in visited:
                return
            path.add(step_name)
            defn = WORKFLOW_DEFINITION.get(step_name)
            if defn:
                for prereq in defn.prerequisites:
                    visit(prereq)
            path.discard(step_name)
            visited.add(step_name)

        for name in WORKFLOW_DEFINITION:
            visit(name)

    def test_pass1_facts_has_no_prerequisites(self):
        assert WORKFLOW_DEFINITION['pass1_facts'].prerequisites == []

    def test_pass1_discussion_requires_facts(self):
        assert 'pass1_facts' in WORKFLOW_DEFINITION['pass1_discussion'].prerequisites

    def test_step4_provisions_requires_commit(self):
        assert 'commit_extraction' in WORKFLOW_DEFINITION['step4_provisions'].prerequisites

    def test_commit_synthesis_requires_phase4(self):
        assert 'step4_phase4' in WORKFLOW_DEFINITION['commit_synthesis'].prerequisites

    def test_section_type_on_pass1_pass2(self):
        assert WORKFLOW_DEFINITION['pass1_facts'].section_type == 'facts'
        assert WORKFLOW_DEFINITION['pass1_discussion'].section_type == 'discussion'
        assert WORKFLOW_DEFINITION['pass2_facts'].section_type == 'facts'
        assert WORKFLOW_DEFINITION['pass2_discussion'].section_type == 'discussion'

    def test_no_section_type_on_other_steps(self):
        no_section_steps = [
            'pass3', 'reconcile', 'commit_extraction',
            'step4_provisions', 'step4_precedents', 'step4_qc',
            'step4_transformation', 'step4_rich_analysis',
            'step4_phase3', 'step4_phase4', 'commit_synthesis',
        ]
        for name in no_section_steps:
            assert WORKFLOW_DEFINITION[name].section_type is None, (
                f"{name} should have no section_type"
            )

    def test_reconcile_uses_reconciliation_check(self):
        assert WORKFLOW_DEFINITION['reconcile'].check_type == CheckType.RECONCILIATION_RUN

    def test_commit_extraction_uses_published_check(self):
        assert WORKFLOW_DEFINITION['commit_extraction'].check_type == CheckType.PUBLISHED_ENTITIES

    def test_commit_synthesis_uses_published_check(self):
        assert WORKFLOW_DEFINITION['commit_synthesis'].check_type == CheckType.PUBLISHED_ENTITIES

    def test_narrative_uses_prompts_check(self):
        assert WORKFLOW_DEFINITION['step4_phase4'].check_type == CheckType.EXTRACTION_PROMPTS

    def test_transformation_uses_prompts_check(self):
        assert WORKFLOW_DEFINITION['step4_transformation'].check_type == CheckType.EXTRACTION_PROMPTS

    def test_commit_synthesis_has_published_types(self):
        defn = WORKFLOW_DEFINITION['commit_synthesis']
        assert defn.published_types is not None
        assert 'code_provision_reference' in defn.published_types
        assert 'canonical_decision_point' in defn.published_types


class TestPipelineStateAPI:
    """Test PipelineState convenience methods with mocked manager."""

    def setup_method(self):
        self.manager = MagicMock(spec=PipelineStateManager)
        self.state = PipelineState(case_id=7, _manager=self.manager)

    def test_is_complete_step_only(self):
        self.manager.check_step_complete.return_value = True
        assert self.state.is_complete('pass1_facts') is True
        self.manager.check_step_complete.assert_called_once_with(7, 'pass1_facts')

    def test_is_complete_step_and_task(self):
        self.manager.check_task_complete.return_value = False
        assert self.state.is_complete('pass1_facts', 'roles') is False
        self.manager.check_task_complete.assert_called_once_with(7, 'pass1_facts', 'roles')

    def test_can_start(self):
        self.manager.check_prerequisites_met.return_value = (True, [])
        assert self.state.can_start('step4_qc') is True

    def test_get_blockers(self):
        self.manager.check_prerequisites_met.return_value = (
            False, ['Provisions not complete']
        )
        blockers = self.state.get_blockers('step4_qc')
        assert blockers == ['Provisions not complete']


class TestToDict:
    """Test to_dict output structure with mocked DB."""

    def setup_method(self):
        self.manager = MagicMock(spec=PipelineStateManager)
        self.manager.get_artifact_counts.return_value = {}
        self.manager.check_prerequisites_met.return_value = (False, ['test blocker'])
        self.manager.check_task_complete.return_value = False
        self.manager.check_step_complete.return_value = False
        self.manager.get_step_status.return_value = TaskStatus.NOT_STARTED
        self.manager.get_step_progress.return_value = {
            'step': 'test', 'display_name': 'Test',
            'tasks_complete': 0, 'tasks_total': 1,
            'percentage': 0, 'status': 'not_started',
        }
        self.state = PipelineState(case_id=999, _manager=self.manager)

    def test_to_dict_has_required_keys(self):
        d = self.state.to_dict()
        assert 'case_id' in d
        assert 'steps' in d
        assert 'step_groups' in d

    def test_to_dict_has_15_steps(self):
        d = self.state.to_dict()
        assert len(d['steps']) == 15

    def test_to_dict_step_has_required_fields(self):
        d = self.state.to_dict()
        step = d['steps']['pass1_facts']
        required = {'name', 'display_name', 'step_group', 'status',
                     'can_start', 'blockers', 'progress', 'tasks'}
        assert required.issubset(step.keys())

    def test_to_dict_task_has_artifact_counts(self):
        self.manager.get_artifact_counts.return_value = {'roles': 15}
        d = self.state.to_dict()
        roles_task = d['steps']['pass1_facts']['tasks']['roles']
        assert 'artifact_counts' in roles_task
        assert roles_task['artifact_counts']['roles'] == 15


# --- Integration tests (require DB) ---

@pytest.fixture
def app_context(app):
    """Provide Flask app context for DB-dependent tests."""
    with app.app_context():
        yield


class TestPSMvsPSSAgreement:
    """Cross-validate PipelineStateManager against PipelineStatusService.

    These tests require a running database with extracted cases.
    They compare PSM output against the battle-tested PSS for known cases.
    """

    @pytest.fixture(autouse=True)
    def setup(self, app_context):
        self.manager = PipelineStateManager()

    def _get_both(self, case_id):
        """Get state from both PSM and PSS for comparison."""
        from app.services.pipeline_status_service import PipelineStatusService
        psm_state = self.manager.get_pipeline_state(case_id)
        pss_status = PipelineStatusService.get_step_status(case_id)
        return psm_state, pss_status

    def _has_extraction(self, case_id):
        """Check if case has any extracted entities."""
        from sqlalchemy import text
        from app import db
        result = db.session.execute(text(
            "SELECT COUNT(*) FROM temporary_rdf_storage WHERE case_id = :cid"
        ), {'cid': case_id}).scalar()
        return result > 0

    def test_step1_facts_agreement(self):
        """PSM pass1_facts matches PSS step1.facts_complete."""
        psm, pss = self._get_both(7)
        assert psm.is_complete('pass1_facts') == pss['step1']['facts_complete']

    def test_step1_discussion_agreement(self):
        """PSM pass1_discussion matches PSS step1.discussion_complete."""
        psm, pss = self._get_both(7)
        assert psm.is_complete('pass1_discussion') == pss['step1']['discussion_complete']

    def test_step2_facts_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('pass2_facts') == pss['step2']['facts_complete']

    def test_step2_discussion_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('pass2_discussion') == pss['step2']['discussion_complete']

    def test_step3_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('pass3') == pss['step3']['complete']

    def test_reconcile_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('reconcile') == pss['reconcile']['complete']

    def test_commit_extraction_agreement(self):
        """PSM commit_extraction matches PSS reconcile.committed."""
        psm, pss = self._get_both(7)
        assert psm.is_complete('commit_extraction') == pss['reconcile']['committed']

    def test_phase2_complete_agreement(self):
        """PSS phase2_complete requires both transformation AND rich_analysis."""
        psm, pss = self._get_both(7)
        psm_phase2 = (
            psm.is_complete('step4_transformation')
            and psm.is_complete('step4_rich_analysis')
        )
        assert psm_phase2 == pss['step4']['phase2_complete']

    def test_phase3_complete_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('step4_phase3') == pss['step4']['phase3_complete']

    def test_phase4_complete_agreement(self):
        psm, pss = self._get_both(7)
        assert psm.is_complete('step4_phase4') == pss['step4']['phase4_complete']

    def test_empty_case_all_not_started(self):
        """A case with no extraction should show all steps as not_started."""
        state = self.manager.get_pipeline_state(99999)
        d = state.to_dict()
        for step_name, info in d['steps'].items():
            assert info['status'] == 'not_started', (
                f"{step_name} should be not_started for empty case"
            )

    def test_empty_case_only_pass1_facts_startable(self):
        state = self.manager.get_pipeline_state(99999)
        d = state.to_dict()
        assert d['steps']['pass1_facts']['can_start'] is True
        for step_name, info in d['steps'].items():
            if step_name != 'pass1_facts':
                assert info['can_start'] is False, (
                    f"{step_name} should not be startable for empty case"
                )


class TestCheckStep4Complete:
    """Test the convenience method for checking all Step 4 substeps."""

    @pytest.fixture(autouse=True)
    def setup(self, app_context):
        self.manager = PipelineStateManager()

    def test_empty_case_step4_not_complete(self):
        assert self.manager.check_step4_complete(99999) is False
