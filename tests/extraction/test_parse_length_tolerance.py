"""Parse-side tolerance for Field constraints stripped from the structured-output grammar.

Regression tests for the case-7 run-21 (Fable 5) parse drops: BaseCandidate /
BaseIndividual.source_text carries max_length=500, but
_clean_structured_output_node strips maxLength from the LLM-facing grammar
(the Anthropic structured-outputs grammar rejects it), so the model is never
format-constrained to the cap and pasted longer verbatim quotes. The strict
re-application at parse time then discarded four whole items whose ONLY error
was string_too_long:

- principles:  'Judgment Primacy over AI Outputs'            (719 chars)
- obligations: 'Engineer A Public Safety Duty'               (510 chars)
- constraints: 'Engineer A Client Consent Sharing Boundary'  (547 chars)
- constraints: 'Engineer A Judgment Substitution Boundary'   (719 chars)

The fix is a clamp in _normalize_field_names (parsing.py): preserve the full
quote in text_references (no max_length), then truncate source_text to the cap
at a whitespace boundary with NO ellipsis so the snippet stays a verbatim
substring of the case text (verbatim re-ground verifier contract). Because
_parse_and_validate normalizes all items before full-schema validation, the
primary path passes outright and the per-item fallback is repaired too.

Fixtures: tests/mocks/responses/run21_fable/{principles,obligations,
constraints}.json are the VERBATIM raw LLM responses from the run-21
extraction_prompts rows (ids 7580 / 7581 / 7583, case 7).

DB/MCP-free: the extractor is built with object.__new__, mirroring
tests/extraction/test_match_honoring.py.
"""
import copy
import json
from pathlib import Path

import pytest

from app.services.extraction.schemas import (
    CONCEPT_MODELS,
    CONCEPT_SCHEMAS,
    SOURCE_TEXT_MAX_LENGTH,
)
from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
from app.services.extraction.unified_dual_extractor.config import CONCEPT_CONFIG

FIXTURE_DIR = Path(__file__).parent.parent / 'mocks' / 'responses' / 'run21_fable'

#: concept_type -> identifiers of the items run 21 dropped at parse time.
RUN21_DROPPED = {
    'principles': ['Judgment Primacy over AI Outputs'],
    'obligations': ['Engineer A Public Safety Duty'],
    'constraints': ['Engineer A Client Consent Sharing Boundary',
                    'Engineer A Judgment Substitution Boundary'],
}


def _bare_extractor(concept_type):
    ext = object.__new__(UnifiedDualExtractor)
    ext.concept_type = concept_type
    ext.config = CONCEPT_CONFIG[concept_type]
    ext.result_schema = CONCEPT_SCHEMAS[concept_type]
    ext.class_model, ext.individual_model = CONCEPT_MODELS[concept_type]
    return ext


def _raw_response(concept_type):
    with open(FIXTURE_DIR / f'{concept_type}.json') as f:
        return json.load(f)


def _raw_item(concept_type, identifier):
    raw = _raw_response(concept_type)
    key = CONCEPT_CONFIG[concept_type]['individuals_key']
    for item in raw[key]:
        if item.get('identifier') == identifier:
            return item
    raise AssertionError(f'{identifier} not in fixture {concept_type}.json')


# ---------------------------------------------------------------------------
# Run-21 regression: the exact rejected items now parse
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('concept_type,identifier', [
    (ct, ident) for ct, idents in RUN21_DROPPED.items() for ident in idents
])
def test_run21_rejected_item_recovers_per_item(concept_type, identifier):
    """Each run-21-dropped item validates on the per-item fallback path, with
    source_text clamped to the cap and the full quote preserved verbatim."""
    ext = _bare_extractor(concept_type)
    item = _raw_item(concept_type, identifier)
    full_quote = item['source_text']
    assert len(full_quote) > SOURCE_TEXT_MAX_LENGTH, 'fixture drifted'

    parsed = ext._parse_items([copy.deepcopy(item)], ext.individual_model,
                              'individual', case_id=7)

    assert len(parsed) == 1, f'{identifier} still dropped'
    obj = parsed[0]
    assert obj.identifier == identifier
    # Clamped: within the cap, no ellipsis, still a verbatim prefix substring.
    assert 0 < len(obj.source_text) <= SOURCE_TEXT_MAX_LENGTH
    assert full_quote.startswith(obj.source_text)
    assert '…' not in obj.source_text
    assert not obj.source_text.endswith('...')
    # The full quote survives in text_references (no max_length there).
    assert full_quote in obj.text_references


