"""Case viewing routes."""

import logging
from flask import render_template, redirect, url_for, flash
from app.utils.environment_auth import auth_optional
from app.models import Document
from app.models.world import World
from app.services.entity_triple_service import EntityTripleService
from app.services.pipeline_status_service import PipelineStatusService
from app import db

logger = logging.getLogger(__name__)


def register_view_routes(bp):

    @bp.route('/<int:id>', methods=['GET'])
    @auth_optional
    def view_case(id):
        """Display a specific case."""
        document = Document.query.get_or_404(id)

        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        metadata = {}
        if document.doc_metadata:
            if isinstance(document.doc_metadata, dict):
                metadata = document.doc_metadata
            else:
                logger.warning(f"doc_metadata for document {document.id} is not a dictionary: {type(document.doc_metadata)}")

        case = {
            'id': document.id,
            'title': document.title,
            'description': document.content or '',
            'decision': metadata.get('decision', ''),
            'outcome': metadata.get('outcome', ''),
            'ethical_analysis': metadata.get('ethical_analysis', ''),
            'source': document.source,
            'document_id': document.id,
            'is_document': True,
            'case_number': metadata.get('case_number', ''),
            'year': metadata.get('year', ''),
            'world_id': document.world_id,
            'doc_metadata': metadata
        }

        world = World.query.get(document.world_id) if document.world_id else None

        entity_triples = []
        knowledge_graph_connections = {}
        try:
            triple_service = EntityTripleService()
            case_uri = f"http://proethica.org/cases/{document.id}"
            entity_triples = triple_service.find_triples(subject=case_uri, entity_type='document')

            related_cases_data = triple_service.find_related_cases_by_triples(document.id)

            if related_cases_data:
                for predicate, data in related_cases_data.items():
                    for case_info in data['related_cases']:
                        case_id = case_info['entity_id']
                        related_doc = Document.query.get(case_id)
                        if related_doc:
                            case_info['title'] = related_doc.title

                    data['related_cases'] = sorted(
                        data['related_cases'],
                        key=lambda x: len(x['shared_triples']),
                        reverse=True
                    )

                knowledge_graph_connections = related_cases_data
        except Exception as e:
            flash(f"Warning: Could not retrieve entity triples or related cases: {str(e)}", 'warning')

        term_links_by_section = {}
        try:
            from app.models.section_term_link import SectionTermLink
            document_term_links = SectionTermLink.get_document_term_links(document.id)

            if document_term_links:
                term_links_by_section = document_term_links
                logger.info(f"Loaded term links for document {document.id}: {len(document_term_links)} sections")
        except Exception as e:
            logger.warning(f"Could not load term links for document {document.id}: {str(e)}")

        annotation_count = 0
        try:
            from app.models.document_concept_annotation import DocumentConceptAnnotation
            annotation_count = DocumentConceptAnnotation.query.filter_by(
                document_type='case',
                document_id=document.id,
                is_current=True
            ).count()
        except Exception as e:
            logger.warning(f"Could not get annotation count for case {document.id}: {str(e)}")

        pipeline_status = PipelineStatusService.get_step_status(document.id)

        entity_count = 0
        question_count = 0
        conclusion_count = 0
        transformation_type = None
        try:
            from app.models import TemporaryRDFStorage
            entity_count = TemporaryRDFStorage.query.filter_by(case_id=document.id).count()

            if metadata:
                questions_list = metadata.get('questions_list', [])
                question_count = len(questions_list) if questions_list else 0

                conclusion_items = metadata.get('conclusion_items', [])
                conclusion_count = len(conclusion_items) if conclusion_items else 0

            if pipeline_status.get('step4', {}).get('complete'):
                from app.models import ExtractionPrompt
                transform_prompt = ExtractionPrompt.query.filter_by(
                    case_id=document.id,
                    concept_type='transformation_classification'
                ).first()
                if transform_prompt and transform_prompt.raw_response:
                    transform_data = transform_prompt.raw_response
                    if isinstance(transform_data, dict):
                        transformation_type = transform_data.get('transformation_type') or transform_data.get('type')
        except Exception as e:
            logger.warning(f"Could not get summary counts for case {document.id}: {str(e)}")

        entity_lookup = {}
        entity_lookup_by_label = {}
        if entity_count > 0:
            try:
                from app.services.unified_entity_resolver import UnifiedEntityResolver
                resolver = UnifiedEntityResolver(case_id=document.id)
                entity_lookup = resolver.get_lookup_dict()
                entity_lookup_by_label = resolver.get_label_index()
            except Exception as e:
                logger.warning(f"Could not get entity lookup for case {document.id}: {str(e)}")

        # Check if case ontology exists in OntServe and get individual count
        ontserve_individual_count = None
        try:
            import psycopg2
            from app.services.ontserve_config import get_ontserve_db_config
            conn = psycopg2.connect(**get_ontserve_db_config())
            cur = conn.cursor()
            cur.execute("""
                SELECT COUNT(*) FROM ontology_entities oe
                JOIN ontologies o ON oe.ontology_id = o.id
                WHERE o.name = %s AND oe.entity_type = 'individual'
            """, (f"proethica-case-{document.id}",))
            row = cur.fetchone()
            if row and row[0] > 0:
                ontserve_individual_count = row[0]
            cur.close()
            conn.close()
        except Exception as e:
            logger.debug(f"Could not query OntServe for case {document.id}: {str(e)}")

        return render_template('case_detail.html', case=case, world=world,
                              entity_triples=entity_triples,
                              knowledge_graph_connections=knowledge_graph_connections,
                              term_links_by_section=term_links_by_section,
                              annotation_count=annotation_count,
                              pipeline_status=pipeline_status,
                              entity_count=entity_count,
                              question_count=question_count,
                              conclusion_count=conclusion_count,
                              transformation_type=transformation_type,
                              entity_lookup=entity_lookup,
                              entity_lookup_by_label=entity_lookup_by_label,
                              ontserve_individual_count=ontserve_individual_count)

    @bp.route('/<int:id>/annotations', methods=['GET'])
    def view_case_annotations(id):
        """View annotations for a specific case using the modular annotation service."""
        from app.services.document_annotation_service import DocumentAnnotationService

        context = DocumentAnnotationService.prepare_annotation_context(id, 'case')

        if not context:
            flash('Case not found', 'error')
            return redirect(url_for('cases.list_cases'))

        if context['document'].document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        return render_template('case_annotations.html', **context)

    @bp.route('/24-02/hero', methods=['GET'])
    def case_24_02_hero():
        """Compact hero banner showcase for Case 24-02 (read-only)."""
        return render_template('case24_02_hero.html')

    @bp.route('/24-02/hero/compact', methods=['GET'])
    def case_24_02_hero_compact():
        """Compact hero banner snapshot for Case 24-02 (width-optimized)."""
        return render_template('demo/case24_02_compact.html')
