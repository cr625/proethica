"""
NSPE reuse notice.

NSPE permits reprinting a Board of Ethical Review opinion provided that its
NOTE statement is included before or after the text of the case, with
attribution to the Board. The shared macros in macros/_nspe_notice.html carry
the NOTE in the site footer while the Engineering world is selected
(nspe_note), and the attribution line of a case on the case view directly
after the opinion text, for a case whose stored source is a page on nspe.org
(nspe_attribution).
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.utils.nspe_source import nspe_source_url

REPO = Path(__file__).resolve().parents[2]
TEMPLATES = REPO / 'app' / 'templates'

# Current wording, as printed in the opinion PDFs of cases 24-1 and 25-1.
NSPE_NOTE = (
    "NOTE: The NSPE Board of Ethical Review considers ethical cases involving either real or "
    "hypothetical matters submitted to it from NSPE members, other engineers, public officials, "
    "and members of the public. The BER reviews each case in the context of the NSPE Code of "
    "Ethics and earlier BER opinions. The facts contained in each case do not necessarily "
    "represent all of the pertinent facts submitted to or reviewed by the BER and shall not be "
    "considered a direct evaluation of any real matter that may have been submitted. "
    "Each opinion is intended as guidance to individual practicing engineers, students, and the "
    "public. In regard to the question of application of the NSPE Code of Ethics to engineering "
    "organizations (e.g., corporations, partnerships, sole proprietorships, government agencies, "
    "and university engineering departments), the specific business form or type should not "
    "negate nor detract from the conformance of individuals to the Code. The NSPE Code deals "
    "with professional services, which must be performed by real persons. Real persons in turn "
    "establish and implement policies within business structures. "
    "This opinion is for educational purposes only and is not legal advice. It may be reprinted "
    "without further permission, provided that this statement is included before or after the "
    "text of the case and appropriate attribution is provided to the National Society of "
    "Professional Engineers' Board of Ethical Review."
)

NSPE_URL = ('https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/'
            'balancing-client-directives-public-welfare')


def _macros():
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    return env.get_template('macros/_nspe_notice.html').module


def _note():
    return str(_macros().nspe_note())


def _attribution(*args, **kwargs):
    return str(_macros().nspe_attribution(*args, **kwargs))


def _text(html):
    text = re.sub(r'<[^>]+>', ' ', html).replace('&#39;', "'")
    return re.sub(r'\s+', ' ', text).strip()


def _collapsed(html):
    return re.search(r'<div class="collapse d-print-block" id="nspe-note-full">(.*?)</div>',
                     html, re.S).group(1)


class TestFooterNote:

    def test_note_is_the_current_nspe_wording_in_published_order(self):
        assert NSPE_NOTE in _text(_note())

    def test_reprint_paragraph_is_visible(self):
        html = _note()
        assert 'educational purposes only' not in _collapsed(html)
        assert 'educational purposes only' in html

    def test_first_two_paragraphs_are_collapsed_on_screen(self):
        collapsed = _text(_collapsed(_note()))
        assert collapsed.startswith('NOTE: The NSPE Board of Ethical Review')
        assert collapsed.endswith('within business structures.')
        html = _note()
        assert 'data-bs-target="#nspe-note-full"' in html
        assert 'aria-expanded="false"' in html

    def test_note_prints_in_full_without_its_toggle(self):
        html = _note()
        assert '<div class="collapse d-print-block" id="nspe-note-full">' in html
        assert re.search(r'<button[^>]*class="[^"]*\bd-print-none\b[^"]*"[^>]*data-bs-toggle="collapse"', html)

    def test_footer_carries_the_note_for_the_engineering_world(self):
        base = (TEMPLATES / 'base.html').read_text()
        footer = base.index('<div class="footer">')
        guard = base.index("{% if selected_domain and selected_domain.name == 'Engineering' %}")
        call = base.index('{{ nspe_note() }}')
        assert footer < guard < call < base.index('Licensed under the')


class TestCaseAttribution:

    def test_attribution_links_to_the_stored_nspe_page(self):
        html = _attribution('24-1', NSPE_URL)
        assert (f'<a href="{NSPE_URL}" target="_blank" rel="noopener" class="link-secondary">'
                'Source: National Society of Professional Engineers, Board of Ethical Review, '
                '<span class="text-nowrap">Case 24-1</span></a>') in html

    def test_attribution_without_a_case_number(self):
        html = _attribution(None, NSPE_URL)
        assert _text(html) == 'Source: National Society of Professional Engineers, Board of Ethical Review'

    def test_attribution_without_a_source_url_has_no_link(self):
        for source in (None, ''):
            html = _attribution('24-1', source)
            assert '<a ' not in html
            assert ('Source: National Society of Professional Engineers, Board of Ethical Review, '
                    'Case 24-1') in _text(html)

    def test_attribution_does_not_repeat_the_note(self):
        assert 'NOTE:' not in _attribution('24-1', NSPE_URL)


class TestSourceHost:

    def test_nspe_pages_qualify(self):
        assert nspe_source_url(NSPE_URL) == NSPE_URL
        assert nspe_source_url(f'  {NSPE_URL}  ') == NSPE_URL
        assert nspe_source_url('http://nspe.org/resources/ethics/case-58-1') == \
            'http://nspe.org/resources/ethics/case-58-1'

    def test_other_hosts_do_not_qualify(self):
        for source in (None, '', 'agent_generated',
                       'https://example.org/case.pdf',
                       'https://example.org/?ref=nspe.org',
                       'https://nspe.org.example.com/case',
                       'https://notnspe.org/case',
                       'ftp://www.nspe.org/case.pdf',
                       'www.nspe.org/case'):
            assert nspe_source_url(source) is None, source


class TestCaseView:

    def test_view_passes_the_verified_nspe_url(self):
        view = (REPO / 'app' / 'routes' / 'cases' / 'view.py').read_text()
        assert "'nspe_source_url': nspe_source_url(document.source)," in view

    def test_attribution_only_for_an_nspe_source(self):
        template = (TEMPLATES / 'case_detail.html').read_text()
        guard = template.index('{% if case.nspe_source_url %}')
        call = template.index('{{ nspe_attribution(case.case_number, case.nspe_source_url) }}')
        other = template.index('{% elif case.source %}')
        assert guard < call < other

    def test_case_view_renders_the_attribution_after_the_opinion_text(self):
        template = (TEMPLATES / 'case_detail.html').read_text()
        assert "{% from 'macros/_nspe_notice.html' import nspe_attribution %}" in template
        call = template.index('{{ nspe_attribution(case.case_number, case.nspe_source_url) }}')
        assert template.index('id="dissent-section"') < call
        assert template.index('{{ case.description|safe }}') < call
        assert call < template.index('{% if case.decision %}')

    def test_attribution_is_the_only_source_line(self):
        template = (TEMPLATES / 'case_detail.html').read_text()
        assert '<strong>Source:</strong>' not in template

    def test_entity_scan_leaves_the_attribution_verbatim(self):
        script = (REPO / 'app' / 'static' / 'js' / 'cases' / 'case_detail_page.js').read_text()
        assert "excludeSelector: '.onto-label, a, button, .badge, .nspe-notice'" in script
