"""
Ontology Utility Functions
-------------------------
Helpers for working with ontologies and their entities
"""

import logging
import json
from datetime import datetime
from app.services.application_context_service import ApplicationContextService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ontology_utils")

def add_entity_to_ontology(ontology_id, entity_data):
    """
    Add an entity to the ontology.
    
    This function adds an entity to the specified ontology and returns the result.
    If the entity already exists, it won't create a duplicate.
    
    Args:
        ontology_id (int): ID of the ontology
        entity_data (dict): Dictionary containing entity data including:
            - label (str): Display label for the entity
            - name (str): Technical name for the entity (usually same as label)
            - description (str): Description of the entity
            - type (str): Entity type (role, condition, resource, action, event, capability)
            - world_id (int): ID of the world this entity belongs to
            
    Returns:
        dict: Result of the operation including:
            - success (bool): Whether the operation was successful
            - message (str): Message explaining the result
            - entity_id (int, optional): ID of the created entity if successful
    """
    try:
        # Use the ApplicationContextService to interact with the database
        app_context = ApplicationContextService()
        
        # Check entity type is valid
        valid_types = ['role', 'condition', 'resource', 'action', 'event', 'capability']
        entity_type = entity_data.get('type', '').lower()
        
        if entity_type not in valid_types:
            return {
                'success': False,
                'message': f"Invalid entity type: {entity_type}. Must be one of: {', '.join(valid_types)}"
            }
        
        # Check if entity already exists in this ontology
        label = entity_data.get('label', '')
        existing_entities = app_context.get_world_entities(entity_data.get('world_id'))
        
        if existing_entities and existing_entities.get('entities'):
            entity_type_plural = f"{entity_type}s"  # Convert to plural form for lookup
            for existing in existing_entities.get('entities', {}).get(entity_type_plural, []):
                if existing.get('label', '').lower() == label.lower():
                    # Entity already exists, return its ID
                    return {
                        'success': True,
                        'message': f"{entity_type.capitalize()} '{label}' already exists",
                        'entity_id': existing.get('id')
                    }
        
        # Entity doesn't exist, create it
        # Typically we would call a proper service method here,
        # but for this implementation we'll use the ApplicationContextService directly
        
        # Create entity data for storage
        entity_to_create = {
            'label': label,
            'name': entity_data.get('name', label),
            'description': entity_data.get('description', ''),
            'type': entity_type,
            'ontology_id': ontology_id,
            'world_id': entity_data.get('world_id'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'metadata': json.dumps({
                'source': 'world_entity_integration',
                'auto_generated': True
            })
        }
        
        # Insert into the database
        # In a real implementation, this would use proper model methods
        # For now, we'll use a generic "create_entity" method that should exist in ApplicationContextService
        result = app_context.create_entity(entity_type, entity_to_create)
        
        if not result or not result.get('id'):
            return {
                'success': False,
                'message': f"Failed to create {entity_type}: {label}"
            }
            
        logger.info(f"Created {entity_type} '{label}' with ID {result.get('id')}")
        
        # Return success response
        return {
            'success': True,
            'message': f"Successfully created {entity_type}: {label}",
            'entity_id': result.get('id')
        }
        
    except Exception as e:
        logger.error(f"Error adding entity to ontology: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f"Error: {str(e)}"
        }

def get_entity_from_ontology(ontology_id, entity_type, entity_id):
    """
    Get an entity from the ontology.
    
    Args:
        ontology_id (int): ID of the ontology
        entity_type (str): Type of entity to get (role, condition, resource, action, event, capability)
        entity_id (int): ID of the entity
        
    Returns:
        dict: Entity data if found, None otherwise
    """
    try:
        app_context = ApplicationContextService()
        return app_context.get_entity(entity_type, entity_id)
    except Exception as e:
        logger.error(f"Error getting entity from ontology: {str(e)}")
        return None
