"""
NSPE reuse notice on the case view.

NSPE permits reprinting a Board of Ethical Review opinion provided that its
NOTE statement is included before or after the text of the case, with
attribution to the Board. The case view renders the shared macro
macros/_nspe_notice.html directly after the opinion text.
"""

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

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


def _render(*args, **kwargs):
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True)
    macro = env.get_template('macros/_nspe_notice.html').module.nspe_notice
    return str(macro(*args, **kwargs))


def _text(html):
    text = re.sub(r'<[^>]+>', ' ', html).replace('&#39;', "'")
    return re.sub(r'\s+', ' ', text).strip()


class TestNoticeMacro:

    def test_note_is_the_current_nspe_wording(self):
        assert NSPE_NOTE in _text(_render('24-1', NSPE_URL))

    def test_attribution_links_to_the_stored_nspe_page(self):
        html = _render('24-1', NSPE_URL)
        assert (f'<a href="{NSPE_URL}" target="_blank" rel="noopener" class="link-secondary">'
                'Source: National Society of Professional Engineers, Board of Ethical Review, '
                'Case 24-1</a>') in html

    def test_attribution_without_an_nspe_url_has_no_link(self):
        for source in (None, '', 'https://example.org/case.pdf'):
            html = _render('24-1', source)
            assert '<a ' not in html
            assert ('Source: National Society of Professional Engineers, Board of Ethical Review, '
                    'Case 24-1') in _text(html)

    def test_note_is_collapsed_behind_its_toggle(self):
        html = _render('24-1', NSPE_URL)
        assert '<div class="collapse d-print-block" id="nspe-note-24-1">' in html
        assert 'data-bs-target="#nspe-note-24-1"' in html
        assert 'aria-expanded="false"' in html

    def test_note_prints_in_full_without_its_toggle(self):
        html = _render('24-1', NSPE_URL)
        assert 'd-print-block" id="nspe-note-24-1"' in html
        assert re.search(r'<button[^>]*class="[^"]*\bd-print-none\b[^"]*"[^>]*data-bs-toggle="collapse"', html)


class TestCaseView:

    def test_case_view_renders_the_notice_after_the_opinion_text(self):
        template = (TEMPLATES / 'case_detail.html').read_text()
        assert "{% from 'macros/_nspe_notice.html' import nspe_notice %}" in template
        call = template.index('{{ nspe_notice(case.case_number, case.source) }}')
        assert template.index('id="dissent-section"') < call
        assert template.index('{{ case.description|safe }}') < call
        assert call < template.index('{% if case.decision %}')

    def test_notice_is_the_only_source_line(self):
        template = (TEMPLATES / 'case_detail.html').read_text()
        assert '<strong>Source:</strong>' not in template

    def test_entity_scan_leaves_the_notice_verbatim(self):
        script = (REPO / 'app' / 'static' / 'js' / 'cases' / 'case_detail_page.js').read_text()
        assert "excludeSelector: '.onto-label, a, button, .badge, .nspe-notice'" in script
