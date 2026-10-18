"""Shared core-category resolver for the curated ontology chain.

Resolves the core D-tuple category (Role / Principle / Obligation / State /
Resource / Action / Event / Capability / Constraint) that a class chains to via
rdfs:subClassOf*, anchored in the curated foundation ontologies
(proethica-core + proethica-intermediate + proethica-intermediate-extended).

Authority note: the chain is trusted only because it is anchored in the curated
tiers. The stored OntServe entity-table category and the per-individual
materialized direct type are extraction-derived and can disagree with the chain;
callers that need the authoritative category must use this module, not those
signals. See docs-internal/reextraction/matcher-category-authority-design.md.

This is the single implementation. ontserve_commit_service delegates here so the
matcher gate and the commit guard resolve categories identically.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional

from rdflib import Graph, OWL, RDF, RDFS, SKOS, URIRef

from app.services.ontserve.ontserve_config import get_ontserve_base_path

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


# Occupational role-axis heads (intermediate namespace). The axis sits BELOW
# the nine core categories: both heads chain to core:Role, so CategoryResolver
# cannot tell them apart, yet they are owl:disjointWith each other -- the
# case-4 (run 20) Pellet inconsistency, where one individual was typed to a
# descendant of each.
ROLE_AXIS_HEADS = {
    "ProfessionalRole": "professional",
    "ParticipantRole": "participant",
}


class RoleAxisResolver(CategoryResolver):
    """Lazily-built local-name -> occupational-axis map over the curated tiers.

    Mirrors CategoryResolver (same TTL tiers, same local-name keying), but the
    rdfs:subClassOf* closure targets the intermediate ProfessionalRole /
    ParticipantRole heads instead of the nine core categories. resolve()
    returns 'professional' or 'participant'; a class with no chain to either
    head resolves to None (unresolvable classes are deliberately ignored by
    guards), and a class whose chain reaches BOTH heads (inconsistent in the
    curated base) also resolves to None with a warning, so guards only ever
    act on an unambiguous side.
    """

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
                        "Could not parse %s for role-axis map: %s", fname, e
                    )

        heads = {
            URIRef(PROETHICA_NS + local): axis
            for local, axis in ROLE_AXIS_HEADS.items()
        }

        def reach_axes(cls) -> set:
            seen, stack, found = set(), [cls], set()
            while stack:
                c = stack.pop()
                if c in seen:
                    continue
                seen.add(c)
                axis = heads.get(c)
                if axis:
                    found.add(axis)
                    continue
                stack.extend(g.objects(c, RDFS.subClassOf))
            return found

        out: Dict[str, str] = {}
        for cls in set(g.subjects(RDFS.subClassOf, None)) | set(heads):
            if not str(cls).startswith(PROETHICA_NS):
                continue
            axes = reach_axes(cls)
            if len(axes) == 1:
                out[str(cls).rsplit("#", 1)[-1]] = next(iter(axes))
            elif len(axes) == 2:
                logger.warning(
                    "Role-axis map: %s chains to BOTH ProfessionalRole and "
                    "ParticipantRole in the curated tiers (disjointness "
                    "violation in the base); leaving it unresolved.", cls,
                )
        logger.info("Loaded %d class -> role-axis mappings", len(out))
        return out


class ClassHierarchyIndex:
    """Lazily-built asserted rdfs:subClassOf* closure plus extended-store
    definitions over the curated tiers.

    Answers the two questions the merge-stage canonicalization guard asks that
    CategoryResolver (core category only) and RoleAxisResolver (occupational
    axis only) cannot: whether one class is a STRICT specialization of another,
    and what definition the extended store already attaches to an IRI. The
    extended store (proethica-intermediate-extended) is where earlier
    extractions mint their case-specific classes, so a canonicalization that
    lands on an extended IRI carrying a different definition would put two
    concepts on one IRI (the case-8 RegulatoryComplianceObligation collision).
    A class the immutable base (core + intermediate) declares is a curated
    reuse target and never counts as a collision, so extended_definition()
    returns None for it.

    Keyed by local name like the sibling resolvers. Same TTL tiers, same lazy
    single parse per instance.
    """

    def __init__(self, ontologies_dir=None):
        self._ontologies_dir = ontologies_dir
        self._parents: Optional[Dict[str, set]] = None
        self._base_classes: Optional[set] = None
        self._extended_defs: Optional[Dict[str, str]] = None

    def _dir(self):
        if self._ontologies_dir is None:
            self._ontologies_dir = get_ontserve_base_path() / "ontologies"
        return self._ontologies_dir

    @staticmethod
    def _local(ref) -> str:
        return CategoryResolver._local_name(str(ref))

    def _build(self) -> None:
        ontologies_dir = self._dir()
        parents: Dict[str, set] = {}
        base_classes: set = set()
        extended_defs: Dict[str, str] = {}
        for fname in _FOUNDATION_TTLS:
            p = ontologies_dir / fname
            if not p.exists():
                continue
            g = Graph()
            try:
                g.parse(str(p), format="turtle")
            except Exception as e:
                logger.warning(
                    "Could not parse %s for class-hierarchy index: %s", fname, e
                )
                continue
            for sub, sup in g.subject_objects(RDFS.subClassOf):
                if isinstance(sub, URIRef) and isinstance(sup, URIRef):
                    parents.setdefault(self._local(sub), set()).add(self._local(sup))
            is_extended = fname == "proethica-intermediate-extended.ttl"
            for cls in g.subjects(RDF.type, OWL.Class):
                if not isinstance(cls, URIRef):
                    continue
                local = self._local(cls)
                if not is_extended:
                    base_classes.add(local)
                    continue
                text = g.value(cls, SKOS.definition) or g.value(cls, RDFS.comment)
                if text:
                    extended_defs[local] = str(text)
        self._parents = parents
        self._base_classes = base_classes
        self._extended_defs = extended_defs
        logger.info(
            "Loaded class-hierarchy index: %d subclass subjects, %d base classes, "
            "%d extended definitions", len(parents), len(base_classes), len(extended_defs)
        )

    def _ensure(self) -> None:
        if self._parents is None:
            self._build()

    def is_strict_subclass(self, sub, sup) -> bool:
        """True when ``sub`` reaches ``sup`` through one or more asserted
        rdfs:subClassOf edges in the curated tiers. A class is not a strict
        subclass of itself, and an unknown class reaches nothing."""
        if not sub or not sup:
            return False
        self._ensure()
        target = self._local(sup)
        start = self._local(sub)
        if not target or start == target:
            return False
        seen, stack = set(), [start]
        while stack:
            c = stack.pop()
            if c in seen:
                continue
            seen.add(c)
            for parent in self._parents.get(c, ()):
                if parent == target:
                    return True
                stack.append(parent)
        return False

    def extended_definition(self, cls) -> Optional[str]:
        """The skos:definition (else rdfs:comment) the extended store attaches
        to ``cls``, or None when the class is unknown, undefined there, or
        declared in the immutable base."""
        if not cls:
            return None
        self._ensure()
        local = self._local(cls)
        if local in self._base_classes:
            return None
        return self._extended_defs.get(local)


# Module-level singleton so the (relatively expensive) TTL parse happens once
# per process. Callers that need an isolated map (tests) can construct their own
# CategoryResolver instance.
_resolver: Optional[CategoryResolver] = None

_axis_resolver: Optional[RoleAxisResolver] = None

_hierarchy_index: Optional[ClassHierarchyIndex] = None


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


def get_axis_resolver() -> RoleAxisResolver:
    global _axis_resolver
    if _axis_resolver is None:
        _axis_resolver = RoleAxisResolver()
    return _axis_resolver


def resolve_role_axis(class_local_name_or_uri: str) -> Optional[str]:
    """Resolve a role class's curated-chain occupational axis.

    Accepts the same forms as resolve_core_category. Returns 'professional'
    or 'participant', or None when the class has no unambiguous asserted
    rdfs:subClassOf* chain to either head in the curated tiers.
    """
    return get_axis_resolver().resolve(class_local_name_or_uri)


def get_hierarchy_index() -> ClassHierarchyIndex:
    global _hierarchy_index
    if _hierarchy_index is None:
        _hierarchy_index = ClassHierarchyIndex()
    return _hierarchy_index


def is_strict_subclass(sub, sup) -> bool:
    """Whether ``sub`` is a strict asserted rdfs:subClassOf* descendant of
    ``sup`` in the curated tiers. Both arguments accept the same forms as
    resolve_core_category (local name, prefixed name, full URI)."""
    return get_hierarchy_index().is_strict_subclass(sub, sup)


def extended_class_definition(cls) -> Optional[str]:
    """The definition proethica-intermediate-extended attaches to ``cls``, or
    None for an unknown class or one the immutable base declares."""
    return get_hierarchy_index().extended_definition(cls)
