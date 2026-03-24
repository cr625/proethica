"""Scenario CRUD operations and helpers."""

import logging
from flask import request, jsonify, render_template, redirect, url_for, flash
from flask_login import login_required
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.resource import Resource
from app.models.world import World

logger = logging.getLogger(__name__)


def _cleanup_case_scenario_references(scenario):
    """Clean up scenario references in case metadata when deleting a scenario."""
    if not scenario.scenario_metadata:
        return

    source_case_id = scenario.scenario_metadata.get('source_case_id')
    if not source_case_id:
        return

    # Import here to avoid circular imports
    from app.models import Document
    from sqlalchemy.orm.attributes import flag_modified

    case = Document.query.get(source_case_id)
    if not case or not case.doc_metadata:
        return

    scenario_id = scenario.id
    metadata_updated = False

    # Clean up latest_scenario reference
    latest_scenario = case.doc_metadata.get('latest_scenario', {})
    if latest_scenario.get('scenario_id') == scenario_id:
        case.doc_metadata['latest_scenario'] = {}
        metadata_updated = True
        logger.info(f"Removed scenario {scenario_id} from latest_scenario in case {source_case_id}")

    # Clean up scenario_versions array
    scenario_versions = case.doc_metadata.get('scenario_versions', [])
    original_count = len(scenario_versions)

    # Remove all versions that reference this scenario_id
    case.doc_metadata['scenario_versions'] = [
        version for version in scenario_versions
        if version.get('scenario_id') != scenario_id
    ]

    removed_count = original_count - len(case.doc_metadata['scenario_versions'])
    if removed_count > 0:
        metadata_updated = True
        logger.info(f"Removed {removed_count} scenario version(s) for scenario {scenario_id} from case {source_case_id}")

    # Mark metadata as modified for SQLAlchemy to detect changes
    if metadata_updated:
        flag_modified(case, 'doc_metadata')


