"""
Unit tests for embedding-based duplicate detection in AutoCommitService._check_duplicate.

The matcher embeds 'label: definition' via all-MiniLM-L6-v2 and runs a single
pgvector cosine query against ontology_entities. These tests mock both
EmbeddingService (to control the candidate vector) and create_engine (to
control the row returned by the SQL query). No real model, no real DB,
no Flask app context.

Coverage:
  - High cosine (>= 0.85) -> (uri, score) auto-link band
  - Medium cosine (0.70-0.85) -> (uri, score) review-flag band
  - Low cosine (< 0.70) -> None (novel class)
  - SQL returns no row -> None
  - EmbeddingService raises -> None (and caller swallows)
  - Type filter: marker LIKE clauses included in params for known type
  - Plural/singular type variants both produce a usable marker
  - Unknown semantic type falls back to title-cased form
  - Empty entity_type omits LIKE filter entirely
  - _check_duplicate: exact label -> (uri, 1.0)
  - _check_duplicate: substring + type-marker match -> (uri, 0.87)
  - _check_duplicate: substring with wrong type -> falls through
  - _check_duplicate: empty cache + no SQL row -> None
  - _check_duplicate: definition forwarded into embedding text
"""

from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(cache_entries: Optional[Dict[str, Dict]] = None):
    """Create a bare AutoCommitService bypassing __init__.

    Skips Flask app and DB setup so the tests run in plain pytest.
    """
    from app.services.auto_commit_service import AutoCommitService
    service = object.__new__(AutoCommitService)
    service._versioned_commit = True
    service._ontserve_classes_cache = (
        cache_entries if cache_entries is not None else {}
    )
    return service


def _make_row(uri: str, label: str, cosine: float):
    """Mimic a SQLAlchemy Row that supports attribute access."""
    row = MagicMock()
    row.uri = uri
    row.label = label
    row.cosine = cosine
    return row


def _patch_pgvector(query_vec: List[float], sql_row, captured: Dict[str, Any]):
    """Context-manager helper: patches EmbeddingService and create_engine.

    sql_row may be a row mock, None (no match), or an Exception (raised by
    fetchone). captured["params"] is filled with the SQL bind params after
    execute() runs so tests can assert on the LIKE filters.
    """
    from contextlib import ExitStack

    stack = ExitStack()
    es_patch = stack.enter_context(
        patch("app.services.embedding_service.EmbeddingService")
    )
    engine_patch = stack.enter_context(
        patch("app.services.auto_commit_service.create_engine")
    )

    # candidate-side embedding
    mock_es_instance = MagicMock()
    mock_es_instance._get_local_embedding.return_value = query_vec
    es_patch.get_instance.return_value = mock_es_instance

    # SQL query result
    mock_conn = MagicMock()

    def _execute(sql, params=None):
        sql_str = str(sql)
        # SET LOCAL ivfflat.probes runs before the SELECT and has no params;
        # only capture the SELECT call so tests can inspect bind values.
        if "SELECT" in sql_str.upper() and params is not None:
            captured["params"] = dict(params)
            captured["sql"] = sql_str
        result = MagicMock()
        if isinstance(sql_row, Exception):
            result.fetchone.side_effect = sql_row
        else:
            result.fetchone.return_value = sql_row
        return result

    mock_conn.execute.side_effect = _execute
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    engine_patch.return_value = mock_engine

    return stack, mock_es_instance


def _run_embedding(label, entity_type, definition, sql_row,
                   query_vec=None, cache_entries=None):
    """Drive _check_embedding_duplicate end to end with mocked deps.

    Returns (result, captured) where result is the function's return and
    captured has 'params' and 'sql' from the simulated SQL call.
    """
    if query_vec is None:
        query_vec = [0.1] * 384  # arbitrary; matcher does not see the vector
    captured: Dict[str, Any] = {}
    service = _make_service(cache_entries)
    with _patch_pgvector(query_vec, sql_row, captured)[0]:
        result = service._check_embedding_duplicate(label, definition, entity_type)
    return result, captured


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

OBL_URI = "http://proethica.org/ontology/intermediate#ConfidentialityObligation"
ROLE_URI = "http://proethica.org/ontology/intermediate#FaithfulAgentRole"
CAP_URI = "http://proethica.org/ontology/intermediate#CompetenceCapability"

LEXICAL_CACHE = {
    OBL_URI: {
        'label': 'Confidentiality Obligation',
        'type': 'class',
        'definition': 'Duty to protect client information',
    },
    ROLE_URI: {
        'label': 'Faithful Agent Role',
        'type': 'class',
        'definition': 'Engineer acting as faithful agent for client',
    },
    CAP_URI: {
        'label': 'Competence Capability',
        'type': 'class',
        'definition': 'Professional competence and technical expertise',
    },
}


