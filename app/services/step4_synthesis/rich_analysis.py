"""Rich Analysis Service for Step 4 Phase 2E.

Three LLM-driven analyses that reveal relationships between extracted entities:
1. Causal-Normative Links: How actions relate to obligations/principles
2. Question Emergence: Why ethical questions arose (Toulmin model)
3. Resolution Patterns: How the board resolved each question

Extracted from case_synthesizer.py. Uses label-based prompts (no IRIs) with
mechanical post-parse URI resolution via entity_prompt_utils.
"""

import time
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime

import anthropic
from app import db
from app.models import TemporaryRDFStorage
from app.utils.llm_utils import get_llm_client, streaming_completion
from app.utils.llm_json_utils import parse_json_response
from app.utils.entity_prompt_utils import (
    format_entities_compact, format_subgraph, resolve_labels_flat, _normalize_label,
)
from app.services.prompt_style import STYLE_FORMATTING_LINE
from model_config import ModelConfig

from app.services.step4_synthesis.template_loader import get_step4_template
from app.services.step4_synthesis.case_synthesis_models import (
    EntityFoundation, LLMTrace,
    CausalNormativeLink, QuestionEmergenceAnalysis, ResolutionPatternAnalysis
)

logger = logging.getLogger(__name__)


def validate_against_extracted(labels: List[str], entity_dict: Dict[str, list],
                               context: str = '') -> List[str]:
    """Keep only the labels that name an extracted entity (any of the nine
    categories, normalized label match via resolve_labels_flat). The dropped
    names are logged with their context. A reference that resolves to no
    entity is free text, not a graph edge (case 8 review, finding E)."""
    labels = [l for l in (labels or []) if isinstance(l, str) and l.strip()]
    if not labels:
        return []
    resolved = resolve_labels_flat(labels, entity_dict)
    kept = []
    for label, uri in zip(labels, resolved):
        if uri:
            kept.append(label)
        else:
            logger.info("rich analysis: %r names no extracted entity (%s); dropped",
                        label, context or 'unspecified field')
    return kept


def extracted_normative_labels(entity_dict: Dict[str, list]) -> List[str]:
    """The closed list of principle and obligation labels a pattern may name
    as determinative, in extraction order."""
    from app.utils.entity_prompt_utils import _get_entity_field
    out = []
    for key in ('principles', 'obligations'):
        for e in (entity_dict or {}).get(key, []) or []:
            lbl = _get_entity_field(e, 'label', 'entity_label')
            if lbl and lbl not in out:
                out.append(lbl)
    return out


def _norm_conditions(text: str) -> str:
    import re as _re
    return _re.sub(r"\s+", " ", (text or "").strip().lower().rstrip("."))


def check_resolution_pattern_consistency(patterns, holding_key=None) -> List[str]:
    """Report patterns of the same holding whose resolution_conditions differ.

    The holding of a pattern is its conclusion (``conclusion_uri``); callers may
    pass ``holding_key`` to widen the grouping (for instance a generated
    conclusion mapped to the Board conclusion it extends). Returns one
    human-readable line per conflicting group; never raises and never alters
    the patterns (case 8 review, finding H: two patterns of the same holding
    carried contradictory conditions)."""
    groups: Dict[str, list] = {}
    for p in patterns or []:
        uri = getattr(p, 'conclusion_uri', None) if not isinstance(p, dict) else p.get('conclusion_uri')
        cond = getattr(p, 'resolution_conditions', None) if not isinstance(p, dict) else p.get('resolution_conditions')
        if not uri or not cond:
            continue
        key = holding_key(uri) if holding_key else uri
        groups.setdefault(key or uri, []).append(cond)
    conflicts = []
    for key, conds in groups.items():
        distinct = {}
        for c in conds:
            distinct.setdefault(_norm_conditions(c), c)
        if len(distinct) > 1:
            shown = ' | '.join(v[:120] for v in distinct.values())
            conflicts.append(f"resolution patterns of {key} carry {len(distinct)} different "
                             f"resolution_conditions: {shown}")
    return conflicts


