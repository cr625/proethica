"""Resolve NSPE provision citation literals to nspe: CodeProvision IRIs.

Case ontologies carry board-conclusion citations as bare literals on
``proeth:citedProvision1..N`` (e.g. "II.4.a." or "I.6."). The NSPE Code of
Ethics ontology (OntServe id 246) declares each provision as a
``proeth-core:CodeProvision`` individual ``nspe:<frag>`` (dots -> underscores).
This module maps the dotted-code literals onto those IRIs and materializes a
``proeth-core:citesProvision`` object-property edge, so case reasoning can
traverse conclusion -> provision -> established Principle/Obligation/Constraint.

Only well-formed dotted codes that match an existing nspe node are mapped.
Verbose ("NSPE Code of Ethics Section 2"), Model-Law, and BER-case-precedent
literals are intentionally skipped (they are not NSPE code provisions or are
ambiguous). Deterministic, no LLM.
"""
from __future__ import annotations

import re
from typing import List, Optional, Set

NSPE_NS = "http://proethica.org/ontology/nspe#"
INTERMEDIATE_NS = "http://proethica.org/ontology/intermediate#"
CORE_NS = "http://proethica.org/ontology/core#"
CORE_CITES_PROVISION = "http://proethica.org/ontology/core#citesProvision"
# Constraint proeth:source -> the provision that establishes it. establishedBy has
# domain union(Principle, Obligation, Constraint) and range CodeProvision in
# proethica-core; the extraction stores the provision source on Constraint
# individuals, so the applier below is Constraint-scoped.
CORE_ESTABLISHED_BY = "http://proethica.org/ontology/core#establishedBy"
# A code resource (Guideline) contains the provisions the case cites for it. containsProvision has
# domain Guideline, range CodeProvision -- the precise property for resource provision_codes (NOT
# refersToDocument, whose range is an IAO document, nor citesProvision, which is for analysis).
CORE_CONTAINS_PROVISION = "http://proethica.org/ontology/core#containsProvision"

# Roman-numeral section, optional dotted numeric subsections, optional single
# lowercase letter: I, I.1, II.1, II.1.a, III.9.d
_DOTTED = re.compile(r"^[IVX]+(\.[0-9]+)*(\.[a-z])?$")

# Dotted-code token EMBEDDED in a free-text source literal ("NSPE Code II.2.b",
# "NSPE Code III.8.a; BER Case 98-3"). Requires at least one dotted numeric
# component so a bare roman numeral inside prose can never resolve; a literal that
# IS a bare section code ("II") still resolves via the whole-literal
# normalize_citation path in extract_provision_fragments.
_EMBEDDED_SECTION = re.compile(r"\b[IVX]+(?:\.[0-9]+)+(?:\.[a-z])?\b")


def _frag(code: str) -> str:
    return code.replace(".", "_")


def _ancestors(code: str):
    parts = code.split(".")
    return [".".join(parts[: i + 1]) for i in range(len(parts))]


def normalize_citation(literal: str) -> Optional[str]:
    """A citation literal -> nspe fragment (e.g. 'II.4.a.' -> 'II_4_a'), or None
    if it is not a well-formed dotted NSPE code."""
    s = (literal or "").strip().rstrip(".").strip()
    if not s or not _DOTTED.match(s):
        return None
    return _frag(s)


def extract_provision_fragments(literal: str) -> List[str]:
    """Dotted NSPE section codes found in a source literal, as nspe fragments,
    order-preserving and deduplicated. The whole literal is tried first (the
    citedProvisionN form, e.g. 'II.4.a.'); otherwise embedded dotted tokens with at
    least one numeric component are extracted ('NSPE Code III.8.a; BER Case 98-3'
    -> ['III_8_a']). Non-code sources ('State Seal Law', 'Local regulations',
    'NSPE Code of Ethics') yield []."""
    whole = normalize_citation(literal)
    if whole:
        return [whole]
    out: List[str] = []
    for tok in _EMBEDDED_SECTION.findall(literal or ""):
        frag = normalize_citation(tok)
        if frag and frag not in out:
            out.append(frag)
    return out


