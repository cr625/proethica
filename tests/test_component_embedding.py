"""
Unit tests for component-level embedding aggregation.

Tests the nine-component embedding functionality including:
- Component weights validation
- Extraction type mapping
- Embedding generation
- Aggregation logic
"""

import pytest
import numpy as np

from app.services.precedent.case_feature_extractor import (
    CaseFeatureExtractor,
    COMPONENT_WEIGHTS,
    EXTRACTION_TYPE_TO_COMPONENT,
    ENTITY_TYPE_TO_COMPONENT
)
from app.services.precedent.similarity_service import (
    PrecedentSimilarityService,
    SimilarityResult
)


class TestComponentMappings:
    """Test component mapping constants."""

    def test_weight_sum_equals_one(self):
        """Weights should sum to 1.0 for proper normalization."""
        total = sum(COMPONENT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001, f"Weights sum to {total}, expected 1.0"

    def test_all_nine_components_have_weights(self):
        """All 9 component codes should have weights."""
        expected_codes = {'R', 'S', 'Rs', 'P', 'O', 'Cs', 'Ca', 'A', 'E'}
        actual_codes = set(COMPONENT_WEIGHTS.keys())
        assert actual_codes == expected_codes, f"Missing: {expected_codes - actual_codes}"

    def test_extraction_type_mapping_coverage(self):
        """Standard extraction types should be mapped (7 of 9)."""
        expected = ['roles', 'states', 'resources', 'principles',
                    'obligations', 'constraints', 'capabilities']
        for ext_type in expected:
            assert ext_type in EXTRACTION_TYPE_TO_COMPONENT, f"Missing: {ext_type}"

    def test_entity_type_mapping_for_temporal(self):
        """Actions and Events should be mapped via entity_type."""
        assert 'actions' in ENTITY_TYPE_TO_COMPONENT
        assert 'events' in ENTITY_TYPE_TO_COMPONENT
        assert ENTITY_TYPE_TO_COMPONENT['actions'] == 'A'
        assert ENTITY_TYPE_TO_COMPONENT['events'] == 'E'

    def test_principles_highest_weight(self):
        """Principles should have the highest weight."""
        max_weight = max(COMPONENT_WEIGHTS.values())
        assert COMPONENT_WEIGHTS['P'] == max_weight
        assert COMPONENT_WEIGHTS['P'] == 0.20

    def test_no_duplicate_component_codes(self):
        """Component codes should not be duplicated across mappings."""
        ext_codes = set(EXTRACTION_TYPE_TO_COMPONENT.values())
        ent_codes = set(ENTITY_TYPE_TO_COMPONENT.values())
        overlap = ext_codes & ent_codes
        assert len(overlap) == 0, f"Duplicate codes: {overlap}"


class TestLocalEmbedding:
    """Test local embedding generation."""

    @pytest.fixture
    def extractor(self):
        return CaseFeatureExtractor()

    def test_embedding_dimension(self, extractor):
        """Generated embeddings should be 384-dimensional."""
        embedding = extractor._get_local_embedding("test text for embedding")
        assert embedding.shape == (384,)

    def test_embedding_type(self, extractor):
        """Embedding should be numpy array."""
        embedding = extractor._get_local_embedding("test text")
        assert isinstance(embedding, np.ndarray)

    def test_empty_text_returns_zeros(self, extractor):
        """Empty text should return zero vector."""
        embedding = extractor._get_local_embedding("")
        assert np.allclose(embedding, np.zeros(384))

    def test_whitespace_text_returns_zeros(self, extractor):
        """Whitespace-only text should return zero vector."""
        embedding = extractor._get_local_embedding("   \n\t  ")
        assert np.allclose(embedding, np.zeros(384))

    def test_different_texts_different_embeddings(self, extractor):
        """Different texts should produce different embeddings."""
        emb1 = extractor._get_local_embedding("engineer violated code of ethics")
        emb2 = extractor._get_local_embedding("client requested design changes")
        # Should not be identical
        assert not np.allclose(emb1, emb2)


class TestSimilarityService:
    """Test similarity service with component embeddings."""

    @pytest.fixture
    def service(self):
        return PrecedentSimilarityService()

    def test_default_weights_sum_to_one(self, service):
        """Default weights should sum to 1.0."""
        total = sum(service.DEFAULT_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_component_aware_weights_sum_to_one(self, service):
        """Component-aware weights should sum to 1.0."""
        total = sum(service.COMPONENT_AWARE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_component_aware_weights_has_component_similarity(self, service):
        """Component-aware weights should include component_similarity."""
        assert 'component_similarity' in service.COMPONENT_AWARE_WEIGHTS
        assert 'facts_similarity' not in service.COMPONENT_AWARE_WEIGHTS
        assert 'discussion_similarity' not in service.COMPONENT_AWARE_WEIGHTS

    def test_similarity_result_has_method_field(self):
        """SimilarityResult should track which method was used."""
        result = SimilarityResult(
            source_case_id=1,
            target_case_id=2,
            overall_similarity=0.5,
            component_scores={},
            matching_provisions=[],
            outcome_match=True,
            weights_used={},
            method='component'
        )
        assert result.method == 'component'


class TestCosineNormalization:
    """Test embedding normalization for cosine similarity."""

    @pytest.fixture
    def extractor(self):
        return CaseFeatureExtractor()

    def test_embedding_not_all_zeros(self, extractor):
        """Real text should not produce zero embedding."""
        embedding = extractor._get_local_embedding(
            "Engineer A was retained by Client B to review structural design"
        )
        norm = np.linalg.norm(embedding)
        assert norm > 0.1  # Should have significant magnitude
