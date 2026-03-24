"""Save-and-view case route and related cases API."""

import re
import json
import logging
from flask import request, redirect, url_for, flash, jsonify
from flask_login import current_user
from app.models import Document
from app.models.document import PROCESSING_STATUS
from app.models.world import World
from app.services.entity_triple_service import EntityTripleService
from app import db

logger = logging.getLogger(__name__)


def register_save_view_routes(bp):

    @bp.route('/save-and-view', methods=['POST'])
    def save_and_view_case():
        """Save case with extracted content and view it directly (no edit step)."""
        url = request.form.get('url')
        world_id = request.form.get('world_id', type=int)
        title = request.form.get('title')
        case_number = request.form.get('case_number')
        year = request.form.get('year')
        full_date = request.form.get('full_date')

        date_parts = None
        try:
            date_parts_str = request.form.get('date_parts')
            if date_parts_str:
                date_parts = json.loads(date_parts_str)
        except Exception as e:
            logger.warning(f"Error parsing date_parts: {str(e)}")

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
            facts = request.form.get('facts', '')
            question_html = request.form.get('question_html', '')
            references = request.form.get('references', '')
            discussion = request.form.get('discussion', '')
            conclusion = request.form.get('conclusion', '')
            dissenting_opinion = request.form.get('dissenting_opinion', '')
            pdf_url = request.form.get('pdf_url', '')

            subject_tags = []
            try:
                subject_tags_str = request.form.get('subject_tags')
                if subject_tags_str:
                    subject_tags = json.loads(subject_tags_str)
            except Exception as e:
                logger.warning(f"Error parsing subject_tags: {str(e)}")
                subject_tags_str = request.form.get('subject_tags', '')
                if subject_tags_str:
                    subject_tags = [subject_tags_str]

            questions_list = []
            conclusion_items = []

            try:
                if request.form.get('questions_list'):
                    questions_list = json.loads(request.form.get('questions_list'))
                if request.form.get('conclusion_items'):
                    conclusion_items = json.loads(request.form.get('conclusion_items'))
            except Exception as e:
                logger.warning(f"Error parsing JSON lists: {str(e)}")

            # Parse questions from HTML if list is empty
            if not questions_list and question_html:
                logger.debug("Attempting to parse questions from question_html")

                questions_raw = question_html

                splits = re.split(r'\?((?=[A-Z][a-z])|$)', questions_raw)

                if len(splits) > 1:
                    temp_questions = []
                    for i in range(0, len(splits) - 1, 2):
                        if i + 1 < len(splits):
                            q = splits[i] + "?"
                            temp_questions.append(q.strip())

                    if temp_questions:
                        logger.debug(f"Successfully parsed {len(temp_questions)} questions from text")
                        questions_list = temp_questions

                if not questions_list:
                    numbered_questions = re.findall(r'(\d+\.\s*[^.;?!]*[.;?!])', questions_raw)
                    if numbered_questions:
                        questions_list = [q.strip() for q in numbered_questions]
                        logger.debug(f"Found {len(questions_list)} numbered questions")
                    else:
                        line_splits = re.split(r'[\r\n]+', questions_raw)
                        if len(line_splits) > 1:
                            questions_list = [q.strip() for q in line_splits if q.strip()]
                            logger.debug(f"Split into {len(questions_list)} questions by line breaks")

            # Build HTML content
            from app.routes.cases.creation_processing import _build_case_html
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
                'extraction_method': 'direct_view',
                'display_format': 'extraction_style'
            }

            document = Document(
                title=title or 'Case from URL',
                content=html_content,
                document_type='case_study',
                world_id=world_id,
                source=url,
                file_type='url',
                doc_metadata=metadata
            )

            document.processing_status = PROCESSING_STATUS['COMPLETED']
            document.processing_progress = 100

            if user_id and document.doc_metadata:
                document.doc_metadata['created_by_user_id'] = user_id

            db.session.add(document)
            db.session.commit()

            flash('Case saved successfully', 'success')
            return redirect(url_for('cases.view_case', id=document.id))

        except Exception as e:
            import traceback
            logger.error(traceback.format_exc())
            flash(f'Error saving case: {str(e)}', 'danger')
            return redirect(url_for('cases.url_form'))

    @bp.route('/api/related-cases', methods=['POST'])
    def get_related_cases():
        """Get cases related to specified triples."""
        data = request.json
        document_id = data.get('document_id')
        selected_triples = data.get('selected_triples', [])

        if not document_id:
            return jsonify({'error': 'Document ID is required'}), 400

        try:
            triple_service = EntityTripleService()

            if not selected_triples:
                return jsonify({'related_cases': []})

            matching_cases = triple_service.find_cases_matching_all_triples(document_id, selected_triples)

            return jsonify({'related_cases': matching_cases})
        except Exception as e:
            return jsonify({'error': str(e)}), 500
