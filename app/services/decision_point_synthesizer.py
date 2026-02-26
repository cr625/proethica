"""
Decision Point Synthesizer (Phase 3)

Unified synthesis pipeline that produces canonical decision points from:
1. Algorithmic composition (E1-E3)
2. Q&C alignment scoring
3. LLM refinement with Toulmin structure
4. Storage to database

Reference: docs-internal/PHASE3_DECISION_POINT_SYNTHESIS_PLAN.md
"""

import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict

from app import db
from app.models import TemporaryRDFStorage, ExtractionPrompt
from app.utils.llm_utils import get_llm_client
from app.utils.llm_json_utils import parse_json_response
from app.domains import DomainConfig, get_domain_config
from models import ModelConfig

# E1-E3 Services
from app.services.entity_analysis import (
    compose_decision_points,
    ComposedDecisionPoints,
    EntityGroundedDecisionPoint
)

# MCP Entity Enrichment
from app.services.mcp_entity_enrichment_service import (
    enrich_prompt_with_entities,
    enrich_prompt_with_metadata,
    EnrichmentResult
)

logger = logging.getLogger(__name__)

PROETHICA_CASE_NS = "http://proethica.org/ontology/case-{case_id}#"


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class ToulminStructure:
    """Toulmin argumentation structure for a decision point."""
    data_summary: str = ""           # Summary of triggering facts (DATA)
    warrants_summary: str = ""       # Summary of competing obligations (WARRANTs)
    rebuttals_summary: str = ""      # What creates uncertainty (REBUTTAL)
    backing_provisions: List[str] = field(default_factory=list)  # Code provisions (BACKING)


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


# =============================================================================
# DECISION POINT SYNTHESIZER
# =============================================================================

