"""Shared Question & Conclusion synthesis row builders.

Behavior-preserving extraction (services modularization, Phase 4) of the
byte-identical per-question / per-conclusion ``TemporaryRDFStorage`` row
constructors that ``step4_synthesis_service._run_qc_unified`` and
``entity_graph_service.extract_questions_conclusions`` each inlined verbatim
(the two blocks were SHA-identical modulo indentation).

Scope note: the two OTHER Phase-2 synthesis wrappers deliberately do NOT use
these factories and must not be folded in -- ``synthesis/phase2_extractor`` and
``case_synthesizer/phase2`` persist extra columns
(``entity_uri``/``ontology_target``) and/or emit different ``rdf_json_ld``
keys, so sharing these builders with them would change emitted output. These
factories return an unsaved row; the caller does ``db.session.add(...)`` and
commits, exactly as the inline loops did. Since 2026-07-11 they also stamp
``extraction_model`` (the default tier the Q/C analyzers actually run) so the
commit service emits ``prov:wasAttributedTo`` for Q/C individuals.
"""
from app.models.temporary_rdf_storage import TemporaryRDFStorage


def _qc_model() -> str:
    """The model that actually produced the Q/C analysis.

    QuestionAnalyzer and ConclusionAnalyzer both resolve the DEFAULT tier
    internally (question_analyzer/conclusion_analyzer), so the row attribution
    resolves the same tier here. Without extraction_model the commit service
    silently skips prov:wasAttributedTo for these individuals.
    """
    from model_config import ModelConfig
    return ModelConfig.get_claude_model("default")


def make_question_storage(case_id, session_id, question):
    """Build the ethical_question TemporaryRDFStorage row (not added/committed)."""
    return TemporaryRDFStorage(
        case_id=case_id,
        extraction_session_id=session_id,
        extraction_type='ethical_question',
        storage_type='individual',
        entity_type='questions',
        entity_label=f"Question_{question['question_number']}",
        entity_definition=question['question_text'],
        extraction_model=_qc_model(),
        rdf_json_ld={
            '@type': 'proeth-case:EthicalQuestion',
            'questionNumber': question['question_number'],
            'questionText': question['question_text'],
            'questionType': question.get('question_type', 'unknown'),
            'mentionedEntities': question.get('mentioned_entities', {}),
            'relatedProvisions': question.get('related_provisions', []),
            'extractionReasoning': question.get('extraction_reasoning', ''),
            # The analytical-question prompt asks for and the parser reads
            # source_question (the board question this extends) and
            # ethical_framework, but until 2026-07-08 both were dropped here,
            # forcing the Q&C view onto a number-offset parent heuristic.
            'sourceQuestion': question.get('source_question'),
            'ethicalFramework': question.get('ethical_framework')
        },
        is_selected=True
    )


def make_conclusion_storage(case_id, session_id, conclusion):
    """Build the ethical_conclusion TemporaryRDFStorage row (not added/committed)."""
    return TemporaryRDFStorage(
        case_id=case_id,
        extraction_session_id=session_id,
        extraction_type='ethical_conclusion',
        storage_type='individual',
        entity_type='conclusions',
        entity_label=f"Conclusion_{conclusion['conclusion_number']}",
        entity_definition=conclusion['conclusion_text'],
        extraction_model=_qc_model(),
        rdf_json_ld={
            '@type': 'proeth-case:EthicalConclusion',
            'conclusionNumber': conclusion['conclusion_number'],
            'conclusionText': conclusion['conclusion_text'],
            'conclusionType': conclusion.get('conclusion_type', 'unknown'),
            # BoardConclusionType (violation/no_violation/... detected by
            # ConclusionAnalyzer) and the per-question link confidences from
            # question_conclusion_linker reached this dict but were dropped
            # here until 2026-07-11.
            'boardConclusionType': conclusion.get('board_conclusion_type', ''),
            'linkConfidences': conclusion.get('link_confidences', {}),
            'mentionedEntities': conclusion.get('mentioned_entities', {}),
            'citedProvisions': conclusion.get('cited_provisions', []),
            'answersQuestions': conclusion.get('answers_questions', []),
            'extractionReasoning': conclusion.get('extraction_reasoning', '')
        },
        is_selected=True
    )