# ---------------------------------------------------------------------------
# _check_embedding_duplicate
# ---------------------------------------------------------------------------

class TestCheckEmbeddingDuplicate:

    def test_high_cosine_returns_uri_and_score(self):
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.92)
        result, _ = _run_embedding("Some Duty", "obligation", "", row)
        assert result is not None
        uri, score = result
        assert uri == OBL_URI
        assert score == pytest.approx(0.92)

    def test_medium_cosine_returns_uri_and_score(self):
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.77)
        result, _ = _run_embedding("Some Duty", "obligation", "", row)
        assert result is not None
        uri, score = result
        assert uri == OBL_URI
        assert 0.70 <= score < 0.85

    def test_low_cosine_returns_none(self):
        """Top match below EMBEDDING_MATCH_MIN is rejected."""
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.60)
        result, _ = _run_embedding("Some Duty", "obligation", "", row)
        assert result is None

    def test_no_match_returns_none(self):
        """Empty SQL result (e.g., empty table or all filtered out)."""
        result, _ = _run_embedding("Some Duty", "obligation", "", None)
        assert result is None

    def test_embedding_service_raises_returns_none(self):
        from contextlib import ExitStack
        captured: Dict[str, Any] = {}

        service = _make_service()
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            mock_es = MagicMock()
            mock_es._get_local_embedding.side_effect = RuntimeError("boom")
            es_patch.get_instance.return_value = mock_es

            result = service._check_embedding_duplicate("X", "", "obligation")
        assert result is None

    def test_type_marker_added_to_params_for_obligation(self):
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.90)
        _, captured = _run_embedding("X", "obligation", "", row)
        # Singular obligation -> 'Obligation' marker
        marker_values = [v for k, v in captured["params"].items() if k.startswith("m")]
        assert any("Obligation" in v for v in marker_values), captured["params"]

    def test_plural_type_marker_singularizes(self):
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.90)
        _, captured = _run_embedding("X", "obligations", "", row)
        marker_values = [v for k, v in captured["params"].items() if k.startswith("m")]
        # Both plural and singular forms expected
        assert any("Obligation" in v for v in marker_values), captured["params"]

    def test_capability_plural_singularizes_to_capability(self):
        """'capabilities' (irregular -ies plural) maps to 'Capability'."""
        row = _make_row(CAP_URI, "Competence Capability", 0.90)
        _, captured = _run_embedding("X", "capabilities", "", row)
        marker_values = [v for k, v in captured["params"].items() if k.startswith("m")]
        assert any("Capability" in v for v in marker_values), captured["params"]

    def test_unknown_semantic_type_falls_back_to_titlecase(self):
        """Vocabulary outside the nine D-tuple components still produces a
        usable marker (title-cased version of the raw input)."""
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.90)
        _, captured = _run_embedding("X", "policy", "", row)
        marker_values = [v for k, v in captured["params"].items() if k.startswith("m")]
        # 'policy' -> 'Policy' fallback
        assert any("Policy" in v for v in marker_values), captured["params"]

    def test_all_nine_dtuple_types_have_markers(self):
        """Each D-tuple component (singular and plural) maps to a marker."""
        from app.services.auto_commit_service import _semantic_type_markers
        for sing, plural, expected in [
            ('role', 'roles', 'Role'),
            ('principle', 'principles', 'Principle'),
            ('obligation', 'obligations', 'Obligation'),
            ('state', 'states', 'State'),
            ('resource', 'resources', 'Resource'),
            ('action', 'actions', 'Action'),
            ('event', 'events', 'Event'),
            ('capability', 'capabilities', 'Capability'),
            ('constraint', 'constraints', 'Constraint'),
        ]:
            assert expected in _semantic_type_markers(sing), sing
            assert expected in _semantic_type_markers(plural), plural

    def test_empty_entity_type_omits_marker_filter(self):
        """No semantic type -> no LIKE clauses in params (only :vec)."""
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.90)
        _, captured = _run_embedding("X", "", "", row)
        marker_keys = [k for k in captured["params"].keys() if k.startswith("m")]
        assert marker_keys == [], captured["params"]
        assert "vec" in captured["params"]

    def test_definition_concatenated_into_embedding_text(self):
        """The candidate text passed to EmbeddingService is 'label: definition'."""
        row = _make_row(OBL_URI, "Confidentiality Obligation", 0.90)
        captured: Dict[str, Any] = {}
        service = _make_service()

        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            mock_es = MagicMock()
            mock_es._get_local_embedding.return_value = [0.1] * 384
            es_patch.get_instance.return_value = mock_es

            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = row
            mock_engine = MagicMock()
            mock_engine.connect.return_value.__enter__.return_value = mock_conn
            engine_patch.return_value = mock_engine

            service._check_embedding_duplicate(
                "Disclosure Duty",
                "Engineer must report safety risks",
                "obligation",
            )

        called_with = mock_es._get_local_embedding.call_args[0][0]
        assert called_with == "Disclosure Duty: Engineer must report safety risks"


