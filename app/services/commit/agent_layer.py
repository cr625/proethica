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

from rdflib import Graph, Literal, Namespace, RDF, RDFS, OWL, XSD

from app.services.commit import naming

logger = logging.getLogger(__name__)

PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CORE = Namespace("http://proethica.org/ontology/core#")
PROV = Namespace("http://www.w3.org/ns/prov#")

# The relational archetype classes (defined classes over the actor edges) and
# their head. A facet typed only to these chains through no occupational
# archetype and fails RoleArchetypeShape (case-8 review, L6).
_RELATIONAL_ARCHETYPES = frozenset({
    'RelationalRole', 'ProviderClientRole', 'ProfessionalPeerRole',
    'EmployerRelationshipRole', 'PublicResponsibilityRole',
})


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
    #
    # _is_role_individual / _actor_key_and_label / _build_agent_indices (the
    # per-instance builder) moved to commit_context.py in Step 2.1; their
    # transitional instance-state delegates on this mixin were removed in
    # Step 2.4 once every call site moved to the CommitContext built by
    # commit_context.build_commit_context.

    def _emit_agent_layer(self, g: Graph, ctx=None) -> None:
        """Emit one proeth-core:Agent per distinct actor and a hasRole edge to
        each role facet it bears. Idempotent: re-emitting the same Agent URI on a
        later-section append commit just re-asserts the same triples. ctx=None
        (a stray direct caller with no per-commit context) means there is
        nothing to emit."""
        if ctx is None:
            return
        for agent_uri, (alabel, facet_uris) in ctx.agent_facets.items():
            g.add((agent_uri, RDF.type, OWL.NamedIndividual))
            g.add((agent_uri, RDF.type, PROETHICA_CORE.Agent))
            g.add((agent_uri, RDFS.label, Literal(alabel)))
            for f in sorted(facet_uris):
                g.add((agent_uri, PROETHICA_CORE.hasRole, f))
        self._carry_occupational_type_to_relational_facets(g, ctx)

    def _carry_occupational_type_to_relational_facets(self, g: Graph, ctx) -> int:
        """Type a relational-only facet to the occupational class its bearer's
        other facets carry (case-8 review, L6).

        A facet typed only to a relational archetype (Engineer L's
        ProviderClientRole and PublicResponsibilityRole facets) chains through
        no occupational archetype, so RoleArchetypeShape warned on every such
        facet although the same agent's DesignEngineerRole facet named the
        occupation. The bearer's occupational class is carried over when the
        agent's facets name exactly one; an agent with two occupational classes
        is left alone (the choice would be a guess). Returns the number of
        rdf:type triples added.
        """
        carried = 0
        for agent_uri, (_alabel, facet_uris) in ctx.agent_facets.items():
            facets = sorted(facet_uris)
            inter_types = {
                f: {t for t in g.objects(f, RDF.type) if str(t).startswith(str(PROETHICA))}
                for f in facets
            }
            occupational = {
                t for f in facets for t in inter_types[f]
                if str(t).split('#')[-1] not in _RELATIONAL_ARCHETYPES
                and str(t).split('#')[-1].endswith('Role')
            }
            if len(occupational) != 1:
                if len(occupational) > 1:
                    logger.info(
                        "Agent %s bears %d occupational role classes (%s); relational-only "
                        "facets left untyped", str(agent_uri).split('#')[-1], len(occupational),
                        sorted(str(t).split('#')[-1] for t in occupational))
                continue
            (occupation,) = occupational
            for f in facets:
                types = inter_types[f]
                if not types or not all(str(t).split('#')[-1] in _RELATIONAL_ARCHETYPES for t in types):
                    continue
                if (f, RDF.type, occupation) not in g:
                    g.add((f, RDF.type, occupation))
                    carried += 1
                    logger.info("Relational-only facet %s typed to the bearer's occupational "
                                "class %s", str(f).split('#')[-1], str(occupation).split('#')[-1])
        return carried

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

