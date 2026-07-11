"""Sample variable providers for the batch-rich-dp Step-4 prompt templates
(P6-P12: rich analysis, decision-point synthesis, board-choice verify).

Each provider returns the full variables dict its template renders with,
populated with realistic no-case sample values, so /tools/prompts Preview
works without a case. Shared constants (STYLE_FORMATTING_LINE,
TOULMIN_FIELD_SPEC) come from their single code sources at call time,
matching what the live builders pass.
"""
import json


def _style_line():
    from app.services.prompt_style import STYLE_FORMATTING_LINE
    return STYLE_FORMATTING_LINE


def _toulmin_spec():
    from app.services.decision_point_synthesizer.strategies import TOULMIN_FIELD_SPEC
    return TOULMIN_FIELD_SPEC


_QUESTIONS = [
    'Was it ethical for Engineer A to seal drawings produced with AI assistance without full verification?',
    'Did Engineer A have an obligation to disclose the use of AI tools to the client?',
]

_CONCLUSIONS = [
    'It was unethical for Engineer A to seal the drawings without full verification of the AI-generated calculations.',
    'Engineer A was obligated to disclose the use of AI tools to the client.',
]


def _causal_reasoning_sample():
    actions_text = (
        "A1. Submit Sealed Drawings Without Full Review\n"
        "   fulfills: none\n"
        "   violates: Duty of Competent Practice; Duty to Verify Work Before Sealing\n"
        "   guided by: Public Safety Paramount\n"
        "A2. Disclose AI Tool Usage to Client\n"
        "   fulfills: Duty of Full Disclosure\n"
        "   violates: none\n"
        "   guided by: Honesty and Integrity"
    )
    causal_text = (
        "  - Sealing unverified drawings -> Undetected structural errors reach construction (responsible: Engineer A)\n"
        "  - Disclosing AI tool usage -> Client can weigh the design provenance"
    )
    return {
        'actions_text': actions_text,
        'causal_text': causal_text,
        'action_count': 2,
        'style_formatting_line': _style_line(),
    }


def _question_emergence_sample():
    from app.academic_references.frameworks.toulmin_argumentation import get_concise_emergence_context
    questions_text = "\n".join(
        f"Q{i+1}. Question {i+1}: {q}" for i, q in enumerate(_QUESTIONS))
    entities_text = (
        "\n**Roles:**\n"
        "  - Engineer A: Licensed professional engineer responsible for the structural design.\n"
        "\n**Obligations:**\n"
        "  - Duty of Competent Practice: Perform services only in areas of competence.\n"
        "  - Duty of Full Disclosure: Be objective and truthful; disclose material facts.\n"
        "\n**Actions:**\n"
        "  - Submit Sealed Drawings Without Full Review\n"
        "      [violates] Duty of Competent Practice\n"
        "  - Disclose AI Tool Usage to Client\n"
        "      [fulfills] Duty of Full Disclosure\n"
        "\n**Events:**\n"
        "  - Client Discovers AI Involvement\n"
    )
    return {
        'toulmin_context': get_concise_emergence_context(),
        'questions_text': questions_text,
        'entities_text': entities_text,
        'style_formatting_line': _style_line(),
    }


def _resolution_patterns_sample():
    qe = _question_emergence_sample()
    conclusions_text = "\n".join(
        f"C{i+1}. Conclusion {i+1}: {c}" for i, c in enumerate(_CONCLUSIONS))
    provisions_text = (
        "P1. NSPE II.2.a: II.2.a - Engineers shall undertake assignments only when qualified by education or experience in the specific t\n"
        "P2. NSPE I.1: I.1 - Hold paramount the safety, health, and welfare of the public."
    )
    return {
        'conclusions_text': conclusions_text,
        'questions_text': qe['questions_text'],
        'provisions_text': provisions_text,
        'norm_structure': qe['entities_text'],
        'conclusion_count': 2,
        'style_formatting_line': _style_line(),
    }


def _dp_causal_sample():
    causal_links_block = (
        "\n1. CausalLink_Submit Sealed Drawings Without Full Review\n"
        "   - Action: Submit Sealed Drawings Without Full Review\n"
        "   - Obligation: []\n"
        "   - Violates: ['Duty of Competent Practice']\n"
        "   - Description: Sealing without verification exposed the public to undetected structural errors.\n"
        "\n"
        "\n2. CausalLink_Disclose AI Tool Usage to Client\n"
        "   - Action: Disclose AI Tool Usage to Client\n"
        "   - Obligation: ['Duty of Full Disclosure']\n"
        "   - Violates: []\n"
        "   - Description: Disclosure let the client weigh the provenance of the design.\n"
    )
    return {
        'causal_links_block': causal_links_block,
        'questions_block': "\n".join(f"Q{i+1}: {q}" for i, q in enumerate(_QUESTIONS)),
        'conclusions_block': "\n".join(f"C{i+1}: {c}" for i, c in enumerate(_CONCLUSIONS)),
        'toulmin_field_spec': _toulmin_spec(),
    }


