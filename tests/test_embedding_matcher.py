"""
Unit tests for embedding-based duplicate detection in AutoCommitService._check_duplicate.

Fully mocked: no SentenceTransformer model, no Flask app context, no database.
The embedding index is built directly on the service instance; only the
query-time embedding call is patched.

Coverage:
  - High cosine (>= 0.85) -> auto-link band
  - Medium cosine (0.70-0.85) -> review-flag band
  - Low cosine (< 0.70) -> novel class (None)
  - Type filter prevents cross-type matching
  - Plural/singular type variants pass filter
  - Best-match selection among multiple same-type classes
  - Empty index returns None without error
  - _check_duplicate: exact label -> (uri, 1.0)
  - _check_duplicate: substring + type match -> (uri, 0.87)
  - _check_duplicate: wrong type substring -> falls through to embedding
  - _check_duplicate: unknown label falls through to embedding
  - _check_duplicate: empty cache -> None
"""

import numpy as np
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit_vec(seed: int, dim: int = 384) -> np.ndarray:
    """Deterministic unit vector."""
    rng = np.random.RandomState(seed)
    v = rng.randn(dim).astype(np.float32)
    return v / np.linalg.norm(v)


def _vec_with_cosine(target: np.ndarray, cosine: float) -> np.ndarray:
    """Unit vector with specified cosine similarity to *target*.

    Decomposition: result = cosine*target + sin*perp, where perp is orthogonal.
    """
    target = target.astype(np.float32)
    # Build a vector orthogonal to target
    perp = np.zeros_like(target)
    perp[0] = -target[1]
    perp[1] = target[0]
    if np.linalg.norm(perp) < 1e-6:
        perp = np.zeros_like(target)
        perp[1] = 1.0
    perp = perp - np.dot(perp, target) * target
    norm_p = np.linalg.norm(perp)
    if norm_p < 1e-6:
        return target.copy()
    perp = perp / norm_p
    sin_val = float(np.sqrt(max(0.0, 1.0 - cosine ** 2)))
    result = cosine * target + sin_val * perp
    return result / np.linalg.norm(result)


def _make_service(index_uris, index_types, index_vectors, cache_entries=None):
    """Create a bare AutoCommitService with a pre-built embedding index.

    Bypasses __init__ entirely to avoid Flask/DB dependencies.
    """
    from app.services.auto_commit_service import AutoCommitService

    service = object.__new__(AutoCommitService)
    service._versioned_commit = True

    if index_vectors:
        matrix = np.stack(
            [v / np.linalg.norm(v) for v in index_vectors], axis=0
        ).astype(np.float32)
    else:
        matrix = None

    service._embedding_index = {
        'matrix': matrix,
        'uris': list(index_uris),
        'types': list(index_types),
    }
    service._ontserve_classes_cache = cache_entries if cache_entries is not None else {}
    return service


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

OBL_URI = "http://proethica.org/ontology/intermediate#ConfidentialityObligation"
ROLE_URI = "http://proethica.org/ontology/intermediate#FaithfulAgentRole"
CAP_URI = "http://proethica.org/ontology/intermediate#CompetenceCapability"

OBL_VEC = _make_unit_vec(seed=1)
ROLE_VEC = _make_unit_vec(seed=2)
CAP_VEC = _make_unit_vec(seed=3)

INDEX_URIS = [OBL_URI, ROLE_URI, CAP_URI]
INDEX_TYPES = ["obligation", "role", "capability"]
INDEX_VECTORS = [OBL_VEC, ROLE_VEC, CAP_VEC]

LEXICAL_CACHE = {
    OBL_URI: {
        'label': 'Confidentiality Obligation',
        'type': 'obligation',
        'definition': 'Duty to protect client information',
    },
    ROLE_URI: {
        'label': 'Faithful Agent Role',
        'type': 'role',
        'definition': 'Engineer acting as faithful agent for client',
    },
    CAP_URI: {
        'label': 'Competence Capability',
        'type': 'capability',
        'definition': 'Professional competence and technical expertise',
    },
}


