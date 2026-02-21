"""
Phase 2 Extractor

Unified extraction for Phase 2 (Analytical Extraction):
- Part A: Code Provisions
- Part B: Ethical Questions & Conclusions
- Part C: Transformation Classification
- Part D: Rich Analysis (Causal Links, Question Emergence, Resolution Patterns)

Based on the working individual SSE endpoints in step4_*.py files.
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional, Tuple

from app import db
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from sqlalchemy import text

from models import ModelConfig
from .base import SynthesisEvent, SynthesisResult, BaseSynthesizer

# Import extraction services
from app.services.nspe_references_parser import NSPEReferencesParser
from app.services.universal_provision_detector import UniversalProvisionDetector
from app.services.provision_grouper import ProvisionGrouper
from app.services.provision_group_validator import ProvisionGroupValidator
from app.services.code_provision_linker import CodeProvisionLinker
from app.services.question_analyzer import QuestionAnalyzer
from app.services.conclusion_analyzer import ConclusionAnalyzer
from app.services.question_conclusion_linker import QuestionConclusionLinker
from app.services.case_analysis.transformation_classifier import TransformationClassifier
from app.services.entity_grounding_service import EntityGroundingService
# Rich analysis is handled by CaseSynthesizer._run_rich_analysis()

logger = logging.getLogger(__name__)


@dataclass
class Phase2Result(SynthesisResult):
    """Result of Phase 2 extraction."""
    provisions: List[Dict] = field(default_factory=list)
    questions: List[Dict] = field(default_factory=list)
    conclusions: List[Dict] = field(default_factory=list)
    transformation_type: Optional[str] = None
    transformation_confidence: float = 0.0
    causal_links: List[Dict] = field(default_factory=list)
    question_emergence: List[Dict] = field(default_factory=list)
    resolution_patterns: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update({
            'provisions_count': len(self.provisions),
            'questions_count': len(self.questions),
            'conclusions_count': len(self.conclusions),
            'transformation_type': self.transformation_type,
            'transformation_confidence': self.transformation_confidence,
            'causal_links_count': len(self.causal_links),
            'question_emergence_count': len(self.question_emergence),
            'resolution_patterns_count': len(self.resolution_patterns)
        })
        return base


class Phase2Extractor(BaseSynthesizer):
    """
    Extracts Phase 2 analytical data from a case.

    Usage:
        extractor = Phase2Extractor(case_id, llm_client)

        # Streaming (for SSE):
        for event in extractor.extract_streaming():
            yield event.to_dict()

        # Non-streaming:
        result = extractor.extract()
    """

    def __init__(self, case_id: int, llm_client=None):
        super().__init__(case_id, llm_client)
        self.llm_client = llm_client or get_llm_client()
        self.session_id = str(uuid.uuid4())
        self._all_entities = None
        self._case = None
        self._sections = None

    def _load_prerequisites(self):
        """Load case and entities before extraction."""
        self._case = Document.query.get_or_404(self.case_id)
        self._sections = self._case.doc_metadata.get('sections_dual', {}) if self._case.doc_metadata else {}
        self._all_entities = self._get_all_case_entities()

    def _get_all_case_entities(self) -> Dict[str, List]:
        """Get all extracted entities for the case."""
        entity_types = {
            'roles': 'roles',
            'states': 'states',
            'resources': 'resources',
            'principles': 'principles',
            'obligations': 'obligations',
            'constraints': 'constraints',
            'capabilities': 'capabilities',
            'actions': 'actions_events',
            'events': 'temporal_dynamics_enhanced',
        }

        all_entities = {}
        for key, extraction_type in entity_types.items():
            entities = TemporaryRDFStorage.query.filter_by(
                case_id=self.case_id,
                extraction_type=extraction_type
            ).all()
            all_entities[key] = entities

        return all_entities

    def _format_entities_for_llm(self, entities: List) -> List[Dict]:
        """Format entities for LLM prompts."""
        return [
            {
                'label': e.entity_label,
                'definition': e.entity_definition or '',
                'uri': e.entity_uri or f"case-{self.case_id}#{e.entity_label}",
                'type': e.entity_type
            }
            for e in entities
        ]

    def _get_section_text(self, section_key: str) -> str:
        """Get text from a case section."""
        data = self._sections.get(section_key, {})
        if isinstance(data, dict):
            return data.get('text', '')
        return str(data) if data else ''

    def _get_section_html(self, section_key: str) -> str:
        """Get HTML from a case section."""
        data = self._sections.get(section_key, {})
        if isinstance(data, dict):
            return data.get('html', '')
        return ''

    def extract_streaming(self) -> Generator[SynthesisEvent, None, None]:
        """Execute Phase 2 extraction with streaming progress events."""
        try:
            # Load prerequisites
            yield self._emit('START', 0, ['Starting Phase 2 Analytical Extraction...'])
            self._load_prerequisites()

            self._result = Phase2Result(
                case_id=self.case_id,
                extraction_session_id=self.session_id
            )

            entity_count = sum(len(v) for v in self._all_entities.values())
            yield self._emit('LOADED', 2, [f'Loaded case with {entity_count} entities from Passes 1-3'])

            # Part A: Provisions
            yield from self._extract_provisions()

            # Part B: Questions & Conclusions
            yield from self._extract_questions_conclusions()

            # Part C: Transformation Classification
            yield from self._classify_transformation()

            # Part D: Rich Analysis
            yield from self._run_rich_analysis()

            # Store all results
            yield self._emit('STORING', 95, ['Storing Phase 2 results to database...'])
            self._store_results()

            yield self._emit('COMPLETE', 100, [
                'Phase 2 Analytical Extraction Complete!',
                f'Provisions: {len(self._result.provisions)}',
                f'Questions: {len(self._result.questions)}',
                f'Conclusions: {len(self._result.conclusions)}',
                f'Transformation: {self._result.transformation_type or "unclassified"}'
            ], result=self._result.to_dict())

        except Exception as e:
            logger.error(f"Phase 2 extraction failed: {e}")
            import traceback
            traceback.print_exc()
            yield self._emit('ERROR', 100, [f'Error: {str(e)}'], error=True)

    def _extract_provisions(self) -> Generator[SynthesisEvent, None, None]:
        """Part A: Extract and validate code provisions."""
        yield self._emit('PART_A_START', 5, ['Part A: Extracting Code Provisions...'])

        # Find references section
        references_html = None
        for section_key in self._sections:
            if 'reference' in section_key.lower():
                references_html = self._get_section_html(section_key)
                break

        if not references_html:
            yield self._emit('PART_A_WARNING', 10, ['No references section found - skipping provisions'])
            return

        # Parse NSPE provisions
        parser = NSPEReferencesParser()
        provisions = parser.parse_references_html(references_html)
        yield self._emit('PART_A_PARSED', 10, [f'Parsed {len(provisions)} NSPE code provisions from references'])

        if not provisions:
            return

        # Get case sections for provision detection
        case_sections = {}
        for section_key in ['facts', 'discussion', 'question', 'conclusion']:
            case_sections[section_key] = self._get_section_text(section_key)

        # Detect provision mentions in case text
        detector = UniversalProvisionDetector()
        all_mentions = detector.detect_all_provisions(case_sections)
        yield self._emit('PART_A_MENTIONS', 15, [f'Detected {len(all_mentions)} provision mentions in case text'])

        # Group mentions by provision
        grouper = ProvisionGrouper()
        grouped_mentions = grouper.group_mentions_by_provision(all_mentions, provisions)

        # Validate each provision's excerpts with LLM
        validator = ProvisionGroupValidator(self.llm_client)

        for i, provision in enumerate(provisions):
            code = provision['code_provision']
            mentions = grouped_mentions.get(code, [])

            if mentions:
                validated = validator.validate_group(code, provision['provision_text'], mentions)
                provision['relevant_excerpts'] = [
                    {
                        'section': v.section,
                        'text': v.excerpt,
                        'matched_citation': v.citation_text,
                        'mention_type': v.content_type,
                        'confidence': v.confidence,
                        'validation_reasoning': v.reasoning
                    }
                    for v in validated
                ]

                # Capture LLM trace
                if hasattr(validator, 'last_validation_prompt') and validator.last_validation_prompt:
                    self._result.llm_traces.append({
                        'stage': 'PROVISION_VALIDATION',
                        'provision': code,
                        'prompt': validator.last_validation_prompt,
                        'response': getattr(validator, 'last_validation_response', ''),
                        'model': ModelConfig.get_claude_model("default"),
                        'timestamp': datetime.utcnow().isoformat()
                    })
            else:
                provision['relevant_excerpts'] = []

            progress = 15 + int((i + 1) / len(provisions) * 10)
            yield self._emit('PART_A_VALIDATING', progress, [f'Validated {i+1}/{len(provisions)} provisions'])

        # Link provisions to extracted entities
        yield self._emit('PART_A_LINKING', 28, ['Linking provisions to extracted entities...'])

        linker = CodeProvisionLinker(self.llm_client)
        linked_provisions = linker.link_provisions_to_entities(
            provisions,
            roles=self._format_entities_for_llm(self._all_entities['roles']),
            states=self._format_entities_for_llm(self._all_entities['states']),
            resources=self._format_entities_for_llm(self._all_entities['resources']),
            principles=self._format_entities_for_llm(self._all_entities['principles']),
            obligations=self._format_entities_for_llm(self._all_entities['obligations']),
            constraints=self._format_entities_for_llm(self._all_entities['constraints']),
            capabilities=self._format_entities_for_llm(self._all_entities['capabilities']),
            actions=self._format_entities_for_llm(self._all_entities['actions']),
            events=self._format_entities_for_llm(self._all_entities['events']),
            case_text_summary=f"Case {self.case_id}: {self._case.title}"
        )

        if hasattr(linker, 'last_linking_prompt') and linker.last_linking_prompt:
            self._result.llm_traces.append({
                'stage': 'PROVISION_LINKING',
                'prompt': linker.last_linking_prompt,
                'response': getattr(linker, 'last_linking_response', ''),
                'model': ModelConfig.get_claude_model("default"),
                'timestamp': datetime.utcnow().isoformat()
            })

        self._result.provisions = linked_provisions
        yield self._emit('PART_A_COMPLETE', 30, [f'Part A complete: {len(linked_provisions)} provisions extracted and linked'])

    def _extract_questions_conclusions(self) -> Generator[SynthesisEvent, None, None]:
        """Part B: Extract ethical questions and conclusions with LLM analysis."""
        yield self._emit('PART_B_START', 32, ['Part B: Extracting Questions & Conclusions...'])

        # Get section texts
        questions_text = self._get_section_text('question')
        conclusions_text = self._get_section_text('conclusion')
        facts_text = self._get_section_text('facts')

        # Format all entities for LLM
        all_entities_formatted = {}
        for key, entities in self._all_entities.items():
            all_entities_formatted[key] = self._format_entities_for_llm(entities)

        # Format provisions for linking
        provisions_for_linking = [
            {
                'code_provision': p.get('code_provision', ''),
                'provision_text': p.get('provision_text', '')
            }
            for p in self._result.provisions
        ]

        # Extract questions with full analysis (uses LLM)
        yield self._emit('PART_B_QUESTIONS', 35, ['Extracting ethical questions with LLM analysis...'])

        question_analyzer = QuestionAnalyzer(self.llm_client)

        # Use the enhanced analysis method that does full LLM extraction
        questions_result = question_analyzer.extract_questions_with_analysis(
            questions_text=questions_text,
            all_entities=all_entities_formatted,
            code_provisions=provisions_for_linking,
            case_facts=facts_text,
            case_conclusion=conclusions_text
        )

        stage1_source = questions_result.get('stage1_source', 'unknown')

        # Capture LLM trace
        if hasattr(question_analyzer, 'last_prompt') and question_analyzer.last_prompt:
            self._result.llm_traces.append({
                'stage': 'QUESTION_EXTRACTION',
                'prompt': question_analyzer.last_prompt,
                'response': getattr(question_analyzer, 'last_response', ''),
                'model': ModelConfig.get_claude_model("default"),
                'timestamp': datetime.utcnow().isoformat()
            })

        # Flatten ALL question types into single list (matching working SSE endpoint)
        questions = []
        for q_type in ['board_explicit', 'implicit', 'principle_tension', 'theoretical', 'counterfactual']:
            for q in questions_result.get(q_type, []):
                # Use the analyzer's conversion method if available
                q_dict = question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                # Add URI for RDF storage
                q_dict['uri'] = f"case-{self.case_id}#Q{q_dict.get('question_number', 0)}"
                q_dict['label'] = f"Question_{q_dict.get('question_number', 0)}"
                questions.append(q_dict)

        board_count = len(questions_result.get('board_explicit', []))
        analytical_count = len(questions) - board_count
        source_note = "(from import)" if stage1_source == 'imported' else "(LLM extracted)"
        yield self._emit('PART_B_QUESTIONS_DONE', 45, [
            f'Extracted {board_count} Board + {analytical_count} analytical = {len(questions)} questions {source_note}'
        ])

        # Prepare board and analytical questions for conclusion extraction
        board_questions = [question_analyzer._question_to_dict(q) if hasattr(q, 'question_number') else q
                          for q in questions_result.get('board_explicit', [])]
        analytical_questions = [q for q in questions if q.get('question_type') != 'board_explicit']

        # Extract conclusions with full analysis (matching working SSE endpoint)
        yield self._emit('PART_B_CONCLUSIONS', 48, ['Extracting Board conclusions + generating analytical conclusions...'])

        conclusion_analyzer = ConclusionAnalyzer(self.llm_client)
        conclusions_result = conclusion_analyzer.extract_conclusions_with_analysis(
            conclusions_text=conclusions_text,
            all_entities=all_entities_formatted,
            code_provisions=provisions_for_linking,
            board_questions=board_questions,
            analytical_questions=analytical_questions,
            case_facts=facts_text
        )

        # Capture LLM trace
        if hasattr(conclusion_analyzer, 'last_prompt') and conclusion_analyzer.last_prompt:
            self._result.llm_traces.append({
                'stage': 'CONCLUSION_EXTRACTION',
                'prompt': conclusion_analyzer.last_prompt,
                'response': getattr(conclusion_analyzer, 'last_response', ''),
                'model': ModelConfig.get_claude_model("default"),
                'timestamp': datetime.utcnow().isoformat()
            })

        # Flatten ALL conclusion types into single list (matching working SSE endpoint)
        conclusions = []
        for c_type in ['board_explicit', 'analytical_extension', 'question_response', 'principle_synthesis']:
            for c in conclusions_result.get(c_type, []):
                # Use the analyzer's conversion method if available
                c_dict = conclusion_analyzer._conclusion_to_dict(c) if hasattr(c, 'conclusion_number') else c
                # Add URI for RDF storage
                c_dict['uri'] = f"case-{self.case_id}#C{c_dict.get('conclusion_number', 0)}"
                c_dict['label'] = f"Conclusion_{c_dict.get('conclusion_number', 0)}"
                conclusions.append(c_dict)

        board_c_count = len(conclusions_result.get('board_explicit', []))
        analytical_c_count = len(conclusions) - board_c_count
        yield self._emit('PART_B_CONCLUSIONS_DONE', 55, [
            f'Extracted {board_c_count} Board + {analytical_c_count} analytical = {len(conclusions)} conclusions'
        ])

        # Link questions to conclusions
        yield self._emit('PART_B_LINKING', 58, ['Linking questions to conclusions...'])

        linker = QuestionConclusionLinker(self.llm_client)
        qc_links = linker.link_questions_to_conclusions(questions, conclusions)

        # Apply links to conclusions using the linker's method (handles dataclass objects)
        conclusions = linker.apply_links_to_conclusions(conclusions, qc_links)

        if hasattr(linker, 'last_prompt') and linker.last_prompt:
            self._result.llm_traces.append({
                'stage': 'QC_LINKING',
                'prompt': linker.last_prompt,
                'response': getattr(linker, 'last_response', ''),
                'model': ModelConfig.get_claude_model("default"),
                'timestamp': datetime.utcnow().isoformat()
            })

        self._result.questions = questions
        self._result.conclusions = conclusions

        yield self._emit('PART_B_COMPLETE', 60, [
            f'Part B complete: {len(questions)} questions, {len(conclusions)} conclusions',
            f'Q->C links established: {len(qc_links)}'
        ])

    def _classify_transformation(self) -> Generator[SynthesisEvent, None, None]:
        """Part C: Classify transformation type."""
        yield self._emit('PART_C_START', 62, ['Part C: Classifying Transformation Type...'])

        try:
            classifier = TransformationClassifier(self.llm_client)

            # Get facts for context
            facts_text = self._get_section_text('facts')

            result = classifier.classify(
                case_id=self.case_id,
                questions=self._result.questions,
                conclusions=self._result.conclusions,
                use_llm=True,
                case_title=self._case.title,
                case_facts=facts_text
            )

            self._result.transformation_type = result.transformation_type
            self._result.transformation_confidence = result.confidence

            # Store transformation type
            self._store_transformation(result)

            # Capture LLM trace
            if hasattr(classifier, 'last_prompt') and classifier.last_prompt:
                self._result.llm_traces.append({
                    'stage': 'TRANSFORMATION_CLASSIFICATION',
                    'prompt': classifier.last_prompt,
                    'response': getattr(classifier, 'last_response', ''),
                    'model': ModelConfig.get_claude_model("default"),
                    'timestamp': datetime.utcnow().isoformat()
                })

                # Save ExtractionPrompt for UI display (must match get_saved_step4_prompt lookup)
                try:
                    transformation_prompt = ExtractionPrompt(
                        case_id=self.case_id,
                        concept_type='transformation_classification',
                        step_number=4,
                        section_type='synthesis',
                        prompt_text=classifier.last_prompt,
                        llm_model=ModelConfig.get_claude_model("default"),
                        extraction_session_id=self.session_id,
                        raw_response=getattr(classifier, 'last_response', ''),
                        results_summary={'transformation_type': result.transformation_type, 'confidence': result.confidence}
                    )
                    db.session.add(transformation_prompt)
                    db.session.commit()
                except Exception as e:
                    logger.warning(f"Could not save transformation prompt: {e}")

            yield self._emit('PART_C_COMPLETE', 68, [
                f'Part C complete: Transformation type = {result.transformation_type}',
                f'Confidence: {result.confidence:.2f}'
            ], result={'transformation_type': result.transformation_type})

        except Exception as e:
            logger.warning(f"Transformation classification failed: {e}")
            yield self._emit('PART_C_WARNING', 68, [f'Transformation classification failed: {e}'])

    def _run_rich_analysis(self) -> Generator[SynthesisEvent, None, None]:
        """Part D: Run rich analysis (causal links, question emergence, resolution patterns)."""
        yield self._emit('PART_D_START', 70, ['Part D: Running Rich Analysis...'])

        try:
            # Use CaseSynthesizer for rich analysis (it has the actual implementation)
            from app.services.case_synthesizer import CaseSynthesizer

            synthesizer = CaseSynthesizer(llm_client=self.llm_client)

            yield self._emit('PART_D_CAUSAL', 72, ['Analyzing causal-normative links...'])

            # Build entity foundation for rich analysis
            foundation = synthesizer._build_entity_foundation(self.case_id)

            yield self._emit('PART_D_QUESTIONS', 78, ['Analyzing question emergence...'])

            yield self._emit('PART_D_RESOLUTION', 84, ['Analyzing resolution patterns...'])

            # Run rich analysis via CaseSynthesizer
            causal_links, question_emergence, resolution_patterns, llm_traces = synthesizer._run_rich_analysis(
                self.case_id,
                foundation,
                self._result.provisions,
                self._result.questions,
                self._result.conclusions
            )

            # Convert dataclass objects to dicts for storage
            self._result.causal_links = [cl.to_dict() if hasattr(cl, 'to_dict') else vars(cl) for cl in causal_links]
            self._result.question_emergence = [qe.to_dict() if hasattr(qe, 'to_dict') else vars(qe) for qe in question_emergence]
            self._result.resolution_patterns = [rp.to_dict() if hasattr(rp, 'to_dict') else vars(rp) for rp in resolution_patterns]

            # Capture LLM traces
            self._result.llm_traces.extend([t.to_dict() if hasattr(t, 'to_dict') else vars(t) for t in llm_traces])

            # Save ExtractionPrompt for UI display (must match get_saved_step4_prompt lookup)
            try:
                # Combine all LLM traces for the prompt/response
                rich_analysis_prompts = [t.get('prompt', '') for t in self._result.llm_traces if 'CAUSAL' in str(t.get('stage', '')) or 'EMERGENCE' in str(t.get('stage', '')) or 'RESOLUTION' in str(t.get('stage', ''))]
                rich_analysis_responses = [t.get('response', '') for t in self._result.llm_traces if 'CAUSAL' in str(t.get('stage', '')) or 'EMERGENCE' in str(t.get('stage', '')) or 'RESOLUTION' in str(t.get('stage', ''))]

                rich_analysis_prompt = ExtractionPrompt(
                    case_id=self.case_id,
                    concept_type='rich_analysis',
                    step_number=4,
                    section_type='synthesis',
                    prompt_text='\n\n---\n\n'.join(rich_analysis_prompts) if rich_analysis_prompts else 'Rich analysis via CaseSynthesizer',
                    llm_model=ModelConfig.get_claude_model("default"),
                    extraction_session_id=self.session_id,
                    raw_response='\n\n---\n\n'.join(rich_analysis_responses) if rich_analysis_responses else f'Causal links: {len(self._result.causal_links)}, Question emergence: {len(self._result.question_emergence)}, Resolution patterns: {len(self._result.resolution_patterns)}',
                    results_summary={
                        'causal_links_count': len(self._result.causal_links),
                        'question_emergence_count': len(self._result.question_emergence),
                        'resolution_patterns_count': len(self._result.resolution_patterns)
                    }
                )
                db.session.add(rich_analysis_prompt)
                db.session.commit()
            except Exception as e:
                logger.warning(f"Could not save rich_analysis prompt: {e}")

            yield self._emit('PART_D_COMPLETE', 90, [
                f'Part D complete:',
                f'  - {len(self._result.causal_links)} causal-normative links',
                f'  - {len(self._result.question_emergence)} question emergence patterns',
                f'  - {len(self._result.resolution_patterns)} resolution patterns'
            ])

        except Exception as e:
            logger.warning(f"Rich analysis failed: {e}")
            import traceback
            traceback.print_exc()
            yield self._emit('PART_D_WARNING', 90, [f'Rich analysis partial: {e}'])

    def _store_transformation(self, result) -> None:
        """Store transformation classification to database."""
        try:
            existing = db.session.execute(
                text("SELECT id FROM case_precedent_features WHERE case_id = :case_id"),
                {'case_id': self.case_id}
            ).fetchone()

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
                        'case_id': self.case_id,
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
                        'case_id': self.case_id,
                        'type': result.transformation_type,
                        'pattern': pattern
                    }
                )
            db.session.commit()
            logger.info(f"Stored transformation type '{result.transformation_type}' for case {self.case_id}")
        except Exception as e:
            logger.warning(f"Failed to store transformation type: {e}")
            db.session.rollback()

    def _store_results(self) -> None:
        """Store all Phase 2 extraction results to database."""
        # Clear existing Phase 2 data
        for extraction_type in ['code_provision_reference', 'ethical_question', 'ethical_conclusion',
                                'causal_normative_link', 'question_emergence', 'resolution_pattern']:
            TemporaryRDFStorage.query.filter_by(
                case_id=self.case_id,
                extraction_type=extraction_type
            ).delete(synchronize_session=False)

        # Store provisions
        for p in self._result.provisions:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='code_provision_reference',
                storage_type='individual',
                entity_type='resources',
                entity_label=p.get('code_provision', ''),
                entity_uri=f"case-{self.case_id}#{p.get('code_provision', '')}",
                entity_definition=p.get('provision_text', ''),
                rdf_json_ld={
                    '@type': 'proeth-case:CodeProvisionReference',
                    'codeProvision': p.get('code_provision', ''),
                    'provisionText': p.get('provision_text', ''),
                    'relevantExcerpts': p.get('relevant_excerpts', []),
                    'linkedEntities': p.get('linked_entities', [])
                },
                is_selected=True,
                extraction_model=ModelConfig.get_claude_model("default"),
                ontology_target=f'proethica-case-{self.case_id}'
            )
            db.session.add(entity)

        # Store questions (matching working SSE endpoint format)
        for q in self._result.questions:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='ethical_question',
                storage_type='individual',
                entity_type='questions',
                entity_label=f"Question_{q.get('question_number', 0)}",
                entity_uri=q.get('uri', ''),
                entity_definition=q.get('question_text', q.get('text', '')),
                rdf_json_ld={
                    '@type': 'proeth-case:EthicalQuestion',
                    'questionNumber': q.get('question_number', 0),
                    'questionText': q.get('question_text', q.get('text', '')),
                    'questionType': q.get('question_type', 'unknown'),
                    'mentionedEntities': q.get('mentioned_entities', {}),
                    'relatedProvisions': q.get('related_provisions', []),
                    'extractionReasoning': q.get('extraction_reasoning', '')
                },
                is_selected=True,
                extraction_model=ModelConfig.get_claude_model("default"),
                ontology_target=f'proethica-case-{self.case_id}'
            )
            db.session.add(entity)

        # Store conclusions (matching working SSE endpoint format)
        for c in self._result.conclusions:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='ethical_conclusion',
                storage_type='individual',
                entity_type='conclusions',
                entity_label=f"Conclusion_{c.get('conclusion_number', 0)}",
                entity_uri=c.get('uri', ''),
                entity_definition=c.get('conclusion_text', c.get('text', '')),
                rdf_json_ld={
                    '@type': 'proeth-case:EthicalConclusion',
                    'conclusionNumber': c.get('conclusion_number', 0),
                    'conclusionText': c.get('conclusion_text', c.get('text', '')),
                    'conclusionType': c.get('conclusion_type', 'unknown'),
                    'mentionedEntities': c.get('mentioned_entities', {}),
                    'citedProvisions': c.get('cited_provisions', []),
                    'answersQuestions': c.get('answers_questions', []),
                    'extractionReasoning': c.get('extraction_reasoning', '')
                },
                is_selected=True,
                extraction_model=ModelConfig.get_claude_model("default"),
                ontology_target=f'proethica-case-{self.case_id}'
            )
            db.session.add(entity)

        # Store rich analysis results
        for link in self._result.causal_links:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='causal_normative_link',
                storage_type='individual',
                entity_type='analysis',
                entity_label=f"CausalLink_{link.get('id', '')}",
                entity_definition=str(link),
                rdf_json_ld=link,
                is_selected=True
            )
            db.session.add(entity)

        for qe in self._result.question_emergence:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='question_emergence',
                storage_type='individual',
                entity_type='analysis',
                entity_label=f"QuestionEmergence_{qe.get('question_uri', '')}",
                entity_definition=str(qe),
                rdf_json_ld=qe,
                is_selected=True
            )
            db.session.add(entity)

        for rp in self._result.resolution_patterns:
            entity = TemporaryRDFStorage(
                case_id=self.case_id,
                extraction_session_id=self.session_id,
                extraction_type='resolution_pattern',
                storage_type='individual',
                entity_type='analysis',
                entity_label=f"Resolution_{rp.get('conclusion_uri', '')}",
                entity_definition=str(rp),
                rdf_json_ld=rp,
                is_selected=True
            )
            db.session.add(entity)

        # Save extraction prompt for provenance
        prompt_summary = {
            'provisions_count': len(self._result.provisions),
            'questions_count': len(self._result.questions),
            'conclusions_count': len(self._result.conclusions),
            'transformation_type': self._result.transformation_type,
            'causal_links_count': len(self._result.causal_links),
            'question_emergence_count': len(self._result.question_emergence),
            'resolution_patterns_count': len(self._result.resolution_patterns),
            'llm_traces_count': len(self._result.llm_traces)
        }

        extraction_prompt = ExtractionPrompt(
            case_id=self.case_id,
            concept_type='phase2_extraction',
            step_number=4,
            section_type='synthesis',
            prompt_text='Phase 2 Analytical Extraction',
            llm_model=ModelConfig.get_claude_model("default"),
            extraction_session_id=self.session_id,
            raw_response=str(prompt_summary),
            results_summary=prompt_summary,
            is_active=True
        )
        db.session.add(extraction_prompt)
        db.session.commit()

        logger.info(f"Stored Phase 2 results for case {self.case_id}")


# Convenience functions
def extract_phase2(case_id: int, llm_client=None) -> Phase2Result:
    """Non-streaming Phase 2 extraction."""
    extractor = Phase2Extractor(case_id, llm_client)
    return extractor.extract()


def extract_phase2_streaming(case_id: int, llm_client=None) -> Generator[SynthesisEvent, None, None]:
    """Streaming Phase 2 extraction."""
    extractor = Phase2Extractor(case_id, llm_client)
    return extractor.extract_streaming()
