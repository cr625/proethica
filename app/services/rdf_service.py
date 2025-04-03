import uuid
import numpy as np
from datetime import datetime
from rdflib import Graph, Namespace, Literal, URIRef, RDF, RDFS
from app import db
from app.models.triple import Triple
from app.models.character import Character
from app.models.role import Role
from sqlalchemy import text, func
from typing import List, Dict, Tuple, Optional, Union, Any

# Define namespaces for our RDF graph
PROETHICA = Namespace("http://proethica.org/ontology/")
ENG_ETHICS = Namespace("http://proethica.org/ontology/engineering-ethics#")
PROETHICA_CHARACTER = Namespace("http://proethica.org/character/")
PROETHICA_RESOURCE = Namespace("http://proethica.org/resource/")
PROETHICA_SCENARIO = Namespace("http://proethica.org/scenario/")

class RDFService:
    """
    Service for handling RDF triple operations.
    This service provides methods for converting between application models
    and RDF triples, and for querying the triple store.
    """
    
    def __init__(self):
        # Common RDF namespaces
        self.namespaces = {
            'rdf': RDF,
            'rdfs': RDFS,
            'proethica': PROETHICA,
            'eng': ENG_ETHICS,
            'character': PROETHICA_CHARACTER,
            'resource': PROETHICA_RESOURCE,
            'scenario': PROETHICA_SCENARIO
        }
    
    def get_namespaces(self):
        """Return the namespaces dictionary."""
        return self.namespaces
    
    def register_namespace(self, prefix, uri):
        """Register a new namespace."""
        self.namespaces[prefix] = Namespace(uri)
        return self.namespaces[prefix]
    
    def generate_character_uri(self, character_name, scenario_id=None):
        """Generate a unique URI for a character."""
        # Sanitize name for URI
        name_part = character_name.lower().replace(' ', '_')
        
        # Add scenario ID if provided
        if scenario_id:
            name_part = f"{scenario_id}_{name_part}"
        
        # Add a unique identifier to ensure uniqueness
        unique_id = str(uuid.uuid4())[:8]
        return PROETHICA_CHARACTER[f"{name_part}_{unique_id}"]
    
    def add_triple(self, subject: str, predicate: str, obj: Any, 
                   is_literal: bool = True, graph: Optional[str] = None,
                   character_id: Optional[int] = None, 
                   scenario_id: Optional[int] = None,
                   subject_embedding: Optional[List[float]] = None,
                   predicate_embedding: Optional[List[float]] = None,
                   object_embedding: Optional[List[float]] = None) -> Triple:
        """
        Add a new triple to the store.
        
        Args:
            subject: Subject URI string
            predicate: Predicate URI string
            obj: Object value (string URI or literal value)
            is_literal: True if object is a literal, False if it's a URI
            graph: Optional named graph identifier
            character_id: Optional character ID reference
            scenario_id: Optional scenario ID reference
            subject_embedding: Optional vector embedding for subject
            predicate_embedding: Optional vector embedding for predicate
            object_embedding: Optional vector embedding for object
            
        Returns:
            The created Triple object
        """
        triple = Triple(
            subject=subject,
            predicate=predicate,
            object_literal=obj if is_literal else None,
            object_uri=obj if not is_literal else None,
            is_literal=is_literal,
            graph=graph,
            character_id=character_id,
            scenario_id=scenario_id,
            subject_embedding=subject_embedding,
            predicate_embedding=predicate_embedding,
            object_embedding=object_embedding,
            metadata={}
        )
        
        db.session.add(triple)
        db.session.flush()  # Get the ID without committing
        return triple
    
    def find_triples(self, subject=None, predicate=None, obj=None, 
                     is_literal=None, graph=None, character_id=None, 
                     scenario_id=None, limit=None):
        """
        Find triples matching the given criteria.
        Any parameter can be None to indicate no filter for that field.
        
        Returns:
            List of Triple objects matching the criteria
        """
        query = db.session.query(Triple)
        
        if subject is not None:
            query = query.filter(Triple.subject == subject)
        
        if predicate is not None:
            query = query.filter(Triple.predicate == predicate)
        
        if obj is not None:
            if is_literal is True:
                query = query.filter(Triple.object_literal == obj)
            elif is_literal is False:
                query = query.filter(Triple.object_uri == obj)
            else:
                # If is_literal not specified, check both fields
                query = query.filter((Triple.object_literal == obj) | 
                                    (Triple.object_uri == obj))
        
        if is_literal is not None and obj is None:
            query = query.filter(Triple.is_literal == is_literal)
        
        if graph is not None:
            query = query.filter(Triple.graph == graph)
        
        if character_id is not None:
            query = query.filter(Triple.character_id == character_id)
        
        if scenario_id is not None:
            query = query.filter(Triple.scenario_id == scenario_id)
        
        if limit is not None:
            query = query.limit(limit)
        
        return query.all()
    
    def delete_triples(self, subject=None, predicate=None, obj=None, 
                       is_literal=None, graph=None, character_id=None, 
                       scenario_id=None):
        """
        Delete triples matching the given criteria.
        Any parameter can be None to indicate no filter for that field.
        
        Returns:
            Number of triples deleted
        """
        query = db.session.query(Triple)
        
        if subject is not None:
            query = query.filter(Triple.subject == subject)
        
        if predicate is not None:
            query = query.filter(Triple.predicate == predicate)
        
        if obj is not None:
            if is_literal is True:
                query = query.filter(Triple.object_literal == obj)
            elif is_literal is False:
                query = query.filter(Triple.object_uri == obj)
            else:
                # If is_literal not specified, check both fields
                query = query.filter((Triple.object_literal == obj) | 
                                    (Triple.object_uri == obj))
        
        if is_literal is not None and obj is None:
            query = query.filter(Triple.is_literal == is_literal)
        
        if graph is not None:
            query = query.filter(Triple.graph == graph)
        
        if character_id is not None:
            query = query.filter(Triple.character_id == character_id)
        
        if scenario_id is not None:
            query = query.filter(Triple.scenario_id == scenario_id)
        
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
            List of created Triple objects
        """
        triples = []
        
        # Generate URI for the character
        character_uri = self.generate_character_uri(character.name, character.scenario_id)
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
            character_id=character.id,
            scenario_id=character.scenario_id
        ))
        
        # Add name
        triples.append(self.add_triple(
            character_uri_str,
            str(RDFS.label),
            character.name,
            is_literal=True,
            graph=graph,
            character_id=character.id,
            scenario_id=character.scenario_id
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
                    character_id=character.id,
                    scenario_id=character.scenario_id
                ))
            
            # Add role name
            triples.append(self.add_triple(
                character_uri_str,
                str(PROETHICA.hasRole),
                role.name,
                is_literal=True,
                graph=graph,
                character_id=character.id,
                scenario_id=character.scenario_id
            ))
            
            # Add explicit role relationship
            triples.append(self.add_triple(
                character_uri_str,
                str(PROETHICA.hasRoleID),
                str(role.id),
                is_literal=True,
                graph=graph,
                character_id=character.id,
                scenario_id=character.scenario_id
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
                    character_id=character.id,
                    scenario_id=character.scenario_id
                ))
        
        # Commit the session if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def triples_to_character(self, subject_uri: str, scenario_id: Optional[int] = None):
        """
        Convert RDF triples to a Character object.
        
        Args:
            subject_uri: URI of the character subject
            scenario_id: Optional scenario ID to filter triples
            
        Returns:
            Character object constructed from triples, or None if no character found
        """
        # Find all triples for this character
        triples = self.find_triples(subject=subject_uri, scenario_id=scenario_id)
        
        if not triples:
            return None
        
        # Extract character data from triples
        character_data = {
            'attributes': {}
        }
        
        character_id = None
        role_id = None
        
        for triple in triples:
            # Use the character_id from the triple if available
            if triple.character_id and not character_id:
                character_id = triple.character_id
            
            # Extract scenario_id if not provided
            if triple.scenario_id and not scenario_id:
                scenario_id = triple.scenario_id
            
            # Process predicates
            pred = triple.predicate
            obj = triple.object_literal if triple.is_literal else triple.object_uri
            
            # Extract name (rdfs:label)
            if pred == str(RDFS.label):
                character_data['name'] = obj
            
            # Extract role ID
            elif pred == str(PROETHICA.hasRoleID):
                role_id = int(obj)
            
            # Add other attributes
            elif pred != str(RDF.type) and pred != str(PROETHICA.hasRole):
                # Extract attribute name from predicate URI
                attr_name = pred.split('#')[-1] if '#' in pred else pred.split('/')[-1]
                character_data['attributes'][attr_name] = obj
        
        # If we have a character ID, try to fetch the existing character
        if character_id:
            character = Character.query.get(character_id)
            if character:
                # Update character attributes from triples
                if 'name' in character_data:
                    character.name = character_data['name']
                
                if role_id:
                    character.role_id = role_id
                
                if character_data['attributes']:
                    character.attributes.update(character_data['attributes'])
                
                return character
        
        # If no existing character or ID not found, create a new one
        if 'name' not in character_data:
            # Extract name from URI if not found in triples
            uri_parts = subject_uri.split('/')[-1].split('_')
            name = ' '.join(uri_parts[:-1])  # Remove the UUID part
            character_data['name'] = name.replace('_', ' ').title()
        
        # Create new character object
        character = Character(
            scenario_id=scenario_id,
            name=character_data['name'],
            role_id=role_id,
            attributes=character_data['attributes']
        )
        
        return character
    
    def sync_character(self, character: Character, commit=True):
        """
        Synchronize a Character object with the triple store.
        If the character exists in the triple store, update it.
        If not, create new triples for it.
        
        Args:
            character: Character object to synchronize
            commit: Whether to commit the session after operation
            
        Returns:
            List of Triple objects created or updated
        """
        # Delete any existing triples for this character
        if character.id:
            self.delete_triples(character_id=character.id)
        
        # Create new triples for the character
        triples = self.character_to_triples(character, commit=False)
        
        # Commit if requested
        if commit:
            db.session.commit()
        
        return triples
    
    def find_characters_by_triple_pattern(self, predicate=None, obj=None, 
                                         is_literal=True, scenario_id=None):
        """
        Find characters matching a specific triple pattern.
        
        Args:
            predicate: Optional predicate URI to match
            obj: Optional object value to match
            is_literal: Whether the object is a literal value
            scenario_id: Optional scenario ID to filter by
            
        Returns:
            List of Character objects matching the pattern
        """
        # Find triples matching the pattern
        triples = self.find_triples(
            predicate=predicate, 
            obj=obj, 
            is_literal=is_literal,
            scenario_id=scenario_id
        )
        
        # Extract unique character IDs
        character_ids = set()
        for triple in triples:
            if triple.character_id:
                character_ids.add(triple.character_id)
        
        # Fetch characters by IDs
        if character_ids:
            return Character.query.filter(Character.id.in_(character_ids)).all()
        
        return []
    
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
                'object': triple.object_literal if triple.is_literal else triple.object_uri
            }
            results.append(result)
        
        return results
    
    def find_similar_subjects(self, embedding, limit=10):
        """
        Find subjects with similar embeddings.
        
        Args:
            embedding: Vector embedding to compare against
            limit: Maximum number of results to return
            
        Returns:
            List of (subject, similarity) tuples
        """
        # Check if embedding is a numpy array and convert to list
        if isinstance(embedding, np.ndarray):
            embedding = embedding.tolist()
        
        # Convert the embedding to a string representation for SQL
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        
        # Query for similar subjects
        query = f"""
        SELECT 
            subject,
            subject_embedding <-> '{embedding_str}'::vector AS distance
        FROM 
            character_triples
        WHERE 
            subject_embedding IS NOT NULL
        ORDER BY 
            distance
        LIMIT {limit}
        """
        
        result = db.session.execute(text(query))
        
        # Format results
        return [(row.subject, 1.0 - row.distance) for row in result]
