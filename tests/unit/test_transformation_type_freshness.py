"""Freshness of case_precedent_features.transformation_type (case 24-1 review,
lesson L4).

The column said 'stalemate' while the active Step 4 classification said
phase_lag: the connector wrote the column only when empty, the synthesis
clear never reset it, and the page read the column. The connector now always
writes, the clear resets, and the page helper reads the latest
classification. No database: models and sessions are patched.
"""

from unittest.mock import MagicMock, patch

from app.models.case_precedent_features import CasePrecedentFeatures
from app.services.precedent import phase4_connector
from app.services.precedent.phase4_connector import update_precedent_features_from_phase4
from app.routes.precedents.helpers import _resolve_transformation_type
from app.routes.scenario_pipeline.step4 import config as step4_config
from app.services.step4_synthesis import step4_synthesis_service


def _stale_features():
    # A transient ORM instance (never added to a session): the connector flags the
    # extraction_metadata column modified after its in-place edit, which needs the
    # instance state a plain namespace lacks.
    return CasePrecedentFeatures(
        case_id=8, transformation_type='stalemate', transformation_pattern='old pattern',
        principle_tensions=None, obligation_conflicts=None, cited_case_numbers=None,
        cited_case_ids=None, extracted_at=None, extraction_method=None, llm_model_used=None,
        extraction_metadata=None, outcome_type='ethical', outcome_confidence=0.65,
        outcome_reasoning='Ethical indicators: explicit ethical statement',
    )


class TestConnectorAlwaysWritesTheClassification:

    def _run(self, features, transformation_type, board_outcome=None):
        model = MagicMock()
        model.query.filter_by.return_value.first.return_value = features
        with patch.object(phase4_connector, 'CasePrecedentFeatures', model), \
             patch.object(phase4_connector, 'db', MagicMock()), \
             patch('app.services.precedent.case_feature_extractor.board_outcome_for_case',
                   return_value=board_outcome):
            return update_precedent_features_from_phase4(
                case_id=8, transformation_type=transformation_type)

    def test_stale_column_is_replaced(self):
        features = _stale_features()
        assert self._run(features, 'phase_lag') is True
        assert features.transformation_type == 'phase_lag'

    def test_empty_column_is_filled(self):
        features = _stale_features()
        features.transformation_type = None
        self._run(features, 'transfer')
        assert features.transformation_type == 'transfer'

    def test_no_classification_leaves_the_column(self):
        features = _stale_features()
        self._run(features, None)
        assert features.transformation_type == 'stalemate'

    def test_board_conclusions_refresh_the_outcome(self):
        features = _stale_features()
        self._run(features, 'phase_lag', board_outcome=('mixed', 0.95, 'Board conclusions of both polarities'))
        assert features.outcome_type == 'mixed'
        assert features.outcome_confidence == 0.95
        assert features.outcome_reasoning == 'Board conclusions of both polarities'

    def test_outcome_stands_without_board_conclusions(self):
        features = _stale_features()
        self._run(features, 'phase_lag', board_outcome=None)
        assert features.outcome_type == 'ethical'


class TestPageHelperReadsTheLatestClassification:

    def test_stale_column_yields_the_latest_classification(self):
        with patch('app.services.case_analysis.transformation_classifier.load_latest_transformation',
                   return_value={'type': 'phase_lag', 'pattern': '', 'confidence': 0.78, 'reasoning': ''}):
            assert _resolve_transformation_type(8, 'stalemate') == 'phase_lag'

    def test_empty_column_yields_the_latest_classification(self):
        with patch('app.services.case_analysis.transformation_classifier.load_latest_transformation',
                   return_value={'type': 'transfer', 'pattern': '', 'confidence': None, 'reasoning': ''}):
            assert _resolve_transformation_type(89, None) == 'transfer'

    def test_column_is_the_fallback_without_a_classification(self):
        with patch('app.services.case_analysis.transformation_classifier.load_latest_transformation',
                   return_value=None):
            assert _resolve_transformation_type(8, 'stalemate') == 'stalemate'

    def test_query_failure_keeps_the_column(self):
        with patch('app.services.case_analysis.transformation_classifier.load_latest_transformation',
                   side_effect=RuntimeError('no app context')):
            assert _resolve_transformation_type(8, 'stalemate') == 'stalemate'


class TestStep4ClearResetsTheFeatureColumns:

    def test_reset_clears_every_step4_column(self):
        features = _stale_features()
        model = MagicMock()
        model.query.filter_by.return_value.first.return_value = features
        with patch('app.models.CasePrecedentFeatures', model):
            step4_config.reset_step4_case_features(8)
        assert features.transformation_type is None
        assert features.transformation_pattern is None
        assert features.principle_tensions is None
        assert features.obligation_conflicts is None
        # Ingestion-time fields are not Step 4 fields.
        assert features.outcome_type == 'ethical'

    def test_synthesis_clear_calls_the_reset(self):
        storage = MagicMock()
        storage.query.filter_by.return_value.delete.return_value = 1
        prompts = MagicMock()
        with patch.object(step4_synthesis_service, 'TemporaryRDFStorage', storage), \
             patch.object(step4_synthesis_service, 'ExtractionPrompt', prompts), \
             patch.object(step4_synthesis_service, 'db', MagicMock()) as fake_db, \
             patch.object(step4_config, 'reset_step4_case_features') as reset:
            result = step4_synthesis_service._clear_step4_data(8)
        reset.assert_called_once_with(8)
        fake_db.session.commit.assert_called_once()
        assert result['deleted_entities'] > 0
