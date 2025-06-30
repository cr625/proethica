#!/usr/bin/env python3
"""
Utility module for managing entities (characters, resources, conditions, etc.) in the ProEthica system.
This module centralizes functions that were previously scattered across multiple scripts.
"""

import os
import sys
from datetime import datetime, timedelta
from rdflib import Graph, Namespace, RDF, RDFS, URIRef

from app import db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.resource import Resource
from app.models.condition import Condition
from app.models.condition_type import ConditionType
from app.models.resource_type import ResourceType
from app.models.role import Role
from app.models.event import Event, Action


def populate_entity_types_from_ontology(world_id, ontology_path=None):
    """
    Populate roles, condition types, and resource types from an ontology file.
    
    Args:
        world_id: ID of the world to populate entity types for
        ontology_path: Path to the ontology file, or None to use the world's ontology_source
    
    Returns:
        Dictionary with counts of entities created/updated
    """
    # Get the world
    world = World.query.get(world_id)
    if not world:
        raise ValueError(f"World with ID {world_id} not found")
    
    # Get the ontology path
    if not ontology_path:
        if not world.ontology_source:
            raise ValueError(f"World {world.name} has no ontology_source and no explicit ontology_path provided")
        ontology_path = world.ontology_source
        
        # If ontology_path is not an absolute path, resolve it relative to the project root
        if not os.path.isabs(ontology_path):
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            ontology_path = os.path.join(project_root, ontology_path)
    
    # Check if the ontology file exists
    if not os.path.exists(ontology_path):
        raise FileNotFoundError(f"Ontology file not found: {ontology_path}")
    
    # Load and parse the ontology
    g = Graph()
    g.parse(ontology_path, format="turtle")
    
    # Define namespace based on the ontology
    # This is a best guess - specific ontologies may need more precise namespaces
    base_uri = next(g.subjects(RDF.type, None))
    base_uri_str = str(base_uri)
    namespace_prefix = base_uri_str.rsplit('#', 1)[0] + '#'
    ONT = Namespace(namespace_prefix)
    
    # Call the individual population functions
    role_count = populate_roles_from_ontology(g, ONT, world)
    condition_count = populate_condition_types_from_ontology(g, ONT, world)
    resource_count = populate_resource_types_from_ontology(g, ONT, world)
    
    return {
        'roles': role_count,
        'condition_types': condition_count,
        'resource_types': resource_count
    }


def populate_roles_from_ontology(g, ONT, world):
    """
    Populate roles from the ontology.
    
    Args:
        g: RDFLib Graph object containing the parsed ontology
        ONT: Namespace object for the ontology
        world: World object to add roles to
    
    Returns:
        Count of roles created/updated
    """
    count = 0
    
    # Look for CharacterType or Role classes
    role_classes = [ONT.CharacterType, ONT.Role]
    for role_class in role_classes:
        # Get all entities that are character types
        for s in g.subjects(RDF.type, role_class):
            if isinstance(s, URIRef):
                # Get the role name (the part after the #)
                role_name = str(s).split('#')[-1]
                
                # Get the label
                label = None
                for label_obj in g.objects(s, RDFS.label):
                    label = str(label_obj)
                    break
                
                if not label:
                    label = role_name
                
                # Get the description
                description = None
                for desc_obj in g.objects(s, RDFS.comment):
                    description = str(desc_obj)
                    break
                
                # Get the tier
                tier = None
                for tier_obj in g.objects(s, ONT.hasTier):
                    for tier_label in g.objects(tier_obj, RDFS.label):
                        tier_str = str(tier_label)
                        # Extract the tier number
                        if "Tier " in tier_str:
                            try:
                                tier = int(tier_str.split("Tier ")[1])
                            except ValueError:
                                pass
                        break
                
                # Get the ontology URI
                ontology_uri = str(s)
                
                # Check if the role already exists
                existing_role = Role.query.filter_by(name=label, world_id=world.id).first()
                if existing_role:
                    existing_role.description = description
                    existing_role.tier = tier
                    existing_role.ontology_uri = ontology_uri
                else:
                    role = Role(
                        name=label,
                        description=description,
                        world_id=world.id,
                        tier=tier,
                        ontology_uri=ontology_uri
                    )
                    db.session.add(role)
                count += 1
    
    db.session.commit()
    return count


