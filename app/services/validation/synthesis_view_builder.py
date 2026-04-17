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

        formatted = []
        for prov in provisions:
            rdf_data = prov.rdf_json_ld or {}
            formatted.append({
                'id': prov.id,
                'code_section': prov.entity_label,
                'provision_text': prov.entity_definition,
                'iao_label': prov.iao_document_label,
                'applies_to': rdf_data.get('appliesTo', []),
                'case_excerpt': rdf_data.get('relevantExcerpt', ''),
                'confidence': prov.match_confidence or 0.0
            })

        return {
            'view_type': 'provisions',
            'count': len(formatted),
            'provisions': formatted,
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

        # Build conclusion lookup by question
        conclusion_map = {}
        for conc in conclusions:
            rdf_data = conc.rdf_json_ld or {}
            answers = rdf_data.get('answersQuestions', [])
            for q_ref in answers:
                if q_ref not in conclusion_map:
                    conclusion_map[q_ref] = []
                conclusion_map[q_ref].append({
                    'id': conc.id,
                    'label': conc.entity_label,
                    'text': conc.entity_definition,
                    'cited_provisions': rdf_data.get('citedProvisions', [])
                })

        formatted = []
        for q in questions:
            rdf_data = q.rdf_json_ld or {}
            q_number = q.entity_label  # e.g., "Q1"
            formatted.append({
                'id': q.id,
                'number': q_number,
                'question_text': q.entity_definition,
                'question_type': rdf_data.get('questionType', 'board_explicit'),
                'related_provisions': rdf_data.get('relatedProvisions', []),
                'mentioned_entities': rdf_data.get('mentionedEntities', {}),
                'linked_conclusions': conclusion_map.get(q_number, [])
            })

        return {
            'view_type': 'qc',
            'count': len(formatted),
            'questions': formatted,
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
                # Strip markdown code fences if present
                response_text = phase3_prompt.raw_response.strip()
                if response_text.startswith('```'):
                    # Remove opening fence (```json or ```)
                    lines = response_text.split('\n', 1)
                    if len(lines) > 1:
                        response_text = lines[1]
                    # Remove closing fence
                    if response_text.rstrip().endswith('```'):
                        response_text = response_text.rstrip()[:-3].rstrip()

                raw = json.loads(response_text)
                if isinstance(raw, list):
                    decisions = raw
                elif isinstance(raw, dict):
                    decisions = raw.get('decision_points', [])
            except json.JSONDecodeError:
                pass

        # Also check TemporaryRDFStorage for decision points
        # Note: Decisions are synthesized output, not reviewed entities,
        # so we don't require is_published=True like we do for provisions
        if not decisions:
            decision_entities = TemporaryRDFStorage.query.filter_by(
                case_id=case_id,
                extraction_type='canonical_decision_point'
            ).all()

            for de in decision_entities:
                rdf_data = de.rdf_json_ld or {}
                decisions.append({
                    'focus_id': de.entity_label,
                    'description': de.entity_definition,
                    'decision_question': rdf_data.get('decisionQuestion', ''),
                    'obligations_in_tension': rdf_data.get('obligationsInTension', []),
                    'alternatives': rdf_data.get('alternatives', []),
                    'arguments': rdf_data.get('arguments', {})
                })

        return {
            'view_type': 'decisions',
            'count': len(decisions),
            'decisions': decisions,
            'description': 'Decision points where the professional faced choices, along with '
                          'alternatives considered and actions taken.'
        }

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
        temporal_entries = TemporaryRDFStorage.query.filter_by(
            case_id=case_id,
            extraction_type='temporal_dynamics_enhanced'
        ).order_by(
            TemporaryRDFStorage.id  # Preserves extraction order (no reliable temporal sort key)
        ).all()

        entries = []
        causal_flow = []
        decision_point_entries = 0

        for seq, row in enumerate(temporal_entries, start=1):
            rdf = row.rdf_json_ld or {}
            at_type = rdf.get('@type', '') or ''
            kind = 'action' if 'Action' in at_type else 'event' if 'Event' in at_type else 'entry'
            is_dp = bool(rdf.get('proeth-scenario:isDecisionPoint'))
            alternatives = rdf.get('proeth-scenario:alternativeActions', []) or []

            fulfills = rdf.get('proeth:fulfillsObligation', []) or []
            violates = rdf.get('proeth:violatesObligation', []) or []

            entry = {
                'sequence': seq,
                'kind': kind,
                'label': row.entity_label,
                'entity_iri': rdf.get('@id', ''),
                'temporal_marker': rdf.get('proeth:temporalMarker', ''),
                'agent': rdf.get('proeth:hasAgent', ''),
                'narrative_role': rdf.get('proeth-scenario:narrativeRole', ''),
                'description': rdf.get('proeth:description', ''),
                'is_decision_point': is_dp,
                'alternative_count': len(alternatives) if isinstance(alternatives, list) else 0,
                'fulfills_obligations': fulfills if isinstance(fulfills, list) else [],
                'violates_obligations': violates if isinstance(violates, list) else [],
            }
            entries.append(entry)
            if is_dp:
                decision_point_entries += 1

            foreseen = rdf.get('proeth:foreseenUnintendedEffects', [])
            if isinstance(foreseen, list):
                for effect in foreseen:
                    causal_flow.append({
                        'from_label': row.entity_label,
                        'to_label': effect,
                        'relation': 'enables'
                    })

        return {
            'view_type': 'timeline',
            'count': len(entries),
            'decision_point_count': decision_point_entries,
            'entries': entries,
            'causal_flow': causal_flow,
            'description': 'Actions and Events in temporal sequence with decision points '
                          'nested beneath their corresponding entries; causal flow shows '
                          'enables links between actions and events.'
        }

    def get_narrative_view(self, case_id: int) -> Dict[str, Any]:
        """Get narrative elements from Step 4 Phase 4.

        Returns narrative with:
        - Characters (protagonist, stakeholders)
        - Timeline events
        - Initial fluents (starting conditions)
        - Scenario seeds
        """
        # Get Phase 4 narrative from ExtractionPrompt
        phase4_prompt = ExtractionPrompt.query.filter_by(
            case_id=case_id,
            concept_type='phase4_narrative'
        ).order_by(
            ExtractionPrompt.created_at.desc()
        ).first()

        narrative = {}
        if phase4_prompt and phase4_prompt.raw_response:
            try:
                narrative = json.loads(phase4_prompt.raw_response)
            except json.JSONDecodeError:
                pass

        # Extract key narrative components with defaults
        characters = narrative.get('characters', [])
        timeline = narrative.get('timeline', narrative.get('events', []))
        initial_fluents = narrative.get('initial_fluents', [])
        scenarios = narrative.get('scenarios', narrative.get('scenario_seeds', []))

        return {
            'view_type': 'narrative',
            'has_content': bool(narrative),
            'characters': characters,
            'timeline': timeline,
            'initial_fluents': initial_fluents,
            'scenarios': scenarios,
            'description': 'Case timeline, participant profiles, and relationship networks '
                          'generated through semantic representation.'
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

    def get_case_facts(self, case_id: int) -> Dict[str, Any]:
        """Get case facts section only (Discussion/Conclusions withheld).

        Chapter 4 Section 4.3.1: Evaluators receive the Facts section from NSPE
        Board of Ethical Review cases. Discussion and Conclusions sections are
        withheld to prevent anchoring on board reasoning.

        Uses HTML-formatted content from doc_metadata.sections_dual when available,
        which provides properly formatted text with paragraphs.
        """
        document = Document.query.get(case_id)
        if not document:
            return {'error': 'Case not found'}

        facts_content = []
        withheld_sections = []

        # Prefer sections_dual HTML format from doc_metadata (properly formatted)
        if document.doc_metadata and isinstance(document.doc_metadata, dict):
            sections_dual = document.doc_metadata.get('sections_dual', {})
            if sections_dual:
                # Facts section only - other sections are withheld for validation
                if 'facts' in sections_dual and sections_dual['facts'].get('html'):
                    facts_content.append({
                        'type': 'facts',
                        'content': sections_dual['facts']['html'],
                        'position': 0,
                        'is_html': True
                    })

                # Track withheld sections (question, references, discussion, conclusion)
                if 'question' in sections_dual:
                    withheld_sections.append('question')
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

            # Only include facts section - all others are withheld
            withheld_types = ['question', 'references', 'discussion', 'conclusion', 'conclusions']

            for section in sections:
                section_type = (section.section_type or '').lower()
                if section_type == 'facts' or section_type == '':
                    # Include facts and unlabeled sections
                    facts_content.append({
                        'type': 'facts',
                        'content': section.content,
                        'position': section.position,
                        'is_html': False
                    })
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

        return {
            'case_id': case_id,
            'title': document.title,
            'case_number': self._extract_case_number(document),
            'domain': 'engineering',
            'facts': facts_content,
            'withheld_sections': list(set(withheld_sections)),
            'withheld_notice': 'The board\'s Questions, Discussion, and Conclusions are withheld '
                              'until after you complete the comprehension questions.'
        }

    def get_board_conclusions(self, case_id: int) -> Dict[str, Any]:
        """Get board conclusions for reveal after comprehension questions.

        Chapter 4 Section 4.3.2 Part 2: Board conclusions are revealed after
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
                    discussion_text = sections_dual['discussion']['html']
                    is_html = True
                if 'conclusion' in sections_dual and sections_dual['conclusion'].get('html'):
                    conclusion_text = sections_dual['conclusion']['html']
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
