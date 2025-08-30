"""
STUB: Ontology Mapper Module
This is a placeholder module to maintain backward compatibility.
Ontology mapping functionality has moved to OntServe.
"""

def map_events(events, world=None):
    """
    Stub function for mapping events to ontology concepts.
    
    Args:
        events: List of events to map
        world: World object (optional)
        
    Returns:
        list: Empty list (mapping functionality moved to OntServe)
    """
    return []

def map_entities(entities, entity_type=None):
    """
    Stub function for mapping entities to ontology concepts.
    
    Args:
        entities: List of entities to map
        entity_type: Type of entity (optional)
        
    Returns:
        list: Empty list (mapping functionality moved to OntServe)
    """
    return []

def map_relationships(subject_uri, predicate_uri, object_uri):
    """
    Stub function for mapping relationships.
    
    Args:
        subject_uri: Subject URI
        predicate_uri: Predicate URI
        object_uri: Object URI
        
    Returns:
        dict: Placeholder mapping result
    """
    return {
        'success': False,
        'message': 'Relationship mapping has moved to OntServe',
        'ontserve_url': 'http://localhost:5003'
    }

def get_concept_hierarchy(concept_uri):
    """
    Stub function for getting concept hierarchy.
    
    Args:
        concept_uri: URI of the concept
        
    Returns:
        dict: Empty hierarchy (functionality moved to OntServe)
    """
    return {}