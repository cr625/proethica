"""Golden test for the shared Q&C row builders (services modularization Phase 4).

make_question_storage / make_conclusion_storage were extracted verbatim from the
byte-identical inline loops in step4_synthesis_service and entity_graph_service.
These assertions pin the exact constructed TemporaryRDFStorage shape.

2026-07-11 (provenance mini-batch, deliberate contract change): the factories
now stamp extraction_model with the default tier (the model the Q/C analyzers
actually run) so the commit service emits prov:wasAttributedTo, and the
conclusion payload carries boardConclusionType + linkConfidences, which reached
the conclusion dict but were dropped here. DB/app-context-free: model instances
construct in memory.
"""
from model_config import ModelConfig

from app.services.step4_synthesis.qc_entity_storage import (
    make_question_storage,
    make_conclusion_storage,
)

DEFAULT_MODEL = ModelConfig.get_claude_model("default")


def test_make_question_storage_golden():
    q = {
        'question_number': 2,
        'question_text': 'May the engineer proceed?',
        'question_type': 'board_explicit',
        'mentioned_entities': {'roles': ['Engineer A']},
        'related_provisions': ['II.1.a'],
        'extraction_reasoning': 'stated in the question section',
    }
    row = make_question_storage(42, 'sess-1', q)
    assert row.case_id == 42
    assert row.extraction_session_id == 'sess-1'
    assert row.extraction_type == 'ethical_question'
    assert row.storage_type == 'individual'
    assert row.entity_type == 'questions'
    assert row.entity_label == 'Question_2'
    assert row.entity_definition == 'May the engineer proceed?'
    assert row.is_selected is True
    # The attribution the commit service turns into prov:wasAttributedTo; a
    # NULL here silently suppressed the triple for every Q/C individual.
    assert row.extraction_model == DEFAULT_MODEL
    assert row.rdf_json_ld == {
        '@type': 'proeth-case:EthicalQuestion',
        'questionNumber': 2,
        'questionText': 'May the engineer proceed?',
        'questionType': 'board_explicit',
        'mentionedEntities': {'roles': ['Engineer A']},
        'relatedProvisions': ['II.1.a'],
        'extractionReasoning': 'stated in the question section',
        'sourceQuestion': None,
        'ethicalFramework': None,
    }
    # entity_uri / ontology_target are NOT set (distinguishes this from the
    # phase2_extractor / case_synthesizer variants).
    assert getattr(row, 'entity_uri', None) in (None, '')


def test_make_question_storage_defaults():
    row = make_question_storage(1, 's', {'question_number': 1, 'question_text': 'Q?'})
    assert row.rdf_json_ld['questionType'] == 'unknown'
    assert row.rdf_json_ld['mentionedEntities'] == {}
    assert row.rdf_json_ld['relatedProvisions'] == []
    assert row.rdf_json_ld['extractionReasoning'] == ''


def test_make_conclusion_storage_golden():
    c = {
        'conclusion_number': 3,
        'conclusion_text': 'The engineer must disclose.',
        'conclusion_type': 'board_explicit',
        'board_conclusion_type': 'violation',
        'link_confidences': {'2': 0.9},
        'mentioned_entities': {'obligations': ['Disclosure']},
        'cited_provisions': ['II.1.c'],
        'answers_questions': [2],
        'extraction_reasoning': 'board determination',
    }
    row = make_conclusion_storage(42, 'sess-1', c)
    assert row.case_id == 42
    assert row.extraction_session_id == 'sess-1'
    assert row.extraction_type == 'ethical_conclusion'
    assert row.storage_type == 'individual'
    assert row.entity_type == 'conclusions'
    assert row.entity_label == 'Conclusion_3'
    assert row.entity_definition == 'The engineer must disclose.'
    assert row.is_selected is True
    assert row.extraction_model == DEFAULT_MODEL
    assert row.rdf_json_ld == {
        '@type': 'proeth-case:EthicalConclusion',
        'conclusionNumber': 3,
        'conclusionText': 'The engineer must disclose.',
        'conclusionType': 'board_explicit',
        'boardConclusionType': 'violation',
        'linkConfidences': {'2': 0.9},
        'mentionedEntities': {'obligations': ['Disclosure']},
        'citedProvisions': ['II.1.c'],
        'answersQuestions': [2],
        'extractionReasoning': 'board determination',
    }


def test_make_conclusion_storage_defaults():
    row = make_conclusion_storage(1, 's', {'conclusion_number': 1, 'conclusion_text': 'C.'})
    assert row.rdf_json_ld['conclusionType'] == 'unknown'
    assert row.rdf_json_ld['boardConclusionType'] == ''
    assert row.rdf_json_ld['linkConfidences'] == {}
    assert row.rdf_json_ld['mentionedEntities'] == {}
    assert row.rdf_json_ld['citedProvisions'] == []
    assert row.rdf_json_ld['answersQuestions'] == []
    assert row.rdf_json_ld['extractionReasoning'] == ''
