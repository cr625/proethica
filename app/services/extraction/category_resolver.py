"""Shared core-category resolver for the curated ontology chain.

Resolves the core D-tuple category (Role / Principle / Obligation / State /
Resource / Action / Event / Capability / Constraint) that a class chains to via
rdfs:subClassOf*, anchored in the curated foundation ontologies
(proethica-core + proethica-intermediate + proethica-intermediate-extended).

Authority note: the chain is trusted only because it is anchored in the curated
tiers. The stored OntServe entity-table category and the per-individual
conceptCategory literal are extraction-derived and can disagree with the chain;
callers that need the authoritative category must use this module, not those
literals. See docs-internal/reextraction/matcher-category-authority-design.md.

This is the single implementation. ontserve_commit_service delegates here so the
matcher gate and the commit guard resolve categories identically.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from rdflib import Graph, RDFS

from app.services.ontserve_config import get_ontserve_base_path

logger = logging.getLogger(__name__)

# Namespace strings (kept as plain strings to avoid a hard rdflib Namespace
# import dependency on callers).
PROETHICA_NS = "http://proethica.org/ontology/intermediate#"
PROETHICA_CORE_NS = "http://proethica.org/ontology/core#"

CORE_CATEGORY_NAMES = {
    "Role", "Principle", "Obligation", "State", "Resource",
    "Action", "Event", "Capability", "Constraint",
}

# The foundation tiers, highest authority first. The chain is resolved over the
# union of all three.
_FOUNDATION_TTLS = (
    "proethica-core.ttl",
    "proethica-intermediate.ttl",
    "proethica-intermediate-extended.ttl",
)


class CategoryResolver:
    """Lazily-built local-name -> core-category map over the curated tiers.

    The map keys on the intermediate-namespace local name of every class that
    chains (via rdfs:subClassOf*) to a proethica-core category. resolve() also
    accepts a full URI and reduces it to its local name before lookup.
    """

    def __init__(self, ontologies_dir=None):
        self._ontologies_dir = ontologies_dir
        self._map: Optional[Dict[str, str]] = None

    def _dir(self):
        if self._ontologies_dir is None:
            self._ontologies_dir = get_ontserve_base_path() / "ontologies"
        return self._ontologies_dir

    @staticmethod
    def _local_name(class_local_name_or_uri: str) -> str:
        """Reduce a URI or prefixed name to its bare local name."""
        s = str(class_local_name_or_uri)
        if "#" in s:
            return s.rsplit("#", 1)[-1]
        if "/" in s:
            return s.rsplit("/", 1)[-1]
        if ":" in s:
            return s.rsplit(":", 1)[-1]
        return s

    def _build_map(self) -> Dict[str, str]:
        g = Graph()
        ontologies_dir = self._dir()
        for fname in _FOUNDATION_TTLS:
            p = ontologies_dir / fname
            if p.exists():
                try:
                    g.parse(str(p), format="turtle")
                except Exception as e:
                    logger.warning(
                        "Could not parse %s for core-category map: %s", fname, e
                    )

        def reach_core(cls) -> Optional[str]:
            seen, stack = set(), [cls]
            while stack:
                c = stack.pop()
                if c in seen:
                    continue
                seen.add(c)
                local = str(c).rsplit("#", 1)[-1]
                if str(c).startswith(PROETHICA_CORE_NS) and local in CORE_CATEGORY_NAMES:
                    return local
                for sup in g.objects(c, RDFS.subClassOf):
                    stack.append(sup)
            return None

        out: Dict[str, str] = {}
        for cls in set(g.subjects(RDFS.subClassOf, None)):
            local = str(cls).rsplit("#", 1)[-1]
            if str(cls).startswith(PROETHICA_NS):
                core = reach_core(cls)
                if core:
                    out[local] = core
        logger.info("Loaded %d class -> core-category mappings", len(out))
        return out

    def resolve(self, class_local_name_or_uri: str) -> Optional[str]:
        """Return the core category the class chains to, or None if unknown."""
        if not class_local_name_or_uri:
            return None
        if self._map is None:
            self._map = self._build_map()
        return self._map.get(self._local_name(class_local_name_or_uri))


# Module-level singleton so the (relatively expensive) TTL parse happens once
# per process. Callers that need an isolated map (tests) can construct their own
# CategoryResolver instance.
_resolver: Optional[CategoryResolver] = None


def get_resolver() -> CategoryResolver:
    global _resolver
    if _resolver is None:
        _resolver = CategoryResolver()
    return _resolver


def resolve_core_category(class_local_name_or_uri: str) -> Optional[str]:
    """Resolve a class's curated-chain core category.

    Accepts a bare local name (e.g. "ProfessionalCompetence"), a prefixed name
    (e.g. "proeth:ProfessionalCompetence"), or a full URI. Returns one of the
    nine core category names, or None when the class is unknown to the curated
    tiers or has no core ancestor.
    """
    return get_resolver().resolve(class_local_name_or_uri)