# ---------------------------------------------------------------------------
# _check_duplicate end-to-end (lexical + embedding fallthrough)
# ---------------------------------------------------------------------------

class TestCheckDuplicate:

    def test_exact_label_returns_confidence_one(self):
        service = _make_service(LEXICAL_CACHE)
        result = service._check_duplicate("Confidentiality Obligation", "obligation")
        assert result == (OBL_URI, 1.0)

    def test_exact_match_case_insensitive(self):
        service = _make_service(LEXICAL_CACHE)
        result = service._check_duplicate("FAITHFUL AGENT ROLE", "role")
        assert result == (ROLE_URI, 1.0)

    def test_substring_match_returns_0_87(self):
        service = _make_service(LEXICAL_CACHE)
        result = service._check_duplicate("Faithful", "role")
        assert result is not None
        uri, conf = result
        assert uri == ROLE_URI
        assert conf == pytest.approx(0.87)

    def test_substring_wrong_type_falls_through_to_embedding(self):
        """Substring 'Competence' matches a Capability class label, but candidate
        type 'obligation' should make the URI-marker filter reject it. The flow
        then reaches the embedding path, which we mock to return None."""
        service = _make_service(LEXICAL_CACHE)
        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            es_patch.get_instance.return_value._get_local_embedding.return_value = [0.1] * 384
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            engine_patch.return_value.connect.return_value.__enter__.return_value = mock_conn

            result = service._check_duplicate("Competence", "obligation")
        assert result is None

    def test_unknown_label_falls_through_to_embedding_match(self):
        service = _make_service(LEXICAL_CACHE)
        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            es_patch.get_instance.return_value._get_local_embedding.return_value = [0.1] * 384
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = _make_row(
                OBL_URI, "Confidentiality Obligation", 0.91,
            )
            engine_patch.return_value.connect.return_value.__enter__.return_value = mock_conn

            result = service._check_duplicate(
                "Client Data Protection Duty", "obligation"
            )
        assert result is not None
        uri, conf = result
        assert uri == OBL_URI
        assert conf == pytest.approx(0.91)

    def test_unknown_label_below_threshold_returns_none(self):
        service = _make_service(LEXICAL_CACHE)
        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            es_patch.get_instance.return_value._get_local_embedding.return_value = [0.1] * 384
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = _make_row(
                OBL_URI, "Confidentiality Obligation", 0.50,
            )
            engine_patch.return_value.connect.return_value.__enter__.return_value = mock_conn

            result = service._check_duplicate(
                "CompletelyUnrelatedConcept999", "obligation"
            )
        assert result is None

    def test_empty_cache_no_sql_row_returns_none(self):
        service = _make_service({})
        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            es_patch.get_instance.return_value._get_local_embedding.return_value = [0.1] * 384
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = None
            engine_patch.return_value.connect.return_value.__enter__.return_value = mock_conn

            result = service._check_duplicate("Any Label", "role")
        assert result is None

    def test_definition_passed_through_to_embedding(self):
        service = _make_service(LEXICAL_CACHE)
        from contextlib import ExitStack
        with ExitStack() as stack:
            es_patch = stack.enter_context(
                patch("app.services.embedding_service.EmbeddingService")
            )
            engine_patch = stack.enter_context(
                patch("app.services.auto_commit_service.create_engine")
            )
            mock_es = MagicMock()
            mock_es._get_local_embedding.return_value = [0.1] * 384
            es_patch.get_instance.return_value = mock_es
            mock_conn = MagicMock()
            mock_conn.execute.return_value.fetchone.return_value = _make_row(
                OBL_URI, "Confidentiality Obligation", 0.88,
            )
            engine_patch.return_value.connect.return_value.__enter__.return_value = mock_conn

            service._check_duplicate(
                "Duty of Confidentiality", "obligation",
                "Engineer must keep client secrets",
            )
        passed = mock_es._get_local_embedding.call_args[0][0]
        assert "Engineer must keep client secrets" in passed
