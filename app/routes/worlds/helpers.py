import json
import ast
import re
import logging

from app.models.ontology import Ontology

logger = logging.getLogger(__name__)


def _get_dynamic_entity_type_config(world):
    """
    Get dynamic entity type configuration from the proethica-intermediate ontology.

    Args:
        world: World model instance

    Returns:
        List of tuples (entity_key, display_name, description)
    """
    try:
        # Get the proethica-intermediate ontology from database
        proethica_ontology = Ontology.query.filter_by(domain_id='proethica-intermediate').first()
        if not proethica_ontology:
            logger.warning("proethica-intermediate ontology not found, using fallback config")
            return _get_fallback_entity_type_config()

        # Parse the ontology to extract GuidelineConceptTypes
        from rdflib import Graph, Namespace, RDF, RDFS
        proeth_namespace = Namespace("http://proethica.org/ontology/intermediate#")

        g = Graph()
        g.parse(data=proethica_ontology.content, format="turtle")

        # Extract GuidelineConceptTypes with their labels and descriptions
        concept_types = []
        for concept_type in g.subjects(RDF.type, proeth_namespace.GuidelineConceptType):
            label = next(g.objects(concept_type, RDFS.label), None)
            description = next(g.objects(concept_type, RDFS.comment), None)

            if label:
                concept_name = str(label)
                entity_key = concept_name.lower()

                # Handle special mappings for legacy compatibility
                if concept_name == "State":
                    entity_key = "state"  # Use "state" instead of legacy "conditions"

                # Create friendly descriptions
                desc = str(description) if description else _get_default_description(concept_name)

                # Smart pluralization
                display_name = _pluralize(concept_name)

                concept_types.append((entity_key, display_name, desc))

        # Sort by a preferred order if possible
        preferred_order = ["role", "principle", "obligation", "state", "resource", "action", "event", "capability"]
        def sort_key(item):
            try:
                return preferred_order.index(item[0])
            except ValueError:
                return len(preferred_order)  # Put unknown types at the end

        concept_types.sort(key=sort_key)

        logger.info(f"Found {len(concept_types)} GuidelineConceptTypes: {[ct[0] for ct in concept_types]}")
        return concept_types

    except Exception as e:
        logger.error(f"Error extracting dynamic entity types: {e}")
        return _get_fallback_entity_type_config()

def _get_fallback_entity_type_config():
    """
    Fallback entity type configuration if dynamic extraction fails.

    Returns:
        List of tuples (entity_key, display_name, description)
    """
    return [
        ('role', 'Roles', 'Users and their responsibilities'),
        ('principle', 'Principles', 'Fundamental ethical values that guide professional conduct'),
        ('obligation', 'Obligations', 'Professional duties that must be fulfilled'),
        ('state', 'States', 'Conditions that provide context for ethical decision-making'),
        ('resource', 'Resources', 'Physical or informational entities used in ethical scenarios'),
        ('action', 'Actions', 'Intentional activities performed by agents'),
        ('event', 'Events', 'Occurrences or happenings in ethical scenarios'),
        ('capability', 'Capabilities', 'Skills and abilities that can be realized')
    ]

def _pluralize(word):
    """
    Smart pluralization for entity type names.

    Args:
        word: Singular word to pluralize

    Returns:
        Pluralized word
    """
    # Handle special cases
    pluralization_rules = {
        "Capability": "Capabilities",
        "Activity": "Activities",
        "Entity": "Entities"
    }

    if word in pluralization_rules:
        return pluralization_rules[word]

    # General rules
    if word.endswith('y') and len(word) > 1 and word[-2] not in 'aeiou':
        return word[:-1] + 'ies'
    elif word.endswith(('s', 'sh', 'ch', 'x', 'z')):
        return word + 'es'
    else:
        return word + 's'

def _get_default_description(concept_name):
    """
    Get default description for a GuidelineConceptType.

    Args:
        concept_name: Name of the concept type

    Returns:
        Default description string
    """
    descriptions = {
        "Role": "Professional positions with associated responsibilities",
        "Principle": "Fundamental ethical values that guide conduct",
        "Obligation": "Professional duties that must be fulfilled",
        "State": "Conditions that provide context for decision-making",
        "Resource": "Physical or informational entities used in scenarios",
        "Action": "Intentional activities performed by agents",
        "Event": "Occurrences or happenings in scenarios",
        "Capability": "Skills and abilities that can be realized"
    }
    return descriptions.get(concept_name, f"{concept_name} entities")

# Utility function for robust JSON parsing
def robust_json_parse(json_str):
    """Parse JSON with fallback methods for common syntax issues."""
    try:
        # Try standard JSON parsing first
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.info(f"Standard JSON parsing failed, attempting recovery: {str(e)}")

        # Debugging: log the problematic JSON string (truncated if large)
        max_log_len = 200  # Only log first 200 chars for debugging
        log_str = json_str[:max_log_len] + "..." if len(json_str) > max_log_len else json_str
        logger.info(f"Problematic JSON string (truncated): {log_str}")

        # If JSON has single quotes instead of double quotes, try to fix it
        try:
            if "'" in json_str:
                # Replace single quotes with double quotes, but be careful with nested quotes
                logger.info("Attempting to fix single quotes in JSON")
                # This approach handles single quotes better by first going through ast.literal_eval
                try:
                    python_obj = ast.literal_eval(json_str)
                    return python_obj
                except Exception:
                    # Fallback to simple replacement if ast.literal_eval fails
                    fixed_json = json_str.replace("'", '"')
                    return json.loads(fixed_json)
        except Exception as e:
            logger.info(f"Single quote fix failed: {str(e)}")
            pass

        # Try using ast.literal_eval for Python-style dictionaries
        try:
            logger.info("Attempting ast.literal_eval")
            return ast.literal_eval(json_str)
        except Exception as e:
            logger.info(f"ast.literal_eval failed: {str(e)}")
            pass

        # Try to fix missing quotes around property names
        try:
            logger.info("Attempting regex fix for property names")
            # Use regex to find and fix common JSON errors
            fixed_json = re.sub(r'(\w+):', r'"\1":', json_str)
            return json.loads(fixed_json)
        except Exception as e:
            logger.info(f"Regex fix failed: {str(e)}")
            pass

        # Try handling JavaScript objects with undefined values
        try:
            logger.info("Attempting to fix undefined values")
            fixed_json = json_str.replace('undefined', 'null')
            return json.loads(fixed_json)
        except Exception:
            pass

        # If all else fails, raise the original error
        logger.error(f"All JSON parsing recovery methods failed for: {log_str}")
        raise
