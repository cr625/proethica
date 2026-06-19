"""Pre-1981 numbered-Canon / Rule provision parsing (VERIFICATION_CRITERIA V6 gap).

Cases adjudicated before the current three-part I/II/III NSPE Code (adopted
January 1981) cite the numbered "Canons of Ethics" and "Rules of Professional
Conduct". The references parser and the in-text detector were Roman-numeral only,
so these older cases produced zero code_provision_reference rows. These tests
pin the historical-format handling, using the verbatim case-103 (BER 63-5)
references wording.
"""

from app.services.provision.nspe_references_parser import NSPEReferencesParser
from app.services.provision.universal_provision_detector import UniversalProvisionDetector


# Verbatim references text from case 103 (BER 63-5), as stored in the DB.
CASE_103_REFERENCES = (
    'Canons of Ethics-Canon 15- "He will not accept compensation, financial or '
    'otherwise, from more than one interested party for the same service, or for '
    'services pertaining to the same work, without the consent of all interested '
    'parties." Canon 27-"He will not use the advantages of a salaried position to '
    'compete unfairly with another engineer." Rules of Professional Conduct '
    'Rule 13-"He will advise his client when he believes a project will not be '
    'successful." Rule 17-"An engineer in private practice may be employed by more '
    'than one party when the parties are informed."'
)

MODERN_REFERENCES = (
    'II.1.f. Engineers shall advise their clients when they believe a project will '
    'not be successful. III.8.b. Engineers shall not attempt to injure another engineer.'
)


def test_parses_canons_and_rules_with_verbatim_text():
    provisions = NSPEReferencesParser().parse_references_html(CASE_103_REFERENCES)
    codes = {p['code_provision'] for p in provisions}
    assert codes == {'Canon 15', 'Canon 27', 'Rule 13', 'Rule 17'}
    by_code = {p['code_provision']: p for p in provisions}
    assert by_code['Canon 15']['provision_text'].startswith('He will not accept compensation')
    # Quotes and the leading dash are stripped, the full sentence is kept.
    assert by_code['Canon 15']['provision_text'].endswith('all interested parties.')
    assert all(p.get('historical') for p in provisions)


def test_historical_fallback_does_not_fire_for_modern_references():
    provisions = NSPEReferencesParser().parse_references_html(MODERN_REFERENCES)
    codes = {p['code_provision'] for p in provisions}
    # Modern Roman-numeral codes parse normally; no spurious Canon/Rule entries.
    assert 'II.1.f' in codes
    assert not any(p.get('historical') for p in provisions)


def test_detector_finds_canon_and_rule_mentions():
    detector = UniversalProvisionDetector()
    sections = {
        'discussion': 'The Board considered Canon 15 and Canon 27 in this matter, '
                      'and also referenced Rule 13 of the Rules of Professional Conduct.'
    }
    mentions = detector.detect_all_provisions(sections)
    found = {m.mentioned_provision for m in mentions}
    assert {'Canon 15', 'Canon 27', 'Rule 13'} <= found
    assert all(
        m.match_type == 'historical'
        for m in mentions if m.mentioned_provision.startswith(('Canon', 'Rule'))
    )


def test_detector_modern_text_yields_no_historical_mentions():
    detector = UniversalProvisionDetector()
    sections = {'discussion': 'The Board cited Section II.1.f and III.8.b.'}
    mentions = detector.detect_all_provisions(sections)
    assert not any(m.match_type == 'historical' for m in mentions)
