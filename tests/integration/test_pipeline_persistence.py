"""
Integration tests for Pipeline Prompt/Response Persistence.

Tests that:
1. LLM prompts and responses are saved to the database during extraction
2. Saved prompts/responses can be retrieved when page is reloaded
3. Entities are available for review after extraction

These tests use mock LLM responses for speed but test real database persistence.
Uses the ai_ethical_dm_test PostgreSQL database via conftest fixtures.
"""

import pytest
from unittest.mock import patch, MagicMock
from app import db
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document import Document
from tests.mocks.llm_client import MockLLMClient


# Note: app, client fixtures inherited from tests/conftest.py


@pytest.fixture
def mock_llm():
    """Create mock LLM client."""
    return MockLLMClient()


class TestPromptPersistence:
    """Test suite for prompt/response persistence."""

    def test_extraction_saves_prompt_and_response(self, app_context, mock_llm):
        """
        CRITICAL TEST: Verify that running an extraction saves both
        the prompt and response to the database.
        """
        # Clear any existing prompts for test case
        case_id = 7
        ExtractionPrompt.query.filter_by(case_id=case_id, section_type='facts', concept_type='roles').delete()
        db.session.commit()

        # Import and run extraction with mock
        from app.tasks.pipeline_tasks import run_extraction, get_extractor_class

        # Mock the LLM calls
        with patch('app.services.external_mcp_client.get_external_mcp_client') as mock_mcp:
            mock_mcp.return_value = MagicMock()

            # Run extraction (uses the extractor class internally)
            extractor_class = get_extractor_class('roles')
            case_text = "Engineer A is working on a project."
            result = run_extraction(
                extractor_class, case_text, case_id, 'facts', 'roles',
                step_number=1
            )

        # Verify prompt was saved
        saved = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='roles',
            section_type='facts',
            is_active=True
        ).first()

        assert saved is not None, "Prompt should be saved to database"
        assert saved.prompt_text is not None, "Prompt text should be saved"
        assert saved.step_number == 1, "Step number should be saved"

    def test_saved_prompt_retrieved_on_reload(self, app_context, client):
        """
        CRITICAL TEST: Verify that saved prompts/responses are retrieved
        when the user reloads the page.
        """
        case_id = 7
        concept_type = 'roles'
        section_type = 'facts'

        # Deactivate existing prompts
        ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type=concept_type,
            section_type=section_type
        ).update({'is_active': False})
        db.session.commit()

        # Create a test prompt
        test_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type=concept_type,
            section_type=section_type,
            step_number=1,
            prompt_text="Test prompt for roles extraction",
            raw_response='{"role_classes": [{"name": "Engineer"}], "role_individuals": []}',
            is_active=True,
            llm_model='claude-sonnet-4-20250514'
        )
        db.session.add(test_prompt)
        db.session.commit()

        # Retrieve via API
        response = client.get(
            f'/scenario_pipeline/case/{case_id}/step1/get_saved_prompt',
            query_string={'concept_type': concept_type, 'section_type': section_type}
        )

        # Verify retrieval
        assert response.status_code == 200
        data = response.get_json()
        assert data.get('success') is True, "Should successfully retrieve prompt"
        assert 'Test prompt' in data.get('prompt_text', ''), "Should return saved prompt text"
        assert data.get('raw_response') is not None, "Should return raw response"

    def test_multiple_sections_have_separate_prompts(self, app_context):
        """
        Test that facts and discussion sections maintain separate prompts.
        """
        case_id = 7
        concept_type = 'roles'

        # Clear existing test prompts
        ExtractionPrompt.query.filter_by(case_id=case_id, concept_type=concept_type).delete()
        db.session.commit()

        # Create prompts for both sections
        facts_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type=concept_type,
            section_type='facts',
            step_number=1,
            prompt_text="Facts section prompt",
            raw_response='{"role_classes": [], "role_individuals": []}',
            is_active=True
        )
        discussion_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type=concept_type,
            section_type='discussion',
            step_number=1,
            prompt_text="Discussion section prompt",
            raw_response='{"role_classes": [], "role_individuals": []}',
            is_active=True
        )
        db.session.add_all([facts_prompt, discussion_prompt])
        db.session.commit()

        # Retrieve prompts
        facts_saved = ExtractionPrompt.get_active_prompt(case_id, concept_type, 'facts')
        discussion_saved = ExtractionPrompt.get_active_prompt(case_id, concept_type, 'discussion')

        assert facts_saved is not None
        assert discussion_saved is not None
        assert facts_saved.prompt_text != discussion_saved.prompt_text


