"""Unit tests for the unified search entity lane (increments 1-2)."""

from unittest.mock import MagicMock

import pytest

from app.services.search.unified_search_service import (
    MIN_SEMANTIC_SCORE,
    UnifiedSearchService,
    case_id_for,
    derive_category,
    is_domain_ontology,
    query_tokens,
)


class TestDeriveCategory:

    def test_core_parent_fragment(self):
        assert derive_category('http://proethica.org/ontology/core#Principle', 'Public Welfare Principle') == 'Principle'

    def test_intermediate_parent_suffix(self):
        assert derive_category('http://proethica.org/ontology/intermediate#PublicWelfarePrinciple', 'Public Welfare in Testimony') == 'Principle'

    def test_label_suffix_fallback_proethica_uri(self):
        assert derive_category('http://purl.obolibrary.org/obo/BFO_0000023', 'Structural Engineer Role',
                               uri='http://proethica.org/ontology/intermediate#StructuralEngineerRole') == 'Role'

    def test_foreign_term_not_categorized_by_label(self):
        # prov:Role is not a nine-component Role despite the label suffix.
        assert derive_category('http://www.w3.org/2002/07/owl#Thing', 'Role',
                               uri='http://www.w3.org/ns/prov#Role') is None

    def test_no_match(self):
        assert derive_category('http://example.org/thing#Widget', 'Widget') is None

    def test_none_inputs(self):
        assert derive_category(None, None) is None


class TestQueryTokens:

    def test_plural_stripping(self):
        assert query_tokens('Faithful Agents') == ['faithful', 'agent']

    def test_double_s_kept(self):
        assert query_tokens('process') == ['process']

    def test_short_token_kept(self):
        assert query_tokens('gas bus') == ['gas', 'bus']

    def test_cap_at_six(self):
        assert len(query_tokens('a b c d e f g h')) == 6


class TestIsDomainOntology:

    def test_proethica_family(self):
        assert is_domain_ontology('proethica-intermediate')
        assert is_domain_ontology('proethica-case-7')
        assert is_domain_ontology('engineering-ethics')
        assert is_domain_ontology('NSPE Code of Ethics')

    def test_foreign(self):
        assert not is_domain_ontology('w3c-prov-o')
        assert not is_domain_ontology('bfo')
        assert not is_domain_ontology(None)


class TestCaseIdFor:

    def test_case_ontology(self):
        assert case_id_for('proethica-case-97') == 97

    def test_base_ontology(self):
        assert case_id_for('proethica-intermediate') is None

    def test_none(self):
        assert case_id_for(None) is None


FAKE_VEC = [0.1] * 384