def register_core_routes(bp):
    """Register scenario CRUD routes on the blueprint."""

    # API endpoints
    @bp.route('/api', methods=['GET'])
    def api_get_scenarios():
        """API endpoint to get all scenarios."""
        scenarios = Scenario.query.all()
        return jsonify({
            'success': True,
            'data': [scenario.to_dict() for scenario in scenarios]
        })

    @bp.route('/api/<int:id>', methods=['GET'])
    def api_get_scenario(id):
        """API endpoint to get a specific scenario by ID."""
        scenario = Scenario.query.get_or_404(id)
        return jsonify({
            'success': True,
            'data': scenario.to_dict()
        })

    # Web routes
    @bp.route('/', methods=['GET'])
    @login_required
    def list_scenarios():
        """Display all scenarios. Requires login since feature is deprecated/WIP."""
        # Get world filter from query parameters
        world_id = request.args.get('world_id', type=int)

        # Filter scenarios by world if specified
        if world_id:
            scenarios = Scenario.query.filter_by(world_id=world_id).all()
        else:
            scenarios = Scenario.query.all()

        worlds = World.query.all()
        return render_template('scenarios.html', scenarios=scenarios, worlds=worlds, selected_world_id=world_id)

    @bp.route('/new', methods=['GET'])
    @login_required
    def new_scenario():
        """Display form to create a new scenario."""
        worlds = World.query.all()
        world_id = request.args.get('world_id', type=int)
        world = None
        if world_id:
            world = World.query.get(world_id)
        return render_template('create_scenario.html', worlds=worlds, world=world)

    @bp.route('/<int:id>', methods=['GET'])
    @login_required
    def view_scenario(id):
        """Display a specific scenario. Requires login since feature is deprecated."""
        scenario = Scenario.query.get_or_404(id)
        return render_template('scenario_detail.html', scenario=scenario)

    @bp.route('/<int:id>/edit', methods=['GET'])
    @login_required
    def edit_scenario(id):
        """Display form to edit an existing scenario."""
        scenario = Scenario.query.get_or_404(id)
        worlds = World.query.all()
        return render_template('edit_scenario.html', scenario=scenario, worlds=worlds)

    @bp.route('/<int:id>/edit', methods=['POST'])
    @login_required
    def update_scenario_form(id):
        """Update an existing scenario from form data."""
        scenario = Scenario.query.get_or_404(id)

        # Get world (required)
        world_id = request.form.get('world_id')
        if not world_id:
            flash('World ID is required', 'danger')
            return redirect(url_for('scenarios.edit_scenario', id=scenario.id))

        try:
            world_id = int(world_id)
            world = World.query.get(world_id)
            if not world:
                flash(f'World with ID {world_id} not found', 'danger')
                return redirect(url_for('scenarios.edit_scenario', id=scenario.id))
        except ValueError:
            flash('Invalid world ID', 'danger')
            return redirect(url_for('scenarios.edit_scenario', id=scenario.id))

        # Update scenario fields
        scenario.name = request.form.get('name', '')
        scenario.description = request.form.get('description', '')
        scenario.world_id = world_id

        db.session.commit()

        flash('Scenario updated successfully', 'success')
        return redirect(url_for('scenarios.view_scenario', id=scenario.id))

    @bp.route('/', methods=['POST'])
    @login_required
    def create_scenario():
        """Create a new scenario."""
        # Check if the request is JSON or form data
        if request.is_json:
            data = request.json
        else:
            data = request.form

        # Get world (required)
        world_id = data.get('world_id')
        if not world_id:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'World ID is required'
                }), 400
            else:
                flash('World ID is required', 'danger')
                return redirect(url_for('scenarios.new_scenario'))

        try:
            world_id = int(world_id)
            world = World.query.get(world_id)
            if not world:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'message': f'World with ID {world_id} not found'
                    }), 404
                else:
                    flash(f'World with ID {world_id} not found', 'danger')
                    return redirect(url_for('scenarios.new_scenario'))
        except ValueError:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Invalid world ID'
                }), 400
            else:
                flash('Invalid world ID', 'danger')
                return redirect(url_for('scenarios.new_scenario'))

        # Create scenario
        scenario = Scenario(
            name=data.get('name', ''),
            description=data.get('description', ''),
            metadata={},
            world_id=world_id
        )
        db.session.add(scenario)

        # Add characters if provided (JSON only)
        if request.is_json:
            for char_data in data.get('characters', []):
                character = Character(
                    scenario=scenario,
                    name=char_data['name'],
                    role=char_data.get('role', ''),
                    attributes=char_data.get('attributes', {})
                )
                db.session.add(character)

                # Add conditions if provided
                for cond_data in char_data.get('conditions', []):
                    condition = Condition(
                        character=character,
                        name=cond_data['name'],
                        description=cond_data.get('description', ''),
                        severity=cond_data.get('severity', 1)
                    )
                    db.session.add(condition)

            # Add resources if provided
            for res_data in data.get('resources', []):
                resource = Resource(
                    scenario=scenario,
                    name=res_data['name'],
                    type=res_data.get('type', ''),
                    quantity=res_data.get('quantity', 1),
                    description=res_data.get('description', '')
                )
                db.session.add(resource)

        db.session.commit()

        if request.is_json:
            return jsonify({
                'success': True,
                'message': 'Scenario created successfully',
                'data': scenario.to_dict()
            }), 201
        else:
            flash('Scenario created successfully', 'success')
            return redirect(url_for('scenarios.view_scenario', id=scenario.id))

    @bp.route('/<int:id>', methods=['PUT'])
    @login_required
    def update_scenario(id):
        """Update an existing scenario."""
        scenario = Scenario.query.get_or_404(id)
        data = request.json

        # Update scenario fields
        if 'name' in data:
            scenario.name = data['name']
        if 'description' in data:
            scenario.description = data['description']
        if 'metadata' in data:
            scenario.metadata = data['metadata']

        # Update world if provided
        if 'world_id' in data:
            world = World.query.get(data['world_id'])
            if not world:
                return jsonify({
                    'success': False,
                    'message': f'World with ID {data["world_id"]} not found'
                }), 404
            scenario.world_id = world.id

        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Scenario updated successfully',
            'data': scenario.to_dict()
        })

    @bp.route('/<int:id>', methods=['DELETE'])
    @login_required
    def delete_scenario(id):
        """Delete a scenario via API."""
        scenario = Scenario.query.get_or_404(id)

        # Clean up case metadata references before deleting scenario
        _cleanup_case_scenario_references(scenario)

        db.session.delete(scenario)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': 'Scenario deleted successfully'
        })

    @bp.route('/<int:id>/delete', methods=['POST'])
    @login_required
    def delete_scenario_form(id):
        """Delete a scenario from web form."""
        scenario = Scenario.query.get_or_404(id)

        # Clean up case metadata references before deleting scenario
        _cleanup_case_scenario_references(scenario)

        db.session.delete(scenario)
        db.session.commit()

        flash('Scenario deleted successfully', 'success')
        return redirect(url_for('scenarios.list_scenarios'))
