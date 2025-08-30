"""
STUB: Ontology Summary Module
This is a placeholder module to maintain backward compatibility.
Ontology summary functionality has moved to OntServe.
"""

def build_ontology_summary(world=None):
    """
    Stub function for building ontology summaries.
    
    Args:
        world: World object (optional)
        
    Returns:
        str: Placeholder message about migration
    """
    return """
# ONTOLOGY SUMMARY MOVED TO ONTSERVE

Ontology summary functionality has been moved to OntServe.
For current ontology information, visit http://localhost:5003

To integrate ontology data:
1. Use the MCP client to query OntServe
2. Access entities via the /api/ontologies endpoint
3. Retrieve hierarchical relationships from OntServe web interface
"""

def get_ontology_entities(world=None, entity_type=None):
    """
    Stub function for getting ontology entities.
    
    Args:
        world: World object (optional)
        entity_type: Type of entity to filter by (optional)
        
    Returns:
        list: Empty list (entities now come from OntServe)
    """
    return []

def format_entity_summary(entity):
    """
    Stub function for formatting entity summaries.
    
    Args:
        entity: Entity object
        
    Returns:
        str: Placeholder message
    """
    return "Entity formatting moved to OntServe"