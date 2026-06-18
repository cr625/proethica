"""Type-safe entity match override: core-category resolution for the override gate.

The set_match route rejects an override whose target class resolves to a different
core component than the entity's extraction type. These tests cover the resolver
that supplies the target category (curated resolver first, OntServe parent_uri
subClassOf walk as the fallback for per-case classes).
"""
from unittest.mock import patch

from app.routes.scenario_pipeline.entity_review import ontserve_ops as ops


def _fake_engine(chain):
    """An engine whose connection resolves parent_uri from a dict chain."""
    class FakeResult:
        def __init__(self, parent):
            self._parent = parent

        def fetchone(self):
            return (self._parent,) if self._parent else None

    class FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, _stmt, params):
            return FakeResult(chain.get(params['u']))

    class FakeEngine:
        def connect(self):
            return FakeConn()

    return FakeEngine()


def test_curated_resolver_takes_precedence():
    with patch('app.services.extraction.category_resolver.resolve_core_category',
               return_value='Obligation'):
        assert ops._resolve_class_core_category('any://uri') == 'Obligation'


def test_chain_walk_resolves_per_case_class_to_core():
    chain = {
        'http://proethica.org/ontology/case/7#FooObligation':
            'http://proethica.org/ontology/intermediate#BarObligation',
        'http://proethica.org/ontology/intermediate#BarObligation':
            'http://proethica.org/ontology/core#Obligation',
    }
    with patch('app.services.extraction.category_resolver.resolve_core_category',
               return_value=None), \
            patch('app.services.ontserve_config.get_ontserve_db_url',
                  return_value='postgresql://x'), \
            patch('sqlalchemy.create_engine', return_value=_fake_engine(chain)):
        cat = ops._resolve_class_core_category(
            'http://proethica.org/ontology/case/7#FooObligation')
    assert cat == 'Obligation'


def test_chain_walk_returns_none_for_orphan_class():
    with patch('app.services.extraction.category_resolver.resolve_core_category',
               return_value=None), \
            patch('app.services.ontserve_config.get_ontserve_db_url',
                  return_value='postgresql://x'), \
            patch('sqlalchemy.create_engine', return_value=_fake_engine({})):
        cat = ops._resolve_class_core_category(
            'http://proethica.org/ontology/case/7#OrphanThing')
    assert cat is None
