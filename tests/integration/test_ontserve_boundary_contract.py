"""Contract test for the ProEthica -> OntServe commit-path boundary.

ProEthica's commit path (app/services/commit/ontserve_commit_service.py,
auto_commit_service.py) couples to OntServe in two ways that NO Python import or
ordinary test would catch if OntServe drifts:

  1. Filesystem / subprocess: it shells `OntServe/tools/sync_ontology_to_db.py`
     via the OntServe venv and writes into `OntServe/ontologies/`, all by raw
     path (ontserve_commit_service.py:60-67,943).
  2. Hand-written SQL into the foreign `ontserve` Postgres DB. Critically,
     OntServe's own SQLAlchemy models (web/models.py) define NO Concept class --
     the `concepts` / `concept_versions` tables and the ProEthica-specific
     columns on them exist only in the live DB, so ProEthica's SQL column lists
     are the ONLY place that schema contract is encoded, and it is encoded in
     string literals. A rename/drop in OntServe surfaces only at commit time in
     production.

This test makes that otherwise-invisible contract fail LOUDLY: it asserts the
subprocess target + venv + ontologies dir exist, and that each `ontserve` table
still carries the exact columns the commit SQL reads/writes (subset check, so
benign OntServe column additions do not false-fail; a rename/drop names the
missing column). It exercises the SAME resolution helpers the commit path uses
(get_ontserve_base_path / get_ontserve_db_config), so the path/cred resolution is
itself covered.

Boundary reference: docs-internal/architecture/ontserve-boundary.md.

Gated behind the `live_db` marker (pytest.ini excludes it from the default
suite); it needs the sibling OntServe checkout present and the `ontserve` DB
reachable, and SKIPS gracefully when either is absent. Run explicitly with:
    pytest tests/integration/test_ontserve_boundary_contract.py -m live_db -v
"""
import pytest

pytestmark = [pytest.mark.live_db, pytest.mark.integration]

# The exact columns the commit-path SQL reads/writes, per table, verified against
# ontserve_commit_service.py (concepts INSERT ~1579 + UPDATE ~1670 + the
# concept_versions SELECT ... FROM concepts) and auto_commit_service.py
# (ontologies/ontology_entities/ontology_versions clear path ~1118-1140, the
# embedding read ~505). Subset semantics: each table must contain AT LEAST these.
REQUIRED_COLUMNS = {
    "concepts": {
        "uuid", "domain_id", "uri", "label", "primary_type", "description",
        "status", "case_id", "extraction_run_version", "is_current",
        "entity_class", "extraction_method", "source_document",
        "confidence_score", "created_by", "metadata", "semantic_label",
        "version_number", "updated_at", "updated_by", "id",
    },
    "concept_versions": {
        "concept_id", "version_number", "uri", "label", "semantic_label",
        "primary_type", "description", "status", "metadata",
        "changed_fields", "change_reason", "changed_by",
    },
    "ontologies": {"id", "name"},
    "ontology_entities": {"ontology_id", "entity_type", "uri", "embedding", "label"},
    "ontology_versions": {"ontology_id"},
    "domains": {"id", "name"},
}


@pytest.fixture(scope="module")
def ontserve_base():
    """The OntServe checkout path via the commit path's own resolver, or skip."""
    from app.services.ontserve.ontserve_config import get_ontserve_base_path
    try:
        base = get_ontserve_base_path()
    except RuntimeError as exc:
        pytest.skip(f"OntServe checkout not resolvable: {exc}")
    if not base.is_dir():
        pytest.skip(f"OntServe checkout not present at {base}")
    return base


@pytest.fixture(scope="module")
def ontserve_conn():
    """A connection to the ontserve DB via the commit path's own config, or skip."""
    import psycopg2
    from app.services.ontserve.ontserve_config import get_ontserve_db_config
    try:
        conn = psycopg2.connect(connect_timeout=5, **get_ontserve_db_config())
    except Exception as exc:  # noqa: BLE001 -- any connect failure -> skip, not error
        pytest.skip(f"ontserve DB not reachable: {exc}")
    yield conn
    conn.close()


def test_subprocess_and_filesystem_targets_exist(ontserve_base):
    """The commit path shells these by raw path; a move breaks prod silently."""
    missing = []
    for rel, kind in [
        ("tools/sync_ontology_to_db.py", "file"),
        ("venv-ontserve/bin/python", "file"),
        ("ontologies", "dir"),
    ]:
        p = ontserve_base / rel
        ok = p.is_dir() if kind == "dir" else p.exists()
        if not ok:
            missing.append(f"{rel} ({kind})")
    assert not missing, (
        "OntServe checkout is missing commit-path targets (ProEthica commits "
        f"would fail at runtime): {missing}"
    )


@pytest.mark.parametrize("table,required", sorted(REQUIRED_COLUMNS.items()))
def test_ontserve_table_has_required_columns(ontserve_conn, table, required):
    """Each ontserve table must carry the columns the commit SQL depends on."""
    with ontserve_conn.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
        actual = {r[0] for r in cur.fetchall()}
    assert actual, f"ontserve table '{table}' does not exist (commit contract broken)"
    missing = required - actual
    assert not missing, (
        f"ontserve.{table} is missing columns the ProEthica commit path writes: "
        f"{sorted(missing)}"
    )


def test_engineering_ethics_domain_row_exists(ontserve_conn):
    """The commit path resolves domain_id by name='engineering-ethics' and silently
    NULLs it if absent (ontserve_commit_service.py ~1566); assert the row exists."""
    with ontserve_conn.cursor() as cur:
        cur.execute("SELECT 1 FROM domains WHERE name = %s LIMIT 1", ("engineering-ethics",))
        assert cur.fetchone() is not None, (
            "ontserve.domains has no row name='engineering-ethics'; committed case "
            "concepts would get domain_id=NULL"
        )