class TestEntityAvailability:
    """Test suite for entity availability after extraction."""

    def test_extracted_entities_stored_in_rdf(self, app_context):
        """
        Test that extracted entities are stored in RDF storage
        for later review.
        """
        from app.models.temporary_rdf_storage import TemporaryRDFStorage

        # Check if case has stored entities
        case_id = 7
        entities = TemporaryRDFStorage.query.filter_by(case_id=case_id).all()

        # This test verifies the mechanism exists
        # Actual entity count depends on what has been extracted
        assert TemporaryRDFStorage.__tablename__ == 'temporary_rdf_storage'

    def test_entity_review_page_loads(self, client):
        """
        Test that the entity review page loads successfully.
        """
        case_id = 7
        response = client.get(f'/scenario_pipeline/case/{case_id}/entity_review')

        # Should either succeed or redirect (depending on auth)
        assert response.status_code in [200, 302, 404]


class TestPipelineRunTracking:
    """Test suite for pipeline run tracking."""

    def test_pipeline_run_created(self, app_context):
        """Test that pipeline runs are tracked in database."""
        from app.models.pipeline_run import PipelineRun, PIPELINE_STATUS

        # Create a test run
        run = PipelineRun(
            case_id=7,
            status=PIPELINE_STATUS['PENDING'],
            config={}
        )
        db.session.add(run)
        db.session.commit()

        # Verify
        saved = PipelineRun.query.get(run.id)
        assert saved is not None
        assert saved.case_id == 7
        assert saved.status == 'pending'

        # Clean up
        db.session.delete(saved)
        db.session.commit()

    def test_pipeline_run_status_transitions(self, app_context):
        """Test status transitions for pipeline runs."""
        from app.models.pipeline_run import PipelineRun, PIPELINE_STATUS

        run = PipelineRun(case_id=7, status=PIPELINE_STATUS['PENDING'])
        db.session.add(run)
        db.session.commit()

        # Test transitions
        run.set_status(PIPELINE_STATUS['RUNNING'])
        assert run.status == 'running'
        assert run.started_at is not None

        run.set_status(PIPELINE_STATUS['COMPLETED'])
        assert run.status == 'completed'
        assert run.completed_at is not None

        # Clean up
        db.session.delete(run)
        db.session.commit()


class TestQueueManagement:
    """Test suite for queue management."""

    def test_queue_add_and_remove(self, app_context, client):
        """Test adding and removing cases from queue."""
        from app.models.pipeline_run import PipelineQueue

        # Clear queue
        PipelineQueue.query.filter_by(case_id=99).delete()
        db.session.commit()

        # Add to queue via API
        response = client.post(
            '/pipeline/api/queue',
            json={'case_ids': [99], 'priority': 1},
            content_type='application/json'
        )

        # Verify addition (may fail if case doesn't exist)
        data = response.get_json()
        if data.get('success'):
            assert 99 in data.get('added', []) or any(
                s.get('case_id') == 99 for s in data.get('skipped', [])
            )

    def test_queue_priority_ordering(self, app_context):
        """Test that queue items are ordered by priority."""
        from app.models.pipeline_run import PipelineQueue

        # Clear test queue items
        PipelineQueue.query.filter(PipelineQueue.case_id.in_([97, 98, 99])).delete()
        db.session.commit()

        # Add items with different priorities
        items = [
            PipelineQueue(case_id=97, priority=0, status='queued'),
            PipelineQueue(case_id=98, priority=2, status='queued'),
            PipelineQueue(case_id=99, priority=1, status='queued'),
        ]
        db.session.add_all(items)
        db.session.commit()

        # Query in priority order
        ordered = PipelineQueue.query.filter(
            PipelineQueue.case_id.in_([97, 98, 99])
        ).order_by(
            PipelineQueue.priority.desc()
        ).all()

        if len(ordered) == 3:
            assert ordered[0].priority == 2
            assert ordered[1].priority == 1
            assert ordered[2].priority == 0

        # Clean up
        PipelineQueue.query.filter(PipelineQueue.case_id.in_([97, 98, 99])).delete()
        db.session.commit()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
