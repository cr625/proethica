"""Case creation processing routes (URL pipeline, manual, document upload)."""

import os
import logging
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import current_user
from app.utils.environment_auth import auth_required_for_write
from app.models import Document
from app.models.document import PROCESSING_STATUS
from app.models.world import World
from app.services.embedding_service import EmbeddingService
from app.services.entity_triple_service import EntityTripleService
from app.services.case_url_processor import CaseUrlProcessor
from app.routes.cases.structure_embeddings import _sync_embeddings_to_precedent_features
from app import db

logger = logging.getLogger(__name__)


def register_creation_processing_routes(bp):

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
                from app.services.section_embedding_service import SectionEmbeddingService
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

    @bp.route('/new/url', methods=['POST'])
    @auth_required_for_write
    def create_from_url():
        """Create a new case from URL."""
        import json

        url = request.form.get('url')
        world_id = request.form.get('world_id', type=int)
        title = request.form.get('title')
        case_number = request.form.get('case_number')
        year = request.form.get('year')

        user_id = None
        try:
            if current_user and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
                user_id = current_user.id
        except Exception:
            pass

        if not url:
            flash('URL is required', 'danger')
            return redirect(url_for('cases.url_form'))

        if not world_id:
            flash('World selection is required', 'danger')
            return redirect(url_for('cases.url_form'))

        world = World.query.get(world_id)
        if not world:
            flash(f'World with ID {world_id} not found', 'danger')
            return redirect(url_for('cases.url_form'))

        try:
            using_extracted_content = request.form.get('extracted_content') == 'true'

            if using_extracted_content:
                facts = request.form.get('facts', '')
                question_html = request.form.get('question_html', '')
                references = request.form.get('references', '')
                discussion = request.form.get('discussion', '')
                conclusion = request.form.get('conclusion', '')
                pdf_url = request.form.get('pdf_url', '')

                questions_list = []
                conclusion_items = []

                try:
                    if request.form.get('questions_list'):
                        questions_list = json.loads(request.form.get('questions_list'))
                    if request.form.get('conclusion_items'):
                        conclusion_items = json.loads(request.form.get('conclusion_items'))
                except Exception as e:
                    print(f"Warning: Error parsing JSON lists: {str(e)}")

                combined_content = f"<h2>Facts</h2>\n{facts}\n\n"

                if question_html:
                    if questions_list and len(questions_list) > 1:
                        combined_content += f"<h2>Questions</h2>\n"
                    else:
                        combined_content += f"<h2>Question</h2>\n"

                    if questions_list:
                        combined_content += "<ol>\n"
                        for q in questions_list:
                            combined_content += f"<li>{q}</li>\n"
                        combined_content += "</ol>\n\n"
                    else:
                        combined_content += f"{question_html}\n\n"

                if references:
                    combined_content += f"<h2>NSPE Code of Ethics References</h2>\n{references}\n\n"

                if discussion:
                    combined_content += f"<h2>Discussion</h2>\n{discussion}\n\n"

                if conclusion:
                    if conclusion_items and len(conclusion_items) > 1:
                        combined_content += f"<h2>Conclusions</h2>\n"
                    else:
                        combined_content += f"<h2>Conclusion</h2>\n"

                    if conclusion_items:
                        combined_content += "<ol>\n"
                        for c in conclusion_items:
                            combined_content += f"<li>{c}</li>\n"
                        combined_content += "</ol>\n\n"
                    else:
                        combined_content += f"{conclusion}\n\n"

                metadata = {
                    'case_number': case_number,
                    'year': year,
                    'pdf_url': pdf_url,
                    'sections': {
                        'facts': facts,
                        'question': question_html,
                        'references': references,
                        'discussion': discussion,
                        'conclusion': conclusion
                    },
                    'questions_list': questions_list,
                    'conclusion_items': conclusion_items,
                    'extraction_method': 'pipeline_preserved'
                }

                document = Document(
                    title=title or 'Case from URL',
                    content=combined_content,
                    document_type='case_study',
                    world_id=world_id,
                    source=url,
                    file_type='url',
                    doc_metadata=metadata
                )

                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100

            else:
                processor = CaseUrlProcessor()

                result = processor.process_url(url, world_id, user_id)

                if 'status' in result and result['status'] == 'error':
                    flash(result['message'], 'danger')
                    return redirect(url_for('cases.url_form'))

                document = Document(
                    title=result.get('title', 'Case from URL'),
                    content=result.get('content', ''),
                    document_type='case_study',
                    world_id=world_id,
                    source=url,
                    file_type='url',
                    doc_metadata=result.get('metadata', {})
                )

                if result.get('content'):
                    document.processing_status = PROCESSING_STATUS['COMPLETED']
                    document.processing_progress = 100

                if 'triples' in result and result['triples']:
                    document.doc_metadata['triples_to_process'] = result['triples']

            if user_id and document.doc_metadata:
                document.doc_metadata['created_by_user_id'] = user_id

            db.session.add(document)
            db.session.commit()

            if document.doc_metadata and document.doc_metadata.get('triples_to_process'):
                triple_service = EntityTripleService()

                for triple in document.doc_metadata['triples_to_process']:
                    try:
                        triple_service.add_triple(
                            subject=f"http://proethica.org/entity/document_{document.id}",
                            predicate=triple['predicate'],
                            obj=triple['object'],
                            is_literal=triple.get('is_literal', True),
                            entity_type='entity',
                            entity_id=document.id
                        )
                    except Exception as e:
                        flash(f'Warning: Error creating triple: {str(e)}', 'warning')

                document.doc_metadata.pop('triples_to_process', None)
                db.session.commit()

            # Generate section embeddings
            try:
                from app.services.section_embedding_service import SectionEmbeddingService
                section_embedding_service = SectionEmbeddingService()
                embedding_result = section_embedding_service.process_document_sections(document.id)
                if embedding_result.get('success'):
                    logger.info(f"Generated embeddings for {embedding_result.get('sections_embedded')} sections")
            except Exception as e:
                logger.warning(f"Error generating section embeddings: {str(e)}")

            # Generate precedent features
            try:
                from app.services.precedent.case_feature_extractor import CaseFeatureExtractor
                feature_extractor = CaseFeatureExtractor()
                features = feature_extractor.extract_precedent_features(document.id)
                feature_extractor.save_features(features)
                logger.info(f"Extracted precedent features for case {document.id}: outcome={features.outcome_type}")
                _sync_embeddings_to_precedent_features(document.id)
            except Exception as e:
                logger.warning(f"Error extracting precedent features: {str(e)}")

            flash('Case created successfully from URL', 'success')
            return redirect(url_for('cases.edit_case_form', id=document.id))

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            flash(f'Error processing URL: {str(e)}', 'danger')
            return redirect(url_for('cases.url_form'))

    @bp.route('/new/document', methods=['POST'])
    @auth_required_for_write
    def create_from_document():
        """Create a new case from document upload."""
        title = request.form.get('title')
        world_id = request.form.get('world_id', type=int)

        if not title:
            flash('Title is required', 'danger')
            return redirect(url_for('cases.upload_document_form'))

        if 'document' not in request.files:
            flash('Document file is required', 'danger')
            return redirect(url_for('cases.upload_document_form'))

        document_file = request.files['document']

        if document_file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('cases.upload_document_form'))

        if not world_id:
            flash('World selection is required', 'danger')
            return redirect(url_for('cases.upload_document_form'))

        world = World.query.get(world_id)
        if not world:
            flash(f'World with ID {world_id} not found', 'danger')
            return redirect(url_for('cases.upload_document_form'))

        try:
            file_ext = os.path.splitext(document_file.filename)[1].lower()

            file_type_map = {
                '.pdf': 'pdf',
                '.docx': 'docx',
                '.doc': 'docx',
                '.txt': 'txt',
                '.html': 'html',
                '.htm': 'html'
            }

            if file_ext not in file_type_map:
                flash(f'Unsupported file type: {file_ext}', 'danger')
                return redirect(url_for('cases.upload_document_form'))

            file_type = file_type_map[file_ext]

            upload_dir = os.path.join('app', 'uploads')
            os.makedirs(upload_dir, exist_ok=True)

            from werkzeug.utils import secure_filename
            import uuid

            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            document_file.save(file_path)

            document = Document(
                title=title,
                document_type='case_study',
                world_id=world_id,
                file_path=file_path,
                file_type=file_type,
                source=document_file.filename,
                processing_status=PROCESSING_STATUS['PROCESSING'],
                doc_metadata={}
            )

            db.session.add(document)
            db.session.commit()

            try:
                embedding_service = EmbeddingService()

                text = embedding_service._extract_text(file_path, file_type)
                document.content = text

                chunks = embedding_service._split_text(text)
                embeddings = embedding_service.embed_documents(chunks)
                embedding_service._store_chunks(document.id, chunks, embeddings)

                document.processing_status = PROCESSING_STATUS['COMPLETED']
                document.processing_progress = 100
                db.session.commit()
            except Exception as e:
                logger.error(f"Error processing document: {str(e)}")
                db.session.rollback()
                raise

            flash('Document processed and case created successfully', 'success')
            return redirect(url_for('cases.edit_case_form', id=document.id))

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            flash(f'Error processing document: {str(e)}', 'danger')
            return redirect(url_for('cases.upload_document_form'))


