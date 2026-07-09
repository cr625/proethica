"""process_url_pipeline + create_case_manual."""
import os
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from app.utils.environment_auth import auth_required_for_write
from app.models import Document
from app.models.document import PROCESSING_STATUS
from app.models.world import World
from app.services.embedding.embedding_service import EmbeddingService
from app.services.entity.entity_triple_service import EntityTripleService
from app.services.case_url_processor import CaseUrlProcessor
from app.routes.cases.structure_embeddings import _sync_embeddings_to_precedent_features
from app import db

logger = logging.getLogger(__name__)
from app.routes.cases.creation_processing.helpers import (
    _build_case_html,
)


def register_creation_url_manual(bp):
    @bp.route('/process/url', methods=['GET', 'POST'])
    def process_url_pipeline():
        """Process a URL through the case processing pipeline and save directly to database."""
        # Handle GET requests (typically from back button)
        if request.method == 'GET':
            url = request.args.get('url')
            if not url:
                return redirect(url_for('cases.url_form'))

            # Re-submit as POST to process the URL
            return render_template('process_url_form.html', url=url)

        # Process POST requests
        url = request.form.get('url')
        process_extraction = request.form.get('process_extraction') == 'true'
        world_id = request.form.get('world_id', type=int, default=1)

        if not url:
            return render_template('raw_url_content.html',
                                   error="URL is required",
                                   error_details="Please provide a valid URL to process.")

        # Initialize pipeline
        from app.services.case_processing.pipeline_manager import PipelineManager
        from app.services.case_processing.pipeline_steps.url_retrieval_step import URLRetrievalStep
        from app.services.case_processing.pipeline_steps.nspe_extraction_step import NSPECaseExtractionStep
        from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep

        pipeline = PipelineManager()
        pipeline.register_step('url_retrieval', URLRetrievalStep())
        pipeline.register_step('nspe_extraction', NSPECaseExtractionStep())
        pipeline.register_step('document_structure', DocumentStructureAnnotationStep())

        steps_to_run = ['url_retrieval']
        if process_extraction:
            steps_to_run.extend(['nspe_extraction', 'document_structure'])

        logger.info(f"Running pipeline for URL: {url} with steps: {', '.join(steps_to_run)}")
        result = pipeline.run_pipeline({'url': url}, steps_to_run)

        final_result = result.get('final_result', {})

        if final_result.get('status') == 'error':
            return render_template('raw_url_content.html',
                                   error=final_result.get('message'),
                                   error_details=final_result,
                                   url=url)

        if process_extraction:
            if 'sections' not in final_result and final_result.get('status') == 'success':
                sections_data = {
                    'facts': final_result.get('facts', ''),
                    'question': final_result.get('question_html', ''),
                    'references': final_result.get('references', ''),
                    'discussion': final_result.get('discussion', ''),
                    'conclusion': final_result.get('conclusion', '')
                }
                final_result['sections'] = sections_data

            if 'conclusion_items' not in final_result and isinstance(final_result.get('conclusion'), dict):
                conclusion_data = final_result.get('conclusion', {})
                if 'conclusions' in conclusion_data:
                    final_result['conclusion_items'] = conclusion_data['conclusions']
                elif isinstance(conclusion_data, dict) and 'html' in conclusion_data and 'conclusions' in conclusion_data:
                    final_result['conclusion_items'] = conclusion_data['conclusions']
                    final_result['sections']['conclusion'] = conclusion_data['html']

            title = final_result.get('title', 'Case from URL')
            case_number = final_result.get('case_number', '')
            year = final_result.get('year', '')
            full_date = final_result.get('full_date')
            date_parts = final_result.get('date_parts')
            pdf_url = final_result.get('pdf_url', '')
            facts = final_result.get('sections', {}).get('facts', '')
            question_html = final_result.get('sections', {}).get('question', '')
            references = final_result.get('sections', {}).get('references', '')
            discussion = final_result.get('sections', {}).get('discussion', '')
            conclusion = final_result.get('sections', {}).get('conclusion', '')
            dissenting_opinion = final_result.get('sections', {}).get('dissenting_opinion', '')

            questions_list = final_result.get('questions_list', [])
            conclusion_items = final_result.get('conclusion_items', [])
            subject_tags = final_result.get('subject_tags', [])

            html_content = _build_case_html(facts, question_html, questions_list,
                                            references, discussion, conclusion,
                                            conclusion_items, dissenting_opinion)

            from app.utils.provision_references import (
                parse_references_html, parse_references_text)
            provision_references = (parse_references_html(references)
                             or parse_references_text(references))

            metadata = {
                'case_number': case_number,
                'year': year,
                'full_date': full_date,
                'date_parts': date_parts,
                'pdf_url': pdf_url,
                'subject_tags': subject_tags,
                'sections': {
                    'facts': facts,
                    'question': question_html,
                    'references': references,
                    'discussion': discussion,
                    'conclusion': conclusion,
                    'dissenting_opinion': dissenting_opinion
                },
                'questions_list': questions_list,
                'conclusion_items': conclusion_items,
                # Board-stated provision set, parsed deterministically at
                # ingestion (provisions-harmonization.md workstream A).
                'provision_references': provision_references,
                'extraction_method': 'direct_process',
                'display_format': 'extraction_style',
                'case_source': 'primary'
            }

            if 'sections_dual' in final_result:
                metadata['sections_dual'] = final_result['sections_dual']
                logger.info("Storing dual format sections (HTML and text)")

            if 'sections_text' in final_result:
                metadata['sections_text'] = final_result['sections_text']

            if 'document_structure' in final_result:
                metadata['document_structure'] = {
                    'document_uri': final_result['document_structure'].get('document_uri'),
                    'structure_triples': final_result['document_structure'].get('structure_triples'),
                    'sections': metadata['sections'],
                    'annotation_timestamp': datetime.utcnow().isoformat()
                }
                logger.info(f"Added document structure with URI: {metadata['document_structure']['document_uri']}")

            if 'section_embeddings_metadata' in final_result:
                metadata['section_embeddings_metadata'] = final_result['section_embeddings_metadata']
                logger.info(f"Added section embeddings metadata with {len(metadata['section_embeddings_metadata'])} sections")

            user_id = None
            try:
                if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                    user_id = current_user.id
                    metadata['created_by_user_id'] = user_id
            except Exception:
                pass

            document = Document(
                title=title,
                content=html_content,
                document_type='case_study',
                world_id=world_id,
                source=url,
                file_type='url',
                doc_metadata=metadata,
                processing_status=PROCESSING_STATUS['COMPLETED']
            )

            db.session.add(document)
            db.session.commit()

            # Generate section embeddings
            logger.info(f"Generating section embeddings for document ID: {document.id}")
            try:
                from app.services.embedding.section_embedding_service import SectionEmbeddingService
                section_embedding_service = SectionEmbeddingService()

                embedding_result = section_embedding_service.process_document_sections(document.id)

                if embedding_result.get('success'):
                    logger.info(f"Successfully generated embeddings for {embedding_result.get('sections_embedded')} sections")
                    if 'document_structure' not in metadata:
                        metadata['document_structure'] = {}

                    metadata['document_structure']['section_embeddings'] = {
                        'count': embedding_result.get('sections_embedded', 0),
                        'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                        'storage_type': 'pgvector'
                    }

                    document.doc_metadata = metadata
                    db.session.commit()
                    logger.info("Updated document metadata with section embedding information")
                else:
                    logger.warning(f"Failed to generate section embeddings: {embedding_result.get('error')}")
            except Exception as e:
                logger.error(f"Error generating section embeddings: {str(e)}")

            # Generate precedent features
            try:
                from app.services.precedent.case_feature_extractor import CaseFeatureExtractor
                feature_extractor = CaseFeatureExtractor()
                features = feature_extractor.extract_precedent_features(document.id)
                feature_extractor.save_features(features)
                logger.info(f"Extracted precedent features for case {document.id}: outcome={features.outcome_type}, provisions={len(features.provisions_cited)}")
                _sync_embeddings_to_precedent_features(document.id)
            except Exception as e:
                logger.warning(f"Error extracting precedent features: {str(e)}")

            # Extract cited cases
            cited_cases_result = None
            try:
                from app.services.precedent.cited_case_ingestor import CitedCaseIngestor
                ingestor = CitedCaseIngestor()
                cited_cases_result = ingestor.ingest_cited_cases_for_primary(
                    case_id=document.id,
                    world_id=world_id,
                    max_cases=20
                )
                if cited_cases_result:
                    ingested_count = len(cited_cases_result.get('ingested', []))
                    pending_count = len(cited_cases_result.get('pending', []))
                    logger.info(f"Cited case ingestion: {ingested_count} ingested, {pending_count} pending")
            except Exception as e:
                logger.warning(f"Error ingesting cited cases: {str(e)}")

            logger.info(f"Case saved successfully with ID: {document.id}, includes document structure: {'document_structure' in metadata}")

            success_msg = 'Case extracted and saved successfully'
            if 'document_structure' in metadata:
                success_msg += ' with document structure annotation'
            if cited_cases_result:
                ingested = cited_cases_result.get('ingested', [])
                pending = cited_cases_result.get('pending', [])
                if ingested:
                    success_msg += f'. Ingested {len(ingested)} cited precedent case(s)'
                if pending:
                    success_msg += f'. {len(pending)} more cited cases pending'
            flash(success_msg, 'success')
            return redirect(url_for('cases.view_case', id=document.id))

        # Otherwise, just show the raw content
        return render_template('raw_url_content.html',
                              url=final_result.get('url'),
                              content=final_result.get('content'),
                              content_type=final_result.get('content_type'),
                              content_length=final_result.get('content_length'),
                              status_code=final_result.get('status_code'),
                              encoding=final_result.get('encoding'))

    @bp.route('/new/manual', methods=['POST'])
    @auth_required_for_write
    def create_case_manual():
        """Create a new case manually."""
        import json

        title = request.form.get('title')
        description = request.form.get('description')
        decision = request.form.get('decision')
        outcome = request.form.get('outcome')
        ethical_analysis = request.form.get('ethical_analysis')
        source = request.form.get('source')
        world_id = request.form.get('world_id', type=int)
        rdf_metadata = request.form.get('rdf_metadata', '')

        if not title:
            flash('Title is required', 'danger')
            return redirect(url_for('cases.manual_create_form'))

        if not description:
            flash('Description is required', 'danger')
            return redirect(url_for('cases.manual_create_form'))

        if not world_id:
            flash('World selection is required', 'danger')
            return redirect(url_for('cases.manual_create_form'))

        world = World.query.get(world_id)
        if not world:
            flash(f'World with ID {world_id} not found', 'danger')
            return redirect(url_for('cases.manual_create_form'))

        metadata = {
            'decision': decision,
            'outcome': outcome,
            'ethical_analysis': ethical_analysis
        }

        if rdf_metadata:
            try:
                rdf_data = json.loads(rdf_metadata)

                if 'triples' not in rdf_data:
                    rdf_data['triples'] = []

                if 'namespaces' not in rdf_data:
                    rdf_data['namespaces'] = {}

                metadata['rdf_triples'] = rdf_data['triples']
                metadata['rdf_namespaces'] = rdf_data['namespaces']

                if world_id == 1:
                    triple_service = EntityTripleService()

                    try:
                        metadata['process_entity_triples'] = True
                    except Exception as e:
                        flash(f'Warning: RDF triples could not be converted to entity triples: {str(e)}', 'warning')

            except json.JSONDecodeError:
                flash('Warning: RDF metadata is not valid JSON. It will be stored as plain text.', 'warning')
                metadata['rdf_metadata_text'] = rdf_metadata
            except Exception as e:
                flash(f'Warning: Error processing RDF metadata: {str(e)}', 'warning')
                metadata['rdf_metadata_text'] = rdf_metadata

        document = Document(
            title=title,
            content=description,
            document_type='case_study',
            world_id=world_id,
            source=source,
            doc_metadata=metadata
        )

        db.session.add(document)
        db.session.commit()

        try:
            embedding_service = EmbeddingService()
            embedding_service.process_document(document.id)

            if metadata.get('process_entity_triples'):
                try:
                    triple_service = EntityTripleService()

                    doc = Document.query.get(document.id)

                    for triple in metadata.get('rdf_triples', []):
                        triple_service.add_triple(
                            subject=f"http://proethica.org/entity/document_{document.id}",
                            predicate=triple['predicate'],
                            obj=triple['object'],
                            is_literal=False,
                            entity_type='entity',
                            entity_id=document.id
                        )

                    flash('RDF triples processed successfully', 'success')
                except Exception as e:
                    flash(f'Warning: Error processing entity triples: {str(e)}', 'warning')

            flash('Case created and processed successfully', 'success')
        except Exception as e:
            flash(f'Case created but error processing embeddings: {str(e)}', 'warning')

        return redirect(url_for('cases.view_case', id=document.id))
