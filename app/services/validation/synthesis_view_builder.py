"""
Synthesis View Builder for the ProEthica user-study interface.

Builds the five synthesis views evaluated in the IRB-approved study
(EvaluationStudyPlan.md):
- Provisions View: Code provision mappings (Step 4 Phase 2A)
- Q&C View: Ethical questions linked to conclusions (Step 4 Phase 2B)
- Decisions View: Decision points with Toulmin argumentative structure (Step 4 Phase 3)
- Timeline View: Actions/Events with nested decision points (Step 3 + Step 4 Phase 3)
- Narrative View: Characters with ethical tensions and opening states (Step 4 Phase 4)
"""

import json
import re
from typing import Dict, List, Optional, Any
from app.models import db, Document, TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt
from app.models.document_section import DocumentSection


class SynthesisViewBuilder:
    """Build synthesis views for the user-study interface.

    Pulls synthesis data from existing Step 4 pipeline outputs stored in:
    - TemporaryRDFStorage: Entity-level extractions (Step 3 + Step 4 Phase 2)
    - ExtractionPrompt: LLM synthesis outputs (Step 4 Phase 3 + Phase 4)
    - DocumentSection: Case text sections
    """

    def get_provisions_view(self, case_id: int) -> Dict[str, Any]:
        """Get code provision mappings from Step 4 Phase 2A.

        Returns provisions with:
        - Code section identifiers (e.g., "II.4.a")
        - Full provision text
        - Relevant case excerpts
        - Entity connections (appliesTo relationships)
        """
        provisions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).filter(
            TemporaryRDFStorage.is_published == True
        ).order_by(
            TemporaryRDFStorage.entity_label
        ).all()

        # Pick a small set of "most concrete" mappings per provision. The
        # full applies_to list runs 8-37 entries spanning all nine entity
        # types -- showing all of them inline makes the view read like a
        # type-count puzzle. Instead we surface up to three diverse
        # examples (one per high-priority type) and leave the rest behind a
        # "Show all" toggle. Priority order favors Obligation, Action,
        # State, and Constraint because those read most naturally as
        # "code applies here in the case" connections; abstract types
        # (Principle, Capability) and situational types (Role, Resource,
        # Event) follow.
        TOP_PRIORITY = ['obligation', 'action', 'state', 'constraint',
                        'principle', 'role', 'event', 'resource', 'capability']
        TYPE_DISPLAY_ORDER = TOP_PRIORITY  # used by the "Show all" group rendering

        def _top_mappings(applies_to: list, max_n: int = 3) -> list:
            """Return up to N entries, one per priority type when possible."""
            picked: list = []
            seen_types: set = set()
            for ptype in TOP_PRIORITY:
                if len(picked) >= max_n:
                    break
                for entity in applies_to:
                    if not isinstance(entity, dict):
                        continue
                    et = (entity.get('entity_type') or '').lower()
                    if et == ptype and et not in seen_types:
                        picked.append(entity)
                        seen_types.add(et)
                        break
            return picked

        formatted = []
        for prov in provisions:
            rdf_data = prov.rdf_json_ld or {}
            applies_to = rdf_data.get('appliesTo', []) or []
            formatted.append({
                'id': prov.id,
                'code_section': prov.entity_label,
                'provision_text': prov.entity_definition,
                'iao_label': prov.iao_document_label,
                'applies_to': applies_to,
                'top_mappings': _top_mappings(applies_to, max_n=3),
                'case_excerpt': rdf_data.get('relevantExcerpt', ''),
                'confidence': prov.match_confidence or 0.0
            })

        # Fetch abstract class definitions for the 9 entity-type chips that
        # appear next to each mapping (Obligation, Action, ...). Keyed by
        # exact label match against proeth-core class entries in OntServe.
        # Labels without a non-empty rdfs:comment are omitted; the template
        # renders those chips without a popover. The order here matches the
        # title-case form rendered by `{{ etype|title }}` in the template.
        type_chip_labels = ['Obligation', 'Action', 'State', 'Principle',
                            'Role', 'Resource', 'Capability', 'Event',
                            'Constraint']
        type_definitions = self._fetch_class_definitions(type_chip_labels)

        return {
            'view_type': 'provisions',
            'count': len(formatted),
            'provisions': formatted,
            'type_definitions': type_definitions,
            'description': 'Code provisions mapped to case elements, showing which sections '
                          'of the professional code apply and how they connect to specific facts.'
        }

    def get_qc_view(self, case_id: int) -> Dict[str, Any]:
        """Get Q&C (Questions and Conclusions) view from Step 4 Phase 2B.

        Returns questions linked to their board/analytical conclusions with:
        - Question text and type classification
        - Conclusions linked to each question via answersQuestions relation
        - Entity involvement breakdown and emergence/resolution overlays
        """
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        ).filter(
            TemporaryRDFStorage.is_published == True
        ).order_by(
            TemporaryRDFStorage.entity_label
        ).all()

        # Also get conclusions for linking
        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).filter(
            TemporaryRDFStorage.is_published == True
        ).all()

        # Provision text lookup, keyed by code section (e.g., "II.2.a"), so
        # the cited-provision badges below can carry hover popovers with
        # the actual NSPE provision text. Conclusions store citedProvisions
        # as bare code strings; without this lookup the badges read as
        # opaque labels. Two sources are merged, in priority order:
        #   1. Per-case code_provision_reference extractions, which carry
        #      case-specific provision wording when present.
        #   2. The canonical GuidelineSection table (the static NSPE Code),
        #      which fills in any cited provision the per-case extraction
        #      did not surface. Audit on 2026-05-12 showed 27 of 99 cited
        #      provisions across the corpus lacked a per-case extraction
        #      row; the canonical fallback resolves all of them except the
        #      occasional 'Preamble' citation, which is not in the table.
        from app.models.guideline_section import GuidelineSection
        provisions_rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).filter(
            TemporaryRDFStorage.is_published == True
        ).all()
        provision_text_lookup: Dict[str, str] = {}
        # Canonical NSPE Code sections (leaf rows only; e.g., III.6.a but
        # not III.6 itself).
        canonical_rows = GuidelineSection.query.all()
        for section in canonical_rows:
            code = (section.section_code or '').strip()
            text = (section.section_text or '').strip()
            if code and text:
                provision_text_lookup[code] = text
        # Parent-section synthesis. Conclusions sometimes cite a parent
        # section (e.g., III.6) where the table only stores the leaves
        # (III.6.a, III.6.b, III.6.c). For each parent code referenced,
        # concatenate the children's texts so the popover still resolves.
        children_by_parent: Dict[str, List[str]] = {}
        for section in canonical_rows:
            code = (section.section_code or '').strip()
            if '.' in code:
                parent = code.rsplit('.', 1)[0]
                if parent and parent != code:
                    children_by_parent.setdefault(parent, []).append(
                        f"{code}: {(section.section_text or '').strip()}"
                    )
        for parent, lines in children_by_parent.items():
            if parent not in provision_text_lookup and lines:
                provision_text_lookup[parent] = ' '.join(lines)
        # Per-case extractions take precedence over canonical text when
        # the case carries case-specific wording.
        for p in provisions_rows:
            code = (p.entity_label or '').strip()
            text = (p.entity_definition or '').strip()
            if code and text:
                provision_text_lookup[code] = text

        # Build conclusion lookup by question. Each conclusion is added to
        # the FIRST question listed in its answersQuestions array — its
        # primary target. Earlier code added a conclusion to every question
        # in the array, which produced the case-5 bug where an LLM
        # commentary primarily answering sub-question Q103 (with Q1 as a
        # secondary linkage) appeared under Q1, where the reader had no
        # context for the embedded "In response to Q103:" reference.
        # answersQuestions stores integer question numbers (e.g., 1, 101,
        # 201). Questions use entity_label strings like "Question_1",
        # "Question_101". Normalize keys to entity_label format so the
        # lookup matches.
        conclusion_map: Dict[str, list] = {}
        for conc in conclusions:
            rdf_data = conc.rdf_json_ld or {}
            answers = rdf_data.get('answersQuestions', []) or []
            if not answers:
                continue
            conc_label = conc.entity_label or ''
            is_board = (
                conc_label.startswith('Conclusion_')
                and conc_label.replace('Conclusion_', '').isdigit()
                and len(conc_label.replace('Conclusion_', '')) <= 2
            )
            primary_q = answers[0]
            key = f"Question_{primary_q}" if isinstance(primary_q, int) else str(primary_q)
            conclusion_map.setdefault(key, []).append({
                'id': conc.id,
                'label': conc.entity_label,
                'text': conc.entity_definition,
                'conclusion_type': 'board' if is_board else 'analytical',
                'cited_provisions': rdf_data.get('citedProvisions', []),
                'also_answers': [a for a in answers[1:] if a != primary_q],
            })

        def _parent_question(label: str) -> Optional[str]:
            """Derive parent board question from numbering convention.

            Question_1 → None (is a board question)
            Question_101 → "Question_1" (first digit = board question number)
            Question_201 → "Question_2"
            Question_301, Question_401 → "Question_3"
            """
            suffix = label.replace('Question_', '')
            if not suffix.isdigit():
                return None
            n = int(suffix)
            if n < 10:
                return None  # board question itself
            parent_n = n // 100
            return f"Question_{parent_n}" if parent_n > 0 else None

        formatted = []
        for q in questions:
            rdf_data = q.rdf_json_ld or {}
            q_number = q.entity_label  # e.g., "Question_1"
            formatted.append({
                'id': q.id,
                'number': q_number,
                'question_text': q.entity_definition,
                'question_type': rdf_data.get('questionType', 'board_explicit'),
                'parent_question': _parent_question(q_number),
                'related_provisions': rdf_data.get('relatedProvisions', []),
                'mentioned_entities': rdf_data.get('mentionedEntities', {}),
                'linked_conclusions': conclusion_map.get(q_number, [])
            })

        # Build grouped structure: board questions with their sub-questions,
        # split into analytical (implicit, principle_tension) and theory
        # (theoretical, counterfactual) groups for progressive disclosure.
        board_questions = [q for q in formatted if q['question_type'] == 'board_explicit']
        board_numbers = {q['number'] for q in board_questions}
        analytical_by_parent: Dict[str, list] = {}
        theory_by_parent: Dict[str, list] = {}
        cross_cutting: list = []
        for q in formatted:
            if q['question_type'] == 'board_explicit':
                continue
            parent = q.get('parent_question')
            # When the sub-question's parent number does not match any
            # extracted board question (e.g. a Question_401 counterfactual
            # whose parent would be Question_4 but the case only has board
            # Q1-Q3), surface it as a cross-cutting question rather than
            # silently dropping it.
            if not parent or parent not in board_numbers:
                cross_cutting.append(q)
                continue
            if q['question_type'] in ('implicit', 'principle_tension'):
                analytical_by_parent.setdefault(parent, []).append(q)
            else:
                theory_by_parent.setdefault(parent, []).append(q)

        return {
            'view_type': 'qc',
            'count': len(formatted),
            'questions': formatted,
            'board_questions': board_questions,
            'analytical_by_parent': analytical_by_parent,
            'theory_by_parent': theory_by_parent,
            'cross_cutting': cross_cutting,
            'provision_text_lookup': provision_text_lookup,
            'description': 'Ethical questions linked to their conclusions with emergence and '
                          'resolution overlays, showing how the board reached its findings.'
        }

    # Backwards-compatible alias while any remaining callers transition.
    get_questions_view = get_qc_view

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

    def get_timeline_view(self, case_id: int) -> Dict[str, Any]:
        """Get Timeline view from Step 3 temporal extraction.

        Returns Actions and Events in temporal sequence with decision-point
        nesting and causal flow. Per HyperText'26 section 3.2:
        - Actions = volitional conduct by identified participants
        - Events = occurrences outside agent control
        - Decision points synthesized in Step 4 nest beneath the Action/Event
          they originate from.

        Data source: `temporal_dynamics_enhanced` rows in `temporary_rdf_storage`
        carry typed JSON-LD with `@type` = `proeth:Action` | `proeth:Event`,
        `proeth:temporalMarker`, `proeth-scenario:isDecisionPoint`,
        `proeth-scenario:alternativeActions`, and obligation links.
        """
        # Load all temporal rows; chronological ordering uses
        # `proeth:temporalSequence` (1-based int) when present and falls back
        # to `id` for cases the temporal-sequence backfill has not visited.
        # See docs-internal/scripts/backfill_temporal_sequence.py and the
        # roadmap entry "Timeline Chronological Ordering".
        temporal_entries = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).order_by(TemporaryRDFStorage.id).all()

        def _temporal_sort_key(row):
            seq = (row.rdf_json_ld or {}).get('proeth:temporalSequence')
            try:
                seq_int = int(seq) if seq is not None else None
            except (TypeError, ValueError):
                seq_int = None
            # Rows with a sequence sort before rows without one; among the
            # latter, fall back to id (extraction order) as a stable tiebreak.
            return (0, seq_int) if seq_int is not None else (1, row.id)

        temporal_entries = sorted(temporal_entries, key=_temporal_sort_key)

        entries = []
        causal_flow = []

        def _uri_fragment(uri: str) -> str:
            frag = uri.split('#')[-1] if '#' in uri else ''
            for prefix in ('Action_', 'Event_'):
                if frag.startswith(prefix):
                    frag = frag[len(prefix):]
                    break
            return frag

        seq = 0
        for row in temporal_entries:
            rdf = row.rdf_json_ld or {}
            at_type = rdf.get('@type', '') or ''
            if 'Action' in at_type:
                kind = 'action'
            elif 'Event' in at_type:
                kind = 'event'
            else:
                # Skip Timeline-skeleton, State, and other temporal types that
                # production also excludes from the rendered timeline.
                continue
            seq += 1
            alternatives = rdf.get('proeth-scenario:alternativeActions', []) or []

            fulfills = rdf.get('proeth:fulfillsObligation', []) or []
            violates = rdf.get('proeth:violatesObligation', []) or []
            raises = rdf.get('proeth:raisesObligation', []) or []

            entry_iri = rdf.get('@id', '')
            entry = {
                'sequence': seq,
                'kind': kind,
                'label': row.entity_label,
                'entity_iri': entry_iri,
                'fragment': _uri_fragment(entry_iri),
                'temporal_marker': rdf.get('proeth:temporalMarker', ''),
                'agent': rdf.get('proeth:hasAgent', ''),
                'narrative_role': rdf.get('proeth-scenario:narrativeRole', ''),
                'description': rdf.get('proeth:description', ''),
                'alternative_count': len(alternatives) if isinstance(alternatives, list) else 0,
                'fulfills_obligations': fulfills if isinstance(fulfills, list) else [],
                'violates_obligations': violates if isinstance(violates, list) else [],
                'raises_obligations': raises if isinstance(raises, list) else [],
                'decision_points': [],  # filled below by fragment match
            }
            entries.append(entry)

            foreseen = rdf.get('proeth:foreseenUnintendedEffects', [])
            if isinstance(foreseen, list):
                for effect in foreseen:
                    causal_flow.append({
                        'from_label': row.entity_label,
                        'to_label': effect,
                        'relation': 'enables'
                    })

        # Match synthesized decision points to their temporal-entry host
        # (same URI-fragment strategy as the production step4 review helper).
        fragment_to_idx = {e['fragment']: i for i, e in enumerate(entries) if e['fragment']}
        dp_rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='canonical_decision_point'
        ).order_by(TemporaryRDFStorage.created_at).all()

        for dp_row in dp_rows:
            data = dp_row.rdf_json_ld or {}
            action_uris = data.get('involved_action_uris') or []
            if not action_uris:
                single = data.get('action_uri') or ''
                if single:
                    action_uris = [single]

            matched_indices = set()
            for uri in action_uris:
                frag = _uri_fragment(uri)
                if frag in fragment_to_idx:
                    matched_indices.add(fragment_to_idx[frag])

            if not matched_indices:
                continue

            # Primary host = earliest matching temporal entry.
            primary = min(matched_indices)
            entries[primary]['decision_points'].append({
                'focus_id': data.get('focus_id', ''),
                'focus_number': data.get('focus_number', 0),
                'entity_label': data.get('description', dp_row.entity_label),
                'options': data.get('options', []) or [],
            })

        entries_with_dps = sum(1 for e in entries if e['decision_points'])
        total_dps_attached = sum(len(e['decision_points']) for e in entries)

        return {
            'view_type': 'timeline',
            'count': len(entries),
            'action_count': sum(1 for e in entries if e['kind'] == 'action'),
            'event_count': sum(1 for e in entries if e['kind'] == 'event'),
            'decision_point_count': total_dps_attached,
            'entries_with_decision_points': entries_with_dps,
            'entries': entries,
            'causal_flow': causal_flow,
            'description': 'Actions and Events in temporal sequence with decision points '
                          'nested beneath their corresponding entries; causal flow shows '
                          'enables links between actions and events.'
        }

    def get_narrative_view(self, case_id: int) -> Dict[str, Any]:
        """Get Narrative view content per paper \u00a73.2 (integrative view).

        Returns the character-driven retelling: characters drawn from
        extracted Roles, ethical tensions drawn from Obligations and
        Constraints (stored as `conflicts` in Phase 4 output), and an
        opening-context paragraph drawn from States (in second-person
        address).

        The Phase 4 JSON is nested
        (`narrative_elements.characters`, `narrative_elements.conflicts`,
        `scenario_seeds.opening_context`); this builder flattens those
        shapes so the template can render each section uniformly.
        """
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(
            ExtractionPrompt.created_at.desc()
        ).first()

        raw: Dict[str, Any] = {}
        if phase4_prompt and phase4_prompt.raw_response:
            try:
                raw = json.loads(phase4_prompt.raw_response)
            except json.JSONDecodeError:
                pass

        narrative_elements = raw.get('narrative_elements') or {}
        scenario_seeds = raw.get('scenario_seeds') or {}

        characters = narrative_elements.get('characters') or []
        raw_tensions = narrative_elements.get('conflicts') or []
        opening_context = scenario_seeds.get('opening_context') or ''

        # Filter spurious characters surfaced by the second-pass content
        # review (cases 11, 19, 60). The extractor sometimes promotes
        # citations to prior BER cases or non-person entities (states,
        # jurisdictions, cities) into the character set. These should
        # never reach a participant-facing Narrative card.
        #
        # Citation pattern: labels starting with 'Case NN-NN' (the BER
        # numbering scheme) are references to other opinions, not present-
        # case people. Place / jurisdiction patterns: labels beginning
        # with 'State ', 'City of ', 'Jurisdiction', 'Country' identify
        # a place rather than a person.
        import re as _re
        _CITATION_RE = _re.compile(r'^\s*Case\s+\d{2}-\d{2}\b', _re.IGNORECASE)
        _PLACE_PREFIXES = ('state ', 'city of ', 'jurisdiction', 'country ')

        def _is_spurious_character(ch: Dict[str, Any]) -> bool:
            label = (ch.get('label') or '').strip()
            if not label:
                return False
            if _CITATION_RE.match(label):
                return True
            if label.lower().startswith(_PLACE_PREFIXES):
                return True
            return False

        characters = [c for c in characters if not _is_spurious_character(c)]

        protagonist_label = scenario_seeds.get('protagonist_label') or ''

        # Flatten tensions + attach a composite moral-intensity score (Jones 1991)
        # so the template can sort rated tensions above unrated ones. Each of the
        # five intensity dimensions maps to a 0-3 ordinal; the composite is the
        # sum. Unrated tensions score 0 and sink to the bottom of the list.
        INTENSITY_SCORES = {
            'low': 1, 'medium': 2, 'high': 3,
            'distal': 1, 'near-term': 2, 'immediate': 3,
            'indirect': 1, 'direct': 3,
            'dispersed': 1, 'concentrated': 3,
        }
        def _score(*values: str) -> int:
            return sum(INTENSITY_SCORES.get((v or '').lower(), 0) for v in values)

        tensions = []
        for c in raw_tensions:
            composite = _score(
                c.get('magnitude_of_consequences'),
                c.get('probability_of_effect'),
                c.get('temporal_immediacy'),
                c.get('proximity'),
                c.get('concentration_of_effect'),
            )
            tensions.append({
                'description': c.get('description') or '',
                'conflict_type': c.get('conflict_type') or '',
                'entity1_label': c.get('entity1_label') or '',
                'entity1_type': c.get('entity1_type') or '',
                'entity2_label': c.get('entity2_label') or '',
                'entity2_type': c.get('entity2_type') or '',
                'magnitude_of_consequences': c.get('magnitude_of_consequences') or '',
                'probability_of_effect': c.get('probability_of_effect') or '',
                'temporal_immediacy': c.get('temporal_immediacy') or '',
                'proximity': c.get('proximity') or '',
                'concentration_of_effect': c.get('concentration_of_effect') or '',
                'affected_role_labels': c.get('affected_role_labels') or [],
                'resolution_rationale': c.get('resolution_rationale') or '',
                'intensity_score': composite,
            })
        # Sort descending by composite intensity; stable for ties so the
        # extractor's emission order is preserved within equal-intensity bands.
        tensions.sort(key=lambda t: t['intensity_score'], reverse=True)
        rated_tension_count = sum(1 for t in tensions if t['intensity_score'] > 0)

        # Group tensions by the characters they affect. Each tension carries an
        # affected_role_labels list; a tension that implicates multiple roles
        # appears under each (no dedup) because the data signals "these
        # characters are co-implicated" and hiding that would lose the chain.
        # Match priority:
        #   1. Exact match of role-label against character.label or character.role.
        #   2. Case-insensitive substring match between role-label and character labels.
        #   3. Fallback: scan the tension's entity1_label/entity2_label for the
        #      character's short-name (first two words of label, e.g.,
        #      "Engineer A" extracted from "Engineer A Environmental Engineering
        #      Consultant"). The case-7 extraction often leaves
        #      affected_role_labels empty even when the tension's entity labels
        #      clearly name a character; the fallback rescues those.
        # If after all three passes nothing matches, the tension goes to
        # unassigned_tensions, rendered as an "Other tensions" section so the
        # participant doesn't lose them.
        char_lookup = {}
        for ch in characters:
            for key in (ch.get('label'), ch.get('role')):
                if key:
                    char_lookup.setdefault(key.strip().lower(), ch.get('label') or key)

        # Map each character's short-name (first 2 words of label) to the
        # full label, for the entity-label scan fallback. Characters whose
        # short-name is shared (e.g., four characters all starting "Engineer A")
        # all collect tensions that mention "Engineer A" in entity labels;
        # we accept that co-attribution because the extractor did not
        # disambiguate the role variant.
        short_name_lookup: Dict[str, List[str]] = {}
        for ch in characters:
            label = (ch.get('label') or '').strip()
            if not label:
                continue
            words = label.split()
            short = ' '.join(words[:2]).lower() if len(words) >= 2 else label.lower()
            short_name_lookup.setdefault(short, []).append(label)

        tensions_by_character: Dict[str, List[Dict[str, Any]]] = {
            ch['label']: [] for ch in characters if ch.get('label')
        }
        unassigned_tensions: List[Dict[str, Any]] = []

        for t in tensions:
            role_labels = t.get('affected_role_labels') or []
            matched_char_labels = set()
            for role_label in role_labels:
                if not role_label:
                    continue
                key = role_label.strip().lower()
                # Pass 1: exact match on label or role.
                if key in char_lookup:
                    matched_char_labels.add(char_lookup[key])
                    continue
                # Pass 2: substring match against full character labels.
                for ch in characters:
                    ch_label = (ch.get('label') or '').strip().lower()
                    if ch_label and (key in ch_label or ch_label in key):
                        matched_char_labels.add(ch.get('label'))

            # Pass 3: entity-label scan fallback (only if passes 1+2 produced
            # no match). Look at the tension's entity1_label and entity2_label
            # for any character's short-name.
            if not matched_char_labels:
                text_to_scan = (
                    (t.get('entity1_label') or '') + ' '
                    + (t.get('entity2_label') or '')
                ).lower()
                for short, full_labels in short_name_lookup.items():
                    if short and short in text_to_scan:
                        for full_label in full_labels:
                            matched_char_labels.add(full_label)

            if matched_char_labels:
                for label in matched_char_labels:
                    tensions_by_character.setdefault(label, []).append(t)
            else:
                unassigned_tensions.append(t)

        # Sort each character's tensions by intensity desc. (Already
        # globally sorted, but per-character sort guards against
        # ordering surprises when fallback matching reshuffles rows.)
        for label in tensions_by_character:
            tensions_by_character[label].sort(
                key=lambda t: t['intensity_score'], reverse=True
            )

        # Identify "main" characters: those whose short-name appears in
        # the opening_context text. The opening context is a 2nd-person
        # narration of the case from the protagonist's point of view; the
        # characters it names are central to the case's ethical structure.
        # Characters not named there are "additional" — present in the
        # case but secondary to the opening narrative.
        import re
        main_short_names: set = set()
        main_short_name_order: Dict[str, int] = {}  # short-name -> first-occurrence index
        for idx, ch in enumerate(characters):
            label = (ch.get('label') or '').strip()
            if not label:
                ch['is_main'] = False
                continue
            short_name = ' '.join(label.split()[:2])
            if short_name and opening_context and short_name in opening_context:
                ch['is_main'] = True
                main_short_names.add(short_name)
                if short_name not in main_short_name_order:
                    main_short_name_order[short_name] = idx
            else:
                ch['is_main'] = False

        # Per-main-character tension sort: surface tensions that involve
        # OTHER main characters first, in the order those characters
        # appear in the character list. Tensions that only involve the
        # character themselves (intra-role conflicts, with the same
        # short-name on both sides) sink to the bottom, where the
        # template hides them behind a per-character "show more" toggle.
        #
        # The cross-main priority is computed per (character, tension)
        # pair without mutating the tension dict, because the same
        # tension can appear in multiple characters' lists with a
        # different cross-main perspective each time.
        def _cross_main_pos(t: Dict[str, Any], own_short: str) -> 'int | None':
            text = ' '.join([
                (t.get('entity1_label') or ''),
                (t.get('entity2_label') or ''),
                ' '.join(t.get('affected_role_labels') or []),
            ])
            best_pos: int | None = None
            for short, pos in main_short_name_order.items():
                if short == own_short:
                    continue
                if short and short in text and (best_pos is None or pos < best_pos):
                    best_pos = pos
            return best_pos

        def _linked_main_shorts(t: Dict[str, Any], own_short: str) -> List[str]:
            """List of OTHER main short-names implicated by this tension,
            in character-list order."""
            text = ' '.join([
                (t.get('entity1_label') or ''),
                (t.get('entity2_label') or ''),
                ' '.join(t.get('affected_role_labels') or []),
            ])
            shorts_with_pos: List[tuple] = []
            for short, pos in main_short_name_order.items():
                if short == own_short:
                    continue
                if short and short in text:
                    shorts_with_pos.append((pos, short))
            shorts_with_pos.sort()
            return [short for _, short in shorts_with_pos]

        # tensions_cross_count_by_character[label] = N means the first
        # N entries of tensions_by_character[label] are cross-main and
        # should render visible by default; the remaining are self-only
        # and the template hides them behind a "show more" toggle.
        # tensions_linked_by_character[label] is a parallel list-of-lists
        # giving the OTHER main short-names implicated by each tension
        # under that character (same order as tensions_by_character[label]).
        tensions_cross_count_by_character: Dict[str, int] = {}
        tensions_linked_by_character: Dict[str, List[List[str]]] = {}
        for char in characters:
            if not char.get('is_main'):
                continue
            label = char.get('label') or ''
            if label not in tensions_by_character:
                continue
            own_short = ' '.join(label.split()[:2])

            def _key(t: Dict[str, Any], _own=own_short) -> tuple:
                pos = _cross_main_pos(t, _own)
                if pos is not None:
                    return (0, pos, -t.get('intensity_score', 0))
                return (1, 0, -t.get('intensity_score', 0))

            tensions_by_character[label].sort(key=_key)
            cross_count = sum(
                1 for t in tensions_by_character[label]
                if _cross_main_pos(t, own_short) is not None
            )
            tensions_cross_count_by_character[label] = cross_count
            tensions_linked_by_character[label] = [
                _linked_main_shorts(t, own_short)
                for t in tensions_by_character[label]
            ]

        # Wrap each main short-name in opening_context with a popover
        # span. The popover content is the character's professional
        # position. When the same short-name maps to multiple character
        # variants (e.g. "Engineer A" -> four role variants), the popover
        # links to the first match; the alternative role cards remain
        # visible in the main-characters section below.
        opening_context_html = opening_context or ''
        if opening_context_html and main_short_names:
            short_to_char = {}
            for ch in characters:
                if not ch.get('is_main'):
                    continue
                label = (ch.get('label') or '').strip()
                short = ' '.join(label.split()[:2])
                short_to_char.setdefault(short, ch)

            sorted_shorts = sorted(short_to_char.keys(), key=len, reverse=True)
            pattern = re.compile(
                r'\b(' + '|'.join(re.escape(n) for n in sorted_shorts) + r')\b'
            )

            def _wrap(match: 're.Match') -> str:
                name = match.group(1)
                ch = short_to_char[name]
                pos_raw = (ch.get('professional_position') or '').strip()
                if len(pos_raw) > 200:
                    cut = pos_raw.rfind(' ', 0, 200)
                    if cut <= 0:
                        cut = 200
                    pos_raw = pos_raw[:cut].rstrip(' ,;:.') + '…'
                pos = pos_raw.replace('"', '&quot;')
                anchor = 'char-' + name.replace(' ', '-').lower()
                return (
                    f'<a class="char-mention" href="#{anchor}" '
                    f'data-bs-toggle="popover" data-bs-trigger="focus hover" '
                    f'data-bs-title="Role in the case" '
                    f'data-bs-content="{pos}" tabindex="0">{name}</a>'
                )

            opening_context_html = pattern.sub(_wrap, opening_context_html)

        # Collapse role-instance character cards under each named individual.
        # The extractor emits one character per role-instance (e.g., "Engineer A
        # Environmental Engineering Consultant" and "Engineer A Groundwater
        # Infrastructure Design Engineer" are two separate cards for the same
        # person). For the participant-facing view we group these under one
        # person card whose tensions are the union of the underlying role
        # instances' tensions. Each tension carries a chip naming which role
        # within the person it attaches to.
        from collections import OrderedDict
        grouped_chars: 'OrderedDict[str, Dict[str, Any]]' = OrderedDict()
        for ch in characters:
            label = (ch.get('label') or '').strip()
            if not label:
                continue
            parts = label.split()
            # Preserve single-letter disambiguators (NSPE naming convention:
            # "Engineer A", "Principal Engineer R", "City Engineer J"). When
            # parts[2] is a single uppercase letter, it identifies the
            # individual rather than a role suffix; include it in short_name.
            if (
                len(parts) >= 3
                and len(parts[2]) == 1
                and parts[2].isupper()
            ):
                short_name = ' '.join(parts[:3])
                role_suffix = ' '.join(parts[3:])
            elif len(parts) >= 2:
                short_name = ' '.join(parts[:2])
                role_suffix = ' '.join(parts[2:])
            else:
                short_name = label
                role_suffix = ''
            if short_name not in grouped_chars:
                grouped_chars[short_name] = {
                    'short_name': short_name,
                    'anchor': 'char-' + short_name.replace(' ', '-').lower(),
                    'role_suffixes': [],
                    'role_suffix_details': {},
                    '_positions': [],
                    '_stances': [],
                    'motivations': [],
                    'tensions': [],
                    '_tension_keys': set(),
                    'is_main': False,
                }
            g = grouped_chars[short_name]
            if role_suffix and role_suffix not in g['role_suffixes']:
                g['role_suffixes'].append(role_suffix)
            if ch.get('is_main'):
                g['is_main'] = True
            pos = (ch.get('professional_position') or '').strip()
            if pos and pos not in g['_positions']:
                g['_positions'].append(pos)
            stance = (ch.get('ethical_stance') or '').strip()
            if stance and stance not in g['_stances']:
                g['_stances'].append(stance)
            for m in (ch.get('motivations') or []):
                if m and m not in g['motivations']:
                    g['motivations'].append(m)
            char_tensions = tensions_by_character.get(label, [])
            char_linked = tensions_linked_by_character.get(label, [])
            for idx, t in enumerate(char_tensions):
                # Dedup key uses the truncated label form (matching the
                # template's |truncate(60)) plus sorted affected roles, so
                # tensions that display identically to the participant merge
                # even when their full extracted labels differ in extraction-
                # artifact suffixes ("Breached By..." vs "Violated By...")
                # past the visible-truncation point. The post-pilot extractor
                # pass will clean the underlying labels; this dedup prevents
                # visually-identical tensions from reaching the pilot.
                e1 = (t.get('entity1_label') or '').strip()
                e2 = (t.get('entity2_label') or '').strip()
                tkey = (
                    e1[:60].lower(),
                    e2[:60].lower(),
                    tuple(sorted(t.get('affected_role_labels') or [])),
                )
                if tkey in g['_tension_keys']:
                    continue
                g['_tension_keys'].add(tkey)
                linked = char_linked[idx] if idx < len(char_linked) else []
                g['tensions'].append({
                    'tension': t,
                    'role_suffix': role_suffix,
                    'linked_main_shorts': linked,
                })

        for g in grouped_chars.values():
            g['tensions'].sort(
                key=lambda x: x['tension'].get('intensity_score', 0),
                reverse=True,
            )
            g['professional_position'] = (
                max(g['_positions'], key=len) if g['_positions'] else ''
            )
            g['ethical_stance'] = ' '.join(g['_stances'])
            g['tension_count'] = len(g['tensions'])
            del g['_tension_keys']
            del g['_positions']
            del g['_stances']

        # Populate role_suffix_details with abstract role-class definitions
        # (rdfs:comment) from OntServe. Keyed by exact label match against
        # ontology_entities.label where entity_type='class'. Role suffixes
        # without a matching class entry (or with empty comment) are simply
        # omitted; the template renders those badges without a popover.
        all_role_suffixes = sorted({
            r for g in grouped_chars.values() for r in g['role_suffixes']
        })
        role_definitions = self._fetch_class_definitions(all_role_suffixes)
        for g in grouped_chars.values():
            g['role_suffix_details'] = {
                r: role_definitions[r]
                for r in g['role_suffixes']
                if r in role_definitions
            }

        grouped_main_characters = [g for g in grouped_chars.values() if g['is_main']]
        grouped_other_characters = [g for g in grouped_chars.values() if not g['is_main']]

        has_content = bool(characters or tensions or opening_context)

        return {
            'view_type': 'narrative',
            'has_content': has_content,
            'characters': characters,
            'tensions': tensions,
            'tensions_by_character': tensions_by_character,
            'tensions_cross_count_by_character': tensions_cross_count_by_character,
            'tensions_linked_by_character': tensions_linked_by_character,
            'unassigned_tensions': unassigned_tensions,
            'opening_context': opening_context,
            'opening_context_html': opening_context_html,
            'protagonist_label': protagonist_label,
            'character_count': len(characters),
            'grouped_main_characters': grouped_main_characters,
            'grouped_other_characters': grouped_other_characters,
            'grouped_main_character_count': len(grouped_main_characters),
            'tension_count': len(tensions),
            'rated_tension_count': rated_tension_count,
            'description': ('Characters with the ethical tensions their roles produce, '
                            'plus an opening-context account. Each character card lists '
                            'the tensions that implicate that role.'),
        }

    def get_all_views(self, case_id: int) -> Dict[str, Any]:
        """Get all five synthesis views for the study display."""
        return {
            'provisions': self.get_provisions_view(case_id),
            'qc': self.get_qc_view(case_id),
            'decisions': self.get_decisions_view(case_id),
            'timeline': self.get_timeline_view(case_id),
            'narrative': self.get_narrative_view(case_id)
        }

    def _fetch_class_definitions(self, labels: List[str]) -> Dict[str, str]:
        """Look up abstract class definitions from OntServe by label.

        Returns {label: rdfs:comment} for each label that matches a class
        entry in the OntServe `ontology_entities` table with a non-empty
        comment. Labels without a matching class (or with empty comment)
        are omitted; callers should treat absence as "no definition
        available, render the badge without a popover."

        Used by:
          - get_narrative_view: role-suffix labels (e.g. "Engineer in
            Responsible Charge") to pull proeth-core role-class definitions
            for the role-badge popovers.
          - get_provisions_view: 9-type chip labels (Obligation, Action,
            State, Principle, Role, Resource, Capability, Event,
            Constraint) to pull the proeth-core class definitions for the
            type-chip popovers.

        Single connection, single query per call. Per-instance caching is
        intentionally omitted because each view-builder method is typically
        invoked once per request; if that changes, add a dict cache keyed
        by frozenset(labels).
        """
        if not labels:
            return {}
        import psycopg2
        from app.services.ontserve_config import get_ontserve_db_config
        conn = psycopg2.connect(**get_ontserve_db_config())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT label, comment
                       FROM ontology_entities
                       WHERE entity_type = 'class'
                         AND comment IS NOT NULL
                         AND comment <> ''
                         AND label = ANY(%s)""",
                    (list(labels),),
                )
                return {row[0]: row[1] for row in cur.fetchall()}
        finally:
            conn.close()

    @staticmethod
    def _repair_paragraphs(text: str) -> str:
        """Restore paragraph structure to run-together NSPE case text.

        Some sections_dual entries arrive without `<p>` tags or whitespace
        at paragraph boundaries — e.g., "...same site.Engineer A is known...".
        This heuristic detects sentence-end + immediate uppercase preceded
        by at least four lowercase letters and inserts a paragraph break.
        The four-letter floor keeps short abbreviations (U.S., I.S.O.,
        Dr.Smith) from being split.

        Also strips trailing whitespace and collapses trailing duplicate
        periods (e.g., ". ." or "..") to a single sentence terminator;
        these occasionally appear when the source document was scraped
        from a PDF.

        If the text already contains <p>, <br>, or newline boundaries the
        paragraph-repair step is skipped but the trailing-punctuation
        cleanup still runs.
        """
        if not text:
            return text
        import re
        cleaned = re.sub(r'(?:\s*\.\s*){2,}$', '.', text.rstrip())
        if '<p' in cleaned or '<br' in cleaned or '\n' in cleaned:
            return cleaned
        repaired = re.sub(r'(?<=[a-z]{4})\.(?=[A-Z][a-z])', '.</p><p>', cleaned)
        if repaired == cleaned:
            return cleaned
        return '<p>' + repaired + '</p>'

    def get_case_facts(self, case_id: int) -> Dict[str, Any]:
        """Get case facts section only (Discussion/Conclusions withheld).

        EvaluationStudyPlan.md Appendix A: Evaluators receive the Facts section
        from NSPE Board of Ethical Review cases. Discussion and Conclusions
        sections are withheld to prevent anchoring on board reasoning.

        Uses HTML-formatted content from doc_metadata.sections_dual when available,
        which provides properly formatted text with paragraphs.
        """
        document = Document.query.get(case_id)
        if not document:
            return {'error': 'Case not found'}

        facts_content = []
        question_content = ''
        question_is_html = False
        withheld_sections = []

        # Prefer sections_dual HTML format from doc_metadata (properly formatted)
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            sections_dual = document.doc_metadata.get('sections_dual', {})
            if sections_dual:
                # Facts and Question are both shown; Discussion and Conclusion
                # remain withheld until step 4 (Reveal).
                if 'facts' in sections_dual and sections_dual['facts'].get('html'):
                    facts_content.append({
                        'type': 'facts',
                        'content': self._repair_paragraphs(sections_dual['facts']['html']),
                        'position': 0,
                        'is_html': True
                    })

                if 'question' in sections_dual and sections_dual['question'].get('html'):
                    question_content = sections_dual['question']['html']
                    question_is_html = True

                if 'references' in sections_dual:
                    withheld_sections.append('references')
                if 'discussion' in sections_dual:
                    withheld_sections.append('discussion')
                if 'conclusion' in sections_dual:
                    withheld_sections.append('conclusion')

        # Fallback to DocumentSection content if no sections_dual
        if not facts_content:
            sections = DocumentSection.query.filter_by(
                document_id=case_id
            ).order_by(
                DocumentSection.position
            ).all()

            withheld_types = ['references', 'discussion', 'conclusion', 'conclusions']

            for section in sections:
                section_type = (section.section_type or '').lower()
                if section_type == 'facts' or section_type == '':
                    facts_content.append({
                        'type': 'facts',
                        'content': section.content,
                        'position': section.position,
                        'is_html': False
                    })
                elif section_type == 'question':
                    if not question_content:
                        question_content = section.content
                        question_is_html = False
                elif section_type in withheld_types:
                    withheld_sections.append(section_type)

        # Final fallback to document content
        if not facts_content and document.content:
            content = document.content
            discussion_markers = ['Discussion:', 'DISCUSSION:', 'Conclusion:', 'CONCLUSION:']
            for marker in discussion_markers:
                if marker in content:
                    content = content.split(marker)[0]
                    break
            facts_content.append({
                'type': 'content',
                'content': content.strip(),
                'position': 0,
                'is_html': False
            })

        # Question list shown on Step 1 (Facts) and Step 2 (Views) — pulled
        # from the extracted board_explicit questions in
        # temporary_rdf_storage rather than naive `?`-split on the raw
        # text. The split heuristic produced two failure modes (verified
        # 2026-05-10 across the study pool):
        #   - Case 5: 4 raw questions, extractor captured 3 — the split
        #     showed 4 but the Q&C view showed only 3 (visible mismatch).
        #   - Case 19: a compound "...in State Q? In State Z?" question
        #     splits into an orphan "In State Z?" fragment.
        # Using the extractor's question list as the source of truth fixes
        # both: each entry is a self-contained question, and the count
        # matches the Q&C view exactly. When the extractor missed a
        # question, that is documented as an extraction-quality issue
        # (see current-application-roadmap.md).
        board_questions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question',
            is_published=True,
        ).all()
        question_list: List[str] = []
        for q in sorted(
            (q for q in board_questions
             if (q.rdf_json_ld or {}).get('questionType') == 'board_explicit'),
            key=lambda q: q.entity_label or '',
        ):
            text = (q.entity_definition or '').strip()
            if not text:
                continue
            if not text.endswith('?'):
                text = text + '?'
            question_list.append(text)

        return {
            'case_id': case_id,
            'title': document.title,
            'case_number': self._extract_case_number(document),
            'domain': 'engineering',
            'facts': facts_content,
            'question': question_content,
            'question_is_html': question_is_html,
            'question_list': question_list,
            'withheld_sections': list(set(withheld_sections)),
            'withheld_notice': (
                'This case is drawn from the NSPE Board of Ethical Review\'s '
                'published opinions. Each opinion contains four sections: '
                '<em>Facts</em>, <em>Questions</em>, <em>Discussion</em>, '
                'and <em>Conclusions</em>. The <em>Facts</em> and '
                '<em>Questions</em> are presented on this page. The Board\'s '
                'full <em>Discussion</em> is presented at the Wrap-up step. '
                'The Conclusions view in step 2 pairs each Board question '
                'with its bottom-line ruling; the underlying reasoning, '
                'cited code provisions, and historical BER case references '
                'are reserved for the Wrap-up.'
            )
        }

    def get_board_conclusions(self, case_id: int) -> Dict[str, Any]:
        """Get board conclusions for reveal after comprehension questions.

        EvaluationStudyPlan.md Appendix A: Board conclusions are revealed after
        evaluators answer comprehension questions, allowing comparison.

        Uses HTML-formatted content from doc_metadata.sections_dual when available.
        """
        document = Document.query.get(case_id)
        if not document:
            return {'error': 'Case not found'}

        discussion_text = ''
        conclusion_text = ''
        is_html = False

        # Prefer sections_dual HTML format from doc_metadata
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            sections_dual = document.doc_metadata.get('sections_dual', {})
            if sections_dual:
                if 'discussion' in sections_dual and sections_dual['discussion'].get('html'):
                    discussion_text = self._repair_paragraphs(sections_dual['discussion']['html'])
                    is_html = True
                if 'conclusion' in sections_dual and sections_dual['conclusion'].get('html'):
                    conclusion_text = self._repair_paragraphs(sections_dual['conclusion']['html'])
                    is_html = True

        # Fallback to DocumentSection content
        if not discussion_text and not conclusion_text:
            sections = DocumentSection.query.filter_by(
                document_id=case_id
            ).filter(
                DocumentSection.section_type.in_(['discussion', 'conclusion', 'conclusions'])
            ).order_by(
                DocumentSection.position
            ).all()

            for section in sections:
                section_type = (section.section_type or '').lower()
                if section_type == 'discussion':
                    discussion_text = section.content
                elif section_type in ['conclusion', 'conclusions']:
                    conclusion_text = section.content

        # Get board-cited provisions from extraction
        board_provisions = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        ).filter(
            TemporaryRDFStorage.is_published == True
        ).all()

        cited_provisions = [
            {'code_section': p.entity_label, 'text': p.entity_definition}
            for p in board_provisions
        ]

        return {
            'case_id': case_id,
            'title': document.title,
            'discussion': discussion_text,
            'conclusion': conclusion_text,
            'is_html': is_html,
            'cited_provisions': cited_provisions,
            'reveal_notice': 'The board\'s reasoning is now revealed. Compare your '
                            'comprehension answers to the board\'s conclusions.'
        }

    def case_has_synthesis(self, case_id: int, require_complete: bool = True) -> bool:
        """Check if a case has sufficient synthesis data for study display.

        Args:
            case_id: Document ID to check
            require_complete: If True, require all five views (Provisions, Q&C,
                            Decisions, Timeline, Narrative). If False, only
                            require Provisions and Q&C.
        """
        # Provisions
        provision_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference',
            is_published=True
        ).count()

        # Q&C (questions)
        question_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question',
            is_published=True
        ).count()

        if provision_count == 0 or question_count == 0:
            return False

        if not require_complete:
            return True

        # Decisions - ExtractionPrompt or TemporaryRDFStorage
        decision_count = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase3_decision_synthesis'
        ).count()

        if decision_count == 0:
            decision_count = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point'
            ).count()

        # Timeline (Step 3 temporal extraction)
        timeline_count = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).count()

        # Narrative (Step 4 Phase 4)
        narrative_count = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).count()

        return decision_count > 0 and timeline_count > 0 and narrative_count > 0

    def get_evaluable_cases(self, domain: Optional[str] = None, require_complete: bool = True) -> List[Dict[str, Any]]:
        """Get list of cases that have synthesis data and are ready for the study.

        Args:
            domain: Domain filter (currently unused - IRB scope is engineering only)
            require_complete: If True, only return cases with all 5 synthesis views.

        The 23-case IRB-approved study pool lives in
        `app.config.study_case_pool.STUDY_CASE_POOL_IDS`. Intersect with cases
        that pass the synthesis check. In practice all 23 should pass because
        the pool was selected from cases with full-prompt extraction and
        downstream synthesis.
        """
        from app.config.study_case_pool import STUDY_CASE_POOL_IDS

        cases = Document.query.filter(
            Document.id.in_(STUDY_CASE_POOL_IDS)
        ).all()

        evaluable = []
        for case in cases:
            if self.case_has_synthesis(case.id, require_complete=require_complete):
                views = self.get_all_views(case.id)
                case_number = self._extract_case_number(case)
                evaluable.append({
                    'id': case.id,
                    'title': case.title,
                    'case_number': case_number,
                    'domain': 'engineering',
                    'provision_count': views['provisions']['count'],
                    'qc_count': views['qc']['count'],
                    'decision_count': views['decisions']['count'],
                    'timeline_count': views['timeline']['count'],
                    'has_narrative': views['narrative']['has_content']
                })

        return evaluable

    def _extract_case_number(self, document: Document) -> str:
        """Extract case number from document metadata or title."""
        # Check metadata first
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            if 'case_number' in document.doc_metadata:
                return document.doc_metadata['case_number']

        # Try to extract from title (e.g., "BER Case 57-8")
        import re
        match = re.search(r'(?:Case|BER)\s*(\d+[-\d]*)', document.title, re.IGNORECASE)
        if match:
            return match.group(1)

        # Fall back to document ID
        return str(document.id)