def populate_condition_types_from_ontology(g, ONT, world):
    """
    Populate condition types from the ontology.
    
    Args:
        g: RDFLib Graph object containing the parsed ontology
        ONT: Namespace object for the ontology
        world: World object to add condition types to
    
    Returns:
        Count of condition types created/updated
    """
    count = 0
    
    # Look for ConditionType class
    condition_classes = [ONT.ConditionType, ONT.Condition]
    for condition_class in condition_classes:
        # Get all entities that are condition types
        for s in g.subjects(RDF.type, condition_class):
            if isinstance(s, URIRef):
                # Get the condition type name (the part after the #)
                condition_type_name = str(s).split('#')[-1]
                
                # Get the label
                label = None
                for label_obj in g.objects(s, RDFS.label):
                    label = str(label_obj)
                    break
                
                if not label:
                    label = condition_type_name
                
                # Get the description
                description = None
                for desc_obj in g.objects(s, RDFS.comment):
                    description = str(desc_obj)
                    break
                
                # Get the category
                category = None
                # Try to determine category from class hierarchy
                for _, _, parent in g.triples((s, RDFS.subClassOf, None)):
                    if parent != ONT.ConditionType and parent != ONT.Condition:
                        parent_name = str(parent).split('#')[-1]
                        category = parent_name
                        break
                
                if not category:
                    category = "General"
                
                # Get the ontology URI
                ontology_uri = str(s)
                
                # Check if the condition type already exists
                existing_condition_type = ConditionType.query.filter_by(name=label, world_id=world.id).first()
                if existing_condition_type:
                    existing_condition_type.description = description
                    existing_condition_type.category = category
                    existing_condition_type.ontology_uri = ontology_uri
                else:
                    condition_type = ConditionType(
                        name=label,
                        description=description,
                        world_id=world.id,
                        category=category,
                        ontology_uri=ontology_uri,
                        severity_range={"min": 1, "max": 10}
                    )
                    db.session.add(condition_type)
                count += 1
    
    db.session.commit()
    return count


def populate_resource_types_from_ontology(g, ONT, world):
    """
    Populate resource types from the ontology.
    
    Args:
        g: RDFLib Graph object containing the parsed ontology
        ONT: Namespace object for the ontology
        world: World object to add resource types to
    
    Returns:
        Count of resource types created/updated
    """
    count = 0
    
    # Look for ResourceType class
    resource_classes = [ONT.ResourceType, ONT.Resource]
    for resource_class in resource_classes:
        # Get all entities that are resource types
        for s in g.subjects(RDF.type, resource_class):
            if isinstance(s, URIRef):
                # Get the resource type name (the part after the #)
                resource_type_name = str(s).split('#')[-1]
                
                # Get the label
                label = None
                for label_obj in g.objects(s, RDFS.label):
                    label = str(label_obj)
                    break
                
                if not label:
                    label = resource_type_name
                
                # Get the description
                description = None
                for desc_obj in g.objects(s, RDFS.comment):
                    description = str(desc_obj)
                    break
                
                # Get the category
                category = None
                # Try to determine category from class hierarchy
                for _, _, parent in g.triples((s, RDFS.subClassOf, None)):
                    if parent != ONT.ResourceType and parent != ONT.Resource:
                        parent_name = str(parent).split('#')[-1]
                        category = parent_name
                        break
                
                if not category:
                    category = "General"
                
                # Get the ontology URI
                ontology_uri = str(s)
                
                # Check if the resource type already exists
                existing_resource_type = ResourceType.query.filter_by(name=label, world_id=world.id).first()
                if existing_resource_type:
                    existing_resource_type.description = description
                    existing_resource_type.category = category
                    existing_resource_type.ontology_uri = ontology_uri
                else:
                    resource_type = ResourceType(
                        name=label,
                        description=description,
                        world_id=world.id,
                        category=category,
                        ontology_uri=ontology_uri
                    )
                    db.session.add(resource_type)
                count += 1
    
    db.session.commit()
    return count


