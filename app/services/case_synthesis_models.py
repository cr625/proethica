"""
Data models for Step 4 Case Synthesis.

Extracted from case_synthesizer.py for modularity. All dataclasses used across
the synthesis pipeline: entity foundation, rich analysis results, narrative
elements, LLM traces, and the complete synthesis model.
"""

from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime


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

    def to_entity_dict(self) -> Dict[str, list]:
        """Return 9 entity categories as dict compatible with entity_prompt_utils.

        Unlike to_dict(), this returns EntitySummary objects directly (no
        serialization) and excludes derived relationships. Works with
        format_entities_compact() and resolve_labels_flat() because
        _get_entity_field() handles EntitySummary via getattr().
        """
        return {
            'roles': self.roles, 'states': self.states, 'resources': self.resources,
            'principles': self.principles, 'obligations': self.obligations,
            'constraints': self.constraints, 'capabilities': self.capabilities,
            'actions': self.actions, 'events': self.events,
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
# LLM TRACES AND ANALYSIS RESULTS
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
    """Analysis of WHY an ethical question emerged from the case.

    Based on Toulmin's (1958/2003) argumentation model:
    - Data-Warrant Tension: How facts could trigger multiple warrants
    - Competing Claims: What different conclusions warrants support
    - Rebuttal Conditions: What circumstances create uncertainty
    """
    question_uri: str
    question_text: str
    # Toulmin DATA: facts that created the ethical situation
    data_events: List[str] = field(default_factory=list)
    data_actions: List[str] = field(default_factory=list)
    involves_roles: List[str] = field(default_factory=list)
    # Toulmin WARRANTS: obligations that could apply (competing pairs)
    competing_warrants: List[Tuple[str, str]] = field(default_factory=list)
    # Toulmin analysis
    data_warrant_tension: str = ""   # How DATA could trigger multiple WARRANTs
    competing_claims: str = ""        # What different CLAIMs the warrants support
    rebuttal_conditions: str = ""     # What REBUTTAL conditions create uncertainty
    emergence_narrative: str = ""
    confidence: float = 0.0

    def to_dict(self) -> Dict:
        return {
            'question_uri': self.question_uri,
            'question_text': self.question_text,
            'data_events': self.data_events,
            'data_actions': self.data_actions,
            'involves_roles': self.involves_roles,
            'competing_warrants': [list(t) for t in self.competing_warrants],
            'data_warrant_tension': self.data_warrant_tension,
            'competing_claims': self.competing_claims,
            'rebuttal_conditions': self.rebuttal_conditions,
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


# =============================================================================
# COMPLETE CASE SYNTHESIS MODEL
# =============================================================================

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
    canonical_decision_points: list = field(default_factory=list)
    algorithmic_candidates_count: int = 0

    # Phase 4: Narrative Construction
    narrative: Optional[CaseNarrative] = None  # Legacy format
    phase4_result: Optional[Any] = None  # New Phase4NarrativeResult from narrative pipeline

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
                'qc_aligned': sum(1 for dp in self.canonical_decision_points
                                  if hasattr(dp, 'aligned_question_uri') and dp.aligned_question_uri)
            },
            'narrative': {
                'has_summary': bool(self.narrative and self.narrative.case_summary),
                'timeline_events': len(self.narrative.timeline) if self.narrative else 0,
                'has_scenario_seeds': bool(self.narrative and self.narrative.scenario_seeds)
            },
            'phase4': self.phase4_result.summary() if self.phase4_result else None,
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
            'phase4_result': self.phase4_result.to_dict() if self.phase4_result else None,
            'llm_traces': [t.to_dict() for t in self.llm_traces],
            'summary': self.summary(),
            'synthesis_timestamp': self.synthesis_timestamp.isoformat() if self.synthesis_timestamp else None,
            'extraction_session_id': self.extraction_session_id
        }


# =============================================================================
# SYNTHESIS RESULT (kept for F1-F3 arguments)
# =============================================================================

@dataclass
class SynthesisResult:
    """Complete synthesis output."""
    case_id: int
    canonical_decision_points: list

    # Metadata
    arguments: Optional[Any] = None
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
