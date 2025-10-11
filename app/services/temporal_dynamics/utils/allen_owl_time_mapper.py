"""
Allen Relation to OWL-Time Property Mapper

Maps ProEthica Allen temporal relations to standard OWL-Time interval algebra properties.
This enables interoperability with standard temporal reasoning systems and SPARQL queries.
"""

from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


# Allen's Interval Algebra - Complete mapping to OWL-Time properties
ALLEN_TO_OWL_TIME = {
    # Basic relations
    'precedes': 'time:before',
    'before': 'time:before',

    'meets': 'time:intervalMeets',

    'overlaps': 'time:intervalOverlaps',

    'during': 'time:intervalDuring',
    'contains': 'time:intervalContains',  # Inverse of during

    'starts': 'time:intervalStarts',
    'started_by': 'time:intervalStartedBy',  # Inverse of starts

    'finishes': 'time:intervalFinishes',
    'finished_by': 'time:intervalFinishedBy',  # Inverse of finishes

    'equals': 'time:intervalEquals',

    # Inverse relations
    'preceded_by': 'time:after',
    'after': 'time:after',

    'met_by': 'time:intervalMetBy',

    'overlapped_by': 'time:intervalOverlappedBy',

    # Additional common temporal relations
    'concurrent': 'time:intervalEquals',  # Concurrent treated as equals
    'simultaneous': 'time:intervalEquals',
}


# OWL-Time property URIs (full URIs for RDF)
OWL_TIME_URIS = {
    'time:before': 'http://www.w3.org/2006/time#before',
    'time:after': 'http://www.w3.org/2006/time#after',
    'time:intervalMeets': 'http://www.w3.org/2006/time#intervalMeets',
    'time:intervalMetBy': 'http://www.w3.org/2006/time#intervalMetBy',
    'time:intervalOverlaps': 'http://www.w3.org/2006/time#intervalOverlaps',
    'time:intervalOverlappedBy': 'http://www.w3.org/2006/time#intervalOverlappedBy',
    'time:intervalDuring': 'http://www.w3.org/2006/time#intervalDuring',
    'time:intervalContains': 'http://www.w3.org/2006/time#intervalContains',
    'time:intervalStarts': 'http://www.w3.org/2006/time#intervalStarts',
    'time:intervalStartedBy': 'http://www.w3.org/2006/time#intervalStartedBy',
    'time:intervalFinishes': 'http://www.w3.org/2006/time#intervalFinishes',
    'time:intervalFinishedBy': 'http://www.w3.org/2006/time#intervalFinishedBy',
    'time:intervalEquals': 'http://www.w3.org/2006/time#intervalEquals',
}


# Human-readable descriptions for each Allen relation
ALLEN_DESCRIPTIONS = {
    'precedes': 'Entity1 ends before Entity2 begins',
    'before': 'Entity1 is before Entity2',
    'meets': 'Entity1 ends exactly when Entity2 begins',
    'overlaps': 'Entity1 starts before Entity2 and ends during Entity2',
    'during': 'Entity1 occurs entirely within the duration of Entity2',
    'contains': 'Entity1 encompasses the entire duration of Entity2',
    'starts': 'Entity1 and Entity2 start at the same time, Entity1 ends first',
    'finishes': 'Entity1 and Entity2 end at the same time, Entity2 starts first',
    'equals': 'Entity1 and Entity2 have the same start and end times',
    'after': 'Entity1 is after Entity2',
    'met_by': 'Entity1 begins exactly when Entity2 ends',
    'overlapped_by': 'Entity1 starts during Entity2 and ends after Entity2',
    'concurrent': 'Entity1 and Entity2 occur at the same time',
    'simultaneous': 'Entity1 and Entity2 are simultaneous',
}


