"""Unit tests for the unified search entity lane (increment 1)."""

from unittest.mock import MagicMock

import pytest

from app.services.search.unified_search_service import (
    UnifiedSearchService,
    case_id_for,
    derive_category,
)


class TestDeriveCategory:

    def test_core_parent_fragment(self):
        assert derive_category('http://proethica.org/ontology/core#Principle', 'Public Welfare Principle') == 'Principle'

    def test_intermediate_parent_suffix(self):
        assert derive_category('http://proethica.org/ontology/intermediate#PublicWelfarePrinciple', 'Public Welfare in Testimony') == 'Principle'

    def test_label_suffix_fallback(self):
        assert derive_category('http://purl.obolibrary.org/obo/BFO_0000023', 'Structural Engineer Role') == 'Role'

    def test_no_match(self):
        assert derive_category('http://example.org/thing#Widget', 'Widget') is None

    def test_none_inputs(self):
        assert derive_category(None, None) is None


class TestCaseIdFor:

    def test_case_ontology(self):
        assert case_id_for('proethica-case-97') == 97

    def test_base_ontology(self):
        assert case_id_for('proethica-intermediate') is None

    def test_none(self):
        assert case_id_for(None) is None


def _make_engine(rows):
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = rows
    return engine, conn


ROW_BASE = ('http://proethica.org/ontology/intermediate#PublicWelfarePrinciple',
            'Public Welfare Principle', 'Definition text.', 'class',
            'http://proethica.org/ontology/core#Principle',
            'proethica-intermediate', 'base')
ROW_CASE_COPY = ('http://proethica.org/ontology/intermediate#PublicWelfarePrinciple',
                 'Public Welfare Principle', 'Definition text.', 'class',
                 'http://proethica.org/ontology/core#Principle',
                 'proethica-case-7', 'case')
ROW_CASE_MINTED = ('http://proethica.org/ontology/case/7#Discussion_Public_Welfare',
                   'Public Welfare in Testimony', None, 'individual',
                   'http://proethica.org/ontology/intermediate#PublicWelfarePrinciple',
                   'proethica-case-7', 'case')


class TestSearchEntities:

    def test_empty_query_returns_empty_without_db(self):
        engine, conn = _make_engine([])
        svc = UnifiedSearchService(engine=engine)
        assert svc.search_entities('') == []
        assert svc.search_entities('   ') == []
        engine.connect.assert_not_called()

    def test_dedup_by_uri_keeps_first(self):
        engine, _ = _make_engine([ROW_BASE, ROW_CASE_COPY, ROW_CASE_MINTED])
        results = UnifiedSearchService(engine=engine).search_entities('public welfare')
        uris = [r['uri'] for r in results]
        assert len(uris) == len(set(uris)) == 2
        # The base-ontology copy (ordered first by the SQL) wins the dedup.
        assert results[0]['ontology_name'] == 'proethica-intermediate'

    def test_result_mapping(self):
        engine, _ = _make_engine([ROW_CASE_MINTED])
        (r,) = UnifiedSearchService(engine=engine).search_entities('public welfare')
        assert r['category'] == 'Principle'
        assert r['color']  # canonical component color attached
        assert r['case_id'] == 7
        assert r['ontserve_url'].endswith('/entity/proethica-case-7/Discussion_Public_Welfare')

    def test_limit_applied_after_dedup(self):
        rows = []
        for i in range(30):
            rows.append((f'http://proethica.org/ontology/intermediate#Thing{i}',
                         f'Thing {i}', None, 'class',
                         'http://proethica.org/ontology/core#Resource',
                         'proethica-intermediate', 'base'))
        engine, _ = _make_engine(rows)
        results = UnifiedSearchService(engine=engine).search_entities('thing', limit=5)
        assert len(results) == 5

    def test_db_error_propagates(self):
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError('db down')
        with pytest.raises(RuntimeError):
            UnifiedSearchService(engine=engine).search_entities('public welfare')


@pytest.mark.integration
class TestSearchEntitiesIntegration:
    """Hits the real local OntServe DB; skipped when it is unreachable."""

    def test_public_welfare_surfaces_principle(self):
        svc = UnifiedSearchService()
        try:
            results = svc.search_entities('public welfare')
        except Exception as e:
            pytest.skip(f'OntServe DB unavailable: {e}')
        assert results, 'expected at least one entity for a corpus-central concept'
        assert any(r['category'] == 'Principle' for r in results)
