"""
Case Synthesizer (Step 4) -- Phase-2 transformation + normative extraction.

The transformation-type + Phase-2 (P/O/Cs/Ca) extraction/storage methods, split out of
case_synthesizer.py as a mixin. Mixed into CaseSynthesizer; `self.` resolution preserved by MRO.
Import header mirrors synthesizer.py so relocated bodies resolve every name.
"""

import json
import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from app.domains import DomainConfig, get_domain_config
from model_config import ModelConfig

# Data models (extracted to separate module for modularity)
from app.services.case_synthesis_models import (  # noqa: F401 -- re-exported for backward compatibility
    EntitySummary, EntityFoundation, TimelineEvent, ScenarioSeeds,
    CaseNarrative, LLMTrace, CausalNormativeLink, QuestionEmergenceAnalysis,
    ResolutionPatternAnalysis, TransformationAnalysis, CaseSynthesisModel,
    SynthesisResult
)

# E1-E3 Services
from app.services.entity_analysis import (
    ObligationCoverageAnalyzer,
    ActionOptionMapper,
    DecisionPointComposer,
    get_obligation_coverage,
    get_action_option_map,
    compose_decision_points,
    ComposedDecisionPoints,
    EntityGroundedDecisionPoint
)

# F1-F3 Services
from app.services.entity_analysis import (
    PrincipleProvisionAligner,
    ArgumentGenerator,
    ArgumentValidator,
    get_principle_provision_alignment,
    generate_arguments,
    validate_arguments,
    GeneratedArguments,
    ValidatedArguments
)

# Phase 4 Narrative Pipeline
from app.services.narrative import construct_phase4_narrative

# Phase 3: Decision Point Synthesis
from app.services.decision_point_synthesizer import (
    DecisionPointSynthesizer,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    synthesize_decision_points
)

from .narrative import NarrativeConstructionMixin

logger = logging.getLogger(__name__)


