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

import re
from typing import Dict, List, Optional, Any
from app.models import Document, TemporaryRDFStorage
from app.models.extraction_prompt import ExtractionPrompt

from .narrative_view import NarrativeViewMixin
from .qc_view import QCViewMixin
from .decisions_view import DecisionsViewMixin
from .timeline_view import TimelineViewMixin
from .source_views import SourceViewsMixin


class SynthesisViewBuilder(
    NarrativeViewMixin,
    QCViewMixin,
    DecisionsViewMixin,
    TimelineViewMixin,
    SourceViewsMixin,
):
    """Build synthesis views for the user-study interface.

    Pulls synthesis data from existing Step 4 pipeline outputs stored in:
    - TemporaryRDFStorage: Entity-level extractions (Step 3 + Step 4 Phase 2)
    - ExtractionPrompt: LLM synthesis outputs (Step 4 Phase 3 + Phase 4)
    - DocumentSection: Case text sections
    """


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
