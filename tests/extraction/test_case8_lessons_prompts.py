"""Case-8 (NSPE 24-1) review lessons on the prompt side: L1, L2 (directives), L6, L7, L8 (states
directive), L9 (role directives), and the canonicalizer's matched-class block (L6).

DB/LLM-free: the extractor is built with object.__new__ (the golden-test pattern), the one DB
loader of the prior-section blocks is stubbed, and the ontology slots read only the TTL files.
"""
from types import SimpleNamespace

import pytest

from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor, CONCEPT_CONFIG
from app.services.extraction.unified_dual_extractor import prompt_building
from app.services.extraction.unified_dual_extractor.prompt_building import (
    format_prior_individuals_block,
)
from app.services.prompt_variable_resolver import (
    _role_directives_block,
    _role_relationships_block,
    concept_ontology_slots,
    discovered_in_cases,
    format_existing_entities,
)


def _bare(concept_type, **attrs):
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.config = CONCEPT_CONFIG[concept_type]
    ext.existing_classes = []
    ext.injection_mode = "full"
    ext.apply_filters = True
    for k, v in attrs.items():
        setattr(ext, k, v)
    return ext


class _RecordingTemplate:
    def __init__(self):
        self.last_variables = None

    def render(self, **variables):
        self.last_variables = variables
        return "RENDERED_BODY"


def _row(label, definition, props):
    return SimpleNamespace(entity_label=label, entity_definition=definition,
                           rdf_json_ld={'properties': props})


_PRINCIPLE_ROWS = [
    _row("Public Welfare Paramountcy", "Engineer L must hold paramount the public welfare.",
         {'principleClass': ['Public Welfare Principle'],
          'concreteExpression': ['Engineer L insists on the stormwater safeguards.'],
          'balancingWith': ['Faithful Agent Principle']}),
    _row("Transparency Toward The Developer", "Candor toward the client.",
         {'principleClass': ['Transparency Principle'],
          'interpretation': ['Engineer L must disclose the standards issue.']}),
]

_OBLIGATION_ROWS = [
    _row("Engineer L Public Welfare Duty", "Hold paramount the public welfare.",
         {'obligationClass': ['Public Welfare Obligation'],
          'obligationStatement': ['Engineer L shall hold paramount the safety, health, and welfare of the public.'],
          'obligatedParty': ['Engineer L'], 'complianceStatus': ['unclear']}),
]


# ---------------------------------------------------------------------------
# L1: prior-section individuals for every component
# ---------------------------------------------------------------------------

def test_prior_individuals_block_principles_lists_identifier_class_and_expression():
    block = format_prior_individuals_block('principles', _PRINCIPLE_ROWS)
    assert '--- PRINCIPLES INDIVIDUALS ALREADY EXTRACTED FROM PRIOR SECTIONS OF THIS CASE ---' in block
    assert 'REUSE' in block and 'REFINE' in block
    assert 'at most one principle individual per value per case' in block
    assert ('- Public Welfare Paramountcy | class: Public Welfare Principle | Engineer L insists on the '
            'stormwater safeguards. | balancingWith: Faithful Agent Principle') in block
    # the interpretation serves as the statement when no concrete expression is stored
    assert '- Transparency Toward The Developer | class: Transparency Principle | Engineer L must disclose' in block


def test_prior_individuals_block_obligations_shows_provisional_status():
    block = format_prior_individuals_block('obligations', _OBLIGATION_ROWS)
    assert 'complianceStatus: unclear' in block
    assert 'confirm or revise EACH one' in block


def test_prior_individuals_block_roles_text_unchanged():
    rows = [_row("Engineer L Design Engineer", "Designed the drainage system.",
                 {'actor': ['Engineer L']})]
    block = format_prior_individuals_block('roles', rows)
    assert block.startswith('\n\n--- ACTORS ALREADY IDENTIFIED IN PRIOR SECTIONS ---')
    assert '- actor "Engineer L" | role facet: Engineer L Design Engineer | section: prior | Designed' in block


def test_prior_individuals_block_empty_rows():
    assert format_prior_individuals_block('constraints', []) == ''


