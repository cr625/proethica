"""End-to-end test for the interactive scenario traversal flow."""
import pytest
from app import create_app
from app.models import db


@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    return app.test_client()


def test_full_traversal_flow(client):
    """Start session -> make choices -> view summary -> view analysis."""
    from app.models import ExtractionPrompt
    with client.application.app_context():
        prompt = ExtractionPrompt.query.filter_by(
            concept_type='phase4_narrative'
        ).first()
        if not prompt:
            pytest.skip("No phase4_narrative data available")
        case_id = prompt.case_id

    prefix = '/scenario_pipeline'

    # Start session
    response = client.post(f'{prefix}/case/{case_id}/step5/interactive/start', follow_redirects=False)
    assert response.status_code in (302, 303)
    location = response.headers.get('Location', '')
    assert '/step5/interactive/' in location

    # Extract session UUID from redirect URL
    session_uuid = location.split('/step5/interactive/')[-1].rstrip('/')

    # Load first decision
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}')
    assert response.status_code == 200
    assert b'decision' in response.data.lower() or b'Decision' in response.data

    # Make choices until complete (max 10 to avoid infinite loop)
    for i in range(10):
        response = client.post(
            f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/choose',
            data={'option_index': 0, 'time_spent_seconds': 5},
            follow_redirects=False,
        )
        assert response.status_code in (302, 303)
        location = response.headers.get('Location', '')

        if '/summary' in location:
            break

    # View summary
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/summary')
    assert response.status_code == 200

    # View analysis
    response = client.get(f'{prefix}/case/{case_id}/step5/interactive/{session_uuid}/analysis')
    assert response.status_code == 200
