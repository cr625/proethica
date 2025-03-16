from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from app import db
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.condition import Condition
from app.models.resource import Resource
from app.models.domain import Domain
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
    # Get domain filter from query parameters
    domain_id = request.args.get('domain_id', type=int)
    
    # Filter scenarios by domain if specified
    if domain_id:
        scenarios = Scenario.query.filter_by(domain_id=domain_id).all()
    else:
        scenarios = Scenario.query.all()
    
    domains = Domain.query.all()
    return render_template('scenarios.html', scenarios=scenarios, domains=domains, selected_domain_id=domain_id)

@scenarios_bp.route('/new', methods=['GET'])
def new_scenario():
    """Display form to create a new scenario."""
    domains = Domain.query.all()
    return render_template('create_scenario.html', domains=domains)

@scenarios_bp.route('/<int:id>', methods=['GET'])
def view_scenario(id):
    """Display a specific scenario."""
    scenario = Scenario.query.get_or_404(id)
    domains = Domain.query.all()
    return render_template('scenario_detail.html', scenario=scenario, domains=domains)

# Character routes
@scenarios_bp.route('/<int:id>/characters/new', methods=['GET'])
def new_character(id):
    """Display form to add a character to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('create_character.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/characters', methods=['POST'])
def add_character(id):
    """Add a character to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Create character
    character = Character(
        scenario=scenario,
        name=data['name'],
        role=data.get('role', ''),
        attributes=data.get('attributes', {})
    )
    db.session.add(character)
    
    # Add conditions if provided
    for cond_data in data.get('conditions', []):
        condition = Condition(
            character=character,
            name=cond_data['name'],
            description=cond_data.get('description', ''),
            severity=cond_data.get('severity', 1)
        )
        db.session.add(condition)
    
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Character added successfully',
        'data': {
            'id': character.id,
            'name': character.name,
            'role': character.role
        }
    })

# Resource routes
@scenarios_bp.route('/<int:id>/resources/new', methods=['GET'])
def new_resource(id):
    """Display form to add a resource to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('create_resource.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/resources', methods=['POST'])
def add_resource(id):
    """Add a resource to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Create resource
    resource = Resource(
        scenario=scenario,
        name=data['name'],
        type=data.get('type', ''),
        quantity=data.get('quantity', 1),
        description=data.get('description', '')
    )
    db.session.add(resource)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Resource added successfully',
        'data': {
            'id': resource.id,
            'name': resource.name,
            'type': resource.type,
            'quantity': resource.quantity
        }
    })

# Event routes
@scenarios_bp.route('/<int:id>/events/new', methods=['GET'])
def new_event(id):
    """Display form to add an event to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('create_event.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/events', methods=['POST'])
def add_event(id):
    """Add an event to a scenario."""
    from app.models.event import Event
    
    scenario = Scenario.query.get_or_404(id)
    data = request.json
    
    # Get character if provided
    character_id = data.get('character_id')
    character = None
    if character_id:
        character = Character.query.get(character_id)
    
    # Create event
    event = Event(
        scenario=scenario,
        event_time=data['event_time'],
        description=data['description'],
        character=character,
        action_type=data.get('action_type'),
        metadata=data.get('metadata', {})
    )
    db.session.add(event)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'message': 'Event added successfully',
        'data': {
            'id': event.id,
            'event_time': event.event_time.isoformat(),
            'description': event.description
        }
    })

# Decision routes
@scenarios_bp.route('/<int:id>/decisions/new', methods=['GET'])
def new_decision(id):
    """Display form to add a decision to a scenario."""
    scenario = Scenario.query.get_or_404(id)
    return render_template('create_decision.html', scenario=scenario)

@scenarios_bp.route('/<int:id>/decisions', methods=['POST'])
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
        character=character,
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

@scenarios_bp.route('/', methods=['POST'])
def create_scenario():
    """Create a new scenario."""
    # Check if the request is JSON or form data
    if request.is_json:
        data = request.json
    else:
        data = request.form
    
    # Get domain if provided, otherwise use default (Military Medical Triage)
    domain_id = data.get('domain_id')
    if domain_id:
        try:
            domain_id = int(domain_id)
            domain = Domain.query.get(domain_id)
            if not domain:
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'message': f'Domain with ID {domain_id} not found'
                    }), 404
                else:
                    flash(f'Domain with ID {domain_id} not found', 'danger')
                    return redirect(url_for('scenarios.new_scenario'))
        except ValueError:
            if request.is_json:
                return jsonify({
                    'success': False,
                    'message': 'Invalid domain ID'
                }), 400
            else:
                flash('Invalid domain ID', 'danger')
                return redirect(url_for('scenarios.new_scenario'))
    else:
        # Default to Military Medical Triage domain (ID 1)
        domain = Domain.query.get(1)
    
    # Create scenario
    scenario = Scenario(
        name=data.get('name', ''),
        description=data.get('description', ''),
        metadata={},
        domain_id=domain.id
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
    
    # Update domain if provided
    if 'domain_id' in data:
        domain = Domain.query.get(data['domain_id'])
        if not domain:
            return jsonify({
                'success': False,
                'message': f'Domain with ID {data["domain_id"]} not found'
            }), 404
        scenario.domain_id = domain.id
    
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