@pytest.mark.parametrize("concept_type,rows,marker", [
    ("principles", _PRINCIPLE_ROWS, "PRINCIPLES INDIVIDUALS ALREADY EXTRACTED"),
    ("obligations", _OBLIGATION_ROWS, "OBLIGATIONS INDIVIDUALS ALREADY EXTRACTED"),
])
def test_assembled_discussion_prompt_carries_prior_individuals(monkeypatch, concept_type, rows, marker):
    """The discussion-pass prompt of a non-role component carries the prior individuals block
    (before the fix only roles did)."""
    monkeypatch.setattr("app.services.prompt_variable_resolver.reuse_block_for_concept",
                        lambda *a, **k: "")
    monkeypatch.setattr(prompt_building, "format_cross_concept_context", lambda *a, **k: "")

    def _rows(case_id, ct, section, storage_type):
        assert case_id == 8 and ct == concept_type and section == 'discussion'
        return rows if storage_type == 'individual' else []
    monkeypatch.setattr(prompt_building, "load_prior_section_rows", _rows)

    tmpl = _RecordingTemplate()
    ext = _bare(concept_type, template=tmpl)
    ext._build_prompt("Discussion text.", "discussion", case_id=8)
    existing = tmpl.last_variables[f"existing_{concept_type}_text"]
    assert marker in existing
    assert existing == tmpl.last_variables["existing_entities_text"]


def test_facts_pass_prompt_has_no_prior_block(monkeypatch):
    monkeypatch.setattr("app.services.prompt_variable_resolver.reuse_block_for_concept",
                        lambda *a, **k: "")
    monkeypatch.setattr(prompt_building, "format_cross_concept_context", lambda *a, **k: "")
    monkeypatch.setattr(prompt_building, "load_prior_section_rows",
                        lambda *a, **k: pytest.fail("the facts pass must not load prior rows"))
    tmpl = _RecordingTemplate()
    ext = _bare("principles", template=tmpl)
    ext._build_prompt("Facts text.", "facts", case_id=8)
    assert "ALREADY EXTRACTED" not in tmpl.last_variables["existing_principles_text"]


# ---------------------------------------------------------------------------
# L2 / L8: per-pass directives (code-side blocks)
# ---------------------------------------------------------------------------

def test_obligations_facts_directive_emits_unclear_and_code_wording():
    d = concept_ontology_slots('obligations', 'facts')['pass_directive']
    assert 'compliance_status "unclear"' in d
    assert "Code's own wording plus the Board's application" in d


def test_obligations_discussion_directive_confirms_or_revises_every_status():
    d = concept_ontology_slots('obligations', 'discussion')['pass_directive']
    assert 'confirm or revise each one' in d
    assert 'SAME identifier' in d


def test_constraints_facts_directive_routes_holdings_to_discussion():
    d = concept_ontology_slots('constraints', 'facts')['pass_directive']
    assert 'is a HOLDING' in d and 'return empty arrays' in d


def test_principles_facts_directive_keeps_tension_resolution_empty():
    d = concept_ontology_slots('principles', 'facts')['pass_directive']
    assert 'leave tension_resolution EMPTY' in d
    assert 'unresolved in the facts' in d


@pytest.mark.parametrize("section", ["facts", "discussion"])
def test_states_directive_asks_for_narrative_order(section):
    d = concept_ontology_slots('states', section)['pass_directive']
    assert 'active_period in narrative order' in d


# ---------------------------------------------------------------------------
# L6: classes minted by an earlier run of this case leave the "from other cases" block
# ---------------------------------------------------------------------------

