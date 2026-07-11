"""Sample variable providers for the batch-qc Step-4 prompt templates (P1-P5).

Each provider returns the full Jinja variables dict for one seeded
step4_* template, built through the live variable builders in the Q&C
analyzers so the samples track the production assembly (category blocks,
QUESTION_TYPES text, provision formatting). Used by the /tools/prompts
Preview/Test tabs, which have no case context for Step-4 prompts.
"""
from __future__ import annotations

from typing import Callable, Dict

_SAMPLE_ENTITIES = {
    'roles': [
        {'label': 'Engineer A',
         'definition': 'Professional engineer retained by Client W to design the water treatment facility.'},
        {'label': 'Client W',
         'definition': 'Municipal water authority that retained Engineer A.'},
    ],
    'states': [
        {'label': 'Undisclosed Financial Interest',
         'definition': 'Engineer A holds an ownership stake in the equipment vendor, unknown to Client W.'},
    ],
    'resources': [],
    'principles': [
        {'label': 'Public Safety Paramountcy',
         'definition': 'Hold paramount the safety, health, and welfare of the public.'},
        {'label': 'Faithful Agency',
         'definition': 'Act for each employer or client as a faithful agent or trustee.'},
    ],
    'obligations': [
        {'label': 'Disclose Conflicts of Interest',
         'definition': 'Disclose all known or potential conflicts of interest that could influence judgment.'},
    ],
    'constraints': [],
    'capabilities': [],
    'actions': [
        {'label': 'Acquiring the Vendor Stake',
         'definition': 'Engineer A acquired an ownership interest in the equipment vendor during the project.'},
    ],
    'events': [],
}

_SAMPLE_PROVISIONS = [
    {'code_provision': 'II.4.a',
     'provision_text': 'Engineers shall disclose all known or potential conflicts of interest that could influence or appear to influence their judgment or the quality of their services.'},
    {'code_provision': 'III.5.a',
     'provision_text': 'Engineers shall not accept financial or other considerations, including free engineering designs, from material or equipment suppliers for specifying their product.'},
]

_SAMPLE_FACTS = (
    'Engineer A, retained by Client W to design a water treatment facility, '
    'acquired an ownership stake in an equipment vendor during the project '
    "and specified that vendor's filtration units in the final design "
    'without disclosing the interest.'
)

_SAMPLE_CONCLUSION = (
    'Engineer A acted unethically in failing to disclose the vendor interest; '
    'the design itself met the applicable safety standards.'
)


def _sample_board_questions():
    from app.services.step4_synthesis.question_analyzer import EthicalQuestion
    return [
        EthicalQuestion(
            question_number=1,
            question_text='Was it ethical for Engineer A to retain an ownership interest in the equipment vendor while specifying its products?',
            question_type='board_explicit',
        ),
        EthicalQuestion(
            question_number=2,
            question_text='Was Engineer A obligated to disclose the vendor interest to Client W?',
            question_type='board_explicit',
        ),
    ]


def _sample_board_conclusions():
    from app.services.step4_synthesis.conclusion_analyzer import EthicalConclusion
    return [
        EthicalConclusion(
            conclusion_number=1,
            conclusion_text='Engineer A acted unethically by specifying the vendor equipment without disclosing the ownership interest.',
            conclusion_type='board_explicit',
            board_conclusion_type='violation',
        ),
        EthicalConclusion(
            conclusion_number=2,
            conclusion_text='The design itself met the applicable safety standards.',
            conclusion_type='board_explicit',
            board_conclusion_type='no_violation',
        ),
    ]


def _q_board_sample() -> Dict[str, object]:
    from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer
    return QuestionAnalyzer()._board_extraction_variables(
        'Question: Was it ethical for Engineer A to retain an ownership '
        'interest in the equipment vendor while specifying its products for '
        'the Client W facility, and was Engineer A obligated to disclose '
        'that interest?',
        _SAMPLE_ENTITIES,
        _SAMPLE_PROVISIONS,
    )


def _q_analytical_sample() -> Dict[str, object]:
    """First live batch shape: implicit + principle_tension."""
    from app.services.step4_synthesis.question_analyzer import QuestionAnalyzer
    return QuestionAnalyzer()._analytical_prompt_variables(
        _sample_board_questions(),
        _SAMPLE_ENTITIES,
        _SAMPLE_PROVISIONS,
        _SAMPLE_FACTS,
        _SAMPLE_CONCLUSION,
        categories=['implicit', 'principle_tension'],
    )


def _c_board_sample() -> Dict[str, object]:
    from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer
    return ConclusionAnalyzer()._board_extraction_variables(
        'The Board concluded that Engineer A acted unethically by specifying '
        'the vendor equipment without disclosing the ownership interest to '
        'Client W. The Board further concluded that the design itself met '
        'the applicable safety standards.',
        _SAMPLE_ENTITIES,
        _SAMPLE_PROVISIONS,
    )


def _c_analytical_sample() -> Dict[str, object]:
    """Live batch shape: one category per call."""
    from app.services.step4_synthesis.conclusion_analyzer import ConclusionAnalyzer
    analytical_questions = [
        {'question_number': 101, 'question_type': 'implicit',
         'question_text': 'Should Engineer A have declined the vendor stake while the project was active?'},
        {'question_number': 201, 'question_type': 'principle_tension',
         'question_text': 'How should Faithful Agency be balanced against Public Safety Paramountcy when the specified equipment is technically adequate?'},
    ]
    return ConclusionAnalyzer()._analytical_prompt_variables(
        _sample_board_conclusions(),
        _SAMPLE_ENTITIES,
        _SAMPLE_PROVISIONS,
        [{'question_number': q.question_number, 'question_text': q.question_text}
         for q in _sample_board_questions()],
        analytical_questions,
        _SAMPLE_FACTS,
        categories=['analytical_extension'],
    )


def _qc_link_sample() -> Dict[str, object]:
    from app.services.step4_synthesis.question_conclusion_linker import QuestionConclusionLinker
    questions = [
        {'question_number': q.question_number, 'question_text': q.question_text}
        for q in _sample_board_questions()
    ]
    conclusions = [
        {'conclusion_number': c.conclusion_number,
         'conclusion_text': c.conclusion_text,
         'conclusion_type': c.conclusion_type}
        for c in _sample_board_conclusions()
    ]
    return QuestionConclusionLinker()._linking_prompt_variables(questions, conclusions)


PROVIDERS: Dict[str, Callable[[], Dict[str, object]]] = {
    'step4_q_board': _q_board_sample,
    'step4_q_analytical': _q_analytical_sample,
    'step4_c_board': _c_board_sample,
    'step4_c_analytical': _c_analytical_sample,
    'step4_qc_link': _qc_link_sample,
}
