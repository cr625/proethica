"""Source-document synthesis views for the user-study interface.

SourceViewsMixin: the views that present case source material rather than a
synthesized analysis -- get_provisions_view (NSPE provisions), get_case_facts,
and get_board_conclusions. Relocated verbatim from builder.py; SynthesisViewBuilder
inherits this mixin, so the shared helpers that stay on the core class
(_fetch_class_definitions, _repair_paragraphs) resolve via MRO.
"""
from __future__ import annotations

from typing import Any, Dict, List

from app.models import Document, TemporaryRDFStorage
from app.models.document_section import DocumentSection


class SourceViewsMixin:
    """Provisions / facts / board-conclusions source views."""


    def get_provisions_view(self, case_id: int) -> Dict[str, Any]:
        """Get code provision mappings from Step 4 Phase 2A.

        Returns provisions with:
        - Code section identifiers (e.g., "II.4.a")
        - Full provision text
        - Relevant case excerpts
        - Entity connections (appliesTo relationships)
        """
        provisions = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        )).order_by(
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

        # Provenance harmonization (provisions-harmonization.md decision 3):
        # each provision is board-stated (in the case's parsed references
        # section), analysis-found (Step-4 extraction only), or both. The
        # display is the UNION -- board-stated provisions the extraction
        # missed still appear, marked accordingly.
        from flask import current_app
        from app.utils.provision_codes import (normalize_provision_code,
                                               nspe_provision_fragment,
                                               provision_display_code)
        doc = Document.query.get(case_id)
        board_refs = ((doc.doc_metadata or {}).get('provision_references')
                      if doc else None) or []
        board_by_code = {r['code']: r for r in board_refs if r.get('code')}
        ontserve_base = current_app.config.get('ONTSERVE_WEB_URL',
                                               'http://localhost:5003')

        def _ontserve_url(code):
            frag = nspe_provision_fragment(code)
            return (f"{ontserve_base}/entity/NSPE Code of Ethics/{frag}"
                    if frag else None)

        formatted = []
        seen_codes = set()
        for prov in provisions:
            rdf_data = prov.rdf_json_ld or {}
            applies_to = rdf_data.get('appliesTo', []) or []
            code = normalize_provision_code(prov.entity_label)
            if code:
                seen_codes.add(code)
            formatted.append({
                'id': prov.id,
                'code_section': prov.entity_label,
                # Identifier-cased display form ('II.3.a'), matching the
                # OntServe citation surfaces; raw spelling kept as fallback.
                'display_code': provision_display_code(prov.entity_label)
                                or prov.entity_label,
                'code': code,
                'provenance': 'both' if code in board_by_code else 'analysis',
                'ontserve_url': _ontserve_url(code) if code else None,
                'provision_text': prov.entity_definition,
                'iao_label': prov.iao_document_label,
                'applies_to': applies_to,
                'top_mappings': _top_mappings(applies_to, max_n=3),
                'case_excerpt': rdf_data.get('relevantExcerpt', ''),
                'confidence': prov.match_confidence or 0.0
            })
        for code, ref in board_by_code.items():
            if code in seen_codes:
                continue
            formatted.append({
                'id': None,
                'code_section': code,
                'display_code': provision_display_code(code) or code,
                'code': code,
                'provenance': 'board',
                'ontserve_url': _ontserve_url(code),
                'provision_text': ref.get('text', ''),
                'iao_label': None,
                'applies_to': [],
                'top_mappings': [],
                'case_excerpt': '',
                'confidence': 1.0
            })
        formatted.sort(key=lambda p: (p['code'] or p['code_section'] or ''))

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
        board_questions = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='ethical_question',
        )).all()
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
        board_provisions = self._published_filter(TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='code_provision_reference'
        )).all()

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
