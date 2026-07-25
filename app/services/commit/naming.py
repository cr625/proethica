"""
Label / URI / literal hygiene helpers for OntServe commit.

Extracted from ontserve_commit_service.py (god-file split, Item 1 Step 1.1).
Pure functions moved verbatim from OntServeCommitService static/module-level
members; the leading underscore is dropped from each name per the split plan.
OntServeCommitService keeps class-attribute shims (staticmethod(...)) so every
existing self._method(...) call site is unaffected.
"""

import logging
from typing import Optional, Tuple

from rdflib import Graph, Literal, URIRef, XSD

logger = logging.getLogger(__name__)

# ONT-4 (2026-07-01): the Step-3 temporal serializer emits an event individual as proeth:Event
# plus proeth:eventType (outcome/exogenous/automatic) with no per-case subclass. The ratified
# design types the event to exactly one of the three DISJOINT core ORIGIN subclasses. This maps
# the emitted eventType to the origin-subclass LOCAL name; each origin subclass is subClassOf
# core:Event, so typing an event to one is consistent with the chain and the nine-way
# AllDisjointClasses (the three origins are disjoint with each other, not with Event). The topical
# event taxonomy this replaces is owl:deprecated in proethica-intermediate.
_EVENT_ORIGIN_SUBCLASS = {
    'outcome': 'AgentCausedEvent',
    'exogenous': 'ExogenousEvent',
    'automatic': 'AutomaticEvent',
}


def resolve_event_origin_category(rdf_data: dict) -> "str | None":
    """Return the core Event ORIGIN-subclass local name (AgentCausedEvent / ExogenousEvent /
    AutomaticEvent) for an event individual's emitted proeth:eventType, or None when the field is
    absent or its value is unrecognized. Reads the flat Step-3 JSON-LD (top-level proeth:eventType)
    and, defensively, a nested properties dict; a list value takes its first element."""
    if not rdf_data:
        return None
    v = rdf_data.get('proeth:eventType') or rdf_data.get('eventType')
    if not v:
        props = rdf_data.get('properties')
        if isinstance(props, dict):
            v = props.get('proeth:eventType') or props.get('eventType')
    if isinstance(v, list):
        v = v[0] if v else None
    if not v:
        return None
    resolved = _EVENT_ORIGIN_SUBCLASS.get(str(v).strip().lower())
    if resolved is None:
        # A PRESENT but unrecognized value must not silently commit as bare
        # Event (no-silent-fallback rule); absence is the intended bare case.
        logger.warning("Event origin routing: eventType value %r not in the "
                       "outcome/exogenous/automatic vocabulary; committing as bare Event",
                       v)
    return resolved


def enforce_role_suffix(local_name: str, label: str, category: Optional[str]) -> Tuple[str, str]:
    """Every role CLASS ends in 'Role' (URI local-name + rdfs:label). Deterministic hard
    enforcement of the convention the extraction prompt only soft-biases; idempotent and a
    no-op for non-Role categories. Applied before the base-check so a suffixless extraction
    (e.g. 'Design Engineer') maps onto the canonical promoted class (DesignEngineerRole) and
    is reused, not re-minted."""
    if category != 'Role':
        return local_name, label
    if local_name and not local_name.endswith('Role'):
        local_name = f"{local_name}Role"
    if label and not label.rstrip().endswith('Role'):
        label = f"{label.rstrip()} Role"
    return local_name, label


def safe_local_name(label: str) -> str:
    """Label -> URI local-name: keep only [A-Za-z0-9], dropping spaces, hyphens, and every other
    punctuation mark. An allowlist, not the former hand-enumerated denylist, so no character is ever
    forgotten -- the denylist missed the hyphen and minted 'CompetenceSelf-AssessmentCapability' where
    the curated base has 'CompetenceSelfAssessmentCapability'. That mismatch defeated both the class
    matcher and the D15 base-residence check, leaking a duplicate class into the extended store."""
    import re
    return re.sub(r'[^A-Za-z0-9]', '', label or '')


def case_ontology_iri(case_id) -> URIRef:
    """The case ontology declaration IRI (<.../ontology/case/N>), used as the
    machine-readable dcterms:source citation on case-discovered classes --
    symmetric with the curated classes' literature dcterms:source (DOIs). A
    discovered class is grounded extensionally by the case(s) it was found
    in (McLaren), so the case IS its source."""
    return URIRef(f"http://proethica.org/ontology/case/{int(case_id)}")


def camelCase(text: str) -> str:
    """Convert a snake_case / spaced key to camelCase for a property local name.

    Delegates to the single shared converter (R3, app/utils/predicate_naming)
    so commit and storage cannot drift apart from the edge readers that hardcode
    these predicate names. Idempotent on an already-camelCase single token (the
    generic `properties` keys arrive already camelCase and must be preserved, not
    lowercased -- that was the `activePeriod` -> `activeperiod` mangling bug).
    """
    from app.utils.predicate_naming import to_camel_case
    return to_camel_case(text)


def sanitize_graph_literals(g: Graph) -> int:
    """Strip C0 control characters (except tab/newline/CR) from every literal in the
    graph, in place, before serialization. Source documents occasionally carry stray
    control bytes (the case-56 probe found U+0002 inside question text propagated from
    document_sections), which survive Turtle but break every XML-based consumer
    (RDF/XML serialization, OWLAPI/Pellet explain). One chokepoint for all emission
    paths rather than per-field cleaning. Returns the number of literals rewritten."""
    import re
    ctrl = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    fixes = []
    for s, p, o in g:
        if isinstance(o, Literal) and ctrl.search(str(o)):
            fixes.append((s, p, o,
                          Literal(ctrl.sub('', str(o)), lang=o.language, datatype=o.datatype)))
    for s, p, o, clean in fixes:
        g.remove((s, p, o))
        g.add((s, p, clean))
    return len(fixes)


def confidence_literal(value) -> Literal:
    """proeth:confidence typed xsd:decimal (B12). The extraction JSON carries
    confidence as a string ("0.9"), which the generic property loops emitted
    as an untyped literal, so the value was not numerically comparable in
    SPARQL. A non-numeric value falls back to the plain literal."""
    try:
        return Literal(float(value), datatype=XSD.decimal)
    except (TypeError, ValueError):
        return Literal(value if isinstance(value, str) else str(value))


def safe_label(label: str) -> str:
    """URI-safe local name from a label (single source of truth for minting
    individual URIs and for the relationship target index)."""
    s = (label or '').replace(" ", "_").replace("(", "").replace(")", "")
    s = s.replace('"', '').replace("'", "").replace(",", "")
    s = s.replace("<", "").replace(">", "").replace("&", "")
    return s


def norm_label(label: str) -> str:
    return ' '.join((label or '').lower().split())


def safe_frag(iri) -> str:
    """Sanitized local name of an IRI, for building a derived provenance-node
    fragment (mirrors defeasibility_pipeline._safe_frag)."""
    frag = str(iri).rsplit('#', 1)[-1].rsplit('/', 1)[-1]
    return ''.join(c if c.isalnum() or c in '_-' else '_' for c in frag)[:60]
