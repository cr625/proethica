"""
Per-commit context for the OntServe commit paths (PHASE 2 Step 2.1).

One CommitContext is built at the start of each individuals-commit (live
append path and versioned fresh-write path) and passed explicitly through
the emit call chain. It carries the per-commit build state that was
previously written onto the service instance by four different mixins
(hidden temporal coupling); the factory below also replaces the
near-duplicated index-building blocks the two paths used to carry.

Cross-commit ontology-derived caches (object-property locals, base
category cache, the category resolver) deliberately stay on long-lived
collaborators, not here.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Set, Tuple

from rdflib import Graph, Namespace, OWL, RDF, RDFS

from app.services.commit import naming

logger = logging.getLogger(__name__)


@dataclass
class CommitContext:
    """Per-commit build state for one individuals-commit run."""

    case_id: int
    case_ns: Namespace
    graph: Graph
    # Label -> individual URI index so role relationship targets (short
    # actor names like "Engineer A") resolve to real edges.
    rel_label_index: Dict[str, object] = field(default_factory=dict)
    # Agent layer (Option C): actor_key -> Agent URI.
    agent_index: Dict[str, object] = field(default_factory=dict)
    # Role-facet URI -> Agent URI.
    facet_to_agent: Dict[object, object] = field(default_factory=dict)
    # Agent URI -> (actor_label, set(facet URIs)).
    agent_facets: Dict[object, Tuple[str, Set[object]]] = field(default_factory=dict)
    # R1 edge-primary relational archetype: role facets that received a
    # relational archetype from an actor edge (the role_category fallback
    # is skipped for them; the edge wins on conflict). Reset per commit.
    role_edge_archetyped: Set[object] = field(default_factory=set)


def _is_role_individual(entity) -> bool:
    return (getattr(entity, 'extraction_type', '') or '').lower() == 'roles'


def _actor_key_and_label(entity, rdf_data: Optional[Dict]):
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
    return naming.norm_label(str(actor)), str(actor)


def build_agent_indices(individuals, case_ns: Namespace):
    """First-pass build of the Agent layer maps over the batch:
    (agent_index, facet_to_agent, agent_facets); see CommitContext fields.
    Used by _emit_agent_layer (mints the Agents + hasRole) and by the
    relationships branch (attaches actor relations at the Agent level)."""
    agent_index: Dict[str, object] = {}
    facet_to_agent: Dict[object, object] = {}
    agent_facets: Dict[object, Tuple[str, Set[object]]] = {}
    for _ent, _rdf in individuals:
        if not _is_role_individual(_ent):
            continue
        akey, alabel = _actor_key_and_label(_ent, _rdf)
        if not akey:
            continue
        facet_uri = case_ns[naming.safe_label(getattr(_ent, 'entity_label', '') or '')]
        agent_uri = agent_index.get(akey)
        if agent_uri is None:
            agent_uri = case_ns['Agent_' + naming.safe_label(alabel)]
            agent_index[akey] = agent_uri
            agent_facets[agent_uri] = (alabel, set())
        facet_to_agent[facet_uri] = agent_uri
        agent_facets[agent_uri][1].add(facet_uri)
    return agent_index, facet_to_agent, agent_facets


def build_commit_context(case_id: int, case_ns: Namespace, g: Graph,
                         individuals, seed_rel_index_from_graph: bool) -> CommitContext:
    """Build the per-commit context for one individuals batch.

    seed_rel_index_from_graph: append path only -- also seed the label
    index from individuals already on disk (the loaded graph), so a
    later-section commit can still resolve targets against actors an
    earlier-section commit wrote. The current batch (authoritative fresh
    URIs) wins via setdefault. The versioned path overwrites and has no
    prior graph, so it passes False.
    """
    ctx = CommitContext(case_id=case_id, case_ns=case_ns, graph=g)

    for _ent, _rdf in individuals:
        _lbl = getattr(_ent, 'entity_label', None)
        if _lbl:
            ctx.rel_label_index[naming.norm_label(_lbl)] = case_ns[naming.safe_label(_lbl)]
    if seed_rel_index_from_graph:
        for _s in g.subjects(RDF.type, OWL.NamedIndividual):
            for _lbl_lit in g.objects(_s, RDFS.label):
                ctx.rel_label_index.setdefault(naming.norm_label(str(_lbl_lit)), _s)

    ctx.agent_index, ctx.facet_to_agent, ctx.agent_facets = build_agent_indices(
        individuals, case_ns)
    return ctx
