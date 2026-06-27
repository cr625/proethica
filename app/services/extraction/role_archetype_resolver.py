"""Map a role label to its OCCUPATIONAL role archetype, data-driven from the ontology.

The matching rules are NOT in this module. They live in the domain's archetype ontology:
each occupational archetype is tagged ``proeth:archetypeAxis "occupational"`` and carries its
matching synonyms as ``rdfs:label`` (the base synonym, with a trailing " Role" stripped) plus
``skos:altLabel``. This module is a generic, domain-agnostic matcher: it loads those archetypes
and their synonyms (cached) and returns the longest-synonym match. A new domain ships only its
archetype ontology with its own roles and altLabels; nothing here changes.

The RELATIONAL axis is resolved separately from the Kong ``role_category``
(``CATEGORY_TO_ONTOLOGY_IRI``); the conformance check is a SHACL ``RoleArchetypeShape``. Spec:
``docs-internal/reextraction/role-archetype-spec.md``.
"""
import os
import threading
from pathlib import Path
from typing import Dict, Optional

import rdflib
from rdflib import RDFS
from rdflib.namespace import SKOS

_INTERMEDIATE_NS = "http://proethica.org/ontology/intermediate#"
_ARCHETYPE_AXIS = rdflib.URIRef(_INTERMEDIATE_NS + "archetypeAxis")
# The archetypeAxis value is now the SKOS concept URI (RoleArchetypeAxisScheme), not the "occupational"
# string. Match the concept, not a Literal.
_OCCUPATIONAL_ARCHETYPE = rdflib.URIRef(_INTERMEDIATE_NS + "OccupationalArchetype")

# Default to the engineering archetype ontology; override per domain via the env var or the
# ttl_path argument so a different domain points at its own archetype ontology.
_DEFAULT_TTL = (
    os.environ.get("PROETHICA_ARCHETYPE_TTL")
    or str(Path(__file__).resolve().parents[4] / "OntServe" / "ontologies"
           / "proethica-intermediate.ttl")
)

_cache: Dict[str, Dict[str, str]] = {}   # ttl_path -> {synonym_lower: archetype_iri}
_lock = threading.Lock()


def _strip_role(label: str) -> str:
    s = label.strip()
    if s.lower().endswith(" role"):
        s = s[:-5].strip()
    return s.lower()


def _build_index(ttl_path: str) -> Dict[str, str]:
    """{synonym (lowercased) -> archetype IRI} for every class tagged
    archetypeAxis="occupational". Synonyms = label minus a trailing " Role", plus altLabels."""
    g = rdflib.Graph()
    g.parse(ttl_path, format="turtle")
    syn_to_iri: Dict[str, str] = {}
    for cls in g.subjects(_ARCHETYPE_AXIS, _OCCUPATIONAL_ARCHETYPE):
        iri = str(cls)
        synonyms = set()
        for lbl in g.objects(cls, RDFS.label):
            s = _strip_role(str(lbl))
            if s:
                synonyms.add(s)
        for alt in g.objects(cls, SKOS.altLabel):
            s = str(alt).strip().lower()
            if s:
                synonyms.add(s)
        for s in synonyms:
            syn_to_iri.setdefault(s, iri)
    return syn_to_iri


def _index(ttl_path: str) -> Dict[str, str]:
    if ttl_path not in _cache:
        with _lock:
            if ttl_path not in _cache:
                _cache[ttl_path] = _build_index(ttl_path)
    return _cache[ttl_path]


def clear_cache() -> None:
    """Drop the cached index (e.g. after the archetype ontology changes)."""
    with _lock:
        _cache.clear()


def resolve_occupational_archetype(label: str, ttl_path: Optional[str] = None) -> Optional[str]:
    """Return the IRI of the occupational archetype whose longest synonym is a substring of the
    role label, or None for the unmapped tail (which the RoleArchetypeShape flags for review)."""
    if not label:
        return None
    try:
        idx = _index(ttl_path or _DEFAULT_TTL)
    except Exception:
        return None
    t = label.lower()
    best_iri: Optional[str] = None
    best_len = -1
    for syn, iri in idx.items():
        if len(syn) > best_len and syn in t:
            best_iri, best_len = iri, len(syn)
    return best_iri
