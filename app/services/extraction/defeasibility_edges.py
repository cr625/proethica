"""
Defeasibility edge extractor.

Emits proethica-core v2.5.0 object-property triples
(competesWith, prevailsOver, defeasibleUnder) between previously-extracted
Obligation and State individuals. Unlike the nine concept extractors, this
module does not emit individuals -- only IRI-valued edges between them.

Symmetric closure of competesWith is added in code (Phase A6 of the
defeasibility-edge-extraction plan): the LLM emits one direction; the
extractor emits the inverse. This is necessary because OWL-DL
owl:SymmetricProperty does NOT materialize the inverse triple on disk,
which means SPARQL queries matching on the subject position would
otherwise miss half the edges.

Reference: proethica/.claude/plans/defeasibility-edge-extraction.md Phase A1.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .edge_extractor_base import StreamingEdgeExtractor
from .enhanced_prompts_defeasibility import (
    NarrativeContext,
    ObligationContext,
    StateContext,
    create_defeasibility_prompt,
    defeasibility_system_prompt,
)
from .schemas import DefeasibilityEdge, DefeasibilityEdgeExtractionResult

logger = logging.getLogger(__name__)


_VALID_PREDICATES = {"competesWith", "prevailsOver", "defeasibleUnder"}


class DefeasibilityEdgeExtractor(StreamingEdgeExtractor):
    """LLM-backed extractor for defeasibility edges.

    The extractor takes already-extracted Obligation and State individuals
    (with their IRIs and key narrative fields) plus optional narrative
    context from related entities (Principles, Constraints), and asks the
    LLM to propose object-property triples drawn exclusively from the
    supplied IRIs.

    The output is a list of `DefeasibilityEdge` Pydantic models. Edges
    referencing IRIs not present in the input lists are dropped with a
    warning. competesWith inverse triples are added in
    `_close_symmetric_competesWith`.

    LLM plumbing (client, model resolution, streaming, truncation recovery)
    lives in `StreamingEdgeExtractor`; this class supplies the system prompt
    and the defeasibility-specific parse/filter/closure/dedupe.
    """

    log_label = "Defeasibility"
    # 32000 = the edge-extractor family convention (rpo uses the same). The
    # former 16384 shared the budget with the default tier's thinking spend,
    # so a narrative-heavy case could exhaust the cap before or mid-output --
    # batch-3 case 84 hit max_tokens with an unsalvageable stream and
    # committed ZERO defeasibility edges on a resolved-conflict holding.
    default_max_tokens = 32000

    def _default_model(self) -> str:
        """The ratified model split (2026-07-01) places the defeasibility
        extractor on the DEFAULT tier alongside the other mechanical edge
        passes. The StreamingEdgeExtractor base pins un-pinned extractors to
        the powerful tier, which run 21 showed deterministically judging zero
        edges on this prompt (F2a); the default tier is the intended
        assignment. Explicit override here rather than a base change so RPO
        keeps its powerful-tier default."""
        from model_config import ModelConfig
        return ModelConfig.get_claude_model("default")

    def _system_prompt(self) -> str:
        return defeasibility_system_prompt()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract(
        self,
        case_id: int,
        obligations: List[ObligationContext],
        states: List[StateContext],
        additional_narratives: Optional[List[NarrativeContext]] = None,
    ) -> List[DefeasibilityEdge]:
        """Extract defeasibility edges for one case.

        Returns an empty list when:
          - there are fewer than two obligations (no competition possible),
          - the LLM returns no edges, or
          - every edge produced fails IRI validation.
        """
        if len(obligations) < 2:
            logger.info(
                "Case %s: skipping defeasibility extraction (only %d obligations)",
                case_id, len(obligations),
            )
            return []

        prompt = create_defeasibility_prompt(
            obligations=obligations,
            states=states,
            additional_narratives=additional_narratives,
            case_id=case_id,
        )
        self.last_prompt = prompt

        raw_response = self._stream_llm(prompt)
        self.last_raw_response = raw_response
        if not raw_response:
            logger.warning("Case %s: defeasibility LLM returned no response", case_id)
            return []

        edges = self._parse_edges(raw_response)
        if not edges:
            return []

        valid_obligation_iris = {ob.iri for ob in obligations}
        valid_state_iris = {st.iri for st in states}
        edges = self._filter_invalid_edges(
            edges, valid_obligation_iris, valid_state_iris, case_id
        )

        edges = self._close_symmetric_competesWith(edges)
        edges = self._enforce_joint_emission(edges, case_id)
        edges = self._dedupe_edges(edges)
        self._warn_met_losers(edges, obligations, case_id)

        logger.info(
            "Case %s: emitted %d defeasibility edges (after closure + dedupe)",
            case_id, len(edges),
        )
        return edges

    # ------------------------------------------------------------------
    # Parsing + validation
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_edges(raw: str) -> List[DefeasibilityEdge]:
        """Parse the LLM JSON response into DefeasibilityEdge models.

        Falls back to per-object recovery when the response is truncated
        (e.g. max_tokens cut off the final edge mid-string). Each
        well-formed `{ ... }` chunk inside the response is tried as a
        candidate edge; chunks that fail to parse are dropped.
        """
        from app.utils.llm_utils import extract_json_from_response

        try:
            data = extract_json_from_response(raw)
        except ValueError as e:
            logger.warning(
                "Defeasibility full-JSON parse failed (%s); attempting "
                "per-edge recovery from possibly truncated response", e,
            )
            return DefeasibilityEdgeExtractor._recover_partial_edges(raw)

        # Tolerate either {edges: [...]} or a bare array.
        edge_dicts: List[Dict[str, Any]]
        if isinstance(data, dict) and isinstance(data.get("edges"), list):
            edge_dicts = data["edges"]
        elif isinstance(data, list):
            edge_dicts = data
        else:
            logger.warning(
                "Defeasibility response did not contain an edges array: %r",
                type(data).__name__,
            )
            return []

        try:
            result = DefeasibilityEdgeExtractionResult(edges=edge_dicts)
            return list(result.edges)
        except Exception as e:
            # Fall back to per-edge validation so one bad row does not
            # discard the whole batch.
            logger.warning(
                "Defeasibility batch validation failed (%s); "
                "trying per-edge validation",
                e,
            )
            edges: List[DefeasibilityEdge] = []
            for i, ed in enumerate(edge_dicts):
                try:
                    edges.append(DefeasibilityEdge(**ed))
                except Exception as inner_e:
                    logger.warning(
                        "  defeasibility edge[%d] discarded: %s (data=%r)",
                        i, inner_e, ed,
                    )
            return edges

    @staticmethod
    def _recover_partial_edges(raw: str) -> List[DefeasibilityEdge]:
        """Salvage edges from a truncated or pre-/post-fixed JSON response.

        Defeasibility edges have flat structure (no nested objects in
        values), so each edge is a minimal `{ ... }` block whose body
        contains no further `{` or `}`. The shared scan in
        `StreamingEdgeExtractor._iter_flat_json_objects` finds such blocks
        anywhere in the response (whether or not the outer "edges" array is
        well-formed), recovering complete edges that landed before the
        max_tokens cutoff.
        """
        edges: List[DefeasibilityEdge] = []
        for obj in StreamingEdgeExtractor._iter_flat_json_objects(raw):
            if "predicate" not in obj or "subject_iri" not in obj:
                continue
            try:
                edges.append(DefeasibilityEdge(**obj))
            except Exception as e:
                logger.debug("  recovered chunk failed validation: %s", e)
        if edges:
            logger.info(
                "Defeasibility partial-recovery salvaged %d edge(s) "
                "from truncated response", len(edges),
            )
        return edges

    @staticmethod
    def _filter_invalid_edges(
        edges: List[DefeasibilityEdge],
        valid_obligation_iris: Set[str],
        valid_state_iris: Set[str],
        case_id: int,
    ) -> List[DefeasibilityEdge]:
        """Drop edges whose IRIs do not appear in the input entity lists.

        This is the IRI-fabrication guard. The prompt forbids invented
        IRIs but the LLM occasionally rewrites fragments (e.g.
        normalizing em-dashes); we silently drop those rather than
        emit dangling triples.
        """
        kept: List[DefeasibilityEdge] = []
        for ed in edges:
            if ed.predicate not in _VALID_PREDICATES:
                logger.warning(
                    "Case %s: dropped edge with invalid predicate %r",
                    case_id, ed.predicate,
                )
                continue

            if ed.subject_iri not in valid_obligation_iris:
                logger.warning(
                    "Case %s: dropped %s edge -- subject IRI not in obligations: %r",
                    case_id, ed.predicate, ed.subject_iri,
                )
                continue

            if ed.predicate == "defeasibleUnder":
                if ed.object_iri not in valid_state_iris:
                    logger.warning(
                        "Case %s: dropped defeasibleUnder edge -- object IRI not "
                        "in states: %r",
                        case_id, ed.object_iri,
                    )
                    continue
            else:
                if ed.object_iri not in valid_obligation_iris:
                    logger.warning(
                        "Case %s: dropped %s edge -- object IRI not in obligations: %r",
                        case_id, ed.predicate, ed.object_iri,
                    )
                    continue

            kept.append(ed)
        return kept

    @staticmethod
    def _warn_met_losers(edges, obligations, case_id: int) -> None:
        """Specification-vs-defeat review signal (2026-07-08 rubric tightening).

        A duty the board found SATISFIED was presumptively not subordinated: a
        prevailsOver edge whose loser has compliancestatus met (or a
        defeasibleUnder edge on a met obligation) usually means the extractor
        cast scope-specification as defeat (the case-9 Competence-over-
        PublicSafety mismodel). Warn-only, never drop: the discharged-then-
        superseded pattern (case 8) legitimately pairs met with yielding, so
        the call needs a human or the prompt-side rubric, not a hard guard.
        """
        status = {
            ob.iri: (ob.compliance_status or "").strip().lower()
            for ob in obligations
        }
        for e in edges:
            flagged = (
                e.object_iri if e.predicate == "prevailsOver"
                else e.subject_iri if e.predicate == "defeasibleUnder"
                else None
            )
            if flagged and status.get(flagged) == "met":
                logger.warning(
                    "Case %s: %s edge against a compliancestatus=met obligation "
                    "(review for specification-cast-as-defeat): %s",
                    case_id, e.predicate, flagged,
                )

    @staticmethod
    def _enforce_joint_emission(
        edges: List[DefeasibilityEdge],
        case_id: int,
    ) -> List[DefeasibilityEdge]:
        """Joint-emission invariant (2026-07-08 defeasibility view review).

        defeasibleUnder records the State under which an obligation yields to a
        COMPETING obligation -- the core property definition presupposes the
        competitor -- so a defeasibleUnder edge is kept only when its subject
        obligation participates in at least one competesWith or prevailsOver
        edge in the same extraction. The prompt asks the LLM to name the
        competition first; a drop here means the model asserted yielding
        without any recorded tension, which is exactly the pattern this
        invariant exists to prevent (9 of 15 gold cases carried defeasibleUnder
        edges with no competition structure at all).
        """
        engaged: Set[str] = set()
        for e in edges:
            if e.predicate in ("competesWith", "prevailsOver"):
                engaged.add(e.subject_iri)
                engaged.add(e.object_iri)
        kept: List[DefeasibilityEdge] = []
        for e in edges:
            if e.predicate == "defeasibleUnder" and e.subject_iri not in engaged:
                logger.warning(
                    "Case %s: dropped defeasibleUnder edge -- subject has no "
                    "competesWith/prevailsOver in this extraction "
                    "(joint-emission invariant): %r",
                    case_id, e.subject_iri,
                )
                continue
            kept.append(e)
        return kept

    # ------------------------------------------------------------------
    # Symmetric closure + dedupe
    # ------------------------------------------------------------------

    @staticmethod
    def _close_symmetric_competesWith(
        edges: List[DefeasibilityEdge],
    ) -> List[DefeasibilityEdge]:
        """For each (A competesWith B) emit (B competesWith A) if absent.

        owl:SymmetricProperty is asserted in the core ontology, but RDF
        graphs do not materialize the inverse on disk. We materialize it
        here so SPARQL queries that match on the subject position see
        both endpoints of every competition pair. The PROV-O provenance
        of the inverse points back to the same source quote.
        """
        existing: Set[Tuple[str, str]] = {
            (e.subject_iri, e.object_iri)
            for e in edges
            if e.predicate == "competesWith"
        }
        closure: List[DefeasibilityEdge] = []
        for e in edges:
            if e.predicate != "competesWith":
                continue
            inverse_key = (e.object_iri, e.subject_iri)
            if inverse_key in existing:
                continue
            closure.append(
                DefeasibilityEdge(
                    predicate="competesWith",
                    subject_iri=e.object_iri,
                    object_iri=e.subject_iri,
                    source_field=e.source_field,
                    source_text=e.source_text,
                    confidence=e.confidence,
                    source_individual_iri=e.source_individual_iri,
                )
            )
            existing.add(inverse_key)
        return list(edges) + closure

    @staticmethod
    def _dedupe_edges(edges: List[DefeasibilityEdge]) -> List[DefeasibilityEdge]:
        """Drop duplicate (predicate, subject, object) triples.

        Keeps the highest-confidence instance when duplicates exist. Used
        in case the LLM emits the same edge multiple times under different
        source fields.
        """
        best: Dict[Tuple[str, str, str], DefeasibilityEdge] = {}
        for e in edges:
            key = (e.predicate, e.subject_iri, e.object_iri)
            current = best.get(key)
            if current is None or e.confidence > current.confidence:
                best[key] = e
        return list(best.values())