_EXT = 'proethica-intermediate-extended'
_ENTITIES = [
    {'uri': 'http://x#PublicWelfarePrinciple', 'label': 'Public Welfare Principle',
     'description': 'Canonical.', 'ontology_name': 'proethica-intermediate'},
    {'uri': 'http://x#StormwaterSafeguardPrinciple', 'label': 'Stormwater Safeguard Principle',
     'description': 'Minted by run 35 of case 8.', 'ontology_name': _EXT,
     'properties': {'discoveredInCase': ['8']}},
    {'uri': 'http://x#ClientCandorPrinciple', 'label': 'Client Candor Principle',
     'description': 'Seen in two cases.', 'ontology_name': _EXT,
     'properties': {'discoveredInCase': ['8', '12']}},
    {'uri': 'http://x#LowercaseKeyPrinciple', 'label': 'Lowercase Key Principle',
     'description': 'Lowercased property key, scalar value.', 'ontology_name': _EXT,
     'properties': {'discoveredincase': 8}},
    {'uri': 'http://x#NoProvenancePrinciple', 'label': 'No Provenance Principle',
     'description': 'No discoveredInCase at all.', 'ontology_name': _EXT},
]


def test_discovered_in_cases_normalizes_shapes():
    assert discovered_in_cases(_ENTITIES[1]) == {'8'}
    assert discovered_in_cases(_ENTITIES[2]) == {'8', '12'}
    assert discovered_in_cases(_ENTITIES[3]) == {'8'}
    assert discovered_in_cases(_ENTITIES[4]) == set()
    assert discovered_in_cases({'properties': {'discoveredInCase': 'http://proethica.org/ontology/case/8'}}) == {'8'}


def test_prior_run_classes_are_set_apart_for_the_current_case(monkeypatch):
    monkeypatch.setattr("app.services.prompt_variable_resolver.reuse_block_for_concept",
                        lambda *a, **k: "")
    text = format_existing_entities(_ENTITIES, 'principles', current_case_id=8)
    other, _, prior = text.partition('=== CLASSES MINTED BY AN EARLIER RUN OF THIS SAME CASE ===')
    assert prior, "the prior-run block is missing"
    assert '=== PREVIOUSLY EXTRACTED CLASSES (from other cases) ===' in other
    # only-this-case provenance (list or lowercased scalar) moves to the prior-run block
    assert 'Stormwater Safeguard Principle' in prior and 'Stormwater Safeguard Principle' not in other
    assert 'Lowercase Key Principle' in prior and 'Lowercase Key Principle' not in other
    # cross-case and provenance-less classes stay cross-case evidence
    assert 'Client Candor Principle' in other and 'Client Candor Principle' not in prior
    assert 'No Provenance Principle' in other and 'No Provenance Principle' not in prior
    assert 'NOT evidence of cross-case recurrence' in prior


def test_without_a_case_id_the_inventory_is_unchanged(monkeypatch):
    monkeypatch.setattr("app.services.prompt_variable_resolver.reuse_block_for_concept",
                        lambda *a, **k: "")
    text = format_existing_entities(_ENTITIES, 'principles')
    assert 'EARLIER RUN OF THIS SAME CASE' not in text
    assert 'Stormwater Safeguard Principle' in text


def test_other_case_id_keeps_everything_cross_case(monkeypatch):
    monkeypatch.setattr("app.services.prompt_variable_resolver.reuse_block_for_concept",
                        lambda *a, **k: "")
    text = format_existing_entities(_ENTITIES, 'principles', current_case_id=12)
    assert 'EARLIER RUN OF THIS SAME CASE' not in text


# ---------------------------------------------------------------------------
# L7: owesDutyToward in the controlled relationships vocabulary
# ---------------------------------------------------------------------------

def test_role_relationships_block_offers_owes_duty_toward():
    block = _role_relationships_block()
    assert '- owesDutyToward:' in block
    line = next(l for l in block.splitlines() if l.startswith('- owesDutyToward:'))
    # the cue is the ontology's own comment (Canon 1) plus the target and archetype note
    assert 'Canon 1' in line and 'PublicInterest' in line and 'public_responsibility' in line
    # the derived relatedTo family is intact
    for n in ('hasClient', 'employedBy', 'professionalPeerOf', 'reviewsWorkOf', 'workReviewedBy'):
        assert f'- {n}:' in block
    assert block.count('- owesDutyToward:') == 1


# ---------------------------------------------------------------------------
# L9: role directives (code-side)
# ---------------------------------------------------------------------------

