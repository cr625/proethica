"""Unit tests for the free-mode deep search (increment 6, D8a-c)."""

from unittest.mock import MagicMock

import pytest

from app.services.search.deep_search_service import (
    DeepSearchService,
    component_display,
    provision_code_from_uri,
)

I = 'http://proethica.org/ontology/intermediate#'
VEC_A = [1.0] + [0.0] * 383
VEC_B = [0.0, 1.0] + [0.0] * 382


class TestProvisionCode:

    def test_underscores_to_dots_lowercased(self):
        assert provision_code_from_uri('http://proethica.org/ontology/nspe#III_1_a') == 'iii.1.a'

    def test_simple_code(self):
        assert provision_code_from_uri('http://proethica.org/ontology/nspe#I_1') == 'i.1'


def _entity(label, category, uri=None):
    return {'label': label, 'category': category,
            'uri': uri or (I + label.replace(' ', ''))}


def _service(embedding_rows, provision_rows, tag_vocab, feature_rows):
    """DeepSearchService with both stores stubbed."""
    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    def ontserve_execute(sql, params=None):
        r = MagicMock()
        if 'nspe' in str(sql):
            r.fetchall.return_value = provision_rows
        else:
            r.__iter__ = lambda self: iter(embedding_rows)
        return r
    conn.execute.side_effect = ontserve_execute

    session = MagicMock()

    def app_execute(sql, params=None):
        r = MagicMock()
        if 'unnest' in str(sql):
            r.fetchall.return_value = [(t,) for t in tag_vocab]
        else:
            r.fetchall.return_value = feature_rows
        return r
    session.execute.side_effect = app_execute

    return DeepSearchService(ontserve_engine=engine, embed_fn=lambda q: [0.1] * 384,
                             app_session=session)


def _feature_row(case_id, provisions, tags, emb_o=None, emb_s=None):
    # case_id, provisions_cited, subject_tags, R P O S Rs A E Ca Cs
    return (case_id, provisions, tags,
            None, None, str(emb_o) if emb_o else None,
            str(emb_s) if emb_s else None, None, None, None, None, None)


class TestStructureQuery:

    def test_components_from_entity_lane(self):
        ents = [_entity('Safety Obligation', 'Obligation'),
                _entity('Risk State', 'State'),
                _entity('No Category Thing', None)]
        svc = _service(
            embedding_rows=[(ents[0]['uri'], str(VEC_A)), (ents[1]['uri'], str(VEC_B))],
            provision_rows=[], tag_vocab=[], feature_rows=[])
        s = svc.structure_query('engineer discovers a defect', ents)
        assert set(s['components']) == {'O', 'S'}
        assert s['components']['O']['entities'] == ['Safety Obligation']

    def test_provisions_floored_and_coded(self):
        svc = _service(
            embedding_rows=[],
            provision_rows=[
                ('http://proethica.org/ontology/nspe#I_1', 'Fundamental Canon I.1', 0.5),
                ('http://proethica.org/ontology/nspe#II_4_e', 'Rule II.4.e', 0.75),
            ],
            tag_vocab=[], feature_rows=[])
        s = svc.structure_query('public safety paramount', [])
        # 1-0.5=0.5 passes the 0.30 floor; 1-0.75=0.25 does not.
        assert s['provisions'] == ['i.1']

    def test_tags_via_token_subset(self):
        svc = _service(embedding_rows=[], provision_rows=[],
                       tag_vocab=['Faithful Agents and Trustees', 'Duty to the Public'],
                       feature_rows=[])
        s = svc.structure_query('faithful agents', [])
        assert s['tags'] == ['Faithful Agents and Trustees']


class TestRankCases:

    def _structure(self, provisions=None, tags=None):
        return {'components': {'O': {'vector': VEC_A, 'entities': ['Safety Obligation']},
                               'S': {'vector': VEC_B, 'entities': ['Risk State']}},
                'provisions': provisions or [], 'provision_labels': [],
                'tags': tags or []}

    def test_shared_component_ranking(self):
        rows = [
            _feature_row(1, [], [], emb_o=VEC_A, emb_s=VEC_B),   # perfect on both
            _feature_row(2, [], [], emb_o=VEC_B, emb_s=VEC_A),   # orthogonal
            _feature_row(3, [], []),                             # no shared components
        ]
        svc = _service([], [], [], rows)
        ranked = svc.rank_cases(self._structure())
        assert [r['case_id'] for r in ranked] == [1, 2]  # case 3 dropped
        assert ranked[0]['score'] > ranked[1]['score']
        assert set(ranked[0]['per_component']) == {'O', 'S'}

    def test_provision_weight_active_only_when_query_has_provisions(self):
        rows = [_feature_row(1, ['I.1'], [], emb_o=VEC_A)]
        svc = _service([], [], [], rows)
        without = svc.rank_cases(self._structure())[0]
        assert 'provision_overlap' not in without['feature_scores']

        rows = [_feature_row(1, ['I.1'], [], emb_o=VEC_A)]
        svc = _service([], [], [], rows)
        with_p = svc.rank_cases(self._structure(provisions=['i.1']))[0]
        # Case-insensitive match against the corpus casing.
        assert with_p['feature_scores']['provision_overlap'] == 1.0
        assert with_p['provision_matches'] == ['i.1']

    def test_provision_match_raises_score(self):
        base = self._structure()
        rows = lambda: [_feature_row(1, ['I.1'], [], emb_o=VEC_A),
                        _feature_row(2, ['III.9'], [], emb_o=VEC_A)]
        svc = _service([], [], [], rows())
        neutral = {r['case_id']: r['score'] for r in svc.rank_cases(base)}
        assert neutral[1] == pytest.approx(neutral[2])

        svc = _service([], [], [], rows())
        ranked = svc.rank_cases(self._structure(provisions=['i.1']))
        assert ranked[0]['case_id'] == 1
        assert ranked[0]['score'] > ranked[1]['score']

    def test_tag_overlap_active_only_with_query_tags(self):
        rows = [_feature_row(1, [], ['Duty to the Public'], emb_o=VEC_A)]
        svc = _service([], [], [], rows)
        r = svc.rank_cases(self._structure(tags=['Duty to the Public']))[0]
        assert r['feature_scores']['tag_overlap'] == 1.0
        assert r['tag_matches'] == ['Duty to the Public']


class TestComponentDisplay:

    def test_top_contributors_with_canonical_colors(self):
        chips = component_display({'O': 0.9, 'S': 0.2, 'P': 0.5}, top=2)
        assert [c['label'] for c in chips] == ['Obligations', 'Principles']
        assert all(c['color'] for c in chips)


@pytest.mark.integration
class TestDeepSearchIntegration:
    """Real DBs; skipped when unavailable. Requires app context for db.session."""

    def test_structure_and_rank(self):
        try:
            from app import create_app
            app = create_app()
        except Exception as e:
            pytest.skip(f'app unavailable: {e}')
        with app.app_context():
            from app.services.search.unified_search_service import UnifiedSearchService
            svc = DeepSearchService()
            try:
                ents = UnifiedSearchService().search_entities(
                    'engineer discovers a defect after project handoff')
                s = svc.structure_query('engineer discovers a defect after project handoff', ents)
                assert len(s['components']) >= 2
                ranked = svc.rank_cases(s, limit=5)
            except Exception as e:
                pytest.skip(f'databases unavailable: {e}')
            assert ranked and all(r['score'] > 0 for r in ranked)
            assert set(ranked[0]['per_component']) <= {'R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs'}