class Phase2ExtractionMixin:
    """Transformation classification + Phase-2 extraction/storage. Mixed into CaseSynthesizer."""

    def _get_transformation_type(self, case_id: int) -> str:
        """Get transformation type from case_precedent_features."""
        try:
            result = db.session.execute(
                text("SELECT transformation_type FROM case_precedent_features WHERE case_id = :case_id"),
                {'case_id': case_id}
            ).fetchone()
            return result[0] if result else ''
        except Exception:
            return ''

    def _run_phase2_extraction(
        self,
        case_id: int,
        case: Document,
        foundation: EntityFoundation
    ) -> Tuple[List[Dict], List[Dict], List[Dict], List[LLMTrace]]:
        """
        Run Phase 2 analytical extraction - the full analytical chain.

        This preserves the complete analysis from the streaming synthesis:
        - Part A: Code provisions with LLM validation and entity linking
        - Part B: Questions and conclusions with entity mentions
        - Part C: Entity graph cross-referencing
        - Part D: Transformation classification with LLM reasoning

        Returns:
            Tuple of (provisions, questions, conclusions, llm_traces)
        """
        from app.services.provision.nspe_references_parser import NSPEReferencesParser
        from app.services.provision.universal_provision_detector import UniversalProvisionDetector
        from app.services.provision.provision_grouper import ProvisionGrouper
        from app.services.provision.provision_group_validator import ProvisionGroupValidator
        from app.services.provision.code_provision_linker import CodeProvisionLinker
        from app.services.question_analyzer import QuestionAnalyzer
        from app.services.conclusion_analyzer import ConclusionAnalyzer
        from app.services.question_conclusion_linker import QuestionConclusionLinker

        llm_traces = []
        session_id = f"phase2_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Get case sections
        sections_dual = case.doc_metadata.get('sections_dual', {}) if case.doc_metadata else {}

        # Build case sections for analysis
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            if section_key in sections_dual:
                section_data = sections_dual[section_key]
                case_sections[section_key] = section_data.get('text', '') if isinstance(section_data, dict) else str(section_data)

        # Format entities for analyzers (with URIs for linking)
        all_entities_formatted = {
            'roles': [{'label': r.label, 'definition': r.definition, 'uri': r.uri} for r in foundation.roles],
            'states': [{'label': s.label, 'definition': s.definition, 'uri': s.uri} for s in foundation.states],
            'resources': [{'label': r.label, 'definition': r.definition, 'uri': r.uri} for r in foundation.resources],
            'principles': [{'label': p.label, 'definition': p.definition, 'uri': p.uri} for p in foundation.principles],
            'obligations': [{'label': o.label, 'definition': o.definition, 'uri': o.uri} for o in foundation.obligations],
            'constraints': [{'label': c.label, 'definition': c.definition, 'uri': c.uri} for c in foundation.constraints],
            'capabilities': [{'label': c.label, 'definition': c.definition, 'uri': c.uri} for c in foundation.capabilities],
            'actions': [{'label': a.label, 'definition': a.definition, 'uri': a.uri} for a in foundation.actions],
            'events': [{'label': e.label, 'definition': e.definition, 'uri': e.uri} for e in foundation.events],
        }

        # =================================================================
        # PART A: Code Provisions with LLM Validation and Entity Linking
        # =================================================================
        logger.info("Phase 2A: Extracting and validating code provisions")
        provisions = []
        provision_dicts = []

        # Find references section
        references_html = None
        for section_key, section_content in sections_dual.items():
            if 'reference' in section_key.lower():
                references_html = section_content.get('html', '') if isinstance(section_content, dict) else ''
                break

        if references_html:
            # Step 1: Parse provisions from references
            parser = NSPEReferencesParser()
            provisions = parser.parse_references_html(references_html)
            logger.info(f"Phase 2A: Parsed {len(provisions)} NSPE code provisions")

            if case_sections:
                # Step 2: Detect provision mentions in case text
                detector = UniversalProvisionDetector()
                all_mentions = detector.detect_all_provisions(case_sections)
                logger.info(f"Phase 2A: Detected {len(all_mentions)} provision mentions")

                # Step 3: Group mentions by provision
                grouper = ProvisionGrouper()
                grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)

                # Step 4: LLM Validation of each provision's mentions
                validator = ProvisionGroupValidator(self.llm_client)
                for i, provision in enumerate(provisions):
                    code = provision.get('code_provision', '')
                    mentions = grouped_mentions.get(code, [])

                    if mentions:
                        try:
                            validated = validator.validate_group(code, provision.get('provision_text', ''), mentions)
                            provision['relevant_excerpts'] = [
                                {
                                    'section': v.section,
                                    'text': v.excerpt,
                                    'matched_citation': v.citation_text if hasattr(v, 'citation_text') else '',
                                    'mention_type': v.content_type if hasattr(v, 'content_type') else 'mention',
                                    'confidence': v.confidence if hasattr(v, 'confidence') else 0.8,
                                    'validation_reasoning': v.reasoning if hasattr(v, 'reasoning') else ''
                                }
                                for v in validated
                            ]

                            # Capture LLM trace for validation
                            if hasattr(validator, 'last_validation_prompt') and validator.last_validation_prompt:
                                llm_traces.append(LLMTrace(
                                    phase=2,
                                    phase_name="Analytical Extraction",
                                    stage=f"Provision Validation ({code})",
                                    prompt=validator.last_validation_prompt,
                                    response=getattr(validator, 'last_validation_response', ''),
                                    model=ModelConfig.get_claude_model("default")
                                ))
                        except Exception as e:
                            logger.warning(f"Validation failed for {code}: {e}")
                            provision['relevant_excerpts'] = []
                    else:
                        provision['relevant_excerpts'] = []

                logger.info(f"Phase 2A: Validated {len(provisions)} provisions")

                # Step 5: LLM Entity Linking - connect provisions to extracted entities
                try:
                    linker = CodeProvisionLinker(self.llm_client)
                    provisions = linker.link_provisions_to_entities(
                        provisions,
                        roles=[e for e in all_entities_formatted['roles']],
                        states=[e for e in all_entities_formatted['states']],
                        resources=[e for e in all_entities_formatted['resources']],
                        principles=[e for e in all_entities_formatted['principles']],
                        obligations=[e for e in all_entities_formatted['obligations']],
                        constraints=[e for e in all_entities_formatted['constraints']],
                        capabilities=[e for e in all_entities_formatted['capabilities']],
                        actions=[e for e in all_entities_formatted['actions']],
                        events=[e for e in all_entities_formatted['events']],
                        case_text_summary=f"Case {case_id}: {case.title}"
                    )

                    # Capture LLM trace for entity linking
                    if hasattr(linker, 'last_linking_prompt') and linker.last_linking_prompt:
                        llm_traces.append(LLMTrace(
                            phase=2,
                            phase_name="Analytical Extraction",
                            stage="Provision Entity Linking",
                            prompt=linker.last_linking_prompt,
                            response=getattr(linker, 'last_linking_response', ''),
                            model=ModelConfig.get_claude_model("default")
                        ))

                    logger.info(f"Phase 2A: Linked provisions to entities")
                except Exception as e:
                    logger.warning(f"Entity linking failed: {e}")

        # Convert provisions to stored format (preserving linked entities)
        for p in provisions:
            # Normalize the code into a URI/label fragment. Modern codes have no
            # spaces (no-op); historical codes ("Canon 15", "Rule 13") carry a
            # space that must become an underscore so the fragment stays a valid
            # identifier (Provision_Canon_15).
            code_frag = p.get('code_provision', '').replace('.', '_').replace(' ', '_')
            provision_dicts.append({
                'uri': f"case-{case_id}#Provision_{code_frag}",
                'label': f"NSPE_{code_frag}",
                'definition': p.get('provision_text', ''),
                'code': p.get('code_provision', ''),
                'relevant_excerpts': p.get('relevant_excerpts', []),
                'linked_entities': p.get('linked_entities', []),
                'applies_to': p.get('applies_to', [])
            })

        # =================================================================
        # PART B: Questions & Conclusions with Entity Awareness
        # =================================================================
        logger.info("Phase 2B: Extracting questions and conclusions")

        questions_text = ""
        if 'question' in sections_dual:
            q_data = sections_dual['question']
            questions_text = q_data.get('text', '') if isinstance(q_data, dict) else str(q_data)

        conclusions_text = ""
        if 'conclusion' in sections_dual:
            c_data = sections_dual['conclusion']
            conclusions_text = c_data.get('text', '') if isinstance(c_data, dict) else str(c_data)

        questions = []
        conclusions = []

        # Extract questions with entity awareness
        if questions_text:
            try:
                question_analyzer = QuestionAnalyzer(self.llm_client)
                q_results = question_analyzer.extract_questions(questions_text, all_entities_formatted, provisions)

                for i, q in enumerate(q_results):
                    # q is a dict from _question_to_dict, not an EthicalQuestion object
                    questions.append({
                        'uri': f"case-{case_id}#Q{i+1}",
                        'label': f"Question_{i+1}",
                        'text': q.get('question_text', str(q)) if isinstance(q, dict) else getattr(q, 'question_text', str(q)),
                        'mentioned_entities': q.get('mentioned_entities', []) if isinstance(q, dict) else getattr(q, 'mentioned_entities', []),
                        'related_provisions': q.get('related_provisions', []) if isinstance(q, dict) else getattr(q, 'related_provisions', [])
                    })

                if hasattr(question_analyzer, 'last_prompt') and question_analyzer.last_prompt:
                    llm_traces.append(LLMTrace(
                        phase=2,
                        phase_name="Analytical Extraction",
                        stage="Question Extraction",
                        prompt=question_analyzer.last_prompt,
                        response=getattr(question_analyzer, 'last_response', ''),
                        model=ModelConfig.get_claude_model("default")
                    ))

                logger.info(f"Phase 2B: Extracted {len(questions)} questions")
            except Exception as e:
                logger.warning(f"Question extraction failed: {e}")

        # Extract conclusions with entity awareness
        if conclusions_text:
            try:
                conclusion_analyzer = ConclusionAnalyzer(self.llm_client)
                c_results = conclusion_analyzer.extract_conclusions(conclusions_text, all_entities_formatted, provisions)

                for i, c in enumerate(c_results):
                    # c is a dict from _conclusion_to_dict, not an EthicalConclusion object
                    conclusions.append({
                        'uri': f"case-{case_id}#C{i+1}",
                        'label': f"Conclusion_{i+1}",
                        'text': c.get('conclusion_text', str(c)) if isinstance(c, dict) else getattr(c, 'conclusion_text', str(c)),
                        'mentioned_entities': c.get('mentioned_entities', []) if isinstance(c, dict) else getattr(c, 'mentioned_entities', []),
                        'cited_provisions': c.get('cited_provisions', []) if isinstance(c, dict) else getattr(c, 'cited_provisions', []),
                        'conclusion_type': c.get('conclusion_type', 'determination') if isinstance(c, dict) else getattr(c, 'conclusion_type', 'determination')
                    })

                if hasattr(conclusion_analyzer, 'last_prompt') and conclusion_analyzer.last_prompt:
                    llm_traces.append(LLMTrace(
                        phase=2,
                        phase_name="Analytical Extraction",
                        stage="Conclusion Extraction",
                        prompt=conclusion_analyzer.last_prompt,
                        response=getattr(conclusion_analyzer, 'last_response', ''),
                        model=ModelConfig.get_claude_model("default")
                    ))

                logger.info(f"Phase 2B: Extracted {len(conclusions)} conclusions")
            except Exception as e:
                logger.warning(f"Conclusion extraction failed: {e}")

        # Link Q->C
        if questions and conclusions:
            try:
                linker = QuestionConclusionLinker(self.llm_client)
                qc_links = linker.link_questions_to_conclusions(questions, conclusions)

                # Apply links to conclusions
                for link in qc_links if qc_links else []:
                    q_idx = link.get('question_index', -1)
                    c_idx = link.get('conclusion_index', -1)
                    if 0 <= c_idx < len(conclusions) and 0 <= q_idx < len(questions):
                        if 'answers_questions' not in conclusions[c_idx]:
                            conclusions[c_idx]['answers_questions'] = []
                        conclusions[c_idx]['answers_questions'].append(questions[q_idx]['uri'])

                if hasattr(linker, 'last_prompt') and linker.last_prompt:
                    llm_traces.append(LLMTrace(
                        phase=2,
                        phase_name="Analytical Extraction",
                        stage="Q&C Linking",
                        prompt=linker.last_prompt,
                        response=getattr(linker, 'last_response', ''),
                        model=ModelConfig.get_claude_model("default")
                    ))

                logger.info(f"Phase 2B: Linked questions to conclusions")
            except Exception as e:
                logger.warning(f"Q&C linking failed: {e}")

        # =================================================================
        # PART D: Transformation Classification
        # =================================================================
        logger.info("Phase 2D: Classifying transformation type")
        transformation_type = ''

        try:
            from app.services.case_analysis import TransformationClassifier

            classifier = TransformationClassifier(self.llm_client)

            # Format for classifier
            questions_for_classifier = [
                {'entity_definition': q.get('text', ''), 'rdf_json_ld': {}}
                for q in questions
            ]
            conclusions_for_classifier = [
                {
                    'entity_definition': c.get('text', ''),
                    'rdf_json_ld': {'conclusionType': c.get('conclusion_type', 'unknown')}
                }
                for c in conclusions
            ]

            transformation_result = classifier.classify(
                case_id=case_id,
                questions=questions_for_classifier,
                conclusions=conclusions_for_classifier,
                resolution_patterns=[],
                use_llm=True,
                case_title=case.title
            )

            transformation_type = transformation_result.transformation_type

            # Capture LLM trace
            if hasattr(classifier, 'last_prompt') and classifier.last_prompt:
                llm_traces.append(LLMTrace(
                    phase=2,
                    phase_name="Analytical Extraction",
                    stage="Transformation Classification",
                    prompt=classifier.last_prompt,
                    response=getattr(classifier, 'last_response', ''),
                    model=ModelConfig.get_claude_model("default")
                ))

            logger.info(f"Phase 2D: Transformation type = {transformation_type} (confidence: {transformation_result.confidence:.0%})")

            # Store transformation type
            self._store_transformation_type(case_id, transformation_result)

        except Exception as e:
            logger.warning(f"Transformation classification failed: {e}")

        # =================================================================
        # Store to database
        # =================================================================
        self._store_phase2_results(case_id, session_id, provision_dicts, questions, conclusions)

        logger.info(f"Phase 2 complete: {len(provision_dicts)} provisions, {len(questions)} Q, {len(conclusions)} C, {len(llm_traces)} LLM traces")
        return provision_dicts, questions, conclusions, llm_traces

    def _store_transformation_type(self, case_id: int, result) -> None:
        """Store transformation classification result."""
        try:
            # Check if record exists
            existing = db.session.execute(
                text("SELECT id FROM case_precedent_features WHERE case_id = :case_id"),
                {'case_id': case_id}
            ).fetchone()

            # Use pattern_description for transformation_pattern column
            pattern = getattr(result, 'pattern_description', '') or getattr(result, 'reasoning', '')

            if existing:
                db.session.execute(
                    text("""
                        UPDATE case_precedent_features
                        SET transformation_type = :type,
                            transformation_pattern = :pattern
                        WHERE case_id = :case_id
                    """),
                    {
                        'case_id': case_id,
                        'type': result.transformation_type,
                        'pattern': pattern
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO case_precedent_features (case_id, transformation_type, transformation_pattern)
                        VALUES (:case_id, :type, :pattern)
                    """),
                    {
                        'case_id': case_id,
                        'type': result.transformation_type,
                        'pattern': pattern
                    }
                )
            db.session.commit()
            logger.info(f"Stored transformation type '{result.transformation_type}' for case {case_id}")
        except Exception as e:
            logger.warning(f"Failed to store transformation type: {e}")
            db.session.rollback()

    def _store_phase2_results(
        self,
        case_id: int,
        session_id: str,
        provisions: List[Dict],
        questions: List[Dict],
        conclusions: List[Dict]
    ):
        """Store Phase 2 extraction results to database with full analytical data."""
        try:
            # Clear existing Phase 2 data
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='code_provision_reference'
            ).delete(synchronize_session=False)
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_question'
            ).delete(synchronize_session=False)
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='ethical_conclusion'
            ).delete(synchronize_session=False)

            # Store provisions with full analytical data
            for p in provisions:
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='code_provision_reference',
                    storage_type='individual',
                    entity_type='resources',
                    entity_label=p['label'],
                    entity_uri=p.get('uri', ''),
                    entity_definition=p.get('definition', ''),
                    rdf_json_ld={
                        '@type': 'proeth-case:CodeProvisionReference',
                        'label': p['label'],
                        'codeProvision': p.get('code', ''),
                        'provisionText': p.get('definition', ''),
                        'relevantExcerpts': p.get('relevant_excerpts', []),
                        'linkedEntities': p.get('linked_entities', []),
                        'appliesTo': p.get('applies_to', []),
                        'providedBy': 'NSPE Board of Ethical Review',
                        'authoritative': True
                    },
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            # Store questions with entity mentions
            for q in questions:
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='ethical_question',
                    storage_type='individual',
                    entity_type='questions',
                    entity_label=q['label'],
                    entity_uri=q.get('uri', ''),
                    entity_definition=q.get('text', ''),
                    rdf_json_ld={
                        '@type': 'proeth-case:EthicalQuestion',
                        'questionText': q.get('text', ''),
                        'mentionedEntities': q.get('mentioned_entities', []),
                        'relatedProvisions': q.get('related_provisions', [])
                    },
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            # Store conclusions with entity mentions and Q linkage
            for c in conclusions:
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='ethical_conclusion',
                    storage_type='individual',
                    entity_type='conclusions',
                    entity_label=c['label'],
                    entity_uri=c.get('uri', ''),
                    entity_definition=c.get('text', ''),
                    rdf_json_ld={
                        '@type': 'proeth-case:EthicalConclusion',
                        'conclusionText': c.get('text', ''),
                        'mentionedEntities': c.get('mentioned_entities', []),
                        'citedProvisions': c.get('cited_provisions', []),
                        'answersQuestions': c.get('answers_questions', []),
                        'conclusionType': c.get('conclusion_type', 'determination')
                    },
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            db.session.commit()
            logger.info(f"Stored Phase 2 results: {len(provisions)} provisions, {len(questions)} Q, {len(conclusions)} C")

        except Exception as e:
            logger.error(f"Failed to store Phase 2 results: {e}")
            db.session.rollback()
