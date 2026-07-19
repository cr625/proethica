"""
Agent-layer mixin for OntServeCommitService (Option C: cross-section actor identity).

Extracted verbatim from ontserve_commit_service.py (god-file split, Item 1
Step 1.4): the "Agent layer" section. OntServeCommitService gains
AgentLayerMixin as a base class so every self._method(...) call site is
unaffected.

rdflib namespace constants are redeclared locally rather than imported back
from ontserve_commit_service.py (which imports this module for the mixin), to
avoid a circular import; Namespace equality is string-based so this has no
behavioral effect.
"""

import logging
from datetime import datetime, timezone
from typing import Dict

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, XSD

logger = logging.getLogger(__name__)

PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")


class AgentLayerMixin:
    """Agent layer (Option C: cross-section actor identity)."""

    # --- Agent layer (Option C: cross-section actor identity) -----------------
    # A role facet (e.g. "Engineer A Original Design Engineer" in facts,
    # "Cooperation-Refusing Design Engineer" in discussion) is a role the same
    # underlying actor bears. We mint ONE proeth-core:Agent per distinct actor
    # and link each facet to it via proeth-core:hasRole, so the actor is not
    # fragmented across sections. The actor identity is the LLM-declared `actor`
    # field (rules-as-data); when absent it falls back to the facet's own label
    # (so every role still gets an Agent, but only a shared `actor` merges
    # facets). The Agent URI is deterministic from the actor label, so separate
    # section commits on the append path converge on the same Agent node.

    @staticmethod
    def _is_role_individual(entity) -> bool:
        return (getattr(entity, 'extraction_type', '') or '').lower() == 'roles'

    def _actor_key_and_label(self, entity, rdf_data: Dict):
        """(normalized key, display label) of a role individual's underlying
        actor, or (None, None) if it cannot be determined."""
        props = (rdf_data or {}).get('properties', {}) or {}
        actor_vals = props.get('actor')
        actor = None
        if actor_vals:
            actor = actor_vals[0] if isinstance(actor_vals, list) else actor_vals
        if not actor:
            actor = getattr(entity, 'entity_label', None)
        if not actor:
            return None, None
        return self._norm_label(str(actor)), str(actor)

    def _build_agent_indices(self, individuals, case_ns: Namespace) -> None:
        """First-pass build of the Agent layer maps over the batch:
        - self._agent_index: actor_key -> Agent URI
        - self._facet_to_agent: role-facet URI -> Agent URI
        - self._agent_facets: Agent URI -> (actor_label, set(facet URIs))
        Used by _emit_agent_layer (mints the Agents + hasRole) and by the
        relationships branch (attaches actor relations at the Agent level)."""
        self._agent_index = {}
        self._facet_to_agent = {}
        self._agent_facets = {}
        for _ent, _rdf in individuals:
            if not self._is_role_individual(_ent):
                continue
            akey, alabel = self._actor_key_and_label(_ent, _rdf)
            if not akey:
                continue
            facet_uri = case_ns[self._safe_label(getattr(_ent, 'entity_label', '') or '')]
            agent_uri = self._agent_index.get(akey)
            if agent_uri is None:
                agent_uri = case_ns['Agent_' + self._safe_label(alabel)]
                self._agent_index[akey] = agent_uri
                self._agent_facets[agent_uri] = (alabel, set())
            self._facet_to_agent[facet_uri] = agent_uri
            self._agent_facets[agent_uri][1].add(facet_uri)

    def _emit_agent_layer(self, g: Graph) -> None:
        """Emit one proeth-core:Agent per distinct actor and a hasRole edge to
        each role facet it bears. Idempotent: re-emitting the same Agent URI on a
        later-section append commit just re-asserts the same triples."""
        for agent_uri, (alabel, facet_uris) in getattr(self, '_agent_facets', {}).items():
            g.add((agent_uri, RDF.type, OWL.NamedIndividual))
            g.add((agent_uri, RDF.type, PROETHICA_CORE.Agent))
            g.add((agent_uri, RDFS.label, Literal(alabel)))
            for f in sorted(facet_uris):
                g.add((agent_uri, PROETHICA_CORE.hasRole, f))

    def _emit_relationship_provenance(self, g: Graph, case_ns: Namespace, subj,
                                      relprop: str, obj, rtype, quote) -> None:
        """PROV-O Derivation for an actor relationship edge, mirroring the
        defeasibility-edge provenance: a prov:Derivation node linking the two
        endpoints, carrying the triggering quote in prov:value when the roles
        prompt supplied one. Best-effort and additive; never blocks the edge."""
        try:
            frag = f"{self._safe_frag(subj)}_{relprop}_{self._safe_frag(obj)}"
            prov_iri = case_ns['relationship_edge_provenance_' + frag]
            # Idempotent: the prov-node IRI is deterministic from (subj, relprop,
            # obj), and the same actor edge is emitted once per facet the actor
            # bears (and again on a re-commit). Emit the node once; re-emission
            # would otherwise multi-value generatedAtTime / comment / value.
            if (prov_iri, RDF.type, PROV.Derivation) in g:
                return
            g.add((prov_iri, RDF.type, PROV.Derivation))
            g.add((prov_iri, PROV.wasDerivedFrom, subj))
            g.add((prov_iri, PROV.wasDerivedFrom, obj))
            g.add((prov_iri, RDFS.label, Literal(f"Actor relationship edge ({rtype or relprop})")))
            if quote:
                g.add((prov_iri, PROV.value, Literal(str(quote))))
            g.add((prov_iri, RDFS.comment, Literal(f"relation_type={rtype}; property={relprop}")))
            g.add((prov_iri, PROV.generatedAtTime, Literal(
                datetime.now(timezone.utc).isoformat(), datatype=XSD.dateTime)))
        except Exception as e:
            logger.info(f"relationship provenance skipped: {e}")

