"""Structured-outputs schema compilation guards.

Regression tests for the 2026-07-01 Stage-0 empty-relationships defect:
Pydantic renders an open ``Dict[str, ...]`` field as ``{"type": "object",
"additionalProperties": {...}}``; ``_clean_structured_output_node`` then
closes every object node (``additionalProperties: false`` + ``required`` =
all properties), leaving a grammar whose only valid instance is ``{}``.
``RoleIndividual.attributes/relationships/additional_relationships`` were
therefore structurally forced empty on every extraction, regardless of model.

The guards here fail on ANY schema (all CONCEPT_SCHEMAS plus the auxiliary
result models) that compiles to an empty-only object node, and verify the
roles round trip end to end: a structured-output-shaped payload validates,
``model_dump()`` reproduces the ``{type, target, quote}`` dict shape the
storage layer stringifies, and ``ast.literal_eval`` of that string restores
the keys the commit bridge (ontserve_commit_service) requires.
"""

import ast

import pytest

from app.services.extraction.schemas import (
    BoardConclusionExtractionResult,
    CONCEPT_SCHEMAS,
    DefeasibilityEdgeExtractionResult,
    ObligationEngagementResult,
    RoleExtractionResult,
    RoleIndividual,
    TemporalSequenceResult,
    fold_key_value_pairs,
    to_structured_output_schema,
)


def _empty_only_object_nodes(node, path=""):
    """Collect paths of object nodes whose only valid instance is {}.

    After cleaning, an object node with ``additionalProperties: false`` and
    no ``properties`` admits exactly one instance: the empty object. Any such
    node in an LLM-facing schema silently forces empty output.
    """
    hits = []
    if isinstance(node, dict):
        if (node.get('type') == 'object'
                and node.get('additionalProperties') is False
                and not node.get('properties')):
            hits.append(path)
        for key, value in node.items():
            hits.extend(_empty_only_object_nodes(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            hits.extend(_empty_only_object_nodes(value, f"{path}[{i}]"))
    return hits


ALL_RESULT_MODELS = dict(CONCEPT_SCHEMAS)
ALL_RESULT_MODELS.update({
    'temporal_sequence': TemporalSequenceResult,
    'obligation_engagement': ObligationEngagementResult,
    'board_conclusions': BoardConclusionExtractionResult,
    'defeasibility_edges': DefeasibilityEdgeExtractionResult,
})


@pytest.mark.parametrize('name', sorted(ALL_RESULT_MODELS))
def test_no_empty_only_object_nodes(name):
    """No compiled schema may contain an object node that only admits {}."""
    schema = to_structured_output_schema(ALL_RESULT_MODELS[name])
    hits = _empty_only_object_nodes(schema, name)
    assert not hits, (
        f"empty-only object node(s) in the {name} structured-output schema "
        f"(the LLM is structurally forced to emit an empty dict there): {hits}"
    )


class TestRolesRelationshipSchema:
    """The roles grammar must be able to express a non-empty relationship."""

    def _role_individual_props(self):
        schema = to_structured_output_schema(RoleExtractionResult)
        resolved = {}
        for field in ('relationships', 'additional_relationships'):
            node = schema['$defs']['RoleIndividual']['properties'][field]
            items = node['items']
            if '$ref' in items:
                items = schema['$defs'][items['$ref'].rsplit('/', 1)[-1]]
            resolved[field] = (node, items)
        return schema, resolved

    def test_relationship_items_carry_typed_properties(self):
        _, resolved = self._role_individual_props()
        for field, (node, items) in resolved.items():
            assert node['type'] == 'array', field
            props = items.get('properties', {})
            assert set(props) == {'type', 'target', 'quote'}, (
                f"{field}.items must expose the bridge keys, got {sorted(props)}"
            )
            # Strict grammar: closed object, every property required.
            assert items['additionalProperties'] is False, field
            assert set(items['required']) == {'type', 'target', 'quote'}, field
            for key in ('type', 'target', 'quote'):
                assert props[key]['type'] == 'string', (field, key)

    def test_attributes_compiles_to_key_value_pair_array(self):
        schema = to_structured_output_schema(RoleExtractionResult)
        node = schema['$defs']['RoleIndividual']['properties']['attributes']
        assert node['type'] == 'array'
        items = node['items']
        assert set(items['properties']) == {'key', 'value'}
        assert items['additionalProperties'] is False
        assert set(items['required']) == {'key', 'value'}

    def test_round_trip_yields_bridge_dict_shape(self):
        """Structured-output payload -> model -> dump -> str -> literal_eval.

        Mirrors the live chain: _parse_and_validate (model_validate), then
        extraction_graph._extract_properties (model_dump + str), then the
        commit bridge (ast.literal_eval + r.get('type')/r.get('target')).
        """
        payload = {
            'name': 'Engineer A',
            'identifier': 'Engineer A',
            'role_class': 'Structural Engineer',
            'relationships': [{
                'type': 'clientOf',
                'target': 'Client W',
                'quote': 'Engineer A performed structural design services for Client W',
            }],
            'additional_relationships': [
                # alias keys the bridge also accepts
                {'relation': 'mentorOf', 'to': 'Engineer B'},
            ],
            'attributes': [
                {'key': 'years_of_experience', 'value': '20'},
                {'key': '', 'value': 'dropped: empty key'},
                'dropped: not a dict',
            ],
        }
        ind = RoleIndividual.model_validate(payload)
        dumped = ind.model_dump(exclude_none=True, exclude_unset=False)

        # relationships: dict shape with the bridge's required keys
        rel = dumped['relationships'][0]
        assert rel == {
            'type': 'clientOf',
            'target': 'Client W',
            'quote': 'Engineer A performed structural design services for Client W',
        }
        # storage stringifies (extraction_graph str(v)); the bridge literal_evals
        restored = ast.literal_eval(str(rel))
        assert (restored.get('type') or restored.get('relation')) == 'clientOf'
        assert (restored.get('target') or restored.get('to')) == 'Client W'

        # alias keys normalize to the canonical field names
        extra = dumped['additional_relationships'][0]
        assert extra['type'] == 'mentorOf'
        assert extra['target'] == 'Engineer B'

        # attributes folded from pairs to the runtime dict; junk skipped
        assert dumped['attributes'] == {'years_of_experience': '20'}

    def test_legacy_dict_attributes_pass_through(self):
        """Old temp rows / non-structured paths supply a dict; keep it."""
        ind = RoleIndividual.model_validate(
            {'name': 'X', 'attributes': {'license': 'PE'}})
        assert ind.attributes == {'license': 'PE'}

    def test_fold_key_value_pairs_non_list_passthrough(self):
        assert fold_key_value_pairs({'a': 1}) == {'a': 1}
        assert fold_key_value_pairs(None) is None
        assert fold_key_value_pairs(
            [{'key': 'k', 'value': 'v'}, {'novalue': True}]) == {'k': 'v'}
