"""
Browser tab titles name the application ProEthica.

Several templates still carried the earlier product name "AI Ethical
Decision-Making Simulator" in their title block. Page titles end in
" - ProEthica", and base.html defaults to "ProEthica".
"""

from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / 'app' / 'templates'


def test_no_template_uses_the_old_product_name():
    stale = [str(p.relative_to(TEMPLATES)) for p in TEMPLATES.rglob('*.html')
             if 'Decision-Making Simulator' in p.read_text(encoding='utf-8')]
    assert stale == []


def test_base_title_defaults_to_proethica():
    base = (TEMPLATES / 'base.html').read_text(encoding='utf-8')
    assert '<title>{% block title %}ProEthica{% endblock %}</title>' in base
