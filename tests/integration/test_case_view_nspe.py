"""
NSPE reuse notice on rendered pages.

The site footer carries the NSPE NOTE while the Engineering world is selected;
the case view adds the linked NSPE attribution line only for a case whose
stored source is a page on nspe.org, and names any other source plainly.
"""

import pytest

from app import db
from app.models.document import Document, PROCESSING_STATUS
from app.models.world import World

NSPE_URL = ('https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/'
            'balancing-client-directives-public-welfare')
ATTRIBUTION = 'Source: National Society of Professional Engineers, Board of Ethical Review'
REPRINT = b'It may be reprinted without further permission'


def _world(name):
    world = World(name=name, description=f'{name} world')
    db.session.add(world)
    db.session.commit()
    return world


def _case(world_id, source, case_number='24-1'):
    doc = Document(
        title=f'Case {case_number}: Test Case',
        document_type='case',
        world_id=world_id,
        content='<p>Opinion text of the test case.</p>',
        source=source,
        processing_status=PROCESSING_STATUS['PENDING'],
        doc_metadata={'case_number': case_number, 'year': '2024'},
    )
    db.session.add(doc)
    db.session.commit()
    return doc


class TestFooterNote:

    def test_engineering_world_shows_the_note_on_every_page(self, client, app_context):
        _world('Engineering')
        for path in ('/', '/cases/'):
            response = client.get(path)
            assert response.status_code == 200, path
            assert b'id="nspe-note-full"' in response.data, path
            assert response.data.count(REPRINT) == 1, path

    def test_other_world_shows_no_note(self, client, app_context):
        _world('Test World')
        response = client.get('/cases/')
        assert response.status_code == 200
        assert b'nspe-note-full' not in response.data
        assert REPRINT not in response.data


class TestCaseView:

    def test_nspe_case_has_the_linked_attribution_and_one_note(self, client, app_context):
        doc = _case(_world('Engineering').id, NSPE_URL)
        html = client.get(f'/cases/{doc.id}').get_data(as_text=True)
        assert f'<a href="{NSPE_URL}" target="_blank" rel="noopener" class="link-secondary">' \
               f'{ATTRIBUTION}, <span class="text-nowrap">Case 24-1</span></a>' in html
        assert html.count('Source:') == 1
        assert html.count('It may be reprinted without further permission') == 1

    def test_other_source_is_named_without_nspe_attribution(self, client, app_context):
        doc = _case(_world('Engineering').id, 'https://example.org/?ref=nspe.org')
        html = client.get(f'/cases/{doc.id}').get_data(as_text=True)
        assert ATTRIBUTION not in html
        assert '<a href="https://example.org/?ref=nspe.org" target="_blank" rel="noopener" ' \
               'class="link-secondary">https://example.org/?ref=nspe.org</a>' in html

    def test_case_without_source_has_no_source_line(self, client, app_context):
        doc = _case(_world('Engineering').id, None)
        html = client.get(f'/cases/{doc.id}').get_data(as_text=True)
        assert 'Source:' not in html
