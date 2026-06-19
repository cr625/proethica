"""Decisions synthesis view for the user-study interface.

DecisionsViewMixin: get_decisions_view plus its deterministic post-processing
(_dedupe_decision_points with the _DEDUP_STOPWORDS set, and
_reorder_evaluative_decisions with the _EVALUATIVE_OPENER regex). Relocated
verbatim from builder.py; SynthesisViewBuilder inherits this mixin, so the
classmethods resolve via MRO whether called on the class (as the unit tests do)
or through an instance.
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from app.models import TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt


class DecisionsViewMixin:
    """The Decisions synthesis view + its dedupe/reorder helpers."""


    def get_decisions_view(self, case_id: int) -> Dict[str, Any]:
        """Get decision points from Step 4 Phase 3.

        Returns decision points with:
        - Decision question
        - Alternatives considered
        - Obligations in tension
        - Arguments pro/con
        """
        # Get Phase 3 decision synthesis from ExtractionPrompt
        phase3_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase3_decision_synthesis'
        ).order_by(
            ExtractionPrompt.created_at.desc()
        ).first()

        decisions = []
        if phase3_prompt and phase3_prompt.raw_response:
            try:
                from app.utils.llm_json_utils import parse_json_response
                raw = parse_json_response(
                    phase3_prompt.raw_response,
                    context='phase3_decision_synthesis'
                )
                if isinstance(raw, list):
                    decisions = raw
                elif isinstance(raw, dict):
                    decisions = raw.get('decision_points', [])
            except json.JSONDecodeError:
                pass

        # TemporaryRDFStorage canonical_decision_point entries carry the
        # full synthesized data (options, Toulmin, Q&C alignment) in
        # rdf_json_ld.  Use them as the primary source when the
        # ExtractionPrompt yields fewer items (the prompt often stores
        # only one merged DP while the DB has the full set).
        decision_entities = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='canonical_decision_point'
        ).order_by(TemporaryRDFStorage.created_at).all()

        if len(decision_entities) > len(decisions):
            decisions = []
            for de in decision_entities:
                rdf_data = de.rdf_json_ld or {}
                # Pass through the full rdf_json_ld as the decision dict,
                # supplementing with entity-level fields.
                dp = dict(rdf_data)
                dp.setdefault('focus_id', rdf_data.get('focus_id', de.entity_label))
                dp.setdefault('description', rdf_data.get('description', de.entity_definition))
                dp.setdefault('decision_question', rdf_data.get('decision_question', ''))
                decisions.append(dp)

        decisions = self._dedupe_decision_points(decisions)
        decisions = self._reorder_evaluative_decisions(decisions)

        return {
            'view_type': 'decisions',
            'count': len(decisions),
            'decisions': decisions,
            'description': 'Decision points where the professional faced choices, along with '
                          'alternatives considered and actions taken.'
        }

    # Stopwords stripped before Jaccard-similarity comparison. The list is
    # intentionally narrow: question-framing tokens ("should", "what", "when")
    # would otherwise inflate similarity between unrelated decisions.
    _DEDUP_STOPWORDS = frozenset({
        'a', 'an', 'the', 'to', 'of', 'in', 'on', 'for', 'and', 'or', 'but',
        'that', 'which', 'should', 'must', 'do', 'does', 'did', 'is', 'are',
        'was', 'were', 'be', 'been', 'being', 'this', 'these', 'those', 'it',
        'its', 'as', 'at', 'by', 'with', 'from', 'have', 'has', 'had', 'can',
        'could', 'would', 'may', 'might', 'when', 'where', 'why', 'how',
        'what', 'who', 'whom', 'whose',
    })

    @classmethod
    def _dedupe_decision_points(cls, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Drop near-duplicate decision points produced by Step 4 Phase 3.

        Three signals flag a duplicate, any of which is sufficient:

        1. Normalized prefix equality on the first 40 chars of the question
           (lowercased, non-alphanumeric stripped, whitespace collapsed).
        2. Content-word token Jaccard >= 0.55 against any kept DP's tokens.
        3. First 6 content tokens of each question share >= 5 tokens (catches
           rephrasings that score below the Jaccard threshold because the
           question body diverges in trailing detail).

        Earliest-by-ordinal wins; later duplicates are silently dropped.
        Options/grounds are not merged across duplicates: the participant
        is rating the quality of a view, not enumerating exhaustively, so
        culling is sufficient to remove the "unfinished analysis" signal.
        """
        if not decisions:
            return decisions
        import re

        def _normalized_prefix(text: str, n: int = 40) -> str:
            s = re.sub(r'[^a-z0-9 ]+', ' ', (text or '').lower())
            s = re.sub(r'\s+', ' ', s).strip()
            return s[:n]

        def _content_tokens(text: str) -> 'set[str]':
            return {
                t for t in re.findall(r'[a-z]+', (text or '').lower())
                if len(t) > 2 and t not in cls._DEDUP_STOPWORDS
            }

        def _first_content_tokens(text: str, n: int = 6) -> 'list[str]':
            out: 'list[str]' = []
            for t in re.findall(r'[a-z]+', (text or '').lower()):
                if len(t) > 2 and t not in cls._DEDUP_STOPWORDS:
                    out.append(t)
                if len(out) >= n:
                    break
            return out

        def _jaccard(a: 'set[str]', b: 'set[str]') -> float:
            if not a or not b:
                return 0.0
            return len(a & b) / len(a | b)

        kept: List[Dict[str, Any]] = []
        kept_prefixes: List[str] = []
        kept_tokens: List['set[str]'] = []
        kept_firsts: List['set[str]'] = []
        for d in decisions:
            question = d.get('decision_question') or d.get('description') or ''
            prefix = _normalized_prefix(question)
            tokens = _content_tokens(question)
            firsts = set(_first_content_tokens(question))
            is_dup = False
            for kp, kt, kf in zip(kept_prefixes, kept_tokens, kept_firsts):
                if prefix and prefix == kp:
                    is_dup = True
                    break
                if _jaccard(tokens, kt) >= 0.55:
                    is_dup = True
                    break
                if len(firsts & kf) >= 5:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(d)
                kept_prefixes.append(prefix)
                kept_tokens.append(tokens)
                kept_firsts.append(firsts)
        return kept

    # Stable partition that demotes retrospective-evaluative decision questions
    # so the visible top-five default opens with a forward-looking decision.
    # Matches "Was <subject> ethical[ly]..." openers: the baseline audit's
    # narrow EVAL opener ("Was it ethical for X to...") plus the equivalent
    # active-voice form ("Was Engineer A ethically obligated to..."). The
    # 1-to-4-word subject bound keeps the match anchored to the question
    # opener and avoids false positives like "...whether the design was
    # ethical" later in a sentence. Across the 19-case study pool this
    # affects 5 DPs in 3 cases (6: 2, 8: 1, 13: 2); the remaining 16 cases
    # are unchanged.
    _EVALUATIVE_OPENER = re.compile(
        r'^\s*was\s+(?:\w+\s+){1,4}ethical(?:ly)?\b',
        re.IGNORECASE,
    )

    @classmethod
    def _reorder_evaluative_decisions(cls, decisions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Stable partition: forward-looking DPs first, evaluative DPs last.

        Preserves relative order within each group, so the only observable
        change is that a "Was it ethical for X to..." card cannot occupy the
        top of the visible top-N slice. No DP text is rewritten; presentation
        change only.
        """
        if not decisions:
            return decisions
        forward: List[Dict[str, Any]] = []
        evaluative: List[Dict[str, Any]] = []
        for d in decisions:
            question = d.get('decision_question') or d.get('description') or ''
            if cls._EVALUATIVE_OPENER.match(question):
                evaluative.append(d)
            else:
                forward.append(d)
        return forward + evaluative
