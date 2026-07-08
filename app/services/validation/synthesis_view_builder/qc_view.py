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