# ---------------------------------------------------------------------------
# _check_embedding_duplicate tests
# ---------------------------------------------------------------------------

class TestCheckEmbeddingDuplicate:
    """Direct unit tests for the embedding similarity path."""

    def _run(self, query_vec, entity_type, *, service=None):
        if service is None:
            service = _make_service(INDEX_URIS, INDEX_TYPES, INDEX_VECTORS)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query_vec
        with patch(
            "app.services.auto_commit_service.EmbeddingService"
        ) as MockCls:
            MockCls.get_instance.return_value = mock_emb
            return service._check_embedding_duplicate(
                "Candidate Label", "some definition", entity_type
            )

    def test_high_cosine_returns_uri_and_high_confidence(self):
        """cosine >= 0.85 returns (uri, score >= 0.85) -> auto-link band."""
        query = _vec_with_cosine(OBL_VEC, 0.92)
        result = self._run(query, "obligation")
        assert result is not None
        uri, score = result
        assert uri == OBL_URI
        assert score >= 0.85, f"Expected score >= 0.85, got {score:.4f}"

    def test_medium_cosine_returns_uri_and_medium_confidence(self):
        """0.70 <= cosine < 0.85 returns (uri, score) in that range -> review-flag."""
        query = _vec_with_cosine(OBL_VEC, 0.77)
        result = self._run(query, "obligation")
        assert result is not None
        uri, score = result
        assert uri == OBL_URI
        assert 0.70 <= score < 0.85, f"Expected [0.70, 0.85), got {score:.4f}"

    def test_low_cosine_returns_none(self):
        """cosine < 0.70 returns None -> treat as novel class."""
        query = _vec_with_cosine(OBL_VEC, 0.60)
        result = self._run(query, "obligation")
        assert result is None

    def test_type_filter_blocks_cross_type_match(self):
        """Obligation candidate must not match a capability class."""
        # Very close to CAP_VEC but entity_type='obligation'
        query = _vec_with_cosine(CAP_VEC, 0.95)
        result = self._run(query, "obligation")
        # CAP_URI must not be returned (type mismatch)
        assert result is None or (result[0] != CAP_URI)

    def test_plural_type_passes_filter(self):
        """'obligations' (plural) should match type 'obligation' in index."""
        query = _vec_with_cosine(OBL_VEC, 0.90)
        result = self._run(query, "obligations")
        assert result is not None
        uri, score = result
        assert uri == OBL_URI

    def test_no_type_filter_matches_best_overall(self):
        """Empty entity_type skips filtering; best cosine across all classes wins."""
        query = _vec_with_cosine(ROLE_VEC, 0.88)
        result = self._run(query, "")
        assert result is not None
        uri, score = result
        assert uri == ROLE_URI

    def test_empty_index_returns_none(self):
        """Empty embedding index returns None without raising."""
        service = _make_service([], [], [])
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = OBL_VEC
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_embedding_duplicate("Any", "", "obligation")
        assert result is None

    def test_returns_best_among_same_type(self):
        """When multiple same-type classes exist, returns the highest-cosine one."""
        obl2_vec = _make_unit_vec(seed=10)
        obl2_uri = "http://proethica.org/ontology/intermediate#NonDisclosureObligation"
        uris = [OBL_URI, obl2_uri]
        types = ["obligation", "obligation"]
        vectors = [OBL_VEC, obl2_vec]
        service = _make_service(uris, types, vectors)

        # Query is very close to obl2_vec
        query = _vec_with_cosine(obl2_vec, 0.95)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_embedding_duplicate(
                "Non-Disclosure Duty", "", "obligation"
            )

        assert result is not None
        uri, score = result
        assert uri == obl2_uri
        assert score >= 0.85

    def test_embedding_service_exception_returns_none(self):
        """If EmbeddingService raises, _check_embedding_duplicate returns None."""
        service = _make_service(INDEX_URIS, INDEX_TYPES, INDEX_VECTORS)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.side_effect = RuntimeError("model not loaded")
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_embedding_duplicate("Any Label", "", "obligation")
        assert result is None