@pytest.mark.parametrize('concept_type', sorted(RUN21_DROPPED))
def test_run21_full_response_passes_primary_path(concept_type, caplog):
    """The complete raw run-21 response validates on the FULL-schema path (no
    per-item fallback, nothing dropped): counts equal the raw channel counts."""
    ext = _bare_extractor(concept_type)
    raw = _raw_response(concept_type)
    n_classes = len(raw[ext.config['classes_key']])
    n_individuals = len(raw[ext.config['individuals_key']])

    with caplog.at_level('WARNING',
                         logger='app.services.extraction.unified_dual_extractor.parsing'):
        classes, individuals = ext._parse_and_validate(
            copy.deepcopy(raw), case_id=7)

    assert len(classes) == n_classes
    assert len(individuals) == n_individuals
    assert 'Full schema validation failed' not in caplog.text
    assert 'Skipping invalid' not in caplog.text
    parsed_ids = {ind.identifier for ind in individuals}
    for ident in RUN21_DROPPED[concept_type]:
        assert ident in parsed_ids


# ---------------------------------------------------------------------------
# Clamp mechanics (synthetic)
# ---------------------------------------------------------------------------

def _normalize(item, concept_type='principles'):
    return _bare_extractor(concept_type)._normalize_field_names(item)


def test_clamp_truncates_at_word_boundary_without_ellipsis():
    src = ('word ' * 130).strip()  # 649 chars of complete words
    item = _normalize({'label': 'X', 'source_text': src})
    clamped = item['source_text']
    assert len(clamped) <= SOURCE_TEXT_MAX_LENGTH
    assert src.startswith(clamped)          # verbatim prefix
    assert not clamped.endswith(' ')        # rstripped
    assert clamped.endswith('word')         # ends on a complete word
    assert '…' not in clamped and not clamped.endswith('...')
    assert src in item['text_references']   # full quote preserved


def test_clamp_no_duplicate_when_full_quote_already_in_refs():
    src = 'a' * 501
    # The bidirectional fallback fires first (refs absent), so the full quote
    # is already in text_references when the clamp runs; no duplicate.
    item = _normalize({'label': 'X', 'source_text': src})
    assert item['text_references'].count(src) == 1


def test_clamp_appends_to_existing_refs_without_losing_them():
    src = 'b' * 40 + ' ' + 'c' * 600
    item = _normalize({'label': 'X', 'source_text': src,
                       'text_references': ['an earlier quote']})
    assert 'an earlier quote' in item['text_references']
    assert src in item['text_references']


def test_clamp_merges_examples_from_case_refs():
    """Refs supplied under the examples_from_case alias are merged into
    text_references (which wins the Pydantic alias choice), not shadowed."""
    src = 'd' * 40 + ' ' + 'e' * 600
    item = _normalize({'label': 'X', 'source_text': src,
                       'examples_from_case': ['aliased quote']})
    assert 'aliased quote' in item['text_references']
    assert src in item['text_references']


def test_source_text_at_cap_is_untouched():
    src = 'f' * SOURCE_TEXT_MAX_LENGTH
    item = _normalize({'label': 'X', 'source_text': src})
    assert item['source_text'] == src


def test_clamp_hard_cuts_unbroken_token():
    # No whitespace anywhere: nothing to retreat to, hard cut at the cap.
    src = 'g' * 700
    item = _normalize({'label': 'X', 'source_text': src})
    assert item['source_text'] == 'g' * SOURCE_TEXT_MAX_LENGTH


def test_clamp_is_idempotent():
    """_parse_and_validate normalizes before validation and _parse_items
    normalizes again; the second pass must be a no-op."""
    src = ('token ' * 120).strip()
    once = _normalize({'label': 'X', 'source_text': src})
    twice = _normalize(copy.deepcopy(once))
    assert twice == once


# ---------------------------------------------------------------------------
# Confidence clamp (ge/le are stripped from the grammar like maxLength)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('raw,expected', [
    (1.5, 1.0), (-0.2, 0.0), (0.85, 0.85), (1, 1.0), (0, 0.0),
])
def test_out_of_range_confidence_is_clamped_not_dropped(raw, expected):
    item = _normalize({'label': 'X', 'confidence': raw})
    assert item['confidence'] == expected
    # And the item validates instead of being discarded.
    ext = _bare_extractor('principles')
    parsed = ext._parse_items(
        [{'identifier': 'X', 'confidence': raw}],
        ext.individual_model, 'individual', case_id=7)
    assert len(parsed) == 1
    assert parsed[0].confidence == expected


def test_non_numeric_confidence_left_for_pydantic():
    # A string confidence is not clamped here; Pydantic coercion still applies.
    item = _normalize({'label': 'X', 'confidence': '0.9'})
    assert item['confidence'] == '0.9'
