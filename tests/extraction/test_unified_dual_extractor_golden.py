"""Golden-output characterization tests for UnifiedDualExtractor.

Written BEFORE the unified_dual_extractor.py -> package split (services
modularization, 2026-06-19). The expected values below were captured from the
live single-file module and must be reproduced byte-identically after the
refactor, because the extractor's emitted entities feed the pending Section-C
re-extraction (idempotency-critical).

DB/LLM-free: instances are built with object.__new__ to bypass __init__ (which
loads MCP, DB templates, schemas); the LLM is a canned mock and the chain
resolver is monkeypatched. Each test exercises a different prospective mixin:

  - _build_prompt / _format_existing_entities  -> prompt_building
  - extract / _check_existing_matches / _link  -> matching + orchestration
  - _parse_and_validate / _normalize_field_names / _repair_truncated_json -> parsing
  - _execute_tool_call                          -> llm_calls

so a NameError from a relocated body that lost a module-level import surfaces
here rather than in production.
"""
import json

from app.services.extraction import category_resolver
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
from app.services.extraction.schemas import CONCEPT_SCHEMAS, CONCEPT_MODELS
from app.services.extraction.unified_dual_extractor import CONCEPT_CONFIG


# Suffix build_json_wrapper_suffix('roles') appends after the rendered template.
_ROLES_JSON_SUFFIX = (
    '\n\nIMPORTANT: Wrap your response as a JSON object with exactly two keys:\n'
    '{"new_role_classes": [...], "role_individuals": [...]}\n'
    'If there are no individuals to report, use an empty array for '
    '"role_individuals".'
)

# format_existing_entities(...) output for the single-class fixture below.
_EXISTING_ROLES_TEXT = (
    '=== CANONICAL ONTOLOGY CLASSES (roles) ===\n'
    'Hand-curated classes from the formal ontology. Match to these with high '
    'confidence.\n'
    '- Engineer Role: A licensed engineer.'
)


def _bare(concept_type, **attrs):
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.config = CONCEPT_CONFIG[concept_type]
    ext.existing_classes = []
    ext.injection_mode = "full"
    for k, v in attrs.items():
        setattr(ext, k, v)
    return ext


class _RecordingTemplate:
    """Deterministic stand-in for an ExtractionPromptTemplate row."""

    def __init__(self):
        self.last_variables = None

    def render(self, **variables):
        self.last_variables = variables
        return "RENDERED_BODY"


# ---------------------------------------------------------------------------
# 1. prompt_building: _build_prompt + _format_existing_entities
# ---------------------------------------------------------------------------

def test_build_prompt_golden():
    tmpl = _RecordingTemplate()
    ext = _bare(
        "roles",
        template=tmpl,
        existing_classes=[
            {"uri": "http://x#EngineerRole", "label": "Engineer Role",
             "description": "A licensed engineer."},
        ],
    )

    # \x07 (BEL) is a non-printable control char -> stripped by _build_prompt.
    prompt = ext._build_prompt("Engineer L\x07 did things.", "facts", case_id=None)

    # The variable dict assembled for the template (case_text control-char
    # stripped; no cross-concept context for roles; existing entities formatted).
    assert tmpl.last_variables == {
        "case_text": "Engineer L did things.",
        "section_type": "facts",
        "existing_roles_text": _EXISTING_ROLES_TEXT,
        "existing_entities_text": _EXISTING_ROLES_TEXT,
        "cross_concept_context": "",
    }
    # The final prompt = rendered body + the code-appended JSON wrapper suffix.
    assert prompt == "RENDERED_BODY" + _ROLES_JSON_SUFFIX


# ---------------------------------------------------------------------------
# 2. orchestration + matching + linking: extract()
# ---------------------------------------------------------------------------

_LLM_JSON = {
    "new_role_classes": [
        {"label": "Engineer Role", "definition": "An engineer.",
         "text_references": ["Engineer L did X"]},
        {"label": "Client Role", "definition": "The client.",
         "confidence": 0.8, "examples_from_case": ["the client"]},
    ],
    "role_individuals": [
        {"identifier": "Engineer L", "role_class": "Engineer Role",
         "text_references": ["Engineer L"]},
    ],
}


class _MockLLM:
    def call(self, prompt, extraction_type, section_type):
        class _R:
            content = json.dumps(_LLM_JSON)
        return _R()


def test_extract_transform_golden(monkeypatch):
    # Keep the cross-category gate deterministic regardless of TTL state.
    monkeypatch.setattr(
        category_resolver, "resolve_core_category", lambda _ref: "Role",
    )
    schema = CONCEPT_SCHEMAS["roles"]
    class_model, individual_model = CONCEPT_MODELS["roles"]
    ext = _bare(
        "roles",
        template=_RecordingTemplate(),
        llm_client=_MockLLM(),
        mcp_client=None,
        result_schema=schema,
        class_model=class_model,
        individual_model=individual_model,
        existing_classes=[
            {"uri": "http://proethica.org/ontology/intermediate#EngineerRole",
             "label": "Engineer Role", "description": "A licensed engineer."},
        ],
        tool_call_count=0,
        tool_call_log=[],
        last_raw_response=None,
        last_prompt=None,
    )
    # Avoid the DB-backed present-case actor lookup.
    ext._present_case_actor_letters = lambda cid: frozenset()

    classes, individuals = ext.extract("case text", case_id=1, section_type="facts")

    assert [c.model_dump() for c in classes] == [
        {"label": "Engineer Role", "definition": "An engineer.",
         "text_references": ["Engineer L did X"], "source_text": "Engineer L did X",
         "confidence": 0.75,
         "match_decision": {
             "matches_existing": True,
             "matched_uri": "http://proethica.org/ontology/intermediate#EngineerRole",
             "matched_label": "Engineer Role", "confidence": 0.9,
             "reasoning": "Label match with existing ontology class"},
         "role_category": None},
        {"label": "Client Role", "definition": "The client.",
         "text_references": ["the client"], "source_text": "the client",
         "confidence": 0.8,
         "match_decision": {"matches_existing": False, "matched_uri": None,
                            "matched_label": None, "confidence": 0.0,
                            "reasoning": None},
         "role_category": None},
    ]
    assert [i.model_dump() for i in individuals] == [
        {"identifier": "Engineer L", "text_references": ["Engineer L"],
         "source_text": "Engineer L", "confidence": 0.75,
         "match_decision": {
             "matches_existing": True,
             "matched_uri": "http://proethica.org/ontology/intermediate#EngineerRole",
             "matched_label": "Engineer Role", "confidence": 0.9,
             "reasoning": "Via class 'Engineer Role': Label match with existing "
                          "ontology class"},
         "name": "Engineer L", "actor": None, "role_class": "Engineer Role",
         "role_category": None, "attributes": {}, "relationships": [],
         "case_involvement": None},
    ]


