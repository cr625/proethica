"""Sample variable providers for the SHARED prompts.

A cross-cutting prompt (the Individual/type filter, splitter, merge, edge passes) has no case context,
so the prompt editor's Preview / Test tabs cannot resolve its variables from a case the way the main
per-component prompts do. Each provider here returns that prompt's Jinja variables filled with a small,
realistic sample, so Preview shows the prompt filled in and Test runs it live. Add a provider when
migrating another shared prompt to an editable template.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional


def _individual_filter_sample() -> Dict[str, str]:
    """Two ambiguous resource individuals: a genuine artifact (keep) and a type masquerading as an
    instance (drop). Criteria come from the live CRITERIA registry so the sample tracks the code."""
    from app.services.extraction.individual_type_filter import CRITERIA
    crit = CRITERIA['resources']
    items = (
        '[0] individual: "NSPE Code of Ethics"\n'
        '    declared class: "Professional Code"\n'
        '    detail: "the code of ethics cited throughout the case"\n'
        '    signals: none\n\n'
        '[1] individual: "Peer Review Notification Standard Instance"\n'
        '    declared class: "Collegial Notification Before Reporting Standard"\n'
        '    detail: "a general norm stated in the discussion"\n'
        '    signals: LABEL IS ESSENTIALLY ITS CLASS (likely a type, not an instance)'
    )
    return {
        'component': crit.component,
        'unit': crit.unit,
        'keep_examples': crit.keep_examples,
        'drop_kinds': crit.drop_kinds,
        'items': items,
    }


def _concept_splitter_sample() -> Dict[str, object]:
    """A compound obligation to decompose, with the obligation few-shot example. example_atomic is a
    list so it renders as the Python list literal the prompt expects."""
    return {
        'concept_type': 'obligation',
        'example_compound': 'Practice only in areas of competence and disclose conflicts of interest',
        'example_atomic': ['Practice only in areas of competence', 'Disclose conflicts of interest'],
        'example_reasoning': 'Two distinct professional duties: competence practice and conflict disclosure',
        'concept_text': 'Maintain confidentiality of project details and report safety violations to the proper authorities',
        'description': '',
    }


def _discussion_segmenter_sample() -> Dict[str, str]:
    """Two discussion paragraphs: a precedent recap (cites BER Case 19-3) and a present-case analysis."""
    return {
        'numbered': (
            "[P0] (cites precedent): In BER Case 19-3, Engineer A chaired a boiler code committee while "
            "Engineer B served as a paid consultant to a manufacturer whose product the committee reviewed.\n"
            "[P1]: Turning to the present case, Engineer L must decide whether to disclose to the client a "
            "conflict arising from a prior consulting relationship."
        ),
    }


def _temporal_sequence_sample() -> Dict[str, object]:
    """Three Action/Event entries in arbitrary order, to be chronologized."""
    items = (
        "IRI: http://proethica.org/case7#Action_SubmitDesign\n"
        "Kind: Action\nLabel: Engineer L submits the structural design\n"
        "TemporalMarker: after the review\n"
        "Description: L finalizes and submits the design package to the client.\n\n"
        "IRI: http://proethica.org/case7#Event_DataExposure\n"
        "Kind: Event\nLabel: Client data is exposed\n"
        "TemporalMarker: early in the project\n"
        "Description: A misconfigured server exposes client data before any design work.\n\n"
        "IRI: http://proethica.org/case7#Action_PeerReview\n"
        "Kind: Action\nLabel: Engineer M reviews the design\n"
        "Description: M performs a peer review prior to submission.\n"
    )
    return {'case_id': 7, 'n_entries': 3, 'items': items}


def _obligation_engagement_sample() -> Dict[str, object]:
    """Two actions: one that violates a competence obligation, one whose review resolves it."""
    actions_block = (
        "IRI: http://proethica.org/case7#Action_UseUnvettedTool\n"
        "Sequence: 1\nLabel: Engineer L uses an unvetted AI tool for the design\n"
        "Description: L adopts a new generative tool without verifying its competence basis.\n"
        "Fulfills (input):\n"
        "Violates (input):\n"
        "  - Practice only in areas of competence\n\n"
        "IRI: http://proethica.org/case7#Action_PeerReview\n"
        "Sequence: 2\nLabel: Engineer M peer-reviews the output\n"
        "Description: M reviews and corrects the tool's output before submission.\n"
        "Fulfills (input):\n"
        "  - Practice only in areas of competence\n"
        "Violates (input):\n"
    )
    return {'case_id': 7, 'case_title': 'AI in Engineering Design', 'action_count': 2,
            'discussion_excerpt': "The Board considered whether using the tool breached competence, "
                                  "and whether the later review cured it.",
            'actions_block': actions_block}


def _board_conclusions_sample() -> Dict[str, object]:
    """Two board questions needing conclusions, with a short Discussion to draw from."""
    return {'case_id': 7, 'case_title': 'AI in Engineering Design',
            'gap_questions': "  Q1: Was it ethical for Engineer L to use the unvetted tool?\n"
                             "  Q2: Did peer review discharge the competence obligation?",
            'discussion_text': "The Board found that using a new tool is permissible only when the "
                               "engineer retains the competence to evaluate its output. Here, Engineer M's "
                               "review supplied that competence, so the obligation was met at the review step.",
            'conclusion_text': '', 'gap_count': 2}


# Registry keyed by the shared prompt's concept_type (matches the seeded template row).
_PROVIDERS: Dict[str, Callable[[], Dict]] = {
    'individual_filter': _individual_filter_sample,
    'concept_splitter': _concept_splitter_sample,
    'discussion_segmenter': _discussion_segmenter_sample,
    'temporal_sequence': _temporal_sequence_sample,
    'obligation_engagement': _obligation_engagement_sample,
    'board_conclusions': _board_conclusions_sample,
}


def is_shared_prompt(concept_type: str) -> bool:
    """True if `concept_type` is a shared prompt with a registered sample provider."""
    return concept_type in _PROVIDERS


def shared_prompt_sample(concept_type: str) -> Optional[Dict[str, str]]:
    """The sample Jinja variables for a shared prompt's editable template, or None if it is not a
    registered shared prompt."""
    provider = _PROVIDERS.get(concept_type)
    return provider() if provider else None
