from flask import Blueprint, request, jsonify
from app.models.entity import Entity
from app.models.event import Event
from app import db

entities_bp = Blueprint('entities', __name__)

@entities_bp.route('/entities', methods=['POST'])
def create_entity():
    data = request.json
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    entity = Entity(name=data['name'], description=data.get('description'))
    db.session.add(entity)
    db.session.commit()
    return jsonify({'message': 'Entity created', 'entity': {'id': entity.id, 'name': entity.name}}), 201

@entities_bp.route('/events/<int:event_id>/entities', methods=['POST'])
def add_entity_to_event(event_id):
    data = request.json
    if not data or 'entity_id' not in data:
        return jsonify({'error': 'Entity ID is required'}), 400
    
    event = Event.query.get_or_404(event_id)
    entity = Entity.query.get_or_404(data['entity_id'])
    event.entities.append(entity)
    db.session.commit()
    return jsonify({'message': 'Entity added to event'}), 200
