from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from flask_login import login_required, current_user
import json
import os
import logging
from app import db
from app.models.world import World
from app.services.ontserve.mcp_client import MCPClient

logger = logging.getLogger(__name__)

mcp_client = MCPClient.get_instance()


def register_concept_routes(bp):
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