def _build_case_html(facts, question_html, questions_list, references,
                     discussion, conclusion, conclusion_items, dissenting_opinion):
    """Build HTML content for a case from its sections."""
    html_content = ""

    if facts:
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Facts</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{facts}</p>
            </div>
        </div>
    </div>
</div>
"""

    if question_html or questions_list:
        question_heading = "Questions" if questions_list and len(questions_list) > 1 else "Question"
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{question_heading}</h5>
            </div>
            <div class="card-body">
"""
        if questions_list:
            html_content += "<ol class=\"mb-0\">\n"
            for q in questions_list:
                clean_question = q.strip()
                html_content += f"    <li>{clean_question}</li>\n"
            html_content += "</ol>\n"
        else:
            html_content += f"<p class=\"mb-0\">{question_html}</p>\n"

        html_content += """
            </div>
        </div>
    </div>
</div>
"""

    if references:
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">NSPE Code of Ethics References</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{references}</p>
            </div>
        </div>
    </div>
</div>
"""

    if discussion:
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">Discussion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{discussion}</p>
            </div>
        </div>
    </div>
</div>
"""

    if conclusion or conclusion_items:
        conclusion_heading = "Conclusions" if conclusion_items and len(conclusion_items) > 1 else "Conclusion"
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-light">
                <h5 class="mb-0">{conclusion_heading}</h5>
            </div>
            <div class="card-body">
"""
        if conclusion_items:
            html_content += "<ol class=\"mb-0\">\n"
            for c in conclusion_items:
                clean_conclusion = c.strip()
                html_content += f"    <li>{clean_conclusion}</li>\n"
            html_content += "</ol>\n"
        else:
            html_content += f"<p class=\"mb-0\">{conclusion}</p>\n"

        html_content += """
            </div>
        </div>
    </div>
</div>
"""

    if dissenting_opinion:
        html_content += f"""
<div class="row mb-4">
    <div class="col-12">
        <div class="card">
            <div class="card-header bg-warning">
                <h5 class="mb-0">Dissenting Opinion</h5>
            </div>
            <div class="card-body">
                <p class="mb-0">{dissenting_opinion}</p>
            </div>
        </div>
    </div>
</div>
"""

    return html_content