def _make_engine(lexical_rows, semantic_rows=None, link_rows=None):
    """Engine mock: execute() returns the lexical rows, then the semantic
    rows, then the case-link rows (matching the service's call order; unused
    trailing result sets are harmless)."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    result_sets = [lexical_rows]
    if semantic_rows is not None:
        result_sets.append(semantic_rows)
    result_sets.append(link_rows or [])
    executes = []
    for rows in result_sets:
        r = MagicMock()
        r.fetchall.return_value = rows
        executes.append(r)
    conn.execute.side_effect = executes
    return engine, conn


def _row(uri, label, onto_name='proethica-intermediate', onto_type='base',
         entity_type='class', parent='http://proethica.org/ontology/core#Principle',
         comment='Definition text.', distance=None):
    return (uri, label, comment, entity_type, parent, onto_name, onto_type, distance)


I = 'http://proethica.org/ontology/intermediate#'


class TestSearchEntities:

    def _svc(self, engine, embed=True, domain_only=True):
        return UnifiedSearchService(
            engine=engine,
            embed_fn=(lambda q: FAKE_VEC) if embed else (lambda q: (_ for _ in ()).throw(RuntimeError('no model'))),
            domain_only=domain_only,
        )

    def test_domain_only_filter_present_in_sql(self):
        engine, conn = _make_engine([], [])
        self._svc(engine).search_entities('welfare')
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert sqls and all('proethica' in s.lower() for s in sqls)

    def test_domain_only_off_omits_filter(self):
        engine, conn = _make_engine([], [])
        self._svc(engine, domain_only=False).search_entities('welfare')
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert sqls and all("o.name ILIKE 'proethica%'" not in s for s in sqls)

    def test_empty_query_returns_empty_without_db(self):
        engine, _ = _make_engine([], [])
        svc = self._svc(engine)
        assert svc.search_entities('') == []
        assert svc.search_entities('   ') == []
        engine.connect.assert_not_called()

    def test_dedup_by_uri_lexical_arm_wins(self):
        base = _row(I + 'PublicWelfarePrinciple', 'Public Welfare Principle', distance=0.3)
        case_copy = _row(I + 'PublicWelfarePrinciple', 'Public Welfare Principle',
                         onto_name='proethica-case-7', onto_type='case', distance=0.3)
        engine, _ = _make_engine([base], [case_copy])
        results = self._svc(engine).search_entities('public welfare')
        assert len(results) == 1
        assert results[0]['ontology_name'] == 'proethica-intermediate'
        assert results[0]['score'] == pytest.approx(0.7)

    def test_semantic_only_hit_included_above_floor(self):
        sem = _row(I + 'DutyToReport', 'Duty To Report Obligation',
                   parent='http://proethica.org/ontology/core#Obligation', distance=0.4)
        engine, _ = _make_engine([], [sem])
        results = self._svc(engine).search_entities('engineer discovers defect')
        assert len(results) == 1
        assert results[0]['score'] == pytest.approx(0.6)

    def test_semantic_only_hit_below_floor_dropped(self):
        sem = _row(I + 'Unrelated', 'Unrelated Thing', distance=1.0 - (MIN_SEMANTIC_SCORE - 0.05))
        engine, _ = _make_engine([], [sem])
        assert self._svc(engine).search_entities('zxqv blorp') == []

    def test_lexical_hit_below_floor_kept(self):
        lex = _row(I + 'ObscureWelfareNote', 'Obscure Welfare Note', distance=0.9)
        engine, _ = _make_engine([lex], [])
        results = self._svc(engine).search_entities('welfare')
        assert len(results) == 1
        assert results[0]['score'] == pytest.approx(0.1)

    def test_ranking_exact_label_first_then_score(self):
        exact = _row(I + 'Welfare', 'Welfare', distance=0.5)
        better_score = _row(I + 'PublicWelfarePrinciple', 'Public Welfare Principle', distance=0.1)
        engine, _ = _make_engine([exact, better_score], [])
        results = self._svc(engine).search_entities('Welfare')
        assert [r['label'] for r in results] == ['Welfare', 'Public Welfare Principle']

    def test_embedding_failure_degrades_to_lexical(self):
        lex = _row(I + 'PublicWelfarePrinciple', 'Public Welfare Principle')
        engine, conn = _make_engine([lex])
        results = self._svc(engine, embed=False).search_entities('public welfare')
        assert len(results) == 1
        assert results[0]['score'] is None
        # Lexical arm + case-links only; the semantic arm never ran.
        sqls = [str(c.args[0]) for c in conn.execute.call_args_list]
        assert len(sqls) == 2
        assert not any('deduped' in s for s in sqls)

    def test_result_mapping(self):
        minted = ('http://proethica.org/ontology/case/7#Discussion_Public_Welfare',
                  'Public Welfare in Testimony', None, 'individual',
                  I + 'PublicWelfarePrinciple', 'proethica-case-7', 'case', 0.2)
        engine, _ = _make_engine([minted], [])
        (r,) = self._svc(engine).search_entities('public welfare')
        assert r['category'] == 'Principle'
        assert r['color']  # canonical component color attached
        assert r['case_id'] == 7
        assert r['ontserve_url'].endswith('/entity/proethica-case-7/Discussion_Public_Welfare')

    def test_foreign_ontology_discounted_in_rank_not_display(self):
        # prov:Agent scores higher raw, but the proethica obligation must
        # outrank it; the displayed score stays the honest cosine.
        prov = ('http://www.w3.org/ns/prov#Agent', 'Agent', 'An agent...', 'class',
                'http://www.w3.org/2002/07/owl#Thing', 'w3c-prov-o', 'base', 0.281)
        faithful = _row(I + 'FaithfulAgentObligation', 'Faithful Agent Obligation',
                        parent='http://proethica.org/ontology/core#Obligation', distance=0.398)
        engine, _ = _make_engine([], [prov, faithful])
        results = self._svc(engine, domain_only=False).search_entities('faithful agents')
        assert [r['label'] for r in results] == ['Faithful Agent Obligation', 'Agent']
        assert results[1]['score'] == pytest.approx(0.719)  # display undiscounted
        assert results[1]['category'] is None  # foreign term: no component badge

    def test_exact_label_beats_foreign_discount(self):
        prov = ('http://www.w3.org/ns/prov#Agent', 'Agent', 'An agent...', 'class',
                'http://www.w3.org/2002/07/owl#Thing', 'w3c-prov-o', 'base', 0.1)
        other = _row(I + 'ParticipantAgent', 'Participant Agent', distance=0.05)
        engine, _ = _make_engine([prov, other], [])
        results = self._svc(engine, domain_only=False).search_entities('Agent')
        assert results[0]['label'] == 'Agent'  # exact pin survives the discount

    def test_base_entity_case_back_links(self):
        base = _row(I + 'PublicWelfarePrinciple', 'Public Welfare Principle', distance=0.2)
        links = [(I + 'PublicWelfarePrinciple', 'proethica-case-11'),
                 (I + 'PublicWelfarePrinciple', 'proethica-case-3'),
                 (I + 'PublicWelfarePrinciple', 'proethica-case-3')]
        engine, _ = _make_engine([base], [], link_rows=links)
        (r,) = self._svc(engine).search_entities('public welfare')
        assert r['case_ids'] == [3, 11]  # deduped, sorted

    def test_case_minted_entity_links_to_own_case(self):
        minted = ('http://proethica.org/ontology/case/7#Discussion_Public_Welfare',
                  'Public Welfare in Testimony', None, 'individual',
                  I + 'PublicWelfarePrinciple', 'proethica-case-7', 'case', 0.2)
        engine, conn = _make_engine([minted], [])
        (r,) = self._svc(engine).search_entities('public welfare')
        assert r['case_ids'] == [7]
        # No base entities in the result set, so no back-link query ran.
        assert conn.execute.call_count == 2

    def test_limit_applied_after_dedup(self):
        rows = [_row(I + f'Thing{i}', f'Thing {i}', distance=0.2) for i in range(30)]
        engine, _ = _make_engine(rows, [])
        assert len(self._svc(engine).search_entities('thing', limit=5)) == 5

    def test_db_error_propagates(self):
        engine = MagicMock()
        engine.connect.side_effect = RuntimeError('db down')
        with pytest.raises(RuntimeError):
            self._svc(engine).search_entities('public welfare')


@pytest.mark.integration
class TestSearchEntitiesIntegration:
    """Hits the real local OntServe DB; skipped when it is unreachable."""

    def _results(self, query):
        try:
            return UnifiedSearchService().search_entities(query)
        except Exception as e:
            pytest.skip(f'OntServe DB unavailable: {e}')

    def test_public_welfare_surfaces_principle(self):
        results = self._results('public welfare')
        assert results, 'expected at least one entity for a corpus-central concept'
        assert any(r['category'] == 'Principle' for r in results)

    def test_conceptual_query_matches_without_shared_wording(self):
        # No entity label contains this phrasing; semantic ranking must carry it.
        results = self._results('engineer discovers a defect after project handoff')
        assert results, 'expected semantic matches for a topical scenario query'
        assert all(r['score'] is not None and r['score'] >= MIN_SEMANTIC_SCORE
                   for r in results if not r['lexical'])

    def test_nonsense_query_returns_little_or_nothing(self):
        results = self._results('zxqv blorp wibble frobnicate')
        semantic_only = [r for r in results if not r['lexical']]
        assert all(r['score'] < 0.6 for r in semantic_only)

    def test_faithful_agents_prefers_domain_over_prov(self):
        # The calibration case for FOREIGN_ONTOLOGY_WEIGHT and the plural-
        # insensitive lexical arm: prov:Agent scores highest raw but must not
        # outrank the on-point proethica obligation.
        results = self._results('Faithful Agents')
        assert results
        assert results[0]['label'] == 'Faithful Agent Obligation'
        assert results[0]['lexical'], 'plural query should still be a lexical hit'

    def test_default_lane_is_domain_only(self):
        results = self._results('Faithful Agents')
        assert results and all(r['is_domain'] for r in results)

    def test_base_class_back_links_cover_corpus(self):
        results = self._results('Public Welfare Principle')
        top = results[0]
        assert top['label'] == 'Public Welfare Principle'
        # Spot-checked 2026-07-17: 65 case ontologies carry this class.
        assert len(top['case_ids']) > 20
