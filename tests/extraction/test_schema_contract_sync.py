"""Contract-sync guard: the four representations of the extraction field contract.

The field contract exists in four artifacts: the SHACL shapes
(OntServe/validation/shapes/core-shapes.ttl, the declared source of truth), the
Pydantic extraction models (schemas.py), the prompt markdown examples, and the
*_meta.json sidecars. They were synchronized by convention only, and every
contract drift the 2026-07-05 correspondence audits found lived in exactly
those seams (extensional_examples vs extensionalCases; a meta documenting a
nonexistent importance field; prompt examples missing shape fields; emitted
predicates with no declaration). These tests make that class of drift a test
failure instead of an audit finding.

Deliberate divergences are ALLOW-LISTED with reasons, so the lists double as
the catalog of known asymmetries; removing an entry is how a divergence gets
retired.
"""
import json
import os
import re
from pathlib import Path

import pytest
import rdflib
from rdflib import Namespace
from rdflib.namespace import OWL, RDF

from app.services.extraction import schemas as S

SH = Namespace('http://www.w3.org/ns/shacl#')
PCSH = Namespace('http://proethica.org/shapes/core#')

_ONTSERVE = Path(__file__).resolve().parents[3] / 'OntServe'
_SHAPES = Path(os.environ.get('ONTSERVE_SHAPES_PATH')
               or _ONTSERVE / 'validation' / 'shapes' / 'core-shapes.ttl')
_PROMPTS = Path(__file__).resolve().parents[2] / 'app' / 'utils' / 'prompts'


def _camel(name: str) -> str:
    parts = name.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])


@pytest.fixture(scope='module')
def shapes_graph():
    g = rdflib.Graph()
    g.parse(str(_SHAPES), format='turtle')
    return g


@pytest.fixture(scope='module')
def declared_property_uris():
    """Every property IRI declared in the curated base (intermediate + core)."""
    uris = set()
    for ttl in ('proethica-intermediate.ttl', 'proethica-core.ttl'):
        g = rdflib.Graph()
        g.parse(str(_ONTSERVE / 'ontologies' / ttl), format='turtle')
        for ptype in (OWL.ObjectProperty, OWL.DatatypeProperty, OWL.AnnotationProperty):
            uris.update(str(p) for p in g.subjects(RDF.type, ptype))
    return uris


def _shape_rows(g, shape_local):
    """[(sh:name, sh:path uri, informational)] for one shape, [] if absent."""
    rows = []
    for pshape in g.objects(PCSH[shape_local], SH.property):
        name = next(g.objects(pshape, SH.name), None)
        path = next(g.objects(pshape, SH.path), None)
        info = next(g.objects(pshape, PCSH.informationalOnly), None)
        if name is None or path is None:
            continue
        rows.append((str(name), str(path),
                     info is not None and str(info).strip().lower() == 'true'))
    return rows


# All shapes referenced by the prompt renderer or the class pages.
_ALL_SHAPES = [
    'RoleDefinitionShape', 'ProfessionalRoleDefinitionShape', 'ProfessionalRolePropertyShape',
    'PrincipleDefinitionShape', 'PrinciplePropertyShape',
    'ObligationDefinitionShape', 'ObligationPropertyShape',
    'StateDefinitionShape', 'StatePropertyShape',
    'ResourceDefinitionShape', 'ResourcePropertyShape',
    'CapabilityDefinitionShape', 'CapabilityPropertyShape',
    'ConstraintDefinitionShape', 'ConstraintPropertyShape',
    'EventDefinitionShape',
    'ActionPropertyShape',
    'CaseAnnotationShape',
]


def test_every_shape_path_is_declared(shapes_graph, declared_property_uris):
    """Clickability/resolvability invariant (the 2026-07-05 sweep): every sh:path
    the shapes reference must have a real declaration in the curated base, or the
    schema advertises predicates that resolve nowhere."""
    missing = []
    for shape in _ALL_SHAPES:
        for name, path, _info in _shape_rows(shapes_graph, shape):
            if path not in declared_property_uris:
                missing.append(f'{shape}: {name} -> {path}')
    assert not missing, 'undeclared sh:path predicates:\n' + '\n'.join(missing)


# Components rendered by the generic {{ x_schema }} block (roles has its own block).
_GENERIC_COMPONENTS = ['Principle', 'Obligation', 'State', 'Resource',
                       'Capability', 'Constraint', 'Event']


@pytest.mark.parametrize('component', _GENERIC_COMPONENTS)
def test_prompt_block_renders_every_shape_field(shapes_graph, component):
    """Prompt-wiring invariant: every shape row (fillable or commit-assigned)
    must appear in the rendered {{ <x>_schema }} block, or prompt and schema
    have drifted apart."""
    from app.services.prompt_variable_resolver import _component_schema_block
    os.environ.setdefault('ONTSERVE_SHAPES_PATH', str(_SHAPES))
    block = _component_schema_block(component)
    absent = []
    for shape in (f'{component}DefinitionShape', f'{component}PropertyShape'):
        for name, _path, _info in _shape_rows(shapes_graph, shape):
            if name not in block:
                absent.append(f'{shape}: {name}')
    assert not absent, f'shape fields missing from the rendered block:\n' + '\n'.join(absent)


def test_role_prompt_block_renders_bearer_fields(shapes_graph):
    from app.services.prompt_variable_resolver import _role_schema_block
    os.environ.setdefault('ONTSERVE_SHAPES_PATH', str(_SHAPES))
    block = _role_schema_block()
    absent = []
    for shape in ('RoleDefinitionShape', 'ProfessionalRoleDefinitionShape',
                  'ProfessionalRolePropertyShape'):
        for name, _path, _info in _shape_rows(shapes_graph, shape):
            if name not in block:
                absent.append(f'{shape}: {name}')
    assert not absent, 'role shape fields missing from the rendered block:\n' + '\n'.join(absent)


