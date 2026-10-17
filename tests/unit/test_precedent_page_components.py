"""The Similar Cases page shows every weighted component (case 24-1 review,
lesson L6).

precedents.html rendered three of the five components of the component-aware
score, so outcome alignment and tension overlap (22.7 of the top match's 62.9
points) were invisible. The helper exports the component list from the weights
themselves, the template loops over it with the weights, and the unused
primary-method computation with its stale docstring formula is gone.
"""

import inspect
from pathlib import Path

from app.routes.precedents import helpers
from app.routes.precedents.helpers import MATCHING_METHODS, RETRIEVAL_COMPONENTS
from app.services.precedent.similarity_service import PrecedentSimilarityService

TEMPLATE = Path(__file__).resolve().parents[2] / 'app' / 'templates' / 'precedents.html'


class TestRetrievalComponents:

    def test_the_five_weighted_components_in_weight_order(self):
        weights = PrecedentSimilarityService.COMPONENT_AWARE_WEIGHTS
        assert RETRIEVAL_COMPONENTS == list(weights)
        assert RETRIEVAL_COMPONENTS == ['component_similarity', 'provision_overlap',
                                        'outcome_alignment', 'tag_overlap', 'principle_overlap']
        assert abs(sum(weights.values()) - 1.0) < 1e-9

    def test_every_component_has_a_display_entry(self):
        for key in RETRIEVAL_COMPONENTS:
            info = MATCHING_METHODS[key]
            assert info['name'] and info['method'] and info['description'], key
        assert MATCHING_METHODS['outcome_alignment']['method'] == 'Match'
        assert MATCHING_METHODS['principle_overlap']['method'] == 'Cosine'


class TestTemplate:

    def test_template_loops_over_the_component_list_with_weights(self):
        html = TEMPLATE.read_text()
        assert "{% for comp_key in retrieval_components %}" in html
        assert "['component_similarity', 'provision_overlap', 'tag_overlap']" not in html
        assert 'weights_used' in html
        assert 'Weighted sum' in html


class TestHelperCleanup:

    def test_primary_method_computation_is_gone(self):
        assert not hasattr(helpers, '_get_primary_method')

    def test_docstring_states_the_component_aware_formula(self):
        doc = inspect.getdoc(helpers._find_precedents_for_case)
        assert 'facts_sim' not in doc
        for weight in ('0.40', '0.25', '0.15', '0.10'):
            assert weight in doc
        for key in RETRIEVAL_COMPONENTS:
            assert key in doc
