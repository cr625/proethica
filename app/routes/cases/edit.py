"""Case edit and delete routes."""

from flask import request, redirect, url_for, flash
from app.utils.environment_auth import auth_required_for_write
from app.models import Document
from app.models.world import World
from app import db
from flask import render_template


def register_edit_routes(bp):

    @bp.route('/<int:id>/delete', methods=['POST'])
    @auth_required_for_write
    def delete_case(id):
        """Delete a case by ID."""
        document = Document.query.get_or_404(id)

        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        world_id = document.world_id

        if world_id:
            world = World.query.get(world_id)
            if world and world.cases and id in world.cases:
                world.cases.remove(id)
                db.session.add(world)

        try:
            from app.services.entity_triple_service import EntityTripleService
            triple_service = EntityTripleService()
            triple_service.delete_triples_for_entity('document', id)
        except Exception as e:
            flash(f"Warning: Could not delete associated entity triples: {str(e)}", 'warning')

        db.session.delete(document)
        db.session.commit()

        flash(f"Case '{document.title}' deleted successfully", 'success')
        return redirect(url_for('cases.list_cases'))

    @bp.route('/<int:id>/edit', methods=['GET'])
    def edit_case_form(id):
        """Display form to edit case title and description."""
        document = Document.query.get_or_404(id)

        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        world = World.query.get(document.world_id) if document.world_id else None

        return render_template('edit_case_details.html', document=document, world=world)

    @bp.route('/<int:id>/edit', methods=['POST'])
    @auth_required_for_write
    def edit_case(id):
        """Process the case edit form submission."""
        document = Document.query.get_or_404(id)

        if document.document_type not in ['case', 'case_study']:
            flash('The requested document is not a case', 'warning')
            return redirect(url_for('cases.list_cases'))

        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title:
            flash('Title is required', 'danger')
            return redirect(url_for('cases.edit_case_form', id=id))

        if not description:
            flash('Description is required', 'danger')
            return redirect(url_for('cases.edit_case_form', id=id))

        document.title = title
        document.content = description

        try:
            db.session.commit()
            flash('Case details updated successfully', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating case: {str(e)}', 'danger')

        return redirect(url_for('cases.view_case', id=id))

    @bp.route('/triple/<int:id>/edit', methods=['GET', 'POST'])
    def dummy_edit_triples(id):
        """Temporary route to fix BuildError for cases_triple.edit_triples."""
        return redirect(url_for('cases.edit_case_form', id=id))

    @bp.route('/<int:id>/triple/edit', methods=['GET', 'POST'])
    def dummy_edit_triples_alt(id):
        """Alternative temporary route to fix BuildError for cases_triple.edit_triples."""
        return redirect(url_for('cases.edit_case_form', id=id))