# meta output_schema -> Pydantic model, per component. Keys are the meta's
# top-level output_schema entries; values the model to check against.
_META_MODELS = {
    'roles': ('new_role_classes', S.CandidateRoleClass, 'role_individuals', S.RoleIndividual),
    'principles': ('new_principle_classes', S.CandidatePrincipleClass, 'principle_individuals', S.PrincipleIndividual),
    'obligations': ('new_obligation_classes', S.CandidateObligationClass, 'obligation_individuals', S.ObligationIndividual),
    'states': ('new_state_classes', S.CandidateStateClass, 'state_individuals', S.StateIndividual),
    'resources': ('new_resource_classes', S.CandidateResourceClass, 'resource_individuals', S.ResourceIndividual),
    'capabilities': ('new_capability_classes', S.CandidateCapabilityClass, 'capability_individuals', S.CapabilityIndividual),
    'constraints': ('new_constraint_classes', S.CandidateConstraintClass, 'constraint_individuals', S.ConstraintIndividual),
}


def _model_field_names(model):
    names = set()
    for fname, field in model.model_fields.items():
        names.add(fname)
        if field.alias:
            names.add(field.alias)
        va = field.validation_alias
        if va is not None and hasattr(va, 'choices'):
            names.update(c for c in va.choices if isinstance(c, str))
        elif isinstance(va, str):
            names.add(va)
    return names


@pytest.mark.parametrize('component', sorted(_META_MODELS))
def test_meta_fields_exist_in_pydantic_model(component):
    """Phantom-field invariant: every field the meta sidecar documents must
    exist on the Pydantic model (the roles meta once documented an
    'importance' field that existed nowhere)."""
    class_key, class_model, ind_key, ind_model = _META_MODELS[component]
    meta = json.loads((_PROMPTS / f'{component}_meta.json').read_text())
    schema = meta.get('output_schema') or {}
    problems = []
    for key, model in ((class_key, class_model), (ind_key, ind_model)):
        entry = schema.get(key)
        if not isinstance(entry, dict):
            continue
        # The meta nests {'type': ..., 'fields': {field: ...}, 'description': ...}.
        fields = entry.get('fields') if isinstance(entry.get('fields'), dict) \
            else (entry.get('items') if isinstance(entry.get('items'), dict) else entry)
        if not isinstance(fields, dict):
            continue
        known = _model_field_names(model)
        for fname in fields:
            if fname in ('type', 'description', 'required'):
                continue
            if fname not in known:
                problems.append(f'{component}.{key}: meta field {fname!r} not on {model.__name__}')
    assert not problems, '\n'.join(problems)


# Individual-model fields that deliberately do NOT correspond to a shape row.
# Removing an entry here is how the divergence gets retired.
_INDIVIDUAL_ALLOWLIST = {
    # BaseIndividual plumbing / identity
    'identifier', 'name', 'text_references', 'source_text', 'confidence',
    'match_decision',
    # routing inputs consumed at commit (R1/CMT-3; shapes mark them
    # informational or the typing carries them)
    'role_class', 'instance_of', 'role_category', 'role_kind',
    'principle_class', 'obligation_class', 'state_class', 'resource_class',
    'capability_class', 'constraint_class',
    # re-shaped collections (bag -> per-key triples / otherAttribute staging;
    # relationships -> object edges)
    'attributes', 'relationships', 'additional_relationships',
    # actor identity (routing to the Agent layer, not a literal)
    'actor',
    # per-case annotation fields covered by CaseAnnotationShape under
    # different names or routed into rdfs:comment
    'case_involvement', 'case_context',
    # component-specific fields that are edge/derived-routed rather than
    # shape-advertised literals (audited 2026-07-05; see field_classification)
    'derived_from_principle', 'obligated_party', 'obligation_statement',
    'temporal_scope', 'compliance_status', 'enforcement_level',
    'subject', 'active_period', 'triggering_event', 'terminated_by',
    'state_category', 'persistence_type', 'urgency_level',
    'document_title', 'topic', 'used_by', 'cited_by', 'resource_category',
    'usage_context', 'availability',
    'possessed_by', 'required_for_obligations', 'capability_category',
    'skill_level', 'demonstrated_through',
    'constrained_entity', 'constraint_statement', 'applicability_condition',
    'source', 'constraint_type', 'flexibility', 'severity', 'exceptions',
    'interpretation', 'concrete_expression', 'applied_to', 'balancing_with',
    'tension_resolution', 'invoked_by', 'principle_category',
}


@pytest.mark.parametrize('component,shape', [
    ('roles', 'ProfessionalRolePropertyShape'),
])
def test_bearer_fields_camelcase_to_shape_paths(shapes_graph, component, shape):
    """Spelling-drift invariant (the extensional_examples lesson): a bearer
    field on the individual model must camelCase to a shape sh:path local
    name, or be a documented divergence. Roles is the fully-aligned exemplar;
    extend per component as their shapes tighten."""
    _, _, _, ind_model = _META_MODELS[component]
    paths = {p.rsplit('#', 1)[-1] for _n, p, _i in _shape_rows(shapes_graph, shape)}
    paths |= {p.rsplit('#', 1)[-1] for _n, p, _i in _shape_rows(shapes_graph, 'CaseAnnotationShape')}
    drifted = []
    for fname in ind_model.model_fields:
        if fname in _INDIVIDUAL_ALLOWLIST:
            continue
        if _camel(fname) not in paths:
            drifted.append(f'{ind_model.__name__}.{fname} -> {_camel(fname)} not a shape path')
    assert not drifted, '\n'.join(drifted)
