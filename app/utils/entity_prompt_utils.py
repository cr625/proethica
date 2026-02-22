"""Shared utilities for formatting entities in LLM prompts and resolving
entity labels back to IRIs after parsing LLM responses.

Used by question_analyzer.py, conclusion_analyzer.py, and any future
Step 4 service that passes case entities to an LLM.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# Canonical ordering for entity type display in prompts
ENTITY_TYPE_ORDER = [
    ('roles', 'Roles'),
    ('states', 'States'),
    ('resources', 'Resources'),
    ('principles', 'Principles'),
    ('obligations', 'Obligations'),
    ('constraints', 'Constraints'),
    ('capabilities', 'Capabilities'),
    ('actions', 'Actions'),
    ('events', 'Events'),
]


def _get_entity_field(entity, *field_names, default=''):
    """Extract a field from an entity that may be a dict or ORM object."""
    for name in field_names:
        if isinstance(entity, dict):
            val = entity.get(name)
        else:
            val = getattr(entity, name, None)
        if val:
            return val
    return default


def format_entities_compact(all_entities: Dict[str, List]) -> str:
    """Format all entity types as label + definition for LLM prompts.

    No URIs are included -- the LLM works with labels only.
    URIs are resolved mechanically after parsing via resolve_entity_labels_to_uris().

    Args:
        all_entities: Dict mapping entity type keys to lists of entity objects
                      (TemporaryRDFStorage ORM objects or dicts with label/definition).

    Returns:
        Formatted string for inclusion in LLM prompts.
    """
    formatted = ""
    for key, display_name in ENTITY_TYPE_ORDER:
        entities = all_entities.get(key, [])
        if entities:
            formatted += f"\n**{display_name}:**\n"
            for entity in entities:
                label = _get_entity_field(entity, 'label', 'entity_label', default='Unknown')
                definition = _get_entity_field(entity, 'definition', 'entity_definition')
                formatted += f"  - {label}"
                if definition and len(definition) < 150:
                    formatted += f": {definition}"
                formatted += "\n"
        else:
            formatted += f"\n**{display_name}:** (none extracted)\n"

    return formatted


def _normalize_label(label: str) -> str:
    """Normalize an entity label for fuzzy matching.

    Handles case differences, underscores vs spaces, and extra whitespace.
    """
    return re.sub(r'[\s_]+', ' ', label.strip().lower())


def _build_label_index(all_entities: Dict[str, List]) -> Dict[str, Dict[str, str]]:
    """Build a normalized-label -> URI index grouped by entity type.

    Returns:
        Dict mapping entity type key -> {normalized_label: uri}
    """
    index = {}
    for key, _ in ENTITY_TYPE_ORDER:
        type_index = {}
        for entity in all_entities.get(key, []):
            label = _get_entity_field(entity, 'label', 'entity_label')
            uri = _get_entity_field(entity, 'uri', 'entity_uri')
            if label:
                type_index[_normalize_label(label)] = uri or ''
        index[key] = type_index
    return index


def resolve_entity_labels_to_uris(
    mentioned_entities: Dict[str, List[str]],
    all_entities: Dict[str, List]
) -> Dict[str, List[str]]:
    """Resolve entity labels from LLM output to full IRIs.

    Builds a label->URI index from all_entities, then looks up each label
    in mentioned_entities. Case-insensitive with underscore/space normalization.

    Args:
        mentioned_entities: Dict from LLM output, e.g.
            {"roles": ["Engineer A"], "principles": ["Public Safety"]}
        all_entities: The same entity dict passed to the LLM prompt
            (from get_all_case_entities()).

    Returns:
        Dict with same structure as mentioned_entities but URIs instead of labels.
        Unresolved labels map to empty string.
    """
    if not mentioned_entities:
        return {}

    label_index = _build_label_index(all_entities)
    resolved = {}

    for entity_type, labels in mentioned_entities.items():
        if not isinstance(labels, list):
            continue
        type_index = label_index.get(entity_type, {})
        uris = []
        for label in labels:
            if not isinstance(label, str):
                uris.append('')
                continue
            normalized = _normalize_label(label)
            uri = type_index.get(normalized, '')
            if not uri:
                # Try cross-type lookup as fallback
                for other_key, other_index in label_index.items():
                    if normalized in other_index:
                        uri = other_index[normalized]
                        break
            uris.append(uri)
        resolved[entity_type] = uris

    return resolved


def resolve_labels_flat(
    labels: List[str],
    all_entities: Dict[str, List]
) -> List[str]:
    """Resolve a flat list of entity labels to URIs, searching across all types.

    Unlike resolve_entity_labels_to_uris which expects {type: [labels]}, this
    takes an untyped list and searches all entity categories. Used by rich
    analysis methods where output fields reference entities without type grouping
    (e.g., fulfills_obligations, data_events, involves_roles).

    Args:
        labels: List of entity labels from LLM output.
        all_entities: Dict mapping entity type keys to entity lists.

    Returns:
        List of URIs in same order as labels. Unresolved labels get empty string.
    """
    if not labels:
        return []

    label_index = _build_label_index(all_entities)
    # Flatten all type indices into one cross-type lookup
    flat_index: Dict[str, str] = {}
    for type_idx in label_index.values():
        flat_index.update(type_idx)

    return [
        flat_index.get(_normalize_label(label), '') if isinstance(label, str) else ''
        for label in labels
    ]
