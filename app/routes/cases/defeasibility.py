"""Defeasibility resolution view route.

Renders the obligation-conflict resolution view for a case: how each obligation
competition was resolved (which obligation prevailed, under what State context),
alongside how comparable cases resolved the analogous tension. Data is read from the
committed case ontology by ``defeasibility_view_service``.
"""

import logging
import re

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

        # People and entities named in the case text (the board's conclusions, boundary
        # resolutions) get the popovers of the case page, from its label index with the
        # text-grounded actor aliases.
        text_entity_lookup = {}
        try:
            from app.services.entity.unified_entity_resolver import UnifiedEntityResolver
            text_entity_lookup = UnifiedEntityResolver(case_id=id, case_source='committed').get_label_index()
        except Exception as e:
            logger.warning(f"Could not get entity label index for case {id}: {str(e)}")
        # Only the labels that occur in that text travel with the page (the full index is
        # several hundred entries), matched like the scanner: whole word, case-insensitive.
        conflicts = view.get('case_conflicts') or {}
        case_text = ' '.join(list(conflicts.get('conclusions') or [])[:3]
                             + [br.get('text') or '' for br in conflicts.get('boundary_resolutions') or []]).lower()
        text_entity_lookup = {
            label: entry for label, entry in text_entity_lookup.items()
            if re.search(r'\b' + re.escape(label) + r'(?![a-z0-9_])', case_text)
        }

        return render_template(
            'case_defeasibility.html',
            case={
                'id': document.id,
                'title': document.title,
                'case_number': meta.get('case_number', ''),
                'year': meta.get('year', ''),
            },
            view=view,
            text_entity_lookup=text_entity_lookup,
        )
