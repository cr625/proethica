"""Defeasibility resolution view route.

Renders the obligation-conflict resolution view for a case: how each obligation
competition was resolved (which obligation prevailed, under what State context),
alongside how comparable cases resolved the analogous tension. Data is read from the
committed case ontology by ``defeasibility_view_service``.
"""

import logging

from flask import render_template, redirect, url_for, flash

from app.utils.environment_auth import auth_optional
from app.models import Document
from app.services.defeasibility_view_service import build_defeasibility_view

logger = logging.getLogger(__name__)


def register_defeasibility_routes(bp):

    @bp.route('/<int:id>/defeasibility', methods=['GET'])
    @auth_optional
    def case_defeasibility(id):
        """Obligation-conflict resolution view for a case."""
        document = Document.query.get_or_404(id)

        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        meta = document.doc_metadata if isinstance(document.doc_metadata, dict) else {}

        try:
            view = build_defeasibility_view(id)
        except FileNotFoundError:
            flash('This case has no committed ontology yet. Run the extraction pipeline first.', 'warning')
            return redirect(url_for('cases.view_case', id=id))

        return render_template(
            'case_defeasibility.html',
            case={
                'id': document.id,
                'title': document.title,
                'case_number': meta.get('case_number', ''),
                'year': meta.get('year', ''),
            },
            view=view,
        )
