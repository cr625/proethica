"""create_from_url + create_from_document."""
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


def register_creation_from_source(bp):
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
                    logger.warning(f"Error parsing JSON lists: {str(e)}")

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
                from app.services.embedding.section_embedding_service import SectionEmbeddingService
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
            logger.error(traceback.format_exc())
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
            logger.error(traceback.format_exc())
            flash(f'Error processing document: {str(e)}', 'danger')
            return redirect(url_for('cases.upload_document_form'))
