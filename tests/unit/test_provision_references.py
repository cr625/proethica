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


def test_nspe_fragment_rule_roundtrips_against_ontology():
    """Every dct:identifier in the NSPE Code ontology must map back to its
    own URI local name under nspe_provision_fragment, so ProEthica-built
    entity links can never dangle."""
    import os
    import pytest
    import rdflib
    from app.utils.provision_codes import nspe_provision_fragment

    path = os.path.join(
        os.environ.get('ONTSERVE_ONTOLOGIES_PATH',
                       os.path.join(os.path.dirname(__file__), '..', '..', '..',
                                    'OntServe', 'ontologies')),
        'NSPE Code of Ethics.ttl')
    if not os.path.exists(path):
        pytest.skip(f'NSPE TTL not found at {path}')
    g = rdflib.Graph()
    g.parse(path, format='turtle')
    DCT_ID = rdflib.URIRef('http://purl.org/dc/terms/identifier')
    NSPE = 'http://proethica.org/ontology/nspe#'
    checked = 0
    for s, _, ident in g.triples((None, DCT_ID, None)):
        if not str(s).startswith(NSPE):
            continue
        local = str(s)[len(NSPE):]
        frag = nspe_provision_fragment(str(ident))
        if frag is None:
            continue  # category identifiers like 'I' handled below
        assert frag == local, f"{ident} -> {frag} != {local}"
        checked += 1
    assert checked >= 50  # the full section canon must round-trip


def test_display_code_matches_ontology_identifiers():
    """provision_display_code is the user-facing spelling on the Provisions
    tab; it must equal the NSPE ontology's dct:identifier exactly for every
    provision, so the tab and the OntServe citation surfaces show the same
    label (2026-07-10 alignment audit: the tab showed raw LLM spellings like
    'II.3.a.' and the internal 'II.3.A' canonical, OntServe showed 'II.3.a')."""
    import os
    import pytest
    import rdflib
    from app.utils.provision_codes import provision_display_code

    # Spelling variants all collapse to the identifier form.
    assert provision_display_code('II.3.a.') == 'II.3.a'
    assert provision_display_code('II.3.A') == 'II.3.a'
    assert provision_display_code('NSPE Section III.1.a.') == 'III.1.a'
    assert provision_display_code('I.1 Public Welfare Paramount') == 'I.1'
    assert provision_display_code('Preamble') == 'Preamble'
    assert provision_display_code('Canon 15') is None  # historical: keep raw

    path = os.path.join(
        os.environ.get('ONTSERVE_ONTOLOGIES_PATH',
                       os.path.join(os.path.dirname(__file__), '..', '..', '..',
                                    'OntServe', 'ontologies')),
        'NSPE Code of Ethics.ttl')
    if not os.path.exists(path):
        pytest.skip(f'NSPE TTL not found at {path}')
    g = rdflib.Graph()
    g.parse(path, format='turtle')
    DCT_ID = rdflib.URIRef('http://purl.org/dc/terms/identifier')
    NSPE = 'http://proethica.org/ontology/nspe#'
    checked = 0
    for s, _, ident in g.triples((None, DCT_ID, None)):
        if not str(s).startswith(NSPE):
            continue
        disp = provision_display_code(str(ident))
        if disp is None:
            continue
        assert disp == str(ident), f"display {disp!r} != identifier {ident!r}"
        checked += 1
    assert checked >= 50