# ---------------------------------------------------------------------------
# _check_duplicate integration tests (lexical + embedding pipeline)
# ---------------------------------------------------------------------------

class TestCheckDuplicate:
    """Integration tests for _check_duplicate: lexical paths and embedding fallthrough."""

    def _make_full_service(self):
        return _make_service(
            INDEX_URIS, INDEX_TYPES, INDEX_VECTORS,
            cache_entries=LEXICAL_CACHE,
        )

    def test_exact_label_returns_confidence_one(self):
        """Exact label match (case-insensitive) returns (uri, 1.0)."""
        service = self._make_full_service()
        result = service._check_duplicate("Confidentiality Obligation", "obligation")
        assert result is not None
        uri, conf = result
        assert uri == OBL_URI
        assert conf == 1.0

    def test_exact_match_case_insensitive(self):
        service = self._make_full_service()
        result = service._check_duplicate("FAITHFUL AGENT ROLE", "role")
        assert result is not None
        uri, conf = result
        assert uri == ROLE_URI
        assert conf == 1.0

    def test_substring_match_returns_0_87(self):
        """Substring match with matching type returns (uri, 0.87)."""
        service = self._make_full_service()
        # 'Faithful' is contained in 'Faithful Agent Role'
        result = service._check_duplicate("Faithful", "role")
        assert result is not None
        uri, conf = result
        assert uri == ROLE_URI
        assert conf == pytest.approx(0.87)

    def test_substring_wrong_type_does_not_match_lexically(self):
        """Substring match with mismatched type is not returned from lexical path."""
        service = self._make_full_service()
        # 'Competence' is a substring of 'Competence Capability' (type=capability)
        # Querying with obligation type -> lexical path blocked
        # Use a query vector with cosine below EMBEDDING_MATCH_MIN so it returns None
        query = _vec_with_cosine(CAP_VEC, 0.50)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_duplicate("Competence", "obligation")
        assert result is None

    def test_unknown_label_falls_through_to_embedding_high(self):
        """Unknown label with no lexical match uses embedding path at high cosine."""
        service = self._make_full_service()
        query = _vec_with_cosine(OBL_VEC, 0.91)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_duplicate(
                "Client Data Protection Duty", "obligation"
            )
        assert result is not None
        uri, conf = result
        assert uri == OBL_URI
        assert conf >= 0.85

    def test_unknown_label_falls_through_to_embedding_novel(self):
        """Unknown label below embedding threshold returns None (novel class)."""
        service = self._make_full_service()
        query = _vec_with_cosine(OBL_VEC, 0.50)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_duplicate(
                "CompletelyUnrelatedConcept999", "obligation"
            )
        assert result is None

    def test_empty_cache_returns_none_immediately(self):
        """Empty OntServe cache returns None without reaching embedding path."""
        service = _make_service([], [], [], cache_entries={})
        result = service._check_duplicate("Any Label", "role")
        assert result is None

    def test_definition_passed_to_embedding(self):
        """Definition argument is forwarded to _check_embedding_duplicate."""
        service = self._make_full_service()
        query = _vec_with_cosine(OBL_VEC, 0.88)
        mock_emb = MagicMock()
        mock_emb._get_local_embedding.return_value = query
        with patch("app.services.auto_commit_service.EmbeddingService") as MockCls:
            MockCls.get_instance.return_value = mock_emb
            result = service._check_duplicate(
                "Duty of Confidentiality",
                "obligation",
                "Engineer must keep client secrets",
            )
        # Should succeed via embedding
        assert result is not None
        # EmbeddingService was called (embedding path was reached)
        mock_emb._get_local_embedding.assert_called()
        # The call text should include the definition
        call_args = mock_emb._get_local_embedding.call_args[0][0]
        assert "Engineer must keep client secrets" in call_args
