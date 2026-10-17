"""One canonical form for case_precedent_features.provisions_cited (case 24-1
review, lesson L3).

The column carried 'II.1.A' (references parser) next to 'II.1.a' (regex
extractor), and the exact-set Jaccard scored the 24-1 / 84-5 pair 0 instead of
0.286. Every writer now passes through normalize_provision_codes and the
overlap compares normalized sets. No database: the writes are patched.
"""

import re
from unittest.mock import MagicMock, patch

from app.utils.provision_codes import normalize_provision_codes, provision_sort_key
from app.services.precedent.case_feature_extractor import CaseFeatureExtractor, ExtractedFeatures
from app.services.precedent.similarity_service import PrecedentSimilarityService
from app.utils import provision_references

CANONICAL = re.compile(r'^(Preamble|(I{1,3}|IV)\.\d+(\.[A-Z])?)$')

# The shape of the 24-1 / 84-5 pair: case 8 stored by update_provisions_cited
# (uppercase letters), case 89 by extract_provisions (lowercase letters); two
# shared codes over seven distinct.
CASE_8_PROVISIONS = ['I.1', 'II.1.A', 'II.1.B', 'II.4', 'III.1.B']
CASE_89_PROVISIONS = ['II.1.a', 'II.4', 'III.4', 'iii.1.c']


class TestNormalizeProvisionCodes:

    def test_canonical_deduplicated_and_code_ordered(self):
        raw = ['II.1.a', 'II.1.A', 'I.1.', 'Section III.4', 'NSPE II.10', 'Canon 15', None, '']
        assert normalize_provision_codes(raw) == ['I.1', 'II.1.A', 'II.10', 'III.4']

    def test_every_value_matches_the_canonical_pattern(self):
        for code in normalize_provision_codes(CASE_8_PROVISIONS + CASE_89_PROVISIONS + ['Preamble']):
            assert CANONICAL.match(code), code

    def test_sort_key_places_preamble_first_and_sections_in_order(self):
        codes = ['III.1.B', 'I.1', 'Preamble', 'II.1.A', 'II.1.B', 'II.10', 'II.4']
        assert sorted(codes, key=provision_sort_key) == [
            'Preamble', 'I.1', 'II.1.A', 'II.1.B', 'II.4', 'II.10', 'III.1.B']


class TestExtractProvisionsWritesCanonicalCodes:

    def test_regex_extractor_uppercases_subsection_letters(self):
        extractor = CaseFeatureExtractor(embedding_service=MagicMock())
        text = ("Section I.1. Hold paramount the safety of the public. "
                "Section II.1.a. Engineers shall ... Section III.2.b. Engineers shall ... "
                "II.1.a is cited twice.")
        codes = extractor.extract_provisions(text)
        assert codes == ['I.1', 'II.1.A', 'III.2.B']
        assert all(CANONICAL.match(c) for c in codes)

    def test_save_features_normalizes_at_the_write(self):
        extractor = CaseFeatureExtractor(embedding_service=MagicMock())
        features = ExtractedFeatures(case_id=89, outcome_type='ethical', outcome_confidence=0.8,
                                     outcome_reasoning='r', provisions_cited=['II.1.a', 'II.4', 'II.1.A'])
        fake_db = MagicMock()
        fake_db.session.execute.return_value.fetchone.return_value = (1,)
        with patch('app.services.precedent.case_feature_extractor.db', fake_db):
            extractor.save_features(features)
        params = fake_db.session.execute.call_args.args[1]
        assert params['provisions_cited'] == ['II.1.A', 'II.4']
        assert params['provision_count'] == 2

    def test_update_provisions_cited_normalizes_at_the_write(self):
        fake_db = MagicMock()
        with patch.object(provision_references, 'harmonized_provision_codes',
                          return_value=['II.1.a', 'I.1', 'II.1.A']), \
             patch('app.models.db', fake_db):
            written = provision_references.update_provisions_cited(8)
        params = fake_db.session.execute.call_args.args[1]
        assert written == ['I.1', 'II.1.A']
        assert params['codes'] == ['I.1', 'II.1.A']
        fake_db.session.commit.assert_called_once()


class TestProvisionOverlapComparesNormalized:

    def test_case_24_1_against_84_5_scores_two_of_seven(self):
        service = PrecedentSimilarityService()
        score, matching = service._calculate_provision_overlap(CASE_8_PROVISIONS, CASE_89_PROVISIONS)
        assert round(score, 3) == 0.286
        assert matching == ['II.1.A', 'II.4']

    def test_exact_comparison_would_have_scored_zero(self):
        # The defect: exact set intersection of the two stored spellings.
        assert set(CASE_8_PROVISIONS) & set(CASE_89_PROVISIONS) == {'II.4'}
        assert len({'II.4'}) / len(set(CASE_8_PROVISIONS) | set(CASE_89_PROVISIONS)) < 0.286

    def test_empty_sides_score_zero(self):
        service = PrecedentSimilarityService()
        assert service._calculate_provision_overlap([], CASE_89_PROVISIONS) == (0.0, [])
        assert service._calculate_provision_overlap(['Canon 15'], CASE_89_PROVISIONS) == (0.0, [])
