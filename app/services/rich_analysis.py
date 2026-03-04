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
from app.utils.entity_prompt_utils import format_entities_compact, resolve_labels_flat
from model_config import ModelConfig

from app.services.case_synthesis_models import (
    EntityFoundation, LLMTrace,
    CausalNormativeLink, QuestionEmergenceAnalysis, ResolutionPatternAnalysis
)

logger = logging.getLogger(__name__)


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

    def _analyze_causal_batch(
        self,
        batch_actions: list,
        batch_offset: int,
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[CausalNormativeLink]:
        """Analyze a batch of actions for causal-normative links."""
        entity_dict = foundation.to_entity_dict()
        entities_text = format_entities_compact(entity_dict)

        # List only the batch actions for analysis
        actions_text = "\n".join([
            f"A{i+1}. {a.label}: {a.definition or 'No definition'}"
            for i, a in enumerate(batch_actions)
        ])

        prompt = f"""Analyze how each ACTION relates to the OBLIGATIONS, PRINCIPLES, and CONSTRAINTS in this ethics case.

## ACTIONS TO ANALYZE
{actions_text}

## ALL EXTRACTED ENTITIES (for reference)
{entities_text}

For EACH action listed above, analyze:
1. Which obligations does it FULFILL? (performing this action satisfies the obligation)
2. Which obligations does it VIOLATE? (performing this action contradicts the obligation)
3. Which principles GUIDE it? (the action is motivated by this principle)
4. Which constraints LIMIT it? (constraints that affect how the action can be performed)
5. Which role PERFORMS this action?
6. One sentence reasoning explaining the relationships

Use exact entity labels from the entity list. Output as JSON array:
```json
[
  {{
    "action_label": "exact action label",
    "fulfills_obligations": ["obligation label", ...],
    "violates_obligations": ["obligation label", ...],
    "guided_by_principles": ["principle label", ...],
    "constrained_by": ["constraint label", ...],
    "agent_role": "role label or null",
    "reasoning": "One sentence explaining the key relationship.",
    "confidence": 0.8
  }}
]
```

Include all {len(batch_actions)} actions even if they have empty relationships."""

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

                links_data = parse_json_response(response_text, f"causal links batch {batch_num}", strict=True)
                if links_data:
                    return self._resolve_causal_links(links_data, entity_dict, foundation)
                return []

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError) as e:
                last_error = e
                wait = 2 ** (attempt + 1)
                logger.warning(f"Causal links batch {batch_num} attempt {attempt + 1}/{max_retries} failed (connection): {e}. Retrying in {wait}s...")
                time.sleep(wait)
            except Exception as e:
                logger.error(f"Failed to analyze causal links batch {batch_num} (non-retryable): {e}")
                return []

        logger.error(f"Causal links batch {batch_num} failed after {max_retries} retries: {last_error}")
        return []

    def _resolve_causal_links(
        self,
        links_data: List[Dict],
        entity_dict: Dict[str, list],
        foundation: EntityFoundation
    ) -> List[CausalNormativeLink]:
        """Resolve label references in parsed causal link data to URIs."""
        # Build action label -> URI lookup for action_id
        action_lookup = {}
        for a in foundation.actions:
            from app.utils.entity_prompt_utils import _normalize_label
            action_lookup[_normalize_label(a.label)] = a.uri

        results = []
        for link in links_data:
            # Resolve action by label
            action_label = link.get('action_label', '')
            action_uri = ''
            if action_label:
                action_uri = action_lookup.get(_normalize_label(action_label), '')

            results.append(CausalNormativeLink(
                action_id=action_uri,
                action_label=action_label,
                fulfills_obligations=resolve_labels_flat(link.get('fulfills_obligations', []), entity_dict),
                violates_obligations=resolve_labels_flat(link.get('violates_obligations', []), entity_dict),
                guided_by_principles=resolve_labels_flat(link.get('guided_by_principles', []), entity_dict),
                constrained_by=resolve_labels_flat(link.get('constrained_by', []), entity_dict),
                agent_role=resolve_labels_flat([link['agent_role']], entity_dict)[0] if link.get('agent_role') else None,
                reasoning=link.get('reasoning', ''),
                confidence=link.get('confidence', 0.5)
            ))
        return results

    # =========================================================================
    # QUESTION EMERGENCE (Toulmin model)
    # =========================================================================

    def analyze_question_emergence(
        self,
        questions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace]
    ) -> List[QuestionEmergenceAnalysis]:
        """Analyze WHY each ethical question emerged, in batches of 5."""
        if not questions:
            return []

        all_results = []
        for batch_start in range(0, len(questions), self.BATCH_SIZE):
            batch = questions[batch_start:batch_start + self.BATCH_SIZE]
            batch_results = self.analyze_question_batch(
                batch, foundation, llm_traces, batch_start
            )
            all_results.extend(batch_results)
        return all_results

    def analyze_question_batch(
        self,
        questions: List[Dict],
        foundation: EntityFoundation,
        llm_traces: List[LLMTrace],
        batch_offset: int = 0
    ) -> List[QuestionEmergenceAnalysis]:
        """Analyze a batch of questions for emergence patterns.

        Labels-only prompt. Questions are numbered so the LLM can reference
        them by index; URIs and text are assigned programmatically after parse.
        """
        if not questions:
            return []

        entity_dict = foundation.to_entity_dict()
        entities_text = format_entities_compact(entity_dict)

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

        prompt = f"""Analyze WHY each ethical question emerged using Toulmin's model.

{toulmin_context}

## QUESTIONS TO ANALYZE
{questions_text}

## EXTRACTED ENTITIES
{entities_text}

For EACH question, use exact entity labels from the list above. Output JSON:
```json
[
  {{
    "question_index": 1,
    "data_events": ["event label", ...],
    "data_actions": ["action label", ...],
    "involves_roles": ["role label", ...],
    "competing_warrants": [["obligation A label", "obligation B label"]],
    "data_warrant_tension": "1 sentence on how data triggers multiple warrants",
    "competing_claims": "1 sentence on what different warrants conclude",
    "rebuttal_conditions": "1 sentence on what creates uncertainty",
    "emergence_narrative": "1-2 sentences explaining why this question arose",
    "confidence": 0.8
  }}
]
```

Include all questions in this batch."""

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

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError) as e:
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

        # Number conclusions within this batch (1-based for LLM)
        conclusions_text = "\n".join([
            f"C{i+1}. {c.get('label', 'C')}: {c.get('text', '')}"
            for i, c in enumerate(batch_conclusions)
        ])

        # Full questions and provisions context (needed for cross-referencing)
        questions_text = "\n".join([
            f"Q{i+1}. {q.get('label', 'Q')}: {q.get('text', '')}"
            for i, q in enumerate(questions)
        ]) if questions else "No questions extracted"

        provisions_text = "\n".join([
            f"P{i+1}. {p.get('label', 'P')}: {p.get('code', '')} - {p.get('definition', '')[:100]}"
            for i, p in enumerate(provisions)
        ]) if provisions else "No provisions extracted"

        prompt = f"""Analyze HOW the board resolved each ethical question in their conclusions.

## BOARD CONCLUSIONS (determinations made)
{conclusions_text}

## ETHICAL QUESTIONS (that needed answers)
{questions_text}

## CODE PROVISIONS (that could be cited)
{provisions_text}

For EACH conclusion above, analyze:
1. Which QUESTIONS does it answer? (by Q number)
2. What PRINCIPLES were determinative? (up to 3 key principles)
3. What FACTS were determinative? (up to 3 key facts)
4. What PROVISIONS were cited? (by P number)
5. How were COMPETING OBLIGATIONS weighed? (1 sentence)
6. A 1-2 sentence NARRATIVE explaining how the board reached this conclusion

Output as JSON array:
```json
[
  {{
    "conclusion_index": 1,
    "answers_questions": [1, 2],
    "determinative_principles": ["principle 1", "principle 2"],
    "determinative_facts": ["fact 1", "fact 2"],
    "cited_provisions": [1, 3],
    "weighing_process": "One sentence on how competing obligations were balanced.",
    "resolution_narrative": "The board concluded X because...",
    "confidence": 0.8
  }}
]
```

Include all {len(batch_conclusions)} conclusions in this batch."""

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

            except (anthropic.APIConnectionError, anthropic.APITimeoutError, ConnectionError) as e:
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
            answers_q = []
            for q_ref in p.get('answers_questions', []):
                if isinstance(q_ref, int):
                    q_idx = q_ref - 1
                    if 0 <= q_idx < len(questions):
                        answers_q.append(questions[q_idx].get('uri', ''))
                elif isinstance(q_ref, str):
                    answers_q.append(q_ref)

            # Resolve provision references (indices -> URIs)
            cited_p = []
            for p_ref in p.get('cited_provisions', []):
                if isinstance(p_ref, int):
                    p_idx = p_ref - 1
                    if 0 <= p_idx < len(provisions):
                        cited_p.append(provisions[p_idx].get('uri', ''))
                elif isinstance(p_ref, str):
                    cited_p.append(p_ref)

            results.append(ResolutionPatternAnalysis(
                conclusion_uri=conclusion_uri,
                conclusion_text=conclusion_text,
                answers_questions=answers_q,
                determinative_principles=p.get('determinative_principles', []),
                determinative_facts=p.get('determinative_facts', []),
                cited_provisions=cited_p,
                weighing_process=p.get('weighing_process', ''),
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
                    resolution_narrative=data.get('resolution_narrative', ''),
                    confidence=data.get('confidence', 0.0)
                ))

            logger.info(f"Loaded rich analysis: {len(causal_links)} links, {len(question_emergence)} QE, {len(resolution_patterns)} RP")

        except Exception as e:
            logger.error(f"Failed to load rich analysis: {e}")

        return causal_links, question_emergence, resolution_patterns
