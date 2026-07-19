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

from app.services.commit import naming

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
        from app.services.commit.commit_context import _is_role_individual
        return _is_role_individual(entity)

    def _actor_key_and_label(self, entity, rdf_data: Dict):
        """(normalized key, display label) of a role individual's underlying
        actor, or (None, None) if it cannot be determined. Canonical logic
        is in commit_context (Step 2.1); this delegate remains for direct
        callers until Step 2.4."""
        from app.services.commit.commit_context import _actor_key_and_label
        return _actor_key_and_label(entity, rdf_data)

    def _build_agent_indices(self, individuals, case_ns: Namespace) -> None:
        """First-pass build of the Agent layer maps over the batch:
        - self._agent_index: actor_key -> Agent URI
        - self._facet_to_agent: role-facet URI -> Agent URI
        - self._agent_facets: Agent URI -> (actor_label, set(facet URIs))
        Transitional (Step 2.1): the canonical builder is
        commit_context.build_agent_indices, which the commit paths use via
        build_commit_context; this instance-state wrapper remains for
        direct test callers and is removed in Step 2.4."""
        from app.services.commit.commit_context import build_agent_indices
        self._agent_index, self._facet_to_agent, self._agent_facets = \
            build_agent_indices(individuals, case_ns)

    def _emit_agent_layer(self, g: Graph, ctx=None) -> None:
        """Emit one proeth-core:Agent per distinct actor and a hasRole edge to
        each role facet it bears. Idempotent: re-emitting the same Agent URI on a
        later-section append commit just re-asserts the same triples."""
        agent_facets = ctx.agent_facets if ctx is not None \
            else getattr(self, '_agent_facets', {})
        for agent_uri, (alabel, facet_uris) in agent_facets.items():
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
            frag = f"{naming.safe_frag(subj)}_{relprop}_{naming.safe_frag(obj)}"
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

