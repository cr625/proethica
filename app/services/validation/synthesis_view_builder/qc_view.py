"""Questions & Conclusions (Q&C) synthesis view for the user-study interface.

QCViewMixin: get_qc_view plus the get_questions_view alias. Relocated verbatim
from builder.py; SynthesisViewBuilder inherits this mixin, so self. resolution
(sibling methods + the shared _fetch_class_definitions / _repair_paragraphs that
stay on the core class) is preserved via MRO.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.models import TemporaryRDFStorage


class QCViewMixin:
    """The Q&C synthesis view for SynthesisViewBuilder."""


    def get_qc_view(self, case_id: int) -> Dict[str, Any]:
        """Get Q&C (Questions and Conclusions) view from Step 4 Phase 2B.

        Returns questions linked to their board/analytical conclusions with:
        - Question text and type classification
        - Conclusions linked to each question via answersQuestions relation
        - Entity involvement breakdown and emergence/resolution overlays
        """
        questions = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question'
        )).order_by(
            TemporaryRDFStorage.entity_label
        ).all()

        # Also get conclusions for linking
        conclusions = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        )).all()

        # Resolution patterns (Step 4 Phase 2B) carry the board's weighing
        # process per conclusion. Deliberately NOT wrapped in
        # _published_filter: resolution_pattern rows stay unpublished even on
        # committed cases (verified is_published=false corpus-wide), so the
        # study-mode gate would blank the resolution surface over correct
        # data. This mirrors the timeline mixin's unfiltered temporal query.
        rp_rows = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='resolution_pattern'
        ).order_by(TemporaryRDFStorage.id).all()

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
        provisions_rows = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        )).all()
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
        # Raw-spelling aliases: citations arrive as 'II.1.c.', 'NSPE I.1',
        # 'I.1 Public Welfare Paramount' etc. (24 of 42 codes carried more
        # than one spelling in the 2026-07-08 Provisions census) while the
        # lookup keys are the canonical forms above. Index every entry under
        # its normalized code, then alias each cited raw form to it so the
        # template's raw-key lookups resolve.
        from app.utils.provision_codes import normalize_provision_code
        normalized_lookup = {}
        for k, v in list(provision_text_lookup.items()):
            nk = normalize_provision_code(k)
            if nk:
                normalized_lookup.setdefault(nk, v)
        for c in conclusions:
            rdf = c.rdf_json_ld if isinstance(c.rdf_json_ld, dict) else {}
            for cp in rdf.get('citedProvisions') or []:
                if cp and cp not in provision_text_lookup:
                    t = normalized_lookup.get(normalize_provision_code(cp) or '')
                    if t:
                        provision_text_lookup[cp] = t
        # Resolution patterns cite provisions under their own raw spellings
        # ('I.1.', 'III.8.'); alias those too so the resolution provision
        # chips resolve in the same lookup.
        for r in rp_rows:
            rdf = r.rdf_json_ld if isinstance(r.rdf_json_ld, dict) else {}
            for cp in rdf.get('cited_provisions') or []:
                if cp and cp not in provision_text_lookup:
                    t = normalized_lookup.get(normalize_provision_code(cp) or '')
                    if t:
                        provision_text_lookup[cp] = t

        # Join resolution patterns to conclusions through qc_refs. Stored
        # conclusion_uri keys arrive in the committed-URI form
        # ('case-9#Conclusion_1', all gold stores) or the legacy positional
        # form ('case-11#C1'); BOTH sides normalize through key_aliases with
        # aliases.get(k, k), or a mixed-generation store silently stops
        # joining (the c422755 finding). The reference list enumerates ALL
        # conclusion rows in id order (the alias-defining enumeration),
        # independent of the published filter above. Rows without a
        # conclusion_uri (case 4 carries three) anchor to nothing and are
        # skipped.
        from app.services.step4_synthesis.qc_refs import conclusion_refs, key_aliases
        conc_rows_all = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_conclusion'
        ).order_by(TemporaryRDFStorage.id).all()
        conc_refs = conclusion_refs(case_id, rows=conc_rows_all)
        aliases = key_aliases(conc_refs, 'C')
        canon_by_conc_id = {
            row.id: aliases.get(ref['uri'] or '', ref['uri'] or '')
            for row, ref in zip(conc_rows_all, conc_refs)
        }
        resolution_by_canon: Dict[str, Dict[str, Any]] = {}
        for r in rp_rows:
            rdf = r.rdf_json_ld if isinstance(r.rdf_json_ld, dict) else {}
            raw_key = (rdf.get('conclusion_uri') or '').strip()
            if not raw_key:
                continue
            resolution_by_canon[aliases.get(raw_key, raw_key)] = {
                'weighing_process': rdf.get('weighing_process') or '',
                'determinative_principles': rdf.get('determinative_principles') or [],
                'determinative_facts': rdf.get('determinative_facts') or [],
                'resolution_conditions': rdf.get('resolution_conditions') or '',
                'resolution_narrative': rdf.get('resolution_narrative') or '',
                'confidence': rdf.get('confidence'),
                'cited_provisions': rdf.get('cited_provisions') or [],
            }

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
                'resolution': resolution_by_canon.get(canon_by_conc_id.get(conc.id, '')),
            })

        # Secondary linkages: conclusions whose answersQuestions cites this
        # question after its primary target. The primary-only conclusion_map
        # (the case-5 fix) is correct for full-text embedding, but it made
        # discussed-but-not-primarily-answered questions look unanswered
        # (2026-07-08 census: theoretical 54/59 addressed by some conclusion,
        # 13/59 shown). These render as reference chips, never embedded text.
        secondary_map: Dict[str, list] = {}
        for conc in conclusions:
            rdf_data = conc.rdf_json_ld or {}
            answers = rdf_data.get('answersQuestions', []) or []
            for a in answers[1:]:
                key = f"Question_{a}" if isinstance(a, int) else str(a)
                secondary_map.setdefault(key, []).append({
                    'label': conc.entity_label,
                    'text': conc.entity_definition,
                })

        formatted = []
        for q in questions:
            rdf_data = q.rdf_json_ld or {}
            q_number = q.entity_label  # e.g., "Question_1"
            # Real parent linkage only: sourceQuestion is the board question
            # the LLM generated this analytical question FROM (persisted since
            # 2026-07-08; older rows lack it). The former number-offset
            # heuristic (parent = n // 100) read a CATEGORY code as a parent
            # pointer -- analytical numbering is implicit=101+, tension=201+,
            # theoretical=301+, counterfactual=401+ -- so implicit questions
            # always nested under Q1 and case 16's counterfactuals nested
            # under board Q4 spuriously. Do not reintroduce it.
            source_q = rdf_data.get('sourceQuestion')
            parent = f"Question_{source_q}" if isinstance(source_q, int) and source_q > 0 else None
            formatted.append({
                'id': q.id,
                'number': q_number,
                'question_text': q.entity_definition,
                'question_type': rdf_data.get('questionType', 'board_explicit'),
                'parent_question': parent,
                'ethical_framework': rdf_data.get('ethicalFramework'),
                'related_provisions': rdf_data.get('relatedProvisions', []),
                'mentioned_entities': rdf_data.get('mentionedEntities', {}),
                'linked_conclusions': conclusion_map.get(q_number, []),
                'secondary_conclusions': secondary_map.get(q_number, []),
            })

        # Build grouped structure: board questions with their sub-questions,
        # split into analytical (implicit, principle_tension) and theory
        # (theoretical, counterfactual) groups for progressive disclosure.
        # Sub-questions without a persisted sourceQuestion parent go to the
        # type-grouped analytical section (cross_cutting key kept for the
        # template contract).
        board_questions = [q for q in formatted if q['question_type'] == 'board_explicit']
        board_numbers = {q['number'] for q in board_questions}
        analytical_by_parent: Dict[str, list] = {}
        theory_by_parent: Dict[str, list] = {}
        cross_cutting: list = []
        for q in formatted:
            if q['question_type'] == 'board_explicit':
                continue
            parent = q.get('parent_question')
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
