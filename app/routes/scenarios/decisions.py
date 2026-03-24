"""Decision, reference, and simulation routes for scenarios."""

import logging
from flask import request, jsonify, render_template, redirect, url_for
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.services.mcp_client import MCPClient

logger = logging.getLogger(__name__)


def register_decision_routes(bp):
    """Register decision, reference, and simulation routes on the blueprint."""

    @bp.route('/<int:id>/decisions/new', methods=['GET'])
    @login_required
    def new_decision(id):
        """Display form to add a decision to a scenario."""
        scenario = Scenario.query.get_or_404(id)
        return render_template('create_decision.html', scenario=scenario)

    @bp.route('/<int:id>/decisions', methods=['POST'])
    @login_required
    def add_decision(id):
        """Add a decision to a scenario."""
        from app.models.decision import Decision

        scenario = Scenario.query.get_or_404(id)
        data = request.json

        # Get character if provided
        character_id = data.get('character_id')
        character = None
        if character_id:
            character = Character.query.get(character_id)

        # Create decision
        decision = Decision(
            scenario=scenario,
            decision_time=data['decision_time'],
            description=data['description'],
            options=data['options'],
            character_id=character_id,
            context=data.get('context', '')
        )
        db.session.add(decision)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Decision added successfully',
            'data': {
                'id': decision.id,
                'decision_time': decision.decision_time.isoformat(),
                'description': decision.description,
                'options': decision.options
            }
        })

    # References routes
    @bp.route('/<int:id>/references', methods=['GET'])
    def scenario_references(id):
        """Display references for a scenario."""
        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)

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
                # Get references based on scenario content
                references_data = mcp_client.get_references_for_scenario(scenario)
                references = {'results': references_data}
        except Exception as e:
            logger.warning(f"Error retrieving references: {str(e)}")
            references = {'results': []}

        return render_template('scenario_references.html', scenario=scenario, references=references, query=query)

    @bp.route('/<int:id>/references/<item_key>/citation', methods=['GET'])
    def get_reference_citation(id, item_key):
        """Get citation for a reference."""
        scenario = Scenario.query.get_or_404(id)
        style = request.args.get('style', 'apa')

        # Get citation
        try:
            # Get a fresh instance of MCPClient to ensure we're using the most up-to-date instance
            # This is important for testing where we might be mocking the client
            mcp_client_instance = MCPClient.get_instance()
            citation = mcp_client_instance.get_zotero_citation(item_key, style)
            return jsonify({
                'success': True,
                'citation': citation
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    @bp.route('/<int:id>/references/add', methods=['POST'])
    @login_required
    def add_reference(id):
        """Add a reference to the Zotero library."""
        mcp_client = MCPClient.get_instance()
        scenario = Scenario.query.get_or_404(id)
        data = request.json

        # Add reference
        try:
            result = mcp_client.add_zotero_item(
                item_type=data.get('item_type', 'journalArticle'),
                title=data.get('title', ''),
                creators=data.get('creators', []),
                additional_fields=data.get('additional_fields', {})
            )

            return jsonify({
                'success': True,
                'message': 'Reference added successfully',
                'data': result
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 500

    # Simulation route
    @bp.route('/<int:id>/simulate', methods=['GET'])
    def simulate_scenario(id):
        """Redirect to the simulation page."""
        return redirect(url_for('simulation.simulate_scenario', id=id))
