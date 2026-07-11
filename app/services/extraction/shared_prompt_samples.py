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


def _rpo_edges_sample() -> Dict[str, object]:
    """One Role, Principle, Obligation plus a state-transformation grounding line. The per-individual
    blocks come from the live rpo_edges formatters so the sample tracks the real prompt; property_axioms
    is the verbatim ontology block the system prompt injects."""
    from app.services.extraction.rpo_edges import (
        Indiv, _fmt, _fmt_transformations, property_axioms_block)
    roles = [Indiv("http://proethica.org/case7#Engineer_A_Role", "Engineer A",
                   {"roleClass": "EngineerRole", "caseInvolvement": "lead designer on the project"})]
    principles = [Indiv("http://proethica.org/case7#Public_Welfare_Principle", "Public Welfare",
                        {"principleClass": "PublicWelfare", "invokedBy": "Engineer A"})]
    obligations = [Indiv("http://proethica.org/case7#Report_Findings_Obligation", "Report Findings",
                         {"obligationStatement": "must report safety-relevant findings to the client"})]
    transformations = [("Risk State", "the risk state turns the public-welfare principle into a "
                        "concrete reporting obligation")]
    return {
        'property_axioms': property_axioms_block(),
        'case_id': 7,
        'roles_block': _fmt(roles),
        'principles_block': _fmt(principles),
        'obligations_block': _fmt(obligations),
        'transformations_block': _fmt_transformations(transformations),
    }


def _defeasibility_edges_sample() -> Dict[str, object]:
    """Two competing obligations, one conflict state, one narrative justification. Blocks come from the
    live defeasibility formatters; property_axioms_block is the verbatim proethica-core.ttl block the
    system prompt injects."""
    from app.services.extraction.enhanced_prompts_defeasibility import (
        ObligationContext, StateContext, NarrativeContext,
        _format_obligations, _format_states, _format_narratives, property_axioms_block)
    obligations = [
        ObligationContext(iri="http://proethica.org/case7#Safety_Obligation", label="Safety",
                          statement="protect the public welfare", obligated_party="Engineer A"),
        ObligationContext(iri="http://proethica.org/case7#Loyalty_Obligation", label="Loyalty",
                          statement="serve the client faithfully"),
    ]
    states = [StateContext(iri="http://proethica.org/case7#Conflict_State", label="Conflict",
                           state_class="ConflictState", triggering_event="client instruction to suppress")]
    narratives = [NarrativeContext(source_iri="http://proethica.org/case7#Tension", source_label="Tension",
                                   source_field="tensionresolution",
                                   text="public welfare overrides loyalty when safety is at stake")]
    return {
        'property_axioms_block': property_axioms_block(),
        'case_tag': 'case 7',
        'obligations_block': _format_obligations(obligations),
        'states_block': _format_states(states),
        'narratives_block': _format_narratives(narratives),
    }


def _merge_pair_eval_sample() -> Dict[str, str]:
    """Two same-actor roles (the canonical keep_separate case). concept_line carries the Roles category
    definition with its leading/trailing newlines, exactly as the live builder assembles it."""
    return {
        'type_label': 'Roles',
        'storage_label': 'class',
        'concept_line': ('\nCategory: Professional roles and role-bearers (e.g., "Engineer A", '
                         '"Structural Design Engineer"). Different roles of the same person are DISTINCT.\n'),
        'pairs_text': ('Pair 1: [ID: 1] "Engineer A Design Role" (source: facts)\n'
                       '     vs [ID: 2] "Engineer A Safety Role" (source: discussion)\n'
                       '  A: "The role of Engineer A in the design phase"\n'
                       '  B: "The role of Engineer A in the safety review"'),
    }


def _merge_canonicalize_sample() -> Dict[str, str]:
    """A compound obligation to generalize plus a clean one to keep. reuse_block is the live reference-
    sheet block for obligations (the OntServe-derived controlled vocabulary), fed from source."""
    from app.services.extraction.reference_sheet import reuse_block_for_concept
    return {
        'type_label': 'Obligations',
        'reuse_block': reuse_block_for_concept('obligations'),
        'entities_text': ('[ID: 10] "AI Tool Disclosure Obligation" -- Duty to disclose use of the AI tool\n'
                          '[ID: 11] "Confidentiality Obligation" -- Keep client information secret'),
    }


# Registry keyed by the shared prompt's concept_type (matches the seeded template row).
_PROVIDERS: Dict[str, Callable[[], Dict]] = {
    'individual_filter': _individual_filter_sample,
    'concept_splitter': _concept_splitter_sample,
    'discussion_segmenter': _discussion_segmenter_sample,
    'temporal_sequence': _temporal_sequence_sample,
    'obligation_engagement': _obligation_engagement_sample,
    'board_conclusions': _board_conclusions_sample,
    'rpo_edges': _rpo_edges_sample,
    'defeasibility_edges': _defeasibility_edges_sample,
    'merge_pair_eval': _merge_pair_eval_sample,
    'merge_canonicalize': _merge_canonicalize_sample,
}

# The Step-4 synthesis family (step_number=4 rows) registers per-batch provider
# modules; same Preview/Test contract as the shared prompts above.
for _mod in ('step4_prompt_samples_qc', 'step4_prompt_samples_rich_dp',
             'step4_prompt_samples_analysis', 'step4_prompt_samples_narrative'):
    _m = __import__(f'app.services.extraction.{_mod}', fromlist=['PROVIDERS'])
    _PROVIDERS.update(_m.PROVIDERS)


def is_shared_prompt(concept_type: str) -> bool:
    """True if `concept_type` is a shared prompt with a registered sample provider."""
    return concept_type in _PROVIDERS


def shared_prompt_sample(concept_type: str) -> Optional[Dict[str, str]]:
    """The sample Jinja variables for a shared prompt's editable template, or None if it is not a
    registered shared prompt."""
    provider = _PROVIDERS.get(concept_type)
    return provider() if provider else None