def _dp_qc_direct_sample():
    return {
        'questions_block': "\n".join(f"Q{i+1} [board]: {q}" for i, q in enumerate(_QUESTIONS)),
        'conclusions_block': "\n".join(f"C{i+1} [board]: {c}" for i, c in enumerate(_CONCLUSIONS)),
        'qe_block': (
            "QE1 (re Q1): The question arises because sealing implies personal verification while the calculations came from an opaque AI tool.\n"
            "QE2 (re Q2): The question arises because the client relied on the firm for engineering judgment without knowing its provenance."
        ),
        'rp_block': (
            "RP1 (re C1): The board weighed the duty of competent practice over schedule pressure and found the cursory review inadequate."
        ),
        'obligations_block': (
            "O1: Duty of Competent Practice -- Perform services only in areas of competence.\n"
            "O2: Duty of Full Disclosure -- Be objective and truthful; disclose material facts."
        ),
        'roles_block': "R1: Engineer A\nR2: Client Representative",
        'toulmin_field_spec': _toulmin_spec(),
    }


def _dp_refine_sample():
    candidates_block = (
        "\n### DP1 (Q&C Alignment: 0.82)\n"
        "- Description: Engineer A must decide how rigorously to verify AI-generated structural calculations before sealing.\n"
        "- Question: Should Engineer A conduct a full independent review of the AI-generated calculations before sealing the drawings?\n"
        "- Role: Engineer A [http://proethica.org/cases/9#Role_1]\n"
        "- Obligation: Duty of Competent Practice [http://proethica.org/cases/9#Obligation_1]\n"
        "- Matched Questions: Q0\n"
        "- Options:\n"
        "    O1: Conduct full independent technical review of all AI outputs before sealing [alternative]\n"
        "    O2: Apply standard firm QA protocols to AI outputs [chosen]"
    )
    questions_block = (
        "\nQ0: " + _QUESTIONS[0] + "\n"
        "  - URI: http://proethica.org/cases/9#Question_1\n"
        "  - DATA (triggering facts): Client Discovers AI Involvement, Submit Sealed Drawings Without Full Review\n"
        "  - WARRANTS (competing obligations): [['Duty of Competent Practice', 'Duty of Full Disclosure']]\n"
        "  - REBUTTAL: Would not apply if the AI outputs had been independently verified before sealing.\n"
    )
    conclusions_block = (
        "\nC0: " + _CONCLUSIONS[0] + "\n"
        "  - URI: http://proethica.org/cases/9#Conclusion_1\n"
        "  - Determinative Principles: Public Safety Paramount\n"
        "  - Resolution: Given the unverified AI calculations, the board concluded the seal attested to work Engineer A had not verified.\n"
    )
    return {
        'case_id': 9,
        'candidates_block': candidates_block,
        'questions_block': questions_block,
        'conclusions_block': conclusions_block,
        'toulmin_field_spec': _toulmin_spec(),
        'target_count': '4-6',
    }


def _dp_board_verify_sample():
    payload = [
        {'id': 'DP1',
         'question': 'Should Engineer A conduct a full independent review of the AI-generated calculations before sealing the drawings?',
         'options': ['Conduct Full Independent Review', 'Apply Standard QA Protocols Only']},
        {'id': 'DP2',
         'question': 'Should Engineer A disclose the use of AI tools to the client before submission?',
         'options': ['Disclose AI Usage to Client', 'Treat AI as Internal Drafting Tool']},
    ]
    return {
        'concl_text': "\n".join(f"- {c}" for c in _CONCLUSIONS),
        'payload_json': json.dumps(payload, indent=1),
    }


PROVIDERS = {
    'step4_causal_reasoning': _causal_reasoning_sample,
    'step4_question_emergence': _question_emergence_sample,
    'step4_resolution_patterns': _resolution_patterns_sample,
    'step4_dp_causal': _dp_causal_sample,
    'step4_dp_qc_direct': _dp_qc_direct_sample,
    'step4_dp_refine': _dp_refine_sample,
    'step4_dp_board_verify': _dp_board_verify_sample,
}
