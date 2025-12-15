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
from dataclasses import dataclass, field, asdict
from datetime import datetime

from sqlalchemy import text
from app import db
from app.models import Document, TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from app.domains import DomainConfig, get_domain_config

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

logger = logging.getLogger(__name__)

PROETHICA_INT_NS = "http://proethica.org/ontology/intermediate#"
PROETHICA_CASE_NS = "http://proethica.org/ontology/case-{case_id}#"


# =============================================================================
# PHASE 1: ENTITY FOUNDATION
# =============================================================================

@dataclass
class EntitySummary:
    """Summary of an entity for display."""
    uri: str
    label: str
    definition: str = ""
    entity_type: str = ""


@dataclass
class EntityFoundation:
    """All entities from Passes 1-3 organized for synthesis."""
    # Pass 1: Contextual Framework
    roles: List[EntitySummary] = field(default_factory=list)
    states: List[EntitySummary] = field(default_factory=list)
    resources: List[EntitySummary] = field(default_factory=list)

    # Pass 2: Normative Requirements
    principles: List[EntitySummary] = field(default_factory=list)
    obligations: List[EntitySummary] = field(default_factory=list)
    constraints: List[EntitySummary] = field(default_factory=list)
    capabilities: List[EntitySummary] = field(default_factory=list)

    # Pass 3: Temporal Dynamics
    actions: List[EntitySummary] = field(default_factory=list)
    events: List[EntitySummary] = field(default_factory=list)

    # Derived relationships
    role_obligation_bindings: List[Dict] = field(default_factory=list)
    action_obligation_map: Dict[str, List[str]] = field(default_factory=dict)

    def summary(self) -> Dict:
        """Summary counts for display."""
        return {
            'pass1': {
                'roles': len(self.roles),
                'states': len(self.states),
                'resources': len(self.resources),
                'total': len(self.roles) + len(self.states) + len(self.resources)
            },
            'pass2': {
                'principles': len(self.principles),
                'obligations': len(self.obligations),
                'constraints': len(self.constraints),
                'capabilities': len(self.capabilities),
                'total': len(self.principles) + len(self.obligations) + len(self.constraints) + len(self.capabilities)
            },
            'pass3': {
                'actions': len(self.actions),
                'events': len(self.events),
                'total': len(self.actions) + len(self.events)
            },
            'total': (len(self.roles) + len(self.states) + len(self.resources) +
                     len(self.principles) + len(self.obligations) + len(self.constraints) +
                     len(self.capabilities) + len(self.actions) + len(self.events)),
            'relationships': {
                'role_obligation_bindings': len(self.role_obligation_bindings),
                'action_obligation_mappings': len(self.action_obligation_map)
            }
        }

    def to_dict(self) -> Dict:
        return {
            'roles': [asdict(e) for e in self.roles],
            'states': [asdict(e) for e in self.states],
            'resources': [asdict(e) for e in self.resources],
            'principles': [asdict(e) for e in self.principles],
            'obligations': [asdict(e) for e in self.obligations],
            'constraints': [asdict(e) for e in self.constraints],
            'capabilities': [asdict(e) for e in self.capabilities],
            'actions': [asdict(e) for e in self.actions],
            'events': [asdict(e) for e in self.events],
            'role_obligation_bindings': self.role_obligation_bindings,
            'action_obligation_map': self.action_obligation_map,
            'summary': self.summary()
        }


# =============================================================================
# PHASE 4: NARRATIVE CONSTRUCTION
# =============================================================================

@dataclass
class TimelineEvent:
    """A point in the case timeline anchored to entities."""
    sequence: int
    phase_label: str  # "Initial State", "Action Phase", "Decision Point", etc.
    description: str
    entity_uris: List[str] = field(default_factory=list)
    entity_labels: List[str] = field(default_factory=list)
    event_type: str = "event"  # 'state', 'action', 'event', 'decision', 'outcome'

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ScenarioSeeds:
    """Elements prepared for scenario generation (Step 5)."""
    protagonist: str  # Primary decision-maker role
    protagonist_uri: str
    setting: str  # Context description
    inciting_incident: str  # What triggers the ethical dilemma
    key_tensions: List[str] = field(default_factory=list)  # Obligation conflicts
    resolution_path: str = ""  # How Board resolved it

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CaseNarrative:
    """Narrative elements constructed from synthesis."""
    case_summary: str  # 2-3 sentence overview
    timeline: List[TimelineEvent] = field(default_factory=list)
    scenario_seeds: Optional[ScenarioSeeds] = None

    def to_dict(self) -> Dict:
        return {
            'case_summary': self.case_summary,
            'timeline': [t.to_dict() for t in self.timeline],
            'scenario_seeds': self.scenario_seeds.to_dict() if self.scenario_seeds else None
        }


# =============================================================================
# COMPLETE CASE SYNTHESIS MODEL
# =============================================================================

@dataclass
class LLMTrace:
    """Record of an LLM interaction during synthesis."""
    phase: int
    phase_name: str
    stage: str
    prompt: str
    response: str
    model: str
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
        return {
            'phase': self.phase,
            'phase_name': self.phase_name,
            'stage': self.stage,
            'prompt': self.prompt[:500] + '...' if len(self.prompt) > 500 else self.prompt,
            'response': self.response[:500] + '...' if len(self.response) > 500 else self.response,
            'model': self.model,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class CausalNormativeLink:
    """Links an action/event to normative requirements (obligations, principles)."""
    action_id: str
    action_label: str
    fulfills_obligations: List[str] = field(default_factory=list)
    violates_obligations: List[str] = field(default_factory=list)
    guided_by_principles: List[str] = field(default_factory=list)
    constrained_by: List[str] = field(default_factory=list)
    agent_role: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class QuestionEmergenceAnalysis:
    """Analysis of WHY an ethical question emerged from the case."""
    question_uri: str
    question_text: str
    triggered_by_events: List[str] = field(default_factory=list)
    triggered_by_actions: List[str] = field(default_factory=list)
    involves_roles: List[str] = field(default_factory=list)
    competing_obligations: List[Tuple[str, str]] = field(default_factory=list)  # (obl1, obl2)
    emergence_narrative: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'question_uri': self.question_uri,
            'question_text': self.question_text,
            'triggered_by_events': self.triggered_by_events,
            'triggered_by_actions': self.triggered_by_actions,
            'involves_roles': self.involves_roles,
            'competing_obligations': [list(t) for t in self.competing_obligations],
            'emergence_narrative': self.emergence_narrative,
            'confidence': self.confidence
        }


