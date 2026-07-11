"""Sample variable providers for the batch-analysis Step-4 prompt templates.

Used by the /tools/prompts Preview path for case-less rendering of the seeded
step4_provision_validate, step4_provision_link, step4_precedents,
step4_transformation, and step4_obligation_relevance templates. Each provider
returns a full variables dict with realistic values for every variable the
template body references (shape mirrors shared_prompt_samples.py providers;
the orchestrator wires the import).
"""


def _provision_validate_sample():
    return {
        'provision_code': 'II.4.e',
        'provision_text': (
            'Engineers shall not solicit or accept a contract from a governmental '
            'body on which a principal or officer of their organization serves as '
            'a member.'
        ),
        'mentions_text': (
            '\nMENTION 1:\n'
            'Section: discussion\n'
            'Citation: "Code II.4.e"\n'
            'Excerpt: "Engineer A accepted the contract while serving on the planning board."\n'
            '\nMENTION 2:\n'
            'Section: facts\n'
            'Citation: "Section II.4.e"\n'
            'Excerpt: "The RFP cited Section II.4.e of the NSPE Code without further analysis."\n'
        ),
    }


def _provision_link_sample():
    return {
        'provisions_text': (
            '1. **I.1**: Hold paramount the safety, health, and welfare of the public.\n'
            '2. **II.4.e**: Engineers shall not solicit or accept a contract from a '
            'governmental body on which a principal or officer of their organization '
            'serves as a member.\n'
        ),
        'type_label': 'Roles',
        'entities_text': (
            '**Roles:**\n'
            '- Engineer A: A professional engineer serving on the municipal planning board.\n'
            '- City Engineer: The public official responsible for reviewing engineering '
            'submittals on behalf of the municipality.\n'
        ),
        'entity_type': 'role',
        'applicability': 'The provision governs the professional conduct of that role',
        'case_summary': 'Case 9: Engineer serving on a public board whose firm seeks municipal work.',
    }


def _precedents_sample():
    from app.routes.scenario_pipeline.step4.precedents import _treatments_block

    return {
        'case_text': (
            '=== FACTS ===\n'
            'Engineer A cited BER Case 94-8 in support of the delegation.\n\n'
            '=== DISCUSSION ===\n'
            'The Board discussed Cases 65-9 and 73-9 jointly, distinguishing both '
            'on their facts.'
        ),
        'citation_treatments_block': _treatments_block(),
    }


def _transformation_sample():
    try:
        from app.academic_references.frameworks.transformation_classification import (
            get_prompt_context,
        )
        framework_context = get_prompt_context(include_examples=True, include_mapping=False)
    except ImportError:
        framework_context = 'TRANSFORMATION CLASSIFICATION FRAMEWORK (module unavailable)'

    return {
        'framework_context': framework_context,
        'case_title': 'Case 24-02: AI in Engineering Practice',
        'case_facts': (
            'Engineer A used an AI system to produce design documents and sealed '
            'them without a full personal review.'
        ),
        'entities_context': (
            'ROLES: Engineer A, Client\n'
            'OBLIGATIONS: Duty of competent practice\n'
            'KEY ACTIONS: Sealing the drawings\n'
            'CONSTRAINTS: License scope'
        ),
        'questions_text': (
            'Q1: Was it ethical for Engineer A to seal drawings produced by the AI system?\n'
            'Q2: Did Engineer B have a duty to report the practice? [board]'
        ),
        'conclusions_text': 'C1: It was not ethical to seal the drawings without full review. [violation]',
        'patterns_text': '- duty_reassertion: The Board reasserted the personal-review duty over delegation to tools.',
    }


def _obligation_relevance_sample():
    return {
        'obligations_text': (
            '- [1] Duty to public safety: Hold paramount the safety, health, and '
            'welfare of the public in all professional duties.\n'
            '- [2] Duty of confidentiality: Maintain client confidences except where '
            'public safety requires disclosure.'
        ),
        'constraints_text': '- [3] Licensure limit: Practice only within areas of licensed competence.',
        'questions_text': 'Q1: Was disclosure of the conflict required?',
        'conclusions_text': 'C1: Disclosure was required under II.1.a.',
    }


PROVIDERS = {
    'step4_provision_validate': _provision_validate_sample,
    'step4_provision_link': _provision_link_sample,
    'step4_precedents': _precedents_sample,
    'step4_transformation': _transformation_sample,
    'step4_obligation_relevance': _obligation_relevance_sample,
}
