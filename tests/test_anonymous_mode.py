"""
Coverage for the ANONYMOUS_MODE withholding introduced for the AAAI-27
double-blind review window.

TestingConfig sets ANONYMOUS_MODE = False so the rest of the suite exercises the
real flows, so every test here opts back in explicitly. Restoration guidance is
in docs-internal/anonymization-restore-2026-07.md.
"""
import pytest


WITHHELD_PATHS = [
    '/demo',
    '/docs/papers/',
    '/docs/papers/index.html',
]


@pytest.fixture
def anon_client(app):
    """Test client with the anonymization active."""
    app.config['ANONYMOUS_MODE'] = True
    return app.test_client()


@pytest.mark.parametrize('path', WITHHELD_PATHS)
def test_withheld_paths_return_notice(anon_client, path):
    """Withheld paths serve the neutral notice, not a bare 404 or the content."""
    resp = anon_client.get(path)
    assert resp.status_code == 404
    body = resp.get_data(as_text=True)
    assert 'anonymous peer review' in body
    # The notice must not itself leak what it is withholding.
    assert 'Rauch' not in body
    assert 'Drexel' not in body


def test_validation_blueprint_withheld(anon_client):
    """
    The validation-study routes are unreachable, so the IRB consent documents
    are not served. Their text is deliberately left verbatim in the templates.
    """
    resp = anon_client.get('/validation/')
    assert resp.status_code == 404
    assert 'anonymous peer review' in resp.get_data(as_text=True)


def test_demo_page_identity_absent(anon_client):
    """The demo landing page names an author and a personal address when shown."""
    body = anon_client.get('/demo').get_data(as_text=True)
    for token in ('christopher.b.rauch', 'cr625', '@drexel.edu'):
        assert token not in body.lower()


def test_footer_repository_link_withheld(anon_client):
    """The footer repository link identifies the author's account; it renders on
    every page, so it is the highest-exposure single item."""
    body = anon_client.get('/').get_data(as_text=True)
    assert 'github.com/cr625' not in body


def test_login_contact_address_withheld(anon_client):
    body = anon_client.get('/auth/login').get_data(as_text=True)
    assert 'cr625@drexel.edu' not in body
    assert 'registered collaborators' in body


def test_disabled_by_default_in_tests(client):
    """
    Guard against the flag silently switching on for the rest of the suite. If
    this fails, the validation-study e2e coverage is being skipped rather than
    run.
    """
    resp = client.get('/demo')
    assert resp.status_code == 200


def test_flag_restores_content(app):
    """Restoration is a single toggle; the camera-ready path must stay working."""
    app.config['ANONYMOUS_MODE'] = False
    body = app.test_client().get('/demo').get_data(as_text=True)
    assert 'github.com/cr625/proethica' in body
