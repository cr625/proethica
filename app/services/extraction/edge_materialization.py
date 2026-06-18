"""Shared edge-materialization helper for committed case TTLs.

A committed case TTL carries individuals + their subClassOf-core chains but no
relational layer. This module adds, in one place, the three edge families the
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


def materialize_edges_on_ttl(case_id: int, ttl_path) -> Dict[str, Any]:
    """Run all three edge appliers over a just-written case TTL (in place).

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
    try:
        from app.services.extraction.resource_edges import apply_resource_edges
        results["resource_edges"] = apply_resource_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: resource-edge applier failed for case %s", case_id)
        results["resource_edges"] = {"error": str(e)}

    # 2c. State-affects edges (DB-driven, embedding-resolved): the state
    # `affectedParties` list becomes State proeth-core:affects Agent edges, naming
    # the case actor(s) a state bears on. Mirrors the resource-edge applier
    # (embedding shortlist + batched LLM multi-select, prov:Derivation).
    try:
        from app.services.extraction.state_affects_edges import apply_state_affects_edges
        results["state_affects_edges"] = apply_state_affects_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: state-affects applier failed for case %s", case_id)
        results["state_affects_edges"] = {"error": str(e)}

    # 2d. Participant edges (DB-driven, embedding-resolved): the Pass-2 component
    # 'who' fields (obligation obligatedParty / constraint constrainedEntity /
    # capability possessedBy / principle invokedBy) become Component -> Agent edges
    # (obligatedParty / constrainedEntity / possessedBy / invokedBy). Additive: the
    # literal is kept because rpo_edges/defeasibility read it as string context.
    # Mirrors the state-affects applier (embedding shortlist + batched LLM select,
    # prov:Derivation). Range Agent is OWL-DL-safe; the unified guard validates the
    # component subject.
    try:
        from app.services.extraction.participant_edges import apply_participant_edges
        results["participant_edges"] = apply_participant_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: participant-edge applier failed for case %s", case_id)
        results["participant_edges"] = {"error": str(e)}

    # 2e. Fluent-transition edges (DB-driven, embedding-resolved): the Step-3 temporal
    # happenings' initiates / terminates State labels become Action/Event -> State edges
    # (proeth-core:initiates / terminates), the canonical Event Calculus direction. Restores
    # the fluent as the middle term between the temporal and normative components. Mirrors
    # the state-affects / participant appliers (embedding shortlist + batched LLM select,
    # prov:Derivation). No-op for cases with no committed temporal individuals.
    try:
        from app.services.extraction.fluent_edges import apply_fluent_edges
        results["fluent_edges"] = apply_fluent_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: fluent-edge applier failed for case %s", case_id)
        results["fluent_edges"] = {"error": str(e)}

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
    # proeth:toEntity object edges + the time:* OWL-Time triple are materialised onto
    # real individuals. Before this the converter's pre-computed endpoint URIs (lossy
    # 50-char truncation, legacy namespace) dangled silently. Range is union(Action,
    # Event); the unified guard validates both endpoints, dropping any phrasing
    # mis-resolved to a State. No-op for cases with no committed temporal relations.
    try:
        from app.services.extraction.temporal_relation_edges import apply_temporal_relation_edges
        results["temporal_relation_edges"] = apply_temporal_relation_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: temporal-relation applier failed for case %s", case_id)
        results["temporal_relation_edges"] = {"error": str(e)}

    # 2g. Action normative-engagement edges (DB-driven, embedding-resolved): the Step-3
    # Action's fulfills / violates / raises obligation labels and guidedByPrinciple labels
    # become Action -> Obligation / Principle edges (proeth-core:fulfillsObligation,
    # proeth:violatesObligation / raisesObligation / guidedByPrinciple). Grounds the
    # normative engagement to the real O/P individuals, closing the Event-Calculus loop
    # begun by fluent_edges (Action -> State) + state_edges (State -> O/Cs). Mirrors the
    # fluent applier; range Obligation/Principle is among the nine disjoint categories, so
    # the unified guard validates both endpoints. No-op for cases with no Action individuals.
    try:
        from app.services.extraction.obligation_edges import apply_obligation_edges
        results["obligation_edges"] = apply_obligation_edges(
            case_id=case_id, ttl_path=ttl_path, write_back=True,
        )
    except Exception as e:
        logger.exception("materialize: obligation-edge applier failed for case %s", case_id)
        results["obligation_edges"] = {"error": str(e)}

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