class RichAnalyzer:
    """Performs 2E rich analysis: causal links, question emergence, resolution patterns."""

    BATCH_SIZE = 5

    def __init__(self, llm_client=None):
        self._llm_client = llm_client

    @property
    def llm_client(self):
        if self._llm_client is None:
            self._llm_client = get_llm_client()
        return self._llm_client

    def run_rich_analysis(
        self,
        case_id: int,
        foundation: EntityFoundation,
        provisions: List[Dict],
        questions: List[Dict],
        conclusions: List[Dict]
    ) -> Tuple[List[CausalNormativeLink], List[QuestionEmergenceAnalysis], List[ResolutionPatternAnalysis], List[LLMTrace]]:
        """Run all three rich analysis sub-tasks sequentially.

        For parallel execution, call the individual methods directly
        (as step4_run_all.py does via ThreadPoolExecutor).

        Returns:
            Tuple of (causal_links, question_analyses, resolution_patterns, llm_traces)
        """
        logger.info(f"Phase 2E: Running rich analysis for case {case_id}")
        llm_traces = []

        causal_links = self.analyze_causal_normative_links(foundation, llm_traces)
        logger.info(f"Phase 2E: {len(causal_links)} causal-normative links")

        question_analysis = self.analyze_question_emergence(questions, foundation, llm_traces)
        logger.info(f"Phase 2E: {len(question_analysis)} question emergence patterns")

        resolution_analysis = self.analyze_resolution_patterns(
            conclusions, questions, provisions, foundation, llm_traces
        )
        logger.info(f"Phase 2E: {len(resolution_analysis)} resolution patterns")

        self.store_rich_analysis(case_id, causal_links, question_analysis, resolution_analysis)

        return causal_links, question_analysis, resolution_analysis, llm_traces

    # =========================================================================
    # CAUSAL-NORMATIVE LINKS
    # =========================================================================

    def analyze_causal_normative_links(
        self,
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[CausalNormativeLink]:
        """Analyze which obligations each action fulfills or violates, in batches.

        Batches actions into groups of BATCH_SIZE to avoid truncation.
        Each batch gets the full entity context but only a subset of actions.
        URIs are resolved mechanically after parsing.
        """
        if not foundation.actions:
            return []

        all_results = []
        actions = foundation.actions
        for batch_start in range(0, len(actions), self.BATCH_SIZE):
            batch = actions[batch_start:batch_start + self.BATCH_SIZE]
            batch_results = self._analyze_causal_batch(
                batch, batch_start, foundation, llm_traces
            )
            all_results.extend(batch_results)
        return all_results

    def _committed_action_edges(self, case_id) -> Dict[str, Dict[str, list]]:
        """{normalized_action_label: {'fulfills', 'violates', 'guided', 'agent'}} from the
        committed Step-3 temporal Action rows (obligation_engagement's output). The fulfills /
        violates pair IS the Step-3 causal-normative analysis; grounded synthesis consumes it
        rather than re-deriving it with a fresh LLM call."""
        from app.models.temporary_rdf_storage import TemporaryRDFStorage
        out: Dict[str, Dict[str, list]] = {}
        if not case_id:
            return out
        rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='temporal_dynamics_enhanced', storage_type='individual'
        ).all()

        def _lst(rdf, key):
            v = rdf.get(key)
            return v if isinstance(v, list) else ([v] if v else [])

        for r in rows:
            rdf = r.rdf_json_ld or {}
            if 'Action' not in (rdf.get('@type', '') or ''):
                continue
            agent = rdf.get('proeth:hasAgent')
            if isinstance(agent, list):
                agent = agent[0] if agent else ''
            out[_normalize_label(r.entity_label or '')] = {
                'fulfills': _lst(rdf, 'proeth:fulfillsObligation'),
                'violates': _lst(rdf, 'proeth:violatesObligation'),
                'guided': _lst(rdf, 'proeth:guidedByPrinciple'),
                'agent': agent or '',
            }
        return out

    def _causal_chains_text(self, case_id) -> str:
        """The Step-3 CausalChain rows as 'cause -> effect (responsible: agent)' lines, so the
        normative reasoning is anchored to the Step-3 causal extraction (per the user's
        principle that causal_normative_link comes from the temporal causal component)."""
        from app.models.temporary_rdf_storage import TemporaryRDFStorage
        if not case_id:
            return ""
        rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id, extraction_type='temporal_dynamics_enhanced', storage_type='individual'
        ).all()
        lines = []
        for r in rows:
            rdf = r.rdf_json_ld or {}
            if 'CausalChain' not in (rdf.get('@type', '') or ''):
                continue
            cause = rdf.get('proeth:cause') or rdf.get('proeth:causeText') or ''
            eff = rdf.get('proeth:effect') or rdf.get('proeth:effectText') or ''
            ra = rdf.get('proeth:responsibleAgent') or rdf.get('proeth:responsibleAgentText') or ''
            if cause or eff:
                lines.append(f"  - {cause} -> {eff}" + (f" (responsible: {ra})" if ra else ""))
        return "\n".join(lines)

    def _committed_edges_by_label(self, case_id, entity_dict: Optional[Dict[str, list]] = None) -> Dict[str, list]:
        """{normalized_label: [(predicate, [target_labels]), ...]} of committed edges, for
        format_subgraph. Surfaces the Step-3 action normative edges (fulfills / violates /
        guided-by) so any synthesis prompt that injects the entity context also sees the
        committed normative structure and grounds its analysis in it rather than re-finding it.

        When ``entity_dict`` is given, a target is kept only when it names an extracted
        entity: the Step-3 rows also carry free-text tags ("Opinions Founded on Facts
        Obligation") that are not individuals of the graph, and presenting them under a
        "committed normative edges" heading let the rich-analysis prompt treat them as such
        (case 8 review, finding E). The dropped tags are logged."""
        edges: Dict[str, list] = {}
        for nl, ce in self._committed_action_edges(case_id).items():
            rels = []
            for pred, key in (('fulfills', 'fulfills'), ('violates', 'violates'), ('guided by', 'guided')):
                targets = ce.get(key) or []
                if entity_dict is not None:
                    targets = validate_against_extracted(targets, entity_dict, context=f"{nl} {pred}")
                if targets:
                    rels.append((pred, targets))
            if rels:
                edges[nl] = rels
        return edges

    def _analyze_causal_batch(
        self,
        batch_actions: list,
        batch_offset: int,
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[CausalNormativeLink]:
        """Grounded causal-normative reasoning. The action -> fulfills/violates/guided edges are
        NOT re-derived here: they are taken from the committed Step-3 obligation_engagement
        output and injected as GIVEN, with the Step-3 causal chains. The LLM produces ONLY the
        normative-significance reasoning per action (the irreducible insight)."""
        entity_dict = foundation.to_entity_dict()
        committed = self._committed_action_edges(foundation.case_id)
        causal_text = self._causal_chains_text(foundation.case_id)

        # GIVEN block: each batch action with its committed normative edges.
        # Only references that name an extracted obligation or principle are
        # shown as GIVEN (closed list); a Step-3 free-text tag is not a
        # committed edge (case 8 review, finding E).
        blocks = []
        for i, a in enumerate(batch_actions):
            ce = committed.get(_normalize_label(a.label), {})
            f = '; '.join(validate_against_extracted(ce.get('fulfills', []), entity_dict, f"{a.label} fulfills")) or 'none'
            v = '; '.join(validate_against_extracted(ce.get('violates', []), entity_dict, f"{a.label} violates")) or 'none'
            g = '; '.join(validate_against_extracted(ce.get('guided', []), entity_dict, f"{a.label} guided by")) or 'none'
            blocks.append(f"A{i+1}. {a.label}\n   fulfills: {f}\n   violates: {v}\n   guided by: {g}")
        actions_text = "\n".join(blocks)

        prompt = get_step4_template('step4_causal_reasoning').render(
            actions_text=actions_text,
            causal_text=causal_text,
            action_count=len(batch_actions),
            style_formatting_line=STYLE_FORMATTING_LINE,
        )

        max_retries = 3
        last_error = None
        batch_num = (batch_offset // self.BATCH_SIZE) + 1
        for attempt in range(max_retries):
            try:
                response_text = streaming_completion(
                    self.llm_client,
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=6000,
                    prompt=prompt,
                    temperature=0.2,
                )
                logger.info(f"Causal links batch {batch_num} response: {len(response_text)} chars")

                llm_traces.append(LLMTrace(
                    phase=2,
                    phase_name="Analytical Extraction",
                    stage=f"Causal-Normative Links (batch {batch_num})",
                    prompt=prompt,
                    response=response_text,
                    model=ModelConfig.get_claude_model("default")
                ))

                reasonings = parse_json_response(response_text, f"causal links batch {batch_num}", strict=True) or []
                return self._build_grounded_links(reasonings, batch_actions, committed, entity_dict)

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError, ValueError) as e:  # ValueError = strict-parse failure on a malformed response: retryable nondeterminism (2026-07-10)
                last_error = e
                wait = 2 ** (attempt + 1)
                logger.warning(f"Causal links batch {batch_num} attempt {attempt + 1}/{max_retries} failed (connection): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"Failed to analyze causal links batch {batch_num} (non-retryable): {e}")
                return []

        logger.error(f"Causal links batch {batch_num} failed after {max_retries} retries: {last_error}")
        return []

    def _build_grounded_links(
        self,
        reasonings: List[Dict],
        batch_actions: list,
        committed: Dict[str, Dict[str, list]],
        entity_dict: Dict[str, list],
    ) -> List[CausalNormativeLink]:
        """Build CausalNormativeLinks from the COMMITTED Step-3 edges (fulfills / violates /
        guided / agent) plus the LLM's per-action reasoning. No relation is re-derived here --
        the edges come straight from the temporal extraction; only the reasoning is new."""
        # Index-keyed lookup (the established QE question_index / RP
        # conclusion_index convention): the prompt numbers actions A1..An and
        # asks for action_index back, which is deterministic. Label-echo
        # matching remains only as the legacy fallback -- it silently missed
        # when the model reworded a label (2026-07-10 replay: 3/5 matched;
        # the 2026-07-08 gold run stored reasoning='' on every link).
        reason_by_index = {}
        for d in reasonings:
            if isinstance(d, dict):
                try:
                    reason_by_index[int(d.get('action_index'))] = d
                except (TypeError, ValueError):
                    pass
        reason_by = {_normalize_label(d.get('action_label', '')): d
                     for d in reasonings if isinstance(d, dict) and d.get('action_label')}

        def _resolve(labels, context=''):
            # Resolve each Step-3 obligation/principle label to its case URI. A
            # reference that names no extracted entity is DROPPED (logged): the
            # causal links of case 8 named obligations that do not exist in the
            # graph because the former fallback kept the free-text tag as the
            # reference (case 8 review, finding E / lesson L5). The committed
            # Step-3 text stays on the temporal rows themselves.
            out = []
            for l in validate_against_extracted([x for x in labels if x], entity_dict, context):
                r = resolve_labels_flat([l], entity_dict)
                out.append(r[0] if (r and r[0]) else l)
            return out

        results = []
        for i, a in enumerate(batch_actions):
            nl = _normalize_label(a.label)
            ce = committed.get(nl, {})
            # Index first (deterministic: the prompt numbers actions A1..An),
            # label echo as the legacy fallback.
            rd = reason_by_index.get(i + 1) or reason_by.get(nl, {})
            results.append(CausalNormativeLink(
                action_id=getattr(a, 'uri', '') or '',
                action_label=a.label,
                fulfills_obligations=_resolve(ce.get('fulfills', []), f"{a.label} fulfills"),
                violates_obligations=_resolve(ce.get('violates', []), f"{a.label} violates"),
                guided_by_principles=_resolve(ce.get('guided', []), f"{a.label} guided by"),
                constrained_by=[],  # action->constraint is not a Step-3 edge; left empty (was LLM-guessed before)
                agent_role=ce.get('agent') or None,
                reasoning=rd.get('reasoning', ''),
                confidence=rd.get('confidence', 0.7),
            ))
        return results

    # =========================================================================
    # QUESTION EMERGENCE (Toulmin model)
    # =========================================================================

    def analyze_question_emergence(
        self,
        questions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace],
        facts_text: Optional[str] = None,
    ) -> List[QuestionEmergenceAnalysis]:
        """Analyze WHY each ethical question emerged, in batches of 5."""
        if not questions:
            return []

        if facts_text is None:
            facts_text = self._load_facts_text(foundation.case_id)
        all_results = []
        for batch_start in range(0, len(questions), self.BATCH_SIZE):
            batch = questions[batch_start:batch_start + self.BATCH_SIZE]
            batch_results = self.analyze_question_batch(
                batch, foundation, llm_traces, batch_start, facts_text=facts_text
            )
            all_results.extend(batch_results)
        return all_results

    def _load_facts_text(self, case_id) -> str:
        """The Facts section text of the case ('' when unavailable). The
        emergence prompt received entity labels and question texts but not the
        facts, and inverted the chronology twice on case 8 (lesson L5)."""
        if not case_id:
            return ""
        try:
            from app.models import Document
            case = Document.query.get(case_id)
            sections = ((case.doc_metadata or {}).get('sections_dual', {}) if case else {}) or {}
            facts = sections.get('facts', '')
            return (facts.get('text', '') if isinstance(facts, dict) else str(facts or '')) or ''
        except Exception as exc:  # noqa: BLE001
            logger.info(f"Facts text unavailable for case {case_id}: {exc}")
            return ""

    def analyze_question_batch(
        self,
        questions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace],
        batch_offset: int = 0,
        facts_text: Optional[str] = None,
    ) -> List[QuestionEmergenceAnalysis]:
        """Analyze a batch of questions for emergence patterns.

        Labels-only prompt. Questions are numbered so the LLM can reference
        them by index; URIs and text are assigned programmatically after parse.
        The Facts section rides along as ``facts_text`` so the chronology the
        analysis narrates is the case's, not inferred from labels.
        """
        if not questions:
            return []

        entity_dict = foundation.to_entity_dict()
        # Grounded synthesis: inject the entity subgraph (nodes + committed normative edges)
        # so the question-emergence analysis is anchored to the committed action->obligation
        # structure rather than re-finding it from labels alone.
        entities_text = format_subgraph(
            entity_dict, self._committed_edges_by_label(foundation.case_id, entity_dict))

        if facts_text is None:
            facts_text = self._load_facts_text(foundation.case_id)

        # Number questions for index-based matching
        questions_text = "\n".join([
            f"Q{i+1}. {q.get('label', 'Q')}: {q.get('text', '')}"
            for i, q in enumerate(questions)
        ])

        # Toulmin context
        try:
            from app.academic_references.frameworks.toulmin_argumentation import get_concise_emergence_context
            toulmin_context = get_concise_emergence_context()
        except ImportError:
            toulmin_context = ""

        prompt = get_step4_template('step4_question_emergence').render(
            toulmin_context=toulmin_context,
            questions_text=questions_text,
            entities_text=entities_text,
            facts_text=facts_text or '',
            style_formatting_line=STYLE_FORMATTING_LINE,
        )

        max_retries = 3
        last_error = None
        for attempt in range(max_retries):
            try:
                response_text = streaming_completion(
                    self.llm_client,
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=5000,
                    prompt=prompt,
                    temperature=0.2,
                )
                batch_num = (batch_offset // 5) + 1
                logger.info(f"Question emergence batch {batch_num} response: {len(response_text)} chars")

                llm_traces.append(LLMTrace(
                    phase=2,
                    phase_name="Analytical Extraction",
                    stage=f"Question Emergence (batch {batch_num})",
                    prompt=prompt,
                    response=response_text,
                    model=ModelConfig.get_claude_model("default")
                ))

                analyses_data = parse_json_response(response_text, "question emergence", strict=True)
                if analyses_data:
                    return self._resolve_question_emergence(analyses_data, questions, entity_dict)
                return []

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError, ValueError) as e:  # ValueError = strict-parse failure on a malformed response: retryable nondeterminism (2026-07-10)
                last_error = e
                wait = 2 ** (attempt + 1)
                logger.warning(f"Question emergence attempt {attempt + 1}/{max_retries} failed (connection): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"Failed to analyze question emergence (non-retryable): {e}")
                return []

        logger.error(f"Question emergence failed after {max_retries} retries: {last_error}")
        return []

    def _resolve_question_emergence(
        self,
        analyses_data: List[Dict],
        questions: List[Dict],
        entity_dict: Dict[str, list]
    ) -> List[QuestionEmergenceAnalysis]:
        """Resolve label references and assign question URI/text by index."""
        results = []
        for a in analyses_data:
            # Match question by index (1-based in LLM output)
            q_idx = a.get('question_index', 0) - 1
            if 0 <= q_idx < len(questions):
                q = questions[q_idx]
                question_uri = q.get('uri', '')
                question_text = q.get('text', '')
            else:
                question_uri = ''
                question_text = ''

            # Resolve competing_warrants: list of [label, label] pairs
            resolved_warrants = []
            for pair in a.get('competing_warrants', []):
                if isinstance(pair, (list, tuple)) and len(pair) == 2:
                    resolved_pair = resolve_labels_flat(list(pair), entity_dict)
                    resolved_warrants.append(tuple(resolved_pair))

            results.append(QuestionEmergenceAnalysis(
                question_uri=question_uri,
                question_text=question_text,
                data_events=resolve_labels_flat(a.get('data_events', []), entity_dict),
                data_actions=resolve_labels_flat(a.get('data_actions', []), entity_dict),
                involves_roles=resolve_labels_flat(a.get('involves_roles', []), entity_dict),
                competing_warrants=resolved_warrants,
                data_warrant_tension=a.get('data_warrant_tension', ''),
                competing_claims=a.get('competing_claims', ''),
                rebuttal_conditions=a.get('rebuttal_conditions', ''),
                emergence_narrative=a.get('emergence_narrative', ''),
                confidence=a.get('confidence', 0.5)
            ))
        return results

    # =========================================================================
    # RESOLUTION PATTERNS
    # =========================================================================

    def analyze_resolution_patterns(
        self,
        conclusions: List[Dict],
        questions: List[Dict],
        provisions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[ResolutionPatternAnalysis]:
        """Analyze HOW the board resolved each ethical question, in batches.

        Batches conclusions into groups of BATCH_SIZE to avoid truncation.
        Each batch gets the full questions/provisions context but only a
        subset of conclusions to analyze.

        Note: foundation parameter added vs old signature so entity labels
        can be resolved to URIs. Callers that pass foundation=None will
        skip URI resolution (labels stored as-is).
        """
        if not conclusions:
            return []

        all_results = []
        for batch_start in range(0, len(conclusions), self.BATCH_SIZE):
            batch = conclusions[batch_start:batch_start + self.BATCH_SIZE]
            batch_results = self._analyze_resolution_batch(
                batch, batch_start, conclusions, questions, provisions,
                foundation, llm_traces
            )
            all_results.extend(batch_results)
        return all_results

    def _analyze_resolution_batch(
        self,
        batch_conclusions: List[Dict],
        batch_offset: int,
        all_conclusions: List[Dict],
        questions: List[Dict],
        provisions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[ResolutionPatternAnalysis]:
        """Analyze a batch of conclusions for resolution patterns."""
        entity_dict = foundation.to_entity_dict() if foundation else {}
        # Grounded synthesis: inject the committed normative subgraph so "determinative
        # principles" and "how competing obligations were weighed" are anchored to the
        # extracted action->obligation structure rather than re-identified from the prose.
        norm_structure = (format_subgraph(entity_dict, self._committed_edges_by_label(foundation.case_id, entity_dict))
                          if foundation else "")

        # Number conclusions within this batch (1-based for LLM). Board
        # determinations and Step-4 generated conclusions are rendered as
        # separate blocks: the "BOARD CONCLUSIONS" heading carries only the
        # board_explicit rows and a generated row is tagged with its category,
        # so a pattern cannot say "the Board reasons" about reasoning the Board
        # never gave (case 8 review, finding E / lesson L5). The C-index stays
        # the batch position, which the parser maps back.
        from app.services.step4_synthesis.qc_refs import is_board_explicit, ref_type_label
        board_lines, generated_lines = [], []
        for i, c in enumerate(batch_conclusions):
            if is_board_explicit(c, 'C'):
                board_lines.append(f"C{i+1}. {c.get('label', 'C')}: {c.get('text', '')}")
            else:
                generated_lines.append(
                    f"C{i+1}. [GENERATED {ref_type_label(c, 'C')}, not a Board determination] "
                    f"{c.get('label', 'C')}: {c.get('text', '')}")
        conclusions_text = "\n".join(board_lines) if board_lines else \
            "(none in this batch)" if generated_lines else ""
        generated_conclusions_text = "\n".join(generated_lines)

        # Full questions and provisions context (needed for cross-referencing)
        questions_text = "\n".join([
            f"Q{i+1}. {q.get('label', 'Q')}: {q.get('text', '')}"
            for i, q in enumerate(questions)
        ]) if questions else "No questions extracted"

        provisions_text = "\n".join([
            f"P{i+1}. {p.get('label', 'P')}: {p.get('code', '')} - {p.get('definition', '')[:100]}"
            for i, p in enumerate(provisions)
        ]) if provisions else "No provisions extracted"

        # Closed list for determinative_principles (lesson L5): the extracted
        # principle and obligation labels, the only values the parser keeps.
        principles_text = "\n".join(
            f"- {lbl}" for lbl in extracted_normative_labels(entity_dict))

        prompt = get_step4_template('step4_resolution_patterns').render(
            conclusions_text=conclusions_text,
            generated_conclusions_text=generated_conclusions_text,
            questions_text=questions_text,
            provisions_text=provisions_text,
            principles_text=principles_text,
            norm_structure=norm_structure,
            conclusion_count=len(batch_conclusions),
            style_formatting_line=STYLE_FORMATTING_LINE,
        )

        max_retries = 3
        last_error = None
        batch_num = (batch_offset // self.BATCH_SIZE) + 1
        for attempt in range(max_retries):
            try:
                response_text = streaming_completion(
                    self.llm_client,
                    model=ModelConfig.get_claude_model("default"),
                    max_tokens=6000,
                    prompt=prompt,
                    temperature=0.2,
                )
                logger.info(f"Resolution patterns batch {batch_num} response: {len(response_text)} chars")

                llm_traces.append(LLMTrace(
                    phase=2,
                    phase_name="Analytical Extraction",
                    stage=f"Resolution Patterns (batch {batch_num})",
                    prompt=prompt,
                    response=response_text,
                    model=ModelConfig.get_claude_model("default")
                ))

                patterns_data = parse_json_response(response_text, f"resolution patterns batch {batch_num}", strict=True)
                if patterns_data:
                    return self._resolve_resolution_patterns(
                        patterns_data, batch_conclusions, questions, provisions,
                        entity_dict, batch_offset
                    )
                return []

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError, ValueError) as e:  # ValueError = strict-parse failure on a malformed response: retryable nondeterminism (2026-07-10)
                last_error = e
                wait = 2 ** (attempt + 1)
                logger.warning(f"Resolution patterns batch {batch_num} attempt {attempt + 1}/{max_retries} failed (connection): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"Failed to analyze resolution patterns batch {batch_num} (non-retryable): {e}")
                return []

        logger.error(f"Resolution patterns batch {batch_num} failed after {max_retries} retries: {last_error}")
        return []

    def _resolve_resolution_patterns(
        self,
        patterns_data: List[Dict],
        batch_conclusions: List[Dict],
        questions: List[Dict],
        provisions: List[Dict],
        entity_dict: Dict[str, list],
        batch_offset: int = 0
    ) -> List[ResolutionPatternAnalysis]:
        """Resolve index references and labels to URIs.

        conclusion_index in LLM output is 1-based within the batch.
        """
        results = []
        for p in patterns_data:
            # Match conclusion by index (1-based within batch)
            c_idx = p.get('conclusion_index', 0) - 1
            if 0 <= c_idx < len(batch_conclusions):
                c = batch_conclusions[c_idx]
                conclusion_uri = c.get('uri', '')
                conclusion_text = c.get('text', '')
            else:
                conclusion_uri = ''
                conclusion_text = ''

            # Resolve question references (indices -> URIs)
            # Never serialize '' for a resolved reference: an unresolvable
            # index is dropped, a resolvable one falls back through uri ->
            # code/label (2026-07-08 Q/C analysis, finding 3: empty-string
            # padding in stored resolution patterns).
            answers_q = []
            for q_ref in p.get('answers_questions', []):
                if isinstance(q_ref, int):
                    q_idx = q_ref - 1
                    if 0 <= q_idx < len(questions):
                        val = questions[q_idx].get('uri') or questions[q_idx].get('label', '')
                        if val:
                            answers_q.append(val)
                elif isinstance(q_ref, str) and q_ref:
                    answers_q.append(q_ref)

            # Resolve provision references (indices -> URIs)
            cited_p = []
            for p_ref in p.get('cited_provisions', []):
                if isinstance(p_ref, int):
                    p_idx = p_ref - 1
                    if 0 <= p_idx < len(provisions):
                        val = (provisions[p_idx].get('uri')
                               or provisions[p_idx].get('code')
                               or provisions[p_idx].get('label', ''))
                        if val:
                            cited_p.append(val)
                elif isinstance(p_ref, str) and p_ref:
                    cited_p.append(p_ref)

            # determinative_principles validated against the extracted labels
            # (lesson L5): the other label fields pass through resolve_labels_flat,
            # this one did not, and a case-8 pattern named a principle that was
            # never extracted. Labels are kept (not URIs) so the stored shape is
            # unchanged; an unresolvable name is dropped and logged.
            principles = validate_against_extracted(
                [x for x in (p.get('determinative_principles') or []) if isinstance(x, str)],
                entity_dict, context=f"determinative_principles of {conclusion_uri or 'C?'}",
            ) if entity_dict else list(p.get('determinative_principles') or [])

            results.append(ResolutionPatternAnalysis(
                conclusion_uri=conclusion_uri,
                conclusion_text=conclusion_text,
                answers_questions=answers_q,
                determinative_principles=principles,
                determinative_facts=p.get('determinative_facts', []),
                cited_provisions=cited_p,
                weighing_process=p.get('weighing_process', ''),
                resolution_conditions=p.get('resolution_conditions', ''),
                resolution_narrative=p.get('resolution_narrative', ''),
                confidence=p.get('confidence', 0.5)
            ))
        return results

    # =========================================================================
    # DATABASE PERSISTENCE
    # =========================================================================

    def store_rich_analysis(
        self,
        case_id: int,
        causal_links: List[CausalNormativeLink],
        question_emergence: List[QuestionEmergenceAnalysis],
        resolution_patterns: List[ResolutionPatternAnalysis]
    ) -> None:
        """Store rich analysis results to database.

        Uses TemporaryRDFStorage with extraction_types:
        causal_normative_link, question_emergence, resolution_pattern.
        Clears existing data before storing (replace semantics).
        """
        # Cross-record consistency (lesson L8): two patterns of the same
        # holding must not carry contradictory resolution_conditions. The
        # conflicts are logged here and returned by the checker for audits.
        for conflict in check_resolution_pattern_consistency(resolution_patterns):
            logger.warning("case %s: %s", case_id, conflict)
        try:
            for ext_type in ('causal_normative_link', 'question_emergence', 'resolution_pattern'):
                TemporaryRDFStorage.query.filter_by(
                    case_id=case_id,
                    extraction_type=ext_type
                ).delete(synchronize_session=False)

            session_id = f"rich_analysis_{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            for i, link in enumerate(causal_links):
                entity = TemporaryRDFStorage(
                    case_id=case_id,
                    extraction_session_id=session_id,
                    extraction_type='causal_normative_link',
                    storage_type='individual',
                    entity_type='analysis',
                    # No truncation: this label mints the committed URI, and
                    # the [:30] cap orphaned analyzesAction grounding via
                    # truncated names ('..._Issuanc'; 2026-07-10 audit).
                    entity_label=f"CausalLink_{link.action_label}",
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
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

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
                        'data_events': qa.data_events,
                        'data_actions': qa.data_actions,
                        'involves_roles': qa.involves_roles,
                        'competing_warrants': [list(pair) for pair in qa.competing_warrants],
                        'data_warrant_tension': qa.data_warrant_tension,
                        'competing_claims': qa.competing_claims,
                        'rebuttal_conditions': qa.rebuttal_conditions,
                        'emergence_narrative': qa.emergence_narrative,
                        'confidence': qa.confidence
                    },
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

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
                        'resolution_conditions': rp.resolution_conditions,
                        'resolution_narrative': rp.resolution_narrative,
                        'confidence': rp.confidence
                    },
                    is_selected=True,
                    extraction_model=ModelConfig.get_claude_model("default"),
                    ontology_target=f'proethica-case-{case_id}'
                )
                db.session.add(entity)

            db.session.commit()
            logger.info(f"Stored rich analysis: {len(causal_links)} links, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

        except Exception as e:
            logger.error(f"Failed to store rich analysis: {e}")
            db.session.rollback()

    def load_rich_analysis(
        self,
        case_id: int
    ) -> Tuple[List[CausalNormativeLink], List[QuestionEmergenceAnalysis], List[ResolutionPatternAnalysis]]:
        """Load rich analysis from database.

        Returns:
            Tuple of (causal_links, question_emergence, resolution_patterns)
        """
        causal_links = []
        question_emergence = []
        resolution_patterns = []

        try:
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

            qe_records = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='question_emergence'
            ).all()

            for r in qe_records:
                data = r.rdf_json_ld or {}
                question_emergence.append(QuestionEmergenceAnalysis(
                    question_uri=data.get('question_uri', ''),
                    question_text=data.get('question_text', ''),
                    data_events=data.get('data_events', []),
                    data_actions=data.get('data_actions', []),
                    involves_roles=data.get('involves_roles', []),
                    competing_warrants=[tuple(p) for p in data.get('competing_warrants', [])],
                    data_warrant_tension=data.get('data_warrant_tension', ''),
                    competing_claims=data.get('competing_claims', ''),
                    rebuttal_conditions=data.get('rebuttal_conditions', ''),
                    emergence_narrative=data.get('emergence_narrative', ''),
                    confidence=data.get('confidence', 0.0)
                ))

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
                    resolution_conditions=data.get('resolution_conditions', ''),
                    resolution_narrative=data.get('resolution_narrative', ''),
                    confidence=data.get('confidence', 0.0)
                ))

            logger.info(f"Loaded rich analysis: {len(causal_links)} links, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

        except Exception as e:
            logger.error(f"Failed to load rich analysis: {e}")

        return causal_links, question_emergence, resolution_patterns
