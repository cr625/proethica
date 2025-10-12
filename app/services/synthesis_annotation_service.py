"""
Synthesis Annotation Service

Generates annotations for Step 4 synthesis artifacts (questions, conclusions, provisions)
showing where they appear in the case text and what entities they reference.

This makes the synthesis reviewable by highlighting the evidence in context.
"""

import logging
import re
from typing import List, Dict, Tuple
from app import db
from app.models.document_concept_annotation import DocumentConceptAnnotation
from app.models import Document
from app.models.temporary_rdf_storage import TemporaryRDFStorage

logger = logging.getLogger(__name__)


class SynthesisAnnotationService:
    """
    Generates annotations showing where synthesis artifacts appear in case text.

    Unlike ontology annotations (which mark concept definitions), synthesis annotations
    mark:
    - Questions and their entity mentions
    - Conclusions and their provision citations
    - Provisions and where they're referenced
    - Cross-references between synthesis elements
    """

    def __init__(self, case_id: int):
        self.case_id = case_id
        self.case = Document.query.get(case_id)
        if not self.case:
            raise ValueError(f"Case {case_id} not found")

        # Get case sections
        self.sections = self._extract_sections()

    def _extract_sections(self) -> Dict[str, Dict]:
        """Extract case sections with text and offsets."""
        sections = {}

        if not self.case.doc_metadata:
            return sections

        sections_dual = self.case.doc_metadata.get('sections_dual', {})

        for section_key, section_data in sections_dual.items():
            if isinstance(section_data, dict):
                sections[section_key] = {
                    'text': section_data.get('text', ''),
                    'html': section_data.get('html', '')
                }
            else:
                sections[section_key] = {
                    'text': str(section_data),
                    'html': ''
                }

        return sections

    def generate_all_synthesis_annotations(self) -> Dict:
        """
        Generate all synthesis annotations for this case.

        Returns:
            Dict with counts of annotations created
        """
        logger.info(f"Generating synthesis annotations for case {self.case_id}")

        # Clear existing synthesis annotations
        DocumentConceptAnnotation.query.filter_by(
            document_type='case',
            document_id=self.case_id,
            ontology_name='step4_synthesis'
        ).delete(synchronize_session=False)

        counts = {
            'questions': 0,
            'conclusions': 0,
            'provisions': 0,
            'entity_mentions': 0,
            'total': 0
        }

        # 1. Annotate questions and their entity mentions
        counts['questions'] = self._annotate_questions()

        # 2. Annotate conclusions and provision citations
        counts['conclusions'] = self._annotate_conclusions()

        # 3. Annotate provision references in case text
        counts['provisions'] = self._annotate_provisions()

        # 4. Annotate entity mentions from synthesis
        counts['entity_mentions'] = self._annotate_entity_mentions()

        counts['total'] = sum([
            counts['questions'],
            counts['conclusions'],
            counts['provisions'],
            counts['entity_mentions']
        ])

        db.session.commit()

        logger.info(f"Created {counts['total']} synthesis annotations for case {self.case_id}")
        return counts

    def _annotate_questions(self) -> int:
        """Annotate ethical questions in the Questions section."""
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=self.case_id,
            extraction_type='ethical_question'
        ).all()

        if not questions:
            return 0

        # Get questions section
        questions_section = self.sections.get('question', {})
        questions_text = questions_section.get('text', '')

        if not questions_text:
            return 0

        count = 0
        for question in questions:
            q_text = question.entity_definition
            if not q_text:
                continue

            # Find question text in section
            matches = self._find_text_spans(q_text, questions_text, fuzzy=True)

            for start, end in matches:
                # Create annotation for the question itself
                annotation = DocumentConceptAnnotation(
                    document_type='case',
                    document_id=self.case_id,
                    text_segment=questions_text[start:end][:500],
                    start_offset=start,
                    end_offset=end,
                    ontology_name='step4_synthesis',
                    ontology_version='1.0',
                    concept_uri=f"case{self.case_id}#questions#{question.id}",
                    concept_label=question.entity_label,
                    concept_definition=question.entity_definition,
                    concept_type='question',
                    confidence=0.9,
                    llm_model='synthesis',
                    llm_reasoning=f"Ethical question from Step 4 synthesis with {len(question.rdf_json_ld.get('mentionedEntities', []))} entity mentions",
                    approval_stage='synthesis_generated',
                    validation_status='approved'
                )
                db.session.add(annotation)
                count += 1

        return count

    def _annotate_conclusions(self) -> int:
        """Annotate board conclusions in the Conclusion section."""
        conclusions = TemporaryRDFStorage.query.filter_by(
            case_id=self.case_id,
            extraction_type='ethical_conclusion'
        ).all()

        if not conclusions:
            return 0

        # Get conclusion section
        conclusion_section = self.sections.get('conclusion', {})
        conclusion_text = conclusion_section.get('text', '')

        if not conclusion_text:
            return 0

        count = 0
        for conclusion in conclusions:
            c_text = conclusion.entity_definition
            if not c_text:
                continue

            # Find conclusion text in section
            matches = self._find_text_spans(c_text, conclusion_text, fuzzy=True)

            for start, end in matches:
                # Get provision citations
                provisions = conclusion.rdf_json_ld.get('citedProvisions', [])
                provisions_str = ', '.join(provisions) if provisions else 'none'

                # Create annotation for the conclusion
                annotation = DocumentConceptAnnotation(
                    document_type='case',
                    document_id=self.case_id,
                    text_segment=conclusion_text[start:end][:500],
                    start_offset=start,
                    end_offset=end,
                    ontology_name='step4_synthesis',
                    ontology_version='1.0',
                    concept_uri=f"case{self.case_id}#conclusions#{conclusion.id}",
                    concept_label=conclusion.entity_label,
                    concept_definition=conclusion.entity_definition,
                    concept_type='conclusion',
                    confidence=0.9,
                    llm_model='synthesis',
                    llm_reasoning=f"Board conclusion citing provisions: {provisions_str}",
                    approval_stage='synthesis_generated',
                    validation_status='approved'
                )
                db.session.add(annotation)
                count += 1

        return count

    def _annotate_provisions(self) -> int:
        """Annotate NSPE provision references throughout the case."""
        provisions = TemporaryRDFStorage.query.filter_by(
            case_id=self.case_id,
            extraction_type='code_provision_reference'
        ).all()

        if not provisions:
            return 0

        count = 0

        # Search all sections for provision codes
        for provision in provisions:
            prov_code = provision.rdf_json_ld.get('codeProvision', '')
            if not prov_code:
                continue

            # Search each section for this provision code
            for section_name, section_data in self.sections.items():
                section_text = section_data['text']

                # Find provision code mentions (e.g., "I.1", "II.1.a")
                pattern = re.escape(prov_code)
                matches = [(m.start(), m.end()) for m in re.finditer(pattern, section_text, re.IGNORECASE)]

                for start, end in matches:
                    # Get context around the provision code
                    context_start = max(0, start - 50)
                    context_end = min(len(section_text), end + 50)
                    context = section_text[context_start:context_end]

                    annotation = DocumentConceptAnnotation(
                        document_type='case',
                        document_id=self.case_id,
                        text_segment=context[:500],
                        start_offset=start,
                        end_offset=end,
                        ontology_name='step4_synthesis',
                        ontology_version='1.0',
                        concept_uri=f"case{self.case_id}#provisions#{provision.id}",
                        concept_label=provision.entity_label,
                        concept_definition=provision.entity_definition,
                        concept_type='provision',
                        confidence=1.0,  # Exact match
                        llm_model='synthesis',
                        llm_reasoning=f"NSPE provision {prov_code} referenced in {section_name} section",
                        approval_stage='synthesis_generated',
                        validation_status='approved'
                    )
                    db.session.add(annotation)
                    count += 1

        return count

    def _annotate_entity_mentions(self) -> int:
        """Annotate entity mentions from synthesis in Facts/Discussion sections."""
        # Get questions to find their mentioned entities
        questions = TemporaryRDFStorage.query.filter_by(
            case_id=self.case_id,
            extraction_type='ethical_question'
        ).all()

        # Collect all mentioned entity labels from nested structure
        # mentionedEntities is a dict like: {"roles": [], "actions": ["Action1", "Action2"], ...}
        entity_labels = set()
        for question in questions:
            mentioned = question.rdf_json_ld.get('mentionedEntities', {})

            if isinstance(mentioned, dict):
                # Parse nested structure by entity type
                for entity_type, entities_list in mentioned.items():
                    if isinstance(entities_list, list):
                        entity_labels.update(entities_list)
            elif isinstance(mentioned, list):
                # Fallback for simple list format
                entity_labels.update(mentioned)

        if not entity_labels:
            logger.info(f"No entity labels found in questions for case {self.case_id}")
            return 0

        logger.info(f"Found {len(entity_labels)} unique entity labels to annotate: {entity_labels}")

        # Get the actual entity objects
        entities = TemporaryRDFStorage.query.filter_by(
            case_id=self.case_id,
            storage_type='individual'
        ).filter(
            TemporaryRDFStorage.entity_label.in_(entity_labels)
        ).all()

        count = 0

        # Search Facts and Discussion sections for entity labels
        search_sections = ['facts', 'discussion']

        for entity in entities:
            entity_label = entity.entity_label
            if not entity_label:
                continue

            for section_name in search_sections:
                section_data = self.sections.get(section_name, {})
                section_text = section_data.get('text', '')

                if not section_text:
                    continue

                # Find entity label in text
                matches = self._find_text_spans(entity_label, section_text, fuzzy=False)

                for start, end in matches:
                    context_start = max(0, start - 30)
                    context_end = min(len(section_text), end + 30)
                    context = section_text[context_start:context_end]

                    annotation = DocumentConceptAnnotation(
                        document_type='case',
                        document_id=self.case_id,
                        text_segment=context[:500],
                        start_offset=start,
                        end_offset=end,
                        ontology_name='step4_synthesis',
                        ontology_version='1.0',
                        concept_uri=entity.entity_uri or f"case{self.case_id}#entity#{entity.id}",
                        concept_label=entity.entity_label,
                        concept_definition=entity.entity_definition,
                        concept_type=f"entity_{entity.entity_type}",
                        confidence=0.85,
                        llm_model='synthesis',
                        llm_reasoning=f"{entity.entity_type.title()} mentioned in question analysis, found in {section_name}",
                        approval_stage='synthesis_generated',
                        validation_status='approved'
                    )
                    db.session.add(annotation)
                    count += 1

        return count

    def _find_text_spans(self, search_text: str, full_text: str, fuzzy: bool = False) -> List[Tuple[int, int]]:
        """
        Find all occurrences of search_text in full_text.

        Args:
            search_text: Text to search for
            full_text: Text to search in
            fuzzy: If True, allow partial matches (first 50 chars)

        Returns:
            List of (start, end) tuples
        """
        spans = []

        if fuzzy:
            # For long text, search for first meaningful chunk
            search_chunk = search_text[:min(100, len(search_text))].strip()
            if len(search_chunk) < 20:
                search_chunk = search_text[:200].strip()
        else:
            search_chunk = search_text

        # Find all occurrences
        start_pos = 0
        while True:
            pos = full_text.find(search_chunk, start_pos)
            if pos == -1:
                break

            end_pos = pos + len(search_chunk)
            spans.append((pos, end_pos))
            start_pos = pos + 1

        return spans

    def get_synthesis_annotation_stats(self) -> Dict:
        """Get statistics about synthesis annotations for this case."""
        annotations = DocumentConceptAnnotation.query.filter_by(
            document_type='case',
            document_id=self.case_id,
            ontology_name='step4_synthesis',
            is_current=True
        ).all()

        stats = {
            'total': len(annotations),
            'by_type': {},
            'by_section': {}
        }

        for ann in annotations:
            # Count by type
            concept_type = ann.concept_type
            stats['by_type'][concept_type] = stats['by_type'].get(concept_type, 0) + 1

        return stats
