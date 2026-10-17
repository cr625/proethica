"""Subject-tag overlap of the Similar Cases page (case 24-1 review, lesson L2).

The scorer and the page use one tag set: the NSPE subject references in
documents.doc_metadata, with the model-assigned feature column as the fallback
when the document carries none. The displayed overlapping tags are the
scorer's own intersection. No database: the feature query and the discovery
service are patched.
"""

from types import SimpleNamespace
from unittest.mock import patch

from app.services.precedent.similarity_service import (
    PrecedentSimilarityService,
    resolve_subject_tags,
)
from app.services.precedent.precedent_discovery_service import PrecedentMatch
from app.routes.precedents import helpers
from app.routes.precedents.helpers import RETRIEVAL_COMPONENTS, _find_precedents_for_case


DOC_TAGS_8 = ['Duty to the Public', 'Public Health and Safety', 'Faithful Agents and Trustees',
              'Client Directives', 'Design Standards', 'Stormwater', 'Professional Judgment',
              'Withdrawal from a Project', 'Flooding']
FEATURE_TAGS_8 = ['Duty to the Public', 'Public Health and Safety', 'Sustainable Development',
                  'Conflict of Interest', 'Professional Responsibility', 'Faithful Agents and Trustees']


class TestResolveSubjectTags:

    def test_document_subject_references_win(self):
        assert resolve_subject_tags(DOC_TAGS_8, FEATURE_TAGS_8) == DOC_TAGS_8

    def test_feature_column_is_the_fallback_when_the_document_has_none(self):
        assert resolve_subject_tags(None, FEATURE_TAGS_8) == FEATURE_TAGS_8
        assert resolve_subject_tags([], FEATURE_TAGS_8) == FEATURE_TAGS_8
        assert resolve_subject_tags(['', None], FEATURE_TAGS_8) == FEATURE_TAGS_8

    def test_empty_when_neither_source_has_tags(self):
        assert resolve_subject_tags(None, None) == []

    def test_deduplicates_and_keeps_order(self):
        assert resolve_subject_tags(['A', 'B', 'A', ' C '], None) == ['A', 'B', 'C']

    def test_single_string_is_one_tag(self):
        assert resolve_subject_tags('Duty to the Public', None) == ['Duty to the Public']


def _features(case_id, tags, provisions=None, outcome='mixed'):
    return {
        'case_id': case_id,
        'outcome_type': outcome,
        'outcome_confidence': 0.9,
        'provisions_cited': provisions or [],
        'subject_tags': tags,
        'feature_subject_tags': [],
        'principle_tensions': [],
        'obligation_conflicts': [],
        'transformation_type': None,
        'facts_embedding': None,
        'discussion_embedding': None,
        'conclusion_embedding': None,
        'combined_embedding': None,
        'embedding_tension': None,
        **{f'embedding_{c}': None for c in ['R', 'P', 'O', 'S', 'Rs', 'A', 'E', 'Ca', 'Cs']},
    }


class TestScorerUsesTheResolvedTagSet:

    def test_tag_overlap_and_matching_tags_come_from_one_set(self):
        service = PrecedentSimilarityService()
        source = _features(8, ['Duty to the Public', 'Public Health and Safety', 'Stormwater', 'Flooding'])
        target = _features(89, ['Public Health and Safety', 'Stormwater', 'Competence'])

        def fake_features(case_id):
            return {8: source, 89: target}[case_id]

        with patch.object(service, '_get_case_features', side_effect=fake_features):
            result = service.calculate_similarity(8, 89, use_component_embedding=True)

        # Jaccard over the resolved sets: 2 shared of 5 distinct.
        assert result.component_scores['tag_overlap'] == 2 / 5
        assert result.matching_tags == ['Public Health and Safety', 'Stormwater']

    def test_jaccard_is_zero_without_shared_tags(self):
        service = PrecedentSimilarityService()
        with patch.object(service, '_get_case_features',
                          side_effect=lambda cid: _features(cid, ['A'] if cid == 1 else ['B'])):
            result = service.calculate_similarity(1, 2, use_component_embedding=True)
        assert result.component_scores['tag_overlap'] == 0.0
        assert result.matching_tags == []


class TestPageDisplaysTheScoredTags:

    def test_overlapping_tags_are_the_scorer_intersection(self):
        match = PrecedentMatch(
            target_case_id=89,
            target_case_title='Case 84-5',
            target_case_url=None,
            overall_score=0.629,
            component_scores={
                'component_similarity': 0.71, 'provision_overlap': 0.286,
                'outcome_alignment': 1.0, 'tag_overlap': 0.4, 'principle_overlap': 0.77,
            },
            matching_provisions=['II.1.A', 'II.4'],
            outcome_match=True,
            target_outcome='mixed',
            target_transformation='transfer',
            matching_tags=['Public Health and Safety', 'Stormwater'],
            weights_used=dict(PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS),
        )
        discovery = SimpleNamespace(find_precedents=lambda **kwargs: [match])
        case_features = {
            'principle_tensions': [], 'obligation_conflicts': [], 'transformation_type': 'phase_lag',
            'cited_case_numbers': [], 'cited_case_ids': [], 'outcome_type': 'mixed',
        }
        with patch('app.services.precedent.PrecedentDiscoveryService', return_value=discovery), \
             patch.object(helpers, '_get_case_features', return_value=case_features), \
             patch.object(helpers, '_resolve_transformation_type', side_effect=lambda cid, col: col):
            payload = _find_precedents_for_case(8)

        assert payload['success'] is True
        precedent = payload['precedents'][0]
        # The topics shown are exactly the set tag_overlap was scored on.
        assert precedent['overlapping_tags'] == match.matching_tags
        assert precedent['component_scores']['tag_overlap'] == 0.4
        # Every weighted component reaches the page, with its weight.
        assert set(RETRIEVAL_COMPONENTS) <= set(precedent['component_scores'])
        assert precedent['weights_used'] == {k: round(v, 3) for k, v in
                                             PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS.items()}
