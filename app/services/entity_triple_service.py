import uuid
import numpy as np
from datetime import datetime
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS
from app import db
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple
from app.models.character import Character
from app.models.event import Event, Action
from app.models.resource import Resource
from app.models.entity import Entity
from sqlalchemy import text, func
from typing import List, Dict, Tuple, Optional, Union, Any

# Define namespaces for our RDF graph
PROETHICA = Namespace("http://proethica.org/ontology/")
ENG_ETHICS = Namespace("http://proethica.org/ontology/engineering-ethics#")
PROETHICA_CHARACTER = Namespace("http://proethica.org/character/")
PROETHICA_EVENT = Namespace("http://proethica.org/event/")
PROETHICA_ACTION = Namespace("http://proethica.org/action/")
PROETHICA_RESOURCE = Namespace("http://proethica.org/resource/")
PROETHICA_ENTITY = Namespace("http://proethica.org/entity/")
PROETHICA_SCENARIO = Namespace("http://proethica.org/scenario/")

class EntityTripleService:
    """
    Service for handling RDF triple operations across all entity types.
    This service provides methods for converting between application models
    and RDF triples, and for querying the unified triple store.
    """
    
    def __init__(self):
        # Common RDF namespaces
        self.namespaces = {
            'rdf': RDF,
            'rdfs': RDFS,
            'proethica': PROETHICA,
            'eng': ENG_ETHICS,
            'character': PROETHICA_CHARACTER,
            'event': PROETHICA_EVENT,
            'action': PROETHICA_ACTION,
            'resource': PROETHICA_RESOURCE,
            'entity': PROETHICA_ENTITY,
            'scenario': PROETHICA_SCENARIO
        }
    
    def get_namespaces(self):
        """Return the namespaces dictionary."""
        return self.namespaces
    
    def register_namespace(self, prefix, uri):
        """Register a new namespace."""
        self.namespaces[prefix] = Namespace(uri)
        return self.namespaces[prefix]
    
    def generate_uri(self, entity_type, entity_name, entity_id=None, scenario_id=None):
        """Generate a unique URI for an entity."""
        # Sanitize name for URI
        name_part = entity_name.lower().replace(' ', '_')
        
        # Add scenario ID if provided
        if scenario_id:
            name_part = f"{scenario_id}_{name_part}"
        
        # Add entity ID if provided
        if entity_id:
            name_part = f"{name_part}_{entity_id}"
        else:
            # Add a unique identifier to ensure uniqueness
            unique_id = str(uuid.uuid4())[:8]
            name_part = f"{name_part}_{unique_id}"
        
        # Select the appropriate namespace based on entity type
        if entity_type == 'character':
            return PROETHICA_CHARACTER[name_part]
        elif entity_type == 'event':
            return PROETHICA_EVENT[name_part]
        elif entity_type == 'action':
            return PROETHICA_ACTION[name_part]
        elif entity_type == 'resource':
            return PROETHICA_RESOURCE[name_part]
        else:
            return PROETHICA_ENTITY[name_part]
    
    def add_triple(self, subject: str, predicate: str, obj: Any, 
                   is_literal: bool = True, graph: Optional[str] = None,
                   entity_type: str = None, entity_id: Optional[int] = None, 
                   scenario_id: Optional[int] = None,
                   character_id: Optional[int] = None,
                   subject_embedding: Optional[List[float]] = None,
                   predicate_embedding: Optional[List[float]] = None,
                   object_embedding: Optional[List[float]] = None) -> EntityTriple:
        """
        Add a new triple to the store.
        
        Args:
            subject: Subject URI string
            predicate: Predicate URI string
            obj: Object value (string URI or literal value)
            is_literal: True if object is a literal, False if it's a URI
            graph: Optional named graph identifier
            entity_type: Entity type ('character', 'event', 'action', 'resource')
            entity_id: Optional entity ID reference
            scenario_id: Optional scenario ID reference
            character_id: Optional character ID reference (for backward compatibility)
            subject_embedding: Optional vector embedding for subject
            predicate_embedding: Optional vector embedding for predicate
            object_embedding: Optional vector embedding for object
            
        Returns:
            The created EntityTriple object
        """
        # Validate entity type
        if entity_type not in ['character', 'event', 'action', 'resource', 'entity']:
            raise ValueError(f"Invalid entity type: {entity_type}")
        
        # For character entities, set character_id for backward compatibility
        if entity_type == 'character' and not character_id and entity_id:
            character_id = entity_id
        
        triple = EntityTriple(
            subject=subject,
            predicate=predicate,
            object_literal=obj if is_literal else None,
            object_uri=obj if not is_literal else None,
            is_literal=is_literal,
            graph=graph,
            entity_type=entity_type,
            entity_id=entity_id,
            scenario_id=scenario_id,
            character_id=character_id,
            subject_embedding=subject_embedding,
            predicate_embedding=predicate_embedding,
            object_embedding=object_embedding,
            triple_metadata={}
        )
        
        db.session.add(triple)
        db.session.flush()  # Get the ID without committing
        return triple
    
    def find_triples(self, subject=None, predicate=None, obj=None, 
                     is_literal=None, graph=None, entity_type=None, 
                     entity_id=None, scenario_id=None, character_id=None, 
                     limit=None):
        """
        Find triples matching the given criteria.
        Any parameter can be None to indicate no filter for that field.
        
        Returns:
            List of EntityTriple objects matching the criteria
        """
        query = db.session.query(EntityTriple)
        
        if subject is not None:
            query = query.filter(EntityTriple.subject == subject)
        
        if predicate is not None:
            query = query.filter(EntityTriple.predicate == predicate)
        
        if obj is not None:
            if is_literal is True:
                query = query.filter(EntityTriple.object_literal == obj)
            elif is_literal is False:
                query = query.filter(EntityTriple.object_uri == obj)
            else:
                # If is_literal not specified, check both fields
                query = query.filter((EntityTriple.object_literal == obj) | 
                                    (EntityTriple.object_uri == obj))
        
        if is_literal is not None and obj is None:
            query = query.filter(EntityTriple.is_literal == is_literal)
        
        if graph is not None:
            query = query.filter(EntityTriple.graph == graph)
        
        if entity_type is not None:
            query = query.filter(EntityTriple.entity_type == entity_type)
        
        if entity_id is not None:
            query = query.filter(EntityTriple.entity_id == entity_id)
        
        if scenario_id is not None:
            query = query.filter(EntityTriple.scenario_id == scenario_id)
        
        if character_id is not None:
            query = query.filter(EntityTriple.character_id == character_id)
        
        if limit is not None:
            query = query.limit(limit)
        
        return query.all()
    
    def delete_triples(self, subject=None, predicate=None, obj=None, 
                       is_literal=None, graph=None, entity_type=None, 
                       entity_id=None, scenario_id=None, character_id=None):
        """
        Delete triples matching the given criteria.
        Any parameter can be None to indicate no filter for that field.
        
        Returns:
            Number of triples deleted
        """
        query = db.session.query(EntityTriple)
        
        if subject is not None:
            query = query.filter(EntityTriple.subject == subject)
        
        if predicate is not None:
            query = query.filter(EntityTriple.predicate == predicate)
        
        if obj is not None:
            if is_literal is True:
                query = query.filter(EntityTriple.object_literal == obj)
            elif is_literal is False:
                query = query.filter(EntityTriple.object_uri == obj)
            else:
                # If is_literal not specified, check both fields
                query = query.filter((EntityTriple.object_literal == obj) | 
                                    (EntityTriple.object_uri == obj))
        
        if is_literal is not None and obj is None:
            query = query.filter(EntityTriple.is_literal == is_literal)
        
        if graph is not None:
            query = query.filter(EntityTriple.graph == graph)
        
        if entity_type is not None:
            query = query.filter(EntityTriple.entity_type == entity_type)
        
        if entity_id is not None:
            query = query.filter(EntityTriple.entity_id == entity_id)
        
        if scenario_id is not None:
            query = query.filter(EntityTriple.scenario_id == scenario_id)
        
        if character_id is not None:
            query = query.filter(EntityTriple.character_id == character_id)
        
        count = query.delete(synchronize_session=False)
        db.session.flush()
        return count
    
    def character_to_triples(self, character: Character, commit=True):
        """
        Convert a Character object to RDF triples.
        
        Args:
            character: Character object
            commit: Whether to commit the session after adding triples
            
        Returns:
            List of created EntityTriple objects
        """
        triples = []
        
        # Generate URI for the character
        character_uri = self.generate_uri('character', character.name, character.id, character.scenario_id)
        character_uri_str = str(character_uri)
        
        # Graph identifier (scenario ID)
        graph = f"scenario_{character.scenario_id}"
        
        # Add basic character information
        triples.append(self.add_triple(
            character_uri_str, 
            str(RDF.type), 
            str(PROETHICA.Character), 
            is_literal=False,
            graph=graph,
            entity_type='character',
            entity_id=character.id,
            scenario_id=character.scenario_id,
            character_id=character.id
        ))
        
        # Add name
        triples.append(self.add_triple(
            character_uri_str,
            str(RDFS.label),
            character.name,
            is_literal=True,
            graph=graph,
            entity_type='character',
            entity_id=character.id,
            scenario_id=character.scenario_id,
            character_id=character.id
        ))
        
        # Add role information
        if character.role_from_role:
            role = character.role_from_role
            
            # Add role type
            if role.ontology_uri:
                triples.append(self.add_triple(
                    character_uri_str,
                    str(RDF.type),
                    role.ontology_uri,
                    is_literal=False,
                    graph=graph,
                    entity_type='character',
                    entity_id=character.id,
                    scenario_id=character.scenario_id,
                    character_id=character.id
                ))
            
            # Add role name
            triples.append(self.add_triple(
                character_uri_str,
                str(PROETHICA.hasRole),
                role.name,
                is_literal=True,
                graph=graph,
                entity_type='character',
                entity_id=character.id,
                scenario_id=character.scenario_id,
                character_id=character.id
            ))
            
            # Add explicit role relationship
            triples.append(self.add_triple(
                character_uri_str,
                str(PROETHICA.hasRoleID),
                str(role.id),
                is_literal=True,
                graph=graph,
                entity_type='character',
                entity_id=character.id,
                scenario_id=character.scenario_id,
                character_id=character.id
            ))
        
        # Add attributes as triples
        if character.attributes:
            for key, value in character.attributes.items():
                # Create predicate URI based on attribute name
                predicate = PROETHICA[key]
                
                # Determine if value is a literal or URI
                is_literal = isinstance(value, (str, int, float, bool)) or value is None
                
                triples.append(self.add_triple(
                    character_uri_str,
                    str(predicate),
                    str(value) if value is not None else "None",
                    is_literal=is_literal,
                    graph=graph,
                    entity_type='character',
                    entity_id=character.id,
                    scenario_id=character.scenario_id,
                    character_id=character.id
                ))
        
        # Commit the session if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def event_to_triples(self, event: Event, commit=True):
        """
        Convert an Event object to RDF triples.
        
        Args:
            event: Event object
            commit: Whether to commit the session after adding triples
            
        Returns:
            List of created EntityTriple objects
        """
        triples = []
        
        # Generate URI for the event
        event_uri = self.generate_uri('event', event.description[:50], event.id, event.scenario_id)
        event_uri_str = str(event_uri)
        
        # Graph identifier (scenario ID)
        graph = f"scenario_{event.scenario_id}"
        
        # Add basic event information
        triples.append(self.add_triple(
            event_uri_str, 
            str(RDF.type), 
            str(PROETHICA.Event), 
            is_literal=False,
            graph=graph,
            entity_type='event',
            entity_id=event.id,
            scenario_id=event.scenario_id
        ))
        
        # Add description
        triples.append(self.add_triple(
            event_uri_str,
            str(RDFS.label),
            event.description,
            is_literal=True,
            graph=graph,
            entity_type='event',
            entity_id=event.id,
            scenario_id=event.scenario_id
        ))
        
        # Add event time with BFO temporal region data
        if event.event_time:
            time_triple = self.add_triple(
                event_uri_str,
                str(PROETHICA.occursAt),
                event.event_time.isoformat(),
                is_literal=True,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            )
            
            # Add BFO temporal region type - default to instant (zero-dimensional temporal region)
            time_triple.temporal_region_type = "BFO_0000148"  # zero-dimensional temporal region
            time_triple.temporal_start = event.event_time
            time_triple.temporal_end = None  # Instant has no end time
            time_triple.temporal_granularity = "seconds"
            
            triples.append(time_triple)
        
        # Add character relationship
        if event.character_id:
            character = event.character
            if character:
                character_uri = self.generate_uri('character', character.name, character.id, character.scenario_id)
                
                triples.append(self.add_triple(
                    event_uri_str,
                    str(PROETHICA.hasParticipant),
                    str(character_uri),
                    is_literal=False,
                    graph=graph,
                    entity_type='event',
                    entity_id=event.id,
                    scenario_id=event.scenario_id
                ))
        
        # Add action relationship
        if event.action_id:
            action = event.action
            if action:
                action_uri = self.generate_uri('action', action.name or "action", action.id, action.scenario_id)
                
                action_uri_str = str(action_uri)
                
                triples.append(self.add_triple(
                    action_uri_str,
                    str(PROETHICA.generates),
                    str(event_uri),
                    is_literal=False,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
                
                triples.append(self.add_triple(
                    event_uri_str,
                    str(PROETHICA.generatedBy),
                    str(action_uri),
                    is_literal=False,
                    graph=graph,
                    entity_type='event',
                    entity_id=event.id,
                    scenario_id=event.scenario_id
                ))
        
        # Add entity relationships
        for entity in event.entities:
            entity_uri = self.generate_uri('entity', entity.name, entity.id, event.scenario_id)
            
            triples.append(self.add_triple(
                event_uri_str,
                str(PROETHICA.involves),
                str(entity_uri),
                is_literal=False,
                graph=graph,
                entity_type='event',
                entity_id=event.id,
                scenario_id=event.scenario_id
            ))
        
        # Add parameters as triples
        if event.parameters:
            for key, value in event.parameters.items():
                # Create predicate URI based on parameter name
                predicate = PROETHICA[f"hasParameter_{key}"]
                
                # Determine if value is a literal or URI
                is_literal = isinstance(value, (str, int, float, bool)) or value is None
                
                triples.append(self.add_triple(
                    event_uri_str,
                    str(predicate),
                    str(value) if value is not None else "None",
                    is_literal=is_literal,
                    graph=graph,
                    entity_type='event',
                    entity_id=event.id,
                    scenario_id=event.scenario_id
                ))
        
        # Commit the session if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def action_to_triples(self, action: Action, commit=True):
        """
        Convert an Action object to RDF triples.
        
        Args:
            action: Action object
            commit: Whether to commit the session after adding triples
            
        Returns:
            List of created EntityTriple objects
        """
        triples = []
        
        # Generate URI for the action
        action_uri = self.generate_uri('action', action.name or "action", action.id, action.scenario_id)
        action_uri_str = str(action_uri)
        
        # Graph identifier (scenario ID)
        graph = f"scenario_{action.scenario_id}"
        
        # Add basic action information
        action_type = PROETHICA.Decision if action.is_decision else PROETHICA.Action
        triples.append(self.add_triple(
            action_uri_str, 
            str(RDF.type), 
            str(action_type), 
            is_literal=False,
            graph=graph,
            entity_type='action',
            entity_id=action.id,
            scenario_id=action.scenario_id
        ))
        
        # Add name and description
        triples.append(self.add_triple(
            action_uri_str,
            str(RDFS.label),
            action.name or "Unnamed Action",
            is_literal=True,
            graph=graph,
            entity_type='action',
            entity_id=action.id,
            scenario_id=action.scenario_id
        ))
        
        if action.description:
            triples.append(self.add_triple(
                action_uri_str,
                str(RDFS.comment),
                action.description,
                is_literal=True,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            ))
        
        # Add action time with BFO temporal region data
        if action.action_time:
            time_triple = self.add_triple(
                action_uri_str,
                str(PROETHICA.occursAt),
                action.action_time.isoformat(),
                is_literal=True,
                graph=graph,
                entity_type='action',
                entity_id=action.id,
                scenario_id=action.scenario_id
            )
            
            # Add BFO temporal region type - decisions are typically instants,
            # regular actions may have duration but default to instant
            if action.is_decision:
                # Decisions are typically instantaneous points in time
                time_triple.temporal_region_type = "BFO_0000148"  # zero-dimensional temporal region
                time_triple.temporal_start = action.action_time
                time_triple.temporal_end = None  # Instant has no end time
            else:
                # Regular actions default to instants but can be updated later with duration
                time_triple.temporal_region_type = "BFO_0000148"  # zero-dimensional temporal region
                time_triple.temporal_start = action.action_time
                time_triple.temporal_end = None
            
            time_triple.temporal_granularity = "seconds"
            triples.append(time_triple)
        
        # Add character relationship
        if action.character_id:
            character = Character.query.get(action.character_id)
            if character:
                character_uri = self.generate_uri('character', character.name, character.id, character.scenario_id)
                
                character_uri_str = str(character_uri)
                
                triples.append(self.add_triple(
                    character_uri_str,
                    str(PROETHICA.performs),
                    str(action_uri),
                    is_literal=False,
                    graph=graph,
                    entity_type='character',
                    entity_id=character.id,
                    scenario_id=character.scenario_id,
                    character_id=character.id
                ))
                
                triples.append(self.add_triple(
                    action_uri_str,
                    str(PROETHICA.performedBy),
                    str(character_uri),
                    is_literal=False,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
        
        # Add decision-specific information
        if action.is_decision:
            # Add selected option
            if action.selected_option:
                triples.append(self.add_triple(
                    action_uri_str,
                    str(PROETHICA.hasSelectedOption),
                    action.selected_option,
                    is_literal=True,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
            
            # Add ethical principles (from options if present)
            if action.options and isinstance(action.options, dict):
                for option_id, option_data in action.options.items():
                    if 'ethical_principles' in option_data and isinstance(option_data['ethical_principles'], list):
                        for principle in option_data['ethical_principles']:
                            # If this is the selected option, it invokes these principles
                            if option_id == action.selected_option:
                                triples.append(self.add_triple(
                                    action_uri_str,
                                    str(PROETHICA.invokes),
                                    str(PROETHICA[principle]),
                                    is_literal=False,
                                    graph=graph,
                                    entity_type='action',
                                    entity_id=action.id,
                                    scenario_id=action.scenario_id
                                ))
        
        # Add parameters as triples
        if action.parameters:
            for key, value in action.parameters.items():
                # Create predicate URI based on parameter name
                predicate = PROETHICA[f"hasParameter_{key}"]
                
                # Determine if value is a literal or URI
                is_literal = isinstance(value, (str, int, float, bool)) or value is None
                
                triples.append(self.add_triple(
                    action_uri_str,
                    str(predicate),
                    str(value) if value is not None else "None",
                    is_literal=is_literal,
                    graph=graph,
                    entity_type='action',
                    entity_id=action.id,
                    scenario_id=action.scenario_id
                ))
        
        # Commit the session if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def sync_entity(self, entity_type, entity, commit=True):
        """
        Synchronize an entity object with the triple store.
        If the entity exists in the triple store, update it.
        If not, create new triples for it.
        
        Args:
            entity_type: Type of the entity ('character', 'event', 'action', 'resource')
            entity: Entity object to synchronize
            commit: Whether to commit the session after operation
            
        Returns:
            List of EntityTriple objects created or updated
        """
        # Delete any existing triples for this entity
        if entity.id:
            self.delete_triples(entity_type=entity_type, entity_id=entity.id)
        
        # Create new triples based on entity type
        if entity_type == 'character':
            triples = self.character_to_triples(entity, commit=False)
        elif entity_type == 'event':
            triples = self.event_to_triples(entity, commit=False)
        elif entity_type == 'action':
            triples = self.action_to_triples(entity, commit=False)
        else:
            raise ValueError(f"Unsupported entity type: {entity_type}")
        
        # Commit if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def sparql_like_query(self, query_template, bindings=None):
        """
        Execute a SPARQL-like query against the triple store.
        This is a simplified implementation that handles basic patterns.
        
        Args:
            query_template: Query template with placeholders
            bindings: Dictionary of bindings for placeholders
            
        Returns:
            Query results as dictionaries
        """
        # Simple implementation for demonstration purposes
        # A full implementation would parse SPARQL syntax and translate to SQL
        
        # For now, just support basic triple pattern matching
        if not bindings:
            bindings = {}
        
        # Parse the query template (very simple implementation)
        parts = query_template.strip().split()
        if len(parts) < 3:
            raise ValueError("Invalid query format")
        
        subject_pattern = parts[0]
        predicate_pattern = parts[1]
        object_pattern = ' '.join(parts[2:])
        
        # Replace bindings
        for key, value in bindings.items():
            key_pattern = f"?{key}"
            subject_pattern = subject_pattern.replace(key_pattern, value)
            predicate_pattern = predicate_pattern.replace(key_pattern, value)
            object_pattern = object_pattern.replace(key_pattern, value)
        
        # Build query parameters
        params = {}
        if not subject_pattern.startswith('?'):
            params['subject'] = subject_pattern
        
        if not predicate_pattern.startswith('?'):
            params['predicate'] = predicate_pattern
        
        if not object_pattern.startswith('?'):
            params['obj'] = object_pattern
            params['is_literal'] = not (object_pattern.startswith('<') and object_pattern.endswith('>'))
        
        # Execute query
        triples = self.find_triples(**params)
        
        # Format results
        results = []
        for triple in triples:
            result = {
                'subject': triple.subject,
                'predicate': triple.predicate,
                'object': triple.object_literal if triple.is_literal else triple.object_uri,
                'entity_type': triple.entity_type,
                'entity_id': triple.entity_id
            }
            results.append(result)
        
        return results
    
    def find_similar_subjects(self, embedding, entity_type=None, limit=10):
        """
        Find subjects with similar embeddings.
        
        Args:
            embedding: Vector embedding to compare against
            entity_type: Optional entity type to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of (subject, similarity) tuples
        """
        # Check if embedding is a numpy array and convert to list
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        
        # Convert the embedding to a string representation for SQL
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        # Build the SQL query
        query = f"""
        SELECT 
            subject,
            entity_type,
            entity_id,
            subject_embedding <-> '{embedding_str}'::vector AS distance
        FROM 
            entity_triples
        WHERE 
            subject_embedding IS NOT NULL
        """
        
        if entity_type:
            query += f" AND entity_type = '{entity_type}'"
        
        query += f"""
        ORDER BY 
            distance
        LIMIT {limit}
        """
        
        result = db.session.execute(text(query))
        
        # Format results
        return [(row.subject, row.entity_type, row.entity_id, 1.0 - row.distance) for row in result]
