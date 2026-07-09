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
from model_config import ModelConfig

# Data models (extracted to separate module for modularity)
from app.services.step4_synthesis.case_synthesis_models import (  # noqa: F401 -- re-exported for backward compatibility
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
from .phase2 import Phase2ExtractionMixin

logger = logging.getLogger(__name__)

PROETHICA_INT_NS = "http://proethica.org/ontology/intermediate#"
# Canonical per-case namespace (slash form), matching the commit serializer + edge
# materialisers. Was the divergent ontology/case-<id># hyphen scheme (R2 unification).
PROETHICA_CASE_NS = "http://proethica.org/ontology/case/{case_id}#"


class CaseSynthesizer(NarrativeConstructionMixin, Phase2ExtractionMixin):
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
            from app.services.step4_synthesis.rich_analysis import RichAnalyzer
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
        foundation.case_id = case_id

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
            # Individuals only: class rows are shared vocabulary, not case
            # content, and they leaked into narrative surfaces (case 9's
            # opening states showed LitigationContextState -- a TYPE CLASS --
            # as a t0 fluent; 2026-07-09 walkthrough). Same correction the
            # E1-E3 analyzers received in 35baf89.
            entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type=extraction_type,
                storage_type='individual'
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
                # Provision rows carry no entity_uri pre-commit (all 96 gold rows
                # empty, 2026-07-08 Q/C analysis): fall back to the provision code
                # so downstream reference resolution never serializes ''.
                'uri': p.entity_uri
                       or (p.rdf_json_ld.get('codeProvision', '') if p.rdf_json_ld else '')
                       or p.entity_label,
                'label': p.entity_label,
                'definition': p.entity_definition or '',
                'code': p.rdf_json_ld.get('codeProvision', '') if p.rdf_json_ld else ''
            }
            for p in provisions
        ]


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
