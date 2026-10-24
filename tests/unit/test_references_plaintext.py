"""Plain-text references parsing for the 2026 NSPE page layout (case 25-1).

The references of 25-1 reach the parser as plain text. The fallback required the
provision text to start with "Engineers", which every Fundamental Canon fails, so the
canons I.1, I.4, I.5 and I.6 produced no code_provision_reference rows.
"""

from app.services.provision.nspe_references_parser import NSPEReferencesParser


# Verbatim references text of case 25-1 (document 184), as stored, shortened after III.1.b.
CASE_25_1_REFERENCES = (
    'Preamble   Engineering is an important and learned profession. As members of this '
    'profession, engineers are expected to exhibit the highest standards of honesty and '
    'integrity.       I.1.   Hold paramount the safety, health, and welfare of the public.   '
    'Subject Reference  Duty to the Public        I.4.   Act for each employer or client as '
    'faithful agents or trustees.   Subject Reference  Employer Faithful Agents and Trustees        '
    'I.5.   Avoid deceptive acts.   Subject Reference  Advertising        I.6.   Conduct '
    'themselves honorably, responsibly, ethically, and lawfully so as to enhance the honor, '
    'reputation, and usefulness of the profession.       II.4.a.   Engineers shall disclose '
    'all known or potential conflicts of interest that could influence or appear to influence '
    'their judgment or the quality of their services.   Subject Reference  Conflict of Interest'
    '        III.1.b.   Engineers shall advise their clients or employers when they believe a '
    'project will not be successful.   Subject Reference  Duty to Disclose'
)


def _by_code(text):
    return {p['code_provision']: p['provision_text']
            for p in NSPEReferencesParser().parse_references_html(text)}


def test_canons_and_rules_are_both_parsed():
    assert list(_by_code(CASE_25_1_REFERENCES)) == [
        'I.1', 'I.4', 'I.5', 'I.6', 'II.4.a', 'III.1.b']


def test_provision_text_stops_before_the_subject_reference_label():
    texts = _by_code(CASE_25_1_REFERENCES)
    assert texts['I.1'] == 'Hold paramount the safety, health, and welfare of the public.'
    assert texts['I.6'].endswith('usefulness of the profession.')
    assert texts['III.1.b'] == ('Engineers shall advise their clients or employers when '
                                'they believe a project will not be successful.')


def test_a_code_cited_mid_sentence_does_not_start_a_provision():
    text = ('II.1.f. Engineers shall act within the limits set by section I.1. of the Code. '
            'III.8.b. Engineers shall not attempt to injure another engineer.')
    assert list(_by_code(text)) == ['II.1.f', 'III.8.b']