@dataclass
class ResolutionPatternAnalysis:
    """Analysis of HOW the board resolved an ethical question."""
    conclusion_uri: str
    conclusion_text: str
    answers_questions: List[str] = field(default_factory=list)
    determinative_principles: List[str] = field(default_factory=list)
    determinative_facts: List[str] = field(default_factory=list)
    cited_provisions: List[str] = field(default_factory=list)
    weighing_process: str = ""  # How competing obligations were weighed
    resolution_narrative: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class TransformationAnalysis:
    """Analysis of the case transformation type with reasoning."""
    transformation_type: str  # transfer, stalemate, oscillation, phase_lag
    confidence: float = 0.0
    reasoning: str = ""
    pattern_description: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class CaseSynthesisModel:
    """Complete synthesis output for a case - all four phases with rich analysis."""
    case_id: int
    case_title: str

    # Phase 1: Entity Foundation (what we're building from)
    entity_foundation: EntityFoundation

    # Phase 2: Analytical Extraction (with rich analysis)
    provisions: List[Dict] = field(default_factory=list)  # Each has validation, excerpts, linked_entities
    questions: List[Dict] = field(default_factory=list)  # Each has mentioned_entities, related_provisions
    conclusions: List[Dict] = field(default_factory=list)  # Each has cited_provisions, answers_questions
    transformation: Optional[TransformationAnalysis] = None
    phase2_ran_extraction: bool = False

    # Phase 2b: Rich Analysis (from CaseSynthesisService)
    causal_normative_links: List[CausalNormativeLink] = field(default_factory=list)
    question_emergence: List[QuestionEmergenceAnalysis] = field(default_factory=list)
    resolution_patterns: List[ResolutionPatternAnalysis] = field(default_factory=list)

    # Phase 3: Decision Point Synthesis
    canonical_decision_points: List['CanonicalDecisionPoint'] = field(default_factory=list)
    algorithmic_candidates_count: int = 0

    # Phase 4: Narrative Construction
    narrative: Optional[CaseNarrative] = None

    # LLM Traces (for all phases that use LLM)
    llm_traces: List[LLMTrace] = field(default_factory=list)

    # Metadata
    synthesis_timestamp: Optional[datetime] = None
    extraction_session_id: Optional[str] = None

    # Backwards compatibility
    @property
    def transformation_type(self) -> str:
        return self.transformation.transformation_type if self.transformation else ""

    def summary(self) -> Dict:
        """Summary for display."""
        return {
            'entity_foundation': self.entity_foundation.summary(),
            'analytical_extraction': {
                'provisions': len(self.provisions),
                'questions': len(self.questions),
                'conclusions': len(self.conclusions),
                'transformation_type': self.transformation_type,
                'transformation_confidence': self.transformation.confidence if self.transformation else 0,
                'ran_extraction': self.phase2_ran_extraction
            },
            'rich_analysis': {
                'causal_normative_links': len(self.causal_normative_links),
                'question_emergence': len(self.question_emergence),
                'resolution_patterns': len(self.resolution_patterns)
            },
            'decision_points': {
                'canonical_count': len(self.canonical_decision_points),
                'algorithmic_candidates': self.algorithmic_candidates_count,
                'qc_aligned': sum(1 for dp in self.canonical_decision_points if dp.aligned_question_uri)
            },
            'narrative': {
                'has_summary': bool(self.narrative and self.narrative.case_summary),
                'timeline_events': len(self.narrative.timeline) if self.narrative else 0,
                'has_scenario_seeds': bool(self.narrative and self.narrative.scenario_seeds)
            },
            'llm_traces': {
                'count': len(self.llm_traces),
                'phases': list(set(t.phase for t in self.llm_traces))
            }
        }

    def to_dict(self) -> Dict:
        return {
            'case_id': self.case_id,
            'case_title': self.case_title,
            'entity_foundation': self.entity_foundation.to_dict(),
            'provisions': self.provisions,
            'questions': self.questions,
            'conclusions': self.conclusions,
            'transformation': self.transformation.to_dict() if self.transformation else None,
            'transformation_type': self.transformation_type,  # Backwards compat
            'phase2_ran_extraction': self.phase2_ran_extraction,
            'causal_normative_links': [c.to_dict() for c in self.causal_normative_links],
            'question_emergence': [q.to_dict() for q in self.question_emergence],
            'resolution_patterns': [r.to_dict() for r in self.resolution_patterns],
            'canonical_decision_points': [dp.to_dict() for dp in self.canonical_decision_points],
            'algorithmic_candidates_count': self.algorithmic_candidates_count,
            'narrative': self.narrative.to_dict() if self.narrative else None,
            'llm_traces': [t.to_dict() for t in self.llm_traces],
            'summary': self.summary(),
            'synthesis_timestamp': self.synthesis_timestamp.isoformat() if self.synthesis_timestamp else None,
            'extraction_session_id': self.extraction_session_id
        }


# =============================================================================
# CANONICAL DECISION POINT (Phase 3 output)
# =============================================================================

