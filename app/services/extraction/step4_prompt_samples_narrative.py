"""Sample variable providers for the batch-narrative Step-4 prompt templates (P19-P27).

Each provider returns the full Jinja variables dict for one seeded
step4_* template, with realistic no-case values shaped exactly like the
production builders' output (bulleted entity lists, conflict_id-keyed tension
lines, indented branch summaries). Used by the /tools/prompts Preview/Test
tabs, which have no case context for Step-4 prompts.
"""
from __future__ import annotations

from typing import Callable, Dict

from app.services.prompt_style import STYLE_FORMATTING_LINE

_SAMPLE_FACTS = (
    'Engineer A, a licensed professional engineer, performed a structural '
    'inspection of a parking garage owned by Client W. The inspection found '
    'deteriorated support columns that Engineer A judged to present a risk to '
    'public safety. Client W directed Engineer A to keep the findings '
    'confidential while repair negotiations proceeded.'
)

_SAMPLE_QUESTION = (
    'Should Engineer A disclose the structural deficiencies to the local '
    'building authority despite the confidentiality directive from Client W?'
)


def _characters_sample() -> Dict[str, object]:
    return {
        'facts_block': _SAMPLE_FACTS,
        'character_list': ('- Engineer A: Licensed structural engineer\n'
                           '- Client W: Role'),
        'obligations_list': ('- Hold paramount the safety of the public\n'
                             '- Maintain client confidentiality'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _tensions_sample() -> Dict[str, object]:
    return {
        'obligations_list': (
            '- [Obligation_public_safety] Hold paramount the safety of the public\n'
            '- [Obligation_client_confidentiality] Maintain client confidentiality'),
        'constraints_list': (
            '- [Constraint_contract_terms] Contractual confidentiality clause'),
        'roles_list': '- Engineer A\n- Client W',
        'existing_tensions': (
            '[tension_1] Hold paramount the safety of the public vs Maintain '
            'client confidentiality: Public safety duty conflicts with the '
            'confidentiality directive\n'
            '[tension_2] Hold paramount the safety of the public vs Contractual '
            'confidentiality clause'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _timeline_sample() -> Dict[str, object]:
    return {
        'event_list': (
            '1. [Initial Situation] Structural inspection: Engineer A inspects '
            'the parking garage for Client W and documents deteriorated support '
            'columns...\n'
            '2. [Conflict Emerges] Confidentiality directive: Client W directs '
            'Engineer A to keep the findings confidential...'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _option_label_sample() -> Dict[str, object]:
    return {
        'question': _SAMPLE_QUESTION,
        'obligations_text': ('Hold paramount the safety of the public, '
                             'Maintain client confidentiality'),
        'option_number': 1,
        'is_board_choice': True,
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _option_set_sample() -> Dict[str, object]:
    return {
        'question': _SAMPLE_QUESTION,
        'obligations_text': ('Hold paramount the safety of the public, '
                             'Maintain client confidentiality'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _opening_sample() -> Dict[str, object]:
    return {
        'case_facts': _SAMPLE_FACTS,
        'setting_description': ('Commercial parking garage assessment for a '
                                'private client'),
        'primary_maker': 'Engineer A',
        'branch_summary': (
            f'  1. [Engineer A] {_SAMPLE_QUESTION}\n'
            '  2. [Engineer A] Should Engineer A continue the engagement while '
            'repairs are negotiated?'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _insights_sample() -> Dict[str, object]:
    return {
        'conflicts_desc': (
            '- Public safety duty conflicts with the confidentiality directive\n'
            '- Duty of loyalty to the client conflicts with the duty to report hazards'),
        'resolution_desc': (
            'The Board concluded that Engineer A must notify the responsible '
            'authorities because public safety takes precedence over client '
            'confidentiality'),
        'transformation_type': 'transfer',
        'principles_desc': (
            '- Public Safety Paramountcy: Overrode the confidentiality directive '
            'once a danger to the public was identified\n'
            '- Truthfulness in Professional Reporting: Required accurate '
            'reporting of the inspection findings'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _case_summary_sample() -> Dict[str, object]:
    return {
        'case_title': 'Case 24-2: Structural Deficiencies and Client Confidentiality',
        'facts_text': _SAMPLE_FACTS,
        'participants': 'Engineer A, Client W',
        'obligations': ('Hold paramount the safety of the public, '
                        'Maintain client confidentiality'),
        'decision_points': f'- {_SAMPLE_QUESTION}',
        'board_conclusions': (
            '- Engineer A has an obligation to report the deteriorated support '
            'columns to the appropriate authority.\n'
            '- The duty of client confidentiality yields when the public safety '
            'obligation is engaged.'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


def _timeline_phases_sample() -> Dict[str, object]:
    return {
        'case_title': 'Case 24-2: Structural Deficiencies and Client Confidentiality',
        'roles': 'Engineer A, Client W',
        'states': 'Structural deficiency identified',
        'actions': 'Conduct structural inspection',
        'events': 'Client issues confidentiality directive',
        'decision_points': f'1. {_SAMPLE_QUESTION}',
        'conclusions': (
            '- Engineer A has an obligation to report the deteriorated support '
            'columns to the appropriate building authority.\n'
            '- The duty of client confidentiality yields when the public safety '
            'obligation is engaged.'),
        'style_formatting_line': STYLE_FORMATTING_LINE,
    }


PROVIDERS: Dict[str, Callable[[], Dict[str, object]]] = {
    'step4_narrative_characters': _characters_sample,
    'step4_narrative_tensions': _tensions_sample,
    'step4_narrative_timeline': _timeline_sample,
    'step4_narrative_option_label': _option_label_sample,
    'step4_narrative_option_set': _option_set_sample,
    'step4_narrative_opening': _opening_sample,
    'step4_narrative_insights': _insights_sample,
    'step4_case_summary': _case_summary_sample,
    'step4_timeline_phases': _timeline_phases_sample,
}
