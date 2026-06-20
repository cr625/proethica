"""Case-creation HTML builder helper."""
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