def create_or_update_character(scenario_id, name, role_name, attributes=None, conditions=None):
    """
    Create or update a character in a scenario.
    
    Args:
        scenario_id: ID of the scenario to add the character to
        name: Name of the character
        role_name: Name of the role for the character
        attributes: Optional dictionary of character attributes
        conditions: Optional list of dictionaries with condition data (type, description, severity)
    
    Returns:
        Character object that was created or updated
    """
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario with ID {scenario_id} not found")
    
    # Find or create the role
    role = Role.query.filter_by(name=role_name, world_id=scenario.world_id).first()
    if not role:
        role = Role(
            name=role_name,
            description=f"Placeholder role for {role_name}",
            world_id=scenario.world_id
        )
        db.session.add(role)
        db.session.flush()
    
    # Find or create the character
    character = Character.query.filter_by(name=name, scenario_id=scenario_id).first()
    if not character:
        character = Character(
            name=name,
            scenario_id=scenario_id,
            role_id=role.id,
            role=role_name,  # Legacy field
            attributes=attributes or {}
        )
        db.session.add(character)
        db.session.flush()
    else:
        character.role_id = role.id
        character.role = role_name
        if attributes:
            character.attributes = attributes
    
    # Add conditions to the character
    if conditions:
        for condition_data in conditions:
            # Find or create the condition type
            condition_type = ConditionType.query.filter_by(
                name=condition_data["type"], 
                world_id=scenario.world_id
            ).first()
            
            if not condition_type:
                condition_type = ConditionType(
                    name=condition_data["type"],
                    description=f"Placeholder condition type for {condition_data['type']}",
                    world_id=scenario.world_id,
                    category=condition_data.get("category", "General"),
                    severity_range={"min": 1, "max": 10}
                )
                db.session.add(condition_type)
                db.session.flush()
            
            # Find or create the condition
            condition = Condition.query.filter_by(
                character_id=character.id,
                name=condition_data["type"]
            ).first()
            
            if not condition:
                condition = Condition(
                    character_id=character.id,
                    name=condition_data["type"],
                    condition_type_id=condition_type.id,
                    description=condition_data["description"],
                    severity=condition_data.get("severity", 5)
                )
                db.session.add(condition)
            else:
                condition.condition_type_id = condition_type.id
                condition.description = condition_data["description"]
                condition.severity = condition_data.get("severity", 5)
    
    db.session.commit()
    return character


def create_or_update_resource(scenario_id, name, resource_type_name, description=None, quantity=1, category=None):
    """
    Create or update a resource in a scenario.
    
    Args:
        scenario_id: ID of the scenario to add the resource to
        name: Name of the resource
        resource_type_name: Name of the resource type
        description: Optional description of the resource
        quantity: Optional quantity of the resource
        category: Optional category for the resource type if it needs to be created
    
    Returns:
        Resource object that was created or updated
    """
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario with ID {scenario_id} not found")
    
    # Find or create the resource type
    resource_type = ResourceType.query.filter_by(
        name=resource_type_name, 
        world_id=scenario.world_id
    ).first()
    
    if not resource_type:
        resource_type = ResourceType(
            name=resource_type_name,
            description=f"Placeholder resource type for {resource_type_name}",
            world_id=scenario.world_id,
            category=category or "General"
        )
        db.session.add(resource_type)
        db.session.flush()
    
    # Find or create the resource
    resource = Resource.query.filter_by(
        name=name,
        scenario_id=scenario_id
    ).first()
    
    if not resource:
        resource = Resource(
            name=name,
            scenario_id=scenario_id,
            resource_type_id=resource_type.id,
            type=resource_type_name,  # Legacy field
            quantity=quantity,
            description=description or f"Resource of type {resource_type_name}"
        )
        db.session.add(resource)
    else:
        resource.resource_type_id = resource_type.id
        resource.type = resource_type_name
        resource.quantity = quantity
        if description:
            resource.description = description
    
    db.session.commit()
    return resource


def create_timeline_event(scenario_id, description, character_id=None, event_time=None, parameters=None):
    """
    Create a timeline event in a scenario.
    
    Args:
        scenario_id: ID of the scenario to add the event to
        description: Description of the event
        character_id: Optional ID of the character involved in the event
        event_time: Optional datetime for the event, defaults to current time
        parameters: Optional dictionary of event parameters
    
    Returns:
        Event object that was created
    """
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario with ID {scenario_id} not found")
    
    # Create the event
    event = Event(
        scenario_id=scenario_id,
        character_id=character_id,
        event_time=event_time or datetime.now(),
        description=description,
        parameters=parameters or {}
    )
    db.session.add(event)
    db.session.commit()
    
    return event