def map_allen_to_owl_time(allen_relation: str) -> Optional[str]:
    """
    Map an Allen relation to its OWL-Time property.

    Args:
        allen_relation: Allen relation name (e.g., 'precedes', 'overlaps')

    Returns:
        OWL-Time property name (e.g., 'time:before') or None if not found
    """
    # Normalize input (lowercase, strip whitespace)
    normalized = allen_relation.lower().strip()

    owl_time_prop = ALLEN_TO_OWL_TIME.get(normalized)

    if not owl_time_prop:
        logger.warning(f"No OWL-Time mapping found for Allen relation: {allen_relation}")

    return owl_time_prop


def get_owl_time_uri(owl_time_property: str) -> Optional[str]:
    """
    Get the full URI for an OWL-Time property.

    Args:
        owl_time_property: OWL-Time property name (e.g., 'time:before')

    Returns:
        Full URI (e.g., 'http://www.w3.org/2006/time#before') or None if not found
    """
    uri = OWL_TIME_URIS.get(owl_time_property)

    if not uri:
        logger.warning(f"No URI found for OWL-Time property: {owl_time_property}")

    return uri


def get_allen_description(allen_relation: str) -> str:
    """
    Get human-readable description of an Allen relation.

    Args:
        allen_relation: Allen relation name

    Returns:
        Description string
    """
    normalized = allen_relation.lower().strip()
    return ALLEN_DESCRIPTIONS.get(normalized, f"Temporal relation: {allen_relation}")


def create_allen_relation_metadata(allen_relation: str) -> Dict:
    """
    Create complete metadata for an Allen relation including both custom and OWL-Time properties.

    Args:
        allen_relation: Allen relation name

    Returns:
        Dictionary with ProEthica custom property and OWL-Time property
    """
    owl_time_prop = map_allen_to_owl_time(allen_relation)
    owl_time_uri = get_owl_time_uri(owl_time_prop) if owl_time_prop else None

    return {
        'proeth_relation': allen_relation,  # Custom ProEthica property
        'owl_time_property': owl_time_prop,  # OWL-Time prefixed property
        'owl_time_uri': owl_time_uri,  # Full OWL-Time URI
        'description': get_allen_description(allen_relation)
    }


def get_inverse_relation(allen_relation: str) -> Optional[str]:
    """
    Get the inverse of an Allen relation.

    Args:
        allen_relation: Allen relation name

    Returns:
        Inverse relation name or None
    """
    inverses = {
        'precedes': 'preceded_by',
        'before': 'after',
        'meets': 'met_by',
        'overlaps': 'overlapped_by',
        'during': 'contains',
        'contains': 'during',
        'starts': 'started_by',
        'finishes': 'finished_by',
        'equals': 'equals',  # Symmetric
        # Inverse mappings
        'preceded_by': 'precedes',
        'after': 'before',
        'met_by': 'meets',
        'overlapped_by': 'overlaps',
        'started_by': 'starts',
        'finished_by': 'finishes',
    }

    normalized = allen_relation.lower().strip()
    return inverses.get(normalized)


# Allen's 13 basic relations for reference
ALLEN_13_BASIC_RELATIONS = [
    'precedes',     # X before Y
    'meets',        # X meets Y
    'overlaps',     # X overlaps Y
    'finished_by',  # X finished by Y
    'contains',     # X contains Y
    'starts',       # X starts Y
    'equals',       # X equals Y
    'started_by',   # X started by Y
    'during',       # X during Y
    'finishes',     # X finishes Y
    'overlapped_by',# X overlapped by Y
    'met_by',       # X met by Y
    'preceded_by',  # X preceded by Y (after)
]


def validate_allen_relation(allen_relation: str) -> bool:
    """
    Validate if a string is a recognized Allen relation.

    Args:
        allen_relation: Relation name to validate

    Returns:
        True if valid, False otherwise
    """
    normalized = allen_relation.lower().strip()
    return normalized in ALLEN_TO_OWL_TIME


def get_all_allen_mappings() -> Dict[str, Dict]:
    """
    Get all Allen relation mappings with complete metadata.

    Returns:
        Dictionary mapping Allen relations to their metadata
    """
    return {
        relation: create_allen_relation_metadata(relation)
        for relation in ALLEN_TO_OWL_TIME.keys()
    }