def test_role_directives_carry_the_case8_rules():
    d = _role_directives_block()
    assert 'When a CANONICAL class and a PREVIOUSLY EXTRACTED class both fit a role, match the canonical' in d
    assert '`generates_obligations`' in d
    assert 'never a new role facet' in d


# ---------------------------------------------------------------------------
# L6 (second half): the canonicalizer lists the classes the matcher already matched
# ---------------------------------------------------------------------------

class _StubCanonTemplate:
    def render(self, **kw):
        return f"{kw['reuse_block']}\n\nENTITIES:\n{kw['entities_text']}"


def test_canonicalize_prompt_lists_matched_classes(monkeypatch):
    from app.services.entity import entity_reconciliation_service as ers
    monkeypatch.setattr(ers, "_load_merge_canonicalize_template", lambda: _StubCanonTemplate())
    svc = object.__new__(ers.EntityReconciliationService)
    entities = [
        SimpleNamespace(id=10, entity_label='Faithful Agent Limit Constraint',
                        entity_definition='Limit on faithful agency.', rdf_json_ld={},
                        matched_ontology_label='FaithfulAgentConstraint',
                        matched_ontology_uri='http://proethica.org/ontology/intermediate-extended#FaithfulAgentConstraint'),
        SimpleNamespace(id=11, entity_label='Stormwater Compliance Constraint',
                        entity_definition='Unmatched.', rdf_json_ld={},
                        matched_ontology_label=None, matched_ontology_uri=None),
    ]
    prompt = svc._build_canonicalize_prompt('constraints', 'SHEET BLOCK', entities)
    assert prompt.startswith('SHEET BLOCK')
    assert '=== ALREADY-MATCHED CLASSES (reuse these targets as-is) ===' in prompt
    assert ('[ID: 10] "Faithful Agent Limit Constraint" -> already matched to existing class '
            '"FaithfulAgentConstraint" (http://proethica.org/ontology/intermediate-extended#FaithfulAgentConstraint)') in prompt
    matched_block = prompt.split('=== ALREADY-MATCHED CLASSES')[1].split('ENTITIES:')[0]
    assert 'Stormwater Compliance Constraint' not in matched_block
    assert 'never GENERALIZE' in prompt


def test_canonicalize_prompt_without_matches_is_unchanged(monkeypatch):
    from app.services.entity import entity_reconciliation_service as ers
    monkeypatch.setattr(ers, "_load_merge_canonicalize_template", lambda: _StubCanonTemplate())
    svc = object.__new__(ers.EntityReconciliationService)
    entities = [SimpleNamespace(id=11, entity_label='X Constraint', entity_definition='d', rdf_json_ld={},
                                matched_ontology_label=None, matched_ontology_uri=None)]
    prompt = svc._build_canonicalize_prompt('constraints', 'SHEET BLOCK', entities)
    assert prompt == 'SHEET BLOCK\n\nENTITIES:\n[ID: 11] "X Constraint" -- d'


# ---------------------------------------------------------------------------
# A/B reading of 2026-10-23: the Board of Ethical Review is the deliberative body, not a participant
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("concept,slot_name", [("capabilities", "capability_boundary"),
                                               ("states", "state_boundary"),
                                               ("constraints", "constraint_boundary")])
def test_boundary_slot_excludes_the_board_as_participant(concept, slot_name):
    slot = concept_ontology_slots(concept, 'discussion')[slot_name]
    assert 'DELIBERATIVE BODY' in slot and 'NSPE Board of Ethical Review' in slot
    assert 'state licensing board' in slot


def test_resource_boundary_keeps_cited_board_cases():
    """A cited BER case is a CasePrecedent resource: the resources pass gets no Board exclusion."""
    assert 'DELIBERATIVE BODY' not in concept_ontology_slots('resources', 'discussion')['resource_boundary']


def test_role_directives_exclude_the_board_as_a_role():
    from app.services.prompt_variable_resolver import _role_directives_block
    block = _role_directives_block()
    assert 'DELIBERATIVE BODY' in block and 'as a Role' in block
