"""
Decision Point Synthesizer (Phase 3) -- data contracts.

The dataclasses produced/consumed by the synthesis pipeline, split out of the
former single-file module (mirrors the case_synthesis_models pattern). The
orchestrating class lives in synthesizer.py; the public surface is re-exported
from the package __init__.
"""

from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

from app.services.entity_analysis import EntityGroundedDecisionPoint


@dataclass
class ToulminStructure:
    """Toulmin (1958) argument structure for a decision point -- all six
    categories. The domain mapping (dissertation Ch3): case facts are the
    grounds; obligations/principles, stated as general rules, are the
    warrants; NSPE Code provisions are the backing behind those warrants;
    the claim is the course of action argued for (the Board's choice where
    the Board ruled); the qualifier carries the modal strength or conditions
    the Board attached; the rebuttal is the condition of exception under
    which the warrant would not license the claim, not a generic
    counter-argument."""
    claim: str = ""                  # CLAIM: the course of action argued for
    data_summary: str = ""           # GROUNDS/DATA: case facts appealed to
    warrants_summary: str = ""       # WARRANT(s): rules licensing facts -> claim
    qualifier: str = ""              # QUALIFIER: modal strength / attached conditions
    rebuttals_summary: str = ""      # REBUTTAL: conditions of exception ("unless ...")
    backing_provisions: List[str] = field(default_factory=list)  # BACKING: code provisions


@dataclass
class QCAlignmentScore:
    """Scoring result for a candidate decision point against Q&C."""
    candidate_id: str
    total_score: float

    # Score components
    obligation_warrant_score: float = 0.0  # Obligation appears in competing_warrants
    action_data_score: float = 0.0         # Actions appear in data_events/data_actions
    role_involvement_score: float = 0.0    # Role appears in question involvement
    conclusion_alignment_score: float = 0.0  # Actions match conclusion citations

    # Alignment details
    matched_questions: List[str] = field(default_factory=list)  # Question URIs
    matched_conclusions: List[str] = field(default_factory=list)  # Conclusion URIs
    matched_warrants: List[Tuple[str, str]] = field(default_factory=list)  # Obligation pairs

    def to_dict(self) -> Dict:
        return {
            'candidate_id': self.candidate_id,
            'total_score': self.total_score,
            'obligation_warrant_score': self.obligation_warrant_score,
            'action_data_score': self.action_data_score,
            'role_involvement_score': self.role_involvement_score,
            'conclusion_alignment_score': self.conclusion_alignment_score,
            'matched_questions': self.matched_questions,
            'matched_conclusions': self.matched_conclusions,
            'matched_warrants': [list(w) for w in self.matched_warrants]
        }


@dataclass
class CanonicalDecisionPoint:
    """
    A canonical decision point produced by the unified Phase 3 pipeline.

    Combines algorithmic composition, Q&C alignment, and LLM refinement.
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

    # Toulmin structure (from question emergence analysis)
    toulmin: Optional[ToulminStructure] = None

    # Q&C alignment (ground truth from Phase 2)
    aligned_question_uri: Optional[str] = None
    aligned_question_text: Optional[str] = None
    aligned_conclusion_uri: Optional[str] = None
    aligned_conclusion_text: Optional[str] = None
    addresses_questions: List[str] = field(default_factory=list)  # Multiple Q URIs
    board_resolution: str = ""  # How board resolved

    # Options with action grounding
    options: List[Dict] = field(default_factory=list)

    # Scores
    intensity_score: float = 0.0
    qc_alignment_score: float = 0.0

    # Source tracking
    source: str = "unified"  # 'algorithmic', 'llm', 'unified'
    source_candidate_ids: List[str] = field(default_factory=list)  # Original IDs from E3
    synthesis_method: str = "algorithmic+llm"
    algorithmic_focus_id: Optional[str] = None  # Original focus ID from algorithmic synthesis

    # LLM refinement
    llm_refined_description: Optional[str] = None
    llm_refined_question: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if self.toulmin:
            result['toulmin'] = asdict(self.toulmin)
        return result


@dataclass
class Phase3SynthesisResult:
    """Complete Phase 3 synthesis output."""
    case_id: int

    # Stage results
    algorithmic_candidates: List[EntityGroundedDecisionPoint] = field(default_factory=list)
    alignment_scores: List[QCAlignmentScore] = field(default_factory=list)
    canonical_decision_points: List[CanonicalDecisionPoint] = field(default_factory=list)

    # Counts
    candidates_count: int = 0
    high_alignment_count: int = 0  # Score > 0.5
    canonical_count: int = 0

    # Provenance
    extraction_session_id: Optional[str] = None
    synthesis_timestamp: Optional[datetime] = None
    llm_prompt: Optional[str] = None
    llm_response: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'case_id': self.case_id,
            'algorithmic_candidates': [c.to_dict() for c in self.algorithmic_candidates],
            'alignment_scores': [s.to_dict() for s in self.alignment_scores],
            'canonical_decision_points': [dp.to_dict() for dp in self.canonical_decision_points],
            'candidates_count': self.candidates_count,
            'high_alignment_count': self.high_alignment_count,
            'canonical_count': self.canonical_count,
            'extraction_session_id': self.extraction_session_id,
            'synthesis_timestamp': self.synthesis_timestamp.isoformat() if self.synthesis_timestamp else None
        }


@dataclass
class SynthesisTrace:
    """
    Detailed provenance trace for a decision point synthesis.

    Captures the full reasoning path including:
    - Entity resolution via MCP/local
    - Algorithmic composition results
    - LLM refinement interaction
    """
    # Timestamps
    synthesis_started: Optional[str] = None
    synthesis_completed: Optional[str] = None

    # Entity Resolution (MCP enrichment)
    entities_resolved: List[Dict] = field(default_factory=list)  # Resolution log
    mcp_resolved_count: int = 0
    local_resolved_count: int = 0
    entities_not_found: int = 0
    mcp_server_url: str = ""

    # Stage 3.1: Algorithmic Composition
    algorithmic_candidates_count: int = 0
    algorithmic_method: str = "E1-E3"

    # Stage 3.2: Q&C Alignment
    alignment_scores_summary: List[Dict] = field(default_factory=list)  # Top scores
    high_alignment_count: int = 0

    # Stage 3.3: LLM Refinement
    llm_model: str = ""
    llm_prompt_length: int = 0
    llm_response_length: int = 0
    llm_temperature: float = 0.2

    # Stage 3.4: Output
    canonical_points_produced: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            'synthesis_started': self.synthesis_started,
            'synthesis_completed': self.synthesis_completed,
            'entity_resolution': {
                'entities_resolved': self.entities_resolved,
                'mcp_resolved_count': self.mcp_resolved_count,
                'local_resolved_count': self.local_resolved_count,
                'entities_not_found': self.entities_not_found,
                'mcp_server_url': self.mcp_server_url
            },
            'algorithmic_composition': {
                'candidates_count': self.algorithmic_candidates_count,
                'method': self.algorithmic_method
            },
            'qc_alignment': {
                'top_scores': self.alignment_scores_summary,
                'high_alignment_count': self.high_alignment_count
            },
            'llm_refinement': {
                'model': self.llm_model,
                'prompt_length': self.llm_prompt_length,
                'response_length': self.llm_response_length,
                'temperature': self.llm_temperature
            },
            'output': {
                'canonical_points_produced': self.canonical_points_produced
            }
        }
