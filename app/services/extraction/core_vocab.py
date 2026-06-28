"""Domain-INDEPENDENT extraction vocabulary (the shared registry).

The nine-component upper model and the core property local-names are the framework, not the
engineering domain. They are identical across every professional-ethics domain (engineering, legal,
medical), so they live here once and are imported wherever needed, instead of being re-declared in
schemas.py / config.py / the matchers / the materializers (which the 2026-06-24 domain-coupling audit
found duplicated in four-plus places). A second domain reuses this module unchanged.

What is domain-DEPENDENT (namespaces, ontology names, the category taxonomy that FILLS these slots,
provision/section conventions) lives in `domain_config.py` + the per-domain reference sheet, not here.

This module imports nothing heavy (no Flask, no DB), so tooling (the judge) and the live extractor can
both import it.
"""
from __future__ import annotations

# The nine components (D-tuple), canonical capitalized names.
COMPONENTS: tuple[str, ...] = (
    "Role", "Principle", "Obligation", "State", "Resource",
    "Action", "Event", "Capability", "Constraint",
)

# Plural extraction-type -> core Category. Mirrors config.CONCEPT_TYPE_TO_CORE_CATEGORY (the existing
# copy stays until the onboarding refactor re-points it here; values are identical so they cannot drift).
CONCEPT_TYPE_TO_CORE_CATEGORY: dict[str, str] = {
    "roles": "Role",
    "principles": "Principle",
    "obligations": "Obligation",
    "states": "State",
    "resources": "Resource",
    "actions": "Action",
    "events": "Event",
    "capabilities": "Capability",
    "constraints": "Constraint",
}

# Happenings (the temporal components that carry time anchors / fluent transitions).
HAPPENING_COMPONENTS: frozenset[str] = frozenset({"Action", "Event"})

# Core property LOCAL-names (the full IRI = a domain's core_ns/intermediate_ns + the local-name).
# Grouped by role so the canonicalization materializer and the edge materializers reference one source.
class CoreProp:
    # role / agent
    hasRole = "hasRole"
    isRoleOf = "isRoleOf"
    hasClient = "hasClient"
    employedBy = "employedBy"
    professionalPeerOf = "professionalPeerOf"
    # normative bearer edges (range = Agent)
    obligatedParty = "obligatedParty"
    constrainedEntity = "constrainedEntity"
    possessedBy = "possessedBy"
    invokedBy = "invokedBy"
    affects = "affects"           # State -> Agent  (the canonicalization state-attachment edge)
    availableTo = "availableTo"
    citedByAgent = "citedByAgent"
    # normative structure
    hasObligation = "hasObligation"
    adheresToPrinciple = "adheresToPrinciple"
    derivedFromPrinciple = "derivedFromPrinciple"
    hasCapability = "hasCapability"
    usesResource = "usesResource"
    # state / fluent machinery
    hasState = "hasState"          # Action -> State (domain = Action, per proeth-core)
    activatesObligation = "activatesObligation"
    activatesConstraint = "activatesConstraint"
    activatedByEvent = "activatedByEvent"
    terminatedByEvent = "terminatedByEvent"
    initiates = "initiates"
    terminates = "terminates"
    # defeasibility
    competesWith = "competesWith"
    prevailsOver = "prevailsOver"
    defeasibleUnder = "defeasibleUnder"
    # action/obligation
    fulfillsObligation = "fulfillsObligation"
    violatesObligation = "violatesObligation"
    guidedByPrinciple = "guidedByPrinciple"
    # provenance / provisions
    citesProvision = "citesProvision"


__all__ = [
    "COMPONENTS", "CONCEPT_TYPE_TO_CORE_CATEGORY", "HAPPENING_COMPONENTS", "CoreProp",
]
