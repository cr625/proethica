"""Shared DB / OntServe / LLM-free OntServeCommitService stub used by
tests/unit/test_commit_service_golden.py and tests/extraction/test_match_honoring.py.

The service is built with ``object.__new__`` (no ``__init__``, no real OntServe
paths) and pointed at a tmp ontologies dir; the touchpoints that would reach a
database or OntServe are stubbed: the curated-chain category resolver
(``_established_core_category``), edge provenance recording, the case-header
lookup (``case_header.case_header_fields``), edge materialization,
canonicalization and the role-axis resolver.
"""
from rdflib import Graph

from app.services.commit.ontserve_commit_service import OntServeCommitService


def make_stub_commit_service(tmp_path, monkeypatch, *, chain_resolver, header_fields):
    """OntServeCommitService wired to ``tmp_path`` with every DB / OntServe
    touchpoint stubbed. ``chain_resolver`` stands in for
    ``_established_core_category`` (local name -> core category or None);
    ``header_fields`` is the dict ``case_header.case_header_fields`` returns
    for any case id (title / case_number / decade)."""
    import app.services.extraction.canonicalization as canon
    import app.services.extraction.edge_materialization as edge_mat
    import app.services.extraction.category_resolver as category_resolver
    import app.services.commit.case_header as case_header

    svc = object.__new__(OntServeCommitService)
    svc.ontologies_dir = tmp_path
    svc._established_core_category = chain_resolver
    # The header helper reads the Document row; stub it with the given facts.
    monkeypatch.setattr(case_header, 'case_header_fields', lambda case_id: dict(header_fields))
    svc._record_edge_provenance = lambda *a, **k: None
    monkeypatch.setattr(edge_mat, 'materialize_edges_on_ttl',
                        lambda case_id, ttl_path: {'stubbed': True})

    # The canonicalize_ttl contract includes the post-rewrite graph under
    # '_graph' (consumed by the post-canonicalization role-axis re-sweep);
    # the stub honors it by parsing the on-disk TTL unchanged.
    def _stub_canonicalize(case_id, ttl_path):
        g = Graph()
        g.parse(str(ttl_path), format='turtle')
        return {'stubbed': True, '_graph': g}

    monkeypatch.setattr(canon, 'canonicalize_ttl', _stub_canonicalize)
    monkeypatch.setattr(category_resolver, 'resolve_role_axis', lambda uri: None)
    return svc
