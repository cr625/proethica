from flask import request, redirect, url_for, flash
import json
import ast
import re
import logging

from app.models.world import World
from app.models.ontology import Ontology

logger = logging.getLogger(__name__)


def register_helper_routes(bp):
    @bp.route('/<int:world_id>/guidelines/<int:document_id>/generate_triples', methods=['POST'])
    def generate_triples_direct(world_id, document_id):
        """Generate triples directly from the guideline view page."""
        from app.routes.worlds.generate_triples import generate_triples_direct as generate_triples_impl
        return generate_triples_impl(world_id, document_id)


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

def _generate_preview_triples(selected_concepts, document_id, world):
    """Generate preview triples for selected concepts without saving to database."""
    triples = []

    for i, concept in enumerate(selected_concepts):
        # Create basic concept definition triple
        concept_uri = f"http://proethica.org/ontology/guideline-{document_id}#{concept.get('label', '').replace(' ', '')}"

        # Add type triple
        concept_type = concept.get('type', 'concept').lower()
        type_uri = f"http://proethica.org/ontology/intermediate#{concept_type.capitalize()}"

        triples.append({
            'id': f"triple_{i*3}",
            'subject': concept_uri,
            'subject_label': concept.get('label', ''),
            'predicate': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type',
            'predicate_label': 'type',
            'object': type_uri,
            'object_label': concept_type.capitalize(),
            'category': 'new_concept',
            'selected': True
        })

        # Add label triple
        triples.append({
            'id': f"triple_{i*3+1}",
            'subject': concept_uri,
            'subject_label': concept.get('label', ''),
            'predicate': 'http://www.w3.org/2000/01/rdf-schema#label',
            'predicate_label': 'label',
            'object': concept.get('label', ''),
            'object_label': concept.get('label', ''),
            'category': 'new_concept',
            'selected': True
        })

        # Add description triple if available
        if concept.get('description'):
            triples.append({
                'id': f"triple_{i*3+2}",
                'subject': concept_uri,
                'subject_label': concept.get('label', ''),
                'predicate': 'http://www.w3.org/2000/01/rdf-schema#comment',
                'predicate_label': 'description',
                'object': concept.get('description', ''),
                'object_label': concept.get('description', '')[:100] + '...' if len(concept.get('description', '')) > 100 else concept.get('description', ''),
                'category': 'new_concept',
                'selected': True
            })

    return triples

def _calculate_triple_stats(triples):
    """Calculate statistics for the triples."""
    stats = {
        'total_triples': len(triples),
        'new_concepts_count': len([t for t in triples if t.get('category') == 'new_concept']),
        'additional_relationships_count': len([t for t in triples if t.get('category') == 'relationship']),
        'predicate_suggestions_count': len([t for t in triples if t.get('category') == 'predicate_suggestion']),
        'core_ontology_count': len([t for t in triples if t.get('category') == 'existing']),
        'other_guidelines_count': 0,
        'selected': len([t for t in triples if t.get('selected', False)])
    }
    return stats

def _extract_predicate_triples(selected_concepts, document_id, world):
    """Extract predicate suggestions from concepts and convert them to reviewable triples."""
    predicate_triples = []
    triple_id_counter = 10000  # Start with high number to avoid conflicts

    for concept in selected_concepts:
        concept_uri = f"http://proethica.org/ontology/guideline-{document_id}#{concept.get('label', '').replace(' ', '')}"
        concept_label = concept.get('label', '')

        # Extract suggested predicates if available
        suggested_predicates = concept.get('suggested_predicates', {})

        # Process "as_subject" predicates (this concept is the subject)
        for pred_suggestion in suggested_predicates.get('as_subject', []):
            predicate_uri = pred_suggestion.get('predicate', '')
            predicate_type = pred_suggestion.get('predicate_type', predicate_uri.split('#')[-1] if '#' in predicate_uri else predicate_uri)
            target_label = pred_suggestion.get('target_label', '')
            confidence = pred_suggestion.get('confidence', 0.0)
            explanation = pred_suggestion.get('explanation', '')

            # Generate target URI (might be from another concept in this extraction)
            target_uri = pred_suggestion.get('target_concept', '')
            if not target_uri:
                target_uri = f"http://proethica.org/ontology/guideline-{document_id}#{target_label.replace(' ', '')}"

            predicate_triples.append({
                'id': f"pred_triple_{triple_id_counter}",
                'subject': concept_uri,
                'subject_label': concept_label,
                'predicate': predicate_uri,
                'predicate_label': predicate_type,
                'object': target_uri,
                'object_label': target_label,
                'category': 'predicate_suggestion',
                'selected': True,  # Default to selected since these are AI suggestions
                'confidence': confidence,
                'explanation': explanation,
                'suggestion_source': 'llm_relationship_discovery'
            })
            triple_id_counter += 1

        # Process "as_object" predicates (this concept is the object)
        # Note: We could include these but they might duplicate the as_subject ones
        # For now, we'll skip them to avoid duplication since each relationship
        # should only appear once in the triple list

    return predicate_triples

def _organize_triples_by_concept(selected_concepts, all_triples, document_id):
    """Organize triples by concept/term for better user experience in triple review."""
    organized = []

    for concept in selected_concepts:
        concept_label = concept.get('label', '')
        concept_uri = f"http://proethica.org/ontology/guideline-{document_id}#{concept_label.replace(' ', '')}"
        concept_type = concept.get('type', 'concept').lower()

        # Find all triples related to this concept
        concept_triples = {
            'basic_definition': [],
            'predicate_suggestions': [],
            'existing_relationships': []
        }

        # Categorize triples by this concept
        for triple in all_triples:
            if (triple.get('subject_label', '') == concept_label or
                triple.get('subject', '') == concept_uri or
                triple.get('object_label', '') == concept_label):

                if triple.get('category') == 'new_concept':
                    concept_triples['basic_definition'].append(triple)
                elif triple.get('category') == 'predicate_suggestion':
                    concept_triples['predicate_suggestions'].append(triple)
                elif triple.get('category') in ['relationship', 'existing']:
                    concept_triples['existing_relationships'].append(triple)

        # Check if this concept has any matching ontology entities (existing concepts)
        ontology_match = concept.get('ontology_match')
        is_existing_concept = ontology_match and not concept.get('is_new', True)

        # Get predicate suggestions from concept data (for existing concepts without triples)
        suggested_predicates = concept.get('suggested_predicates', {})

        organized.append({
            'concept': concept,
            'concept_label': concept_label,
            'concept_type': concept_type,
            'is_existing_concept': is_existing_concept,
            'ontology_match': ontology_match,
            'triples': concept_triples,
            'suggested_predicates': suggested_predicates,
            'has_suggestions': bool(suggested_predicates.get('as_subject', []) or suggested_predicates.get('as_object', [])),
            'triple_count': len(concept_triples['basic_definition']) + len(concept_triples['predicate_suggestions']) + len(concept_triples['existing_relationships'])
        })

    return organized
