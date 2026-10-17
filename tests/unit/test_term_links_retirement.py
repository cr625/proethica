"""
Legacy section term links (review of case 24-1, defect G).

The 2025 word-level term links point at engineering-ethics URIs that no
current ontology declares. The case page no longer loads them, the listing no
longer computes a flag for them, and the Structure page card renders only
while a case has no committed ontology. The table and model stay in place.
"""

import inspect
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]


class TestCasePageAndListing:

    def test_view_case_no_longer_loads_term_links(self):
        import app.routes.cases.view as view

        source = inspect.getsource(view)
        assert 'SectionTermLink' not in source
        assert 'term_links_by_section' not in source

    def test_case_template_never_referenced_the_loader_output(self):
        template = (REPO / 'app' / 'templates' / 'case_detail.html').read_text()
        assert 'term_links_by_section' not in template

    def test_listing_no_longer_computes_has_term_links(self):
        import app.routes.cases.listing as listing

        source = inspect.getsource(listing)
        assert 'has_term_links' not in source
        assert 'section_term_links' not in source

    def test_case_page_script_dropped_the_dead_term_links_global(self):
        script = (REPO / 'app' / 'static' / 'js' / 'cases' / 'case_detail_page.js').read_text()
        assert 'termLinksData' not in script

    def test_model_and_table_stay(self):
        from app.models.section_term_link import SectionTermLink

        assert SectionTermLink.__tablename__ == 'section_term_links'


class TestStructurePageGate:

    def _context(self, committed, links):
        from app.routes.document_structure import view_routes

        with patch('app.services.entity.committed_case_graph.committed_case_exists',
                   return_value=committed), \
                patch.object(view_routes.SectionTermLink, 'get_document_term_links',
                             return_value=links) as loader:
            context = view_routes.term_links_context(8)
        return context, loader

    def test_committed_case_hides_the_card_and_skips_the_query(self):
        context, loader = self._context(committed=True, links={'facts': [{'term_text': 'Engineer'}]})
        assert context == {'show_term_links': False, 'has_term_links': False, 'section_term_links': None}
        loader.assert_not_called()

    def test_uncommitted_case_keeps_the_legacy_card(self):
        links = {'facts': [{'term_text': 'Engineer'}], 'discussion': []}
        context, loader = self._context(committed=False, links=links)
        assert context['show_term_links'] is True
        assert context['has_term_links'] is True
        assert context['section_term_links'] == links
        loader.assert_called_once_with(8)

    def test_uncommitted_case_without_rows(self):
        context, _ = self._context(committed=False, links={})
        assert context == {'show_term_links': True, 'has_term_links': False, 'section_term_links': None}

    def test_template_gates_the_card_and_its_toc_entry(self):
        template = (REPO / 'app' / 'templates' / 'document_structure.html').read_text()
        assert template.count('{% if show_term_links %}') == 2
        card = template.index('<div id="term-links"')
        assert template.rfind('{% if show_term_links %}', 0, card) != -1
        assert '{% endif %}\n\n    {% if structure_triples %}' in template
