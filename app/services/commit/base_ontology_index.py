"""
Cross-commit base-ontology caches for the commit service (PHASE 2 Step 2.2).

One BaseOntologyIndex owns every ontology-file-derived cache the commit
service needs across commits: the established-category resolver adapter,
the immutable-base category reservation map, and the object-property
local-name set. These were previously three lazily-written instance
attributes on the service (spread across two mixins); owning them in one
collaborator makes the service's remaining state exactly its immutable
configuration.

Semantics preserved verbatim from the mixin implementations:

- established_core_category consults the shared extraction
  CategoryResolver, which INCLUDES proethica-intermediate-extended.
- base_core_category walks core + intermediate ONLY (the immutable base;
  the extended store is being written during a re-extraction run and
  would mask collisions).
- object_property_locals includes the extended store, because the
  temporal serializer must not emit literals on ANY declared object
  property.
"""

import logging
from typing import Optional, Set

from rdflib import Graph, Namespace, OWL, RDF, RDFS

logger = logging.getLogger(__name__)

PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")

_NINE_CORE = {'Role', 'Principle', 'Obligation', 'State', 'Resource',
              'Action', 'Event', 'Capability', 'Constraint'}


class BaseOntologyIndex:
    """Lazy caches over the on-disk base ontologies, pinned to one
    ontologies directory. Build cost is paid at most once per cache per
    instance; the commit service holds one instance for its lifetime."""

    def __init__(self, ontologies_dir):
        self.ontologies_dir = ontologies_dir
        self._category_resolver = None
        self._base_cat_cache = None
        self._objprop_cache = None

    def established_core_category(self, class_local_name: str) -> Optional[str]:
        """Core category an EXISTING intermediate class already chains to
        (via rdfs:subClassOf*), or None. Delegates to the shared
        CategoryResolver (one implementation, shared with the matcher
        cross-category gate)."""
        if self._category_resolver is None:
            from app.services.extraction.category_resolver import CategoryResolver
            self._category_resolver = CategoryResolver(self.ontologies_dir)
        return self._category_resolver.resolve(class_local_name)

    def base_core_category(self, class_local_name: str) -> Optional[str]:
        """Core category an IRI is reserved for in the IMMUTABLE base
        (core + intermediate ONLY, NOT the extended store)."""
        if self._base_cat_cache is None:
            cache = {}
            base = Graph()
            for fn in ('proethica-core.ttl', 'proethica-intermediate.ttl'):
                p = self.ontologies_dir / fn
                if p.exists():
                    try:
                        base.parse(str(p), format='turtle')
                    except Exception as e:
                        logger.warning("base-category map: could not parse %s: %s", fn, e)
            core_ns = str(PROETHICA_CORE)

            def reach(cls, seen):
                if cls in seen:
                    return None
                seen.add(cls)
                s = str(cls)
                if s.startswith(core_ns) and s.split('#')[-1] in _NINE_CORE:
                    return s.split('#')[-1]
                for sup in base.objects(cls, RDFS.subClassOf):
                    r = reach(sup, seen)
                    if r:
                        return r
                return None

            for cls in set(base.subjects(RDF.type, OWL.Class)):
                local = str(cls).split('#')[-1].split('/')[-1]
                cat = reach(cls, set())
                if cat:
                    cache[local] = cat
            self._base_cat_cache = cache
        return self._base_cat_cache.get(class_local_name)

    def object_property_locals(self) -> Set[str]:
        """Local names of every owl:ObjectProperty declared in core /
        intermediate / intermediate-extended."""
        if self._objprop_cache is not None:
            return self._objprop_cache
        names: Set[str] = set()
        if not self.ontologies_dir:
            self._objprop_cache = names
            return names
        for fn in ('proethica-core.ttl', 'proethica-intermediate.ttl',
                   'proethica-intermediate-extended.ttl'):
            p = self.ontologies_dir / fn
            if not p.exists():
                continue
            try:
                gg = Graph()
                gg.parse(p, format='turtle')
            except Exception as e:
                logger.warning(f"Could not parse {fn} for object-property detection: {e}")
                continue
            for s in gg.subjects(RDF.type, OWL.ObjectProperty):
                names.add(str(s).split('#')[-1].split('/')[-1])
        self._objprop_cache = names
        return names
