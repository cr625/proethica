"""Board-stated provision reference parsing (2026-07-09 harmonization plan,
provisions-harmonization.md workstream A). The references section is the
authoritative board-stated provision list; these tests pin the HTML parser
to the scraped Drupal structure and the text fallback to the flattened
form."""
from app.utils.provision_references import (
    parse_references_html,
    parse_references_text,
)

CASE7_STYLE_HTML = """
<div class="field__items">
<div class="field__item"><div>
<h2><div class="field field--name-name field--type-string field--label-hidden field__item">I.1.</div></h2>
<div>
<div class="clearfix text-formatted field field--name-description field--type-text-long field--label-hidden field__item"><p>Hold paramount the safety, health, and welfare of the public.</p></div>
<div><div>Subject Reference</div>
<div class="field__items"><div class="field__item"><a href="https://www.nspe.org/x" target="_blank">Duty to the Public</a></div></div>
</div></div></div></div>
<div class="field__item"><div>
<h2><div class="field field--name-name field--type-string field--label-hidden field__item">II.1.c.</div></h2>
<div>
<div class="clearfix text-formatted field field--name-description field--type-text-long field--label-hidden field__item"><p>Engineers shall not reveal facts, data, or information without the prior consent of the client.</p></div>
<div><div>Subject Reference</div>
<div class="field__items"><div class="field__item"><a href="https://www.nspe.org/y">Confidentiality</a></div></div>
</div></div></div></div>
</div>
"""


def test_parse_html_extracts_codes_texts_subjects():
    out = parse_references_html(CASE7_STYLE_HTML)
    assert [p['code'] for p in out] == ['I.1', 'II.1.C']
    assert out[0]['text'].startswith('Hold paramount the safety')
    assert out[0]['subjects'] == ['Duty to the Public']
    assert out[1]['subjects'] == ['Confidentiality']


def test_parse_html_empty_and_garbage():
    assert parse_references_html('') == []
    assert parse_references_html('<p>No provisions here</p>') == []


def test_parse_text_fallback():
    text = ("I.1. Hold paramount the safety, health, and welfare of the public. "
            "Subject Reference Duty to the Public "
            "II.1.c. Engineers shall not reveal facts, data, or information "
            "without the prior consent of the client. Subject Reference Confidentiality")
    out = parse_references_text(text)
    assert [p['code'] for p in out] == ['I.1', 'II.1.C']
    assert out[0]['text'].startswith('Hold paramount')
    assert 'Duty to the Public' in out[0]['subjects'][0]