class DecisionPointSynthesizer:
    """
    Phase 3: Unified Decision Point Synthesis Pipeline

    Four stages:
    3.1: Algorithmic Composition (E1-E3)
    3.2: Q&C Alignment Scoring
    3.3: LLM Refinement
    3.4: Canonical Storage
    """

    def __init__(
        self,
        llm_client=None,
        domain_config: Optional[DomainConfig] = None
    ):
        self._llm_client = llm_client
        self.domain = domain_config or get_domain_config('engineering')

    @property
    def llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def _build_entity_uri_lookup(self, case_id: int) -> Dict[str, str]:
        """Build lowercase-label -> URI lookup from case entities (roles, obligations, constraints).

        Used to resolve LLM-generated labels back to proper extraction URIs.
        """
        lookup = {}
        for etype in ('roles', 'obligations', 'constraints'):
            entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id, extraction_type=etype
            ).all()
            for e in entities:
                if e.entity_label and e.entity_uri:
                    lookup[e.entity_label.lower()] = e.entity_uri
        return lookup

    def synthesize(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict],
        skip_llm: bool = False
    ) -> Phase3SynthesisResult:
        """
        Execute full Phase 3 synthesis pipeline.

        Args:
            case_id: Case to synthesize
            questions: Ethical questions from Phase 2
            conclusions: Board conclusions from Phase 2
            question_emergence: Toulmin analysis of question emergence
            resolution_patterns: Analysis of how board resolved questions
            skip_llm: If True, skip LLM refinement (for testing)

        Returns:
            Phase3SynthesisResult with all stages
        """
        logger.info(f"Phase 3: Starting decision point synthesis for case {case_id}")
        session_id = f"phase3_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        result = Phase3SynthesisResult(
            case_id=case_id,
            extraction_session_id=session_id,
            synthesis_timestamp=datetime.now()
        )

        # Stage 3.1: Algorithmic Composition
        logger.info("Stage 3.1: Running E1-E3 algorithmic composition")
        candidates = self._run_algorithmic_composition(case_id)
        result.algorithmic_candidates = candidates.decision_points
        result.candidates_count = len(candidates.decision_points)
        logger.info(f"Stage 3.1: {result.candidates_count} candidates composed")

        if result.candidates_count == 0:
            if not skip_llm:
                # Fallback 1: try causal_normative_links
                logger.warning("No algorithmic candidates - trying LLM fallback with causal links")
                canonical_points, llm_prompt, llm_response, fallback_enrichment = self._llm_generate_from_causal_links(
                    case_id, questions, conclusions, question_emergence, resolution_patterns
                )

                # Fallback 2: if no causal links, synthesize from Q&C + QE + RP directly
                if not canonical_points:
                    logger.warning("Causal link fallback produced nothing - trying Q&C direct synthesis")
                    canonical_points, llm_prompt, llm_response, fallback_enrichment = self._llm_generate_from_qc_direct(
                        case_id, questions, conclusions, question_emergence, resolution_patterns
                    )
                    fallback_method = "qc_direct_fallback"
                else:
                    fallback_method = "causal_links_fallback"

                if canonical_points:
                    result.canonical_decision_points = canonical_points
                    result.canonical_count = len(canonical_points)
                    result.llm_prompt = llm_prompt
                    result.llm_response = llm_response
                    logger.info(f"LLM fallback ({fallback_method}) generated {result.canonical_count} decision points")

                    fallback_trace = SynthesisTrace(
                        synthesis_started=result.synthesis_timestamp.isoformat() if result.synthesis_timestamp else None,
                        synthesis_completed=datetime.now().isoformat(),
                        algorithmic_candidates_count=0,
                        algorithmic_method=fallback_method,
                        canonical_points_produced=result.canonical_count,
                        llm_model=ModelConfig.get_claude_model("default"),
                        llm_prompt_length=len(llm_prompt),
                        llm_response_length=len(llm_response),
                        mcp_server_url=os.environ.get("ONTSERVE_MCP_URL", "http://localhost:8082")
                    )
                    if fallback_enrichment:
                        fallback_trace.entities_resolved = fallback_enrichment.resolution_log
                        fallback_trace.mcp_resolved_count = fallback_enrichment.mcp_resolved_count
                        fallback_trace.local_resolved_count = fallback_enrichment.local_resolved_count
                        fallback_trace.entities_not_found = fallback_enrichment.not_found_count

                    self._store_canonical_points(case_id, canonical_points, session_id, fallback_trace)
                    return result
            logger.warning("No decision points generated - returning empty result")
            return result

        # Stage 3.2: Q&C Alignment Scoring
        logger.info("Stage 3.2: Scoring candidates against Q&C")
        alignment_scores = self._score_qc_alignment(
            candidates.decision_points,
            questions,
            conclusions,
            question_emergence
        )
        result.alignment_scores = alignment_scores
        result.high_alignment_count = sum(1 for s in alignment_scores if s.total_score > 0.5)
        logger.info(f"Stage 3.2: {result.high_alignment_count}/{len(alignment_scores)} candidates scored > 0.5")

        # Stage 3.3: LLM Refinement
        enrichment_result = None
        if skip_llm:
            logger.info("Stage 3.3: Skipping LLM refinement (skip_llm=True)")
            canonical_points = self._convert_to_canonical_without_llm(
                candidates.decision_points,
                alignment_scores,
                questions,
                conclusions,
                question_emergence,
                resolution_patterns
            )
        else:
            logger.info("Stage 3.3: Running LLM refinement")
            canonical_points, llm_prompt, llm_response, enrichment_result = self._llm_refine(
                case_id,
                candidates.decision_points,
                alignment_scores,
                questions,
                conclusions,
                question_emergence,
                resolution_patterns
            )
            result.llm_prompt = llm_prompt
            result.llm_response = llm_response

        result.canonical_decision_points = canonical_points
        result.canonical_count = len(canonical_points)
        logger.info(f"Stage 3.3: {result.canonical_count} canonical decision points")

        # Build synthesis trace for provenance
        synthesis_trace = SynthesisTrace(
            synthesis_started=result.synthesis_timestamp.isoformat() if result.synthesis_timestamp else None,
            synthesis_completed=datetime.now().isoformat(),
            algorithmic_candidates_count=result.candidates_count,
            high_alignment_count=result.high_alignment_count,
            canonical_points_produced=result.canonical_count,
            llm_model=ModelConfig.get_claude_model("default") if not skip_llm else "",
            llm_prompt_length=len(result.llm_prompt or ""),
            llm_response_length=len(result.llm_response or ""),
            llm_temperature=0.2,
            mcp_server_url=os.environ.get("ONTSERVE_MCP_URL", "http://localhost:8082")
        )

        # Add enrichment info if available
        if enrichment_result:
            synthesis_trace.entities_resolved = enrichment_result.resolution_log
            synthesis_trace.mcp_resolved_count = enrichment_result.mcp_resolved_count
            synthesis_trace.local_resolved_count = enrichment_result.local_resolved_count
            synthesis_trace.entities_not_found = enrichment_result.not_found_count

        # Add top alignment scores summary
        synthesis_trace.alignment_scores_summary = [
            {"candidate_id": s.candidate_id, "score": s.total_score}
            for s in sorted(alignment_scores, key=lambda x: x.total_score, reverse=True)[:5]
        ]

        # Stage 3.4: Storage
        logger.info("Stage 3.4: Storing canonical decision points")
        self._store_canonical_points(case_id, canonical_points, session_id, synthesis_trace)

        logger.info(f"Phase 3 complete: {result.canonical_count} decision points synthesized")
        return result

    # =========================================================================
    # STAGE 3.1: ALGORITHMIC COMPOSITION
    # =========================================================================

    def _run_algorithmic_composition(self, case_id: int) -> ComposedDecisionPoints:
        """Run E1-E3 algorithmic composition."""
        return compose_decision_points(case_id, self.domain.name)

    # =========================================================================
    # STAGE 3.2: Q&C ALIGNMENT SCORING
    # =========================================================================

    def _score_qc_alignment(
        self,
        candidates: List[EntityGroundedDecisionPoint],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict]
    ) -> List[QCAlignmentScore]:
        """
        Score each candidate decision point against board's Q&C.

        Uses Toulmin structure from question emergence:
        - competing_warrants: Obligation pairs creating tension
        - data_events/data_actions: Facts that triggered questions
        - involves_roles: Roles mentioned in questions

        Scoring (0-1 scale):
        - 0.30: Obligation appears in competing_warrants
        - 0.30: Actions appear in data_events/data_actions
        - 0.20: Role appears in question involvement
        - 0.20: Actions match conclusion citations
        """
        scores = []

        # Build lookup structures from question emergence
        warrant_obligations = set()  # All obligations that appear as warrants
        data_actions = set()         # All actions mentioned as data
        data_events = set()          # All events mentioned as data
        involved_roles = set()       # All roles involved in questions

        question_to_warrants = {}    # question_uri -> list of warrant pairs

        for qe in question_emergence:
            q_uri = qe.get('question_uri', '')

            # Collect competing warrants (obligation pairs)
            for warrant_pair in qe.get('competing_warrants', []):
                if isinstance(warrant_pair, (list, tuple)) and len(warrant_pair) >= 2:
                    warrant_obligations.add(warrant_pair[0])
                    warrant_obligations.add(warrant_pair[1])
                    if q_uri not in question_to_warrants:
                        question_to_warrants[q_uri] = []
                    question_to_warrants[q_uri].append(tuple(warrant_pair[:2]))

            # Collect data events and actions
            for action in qe.get('data_actions', []):
                data_actions.add(action.lower() if isinstance(action, str) else str(action))
            for event in qe.get('data_events', []):
                data_events.add(event.lower() if isinstance(event, str) else str(event))

            # Collect involved roles
            for role in qe.get('involves_roles', []):
                involved_roles.add(role.lower() if isinstance(role, str) else str(role))

        # Build conclusion action lookup
        conclusion_actions = set()
        for c in conclusions:
            for action in c.get('cited_actions', []):
                conclusion_actions.add(action.lower() if isinstance(action, str) else str(action))

        # Helper to extract fragment from URI for flexible matching
        def uri_fragment(uri: str) -> str:
            """Extract the fragment/local name from a URI for matching."""
            if '#' in uri:
                return uri.split('#')[-1].lower().replace('_', ' ')
            if '/' in uri:
                return uri.split('/')[-1].lower().replace('_', ' ')
            return uri.lower()

        # Score each candidate
        for candidate in candidates:
            score = QCAlignmentScore(
                candidate_id=candidate.focus_id,
                total_score=0.0
            )

            # 1. Obligation appears in competing warrants (0.30)
            # Compare both URI and label for flexibility
            obl_uri = (candidate.grounding.obligation_uri or '').lower()
            obl_label = (candidate.grounding.obligation_label or '').lower()
            obl_fragment = uri_fragment(obl_uri) if obl_uri else ''

            for warrant_uri in warrant_obligations:
                warrant_lower = warrant_uri.lower()
                warrant_fragment = uri_fragment(warrant_uri)
                # Match by URI, fragment, or label substring
                if (obl_uri and obl_uri == warrant_lower) or \
                   (obl_fragment and obl_fragment == warrant_fragment) or \
                   (obl_label and obl_label in warrant_fragment) or \
                   (obl_label and warrant_fragment in obl_label):
                    score.obligation_warrant_score = 0.30
                    # Track which questions this matches
                    for q_uri, warrants in question_to_warrants.items():
                        for w1, w2 in warrants:
                            w1_frag = uri_fragment(w1)
                            w2_frag = uri_fragment(w2)
                            if (obl_label and (obl_label in w1_frag or obl_label in w2_frag)) or \
                               (obl_fragment and (obl_fragment == w1_frag or obl_fragment == w2_frag)):
                                if q_uri not in score.matched_questions:
                                    score.matched_questions.append(q_uri)
                                score.matched_warrants.append((w1, w2))
                    break

            # 2. Actions appear in data (0.30)
            action_matches = 0
            for opt in candidate.options:
                action_uri = getattr(opt, 'action_uri', '') or ''
                action_label = (getattr(opt, 'action_label', '') or '').lower()
                action_fragment = uri_fragment(action_uri) if action_uri else action_label

                if action_fragment:
                    # Check against data_actions (URIs)
                    for da in data_actions:
                        da_frag = uri_fragment(da)
                        if action_fragment == da_frag or action_label in da_frag or da_frag in action_label:
                            action_matches += 1
                            break
                    # Check against data_events (URIs)
                    for de in data_events:
                        de_frag = uri_fragment(de)
                        if action_fragment == de_frag or action_label in de_frag or de_frag in action_label:
                            action_matches += 1
                            break
            if action_matches > 0:
                score.action_data_score = min(0.30, action_matches * 0.10)

            # 3. Role appears in question involvement (0.20)
            role_uri = getattr(candidate.grounding, 'role_uri', '') or ''
            role_label = (candidate.grounding.role_label or '').lower()
            role_fragment = uri_fragment(role_uri) if role_uri else role_label

            for r in involved_roles:
                r_frag = uri_fragment(r)
                if role_fragment == r_frag or role_label in r_frag or r_frag in role_label:
                    score.role_involvement_score = 0.20
                    break

            # 4. Actions match conclusion citations (0.20)
            for opt in candidate.options:
                action_uri = getattr(opt, 'action_uri', '') or ''
                action_label = (getattr(opt, 'action_label', '') or '').lower()
                action_fragment = uri_fragment(action_uri) if action_uri else action_label

                for ca in conclusion_actions:
                    ca_frag = uri_fragment(ca)
                    if action_fragment == ca_frag or action_label in ca_frag or ca_frag in action_label:
                        score.conclusion_alignment_score = 0.20
                        break
                if score.conclusion_alignment_score > 0:
                    break

            # Calculate total score
            score.total_score = (
                score.obligation_warrant_score +
                score.action_data_score +
                score.role_involvement_score +
                score.conclusion_alignment_score
            )

            scores.append(score)

        # Sort by score descending
        scores.sort(key=lambda s: s.total_score, reverse=True)

        return scores

    # =========================================================================
    # STAGE 3.3: LLM REFINEMENT
    # =========================================================================

    REFINEMENT_BATCH_SIZE = 5

    def _llm_refine(
        self,
        case_id: int,
        candidates: List[EntityGroundedDecisionPoint],
        alignment_scores: List[QCAlignmentScore],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        Use LLM to refine top-scoring candidates into canonical decision points.

        When more than REFINEMENT_BATCH_SIZE candidates qualify, they are split
        into batches and each batch is refined in a separate LLM call. This
        prevents response truncation from exceeding max_tokens.

        Returns:
            Tuple of (canonical_points, prompt, response, enrichment_result)
        """
        # Select top candidates (score > 0.3 or top 8)
        score_map = {s.candidate_id: s for s in alignment_scores}
        top_candidates = []
        for candidate in candidates:
            score = score_map.get(candidate.focus_id)
            if score and (score.total_score > 0.3 or len(top_candidates) < 8):
                top_candidates.append((candidate, score))

        if not top_candidates:
            logger.warning("No candidates passed threshold - using all candidates")
            top_candidates = [(c, score_map.get(c.focus_id, QCAlignmentScore(c.focus_id, 0.0)))
                            for c in candidates[:8]]

        # Batch candidates if there are too many for a single LLM call
        batch_size = self.REFINEMENT_BATCH_SIZE
        if len(top_candidates) <= batch_size:
            batches = [top_candidates]
        else:
            batches = [
                top_candidates[i:i + batch_size]
                for i in range(0, len(top_candidates), batch_size)
            ]
            logger.info(f"Stage 3.3: Splitting {len(top_candidates)} candidates into {len(batches)} batches")

        all_canonical = []
        all_prompts = []
        all_responses = []
        enrichment_result = None

        for batch_idx, batch in enumerate(batches):
            batch_label = f"batch {batch_idx + 1}/{len(batches)}" if len(batches) > 1 else "single batch"

            # Calculate how many decision points this batch should produce
            # Distribute evenly: aim for 2-3 per batch, min 1
            if len(batches) == 1:
                target_count = "4-6"
            else:
                per_batch = max(1, round(len(batch) * 0.5))
                target_count = f"{per_batch}-{per_batch + 1}"

            prompt = self._build_refinement_prompt(
                case_id,
                batch,
                questions,
                conclusions,
                question_emergence,
                resolution_patterns,
                target_count=target_count,
            )

            # Enrich only the first batch prompt (enrichment applies globally)
            if batch_idx == 0:
                try:
                    enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
                    prompt = enrichment_result.enriched_text
                    logger.info(f"Enriched refinement prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                               f"{enrichment_result.local_resolved_count} from local, "
                               f"{enrichment_result.not_found_count} not found")
                except Exception as e:
                    logger.warning(f"MCP enrichment failed, using unenriched prompt: {e}")

            try:
                from app.utils.llm_utils import streaming_completion

                # Retry once on failure (streaming timeout, JSON parse error, etc.)
                response_text = None
                last_error = None
                for attempt in range(2):
                    try:
                        response_text = streaming_completion(
                            self.llm_client,
                            model=ModelConfig.get_claude_model("default"),
                            max_tokens=16000,
                            prompt=prompt,
                            temperature=0.2,
                        )
                        logger.info(f"Stage 3.3 {batch_label} response: {len(response_text)} chars")

                        batch_points = self._parse_refinement_response(
                            response_text,
                            batch,
                            questions,
                            conclusions,
                            question_emergence,
                            resolution_patterns
                        )
                        all_canonical.extend(batch_points)
                        all_prompts.append(prompt)
                        all_responses.append(response_text)
                        last_error = None
                        break
                    except Exception as retry_err:
                        last_error = retry_err
                        if attempt == 0:
                            logger.warning(f"Stage 3.3 {batch_label} attempt 1 failed: {retry_err}, retrying...")
                            continue

                if last_error:
                    raise last_error

            except Exception as e:
                logger.error(f"LLM refinement failed for {batch_label}: {e}")
                # Fall back to algorithmic conversion for this batch only
                batch_candidates = [c for c, _ in batch]
                batch_scores = [s for _, s in batch]
                fallback_points = self._convert_to_canonical_without_llm(
                    batch_candidates, batch_scores, questions, conclusions,
                    question_emergence, resolution_patterns
                )
                all_canonical.extend(fallback_points)
                all_responses.append(f"ERROR: {e}")

        # Renumber focus_ids sequentially across batches
        for i, dp in enumerate(all_canonical, 1):
            dp.focus_id = f"DP{i}"
            dp.focus_number = i

        combined_prompt = "\n---\n".join(all_prompts) if all_prompts else ""
        combined_response = "\n---\n".join(all_responses) if all_responses else ""

        if not all_canonical:
            logger.warning("All batches failed - full algorithmic fallback")
            all_canonical = self._convert_to_canonical_without_llm(
                candidates, alignment_scores, questions, conclusions,
                question_emergence, resolution_patterns
            )

        return all_canonical, combined_prompt, combined_response, enrichment_result

    def _llm_generate_from_causal_links(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        LLM fallback: Generate decision points from causal_normative_links when E1-E3 finds 0 candidates.

        Uses the already-extracted causal links (action-obligation relationships) to generate
        meaningful decision points via LLM.

        Returns:
            Tuple of (canonical_points, prompt, response, enrichment_result)
        """
        logger.info(f"LLM fallback: Loading causal links for case {case_id}")

        # Load causal_normative_links from database
        causal_links = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='causal_normative_link'
        ).all()

        if not causal_links:
            logger.warning("No causal links found for LLM fallback")
            return [], "", "", None

        # Format causal links for the prompt
        causal_links_text = []
        for i, link in enumerate(causal_links):
            link_data = link.rdf_json_ld or {}
            causal_links_text.append(f"""
{i+1}. {link.entity_label}
   - Action: {link_data.get('action_label', link.entity_label)}
   - Obligation: {link_data.get('fulfills_obligations', link_data.get('obligation_label', 'N/A'))}
   - Violates: {link_data.get('violates_obligations', 'N/A')}
   - Description: {link.entity_definition or link_data.get('description', '')}
""")

        # Format questions
        questions_text = []
        for i, q in enumerate(questions[:10]):  # Limit to 10
            questions_text.append(f"Q{i+1}: {q.get('question_text', q.get('text', ''))[:200]}")

        # Format conclusions
        conclusions_text = []
        for i, c in enumerate(conclusions[:10]):  # Limit to 10
            conclusions_text.append(f"C{i+1}: {c.get('conclusion_text', c.get('text', ''))[:200]}")

        prompt = f"""You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The E1-E3 algorithmic composition found no decision point candidates. However, the case analysis has identified
the following CAUSAL-NORMATIVE LINKS (relationships between actions and obligations):

{chr(10).join(causal_links_text)}

ETHICAL QUESTIONS identified in the case:
{chr(10).join(questions_text)}

BOARD CONCLUSIONS:
{chr(10).join(conclusions_text)}

Based on these causal links, generate 3-5 canonical decision points. Each decision point should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question (what choice must be made?)
4. The primary role/agent facing the decision
5. The relevant obligation or constraint
6. 2-3 options available to the decision-maker
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)

CRITICAL: Option descriptions must be ACTION PHRASES (verb form), not policy statements.
- Good: "Disclose AI tool usage to client", "Verify code with subject matter expert"
- Bad: "No disclosure required unless contractually specified", "AI Tool Adoption Strategy"

Return as JSON array:
```json
[
  {{
    "focus_id": "DP1",
    "description": "...",
    "decision_question": "...",
    "role_label": "...",
    "obligation_label": "...",
    "options": [
      {{"label": "Option A", "description": "Disclose X to stakeholders"}},
      {{"label": "Option B", "description": "Do not disclose X"}}
    ],
    "addresses_questions": ["Q1", "Q2"],
    "board_resolution": "The board concluded that... (C1)"
  }}
]
```
"""

        # Enrich prompt with entity definitions from OntServe MCP
        enrichment_result = None
        try:
            enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
            prompt = enrichment_result.enriched_text
            logger.info(f"Enriched causal link prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                       f"{enrichment_result.local_resolved_count} from local, "
                       f"{enrichment_result.not_found_count} not found")
        except Exception as e:
            logger.warning(f"MCP enrichment failed, using unenriched prompt: {e}")

        try:
            from app.utils.llm_utils import streaming_completion
            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                prompt=prompt,
                temperature=0.3,
            )

            # Parse response
            canonical_points = self._parse_causal_link_response(
                response_text, case_id, questions, conclusions
            )

            logger.info(f"LLM fallback generated {len(canonical_points)} decision points")
            return canonical_points, prompt, response_text, enrichment_result

        except Exception as e:
            logger.error(f"LLM fallback failed: {e}")
            return [], prompt, f"ERROR: {e}", enrichment_result

    def _parse_causal_link_response(
        self,
        response_text: str,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> List[CanonicalDecisionPoint]:
        """Parse LLM response from causal link generation."""

        parsed = parse_json_response(
            response_text, "causal link decision points", strict=True
        )
        if not parsed:
            return []

        # Build question/conclusion URI lookup
        q_uri_map = {f"Q{i+1}": q.get('uri', '') for i, q in enumerate(questions)}
        c_uri_map = {f"C{i+1}": c.get('uri', '') for i, c in enumerate(conclusions)}

        # Resolve LLM labels to real extraction URIs
        entity_uri_lookup = self._build_entity_uri_lookup(case_id)

        canonical_points = []
        for i, dp_data in enumerate(parsed):
            # Find aligned question
            addresses = dp_data.get('addresses_questions', [])
            aligned_q_uri = None
            aligned_q_text = None
            if addresses:
                first_q = addresses[0] if isinstance(addresses, list) else addresses
                aligned_q_uri = q_uri_map.get(first_q, '')
                for q in questions:
                    if q.get('uri') == aligned_q_uri:
                        aligned_q_text = q.get('question_text', q.get('text', ''))
                        break

            # Resolve role/obligation labels to proper extraction URIs
            role_label = dp_data.get('role_label', 'Unknown')
            role_uri = entity_uri_lookup.get(role_label.lower(), '') if role_label else ''
            obl_label = dp_data.get('obligation_label')
            obl_uri = entity_uri_lookup.get(obl_label.lower(), '') if obl_label else None

            # Create canonical decision point
            dp = CanonicalDecisionPoint(
                focus_id=dp_data.get('focus_id', f'DP{i+1}'),
                focus_number=i + 1,
                description=dp_data.get('description', ''),
                decision_question=dp_data.get('decision_question', ''),
                role_uri=role_uri,
                role_label=role_label,
                obligation_uri=obl_uri,
                obligation_label=obl_label,
                aligned_question_uri=aligned_q_uri,
                aligned_question_text=aligned_q_text,
                board_resolution=dp_data.get('board_resolution', ''),
                addresses_questions=[q_uri_map.get(q, q) for q in (addresses if isinstance(addresses, list) else [addresses])],
                options=[
                    {'label': opt.get('label', f'Option {j+1}'), 'description': opt.get('description', '')}
                    for j, opt in enumerate(dp_data.get('options', []))
                ],
                intensity_score=0.5,  # Default score for LLM-generated
                qc_alignment_score=0.7  # Higher since LLM explicitly aligned
            )
            canonical_points.append(dp)

        return canonical_points

    def _llm_generate_from_qc_direct(
        self,
        case_id: int,
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> Tuple[List[CanonicalDecisionPoint], str, str, Optional[EnrichmentResult]]:
        """
        Last-resort fallback: Generate decision points directly from Q&C + QE + RP
        when both E1-E3 and causal link fallback produce nothing.

        This path uses the rich analysis data (questions, conclusions, question emergence,
        resolution patterns) plus obligation/role context to synthesize decision points.
        """
        logger.info(f"Q&C direct fallback: Synthesizing decision points for case {case_id}")

        # Load obligations and roles for grounding
        obligations = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='obligations'
        ).all()
        roles = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='roles'
        ).all()

        # Format questions
        questions_text = []
        for i, q in enumerate(questions[:15]):
            q_text = q.get('question_text', q.get('text', ''))
            source = q.get('source', '')
            source_tag = f" [{source}]" if source else ""
            questions_text.append(f"Q{i+1}{source_tag}: {q_text[:250]}")

        # Format conclusions
        conclusions_text = []
        for i, c in enumerate(conclusions[:15]):
            c_text = c.get('conclusion_text', c.get('text', ''))
            source = c.get('source', '')
            source_tag = f" [{source}]" if source else ""
            conclusions_text.append(f"C{i+1}{source_tag}: {c_text[:250]}")

        # Format question emergence (how questions arise)
        qe_text = []
        for i, qe in enumerate(question_emergence[:10]):
            qe_str = qe.get('description', qe.get('text', ''))
            q_ref = qe.get('question_ref', '')
            qe_text.append(f"QE{i+1} (re {q_ref}): {qe_str[:200]}")

        # Format resolution patterns (how board resolved)
        rp_text = []
        for i, rp in enumerate(resolution_patterns[:10]):
            rp_str = rp.get('description', rp.get('text', ''))
            c_ref = rp.get('conclusion_ref', '')
            rp_text.append(f"RP{i+1} (re {c_ref}): {rp_str[:200]}")

        # Format obligations
        obl_text = []
        for i, o in enumerate(obligations[:15]):
            obl_text.append(f"O{i+1}: {o.entity_label} -- {(o.entity_definition or '')[:150]}")

        # Format roles
        role_text = []
        for i, r in enumerate(roles[:10]):
            role_text.append(f"R{i+1}: {r.entity_label}")

        prompt = f"""You are analyzing an ethics case to identify key decision points where ethical choices must be made.

The algorithmic composition and causal link analysis found no decision point candidates for this case.
However, the case has rich analytical data. Synthesize decision points from the following context.

ETHICAL QUESTIONS identified in the case:
{chr(10).join(questions_text)}

BOARD CONCLUSIONS:
{chr(10).join(conclusions_text)}

QUESTION EMERGENCE (how ethical questions arise from case facts):
{chr(10).join(qe_text)}

RESOLUTION PATTERNS (how the board resolved questions):
{chr(10).join(rp_text)}

OBLIGATIONS extracted from the case:
{chr(10).join(obl_text)}

ROLES in the case:
{chr(10).join(role_text)}

Based on this analysis, generate 3-5 canonical decision points. Each should represent
a moment where an agent must choose between actions with ethical implications.

For each decision point, provide:
1. A focus_id (e.g., "DP1", "DP2")
2. A description of the decision situation
3. A decision_question (what choice must be made?)
4. The primary role/agent facing the decision (use exact role labels from above)
5. The relevant obligation (use exact obligation labels from above)
6. 2-3 options available to the decision-maker
7. Which question(s) this addresses (reference Q numbers)
8. How the board resolved it (reference C numbers)

CRITICAL: Option descriptions must be ACTION PHRASES (verb form), not policy statements.
- Good: "Disclose the conflict of interest to the client", "Recuse from the project"
- Bad: "No disclosure required", "Conflict of Interest Policy"

Return as JSON array:
```json
[
  {{
    "focus_id": "DP1",
    "description": "...",
    "decision_question": "...",
    "role_label": "...",
    "obligation_label": "...",
    "options": [
      {{"label": "Option A", "description": "Action phrase here"}},
      {{"label": "Option B", "description": "Alternative action phrase"}}
    ],
    "addresses_questions": ["Q1", "Q2"],
    "board_resolution": "The board concluded that... (C1)"
  }}
]
```
"""

        enrichment_result = None
        try:
            enrichment_result = enrich_prompt_with_metadata(prompt, mode="glossary")
            prompt = enrichment_result.enriched_text
            logger.info(f"Enriched Q&C direct prompt: {enrichment_result.mcp_resolved_count} from MCP, "
                       f"{enrichment_result.local_resolved_count} from local")
        except Exception as e:
            logger.warning(f"MCP enrichment failed: {e}")

        try:
            from app.utils.llm_utils import streaming_completion
            response_text = streaming_completion(
                self.llm_client,
                model=ModelConfig.get_claude_model("default"),
                max_tokens=4000,
                prompt=prompt,
                temperature=0.3,
            )

            # Reuse the same parser as the causal link fallback
            canonical_points = self._parse_causal_link_response(
                response_text, case_id, questions, conclusions
            )

            logger.info(f"Q&C direct fallback generated {len(canonical_points)} decision points")
            return canonical_points, prompt, response_text, enrichment_result

        except Exception as e:
            logger.error(f"Q&C direct fallback failed: {e}")
            return [], prompt, f"ERROR: {e}", enrichment_result

    def _build_refinement_prompt(
        self,
        case_id: int,
        top_candidates: List[Tuple[EntityGroundedDecisionPoint, QCAlignmentScore]],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict],
        target_count: str = "4-6",
    ) -> str:
        """Build LLM prompt for decision point refinement."""

        # Format candidates with scores
        candidates_text = []
        for candidate, score in top_candidates:
            candidates_text.append(f"""
### {candidate.focus_id} (Q&C Alignment: {score.total_score:.2f})
- Description: {candidate.description}
- Question: {candidate.decision_question}
- Role: {candidate.grounding.role_label} [{candidate.grounding.role_uri}]
- Obligation: {candidate.grounding.obligation_label or 'N/A'} [{candidate.grounding.obligation_uri or 'N/A'}]
- Matched Questions: {', '.join(score.matched_questions) or 'None'}
- Options:
""" + "\n".join(
                f"    O{j+1}: {opt.description} [{'chosen' if opt.is_extracted_action else 'alternative'}]"
                for j, opt in enumerate(candidate.options)
            ))


        # Format questions with Toulmin analysis
        qe_map = {qe.get('question_uri', ''): qe for qe in question_emergence}
        questions_text = []
        for i, q in enumerate(questions):
            q_uri = q.get('uri', '')
            qe = qe_map.get(q_uri, {})
            questions_text.append(f"""
Q{i}: {q.get('text', q.get('label', ''))}
  - URI: {q_uri}
  - DATA (triggering facts): {', '.join(qe.get('data_events', []) + qe.get('data_actions', [])) or 'Not analyzed'}
  - WARRANTS (competing obligations): {qe.get('competing_warrants', 'Not analyzed')}
  - REBUTTAL: {qe.get('rebuttal_conditions', 'Not analyzed')[:200] if qe.get('rebuttal_conditions') else 'None'}
""")

        # Format conclusions with resolution patterns
        rp_map = {rp.get('conclusion_uri', ''): rp for rp in resolution_patterns}
        conclusions_text = []
        for i, c in enumerate(conclusions):
            c_uri = c.get('uri', '')
            rp = rp_map.get(c_uri, {})
            conclusions_text.append(f"""
C{i}: {c.get('text', c.get('label', ''))}
  - URI: {c_uri}
  - Determinative Principles: {', '.join(rp.get('determinative_principles', [])) or 'Not analyzed'}
  - Resolution: {rp.get('resolution_narrative', '')[:200] if rp.get('resolution_narrative') else 'Not analyzed'}
""")

        return f"""You are synthesizing decision points for NSPE ethics case {case_id}.

## TOP ALGORITHMIC CANDIDATES (Scored by Q&C Alignment)

These candidates were composed algorithmically from extracted entities and scored against the board's actual questions and conclusions:

{''.join(candidates_text)}

## BOARD'S QUESTIONS (with Toulmin Analysis)

These are the actual ethical questions with their Toulmin structure:

{''.join(questions_text)}

## BOARD'S CONCLUSIONS (with Resolution Patterns)

{''.join(conclusions_text)}

## TASK

Synthesize {target_count} decision points that:

1. **Preserve entity grounding** - Keep URI references from candidates
2. **Align with Q&C** - Each point should address real board concerns
3. **Merge similar candidates** - Combine candidates addressing the same issue
4. **Include Toulmin structure** - Show DATA, WARRANTs, and REBUTTAL for each
5. **Use action-form options** - Options must be verb phrases describing actions

CRITICAL OPTION REQUIREMENTS:

1. Option descriptions must be ACTION PHRASES (verb form), not policy statements.
   - Good: "Disclose AI tool usage to client", "Verify code with subject matter expert"
   - Bad: "No disclosure required unless contractually specified", "AI Tool Adoption Strategy"

2. Each decision point MUST have 2-3 options that represent GENUINELY DEFENSIBLE positions.
   Do NOT create straw-man alternatives. Each option should be an action a reasonable
   professional could plausibly choose given competing pressures (time, cost, client
   relationship, scope of duty, professional judgment).

   - BAD (straw-man negation):
     O1: "Conduct rigorous line-by-line review before sealing"
     O2: "Seal without any verification"
   - GOOD (genuine tension):
     O1: "Conduct full independent technical review of all AI outputs before sealing"
     O2: "Apply standard firm QA protocols to AI outputs at the same level as conventional CAD software"
     O3: "Engage a third-party reviewer with AI expertise for safety-critical elements while applying standard review to remaining outputs"

   The non-board-choice options must represent positions with real justifications
   (efficiency, precedent, scope limitation, competing obligations) -- not simply
   omitting or refusing to perform the ethical action.

## OUTPUT FORMAT (JSON)

```json
[
  {{
    "focus_id": "DP1",
    "source_candidate_ids": ["DP1", "DP3"],
    "description": "Clear description",
    "decision_question": "The key ethical question",
    "role_label": "Engineer A",
    "role_uri": "URI from candidate",
    "obligation_label": "From candidate",
    "obligation_uri": "URI",
    "constraint_label": null,
    "constraint_uri": null,
    "provision_labels": ["II.1.c"],
    "provision_uris": ["URIs"],
    "involved_action_uris": ["action URIs"],
    "toulmin_data": "Summary of triggering facts",
    "toulmin_warrants": "Summary of competing obligations",
    "toulmin_rebuttals": "What creates uncertainty",
    "addresses_questions": ["Q0", "Q1"],
    "board_resolution": "How board resolved this",
    "qc_alignment_score": 0.85,
    "intensity_score": 0.7,
    "options": [
      {{"option_id": "O1", "description": "Proactively disclose AI tool usage and identify AI-generated sections to client before submission", "action_uri": "URI", "is_board_choice": true}},
      {{"option_id": "O2", "description": "Treat AI tool as internal drafting software equivalent to CAD, disclosing only upon direct client inquiry", "action_uri": "URI", "is_board_choice": false}},
      {{"option_id": "O3", "description": "Disclose AI usage in project documentation without separate client notification, following existing firm software disclosure policy", "action_uri": "URI", "is_board_choice": false}}
    ]
  }}
]
```

Produce exactly {target_count} decision points capturing the key ethical issues. Do NOT produce more than the requested count.
"""

    def _parse_refinement_response(
        self,
        response_text: str,
        top_candidates: List[Tuple[EntityGroundedDecisionPoint, QCAlignmentScore]],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> List[CanonicalDecisionPoint]:
        """Parse LLM refinement response into canonical decision points."""

        synthesis_data = parse_json_response(
            response_text, "decision point refinement", strict=False
        )
        if not synthesis_data:
            raise ValueError("No JSON found in LLM refinement response")

        # Build label->URI lookup from algorithmic candidates so we don't
        # trust the LLM's fabricated URIs (e.g. "case-74#Engineer" instead
        # of the real extraction URI).
        entity_uri_lookup = {}  # lowercase label -> URI
        for candidate, _ in top_candidates:
            g = candidate.grounding
            if g.role_label and g.role_uri:
                entity_uri_lookup[g.role_label.lower()] = g.role_uri
            if g.obligation_label and g.obligation_uri:
                entity_uri_lookup[g.obligation_label.lower()] = g.obligation_uri
            if g.constraint_label and g.constraint_uri:
                entity_uri_lookup[g.constraint_label.lower()] = g.constraint_uri

        def _resolve_uri(label: str, llm_uri: str) -> str:
            """Resolve label to real URI via candidate lookup, falling back to LLM URI."""
            if label:
                resolved = entity_uri_lookup.get(label.lower())
                if resolved:
                    return resolved
            return llm_uri

        canonical_points = []
        for i, data in enumerate(synthesis_data, 1):
            # Build Toulmin structure
            toulmin = ToulminStructure(
                data_summary=data.get('toulmin_data', ''),
                warrants_summary=data.get('toulmin_warrants', ''),
                rebuttals_summary=data.get('toulmin_rebuttals', ''),
                backing_provisions=data.get('provision_labels', [])
            )

            # Map question indices to URIs
            addresses_q = []
            for q_ref in data.get('addresses_questions', []):
                if isinstance(q_ref, int) and q_ref < len(questions):
                    addresses_q.append(questions[q_ref].get('uri', ''))
                elif isinstance(q_ref, str):
                    # Could be "Q0", "Q1" format
                    try:
                        idx = int(q_ref.replace('Q', ''))
                        if idx < len(questions):
                            addresses_q.append(questions[idx].get('uri', ''))
                    except ValueError:
                        addresses_q.append(q_ref)  # Already a URI

            # Get primary aligned Q&C
            aligned_q = None
            aligned_c = None
            if addresses_q and questions:
                for q in questions:
                    if q.get('uri') in addresses_q:
                        aligned_q = q
                        break

            canonical = CanonicalDecisionPoint(
                focus_id=data.get('focus_id', f'DP{i}'),
                focus_number=i,
                description=data.get('description', ''),
                decision_question=data.get('decision_question', ''),
                role_uri=_resolve_uri(data.get('role_label', ''), data.get('role_uri', '')),
                role_label=data.get('role_label', ''),
                obligation_uri=_resolve_uri(data.get('obligation_label'), data.get('obligation_uri', '')),
                obligation_label=data.get('obligation_label'),
                constraint_uri=_resolve_uri(data.get('constraint_label'), data.get('constraint_uri', '')),
                constraint_label=data.get('constraint_label'),
                involved_action_uris=data.get('involved_action_uris', []),
                provision_uris=data.get('provision_uris', []),
                provision_labels=data.get('provision_labels', []),
                toulmin=toulmin,
                aligned_question_uri=aligned_q.get('uri') if aligned_q else None,
                aligned_question_text=aligned_q.get('text') if aligned_q else None,
                aligned_conclusion_uri=aligned_c.get('uri') if aligned_c else None,
                aligned_conclusion_text=aligned_c.get('text') if aligned_c else None,
                addresses_questions=addresses_q,
                board_resolution=data.get('board_resolution', ''),
                options=data.get('options', []),
                intensity_score=data.get('intensity_score', 0.0),
                qc_alignment_score=data.get('qc_alignment_score', 0.0),
                source='unified',
                source_candidate_ids=data.get('source_candidate_ids', []),
                synthesis_method='algorithmic+llm',
                llm_refined_description=data.get('description'),
                llm_refined_question=data.get('decision_question')
            )
            canonical_points.append(canonical)

        return canonical_points

    def _convert_to_canonical_without_llm(
        self,
        candidates: List[EntityGroundedDecisionPoint],
        alignment_scores: List[QCAlignmentScore],
        questions: List[Dict],
        conclusions: List[Dict],
        question_emergence: List[Dict],
        resolution_patterns: List[Dict]
    ) -> List[CanonicalDecisionPoint]:
        """Convert algorithmic candidates to canonical format without LLM."""

        score_map = {s.candidate_id: s for s in alignment_scores}
        qe_map = {qe.get('question_uri', ''): qe for qe in question_emergence}

        canonical_points = []
        for i, candidate in enumerate(candidates, 1):
            score = score_map.get(candidate.focus_id, QCAlignmentScore(candidate.focus_id, 0.0))

            # Build Toulmin from matched questions
            toulmin = ToulminStructure(backing_provisions=candidate.provision_labels)
            if score.matched_questions:
                for q_uri in score.matched_questions[:1]:  # Use first matched
                    qe = qe_map.get(q_uri, {})
                    toulmin.data_summary = ', '.join(qe.get('data_events', []) + qe.get('data_actions', []))
                    toulmin.warrants_summary = str(qe.get('competing_warrants', ''))
                    toulmin.rebuttals_summary = qe.get('rebuttal_conditions', '')[:200]

            # Find aligned Q&C
            aligned_q = None
            if score.matched_questions:
                for q in questions:
                    if q.get('uri') in score.matched_questions:
                        aligned_q = q
                        break

            options = []
            for opt in candidate.options:
                options.append({
                    'option_id': opt.option_id,
                    'description': opt.description,
                    'action_uri': opt.action_uri,
                    'is_board_choice': opt.is_board_choice
                })

            canonical = CanonicalDecisionPoint(
                focus_id=f'DP{i}',
                focus_number=i,
                description=candidate.description,
                decision_question=candidate.decision_question,
                role_uri=candidate.grounding.role_uri,
                role_label=candidate.grounding.role_label,
                obligation_uri=candidate.grounding.obligation_uri,
                obligation_label=candidate.grounding.obligation_label,
                constraint_uri=candidate.grounding.constraint_uri,
                constraint_label=candidate.grounding.constraint_label,
                involved_action_uris=[opt.action_uri for opt in candidate.options if opt.action_uri],
                provision_uris=candidate.provision_uris,
                provision_labels=candidate.provision_labels,
                toulmin=toulmin,
                aligned_question_uri=aligned_q.get('uri') if aligned_q else None,
                aligned_question_text=aligned_q.get('text') if aligned_q else None,
                addresses_questions=score.matched_questions,
                options=options,
                intensity_score=candidate.intensity_score,
                qc_alignment_score=score.total_score,
                source='algorithmic',
                source_candidate_ids=[candidate.focus_id],
                synthesis_method='algorithmic_only'
            )
            canonical_points.append(canonical)

        return canonical_points

    # =========================================================================
    # STAGE 3.4: STORAGE
    # =========================================================================

    def _store_canonical_points(
        self,
        case_id: int,
        canonical_points: List[CanonicalDecisionPoint],
        session_id: str,
        synthesis_trace: Optional[SynthesisTrace] = None
    ) -> None:
        """Store canonical decision points to database with provenance."""
        try:
            # Clear existing canonical decision points
            TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point'
            ).delete(synchronize_session=False)

            # Build provenance metadata from synthesis trace
            provenance = synthesis_trace.to_dict() if synthesis_trace else {}

            for dp in canonical_points:
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='canonical_decision_point',
                    storage_type='individual',
                    entity_type='decision_point',
                    entity_label=dp.description[:100],
                    entity_uri=f"{PROETHICA_CASE_NS.format(case_id=case_id)}{dp.focus_id}",
                    entity_definition=dp.decision_question,
                    rdf_json_ld=dp.to_dict(),
                    provenance_metadata=provenance,
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            db.session.commit()
            logger.info(f"Stored {len(canonical_points)} canonical decision points for case {case_id} with provenance")

        except Exception as e:
            logger.error(f"Failed to store canonical decision points: {e}")
            db.session.rollback()
            raise


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def synthesize_decision_points(
    case_id: int,
    questions: List[Dict],
    conclusions: List[Dict],
    question_emergence: List[Dict],
    resolution_patterns: List[Dict],
    domain: str = 'engineering',
    skip_llm: bool = False
) -> Phase3SynthesisResult:
    """
    Convenience function to run Phase 3 decision point synthesis.

    Args:
        case_id: Case to synthesize
        questions: Ethical questions from Phase 2
        conclusions: Board conclusions from Phase 2
        question_emergence: Toulmin analysis from Phase 2B
        resolution_patterns: Resolution analysis from Phase 2B
        domain: Domain configuration name
        skip_llm: If True, skip LLM refinement

    Returns:
        Phase3SynthesisResult with canonical decision points
    """
    synthesizer = DecisionPointSynthesizer(
        domain_config=get_domain_config(domain)
    )
    return synthesizer.synthesize(
        case_id=case_id,
        questions=questions,
        conclusions=conclusions,
        question_emergence=question_emergence,
        resolution_patterns=resolution_patterns,
        skip_llm=skip_llm
    )
