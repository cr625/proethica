"""Shared fixture inputs for the batch-qc Step-4 prompt parity tests.

The golden-capture script (run once against the pre-migration builders) and
tests/extraction/test_step4_prompt_parity_qc.py both build their
prompt inputs from this module, so the goldens and the rendered sidecars
are derived from identical data. Do not edit values here without
re-capturing the goldens.
"""

ALL_ENTITIES = {
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

CODE_PROVISIONS = [
    {'code_provision': 'II.4.a',
     'provision_text': 'Engineers shall disclose all known or potential conflicts of interest that could influence or appear to influence their judgment or the quality of their services.'},
    {'code_provision': 'III.5.a',
     'provision_text': 'Engineers shall not accept financial or other considerations, including free engineering designs, from material or equipment suppliers for specifying their product.'},
]

QUESTIONS_SECTION_TEXT = (
    'Question: Was it ethical for Engineer A to retain an ownership interest '
    'in the equipment vendor while specifying its products for the Client W '
    'facility, and was Engineer A obligated to disclose that interest?'
)

CONCLUSIONS_SECTION_TEXT = (
    'The Board concluded that Engineer A acted unethically by specifying the '
    'vendor equipment without disclosing the ownership interest to Client W. '
    'The Board further concluded that the design itself met the applicable '
    'safety standards.'
)

CASE_FACTS = (
    'Engineer A, retained by Client W to design a water treatment facility, '
    'acquired an ownership stake in an equipment vendor during the project '
    'and specified that vendor\'s filtration units in the final design '
    'without disclosing the interest.'
)

CASE_CONCLUSION = (
    'Engineer A acted unethically in failing to disclose the vendor interest; '
    'the design itself met the applicable safety standards.'
)


def board_questions():
    """EthicalQuestion objects for the question-side analytical prompt."""
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


def board_conclusions():
    """EthicalConclusion objects for the conclusion-side analytical prompt."""
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


def board_question_dicts():
    """Dict-form board questions (the conclusion analyzer receives dicts)."""
    return [
        {'question_number': 1,
         'question_text': 'Was it ethical for Engineer A to retain an ownership interest in the equipment vendor while specifying its products?'},
        {'question_number': 2,
         'question_text': 'Was Engineer A obligated to disclose the vendor interest to Client W?'},
    ]


def analytical_question_dicts():
    """Dict-form analytical questions grouped-by-type input for P4."""
    return [
        {'question_number': 101, 'question_type': 'implicit',
         'question_text': 'Should Engineer A have declined the vendor stake while the project was active?'},
        {'question_number': 201, 'question_type': 'principle_tension',
         'question_text': 'How should Faithful Agency be balanced against Public Safety Paramountcy when the specified equipment is technically adequate?'},
    ]


def linker_questions():
    """Dict-form questions for the Q-to-C linking prompt."""
    return [
        {'question_number': 1,
         'question_text': 'Was it ethical for Engineer A to retain an ownership interest in the equipment vendor while specifying its products?'},
        {'question_number': 2,
         'question_text': 'Was Engineer A obligated to disclose the vendor interest to Client W?'},
    ]


def linker_conclusions():
    """Dict-form conclusions for the Q-to-C linking prompt."""
    return [
        {'conclusion_number': 1,
         'conclusion_text': 'Engineer A acted unethically by specifying the vendor equipment without disclosing the ownership interest.',
         'conclusion_type': 'board_explicit'},
        {'conclusion_number': 2,
         'conclusion_text': 'The design itself met the applicable safety standards.',
         'conclusion_type': 'board_explicit'},
    ]


def q_analytical_variants():
    """The two real per-case call shapes of the question analytical prompt.

    batch1 mirrors the first live call (implicit + principle_tension, full
    context); batch2 mirrors the second (theoretical + counterfactual) and
    additionally exercises the empty-board-questions and empty-conclusion
    template branches.
    """
    return {
        'batch1': dict(
            board_questions=board_questions(),
            all_entities=ALL_ENTITIES,
            code_provisions=CODE_PROVISIONS,
            case_facts=CASE_FACTS,
            case_conclusion=CASE_CONCLUSION,
            categories=['implicit', 'principle_tension'],
        ),
        'batch2': dict(
            board_questions=[],
            all_entities=ALL_ENTITIES,
            code_provisions=CODE_PROVISIONS,
            case_facts=CASE_FACTS,
            case_conclusion='',
            categories=['theoretical', 'counterfactual'],
        ),
    }


def c_analytical_variants():
    """Full (default all-three categories) and reduced (one category, empty
    context) variants of the conclusion analytical prompt. The live path
    calls one category per batch; 'full' exercises the default expansion
    and multi-category joining, 'single' the empty-context branches.
    """
    return {
        'full': dict(
            board_conclusions=board_conclusions(),
            all_entities=ALL_ENTITIES,
            code_provisions=CODE_PROVISIONS,
            board_questions=board_question_dicts(),
            analytical_questions=analytical_question_dicts(),
            case_facts=CASE_FACTS,
            categories=None,
        ),
        'single': dict(
            board_conclusions=[],
            all_entities=ALL_ENTITIES,
            code_provisions=[],
            board_questions=[],
            analytical_questions=[],
            case_facts='',
            categories=['analytical_extension'],
        ),
    }