def create_timeline_action(scenario_id, name, description, character_id=None, action_time=None, 
                          action_type=None, parameters=None, is_decision=False, options=None):
    """
    Create a timeline action in a scenario.
    
    Args:
        scenario_id: ID of the scenario to add the action to
        name: Name of the action
        description: Description of the action
        character_id: Optional ID of the character performing the action
        action_time: Optional datetime for the action, defaults to current time
        action_type: Optional type of action
        parameters: Optional dictionary of action parameters
        is_decision: Whether this action is a decision point
        options: Optional list of decision options (required if is_decision is True)
    
    Returns:
        Action object that was created
    """
    # Get the scenario
    scenario = Scenario.query.get(scenario_id)
    if not scenario:
        raise ValueError(f"Scenario with ID {scenario_id} not found")
    
    # If this is a decision, ensure we have options
    if is_decision and not options:
        raise ValueError("Options must be provided for decision actions")
    
    # Create the action
    action = Action(
        name=name,
        description=description,
        scenario_id=scenario_id,
        character_id=character_id,
        action_time=action_time or datetime.now(),
        action_type=action_type or "GenericAction",
        parameters=parameters or {},
        is_decision=is_decision,
        options=options if is_decision else []
    )
    db.session.add(action)
    db.session.commit()
    
    return action


def create_ethical_scenario(world_name, scenario_name, scenario_description, characters, resources, timeline):
    """
    Create a complete ethical scenario with characters, resources, and timeline items.
    
    Args:
        world_name: Name of the world for the scenario
        scenario_name: Name of the scenario
        scenario_description: Description of the scenario
        characters: Dictionary mapping character keys to character data
        resources: List of dictionaries with resource data
        timeline: Dictionary with 'events' and 'actions' lists
    
    Returns:
        ID of the created scenario
    """
    from app import create_app
    
    app = create_app()
    with app.app_context():
        # Find the world
        world = World.query.filter_by(name=world_name).first()
        if not world:
            raise ValueError(f"World '{world_name}' not found")
        
        # Create the scenario
        scenario = Scenario(
            name=scenario_name,
            description=scenario_description,
            world_id=world.id
        )
        db.session.add(scenario)
        db.session.commit()
        
        # Add characters
        character_objects = {}
        for char_key, char_data in characters.items():
            character = create_or_update_character(
                scenario_id=scenario.id,
                name=char_data["name"],
                role_name=char_data["role"],
                attributes=char_data.get("attributes"),
                conditions=char_data.get("conditions")
            )
            character_objects[char_key] = character
        
        # Add resources
        for resource_data in resources:
            create_or_update_resource(
                scenario_id=scenario.id,
                name=resource_data["name"],
                resource_type_name=resource_data["type"],
                description=resource_data.get("description"),
                quantity=resource_data.get("quantity", 1),
                category=resource_data.get("category")
            )
        
        # Base time for the timeline
        base_time = datetime.now() - timedelta(days=7)  # Start a week ago
        
        # Add events
        for event_data in timeline.get("events", []):
            # Get the character if specified
            character_id = None
            if "character" in event_data:
                character_key = event_data["character"]
                if character_key in character_objects:
                    character_id = character_objects[character_key].id
            
            # Calculate event time
            days = event_data.get("days", 0)
            hours = event_data.get("hours", 0)
            minutes = event_data.get("minutes", 0)
            event_time = base_time + timedelta(days=days, hours=hours, minutes=minutes)
            
            create_timeline_event(
                scenario_id=scenario.id,
                description=event_data["description"],
                character_id=character_id,
                event_time=event_time,
                parameters=event_data.get("parameters")
            )
        
        # Add actions
        for action_data in timeline.get("actions", []):
            # Get the character if specified
            character_id = None
            if "character" in action_data:
                character_key = action_data["character"]
                if character_key in character_objects:
                    character_id = character_objects[character_key].id
            
            # Calculate action time
            days = action_data.get("days", 0)
            hours = action_data.get("hours", 0)
            minutes = action_data.get("minutes", 0)
            action_time = base_time + timedelta(days=days, hours=hours, minutes=minutes)
            
            create_timeline_action(
                scenario_id=scenario.id,
                name=action_data["name"],
                description=action_data["description"],
                character_id=character_id,
                action_time=action_time,
                action_type=action_data.get("type"),
                parameters=action_data.get("parameters"),
                is_decision=action_data.get("is_decision", False),
                options=action_data.get("options")
            )
        
        return scenario.id


if __name__ == "__main__":
    # This module is intended to be imported, not run directly
    print("This module provides utility functions for entity management.")
    print("Import it into your scripts or the application to use its functionality.")