# ---------------------------------------------------------------------------
# 3. parsing: _parse_and_validate, _normalize_field_names, _repair_truncated_json
# ---------------------------------------------------------------------------

def test_parse_and_validate_golden():
    schema = CONCEPT_SCHEMAS["roles"]
    class_model, individual_model = CONCEPT_MODELS["roles"]
    ext = _bare(
        "roles",
        result_schema=schema,
        class_model=class_model,
        individual_model=individual_model,
    )
    classes, individuals = ext._parse_and_validate(dict(_LLM_JSON), case_id=1)

    assert [c.model_dump() for c in classes] == [
        {"label": "Engineer Role", "definition": "An engineer.",
         "text_references": ["Engineer L did X"], "source_text": "Engineer L did X",
         "confidence": 0.75,
         "match_decision": {"matches_existing": False, "matched_uri": None,
                            "matched_label": None, "confidence": 0.5,
                            "reasoning": "match_decision omitted by LLM; post-hoc "
                                         "matching will resolve"},
         "role_category": None},
        {"label": "Client Role", "definition": "The client.",
         "text_references": ["the client"], "source_text": "the client",
         "confidence": 0.8,
         "match_decision": {"matches_existing": False, "matched_uri": None,
                            "matched_label": None, "confidence": 0.5,
                            "reasoning": "match_decision omitted by LLM; post-hoc "
                                         "matching will resolve"},
         "role_category": None},
    ]
    assert [i.model_dump() for i in individuals] == [
        {"identifier": "Engineer L", "text_references": ["Engineer L"],
         "source_text": "Engineer L", "confidence": 0.75,
         "match_decision": {"matches_existing": False, "matched_uri": None,
                            "matched_label": None, "confidence": 0.0,
                            "reasoning": None},
         "name": "Engineer L", "actor": None, "role_class": "Engineer Role",
         "role_category": None, "attributes": {}, "relationships": [],
         "case_involvement": None},
    ]


def test_normalize_field_names_golden():
    ext = _bare("principles")
    item = {
        "label": "Public Welfare Paramount",
        "definition": "The safety of the public is paramount.",
        "balancing_requirements": ["a", "b"],
        "application_context": "drop me",
        "match_decision": {"matched_class": "Existing Principle"},
        "principle_category": "fundamental-ethical",
    }
    assert ext._normalize_field_names(dict(item)) == {
        "label": "Public Welfare Paramount",
        "definition": "The safety of the public is paramount.",
        "match_decision": {"matches_existing": False, "confidence": 0.5,
                           "reasoning": "No reasoning provided by LLM",
                           "matched_label": "Existing Principle"},
        "principle_category": "fundamental_ethical",
        "identifier": "Public Welfare Paramount",
        "potential_conflicts": ["a", "b"],
        "confidence": 0.75,
    }


def test_normalize_compliance_status_golden():
    ext = _bare("obligations")

    def cs(value):
        return ext._normalize_field_names(
            {"identifier": "X", "compliance_status": value}
        )["compliance_status"]

    assert cs("not_met") == "unmet"             # exact synonym map
    assert cs("potentially_violated") == "partial"
    assert cs("so_breached_thing") == "unmet"   # token fallback ('breached')
    assert cs("weird_value") == "unclear"       # default fallback


def test_repair_truncated_json_golden():
    truncated = (
        '{"new_role_classes": [{"label": "A", "definition": "aaa"}, '
        '{"label": "B", "definition": "bbb'
    )
    assert UnifiedDualExtractor._repair_truncated_json(truncated) == (
        '{"new_role_classes": [{"label": "A", "definition": "aaa"}\n]}'
    )


# ---------------------------------------------------------------------------
# 4. llm_calls: _execute_tool_call (the one DB/LLM-free method in the group)
# ---------------------------------------------------------------------------

def test_execute_tool_call_golden():
    class _MCP:
        def call_tool(self, name, args):
            return {"success": True, "result": {
                "found": True, "definition": "An engineer.",
                "source_ontology": "proethica-core", "parent_type": "Role",
            }}

    ext = _bare("roles", mcp_client=_MCP(), tool_call_count=0, tool_call_log=[])
    out = ext._execute_tool_call("get_class_definition", {"label": "Engineer Role"})

    assert out == (
        "Class: Engineer Role\nDefinition: An engineer.\n"
        "Source ontology: proethica-core\nParent class: Role"
    )
    assert ext.tool_call_log == [
        {"label": "Engineer Role", "found": True,
         "source": "proethica-core", "concept_type": "roles"},
    ]
    assert ext.tool_call_count == 1
