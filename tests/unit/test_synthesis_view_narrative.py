"""Narrative-view builder tests: role-instance grouping + tension dedup.

Covers the predecessor branch behaviors (study/fresh-eyes-fixes-2026-05-10):

- 2c704e8 collapses one card per role-instance into one card per named
  individual; the per-character "tensions" list is the union across the
  person's role-instances.
- The dedup key tightened post-second-pass uses truncated entity labels
  (matching the template's |truncate(60)) plus sorted affected-role
  labels, so visually-identical tensions whose extracted labels diverge
  only after the visible-truncation point collapse to one entry.

The builder reads its input from ExtractionPrompt.raw_response (JSON);
each test mocks the ORM query to return a synthetic phase4 narrative
fixture so a single in-process call exercises the grouping + dedup
logic without DB or LLM access.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.validation.synthesis_view_builder import SynthesisViewBuilder


def _make_character(label, is_main=True):
    return {
        'label': label,
        'is_main': is_main,
        'role': label,
        'professional_position': '',
        'ethical_stance': '',
        'motivations': [],
    }


def _make_tension(e1, e2, affected_roles=None, description=''):
    return {
        'description': description,
        'conflict_type': 'role_obligation',
        'entity1_label': e1,
        'entity1_type': 'Obligation',
        'entity2_label': e2,
        'entity2_type': 'Constraint',
        'magnitude_of_consequences': 'high',
        'probability_of_effect': 'high',
        'temporal_immediacy': 'immediate',
        'proximity': 'direct',
        'concentration_of_effect': 'concentrated',
        'affected_role_labels': affected_roles or [],
        'resolution_rationale': '',
    }


def _phase4_payload(characters, tensions, opening_context=''):
    return json.dumps({
        'narrative_elements': {
            'characters': characters,
            'conflicts': tensions,
        },
        'scenario_seeds': {
            'opening_context': opening_context,
            'protagonist_label': characters[0]['label'] if characters else '',
        },
    })


def _build_view(characters, tensions, opening_context=''):
    """Run get_narrative_view with a mocked ExtractionPrompt query."""
    fake_prompt = MagicMock()
    fake_prompt.raw_response = _phase4_payload(characters, tensions, opening_context)

    fake_query = MagicMock()
    fake_query.filter_by.return_value = fake_query
    fake_query.order_by.return_value = fake_query
    fake_query.first.return_value = fake_prompt

    with patch(
        'app.services.validation.synthesis_view_builder.ExtractionPrompt'
    ) as mock_ep:
        mock_ep.query = fake_query
        mock_ep.created_at = MagicMock()
        builder = SynthesisViewBuilder()
        return builder.get_narrative_view(case_id=1)


def test_role_instances_grouped_by_named_individual():
    """Two role-instances of the same named person collapse to one card."""
    chars = [
        _make_character('Engineer A Environmental Engineering Consultant'),
        _make_character('Engineer A Groundwater Infrastructure Design Engineer'),
        _make_character('Client W Environmental Engineering Client'),
    ]
    tensions = [
        _make_tension(
            'Intellectual Authorship Integrity Obligation',
            'Non-Deception Constraint',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
        _make_tension(
            'Responsible Charge Active Review Obligation',
            'AI Tool Competence Boundary Constraint',
            affected_roles=['Engineer A Groundwater Infrastructure Design Engineer'],
        ),
    ]

    view = _build_view(chars, tensions, opening_context='Engineer A and Client W work together.')
    grouped = view['grouped_main_characters']
    short_names = [c['short_name'] for c in grouped]

    assert short_names.count('Engineer A') == 1, (
        f'Expected one card for Engineer A, got {short_names}'
    )
    assert 'Client W' in short_names

    eng_a = next(c for c in grouped if c['short_name'] == 'Engineer A')
    assert len(eng_a['role_suffixes']) == 2, (
        f'Expected two role suffixes, got {eng_a["role_suffixes"]}'
    )
    assert len(eng_a['tensions']) == 2


def test_character_tensions_dedup_on_truncated_label_match():
    """Two tensions identical past the 60-char truncation point dedupe to one.

    Reproduces the second-pass blocker on Case 7 where Engineer A's
    expanded list showed 'Mentorship Succession and Peer Review
    Continuity Obligation Breached By Engineer...' and
    '...Continuity Obligation Violated By Engineer...' as
    visually-identical entries (the differentiator falls past char 60).
    """
    chars = [
        _make_character('Engineer A Environmental Engineering Consultant'),
    ]
    tensions = [
        _make_tension(
            'Mentorship Succession and Peer Review Continuity Obligation Breached By Engineer A',
            'Client Data Confidentiality in AI Tool Use Violated by Engineer A',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
            description='whitespace-noise variant one',
        ),
        _make_tension(
            'Mentorship Succession and Peer Review Continuity Obligation Violated By Engineer A',
            'Client Data Confidentiality in AI Tool Use Violated by Engineer A',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
            description='whitespace-noise variant two',
        ),
    ]

    view = _build_view(chars, tensions, opening_context='Engineer A and Client W work together.')
    eng_a = next(
        c for c in view['grouped_main_characters'] if c['short_name'] == 'Engineer A'
    )
    assert len(eng_a['tensions']) == 1, (
        'Tensions whose first 60 chars + affected roles match should dedup'
    )


def test_character_tensions_with_distinct_labels_kept_separate():
    """Genuinely distinct tensions are not deduped."""
    chars = [
        _make_character('Engineer A Environmental Engineering Consultant'),
    ]
    tensions = [
        _make_tension(
            'Intellectual Authorship Integrity Obligation',
            'Non-Deception Constraint',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
        _make_tension(
            'Client Consent for Third-Party Data Sharing Obligation',
            'Confidential Client Data Input Constraint',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
    ]

    view = _build_view(chars, tensions, opening_context='Engineer A and Client W work together.')
    eng_a = next(
        c for c in view['grouped_main_characters'] if c['short_name'] == 'Engineer A'
    )
    assert len(eng_a['tensions']) == 2


def test_spurious_characters_filtered_citation_pattern():
    """Labels matching 'Case NN-NN' are dropped as prior-BER citations.

    Reproduces Pass 3 finding [6]: case 60's narrative was promoting
    'Case 04-11 Engineer Situation N' (a prior-case reference) into
    the character set.
    """
    chars = [
        _make_character('Engineer A Environmental Engineering Consultant'),
        _make_character('Case 04-11 Engineer Situation N'),
        _make_character('case 24-02 prior reference', is_main=True),
    ]
    view = _build_view(
        chars,
        tensions=[],
        opening_context='Engineer A is the protagonist.',
    )
    labels = [c['label'] for c in view['characters']]
    assert 'Engineer A Environmental Engineering Consultant' in labels
    assert all('Case ' not in l[:5] and 'case ' not in l[:5] for l in labels), (
        f'Citation-pattern characters should be filtered, got {labels}'
    )


def test_spurious_characters_filtered_place_prefixes():
    """Labels beginning with State / City of / Jurisdiction are dropped.

    Reproduces Pass 3 finding [7]: case 19's narrative was promoting
    'State Q' and 'State Z' (jurisdictions, not persons) to main
    characters.
    """
    chars = [
        _make_character('Engineer A Civil Engineer'),
        _make_character('State Q'),
        _make_character('State Z'),
        _make_character('City of Springfield'),
        _make_character('Jurisdiction X'),
    ]
    view = _build_view(
        chars,
        tensions=[],
        opening_context='Engineer A is the protagonist.',
    )
    labels = [c['label'] for c in view['characters']]
    assert labels == ['Engineer A Civil Engineer'], (
        f'Place-prefix characters should be filtered, got {labels}'
    )


def test_short_name_preserves_single_letter_disambiguator():
    """Names like 'City Engineer J' keep the disambiguating letter.

    Reproduces Pass 3 finding [4]: case 11's narrative collapsed
    'City Engineer J' to short_name='City Engineer', losing the
    disambiguating letter and merging two distinct people.
    """
    chars = [
        _make_character('City Engineer J Civil Engineer'),
        _make_character('City Engineer R Mechanical Engineer'),
    ]
    view = _build_view(
        chars,
        tensions=[],
        opening_context='City Engineer J and City Engineer R disagree.',
    )
    grouped = view['grouped_main_characters']
    short_names = sorted(c['short_name'] for c in grouped)
    assert short_names == ['City Engineer J', 'City Engineer R'], (
        f'Single-letter disambiguators must be preserved, got {short_names}'
    )


def test_character_tension_count_matches_visible_list():
    """tension_count equals len(tensions) post-dedup so badge and expander agree."""
    chars = [
        _make_character('Engineer A Environmental Engineering Consultant'),
    ]
    tensions = [
        _make_tension(
            'Mentorship Succession and Peer Review Continuity Obligation Breached By Engineer A',
            'Client Data Confidentiality in AI Tool Use Violated by Engineer A',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
        _make_tension(
            'Mentorship Succession and Peer Review Continuity Obligation Violated By Engineer A',
            'Client Data Confidentiality in AI Tool Use Violated by Engineer A',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
        _make_tension(
            'Intellectual Authorship Integrity Obligation',
            'Non-Deception Constraint',
            affected_roles=['Engineer A Environmental Engineering Consultant'],
        ),
    ]

    view = _build_view(chars, tensions, opening_context='Engineer A and Client W work together.')
    eng_a = next(
        c for c in view['grouped_main_characters'] if c['short_name'] == 'Engineer A'
    )
    assert eng_a['tension_count'] == len(eng_a['tensions']) == 2
