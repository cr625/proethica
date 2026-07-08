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
from app.services.ontserve.ontserve_config import get_ontserve_mcp_url
from model_config import ModelConfig

# E1-E3 Services
from app.services.entity_analysis import (
    compose_decision_points,
    ComposedDecisionPoints,
    EntityGroundedDecisionPoint
)

# MCP Entity Enrichment
from app.services.ontserve.mcp_entity_enrichment_service import (
    enrich_prompt_with_metadata,
    EnrichmentResult
)

from .models import (
    ToulminStructure,
    QCAlignmentScore,
    CanonicalDecisionPoint,
    Phase3SynthesisResult,
    SynthesisTrace,
)
from .strategies import LLMStrategiesMixin

logger = logging.getLogger(__name__)

# Canonical per-case namespace (slash form), matching the commit serializer + edge
# materialisers. Was the divergent ontology/case-<id># hyphen scheme (R2 unification).
PROETHICA_CASE_NS = "http://proethica.org/ontology/case/{case_id}#"


# =============================================================================
# DECISION POINT SYNTHESIZER
# =============================================================================

class DecisionPointSynthesizer(LLMStrategiesMixin):
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
        # HO-005: compact obligation-compliance / capability-proficiency block,
        # populated per-case at the start of synthesize() and appended to each
        # synthesis prompt. None until built.
        self._normative_status_context: Optional[str] = None

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
        # Fresh-architecture temp rows carry no entity_uri (URIs are minted at
        # commit), which left this lookup EMPTY and the fallback conversions
        # unable to bind labels. The committed case graph carries every
        # individual's label and IRI; use it as the backing source
        # (2026-07-08 Decisions analysis).
        try:
            from rdflib import RDFS
            from app.services.entity.committed_case_graph import load_case_graph
            g = load_case_graph(case_id)
            for s, o in g.subject_objects(RDFS.label):
                lookup.setdefault(str(o).lower(), str(s))
        except Exception as exc:  # noqa: BLE001 - no committed TTL yet
            logger.info(f"Case-graph label lookup unavailable for case {case_id}: {exc}")
        return lookup

    def _build_normative_status_context(self, case_id: int) -> str:
        """Build a compact normative-status block for Phase-3 synthesis (HO-005).

        Surfaces obligation ``compliance_status`` and capability
        ``proficiency_level`` from the persisted Step-2 individuals. Both fields
        are extracted, normalized, and stored in ``rdf_json_ld['properties']``
        (as ``complianceStatus`` / ``proficiencyLevel``) but were not previously
        passed to synthesis. Deduplicated by label; capped. Returns '' when
        neither field is present so callers can skip the block.
        """
        def _first(v):
            if isinstance(v, list):
                return v[0] if v else None
            return v

        obl_map = {}
        for o in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='obligations', storage_type='individual'
        ).all():
            props = (o.rdf_json_ld or {}).get('properties', {})
            status = _first(props.get('complianceStatus'))
            if o.entity_label and status:
                obl_map[o.entity_label] = status

        cap_map = {}
        for c in TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='capabilities', storage_type='individual'
        ).all():
            props = (c.rdf_json_ld or {}).get('properties', {})
            level = _first(props.get('proficiencyLevel'))
            # demonstratedThrough is extracted, committed (proeth:demonstratedThrough)
            # and shown on the review page but had no downstream consumer (HO-005
            # audit). Pair the proficiency rating with its textual evidence so the
            # rating is defensible in synthesis, not a bare model judgment. Already
            # stored at extraction -- re-consumed here, no new LLM call. The guard
            # also surfaces evidenced-but-unrated capabilities (the evidence is the
            # useful part); proficiency is rendered only when present (no fallback).
            evidence = _first(props.get('demonstratedThrough'))
            if c.entity_label and (level or evidence):
                cap_map[c.entity_label] = {'level': level, 'evidence': evidence}

        if not obl_map and not cap_map:
            return ''

        sections = [
            "NORMATIVE STATUS (from Step 2 extraction; use to weigh whether duties "
            "were met and whether actors had adequate competence):"
        ]
        if obl_map:
            lines = [f"- {lbl}: compliance={st}" for lbl, st in list(obl_map.items())[:20]]
            sections.append("Obligation compliance:\n" + "\n".join(lines))
        if cap_map:
            lines = []
            for lbl, d in list(cap_map.items())[:20]:
                line = f"- {lbl}: proficiency={d['level']}" if d['level'] else f"- {lbl}:"
                if d['evidence']:
                    line += f" (evidenced by: {d['evidence']})"
                lines.append(line)
            sections.append("Capability proficiency:\n" + "\n".join(lines))
        return "\n\n".join(sections)

    def _append_normative_status(self, prompt: str) -> str:
        """Append the cached normative-status block to a synthesis prompt (HO-005)."""
        block = getattr(self, '_normative_status_context', None)
        return prompt + "\n\n" + block if block else prompt

    @staticmethod
    def _clean_text_formatting(dp: 'CanonicalDecisionPoint') -> None:
        """Clean em dashes and verbose labels on a canonical decision point in-place."""
        import re as _re

        def _strip_em_dashes(text: str) -> str:
            if not text or '\u2014' not in text:
                return text
            text = _re.sub(r'\s*\u2014\s*', ', ', text)
            text = _re.sub(r',\s*,', ',', text)
            text = _re.sub(r',\s*\?', '?', text)
            return text

        def _shorten_role(label: str) -> str:
            if not label or len(label) <= 40:
                return label
            # "Engineer[s] X [and Engineer Y] [verbose description]" -> core name
            m = _re.match(
                r'^(Engineers?\s+[A-Z](?:\s+and\s+Engineers?\s+[A-Z])?)',
                label
            )
            if m:
                return m.group(1)
            # "Firm X ..." -> "Firm X"
            m = _re.match(r'^(Firm\s+[A-Z]+)\s+', label)
            if m:
                return m.group(1)
            # Generic roles with jargon appended
            for role in ('Client', 'Public', 'Employer', 'Owner', 'Contractor'):
                if label.startswith(role + ' '):
                    return role
            # Em dash separator
            if '\u2014' in label:
                return label.split('\u2014')[0].strip()
            return label

        dp.decision_question = _strip_em_dashes(dp.decision_question)
        dp.description = _strip_em_dashes(dp.description)
        dp.role_label = _shorten_role(_strip_em_dashes(dp.role_label))

        if dp.options:
            for opt in dp.options:
                if isinstance(opt, dict):
                    opt['label'] = _strip_em_dashes(opt.get('label', ''))
                    opt['description'] = _strip_em_dashes(opt.get('description', ''))

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

        # HO-005: surface obligation compliance_status / capability proficiency_level
        # (extracted in Step 2, previously dropped) into the synthesis prompts below.
        self._normative_status_context = self._build_normative_status_context(case_id)

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
                        mcp_server_url=get_ontserve_mcp_url()
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
            mcp_server_url=get_ontserve_mcp_url()
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
                    'label': opt.action_label,
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