@dataclass
class CanonicalDecisionPoint:
    """
    A canonical decision point produced by the unified pipeline.

    Combines algorithmic composition with LLM refinement.
    """
    focus_id: str
    focus_number: int
    description: str
    decision_question: str

    # Entity grounding (from E3)
    role_uri: str
    role_label: str
    obligation_uri: Optional[str] = None
    obligation_label: Optional[str] = None
    constraint_uri: Optional[str] = None
    constraint_label: Optional[str] = None

    # Related entities
    involved_action_uris: List[str] = field(default_factory=list)
    provision_uris: List[str] = field(default_factory=list)
    provision_labels: List[str] = field(default_factory=list)

    # Q&C alignment (ground truth from Step 4B)
    aligned_question_uri: Optional[str] = None
    aligned_question_text: Optional[str] = None
    aligned_conclusion_uri: Optional[str] = None
    aligned_conclusion_text: Optional[str] = None

    # Options with action grounding
    options: List[Dict] = field(default_factory=list)

    # Scores
    intensity_score: float = 0.0
    qc_alignment_score: float = 0.0

    # Source tracking
    source: str = "unified"  # 'algorithmic', 'llm', 'unified'
    algorithmic_focus_id: Optional[str] = None  # Original ID from E3

    # LLM refinement
    llm_refined_description: Optional[str] = None
    llm_refined_question: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SynthesisResult:
    """Complete synthesis output."""
    case_id: int
    canonical_decision_points: List[CanonicalDecisionPoint]
    arguments: Optional[ValidatedArguments] = None

    # Metadata
    algorithmic_candidates_count: int = 0
    llm_merged_count: int = 0
    qc_aligned_count: int = 0

    # Provenance
    synthesis_timestamp: Optional[datetime] = None
    extraction_session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'canonical_decision_points': [dp.to_dict() for dp in self.canonical_decision_points],
            'arguments': self.arguments.to_dict() if self.arguments else None,
            'algorithmic_candidates_count': self.algorithmic_candidates_count,
            'llm_merged_count': self.llm_merged_count,
            'qc_aligned_count': self.qc_aligned_count,
            'synthesis_timestamp': self.synthesis_timestamp.isoformat() if self.synthesis_timestamp else None,
            'extraction_session_id': self.extraction_session_id
        }


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

        # PHASE 3: Decision Point Synthesis
        logger.info("Phase 3: Synthesizing decision points")
        candidates = self._run_algorithmic_composition(case_id)
        logger.info(f"E1-E3: {len(candidates.decision_points)} candidates")

        if skip_llm_synthesis:
            canonical_points = self._convert_algorithmic_to_canonical(candidates, questions, conclusions)
        else:
            entities_dict = self._load_all_entities(case_id)
            canonical_points = self._llm_synthesize(case_id, candidates, questions, conclusions, entities_dict)

            # Track Phase 3 LLM trace
            if self.last_prompt and self.last_response:
                llm_traces.append(LLMTrace(
                    phase=3,
                    phase_name="Decision Point Synthesis",
                    stage="LLM Refinement",
                    prompt=self.last_prompt,
                    response=self.last_response,
                    model="claude-sonnet-4-20250514"
                ))

        logger.info(f"Canonical: {len(canonical_points)} decision points")

        # PHASE 4: Narrative Construction (with LLM enhancement)
        logger.info("Phase 4: Constructing narrative")
        if skip_llm_synthesis:
            narrative = self._construct_narrative(case_id, foundation, canonical_points, conclusions)
        else:
            narrative, phase4_traces = self._construct_narrative_with_llm(
                case_id, case, foundation, canonical_points, conclusions
            )
            llm_traces.extend(phase4_traces)

        logger.info(f"Narrative: {len(narrative.timeline)} timeline events")

        # Save canonical points
        self._save_canonical_points(case_id, canonical_points, extraction_session_id)

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
            algorithmic_candidates_count=len(candidates.decision_points),
            narrative=narrative,
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
                                    model="claude-sonnet-4-20250514"
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
                            model="claude-sonnet-4-20250514"
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
                    questions.append({
                        'uri': f"case-{case_id}#Q{i+1}",
                        'label': f"Question_{i+1}",
                        'text': getattr(q, 'question_text', str(q)),
                        'mentioned_entities': getattr(q, 'mentioned_entities', []),
                        'related_provisions': getattr(q, 'related_provisions', [])
                    })

                if hasattr(question_analyzer, 'last_prompt') and question_analyzer.last_prompt:
                    llm_traces.append(LLMTrace(
                        phase=2,
                        phase_name="Analytical Extraction",
                        stage="Question Extraction",
                        prompt=question_analyzer.last_prompt,
                        response=getattr(question_analyzer, 'last_response', ''),
                        model="claude-sonnet-4-20250514"
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
                    conclusions.append({
                        'uri': f"case-{case_id}#C{i+1}",
                        'label': f"Conclusion_{i+1}",
                        'text': getattr(c, 'conclusion_text', str(c)),
                        'mentioned_entities': getattr(c, 'mentioned_entities', []),
                        'cited_provisions': getattr(c, 'cited_provisions', []),
                        'conclusion_type': getattr(c, 'conclusion_type', 'determination')
                    })

                if hasattr(conclusion_analyzer, 'last_prompt') and conclusion_analyzer.last_prompt:
                    llm_traces.append(LLMTrace(
                        phase=2,
                        phase_name="Analytical Extraction",
                        stage="Conclusion Extraction",
                        prompt=conclusion_analyzer.last_prompt,
                        response=getattr(conclusion_analyzer, 'last_response', ''),
                        model="claude-sonnet-4-20250514"
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
                        model="claude-sonnet-4-20250514"
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
                    model="claude-sonnet-4-20250514"
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

            if existing:
                db.session.execute(
                    text("""
                        UPDATE case_precedent_features
                        SET transformation_type = :type,
                            transformation_confidence = :confidence,
                            transformation_reasoning = :reasoning
                        WHERE case_id = :case_id
                    """),
                    {
                        'case_id': case_id,
                        'type': result.transformation_type,
                        'confidence': result.confidence,
                        'reasoning': result.reasoning
                    }
                )
            else:
                db.session.execute(
                    text("""
                        INSERT INTO case_precedent_features (case_id, transformation_type, transformation_confidence, transformation_reasoning)
                        VALUES (:case_id, :type, :confidence, :reasoning)
                    """),
                    {
                        'case_id': case_id,
                        'type': result.transformation_type,
                        'confidence': result.confidence,
                        'reasoning': result.reasoning
                    }
                )
            db.session.commit()
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
                    extraction_model='claude-sonnet-4-20250514',
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
                    extraction_model='claude-sonnet-4-20250514',
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
                    extraction_model='claude-sonnet-4-20250514',
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            db.session.commit()
            logger.info(f"Stored Phase 2 results: {len(provisions)} provisions, {len(questions)} Q, {len(conclusions)} C")

        except Exception as e:
            logger.error(f"Failed to store Phase 2 results: {e}")
            db.session.rollback()

    # =========================================================================
    # PHASE 2B: RICH ANALYSIS
    # =========================================================================

    def _run_rich_analysis(
        self,
        case_id: int,
        foundation: EntityFoundation,
        provisions: List[Dict],
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> Tuple[List[CausalNormativeLink], List[QuestionEmergenceAnalysis], List[ResolutionPatternAnalysis], List[LLMTrace]]:
        """
        Analyze relationships between entities, questions, and conclusions.

        This is the ANALYTICAL layer that makes Phase 2 valuable - it shows:
        1. How actions relate to obligations (causal-normative links)
        2. Why each ethical question emerged (triggers, competing obligations)
        3. How the board resolved each question (determinative factors)

        Args:
            case_id: Case being analyzed
            foundation: Entity foundation from Phase 1
            provisions: Code provisions extracted in Phase 2
            questions: Ethical questions extracted in Phase 2
            conclusions: Board conclusions extracted in Phase 2

        Returns:
            Tuple of (causal_links, question_analyses, resolution_patterns, llm_traces)
        """
        logger.info(f"Phase 2B: Running rich analysis for case {case_id}")
        llm_traces = []

        # 1. Causal-Normative Links: For each Action/Event, which obligations does it fulfill/violate?
        causal_links = self._analyze_causal_normative_links(foundation, llm_traces)
        logger.info(f"Phase 2B: Analyzed {len(causal_links)} causal-normative links")

        # 2. Question Emergence: WHY did each ethical question arise?
        question_analysis = self._analyze_question_emergence(questions, foundation, llm_traces)
        logger.info(f"Phase 2B: Analyzed {len(question_analysis)} question emergence patterns")

        # 3. Resolution Patterns: HOW did the board resolve each question?
        resolution_analysis = self._analyze_resolution_patterns(conclusions, questions, provisions, llm_traces)
        logger.info(f"Phase 2B: Analyzed {len(resolution_analysis)} resolution patterns")

        # Store rich analysis to database
        self._store_rich_analysis(case_id, causal_links, question_analysis, resolution_analysis)

        return causal_links, question_analysis, resolution_analysis, llm_traces

    def _store_rich_analysis(
        self,
        case_id: int,
        causal_links: List[CausalNormativeLink],
        question_emergence: List[QuestionEmergenceAnalysis],
        resolution_patterns: List[ResolutionPatternAnalysis]
    ) -> None:
        """
        Store rich analysis results to database.

        Uses TemporaryRDFStorage with specific extraction_types:
        - causal_normative_link
        - question_emergence
        - resolution_pattern

        Clears existing data before storing (replace semantics).
        """
        try:
            # Clear existing rich analysis data
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='causal_normative_link'
            ).delete(synchronize_session=False)
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='question_emergence'
            ).delete(synchronize_session=False)
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='resolution_pattern'
            ).delete(synchronize_session=False)

            session_id = f"rich_analysis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Store causal-normative links
            for i, link in enumerate(causal_links):
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='causal_normative_link',
                    storage_type='individual',
                    entity_type='analysis',
                    entity_label=f"CausalLink_{link.action_label[:30]}",
                    entity_uri=f"case-{case_id}#CausalLink_{i+1}",
                    entity_definition=link.reasoning,
                    rdf_json_ld={
                        '@type': 'proeth-analysis:CausalNormativeLink',
                        'action_id': link.action_id,
                        'action_label': link.action_label,
                        'fulfills_obligations': link.fulfills_obligations,
                        'violates_obligations': link.violates_obligations,
                        'guided_by_principles': link.guided_by_principles,
                        'constrained_by': link.constrained_by,
                        'agent_role': link.agent_role,
                        'reasoning': link.reasoning,
                        'confidence': link.confidence
                    },
                    is_selected=True,
                    extraction_model='claude-sonnet-4-20250514',
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            # Store question emergence analyses
            for i, qa in enumerate(question_emergence):
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='question_emergence',
                    storage_type='individual',
                    entity_type='analysis',
                    entity_label=f"QuestionEmergence_{i+1}",
                    entity_uri=qa.question_uri or f"case-{case_id}#QuestionEmergence_{i+1}",
                    entity_definition=qa.emergence_narrative,
                    rdf_json_ld={
                        '@type': 'proeth-analysis:QuestionEmergence',
                        'question_uri': qa.question_uri,
                        'question_text': qa.question_text,
                        'triggered_by_events': qa.triggered_by_events,
                        'triggered_by_actions': qa.triggered_by_actions,
                        'involves_roles': qa.involves_roles,
                        'competing_obligations': [list(pair) for pair in qa.competing_obligations],
                        'emergence_narrative': qa.emergence_narrative,
                        'confidence': qa.confidence
                    },
                    is_selected=True,
                    extraction_model='claude-sonnet-4-20250514',
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            # Store resolution patterns
            for i, rp in enumerate(resolution_patterns):
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='resolution_pattern',
                    storage_type='individual',
                    entity_type='analysis',
                    entity_label=f"ResolutionPattern_{i+1}",
                    entity_uri=rp.conclusion_uri or f"case-{case_id}#ResolutionPattern_{i+1}",
                    entity_definition=rp.resolution_narrative,
                    rdf_json_ld={
                        '@type': 'proeth-analysis:ResolutionPattern',
                        'conclusion_uri': rp.conclusion_uri,
                        'conclusion_text': rp.conclusion_text,
                        'answers_questions': rp.answers_questions,
                        'determinative_principles': rp.determinative_principles,
                        'determinative_facts': rp.determinative_facts,
                        'cited_provisions': rp.cited_provisions,
                        'weighing_process': rp.weighing_process,
                        'resolution_narrative': rp.resolution_narrative,
                        'confidence': rp.confidence
                    },
                    is_selected=True,
                    extraction_model='claude-sonnet-4-20250514',
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            db.session.commit()
            logger.info(f"Stored rich analysis: {len(causal_links)} links, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

        except Exception as e:
            logger.error(f"Failed to store rich analysis: {e}")
            db.session.rollback()

    def _load_rich_analysis(
        self,
        case_id: int
    ) -> Tuple[List[CausalNormativeLink], List[QuestionEmergenceAnalysis], List[ResolutionPatternAnalysis]]:
        """
        Load rich analysis from database.

        Returns:
            Tuple of (causal_links, question_emergence, resolution_patterns)
        """
        causal_links = []
        question_emergence = []
        resolution_patterns = []

        try:
            # Load causal-normative links
            causal_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='causal_normative_link'
            ).all()

            for r in causal_records:
                data = r.rdf_json_ld or {}
                causal_links.append(CausalNormativeLink(
                    action_id=data.get('action_id', ''),
                    action_label=data.get('action_label', ''),
                    fulfills_obligations=data.get('fulfills_obligations', []),
                    violates_obligations=data.get('violates_obligations', []),
                    guided_by_principles=data.get('guided_by_principles', []),
                    constrained_by=data.get('constrained_by', []),
                    agent_role=data.get('agent_role'),
                    reasoning=data.get('reasoning', ''),
                    confidence=data.get('confidence', 0.0)
                ))

            # Load question emergence
            qe_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='question_emergence'
            ).all()

            for r in qe_records:
                data = r.rdf_json_ld or {}
                question_emergence.append(QuestionEmergenceAnalysis(
                    question_uri=data.get('question_uri', ''),
                    question_text=data.get('question_text', ''),
                    triggered_by_events=data.get('triggered_by_events', []),
                    triggered_by_actions=data.get('triggered_by_actions', []),
                    involves_roles=data.get('involves_roles', []),
                    competing_obligations=[tuple(p) for p in data.get('competing_obligations', [])],
                    emergence_narrative=data.get('emergence_narrative', ''),
                    confidence=data.get('confidence', 0.0)
                ))

            # Load resolution patterns
            rp_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='resolution_pattern'
            ).all()

            for r in rp_records:
                data = r.rdf_json_ld or {}
                resolution_patterns.append(ResolutionPatternAnalysis(
                    conclusion_uri=data.get('conclusion_uri', ''),
                    conclusion_text=data.get('conclusion_text', ''),
                    answers_questions=data.get('answers_questions', []),
                    determinative_principles=data.get('determinative_principles', []),
                    determinative_facts=data.get('determinative_facts', []),
                    cited_provisions=data.get('cited_provisions', []),
                    weighing_process=data.get('weighing_process', ''),
                    resolution_narrative=data.get('resolution_narrative', ''),
                    confidence=data.get('confidence', 0.0)
                ))

            logger.info(f"Loaded rich analysis: {len(causal_links)} links, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

        except Exception as e:
            logger.error(f"Failed to load rich analysis: {e}")

        return causal_links, question_emergence, resolution_patterns

    def _analyze_causal_normative_links(
        self,
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[CausalNormativeLink]:
        """
        Analyze which obligations each action fulfills or violates.

        For each Action in the foundation, determines:
        - Which obligations it fulfills
        - Which obligations it violates
        - Which principles guide it
        - Which constraints limit it
        - Which role performs it
        """
        if not foundation.actions:
            return []

        # Format actions for the prompt
        actions_text = "\n".join([
            f"- {a.label}: {a.definition or 'No definition'} (URI: {a.uri})"
            for a in foundation.actions
        ])

        # Format obligations
        obligations_text = "\n".join([
            f"- {o.label}: {o.definition or 'No definition'} (URI: {o.uri})"
            for o in foundation.obligations
        ])

        # Format principles
        principles_text = "\n".join([
            f"- {p.label}: {p.definition or 'No definition'} (URI: {p.uri})"
            for p in foundation.principles
        ])

        # Format constraints
        constraints_text = "\n".join([
            f"- {c.label}: {c.definition or 'No definition'} (URI: {c.uri})"
            for c in foundation.constraints
        ])

        # Format roles
        roles_text = "\n".join([
            f"- {r.label}: {r.definition or 'No definition'} (URI: {r.uri})"
            for r in foundation.roles
        ])

        prompt = f"""Analyze how each ACTION relates to the OBLIGATIONS, PRINCIPLES, and CONSTRAINTS in this ethics case.

## ACTIONS (things that happened or could happen)
{actions_text}

## OBLIGATIONS (duties that apply)
{obligations_text}

## PRINCIPLES (ethical foundations)
{principles_text}

## CONSTRAINTS (limitations that apply)
{constraints_text}

## ROLES (agents in the case)
{roles_text}

For EACH action, analyze:
1. Which obligations does it FULFILL? (performing this action satisfies the obligation)
2. Which obligations does it VIOLATE? (performing this action contradicts the obligation)
3. Which principles GUIDE it? (the action is motivated by this principle)
4. Which constraints LIMIT it? (constraints that affect how the action can be performed)
5. Which role PERFORMS this action?
6. Brief reasoning explaining the relationships

Output as JSON array:
```json
[
  {{
    "action_id": "<action_uri>",
    "action_label": "<action_label>",
    "fulfills_obligations": ["<obligation_uri>", ...],
    "violates_obligations": ["<obligation_uri>", ...],
    "guided_by_principles": ["<principle_uri>", ...],
    "constrained_by": ["<constraint_uri>", ...],
    "agent_role": "<role_uri>",
    "reasoning": "Brief explanation of why...",
    "confidence": 0.0-1.0
  }},
  ...
]
```

Include ALL actions even if they have empty relationships. Be precise with URI matching."""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            llm_traces.append(LLMTrace(
                phase=2,
                phase_name="Analytical Extraction",
                stage="Causal-Normative Links",
                prompt=prompt,
                response=response_text,
                model="claude-sonnet-4-20250514"
            ))

            # Parse JSON from response
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                links_data = json.loads(json_match.group(1))

                return [
                    CausalNormativeLink(
                        action_id=link.get('action_id', ''),
                        action_label=link.get('action_label', ''),
                        fulfills_obligations=link.get('fulfills_obligations', []),
                        violates_obligations=link.get('violates_obligations', []),
                        guided_by_principles=link.get('guided_by_principles', []),
                        constrained_by=link.get('constrained_by', []),
                        agent_role=link.get('agent_role'),
                        reasoning=link.get('reasoning', ''),
                        confidence=link.get('confidence', 0.5)
                    )
                    for link in links_data
                ]
            else:
                logger.warning("Could not parse causal-normative links JSON")
                return []

        except Exception as e:
            logger.error(f"Failed to analyze causal-normative links: {e}")
            return []

    def _analyze_question_emergence(
        self,
        questions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[QuestionEmergenceAnalysis]:
        """
        Analyze WHY each ethical question emerged from the case.

        For each question, determines:
        - What events/actions triggered it
        - Which roles are involved
        - What competing obligations create tension
        - A narrative explaining the emergence
        """
        if not questions:
            return []

        # Format questions
        questions_text = "\n".join([
            f"- {q.get('label', 'Q')}: {q.get('text', '')} (URI: {q.get('uri', '')})"
            for q in questions
        ])

        # Format events
        events_text = "\n".join([
            f"- {e.label}: {e.definition or 'No definition'} (URI: {e.uri})"
            for e in foundation.events
        ]) if foundation.events else "No events extracted"

        # Format actions
        actions_text = "\n".join([
            f"- {a.label}: {a.definition or 'No definition'} (URI: {a.uri})"
            for a in foundation.actions
        ]) if foundation.actions else "No actions extracted"

        # Format roles
        roles_text = "\n".join([
            f"- {r.label}: {r.definition or 'No definition'} (URI: {r.uri})"
            for r in foundation.roles
        ])

        # Format obligations
        obligations_text = "\n".join([
            f"- {o.label}: {o.definition or 'No definition'} (URI: {o.uri})"
            for o in foundation.obligations
        ])

        prompt = f"""Analyze WHY each ethical question emerged in this case.

## ETHICAL QUESTIONS (posed to the board)
{questions_text}

## EVENTS (things that happened)
{events_text}

## ACTIONS (things done by agents)
{actions_text}

## ROLES (agents involved)
{roles_text}

## OBLIGATIONS (duties that apply)
{obligations_text}

For EACH question, analyze:
1. What EVENTS triggered this question? (URI list)
2. What ACTIONS triggered this question? (URI list)
3. Which ROLES are involved? (URI list)
4. What COMPETING OBLIGATIONS create the tension? (pairs of obligation URIs that conflict)
5. A 1-2 sentence NARRATIVE explaining why this question emerged

Output as JSON array:
```json
[
  {{
    "question_uri": "<question_uri>",
    "question_text": "<question text>",
    "triggered_by_events": ["<event_uri>", ...],
    "triggered_by_actions": ["<action_uri>", ...],
    "involves_roles": ["<role_uri>", ...],
    "competing_obligations": [["<obl1_uri>", "<obl2_uri>"], ...],
    "emergence_narrative": "This question emerged because...",
    "confidence": 0.0-1.0
  }},
  ...
]
```

Be precise with URI matching. Include all questions."""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            llm_traces.append(LLMTrace(
                phase=2,
                phase_name="Analytical Extraction",
                stage="Question Emergence Analysis",
                prompt=prompt,
                response=response_text,
                model="claude-sonnet-4-20250514"
            ))

            # Parse JSON from response
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                analyses_data = json.loads(json_match.group(1))

                return [
                    QuestionEmergenceAnalysis(
                        question_uri=a.get('question_uri', ''),
                        question_text=a.get('question_text', ''),
                        triggered_by_events=a.get('triggered_by_events', []),
                        triggered_by_actions=a.get('triggered_by_actions', []),
                        involves_roles=a.get('involves_roles', []),
                        competing_obligations=[tuple(pair) for pair in a.get('competing_obligations', [])],
                        emergence_narrative=a.get('emergence_narrative', ''),
                        confidence=a.get('confidence', 0.5)
                    )
                    for a in analyses_data
                ]
            else:
                logger.warning("Could not parse question emergence JSON")
                return []

        except Exception as e:
            logger.error(f"Failed to analyze question emergence: {e}")
            return []

    def _analyze_resolution_patterns(
        self,
        conclusions: List[Dict],
        questions: List[Dict],
        provisions: List[Dict],
        llm_traces: List[LLMTrace]
    ) -> List[ResolutionPatternAnalysis]:
        """
        Analyze HOW the board resolved each ethical question.

        For each conclusion, determines:
        - Which questions it answers
        - What principles were determinative
        - What facts were determinative
        - What provisions were cited
        - How competing obligations were weighed
        - A narrative explaining the resolution
        """
        if not conclusions:
            return []

        # Format conclusions
        conclusions_text = "\n".join([
            f"- {c.get('label', 'C')}: {c.get('text', '')} (URI: {c.get('uri', '')})"
            for c in conclusions
        ])

        # Format questions
        questions_text = "\n".join([
            f"- {q.get('label', 'Q')}: {q.get('text', '')} (URI: {q.get('uri', '')})"
            for q in questions
        ])

        # Format provisions
        provisions_text = "\n".join([
            f"- {p.get('label', 'P')}: {p.get('code', '')} - {p.get('definition', '')[:100]} (URI: {p.get('uri', '')})"
            for p in provisions
        ]) if provisions else "No provisions extracted"

        prompt = f"""Analyze HOW the board resolved each ethical question in their conclusions.

## BOARD CONCLUSIONS (determinations made)
{conclusions_text}

## ETHICAL QUESTIONS (that needed answers)
{questions_text}

## CODE PROVISIONS (that could be cited)
{provisions_text}

For EACH conclusion, analyze:
1. Which QUESTIONS does it answer? (URI list)
2. What PRINCIPLES were determinative? (list of principle names/descriptions)
3. What FACTS were determinative? (list of key facts that influenced the decision)
4. What PROVISIONS were cited? (URI list)
5. How were COMPETING OBLIGATIONS weighed? (description of balancing)
6. A 1-2 sentence NARRATIVE explaining how the board reached this conclusion

Output as JSON array:
```json
[
  {{
    "conclusion_uri": "<conclusion_uri>",
    "conclusion_text": "<conclusion text>",
    "answers_questions": ["<question_uri>", ...],
    "determinative_principles": ["principle name or description", ...],
    "determinative_facts": ["key fact 1", "key fact 2", ...],
    "cited_provisions": ["<provision_uri>", ...],
    "weighing_process": "Description of how competing obligations were balanced...",
    "resolution_narrative": "The board concluded X because...",
    "confidence": 0.0-1.0
  }},
  ...
]
```

Be precise with URI matching. Include all conclusions."""

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text

            llm_traces.append(LLMTrace(
                phase=2,
                phase_name="Analytical Extraction",
                stage="Resolution Pattern Analysis",
                prompt=prompt,
                response=response_text,
                model="claude-sonnet-4-20250514"
            ))

            # Parse JSON from response
            import re
            json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
            if json_match:
                patterns_data = json.loads(json_match.group(1))

                return [
                    ResolutionPatternAnalysis(
                        conclusion_uri=p.get('conclusion_uri', ''),
                        conclusion_text=p.get('conclusion_text', ''),
                        answers_questions=p.get('answers_questions', []),
                        determinative_principles=p.get('determinative_principles', []),
                        determinative_facts=p.get('determinative_facts', []),
                        cited_provisions=p.get('cited_provisions', []),
                        weighing_process=p.get('weighing_process', ''),
                        resolution_narrative=p.get('resolution_narrative', ''),
                        confidence=p.get('confidence', 0.5)
                    )
                    for p in patterns_data
                ]
            else:
                logger.warning("Could not parse resolution patterns JSON")
                return []

        except Exception as e:
            logger.error(f"Failed to analyze resolution patterns: {e}")
            return []

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
                model="claude-sonnet-4-20250514",
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
                model="claude-sonnet-4-20250514"
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
                model="claude-sonnet-4-20250514",
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
                model="claude-sonnet-4-20250514"
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

    def _run_algorithmic_composition(self, case_id: int) -> ComposedDecisionPoints:
        """Run E1-E3 algorithmic composition."""
        return compose_decision_points(case_id, self.domain.name)

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

    def _llm_synthesize(
        self,
        case_id: int,
        candidates: ComposedDecisionPoints,
        questions: List[Dict],
        conclusions: List[Dict],
        entities: Dict[str, List[Dict]]
    ) -> List[CanonicalDecisionPoint]:
        """
        Use LLM to synthesize canonical decision points.

        Takes algorithmic candidates and refines them using Q&C as ground truth.
        """
        if not candidates.decision_points:
            logger.warning("No algorithmic candidates to synthesize")
            return []

        # Format candidates for prompt
        candidates_text = self._format_candidates(candidates)

        # Format Q&C
        qc_text = self._format_qc(questions, conclusions)

        # Format available entities for context
        entities_text = self._format_entities_summary(entities)

        prompt = f"""You are synthesizing canonical decision points for an NSPE ethics case.

## ALGORITHMIC CANDIDATES (from E1-E3 pipeline)

These decision points were composed algorithmically from extracted entities:

{candidates_text}

## BOARD'S QUESTIONS AND CONCLUSIONS (Ground Truth)

These are the actual ethical questions and Board determinations:

{qc_text}

## AVAILABLE ENTITIES

The following entities were extracted from the case and are available for grounding:

{entities_text}

## TASK

Synthesize CANONICAL decision points that:

1. **Align with Board's actual concerns** - Each canonical point should address a real Q&C
2. **Preserve entity grounding** - Keep the URI references from algorithmic candidates
3. **Merge similar candidates** - Combine candidates that address the same ethical issue
4. **Refine descriptions** - Write clear, natural language descriptions

For each canonical decision point, output:
- Whether it maps to an algorithmic candidate (and which one)
- The Q&C it aligns with
- A refined description and decision question
- The entity URIs to preserve

## OUTPUT FORMAT (JSON)

```json
[
  {{
    "focus_id": "CDP1",
    "source_algorithmic_id": "DP1",  // or null if new
    "description": "Clear description of the decision point",
    "decision_question": "The key ethical question to be resolved",
    "aligned_question_index": 0,  // index into questions list, or null
    "aligned_conclusion_index": 0,  // index into conclusions list, or null
    "qc_alignment_reasoning": "Why this maps to that Q&C",
    "role_label": "Engineer A",
    "role_uri": "URI from candidate",
    "obligation_label": "From candidate or null",
    "obligation_uri": "URI or null",
    "constraint_label": "From candidate or null",
    "constraint_uri": "URI or null",
    "provision_labels": ["II.1.c", "II.3.a"],
    "provision_uris": ["URIs from candidate"],
    "involved_action_uris": ["Action URIs from options"],
    "intensity_score": 0.8,
    "options": [
      {{
        "option_id": "O1",
        "description": "Option description",
        "action_uri": "URI if from extracted action",
        "is_board_choice": true
      }}
    ]
  }}
]
```

Produce 3-6 canonical decision points that capture the key ethical issues in this case.
"""

        self.last_prompt = prompt

        try:
            response = self.llm_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                temperature=0.2,
                messages=[{"role": "user", "content": prompt}]
            )

            response_text = response.content[0].text
            self.last_response = response_text

            # Parse response
            canonical = self._parse_synthesis_response(
                response_text, questions, conclusions, candidates
            )

            return canonical

        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            # Fall back to algorithmic candidates converted to canonical format
            return self._convert_algorithmic_to_canonical(candidates, questions, conclusions)

    def _format_candidates(self, candidates: ComposedDecisionPoints) -> str:
        """Format algorithmic candidates for prompt."""
        lines = []
        for dp in candidates.decision_points:
            lines.append(f"""
### {dp.focus_id}: {dp.description}
- Question: {dp.decision_question}
- Role: {dp.grounding.role_label} [{dp.grounding.role_uri}]
- Obligation: {dp.grounding.obligation_label or 'N/A'} [{dp.grounding.obligation_uri or 'N/A'}]
- Constraint: {dp.grounding.constraint_label or 'N/A'} [{dp.grounding.constraint_uri or 'N/A'}]
- Provisions: {', '.join(dp.provision_labels) or 'None'}
- Intensity Score: {dp.intensity_score:.2f}
- Options: {len(dp.options)}
""")
            for opt in dp.options[:3]:  # Limit options shown
                board_mark = " [BOARD CHOICE]" if opt.is_board_choice else ""
                lines.append(f"  - {opt.option_id}: {opt.description}{board_mark}")

        return "\n".join(lines)

    def _format_qc(self, questions: List[Dict], conclusions: List[Dict]) -> str:
        """Format Q&C for prompt."""
        lines = ["### Questions:"]
        for i, q in enumerate(questions):
            lines.append(f"Q{i}: {q['text']}")

        lines.append("\n### Conclusions:")
        for i, c in enumerate(conclusions):
            lines.append(f"C{i}: {c['text']}")

        return "\n".join(lines)

    def _format_entities_summary(self, entities: Dict[str, List[Dict]]) -> str:
        """Format entity summary for context."""
        lines = []
        for etype, elist in entities.items():
            if elist:
                count = len(elist)
                examples = [e['label'] for e in elist[:3]]
                lines.append(f"- {etype}: {count} ({', '.join(examples)}{'...' if count > 3 else ''})")
        return "\n".join(lines)

    def _parse_synthesis_response(
        self,
        response_text: str,
        questions: List[Dict],
        conclusions: List[Dict],
        candidates: ComposedDecisionPoints
    ) -> List[CanonicalDecisionPoint]:
        """Parse LLM synthesis response."""
        import re

        # Extract JSON
        json_match = re.search(r'```json\n(.*?)\n```', response_text, re.DOTALL)
        if not json_match:
            json_match = re.search(r'\[\s*\{.*?\}\s*\]', response_text, re.DOTALL)
            if not json_match:
                logger.warning("Could not find JSON in synthesis response")
                return []

        try:
            json_text = json_match.group(1) if '```json' in response_text else json_match.group(0)
            synthesis_data = json.loads(json_text)

            canonical_points = []
            for i, data in enumerate(synthesis_data, 1):
                # Get aligned Q&C
                q_idx = data.get('aligned_question_index')
                c_idx = data.get('aligned_conclusion_index')

                aligned_q = questions[q_idx] if q_idx is not None and q_idx < len(questions) else None
                aligned_c = conclusions[c_idx] if c_idx is not None and c_idx < len(conclusions) else None

                # Parse options
                options = []
                for opt in data.get('options', []):
                    options.append({
                        'option_id': opt.get('option_id', f'O{len(options)+1}'),
                        'description': opt.get('description', ''),
                        'action_uri': opt.get('action_uri', ''),
                        'is_board_choice': opt.get('is_board_choice', False)
                    })

                canonical = CanonicalDecisionPoint(
                    focus_id=data.get('focus_id', f'CDP{i}'),
                    focus_number=i,
                    description=data.get('description', ''),
                    decision_question=data.get('decision_question', ''),
                    role_uri=data.get('role_uri', ''),
                    role_label=data.get('role_label', ''),
                    obligation_uri=data.get('obligation_uri'),
                    obligation_label=data.get('obligation_label'),
                    constraint_uri=data.get('constraint_uri'),
                    constraint_label=data.get('constraint_label'),
                    involved_action_uris=data.get('involved_action_uris', []),
                    provision_uris=data.get('provision_uris', []),
                    provision_labels=data.get('provision_labels', []),
                    aligned_question_uri=aligned_q['uri'] if aligned_q else None,
                    aligned_question_text=aligned_q['text'] if aligned_q else None,
                    aligned_conclusion_uri=aligned_c['uri'] if aligned_c else None,
                    aligned_conclusion_text=aligned_c['text'] if aligned_c else None,
                    options=options,
                    intensity_score=data.get('intensity_score', 0.0),
                    qc_alignment_score=1.0 if aligned_q else 0.0,
                    source='unified',
                    algorithmic_focus_id=data.get('source_algorithmic_id'),
                    llm_refined_description=data.get('description'),
                    llm_refined_question=data.get('decision_question')
                )
                canonical_points.append(canonical)

            return canonical_points

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse synthesis JSON: {e}")
            return []

    def _convert_algorithmic_to_canonical(
        self,
        candidates: ComposedDecisionPoints,
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> List[CanonicalDecisionPoint]:
        """Convert algorithmic candidates to canonical format (fallback)."""
        canonical_points = []

        for i, dp in enumerate(candidates.decision_points, 1):
            # Try to find matching Q&C
            aligned_q = None
            aligned_c = None

            if dp.board_question_uri:
                for q in questions:
                    if q['uri'] == dp.board_question_uri:
                        aligned_q = q
                        break

            if dp.board_conclusion_uri:
                for c in conclusions:
                    if c['uri'] == dp.board_conclusion_uri:
                        aligned_c = c
                        break

            options = []
            for opt in dp.options:
                options.append({
                    'option_id': opt.option_id,
                    'description': opt.description,
                    'action_uri': opt.action_uri,
                    'is_board_choice': opt.is_board_choice
                })

            canonical = CanonicalDecisionPoint(
                focus_id=f'CDP{i}',
                focus_number=i,
                description=dp.description,
                decision_question=dp.decision_question,
                role_uri=dp.grounding.role_uri,
                role_label=dp.grounding.role_label,
                obligation_uri=dp.grounding.obligation_uri,
                obligation_label=dp.grounding.obligation_label,
                constraint_uri=dp.grounding.constraint_uri,
                constraint_label=dp.grounding.constraint_label,
                involved_action_uris=[opt.action_uri for opt in dp.options if opt.action_uri],
                provision_uris=dp.provision_uris,
                provision_labels=dp.provision_labels,
                aligned_question_uri=aligned_q['uri'] if aligned_q else None,
                aligned_question_text=aligned_q['text'] if aligned_q else None,
                aligned_conclusion_uri=aligned_c['uri'] if aligned_c else None,
                aligned_conclusion_text=aligned_c['text'] if aligned_c else None,
                options=options,
                intensity_score=dp.intensity_score,
                qc_alignment_score=1.0 if aligned_q else 0.0,
                source='algorithmic',
                algorithmic_focus_id=dp.focus_id
            )
            canonical_points.append(canonical)

        return canonical_points

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

    def _save_canonical_points(
        self,
        case_id: int,
        canonical_points: List[CanonicalDecisionPoint],
        extraction_session_id: str
    ) -> int:
        """Save canonical decision points to temporary_rdf_storage."""
        case_ns = PROETHICA_CASE_NS.format(case_id=case_id)
        stored_count = 0

        try:
            # Clear existing canonical decision points
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point',
                is_published=False
            ).delete()

            for dp in canonical_points:
                dp_uri = f"{case_ns}CanonicalDecisionPoint_{dp.focus_id}"

                # Build relationships list
                relationships = []

                # Role relationship
                if dp.role_uri:
                    relationships.append({
                        "type": "proeth:involvesRole",
                        "target_uri": dp.role_uri,
                        "target_label": dp.role_label
                    })

                # Obligation relationship
                if dp.obligation_uri:
                    relationships.append({
                        "type": "proeth:involvesObligation",
                        "target_uri": dp.obligation_uri,
                        "target_label": dp.obligation_label
                    })

                # Constraint relationship
                if dp.constraint_uri:
                    relationships.append({
                        "type": "proeth:involvesConstraint",
                        "target_uri": dp.constraint_uri,
                        "target_label": dp.constraint_label
                    })

                # Q&C alignment relationships
                if dp.aligned_question_uri:
                    relationships.append({
                        "type": "proeth:alignsWithQuestion",
                        "target_uri": dp.aligned_question_uri,
                        "target_label": dp.aligned_question_text[:50] if dp.aligned_question_text else ""
                    })

                if dp.aligned_conclusion_uri:
                    relationships.append({
                        "type": "proeth:alignsWithConclusion",
                        "target_uri": dp.aligned_conclusion_uri,
                        "target_label": dp.aligned_conclusion_text[:50] if dp.aligned_conclusion_text else ""
                    })

                # Provision relationships
                for prov_uri, prov_label in zip(dp.provision_uris, dp.provision_labels):
                    relationships.append({
                        "type": "proeth:appliesProvision",
                        "target_uri": prov_uri,
                        "target_label": prov_label
                    })

                rdf_json_ld = {
                    "@id": dp_uri,
                    "@type": [f"{PROETHICA_INT_NS}CanonicalDecisionPoint"],
                    "label": dp.description,
                    "focus_id": dp.focus_id,
                    "focus_number": dp.focus_number,
                    "decision_question": dp.decision_question,
                    "role_uri": dp.role_uri,
                    "role_label": dp.role_label,
                    "obligation_uri": dp.obligation_uri,
                    "obligation_label": dp.obligation_label,
                    "constraint_uri": dp.constraint_uri,
                    "constraint_label": dp.constraint_label,
                    "aligned_question_uri": dp.aligned_question_uri,
                    "aligned_question_text": dp.aligned_question_text,
                    "aligned_conclusion_uri": dp.aligned_conclusion_uri,
                    "aligned_conclusion_text": dp.aligned_conclusion_text,
                    "provision_uris": dp.provision_uris,
                    "provision_labels": dp.provision_labels,
                    "involved_action_uris": dp.involved_action_uris,
                    "options": dp.options,
                    "intensity_score": dp.intensity_score,
                    "qc_alignment_score": dp.qc_alignment_score,
                    "source": dp.source,
                    "algorithmic_focus_id": dp.algorithmic_focus_id,
                    "properties": {
                        "rdfs:label": dp.description,
                        "proeth:decisionQuestion": dp.decision_question,
                        "proeth:intensityScore": dp.intensity_score,
                        "proeth:qcAlignmentScore": dp.qc_alignment_score
                    },
                    "relationships": relationships
                }

                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=extraction_session_id,
                    extraction_type='canonical_decision_point',
                    storage_type='individual',
                    ontology_target=f'proethica-case-{case_id}',
                    entity_label=dp.description,
                    entity_uri=dp_uri,
                    entity_type='CanonicalDecisionPoint',
                    entity_definition=dp.decision_question,
                    rdf_json_ld=rdf_json_ld,
                    extraction_model='claude-sonnet-4-20250514',
                    triple_count=len(rdf_json_ld["properties"]) + len(relationships) + 2,
                    property_count=len(rdf_json_ld["properties"]),
                    relationship_count=len(relationships),
                    provenance_metadata={
                        'extraction_step': 'unified_synthesis',
                        'focus_id': dp.focus_id,
                        'source': dp.source,
                        'algorithmic_focus_id': dp.algorithmic_focus_id,
                        'qc_aligned': dp.aligned_question_uri is not None
                    },
                    is_selected=True,
                    matched_ontology_uri=f"{PROETHICA_INT_NS}CanonicalDecisionPoint",
                    matched_ontology_label="Canonical Decision Point",
                    match_confidence=1.0,
                    match_method='exact_class'
                )
                db.session.add(entity)
                stored_count += 1

            db.session.commit()
            logger.info(f"Stored {stored_count} canonical decision points for case {case_id}")
            return stored_count

        except Exception as e:
            logger.error(f"Failed to store canonical decision points: {e}")
            db.session.rollback()
            return 0

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
                llm_model='claude-sonnet-4-20250514',
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
