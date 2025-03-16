from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.resource import Resource
from app.services import EventEngine, DecisionEngine

scenarios_bp = Blueprint('scenarios', __name__, url_prefix='/scenarios')

# API endpoints
@scenarios_bp.route('/api', methods=['GET'])
def api_get_scenarios():
    """API endpoint to get all scenarios."""
    scenarios = Scenario.query.all()
    return jsonify({
        'success': True,
        'data': [scenario.to_dict() for scenario in scenarios]
    })

@scenarios_bp.route('/api/<int:id>', methods=['GET'])
def api_get_scenario(id):
    """API endpoint to get a specific scenario by ID."""
    scenario = Scenario.query.get_or_404(id)
    return jsonify({
        'success': True,
        'data': scenario.to_dict()
    })

# Web routes
@scenarios_bp.route('/', methods=['GET'])
def list_scenarios():
    """Display all scenarios."""
    scenarios = Scenario.query.all()
    return render_template('scenarios.html', scenarios=scenarios)

@scenarios_bp.route('/<int:id>', methods=['GET'])
def view_scenario(id):
    """Display a specific scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('scenario_detail.html', scenario=scenario)

@scenarios_bp.route('/', methods=['POST'])
def create_scenario():
    """Create a new scenario."""
    data = request.json
    
    # Create scenario
    scenario = Scenario(
        name=data['name'],
        description=data.get('description', ''),
        metadata=data.get('metadata', {})
    )
    db.session.add(scenario)
    
    # Add characters if provided
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
    
    return jsonify({
        'success': True,
        'message': 'Scenario created successfully',
        'data': scenario.to_dict()
    }), 201

@scenarios_bp.route('/<int:id>', methods=['PUT'])
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
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Scenario updated successfully',
        'data': scenario.to_dict()
    })

@scenarios_bp.route('/<int:id>', methods=['DELETE'])
def delete_scenario(id):
    """Delete a scenario."""
    scenario = Scenario.query.get_or_404(id)
    db.session.delete(scenario)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Scenario deleted successfully'
    })
