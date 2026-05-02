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

from .enhanced_prompts_defeasibility import (
    NarrativeContext,
    ObligationContext,
    StateContext,
    SYSTEM_PROMPT,
    create_defeasibility_prompt,
)
from .schemas import DefeasibilityEdge, DefeasibilityEdgeExtractionResult

logger = logging.getLogger(__name__)


_VALID_PREDICATES = {"competesWith", "prevailsOver", "defeasibleUnder"}


class DefeasibilityEdgeExtractor:
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
    """

    def __init__(
        self,
        llm_client: Any = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 16384,
    ):
        # Lazy LLM client; mirrors the obligations extractor pattern so the
        # backfill script can supply a pre-built client and the live
        # pipeline can let us fetch one at extract() time.
        self._llm_client = llm_client
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.last_prompt: Optional[str] = None
        self.last_raw_response: Optional[str] = None

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

        raw_response = self._call_llm(prompt)
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
        edges = self._dedupe_edges(edges)

        logger.info(
            "Case %s: emitted %d defeasibility edges (after closure + dedupe)",
            case_id, len(edges),
        )
        return edges

    # ------------------------------------------------------------------
    # LLM invocation
    # ------------------------------------------------------------------

    def _get_client(self):
        if self._llm_client is not None:
            return self._llm_client
        from app.utils.llm_utils import get_llm_client
        self._llm_client = get_llm_client()
        return self._llm_client

    def _resolve_model(self) -> str:
        if self.model:
            return self.model
        from model_config import ModelConfig
        return ModelConfig.get_default_model()

    def _call_llm(self, user_prompt: str) -> Optional[str]:
        """Invoke the configured LLM via Anthropic streaming.

        Streaming is the standard pattern in this codebase: it keeps the
        TCP connection alive past the WSL2 60s idle window and avoids
        the APIConnectionError that non-streaming requests hit when
        generation runs long. We use the system+user split so the
        property axioms in SYSTEM_PROMPT receive Anthropic's higher
        system-prompt treatment.
        """
        client = self._get_client()
        model = self._resolve_model()

        if not (hasattr(client, "messages") and hasattr(client.messages, "stream")):
            logger.error(
                "DefeasibilityEdgeExtractor requires an Anthropic streaming "
                "client; got %s", type(client).__name__,
            )
            return None

        try:
            chunks: List[str] = []
            with client.messages.stream(
                model=model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    chunks.append(text)
                final_msg = stream.get_final_message()
            stop_reason = getattr(final_msg, "stop_reason", None)
            usage = getattr(final_msg, "usage", None)
            if usage:
                logger.info(
                    "Defeasibility stream complete: %d in / %d out, stop=%s",
                    usage.input_tokens, usage.output_tokens, stop_reason,
                )
            if stop_reason == "max_tokens":
                logger.warning(
                    "Defeasibility hit max_tokens (%d); some edges may be lost",
                    self.max_tokens,
                )
            return "".join(chunks)
        except Exception as e:
            logger.error("Anthropic defeasibility stream failed: %s", e)
            return None

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
        contains no further `{` or `}`. We scan for such blocks anywhere
        in the response: this works whether or not the outer "edges"
        array is well-formed, and recovers complete edges that landed
        before the max_tokens cutoff.
        """
        import json as _json
        import re as _re

        edges: List[DefeasibilityEdge] = []
        # Match flat objects: `{ ...no inner braces... }`
        for m in _re.finditer(r"\{[^{}]*\}", raw):
            chunk = m.group(0)
            try:
                obj = _json.loads(chunk)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
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
