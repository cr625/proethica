"""Case creation form display routes."""

from flask import render_template
from app.utils.environment_auth import auth_required_for_create
from app.models.world import World


def register_creation_form_routes(bp):

    @bp.route('/new', methods=['GET'])
    @auth_required_for_create
    def case_options():
        """Display case creation options."""
        return render_template('create_case_options.html')

    @bp.route('/new/manual', methods=['GET'])
    @auth_required_for_create
    def manual_create_form():
        """Display form to manually create a new case."""
        worlds = World.query.all()
        return render_template('create_case_manual.html', worlds=worlds)

    @bp.route('/new/url', methods=['GET'])
    @auth_required_for_create
    def url_form():
        """Display form to create a case from URL."""
        worlds = World.query.all()
        return render_template('create_case_from_url.html', worlds=worlds)

    @bp.route('/new/document', methods=['GET'])
    def upload_document_form():
        """Display form to create a case from document upload."""
        worlds = World.query.all()
        return render_template('create_case_from_document.html', worlds=worlds)
