"""Shared edge-materialization helper for committed case TTLs.

A committed case TTL carries individuals + their subClassOf-core chains but no
relational layer. This module adds, in one place, the edge families the
KI2026 corpus relies on:

  - Defeasibility (competesWith / prevailsOver / defeasibleUnder), LLM-derived.
  - R->P->O dependency (hasObligation / adheresToPrinciple / derivedFromPrinciple),
    LLM-derived, with a domain/range guard that keeps the case Pellet-consistent.
  - cites-provision (citesProvision nspe:<frag>), deterministic, DB-driven.

Before this helper existed the edges were produced only by one-off corpus
backfill scripts and the entity-review-UI commit path (auto_commit_service),
so the pipeline commit (run_commit_task -> OntServeCommitService) emitted none
and re-extraction silently stripped them. Routing every commit path through
materialize_edges_on_ttl is what keeps the two paths from drifting again.

Each applier is best-effort: a failure in one is logged and recorded in the
result dict but never raised, so edge materialization can never fail a commit.
The backfill scripts remain the corpus-level safety net.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _run_family(results: Dict[str, Any], key: str, case_id: int, ttl_path) -> None:
    """Run one data-driven edge family from the registry (by spec name) at its place
    in the ordered pipeline, recording its result under ``key`` (best-effort: a
    failure is logged and stored, never raised). The six migrated families
    (resource / state-affects / participant / fluent / obligation / temporal-relation)
    share one framework; the spec for ``key`` carries all the per-family data."""
    try:
        from app.services.extraction.edge_spec import EDGE_REGISTRY, materialize_edge_family
        spec = next(s for s in EDGE_REGISTRY if s.name == key)
        results[key] = materialize_edge_family(case_id, ttl_path, spec, write_back=True)
    except Exception as e:
        logger.exception("materialize: %s applier failed for case %s", key, case_id)
        results[key] = {"error": str(e)}


def materialize_edges_on_ttl(case_id: int, ttl_path) -> Dict[str, Any]:
    """Run the full ordered edge-applier registry plus the deterministic appliers
    and the unified domain/range guard over a just-written case TTL (in place).

    Args:
        case_id: numeric case id (used for PROV IRI minting).
        ttl_path: path to the committed proethica-case-<id>.ttl on disk.

    Returns:
        dict mapping each applier name to its result (or {"error": ...}).
    """
    ttl_path = Path(ttl_path)
    results: Dict[str, Any] = {}

    # 1. Defeasibility edges (LLM).
    try:
        from app.services.extraction.defeasibility_pipeline import apply_defeasibility_edges
        results["defeasibility"] = apply_defeasibility_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: defeasibility applier failed for case %s", case_id)
        results["defeasibility"] = {"error": str(e)}

    # 2. State-anchored edges (DB-driven, embedding-resolved): the state
    # extractor's obligation_activation / action_constraints / activation+
    # termination_conditions become activatesObligation / activatesConstraint /
    # activatedByEvent / terminatedByEvent, plus a principleTransformation
    # annotation. Runs before R->P->O so the annotation can ground that derivation.
    try:
        from app.services.extraction.state_edges import apply_state_edges
        results["state_edges"] = apply_state_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: state-edge applier failed for case %s", case_id)
        results["state_edges"] = {"error": str(e)}

    # 2b. Resource-anchored edges (DB-driven, embedding-resolved): the resource
    # `used_by` field becomes Resource proeth-core:availableTo Agent edges, naming
    # the case actor(s) that use each resource. Mirrors the state-edge applier
    # (embedding shortlist + batched LLM multi-select, prov:Derivation).
    _run_family(results, "resource_edges", case_id, ttl_path)

    # 2c. State-affects edges (DB-driven, embedding-resolved): the state
    # `affectedParties` list becomes State proeth-core:affects Agent edges, naming
    # the case actor(s) a state bears on. Mirrors the resource-edge applier
    # (embedding shortlist + batched LLM multi-select, prov:Derivation).
    _run_family(results, "state_affects_edges", case_id, ttl_path)

    # 2d. Participant edges (DB-driven, embedding-resolved): the Pass-2 component
    # 'who' fields (obligation obligatedParty / constraint constrainedEntity /
    # capability possessedBy / principle invokedBy) plus the actor-edge additions
    # (resource cited_by -> citedByAgent; Step-3 per-action hasAgent ->
    # isPerformedBy) become Component -> Agent edges. The commit writes no
    # literal shadow for these fields (CMT-3: a RELATION field is materialized
    # as an object-property edge only); readers that need string context derive
    # it from the edges (e.g. rpo_edges resolves principle invokedBy from the
    # proeth-core:invokedBy targets' labels). Mirrors the state-affects applier
    # (embedding shortlist + batched LLM select, prov:Derivation). Range Agent is OWL-DL-safe; the unified guard validates the
    # component subject. invokedBy/citedByAgent Board-pattern literals resolve
    # deterministically to the single case-scoped NSPE Board Agent (minted on first
    # use, excluded from every actor candidate pool).
    _run_family(results, "participant_edges", case_id, ttl_path)

    # 2d-bis. Obligation -> Capability requirement edges (DB-driven,
    # embedding-resolved): the capability individuals' requiredForObligations labels
    # become Obligation proeth-core:requiresCapability Capability edges (core v2.8.0:
    # an obligation presupposes the capacity to discharge it). The family emits
    # INVERTED (the row subject is the Capability); closes the O->Ca loop previously
    # stranded as class-level literals with no commit consumer.
    _run_family(results, "requires_capability_edges", case_id, ttl_path)

    # 2e. Fluent-transition edges (DB-driven, embedding-resolved): the Step-3 temporal
    # happenings' initiates / terminates State labels become Action/Event -> State edges
    # (proeth-core:initiates / terminates), the canonical Event Calculus direction. Restores
    # the fluent as the middle term between the temporal and normative components. Mirrors
    # the state-affects / participant appliers (embedding shortlist + batched LLM select,
    # prov:Derivation). No-op for cases with no committed temporal individuals.
    _run_family(results, "fluent_edges", case_id, ttl_path)

    # 2f. OWL-Time anchors (deterministic): mint a time:Instant / time:ProperInterval
    # individual per happening (from its proeth:temporalExtent) and link via time:hasTime.
    # The OWL-Time "when" complement to the Event Calculus fluent layer; Allen-relation
    # individuals supply the ordering. Outside the nine disjoint categories, so guard-neutral.
    try:
        from app.services.extraction.time_anchor import apply_time_anchors
        results["time_anchors"] = apply_time_anchors(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: time-anchor applier failed for case %s", case_id)
        results["time_anchors"] = {"error": str(e)}

    # 2f-bis. Temporal (Allen) relation endpoints (DB-driven, embedding-resolved): each
    # reified TemporalRelation's fromEntity/toEntity free-text timeline phrasings are
    # resolved to the committed Action/Event individuals and the proeth:fromEntity /
    # proeth:toEntity object edges + the time:* OWL-Time triple are materialized onto
    # real individuals. Before this the converter's pre-computed endpoint URIs (lossy
    # 50-char truncation, legacy namespace) dangled silently. Range is union(Action,
    # Event); the unified guard validates both endpoints, dropping any phrasing
    # mis-resolved to a State. No-op for cases with no committed temporal relations.
    _run_family(results, "temporal_relation_edges", case_id, ttl_path)

    # 2g. Action normative-engagement edges (DB-driven, embedding-resolved): the Step-3
    # Action's fulfills / violates / raises obligation labels and guidedByPrinciple labels
    # become Action -> Obligation / Principle edges (all four core: proeth-core:fulfillsObligation,
    # proeth-core:violatesObligation / raisesObligation / guidedByPrinciple, promoted v2.8.0). Grounds the
    # normative engagement to the real O/P individuals, closing the Event-Calculus loop
    # begun by fluent_edges (Action -> State) + state_edges (State -> O/Cs). Mirrors the
    # fluent applier; range Obligation/Principle is among the nine disjoint categories, so
    # the unified guard validates both endpoints. No-op for cases with no Action individuals.
    _run_family(results, "obligation_edges", case_id, ttl_path)

    # 2h. Causal-chain endpoint edges (DB-driven, embedding-resolved): the Step-3 causal
    # analysis' cause / effect labels become CausalChain -> Action/Event edges and the
    # responsibleAgent label(s) become CausalChain -> Agent edges. Wires the causal chain
    # (the irreducible NESS analysis stays as literal content) into the graph so it is
    # traversable. Mirrors the fluent/obligation appliers; CausalChain is a non-core domain,
    # so the unified guard validates only the object endpoints.
    try:
        from app.services.extraction.causal_edges import apply_causal_edges
        results["causal_edges"] = apply_causal_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: causal-edge applier failed for case %s", case_id)
        results["causal_edges"] = {"error": str(e)}

    # 2i. Event -> causing Action edges (deterministic): the converter's legacy
    # causedByAction IRI, skipped by the serializer, resolved to the committed Action
    # individual so the event->cause link is durable (not always covered by a CausalChain).
    try:
        from app.services.extraction.causal_edges import apply_event_cause_edges
        results["event_cause_edges"] = apply_event_cause_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: event-cause-edge applier failed for case %s", case_id)
        results["event_cause_edges"] = {"error": str(e)}

    # 2j. Ground synthesis CausalNormativeLink reasoning nodes to the Action they analyze
    # (proeth:analyzesAction), so the reasoning -> action -> obligation-URI chain is reachable.
    try:
        from app.services.extraction.causal_edges import apply_causal_normative_link_edges
        results["causal_normative_link_edges"] = apply_causal_normative_link_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: causal-normative-link applier failed for case %s", case_id)
        results["causal_normative_link_edges"] = {"error": str(e)}

    # 3. R->P->O dependency edges (LLM) with the domain/range Pellet guard.
    try:
        from app.services.extraction.rpo_edges import apply_rpo_edges
        results["rpo"] = apply_rpo_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: R->P->O applier failed for case %s", case_id)
        results["rpo"] = {"error": str(e)}

    # 3. cites-provision edges (deterministic, DB-driven).
    try:
        from app.services.extraction.provision_citation_resolver import apply_cites_provision_on_ttl
        results["cites_provision"] = {"edges_added": apply_cites_provision_on_ttl(ttl_path)}
    except Exception as e:
        logger.exception("materialize: cites-provision applier failed for case %s", case_id)
        results["cites_provision"] = {"error": str(e)}

    # 3b. resource provisionCodes -> containsProvision edges (a code resource -> the CodeProvisions
    # it cites; deterministic, DB-driven). Gap 3 of the Resources fix, mirroring cites-provision.
    try:
        from app.services.extraction.provision_citation_resolver import apply_resource_provisions_on_ttl
        results["resource_provisions"] = {"edges_added": apply_resource_provisions_on_ttl(ttl_path)}
    except Exception as e:
        logger.exception("materialize: resource-provision applier failed for case %s", case_id)
        results["resource_provisions"] = {"error": str(e)}

    # 3c. constraint source -> establishedBy edges (deterministic, DB-validated):
    # dotted NSPE codes inside Constraint proeth:source literals resolve to nspe:
    # CodeProvision IRIs via the SAME provision resolver as citesProvision
    # (constraint -> the provision that establishes it). Non-code sources
    # ("State Seal Law", "Local regulations") yield no edge; the literal is kept.
    try:
        from app.services.extraction.provision_citation_resolver import apply_established_by_on_ttl
        results["established_by"] = {"edges_added": apply_established_by_on_ttl(ttl_path)}
    except Exception as e:
        logger.exception("materialize: establishedBy applier failed for case %s", case_id)
        results["established_by"] = {"error": str(e)}

    # 4. Unified Pellet-safety guard over ALL edge families on the final TTL.
    # apply_rpo_edges guards its own edges, but a defeasibility edge can still
    # pull an endpoint into a disjoint core class by domain/range inference
    # (e.g. a Principle-typed individual used as a competesWith endpoint, range
    # Obligation). Running the guard once here, after every applier, drops any
    # such cross-family violation so the persisted case stays OWL-DL consistent.
    try:
        from rdflib import Graph
        from app.services.extraction.rpo_edges import (
            drop_domain_range_violations, ALL_EDGE_RANGE,
        )
        g = Graph()
        g.parse(str(ttl_path), format="turtle")
        dropped = drop_domain_range_violations(g, case_id, edge_range=ALL_EDGE_RANGE)
        if dropped:
            g.serialize(destination=str(ttl_path), format="turtle")
        results["unified_guard"] = {"triples_dropped": dropped}
    except Exception as e:
        logger.exception("materialize: unified domain/range guard failed for case %s", case_id)
        results["unified_guard"] = {"error": str(e)}

    logger.info("Edge materialization for case %s: %s", case_id, results)

    # Refresh the cross-case defeasibility band index from the just-materialized TTL.
    # Derived/rebuildable cache; a failure must not fail the commit but is logged so it
    # stays visible (matches the edge-applier hook convention above).
    try:
        from app.services.defeasibility_view_service import refresh_band_index
        results["band_index"] = {"rows": refresh_band_index(case_id)}
    except Exception as e:
        logger.warning("materialize: band-index refresh failed for case %s: %s",
                       case_id, e, exc_info=True)
        results["band_index"] = {"error": str(e)}

    return results
