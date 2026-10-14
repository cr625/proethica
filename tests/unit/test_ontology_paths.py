"""Ontology TTL path resolution must honour the configured OntServe location.

Regression coverage for the production template-24 render failure
(Oct 5/8 2026): rpo_edges._default_ontology_paths hard-coded
``parents[4] / "OntServe" / "ontologies"``, which exists only in the
development checkout layout. On the droplet the checkout is
/opt/ontserve and the location is configured through
ONTSERVE_BASE_PATH / ONTSERVE_ONTOLOGIES_PATH, so the render raised
FileNotFoundError for proethica-core.ttl.
"""
import shutil
from pathlib import Path


def test_ontologies_path_honours_ontologies_env(monkeypatch, tmp_path):
    from app.services.ontserve import ontserve_config
    monkeypatch.setenv('ONTSERVE_ONTOLOGIES_PATH', str(tmp_path))
    assert ontserve_config.get_ontserve_ontologies_path() == tmp_path


def test_ontologies_path_derives_from_base_env(monkeypatch, tmp_path):
    from app.services.ontserve import ontserve_config
    monkeypatch.delenv('ONTSERVE_ONTOLOGIES_PATH', raising=False)
    monkeypatch.setenv('ONTSERVE_BASE_PATH', str(tmp_path))
    assert ontserve_config.get_ontserve_ontologies_path() == tmp_path / 'ontologies'


def test_rpo_default_paths_honour_ontologies_env(monkeypatch, tmp_path):
    from app.services.extraction.rpo_edges import _default_ontology_paths
    monkeypatch.setenv('ONTSERVE_ONTOLOGIES_PATH', str(tmp_path))
    core, intermediate = _default_ontology_paths()
    assert core == tmp_path / 'proethica-core.ttl'
    assert intermediate == tmp_path / 'proethica-intermediate.ttl'


def test_rpo_default_paths_resolve_to_existing_files():
    from app.services.extraction.rpo_edges import _default_ontology_paths
    core, intermediate = _default_ontology_paths()
    assert Path(core).is_file()
    assert Path(intermediate).is_file()


def test_archetype_default_ttl_honours_ontologies_env(monkeypatch, tmp_path):
    from app.services.extraction import role_archetype_resolver
    monkeypatch.setenv('ONTSERVE_ONTOLOGIES_PATH', str(tmp_path))
    assert role_archetype_resolver._default_ttl() == str(
        tmp_path / 'proethica-intermediate.ttl')


def test_property_axioms_block_reads_configured_core_ttl(monkeypatch, tmp_path):
    """The template-24 render path: property_axioms_block with no explicit
    TTL must parse proethica-core.ttl from the configured ontologies dir
    (a production-layout directory), not a hard-coded checkout path."""
    from app.services.extraction import rpo_edges
    real_core, _ = rpo_edges._default_ontology_paths()
    shutil.copy(real_core, tmp_path / 'proethica-core.ttl')
    monkeypatch.setenv('ONTSERVE_ONTOLOGIES_PATH', str(tmp_path))
    block = rpo_edges.property_axioms_block()
    assert 'proeth-core:hasObligation' in block
