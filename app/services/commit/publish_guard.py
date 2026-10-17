"""
Publish guard: an individual whose type class is unpublished cannot publish
(case-8 review, lesson L5).

The verification gate dropped the class row ProactiveRiskDisclosureObligation
as over-reach, yet the individual typed to it was committed and the case TTL
redeclared the rejected class (the writer declares a type class locally when
the shared ontology does not establish it). The guard partitions a commit
batch: an individual typed to a class row of the same case that is unpublished
and outside the batch, and that no shared ontology tier establishes, is
refused and stays unpublished for review. The functions are pure so the
commit paths and the tests share one rule.
"""

import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from app.services.commit import naming

_ROLE_TYPES = ('roles',)


def normalize_class_key(label_or_local: Any) -> str:
    """Collapse a class label or local name to the form the committed IRI
    collapses it to (alphanumeric, lowercased): 'Proactive Risk Disclosure
    Obligation' and 'ProactiveRiskDisclosureObligation' are one class."""
    return re.sub(r'[^a-z0-9]', '', str(label_or_local or '').lower())


def individual_type_locals(rdf_data: Optional[Dict[str, Any]]) -> List[str]:
    """Local names of the classes an individual row types to (``types``)."""
    types = (rdf_data or {}).get('types') if isinstance(rdf_data, dict) else None
    if not types:
        return []
    out = []
    for type_uri in types:
        s = str(type_uri)
        local = s.split('#')[-1] if '#' in s else s.split('/')[-1]
        local = naming.safe_local_name(local)
        if local:
            out.append(local)
    return out


def class_row_keys(label: Any, extraction_type: Optional[str] = None) -> Set[str]:
    """Normalized keys under which a class-channel row would be minted. Role
    classes carry the enforced 'Role' suffix, so both spellings are keys."""
    key = normalize_class_key(naming.safe_local_name(str(label or '')))
    if not key:
        return set()
    keys = {key}
    if (extraction_type or '').lower() in _ROLE_TYPES and not key.endswith('role'):
        keys.add(key + 'role')
    return keys


def unpublished_class_keys(class_rows: Iterable[Any], batch_ids: Iterable[Any] = ()) -> Set[str]:
    """Keys of class rows that are unpublished and not part of the batch being
    committed (a class in the batch publishes together with its individuals).
    ``class_rows`` are working-store rows or stand-ins with ``id``,
    ``storage_type``, ``is_published``, ``entity_label`` and
    ``extraction_type``."""
    batch = set(batch_ids)
    keys: Set[str] = set()
    for row in class_rows:
        if (getattr(row, 'storage_type', 'class') or 'class') != 'class':
            continue
        if getattr(row, 'is_published', False):
            continue
        if getattr(row, 'id', None) in batch:
            continue
        keys |= class_row_keys(getattr(row, 'entity_label', ''), getattr(row, 'extraction_type', None))
    return keys


def partition_by_unpublished_type(
    individuals: List[Tuple[Any, Dict]],
    rejected_keys: Set[str],
    established: Callable[[str], Optional[str]],
) -> Tuple[List[Tuple[Any, Dict]], List[Tuple[Any, Dict, str]]]:
    """Split ``individuals`` into (kept, refused).

    An individual is refused when one of its type classes is in
    ``rejected_keys`` and ``established(local)`` returns None (the shared
    ontology tiers do not define the class, so the writer would have to
    declare the rejected class in the case TTL). Each refused entry carries the
    offending class local name.
    """
    kept: List[Tuple[Any, Dict]] = []
    refused: List[Tuple[Any, Dict, str]] = []
    if not rejected_keys:
        return list(individuals), refused
    for entity, rdf_data in individuals:
        offending = None
        for local in individual_type_locals(rdf_data):
            if normalize_class_key(local) in rejected_keys:
                try:
                    if established(local) is not None:
                        continue
                except Exception:  # noqa: BLE001 - resolver failure reads as not established
                    pass
                offending = local
                break
        if offending is None:
            kept.append((entity, rdf_data))
        else:
            refused.append((entity, rdf_data, offending))
    return kept, refused