def valid_fragments_from_codes(codes) -> Set[str]:
    """Valid nspe node fragments = every dotted ancestor of the given section
    codes (matches the nodes the NSPE ontology generator materializes)."""
    frags: Set[str] = set()
    for code in codes:
        for anc in _ancestors(code):
            frags.add(_frag(anc))
    return frags


def load_valid_fragments(conn) -> Set[str]:
    """Load valid fragments from a psycopg2 connection to ai_ethical_dm."""
    cur = conn.cursor()
    cur.execute("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    return valid_fragments_from_codes(code for (code,) in cur.fetchall())


class ProvisionCitationResolver:
    def __init__(self, valid_fragments: Set[str]):
        self.valid = valid_fragments

    def resolve(self, literal: str) -> Optional[str]:
        frag = normalize_citation(literal)
        if frag and frag in self.valid:
            return NSPE_NS + frag
        return None

    def resolve_all(self, literal: str) -> List[str]:
        """All nspe: IRIs cited in a FREE-TEXT source literal (whole-literal dotted
        code first, then embedded dotted tokens), validated against the existing
        nspe nodes. Order-preserving, deduplicated. The multi-code counterpart of
        resolve() for literals like 'NSPE Code III.8.a; BER Case 98-3'."""
        return [NSPE_NS + frag for frag in extract_provision_fragments(literal)
                if frag in self.valid]


def _is_cited_provision_pred(p) -> bool:
    local = str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return local.startswith("citedProvision")


def apply_cites_provision_edges(g, resolver: ProvisionCitationResolver) -> int:
    """Add ``proeth-core:citesProvision nspe:<frag>`` for each resolvable
    ``citedProvisionN`` literal in graph ``g``. Returns the number of new edges.
    Idempotent: skips edges already present.
    """
    from rdflib import URIRef, Literal

    cites = URIRef(CORE_CITES_PROVISION)
    new_edges = set()
    for s, p, o in g:
        if isinstance(o, Literal) and _is_cited_provision_pred(p):
            iri = resolver.resolve(str(o))
            if iri:
                edge = (s, cites, URIRef(iri))
                if edge not in g:
                    new_edges.add(edge)
    for e in new_edges:
        g.add(e)
    return len(new_edges)


def apply_cites_provision_on_ttl(ttl_path) -> int:
    """Resolve citedProvisionN literals to nspe: IRIs on one case TTL and add
    proeth-core:citesProvision edges, writing back when any are added.

    Deterministic (no LLM). Loads valid NSPE fragments from the live
    ai_ethical_dm guideline_sections via the active SQLAlchemy session. Returns
    the number of edges added. Raises on DB/parse errors -- callers that must
    not fail a commit should wrap this.
    """
    from pathlib import Path
    from rdflib import Graph
    from sqlalchemy import text
    from app.models import db

    codes = [r[0] for r in db.session.execute(
        text("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    ).fetchall()]
    if not codes:
        return 0
    resolver = ProvisionCitationResolver(valid_fragments_from_codes(codes))

    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    added = apply_cites_provision_edges(g, resolver)
    if added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return added


def apply_established_by_edges(g, resolver: ProvisionCitationResolver) -> int:
    """Add ``proeth-core:establishedBy nspe:<frag>`` for each dotted NSPE code found
    in a Constraint individual's ``proeth:source`` literal(s). Returns the number of
    new edges. Idempotent and ADDITIVE (the source literal is kept). Deliberately
    emits no prov:Derivation nodes, unlike the LLM-resolved edge families: the
    mapping is deterministic (dotted code to DB-validated fragment) and the
    untouched ``proeth:source`` literal on the same subject is the derivation
    record.

    Endpoint validation: the subject must carry the materialized direct
    ``rdf:type proeth-core:Constraint`` (core declares establishedBy on
    union(Principle, Obligation, Constraint); the extraction stores provision
    sources on Constraints, so a source literal on any other subject is ignored);
    the object is validated by DB fragment membership exactly as citesProvision.
    Non-code sources ("State Seal Law", "Local regulations", "NSPE Code of Ethics")
    resolve to nothing and yield no edge. Deterministic, no LLM."""
    from rdflib import RDF, URIRef, Literal

    established = URIRef(CORE_ESTABLISHED_BY)
    constraint_cls = URIRef(CORE_NS + "Constraint")
    source_pred = URIRef(INTERMEDIATE_NS + "source")
    new_edges = set()
    for s in g.subjects(RDF.type, constraint_cls):
        for o in g.objects(s, source_pred):
            if not isinstance(o, Literal):
                continue
            for iri in resolver.resolve_all(str(o)):
                edge = (s, established, URIRef(iri))
                if edge not in g:
                    new_edges.add(edge)
    for e in new_edges:
        g.add(e)
    return len(new_edges)


def apply_established_by_on_ttl(ttl_path) -> int:
    """Resolve Constraint proeth:source literals to nspe: IRIs on one case TTL and
    add proeth-core:establishedBy edges (constraint -> the provision that
    establishes it), writing back when any are added.

    Deterministic (no LLM), DB-validated against the live ai_ethical_dm
    guideline_sections via the SAME provision resolver as citesProvision. Returns
    the number of edges added. Raises on DB/parse errors; callers that must not
    fail a commit should wrap this. Mirrors apply_cites_provision_on_ttl."""
    from pathlib import Path
    from rdflib import Graph
    from sqlalchemy import text
    from app.models import db

    codes = [r[0] for r in db.session.execute(
        text("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    ).fetchall()]
    if not codes:
        return 0
    resolver = ProvisionCitationResolver(valid_fragments_from_codes(codes))

    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    added = apply_established_by_edges(g, resolver)
    if added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return added


def _is_provision_codes_pred(p) -> bool:
    local = str(p).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return local == "provisionCodes"


def apply_resource_provision_edges(g, resolver: ProvisionCitationResolver) -> int:
    """Add ``proeth-core:containsProvision nspe:<frag>`` for each resolvable code in a resource
    individual's ``provisionCodes`` literals. Returns the number of new edges. Idempotent.

    A code resource (e.g. the NSPE Code, typed EthicalCode subClassOf Guideline) contains the
    provisions the case cites for it; provision_codes is the LLM-extracted routing input and
    containsProvision is its canonical form, connecting the resource to the nspe: CodeProvision
    nodes so case reasoning can traverse resource -> provision -> established Principle/Obligation.
    Same DB-validated, deterministic resolution as the conclusion citesProvision pass.
    """
    from rdflib import RDF, URIRef, Literal

    contains = URIRef(CORE_CONTAINS_PROVISION)
    ethical_code = URIRef(INTERMEDIATE_NS + "EthicalCode")
    new_edges = set()
    for s, p, o in g:
        if isinstance(o, Literal) and _is_provision_codes_pred(p):
            # Only a code resource contains provisions (the class whose chain reaches
            # Guideline). Direct-type check: the case graph alone cannot see the
            # Guideline link (it is only in proethica-intermediate), and a dotted
            # designation on e.g. a LegalResource must not mint a containsProvision.
            if (s, RDF.type, ethical_code) not in g:
                continue
            iri = resolver.resolve(str(o))
            if iri:
                edge = (s, contains, URIRef(iri))
                if edge not in g:
                    new_edges.add(edge)
    for e in new_edges:
        g.add(e)
    return len(new_edges)


def apply_resource_provisions_on_ttl(ttl_path) -> int:
    """Resolve resource provisionCodes literals to nspe: IRIs on one case TTL and add
    proeth-core:containsProvision edges (a code resource -> the CodeProvisions it cites).

    Deterministic (no LLM), DB-validated against the live ai_ethical_dm guideline_sections.
    Returns the number of edges added. Raises on DB/parse errors; callers that must not fail a
    commit should wrap this. Mirrors apply_cites_provision_on_ttl for the resource direction.
    """
    from pathlib import Path
    from rdflib import Graph
    from sqlalchemy import text
    from app.models import db

    codes = [r[0] for r in db.session.execute(
        text("SELECT section_code FROM guideline_sections WHERE guideline_id = 1")
    ).fetchall()]
    if not codes:
        return 0
    resolver = ProvisionCitationResolver(valid_fragments_from_codes(codes))

    ttl_path = Path(ttl_path)
    g = Graph()
    g.parse(str(ttl_path), format="turtle")
    added = apply_resource_provision_edges(g, resolver)
    if added:
        g.serialize(destination=str(ttl_path), format="turtle")
    return added
