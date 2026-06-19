from rdflib import Namespace, RDF, RDFS
from app import db
from app.models.entity_triple import EntityTriple
from sqlalchemy import text
from typing import List, Dict, Optional, Any

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

    def add_triple(self, subject: str, predicate: str, obj: Any,
                   is_literal: bool = True, graph: Optional[str] = None,
                   entity_type: str = None, entity_id: Optional[int] = None,
                   scenario_id: Optional[int] = None,
                   character_id: Optional[int] = None,
                   subject_embedding: Optional[List[float]] = None,
                   predicate_embedding: Optional[List[float]] = None,
                   object_embedding: Optional[List[float]] = None,
                   triple_metadata: Optional[Dict] = None) -> EntityTriple:
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
            triple_metadata: Optional metadata dictionary (can include provenance data)

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
            triple_metadata=triple_metadata or {}
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
    
    def delete_triples_for_entity(self, entity_type, entity_id):
        """
        Delete all triples for a specific entity.
        
        Args:
            entity_type: The type of entity ('character', 'event', 'action', 'resource', 'document')
            entity_id: The ID of the entity
            
        Returns:
            Number of triples deleted
        """
        return self.delete_triples(entity_type=entity_type, entity_id=entity_id)
    
    def find_related_cases_by_triples(self, document_id):
        """
        Find cases that share similar triples with the given document.
        
        Args:
            document_id: The ID of the document to find related cases for
            
        Returns:
            Dictionary mapping predicates to lists of related cases and their shared triples
        """
        # Get all triples for the source document
        source_triples = self.find_triples(entity_type='document', entity_id=document_id)
        
        # If no triples found, return empty result
        if not source_triples:
            return {}
        
        # Group source triples by predicate
        predicates_to_triples = {}
        for triple in source_triples:
            if triple.predicate not in predicates_to_triples:
                predicates_to_triples[triple.predicate] = []
            predicates_to_triples[triple.predicate].append(triple)
        
        # Initialize result structure
        result = {}
        
        # For each predicate, find related cases
        for predicate, triples in predicates_to_triples.items():
            related_cases = {}
            
            for triple in triples:
                # Find documents that have triples with the same predicate and object
                object_value = triple.object_literal if triple.is_literal else triple.object_uri
                
                # Find matching triples in other documents
                matching_triples = self.find_triples(
                    predicate=predicate,
                    obj=object_value,
                    is_literal=triple.is_literal,
                    entity_type='document'
                )
                
                # Group by document ID
                for mt in matching_triples:
                    # Skip if it's the same document
                    if mt.entity_id == document_id:
                        continue
                    
                    # Add to related cases
                    if mt.entity_id not in related_cases:
                        related_cases[mt.entity_id] = {
                            'entity_id': mt.entity_id,
                            'shared_triples': []
                        }
                    
                    related_cases[mt.entity_id]['shared_triples'].append({
                        'source_triple': triple.to_dict(),
                        'related_triple': mt.to_dict()
                    })
            
            # If there are related cases for this predicate, add to result
            if related_cases:
                result[predicate] = {
                    'source_triples': [t.to_dict() for t in triples],
                    'related_cases': list(related_cases.values())
                }
        
        return result
    
    def find_cases_matching_all_triples(self, source_document_id, triple_selectors):
        """
        Find cases that match ALL of the given triple selectors.
        
        Args:
            source_document_id: The ID of the document to exclude from results
            triple_selectors: List of {predicate, object, is_literal} dictionaries
            
        Returns:
            List of matching case information
        """
        if not triple_selectors:
            return []
        
        # For each selector, find matching cases
        matching_case_sets = []
        
        for selector in triple_selectors:
            # Find documents with matching triple
            matching_triples = self.find_triples(
                predicate=selector['predicate'],
                obj=selector['object'],
                is_literal=selector.get('is_literal', True),
                entity_type='document'
            )
            
            # Extract unique document IDs (excluding source document)
            matching_cases = set(
                t.entity_id for t in matching_triples 
                if t.entity_id != int(source_document_id)
            )
            
            matching_case_sets.append(matching_cases)
        
        # Find intersection of all matching case sets (cases that match ALL selectors)
        if matching_case_sets:
            intersection = set.intersection(*matching_case_sets)
        else:
            intersection = set()
        
        # Get case details for the matching cases
        result = []
        for case_id in intersection:
            from app.models import Document
            doc = Document.query.get(case_id)
            if doc:
                # Extract metadata
                metadata = {}
                if doc.doc_metadata and isinstance(doc.doc_metadata, dict):
                    metadata = doc.doc_metadata
                
                result.append({
                    'id': doc.id,
                    'title': doc.title,
                    'description': doc.content[:150] + '...' if doc.content and len(doc.content) > 150 else (doc.content or ''),
                    'case_number': metadata.get('case_number', ''),
                    'year': metadata.get('year', '')
                })
        
        return result
