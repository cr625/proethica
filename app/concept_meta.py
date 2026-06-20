"""Canonical nine-component concept metadata: a single source of truth for the
colour and abbreviation maps for R, P, O, S, Rs, A, E, Ca, Cs.

These maps were previously duplicated as literals across several route helpers,
a service, and three templates. Consumers that need extra non-concept keys (the
provenance timeline rows, the entity-graph synthesis nodes) or a different
keying (by abbreviation, for the precedents D-tuple views) derive from these
canonical maps rather than re-declaring the palette. See
docs/concepts/color-scheme.md for the documented scheme.

Note: the reconciliation view (scenario_pipeline/reconcile.html) intentionally
uses a different (legacy SB-Admin) palette and is NOT a consumer of these maps.
"""

# Concept name (lowercase plural) -> Bootstrap hex colour.
CONCEPT_COLORS = {
    'roles': '#0d6efd',
    'states': '#6f42c1',
    'resources': '#20c997',
    'principles': '#fd7e14',
    'obligations': '#dc3545',
    'constraints': '#6c757d',
    'capabilities': '#0dcaf0',
    'actions': '#198754',
    'events': '#ffc107',
}

# Concept name -> single/double-letter abbreviation.
CONCEPT_ABBREVS = {
    'roles': 'R',
    'states': 'S',
    'resources': 'Rs',
    'principles': 'P',
    'obligations': 'O',
    'constraints': 'Cs',
    'capabilities': 'Ca',
    'actions': 'A',
    'events': 'E',
}

# Abbreviation-keyed derivations consumed by the precedents D-tuple views.
COMPONENT_COLORS = {abbrev: CONCEPT_COLORS[name] for name, abbrev in CONCEPT_ABBREVS.items()}
COMPONENT_LABELS = {abbrev: name.title() for name, abbrev in CONCEPT_ABBREVS.items()}
