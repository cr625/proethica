from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
import json
import os
import logging
from app import db
from app.models.world import World
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)

mcp_client = MCPClient.get_instance()


def register_concept_routes(bp):
    @bp.route('/<int:id>/guidelines/<int:guideline_id>/delete', methods=['POST'])
    @login_required
    def delete_guideline(id, guideline_id):
        """Delete a guideline and all associated data."""
        world = World.query.get_or_404(id)

        from app.models import Document
        from app.models.guideline import Guideline
        from app.models.entity_triple import EntityTriple

        # Try to get the guideline from the Guideline table first (new approach)
        guideline = Guideline.query.get(guideline_id)

        if guideline:
            # Check if guideline belongs to this world
            if guideline.world_id != world.id:
                flash('Guideline does not belong to this world', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if user can delete this guideline
            if not guideline.can_delete(current_user):
                flash('You do not have permission to delete this guideline.', 'error')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

            actual_guideline_id = guideline_id
        else:
            # Fallback: try to get from Document table (legacy approach)
            document = Document.query.get(guideline_id)
            if not document:
                flash('Guideline not found', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if document belongs to this world
            if document.world_id != world.id:
                flash('Document does not belong to this world', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if document is a guideline
            if document.document_type != "guideline":
                flash('Document is not a guideline', 'error')
                return redirect(url_for('worlds.world_guidelines', id=world.id))

            # Check if user can delete this document
            if not document.can_delete(current_user):
                flash('You do not have permission to delete this guideline.', 'error')
                return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

            # Get associated guideline ID if exists
            actual_guideline_id = None
            if document.guideline_metadata and 'guideline_id' in document.guideline_metadata:
                actual_guideline_id = document.guideline_metadata['guideline_id']

        # User option: delete associated derived ontology too
        delete_derived = request.form.get('delete_derived_ontology') in ('on', 'true', '1')
        derived_ontology_id = request.form.get('derived_ontology_id')

        logger.info(f"Deleting guideline {guideline_id} (actual_guideline_id: {actual_guideline_id})")

        # Delete associated data in order (due to foreign key constraints)
        deleted_counts = {
            'triples': 0,
            'guideline': 0,
            'document': 0
        }

        try:
            # Use no_autoflush to prevent premature queries to related tables
            with db.session.no_autoflush:
                # 1. Delete entity triples associated with the guideline
                if actual_guideline_id:
                    deleted_counts['triples'] = EntityTriple.query.filter_by(
                        guideline_id=actual_guideline_id
                    ).delete(synchronize_session=False)
                    logger.info(f"Deleted {deleted_counts['triples']} triples for guideline {actual_guideline_id}")

                # 2. Delete the guideline entry
                if guideline:
                    db.session.delete(guideline)
                    deleted_counts['guideline'] = 1
                    logger.info(f"Deleted guideline {guideline_id}")
                elif 'document' in locals():
                    # Delete legacy document
                    db.session.delete(document)
                    deleted_counts['document'] = 1
                    logger.info(f"Deleted legacy document {guideline_id}")

                    # Also delete the associated guideline if it exists
                    if actual_guideline_id:
                        guideline_obj = Guideline.query.get(actual_guideline_id)
                        if guideline_obj:
                            db.session.delete(guideline_obj)
                            deleted_counts['guideline'] = 1
                            logger.info(f"Deleted associated guideline {actual_guideline_id}")

                # Optionally delete derived ontology first to avoid orphan
                if delete_derived and derived_ontology_id:
                    try:
                        from app.models.ontology import Ontology
                        derived_ont = Ontology.query.get(int(derived_ontology_id))
                        if derived_ont:
                            logger.info(f"Deleting derived ontology {derived_ontology_id} as requested")
                            db.session.delete(derived_ont)
                    except Exception as e:
                        logger.warning(f"Could not delete derived ontology {derived_ontology_id}: {e}")

                # 3. Delete temporary concepts and document chunks (only for legacy Document approach)
                if 'document' in locals():
                    from app.models.temporary_concept import TemporaryConcept
                    deleted_temp_concepts = TemporaryConcept.query.filter_by(document_id=document.id).delete(synchronize_session=False)
                    if deleted_temp_concepts > 0:
                        logger.info(f"Deleted {deleted_temp_concepts} temporary concepts for document {document.id}")

                    from app.models.document import DocumentChunk
                    deleted_chunks = DocumentChunk.query.filter_by(document_id=document.id).delete(synchronize_session=False)
                    if deleted_chunks > 0:
                        logger.info(f"Deleted {deleted_chunks} document chunks for document {document.id}")

                    # Delete the file if it exists
                    if document.file_path and os.path.exists(document.file_path):
                        try:
                            os.remove(document.file_path)
                            logger.info(f"Deleted file {document.file_path}")
                        except Exception as e:
                            flash(f'Error deleting file: {str(e)}', 'warning')

                    # Delete the document
                    db.session.delete(document)
                else:
                    # For independent Guidelines, no additional file cleanup needed
                    logger.info(f"Independent guideline deletion - no file cleanup needed")

            # Commit all deletions
            db.session.commit()

            # Provide detailed feedback
            if deleted_counts['triples'] > 0:
                flash(f'Guideline deleted successfully along with {deleted_counts["triples"]} associated triples', 'success')
            else:
                flash('Guideline deleted successfully', 'success')
            if delete_derived and derived_ontology_id:
                flash('Derived ontology deleted as well.', 'info')

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error deleting guideline: {str(e)}")
            flash(f'Error deleting guideline: {str(e)}', 'error')
            return redirect(url_for('worlds.view_guideline', id=world.id, document_id=guideline_id))

        return redirect(url_for('worlds.world_guidelines', id=world.id))

    # References routes
    @bp.route('/<int:id>/references', methods=['GET'])
    def world_references(id):
        """Display references for a world."""
        world = World.query.get_or_404(id)

        # Get search query from request parameters
        query = request.args.get('query', '')

        # Get references
        references = None
        try:
            if query:
                # Search with the provided query
                references_data = mcp_client.search_zotero_items(query, limit=10)
                references = {'results': references_data}
            else:
                # Get references based on world content
                references_data = mcp_client.get_references_for_world(world)
                references = {'results': references_data}
        except Exception as e:
            logger.warning(f"Error retrieving references: {str(e)}")
            references = {'results': []}

        return render_template('world_references.html', world=world, references=references, query=query)
