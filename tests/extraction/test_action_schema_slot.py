"""Step-3 action_schema wire: the PropertyShape-only {{ action_schema }} slot.

Action deliberately has NO SHACL DefinitionShape (bare, per the ratified spec), so its schema
slot renders the per-case ActionPropertyShape alone via the property_only branch of
_component_schema_block; adding 'actions' to _COMPONENT_SHAPE instead would raise on the missing
DefinitionShape. These tests pin the wire: the slot resolves non-empty with every
ActionPropertyShape field name, the seeded body and the live hand-built Step-3 prompt both carry
the block, and the events path (DefinitionShape-driven) is unchanged.

DB/LLM-free: the slot builders read only core-shapes.ttl and the ontology TTLs.
"""
import os
from pathlib import Path

import pytest
import rdflib
from rdflib import Namespace

from app.services.prompt_variable_resolver import (
    _component_schema_block,
    concept_ontology_slots,
)

SH = Namespace('http://www.w3.org/ns/shacl#')
PCSH = Namespace('http://proethica.org/shapes/core#')

_SHAPES = Path(os.environ.get('ONTSERVE_SHAPES_PATH')
               or Path(__file__).resolve().parents[3] / 'OntServe' / 'validation' / 'shapes'
               / 'core-shapes.ttl')
_PROMPTS_DIR = Path(__file__).resolve().parents[2] / 'app' / 'utils' / 'prompts'


def _shape_field_names(shape_local: str):
    g = rdflib.Graph()
    g.parse(str(_SHAPES), format='turtle')
    names = []
    for pshape in g.objects(PCSH[shape_local], SH.property):
        name = next(g.objects(pshape, SH.name), None)
        if name is not None:
            names.append(str(name))
    return names


def test_action_schema_slot_resolves_non_empty():
    slots = concept_ontology_slots('actions', 'all')
    block = slots.get('action_schema')
    assert block, "action_schema missing/empty in concept_ontology_slots('actions')"
    assert block.startswith('=== ACTION SCHEMA')
    assert 'Per-case fields' in block


def test_action_schema_carries_every_property_shape_field():
    names = _shape_field_names('ActionPropertyShape')
    assert names, 'ActionPropertyShape has no fields in core-shapes.ttl'
    block = concept_ontology_slots('actions', 'all')['action_schema']
    absent = [n for n in names if n not in block]
    assert not absent, f'ActionPropertyShape fields missing from action_schema: {absent}'


def test_action_schema_has_no_class_fields_section():
    # PropertyShape-only: no type-level section may appear (authoring an ActionDefinitionShape
    # would re-open the ratified bare-Action decision).
    block = concept_ontology_slots('actions', 'all')['action_schema']
    assert 'Class fields' not in block
    assert 'DefinitionShape' not in block


def test_property_only_raises_on_missing_shape():
    with pytest.raises(RuntimeError, match='PropertyShape has no fields'):
        _component_schema_block('Nonexistent', property_only=True)


def test_actions_md_wires_action_schema_slot():
    body = (_PROMPTS_DIR / 'actions.md').read_text()
    assert '{{ action_schema }}' in body


def test_live_phase1_prompt_carries_schema_block():
    # The live Step-3 path (LangGraph, hand-built prompt) must inject the same block.
    from app.services.temporal_dynamics.extractors.action_extractor import _build_phase1_prompt
    prompt = _build_phase1_prompt({}, {}, facts_text='facts', discussion_text='discussion')
    assert '=== ACTION SCHEMA' in prompt
    assert 'Per-case fields' in prompt


def test_event_schema_unchanged():
    # Events stay on the DefinitionShape-driven generic path: same builder, same header, all
    # EventDefinitionShape fields present, no per-case section (Event has no PropertyShape).
    slots = concept_ontology_slots('events', 'all')
    block = slots.get('event_schema')
    assert block
    assert block == _component_schema_block('Event')
    assert block.startswith('=== EVENT SCHEMA')
    assert 'Per-case fields' not in block
    names = _shape_field_names('EventDefinitionShape')
    assert names, 'EventDefinitionShape has no fields in core-shapes.ttl'
    absent = [n for n in names if n not in block]
    assert not absent, f'EventDefinitionShape fields missing from event_schema: {absent}'
