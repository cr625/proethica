"""
Case Synthesizer Service

Unified synthesis pipeline that:
1. Gathers ALL extracted entities from Passes 1-3 (Entity Foundation)
2. Loads analytical extraction from Parts A-D (Provisions, Q&C, Transformation)
3. Synthesizes decision points using E1-E3 + LLM refinement
4. Constructs narrative elements for case explanation and scenario generation

This provides a coherent case model showing how entities flow into
decision points and narrative elements.

Reference: docs-internal/STEP4_REIMAGINED.md
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
from models import ModelConfig

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

logger = logging.getLogger(__name__)

PROETHICA_INT_NS = "http://proethica.org/ontology/intermediate#"
PROETHICA_CASE_NS = "http://proethica.org/ontology/case-{case_id}#"


class CaseSynthesizer:
    """
    Unified case synthesis pipeline.

    Four-phase synthesis:
    1. Entity Foundation - gather all entities from Passes 1-3
    2. Analytical Extraction - load provisions, Q&C, transformation type
    3. Decision Point Synthesis - E1-E3 composition + LLM refinement
    4. Narrative Construction - build timeline and scenario seeds
    """

    def __init__(
        self,
        llm_client=None,
        domain_config: Optional[DomainConfig] = None
    ):
        self._llm_client = llm_client
        self.domain = domain_config or get_domain_config('engineering')
        self.last_prompt = None
        self.last_response = None

    @property
    def llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    # Rich analysis delegation -- actual implementation in rich_analysis.py
    _rich_analyzer = None

    def _get_rich_analyzer(self):
        """Lazy-load RichAnalyzer, sharing the LLM client."""
        if self._rich_analyzer is None:
            from app.services.rich_analysis import RichAnalyzer
            self._rich_analyzer = RichAnalyzer(llm_client=self.llm_client)
        return self._rich_analyzer

    def synthesize_complete(
        self,
        case_id: int,
        skip_llm_synthesis: bool = False,
        run_extraction_if_needed: bool = True
    ) -> CaseSynthesisModel:
        """
        Execute complete four-phase synthesis pipeline.

        Args:
            case_id: Case to synthesize
            skip_llm_synthesis: If True, skip LLM refinement (for testing)
            run_extraction_if_needed: If True, run Phase 2 extraction if not found

        Returns:
            CaseSynthesisModel with all four phases
        """
        logger.info(f"Starting complete synthesis for case {case_id}")
        extraction_session_id = f"synthesis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        llm_traces = []

        # Get case title
        case = Document.query.get(case_id)
        case_title = case.title if case else f"Case {case_id}"

        # PHASE 1: Entity Foundation
        logger.info("Phase 1: Building entity foundation")
        foundation = self._build_entity_foundation(case_id)
        logger.info(f"Foundation: {foundation.summary()['total']} entities")

        # PHASE 2: Analytical Extraction
        logger.info("Phase 2: Loading/running analytical extraction")
        provisions = self._load_provisions(case_id)
        questions, conclusions = self._load_qc(case_id)
        transformation = self._get_transformation_type(case_id)
        phase2_ran_extraction = False

        # Check if extraction needed
        if not provisions and not questions and run_extraction_if_needed:
            logger.info("Phase 2: No existing data - running extraction")
            phase2_ran_extraction = True
            provisions, questions, conclusions, phase2_traces = self._run_phase2_extraction(
                case_id, case, foundation
            )
            llm_traces.extend(phase2_traces)

        logger.info(f"Extraction: {len(provisions)} provisions, {len(questions)} Q, {len(conclusions)} C")

        # PHASE 2B: Rich Analysis (always run - this is the analytical value)
        logger.info("Phase 2B: Running rich analysis")
        causal_links, question_emergence, resolution_patterns, phase2b_traces = self._run_rich_analysis(
            case_id, foundation, provisions, questions, conclusions
        )
        llm_traces.extend(phase2b_traces)
        logger.info(f"Rich analysis: {len(causal_links)} causal links, {len(question_emergence)} Q emergence, {len(resolution_patterns)} resolution patterns")

        # PHASE 3: Decision Point Synthesis (using modular DecisionPointSynthesizer)
        logger.info("Phase 3: Synthesizing decision points")

        # Convert dataclass lists to dicts for the synthesizer
        qe_dicts = [qe.to_dict() for qe in question_emergence]
        rp_dicts = [rp.to_dict() for rp in resolution_patterns]

        # Run the unified Phase 3 pipeline
        phase3_result = synthesize_decision_points(
            case_id=case_id,
            questions=questions,
            conclusions=conclusions,
            question_emergence=qe_dicts,
            resolution_patterns=rp_dicts,
            domain=self.domain.name,
            skip_llm=skip_llm_synthesis
        )

        canonical_points = phase3_result.canonical_decision_points
        algorithmic_candidates_count = phase3_result.candidates_count

        # Track Phase 3 LLM trace
        if phase3_result.llm_prompt and phase3_result.llm_response:
            llm_traces.append(LLMTrace(
                phase=3,
                phase_name="Decision Point Synthesis",
                stage="LLM Refinement",
                prompt=phase3_result.llm_prompt,
                response=phase3_result.llm_response,
                model=ModelConfig.get_claude_model("default")
            ))

        logger.info(f"Phase 3: {len(canonical_points)} canonical decision points (from {algorithmic_candidates_count} candidates)")

        # PHASE 4: Narrative Construction (using new 4.1-4.4 pipeline)
        logger.info("Phase 4: Constructing narrative with new pipeline")

        # Get causal links as dicts for narrative pipeline
        causal_links_for_narrative = [cl.to_dict() for cl in causal_links]

        # Run the new Phase 4 pipeline
        phase4_result = construct_phase4_narrative(
            case_id=case_id,
            foundation=foundation,
            canonical_points=canonical_points,
            conclusions=conclusions,
            transformation_type=transformation,
            causal_normative_links=causal_links_for_narrative,
            use_llm=not skip_llm_synthesis
        )

        # Save Phase 4 result to database for provenance
        import uuid
        phase4_extraction_prompt = ExtractionPrompt(
            case_id=case_id,
            concept_type='phase4_narrative',
            step_number=4,
            section_type='synthesis',
            prompt_text=f"Complete Synthesis - Phase 4 Narrative Construction (non-streaming)",
            llm_model=ModelConfig.get_claude_model("default"),
            extraction_session_id=extraction_session_id,
            raw_response=json.dumps(phase4_result.to_dict()),
            results_summary=json.dumps(phase4_result.summary())
        )
        db.session.add(phase4_extraction_prompt)
        db.session.commit()

        # Create legacy CaseNarrative for backwards compatibility
        legacy_timeline = []
        for event in phase4_result.timeline.events:
            legacy_timeline.append(TimelineEvent(
                sequence=event.sequence,
                event_label=event.event_label,
                description=event.description,
                entity_uris=[],
                phase=event.phase
            ))

        narrative = CaseNarrative(
            case_summary=phase4_result.scenario_seeds.opening_context[:500] if phase4_result.scenario_seeds.opening_context else "",
            timeline=legacy_timeline,
            scenario_seeds=ScenarioSeeds(
                protagonist=phase4_result.scenario_seeds.protagonist_label,
                opening_situation=phase4_result.scenario_seeds.opening_context,
                central_tension="",
                available_actions=[],
                ethical_considerations=[]
            )
        )

        logger.info(f"Narrative: {len(phase4_result.timeline.events)} timeline events, {len(phase4_result.narrative_elements.characters)} characters")

        # Add Phase 4 LLM traces to the model's trace list
        if phase4_result.llm_traces:
            for trace in phase4_result.llm_traces:
                llm_traces.append(LLMTrace(
                    phase=4,
                    phase_name="Narrative Construction",
                    stage=trace.get('stage', 'unknown'),
                    prompt=trace.get('prompt', ''),
                    response=trace.get('response', ''),
                    model=trace.get('model', ModelConfig.get_claude_model("default"))
                ))
            logger.info(f"Phase 4 LLM traces: {len(phase4_result.llm_traces)}")

        # Note: Canonical points are already stored by DecisionPointSynthesizer

        model = CaseSynthesisModel(
            case_id=case_id,
            case_title=case_title,
            entity_foundation=foundation,
            provisions=provisions,
            questions=questions,
            conclusions=conclusions,
            transformation=TransformationAnalysis(
                transformation_type=transformation,
                confidence=0.8,  # TODO: Load from case_precedent_features
                reasoning="",
                pattern_description="",
                evidence=[]
            ) if transformation else None,
            phase2_ran_extraction=phase2_ran_extraction,
            # Phase 2B: Rich Analysis
            causal_normative_links=causal_links,
            question_emergence=question_emergence,
            resolution_patterns=resolution_patterns,
            # Phase 3
            canonical_decision_points=canonical_points,
            algorithmic_candidates_count=algorithmic_candidates_count,
            # Phase 4
            narrative=narrative,
            phase4_result=phase4_result,
            llm_traces=llm_traces,
            synthesis_timestamp=datetime.now(),
            extraction_session_id=extraction_session_id
        )

        logger.info(f"Synthesis complete: {model.summary()}")
        return model

    def _build_entity_foundation(self, case_id: int) -> EntityFoundation:
        """
        Build entity foundation from all Pass 1-3 extractions.
        """
        foundation = EntityFoundation()

        # Map extraction types to foundation attributes
        type_mapping = {
            'roles': ('roles', foundation.roles),
            'states': ('states', foundation.states),
            'resources': ('resources', foundation.resources),
            'principles': ('principles', foundation.principles),
            'obligations': ('obligations', foundation.obligations),
            'constraints': ('constraints', foundation.constraints),
            'capabilities': ('capabilities', foundation.capabilities),
        }

        for extraction_type, (attr_name, entity_list) in type_mapping.items():
            entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type
            ).all()

            for e in entities:
                entity_list.append(EntitySummary(
                    uri=e.entity_uri or f"case-{case_id}#{e.entity_label.replace(' ', '_')}",
                    label=e.entity_label,
                    definition=e.entity_definition or '',
                    entity_type=extraction_type
                ))

        # Load actions and events from temporal_dynamics_enhanced
        temporal = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).all()

        for e in temporal:
            etype = e.entity_type or ''
            summary = EntitySummary(
                uri=e.entity_uri or f"case-{case_id}#{e.entity_label.replace(' ', '_')}",
                label=e.entity_label,
                definition=e.entity_definition or '',
                entity_type=etype
            )
            if 'action' in etype.lower():
                foundation.actions.append(summary)
            elif 'event' in etype.lower():
                foundation.events.append(summary)

        # Build role-obligation bindings
        for obl in foundation.obligations:
            # Look for role references in the obligation's JSON-LD
            obl_record = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='obligations',
                entity_label=obl.label
            ).first()

            if obl_record and obl_record.rdf_json_ld:
                json_ld = obl_record.rdf_json_ld
                bound_role = json_ld.get('bound_role') or json_ld.get('role_label')
                if bound_role:
                    foundation.role_obligation_bindings.append({
                        'role_label': bound_role,
                        'obligation_label': obl.label,
                        'obligation_uri': obl.uri
                    })

        return foundation

    def _load_provisions(self, case_id: int) -> List[Dict]:
        """Load code provisions from Part A extraction."""
        provisions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).all()

        return [
            {
                'uri': p.entity_uri or '',
                'label': p.entity_label,
                'definition': p.entity_definition or '',
                'code': p.rdf_json_ld.get('codeProvision', '') if p.rdf_json_ld else ''
            }
            for p in provisions
        ]

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
        from app.services.nspe_references_parser import NSPEReferencesParser
        from app.services.universal_provision_detector import UniversalProvisionDetector
        from app.services.provision_grouper import ProvisionGrouper
        from app.services.provision_group_validator import ProvisionGroupValidator
        from app.services.code_provision_linker import CodeProvisionLinker
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
            provision_dicts.append({
                'uri': f"case-{case_id}#Provision_{p.get('code_provision', '').replace('.', '_')}",
                'label': f"NSPE_{p.get('code_provision', '').replace('.', '_')}",
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

    # =========================================================================
    # PHASE 2E: RICH ANALYSIS (delegated to RichAnalyzer)
    # =========================================================================

    def _run_rich_analysis(self, case_id, foundation, provisions, questions, conclusions):
        """Delegate to RichAnalyzer. Backward-compatible signature."""
        return self._get_rich_analyzer().run_rich_analysis(
            case_id, foundation, provisions, questions, conclusions
        )


    def _store_rich_analysis(self, case_id, causal_links, question_emergence, resolution_patterns):
        """Delegate to RichAnalyzer."""
        self._get_rich_analyzer().store_rich_analysis(
            case_id, causal_links, question_emergence, resolution_patterns
        )

    def _load_rich_analysis(self, case_id):
        """Delegate to RichAnalyzer."""
        return self._get_rich_analyzer().load_rich_analysis(case_id)

    def _analyze_causal_normative_links(self, foundation, llm_traces):
        """Delegate to RichAnalyzer."""
        return self._get_rich_analyzer().analyze_causal_normative_links(foundation, llm_traces)

    def _analyze_question_emergence(self, questions, foundation, llm_traces):
        """Delegate to RichAnalyzer."""
        return self._get_rich_analyzer().analyze_question_emergence(questions, foundation, llm_traces)

    def _analyze_question_batch(self, questions, foundation, llm_traces, batch_offset=0):
        """Delegate to RichAnalyzer."""
        return self._get_rich_analyzer().analyze_question_batch(questions, foundation, llm_traces, batch_offset)

    def _analyze_resolution_patterns(self, conclusions, questions, provisions, llm_traces):
        """Delegate to RichAnalyzer. Passes foundation=None (legacy callers don't supply it)."""
        return self._get_rich_analyzer().analyze_resolution_patterns(
            conclusions, questions, provisions, None, llm_traces
        )


    def _construct_narrative(
        self,
        case_id: int,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> CaseNarrative:
        """
        Construct narrative elements for case explanation and scenario.
        """
        # Build timeline from entities
        timeline = []
        sequence = 1

        # Phase 1: Initial states
        if foundation.states:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Initial Context",
                description=f"Case begins with {len(foundation.states)} contextual states",
                entity_uris=[s.uri for s in foundation.states[:3]],
                entity_labels=[s.label for s in foundation.states[:3]],
                event_type='state'
            ))
            sequence += 1

        # Phase 2: Actions taken
        if foundation.actions:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Actions",
                description=f"{len(foundation.actions)} key actions by participants",
                entity_uris=[a.uri for a in foundation.actions],
                entity_labels=[a.label for a in foundation.actions],
                event_type='action'
            ))
            sequence += 1

        # Phase 3: Events that occurred
        if foundation.events:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Events",
                description=f"{len(foundation.events)} significant events",
                entity_uris=[e.uri for e in foundation.events],
                entity_labels=[e.label for e in foundation.events],
                event_type='event'
            ))
            sequence += 1

        # Phase 4: Decision points
        for dp in canonical_points:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label=f"Decision: {dp.focus_id}",
                description=dp.description,
                entity_uris=[dp.role_uri] + (dp.involved_action_uris or []),
                entity_labels=[dp.role_label],
                event_type='decision'
            ))
            sequence += 1

        # Phase 5: Resolution
        if conclusions:
            timeline.append(TimelineEvent(
                sequence=sequence,
                phase_label="Board Resolution",
                description=conclusions[0].get('text', conclusions[0].get('label', 'Board determination'))[:200],
                entity_uris=[c.get('uri', '') for c in conclusions],
                entity_labels=[c.get('label', '') for c in conclusions],
                event_type='outcome'
            ))

        # Build scenario seeds
        protagonist = foundation.roles[0] if foundation.roles else None
        scenario_seeds = None
        if protagonist and canonical_points:
            key_tensions = []
            for dp in canonical_points:
                if dp.obligation_label and dp.constraint_label:
                    key_tensions.append(f"{dp.obligation_label} vs {dp.constraint_label}")
                elif dp.obligation_label:
                    key_tensions.append(dp.obligation_label)

            scenario_seeds = ScenarioSeeds(
                protagonist=protagonist.label,
                protagonist_uri=protagonist.uri,
                setting=f"Professional engineering context with {len(foundation.roles)} key participants",
                inciting_incident=canonical_points[0].decision_question if canonical_points else "Ethical dilemma emerges",
                key_tensions=key_tensions[:3],
                resolution_path=conclusions[0].get('text', '')[:200] if conclusions else ""
            )

        # Generate case summary
        case_summary = self._generate_case_summary(foundation, canonical_points, conclusions)

        return CaseNarrative(
            case_summary=case_summary,
            timeline=timeline,
            scenario_seeds=scenario_seeds
        )

    def _generate_case_summary(
        self,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> str:
        """Generate a 2-3 sentence case summary."""
        # Build summary from entities
        protagonist = foundation.roles[0].label if foundation.roles else "An engineer"
        num_decisions = len(canonical_points)
        key_question = canonical_points[0].decision_question if canonical_points else "a professional ethics question"
        resolution = conclusions[0].get('label', 'The Board provided guidance') if conclusions else "The Board deliberated"

        return (
            f"{protagonist} faced {num_decisions} key decision point{'s' if num_decisions != 1 else ''} "
            f"involving {key_question[:100]}{'...' if len(key_question) > 100 else ''} "
            f"{resolution[:100]}{'...' if len(resolution) > 100 else ''}"
        )

    def _construct_narrative_with_llm(
        self,
        case_id: int,
        case: Document,
        foundation: EntityFoundation,
        canonical_points: List[CanonicalDecisionPoint],
        conclusions: List[Dict]
    ) -> Tuple[CaseNarrative, List[LLMTrace]]:
        """
        Construct narrative elements using LLM for richer descriptions.

        Uses LLM to:
        1. Generate a compelling 2-3 sentence case summary
        2. Create timeline event descriptions that tell a coherent story
        3. Build scenario seeds with meaningful tensions

        Returns:
            Tuple of (CaseNarrative, list of LLMTraces)
        """
        llm_traces = []

        # Build base narrative first (non-LLM)
        base_narrative = self._construct_narrative(case_id, foundation, canonical_points, conclusions)

        # Get case context
        case_title = case.title if case else f"Case {case_id}"
        facts_text = ""
        if case.doc_metadata:
            sections_dual = case.doc_metadata.get('sections_dual', {})
            if 'facts' in sections_dual:
                facts_data = sections_dual['facts']
                facts_text = facts_data.get('text', '')[:1500] if isinstance(facts_data, dict) else str(facts_data)[:1500]

        # =================================================================
        # LLM-Enhanced Case Summary
        # =================================================================
        summary_prompt = f"""Generate a concise 2-3 sentence summary of this NSPE ethics case.

## Case: {case_title}

## Facts (excerpt):
{facts_text}

## Key Participants:
{', '.join([r.label for r in foundation.roles[:5]])}

## Obligations at stake:
{', '.join([o.label for o in foundation.obligations[:5]])}

## Decision Points:
{chr(10).join([f"- {dp.decision_question}" for dp in canonical_points[:3]])}

## Board Conclusions:
{chr(10).join([f"- {c.get('text', c.get('label', ''))[:100]}" for c in conclusions[:2]])}

Write a professional, objective summary that:
1. Identifies the key ethical tension
2. Names the primary decision-maker role (without using "Engineer A" - describe their role)
3. Hints at the resolution

Output ONLY the 2-3 sentence summary, no additional text."""

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=300,
                temperature=0.3,
                messages=[{"role": "user", "content": summary_prompt}]
            )

            enhanced_summary = response.content[0].text.strip()

            llm_traces.append(LLMTrace(
                phase=4,
                phase_name="Narrative Construction",
                stage="Case Summary",
                prompt=summary_prompt,
                response=enhanced_summary,
                model=ModelConfig.get_claude_model("default")
            ))

            logger.info(f"Phase 4: Generated LLM-enhanced case summary")
        except Exception as e:
            logger.warning(f"LLM summary generation failed: {e}")
            enhanced_summary = base_narrative.case_summary

        # =================================================================
        # LLM-Enhanced Timeline
        # =================================================================
        timeline_prompt = f"""Create a timeline of key events for this ethics case. For each phase, write a 1-2 sentence description.

## Case: {case_title}

## Extracted Entities:
- Roles: {', '.join([r.label for r in foundation.roles[:5]])}
- States: {', '.join([s.label for s in foundation.states[:5]])}
- Actions: {', '.join([a.label for a in foundation.actions[:5]])}
- Events: {', '.join([e.label for e in foundation.events[:5]])}

## Decision Points:
{chr(10).join([f"{i+1}. {dp.decision_question}" for i, dp in enumerate(canonical_points[:4])])}

## Conclusions:
{chr(10).join([f"- {c.get('text', c.get('label', ''))[:150]}" for c in conclusions[:2]])}

Generate 4-6 timeline phases. For each, output:
1. Phase label (e.g., "Initial Situation", "Conflict Emerges", "Decision Point", "Resolution")
2. Description (1-2 sentences, objective professional tone)
3. Event type: state/action/event/decision/outcome

Output as JSON array:
```json
[
  {{"phase_label": "...", "description": "...", "event_type": "state"}},
  ...
]
```"""

        try:
            response = self.llm_client.messages.create(
                model=ModelConfig.get_claude_model("default"),
                max_tokens=800,
                temperature=0.3,
                messages=[{"role": "user", "content": timeline_prompt}]
            )

            response_text = response.content[0].text

            llm_traces.append(LLMTrace(
                phase=4,
                phase_name="Narrative Construction",
                stage="Timeline Construction",
                prompt=timeline_prompt,
                response=response_text,
                model=ModelConfig.get_claude_model("default")
            ))

            # Parse timeline JSON
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                timeline_data = json.loads(json_match.group(1))

                enhanced_timeline = []
                for i, item in enumerate(timeline_data, 1):
                    enhanced_timeline.append(TimelineEvent(
                        sequence=i,
                        phase_label=item.get('phase_label', f'Phase {i}'),
                        description=item.get('description', ''),
                        entity_uris=[],  # LLM doesn't provide URIs
                        entity_labels=[],
                        event_type=item.get('event_type', 'event')
                    ))

                logger.info(f"Phase 4: Generated {len(enhanced_timeline)} LLM-enhanced timeline events")
            else:
                enhanced_timeline = base_narrative.timeline
        except Exception as e:
            logger.warning(f"LLM timeline generation failed: {e}")
            enhanced_timeline = base_narrative.timeline

        # =================================================================
        # Enhanced Scenario Seeds
        # =================================================================
        scenario_seeds = base_narrative.scenario_seeds

        if foundation.roles and canonical_points:
            # Use first canonical point's question as inciting incident
            scenario_seeds = ScenarioSeeds(
                protagonist=foundation.roles[0].label,
                protagonist_uri=foundation.roles[0].uri,
                setting=f"Professional engineering context involving {case_title}",
                inciting_incident=canonical_points[0].decision_question if canonical_points else "An ethical dilemma emerges",
                key_tensions=[
                    f"{dp.obligation_label} vs {dp.constraint_label}"
                    for dp in canonical_points
                    if dp.obligation_label and dp.constraint_label
                ][:3],
                resolution_path=conclusions[0].get('text', '')[:200] if conclusions else ""
            )

        return CaseNarrative(
            case_summary=enhanced_summary,
            timeline=enhanced_timeline,
            scenario_seeds=scenario_seeds
        ), llm_traces

    def synthesize(
        self,
        case_id: int,
        generate_arguments: bool = True
    ) -> SynthesisResult:
        """
        Execute unified synthesis pipeline.

        Args:
            case_id: Case to synthesize
            generate_arguments: Whether to run F1-F3 argument generation

        Returns:
            SynthesisResult with canonical decision points and optional arguments
        """
        logger.info(f"Starting unified synthesis for case {case_id}")

        extraction_session_id = f"synthesis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Step S1: Load all extracted entities
        entities = self._load_all_entities(case_id)
        logger.info(f"Loaded entities: {sum(len(v) for v in entities.values())} total")

        # Step S2: Run E1-E3 algorithmic composition
        candidates = self._run_algorithmic_composition(case_id)
        logger.info(f"E1-E3 produced {len(candidates.decision_points)} candidate decision points")

        # Step S3: Load Q&C ground truth
        questions, conclusions = self._load_qc(case_id)
        logger.info(f"Loaded {len(questions)} questions, {len(conclusions)} conclusions as ground truth")

        # Step S4: LLM synthesis - merge candidates with Q&C alignment
        canonical_points = self._llm_synthesize(
            case_id, candidates, questions, conclusions, entities
        )
        logger.info(f"LLM synthesis produced {len(canonical_points)} canonical decision points")

        # Count Q&C aligned
        qc_aligned = sum(1 for dp in canonical_points if dp.aligned_question_uri)

        # Step S5: Generate arguments (optional)
        validated_args = None
        if generate_arguments and canonical_points:
            validated_args = self._generate_arguments(case_id, canonical_points)
            if validated_args:
                logger.info(f"Generated {len(validated_args.valid_arguments)} valid arguments")

        # Save to database
        self._save_canonical_points(case_id, canonical_points, extraction_session_id)
        self._save_provenance(case_id, extraction_session_id)

        result = SynthesisResult(
            case_id=case_id,
            canonical_decision_points=canonical_points,
            arguments=validated_args,
            algorithmic_candidates_count=len(candidates.decision_points),
            llm_merged_count=len(canonical_points),
            qc_aligned_count=qc_aligned,
            synthesis_timestamp=datetime.now(),
            extraction_session_id=extraction_session_id
        )

        logger.info(
            f"Synthesis complete: {len(canonical_points)} decision points, "
            f"{qc_aligned} Q&C aligned"
        )

        return result

    def _load_all_entities(self, case_id: int) -> Dict[str, List[Dict]]:
        """
        Load ALL entity types from database with URIs.

        Returns dict by entity type with label, definition, uri.
        """
        extraction_type_map = {
            'roles': 'roles',
            'states': 'states',
            'resources': 'resources',
            'principles': 'principles',
            'obligations': 'obligations',
            'constraints': 'constraints',
            'capabilities': 'capabilities',
            'actions': 'temporal_dynamics_enhanced',
            'events': 'temporal_dynamics_enhanced',
            'provisions': 'code_provision_reference',
            'questions': 'ethical_question',
            'conclusions': 'ethical_conclusion'
        }

        entity_type_filter = {
            'actions': 'actions',
            'events': 'events'
        }

        entities = {}
        for key, extraction_type in extraction_type_map.items():
            query = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type
            )

            if key in entity_type_filter:
                query = query.filter_by(entity_type=entity_type_filter[key])

            records = query.all()

            entities[key] = [
                {
                    'label': r.entity_label,
                    'definition': r.entity_definition or '',
                    'uri': r.entity_uri or '',
                    'id': r.id,
                    'rdf_json_ld': r.rdf_json_ld
                }
                for r in records
            ]

        return entities

    # Note: _run_algorithmic_composition moved to decision_point_synthesizer.py

    def _load_qc(self, case_id: int) -> Tuple[List[Dict], List[Dict]]:
        """Load questions and conclusions from Step 4B."""
        questions_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).all()

        conclusions_raw = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).all()

        questions = [
            {
                'uri': q.entity_uri or f"case-{case_id}#Q{i+1}",
                'label': q.entity_label,
                'text': q.entity_definition or q.entity_label
            }
            for i, q in enumerate(questions_raw)
        ]

        conclusions = [
            {
                'uri': c.entity_uri or f"case-{case_id}#C{i+1}",
                'label': c.entity_label,
                'text': c.entity_definition or c.entity_label
            }
            for i, c in enumerate(conclusions_raw)
        ]

        return questions, conclusions

    # Note: _llm_synthesize, _format_candidates, _format_qc, _format_entities_summary,
    # _parse_synthesis_response, _convert_algorithmic_to_canonical moved to decision_point_synthesizer.py

    def _generate_arguments(
        self,
        case_id: int,
        canonical_points: List[CanonicalDecisionPoint]
    ) -> Optional[ValidatedArguments]:
        """Generate arguments for canonical decision points using F1-F3."""
        try:
            # F1: Principle-Provision Alignment
            alignment = get_principle_provision_alignment(case_id, self.domain.name)

            # F2: Generate Arguments
            # Convert canonical points to the format expected by ArgumentGenerator
            args = generate_arguments(case_id, self.domain.name)

            # F3: Validate Arguments
            validated = validate_arguments(case_id, args, self.domain.name)

            return validated

        except Exception as e:
            logger.error(f"Argument generation failed: {e}")
            return None

    # Note: _save_canonical_points moved to decision_point_synthesizer.py

    def _save_provenance(self, case_id: int, extraction_session_id: str) -> Optional[int]:
        """Save synthesis provenance."""
        if not self.last_prompt or not self.last_response:
            return None

        try:
            prompt = ExtractionPrompt.save_prompt(
                case_id=case_id,
                concept_type='unified_synthesis',
                prompt_text=self.last_prompt,
                raw_response=self.last_response,
                step_number=4,
                llm_model=ModelConfig.get_claude_model("default"),
                section_type='synthesis',
                extraction_session_id=extraction_session_id
            )
            return prompt.id
        except Exception as e:
            logger.error(f"Failed to save synthesis provenance: {e}")
            return None

    def load_canonical_points(self, case_id: int) -> List[CanonicalDecisionPoint]:
        """Load canonical decision points from database."""
        try:
            entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point'
            ).order_by(TemporaryRDFStorage.id).all()

            canonical_points = []
            for entity in entities:
                json_ld = entity.rdf_json_ld or {}

                canonical = CanonicalDecisionPoint(
                    focus_id=json_ld.get('focus_id', ''),
                    focus_number=json_ld.get('focus_number', 0),
                    description=entity.entity_label,
                    decision_question=json_ld.get('decision_question', ''),
                    role_uri=json_ld.get('role_uri', ''),
                    role_label=json_ld.get('role_label', ''),
                    obligation_uri=json_ld.get('obligation_uri'),
                    obligation_label=json_ld.get('obligation_label'),
                    constraint_uri=json_ld.get('constraint_uri'),
                    constraint_label=json_ld.get('constraint_label'),
                    involved_action_uris=json_ld.get('involved_action_uris', []),
                    provision_uris=json_ld.get('provision_uris', []),
                    provision_labels=json_ld.get('provision_labels', []),
                    aligned_question_uri=json_ld.get('aligned_question_uri'),
                    aligned_question_text=json_ld.get('aligned_question_text'),
                    aligned_conclusion_uri=json_ld.get('aligned_conclusion_uri'),
                    aligned_conclusion_text=json_ld.get('aligned_conclusion_text'),
                    options=json_ld.get('options', []),
                    intensity_score=json_ld.get('intensity_score', 0.0),
                    qc_alignment_score=json_ld.get('qc_alignment_score', 0.0),
                    source=json_ld.get('source', 'unified'),
                    algorithmic_focus_id=json_ld.get('algorithmic_focus_id')
                )
                canonical_points.append(canonical)

            return canonical_points

        except Exception as e:
            logger.error(f"Failed to load canonical decision points: {e}")
            return []


def synthesize_case(case_id: int, domain: str = 'engineering') -> SynthesisResult:
    """
    Convenience function to run unified synthesis.

    Args:
        case_id: Case to synthesize
        domain: Domain code (default: engineering)

    Returns:
        SynthesisResult with canonical decision points
    """
    domain_config = get_domain_config(domain)
    synthesizer = CaseSynthesizer(domain_config=domain_config)
    return synthesizer.synthesize(case_id)
