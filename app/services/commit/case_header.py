"""
Case ontology header: the owl:Ontology declaration written at the top of every
proethica-case-N.ttl.

One place for the header so all commit paths (fresh, legacy-merge, versioned,
temporal) emit the same triples. The header carries the facts OntServe reads
into the ontology record on sync (services/ontology_sync_service.py):

    rdfs:label         "ProEthica Case N Ontology"
    dcterms:title      the case title            -> metadata.display_name
    dcterms:identifier the NSPE case number      -> metadata.case_number
    dcterms:temporal   the decade, e.g. "1990s"  -> metadata.subcategory (index grouping)
    dcterms:created    commit timestamp
    owl:imports        the base ontologies the case builds on

The decade comes from the case-number prefix (NSPE numbers cases YY-N by the
year of the Board decision; two-digit years >= 50 are 19YY, otherwise 20YY),
falling back to doc_metadata['year'] when the number is not in that form.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS, OWL, RDF, RDFS

CASE_ONTOLOGY_URI = "http://proethica.org/ontology/case/{case_id}"
DEFAULT_IMPORTS = (
    "http://proethica.org/ontology/cases",
    "http://proethica.org/ontology/intermediate",
)

_CASE_NUMBER = re.compile(r'^\s*(\d{2})-\d+\s*$')


def decade_from_case_number(case_number: Optional[str], year: Optional[object] = None) -> Optional[str]:
    """'24-2' -> '2020s'; '58-1' -> '1950s'; else from a four-digit year; else None."""
    if case_number:
        m = _CASE_NUMBER.match(str(case_number))
        if m:
            yy = int(m.group(1))
            full = 1900 + yy if yy >= 50 else 2000 + yy
            return f"{full // 10 * 10}s"
    if year:
        try:
            y = int(str(year)[:4])
            if 1900 <= y <= 2099:
                return f"{y // 10 * 10}s"
        except ValueError:
            pass
    return None


def case_header_fields(case_id: int) -> Dict[str, Optional[str]]:
    """title / case_number / decade for a case id from the Document row; all
    values None when the document is absent. Import inside so this module stays
    importable without an app context (the commit mixins are imported early)."""
    from app.models.document import Document
    from app.models import db

    doc = db.session.get(Document, case_id)
    if doc is None:
        return {'title': None, 'case_number': None, 'decade': None}
    title = (doc.title or '').strip() or None
    case_number = (doc.case_number or '').strip() or None
    md = doc.doc_metadata if isinstance(doc.doc_metadata, dict) else {}
    decade = decade_from_case_number(case_number, md.get('year'))
    return {'title': title, 'case_number': case_number, 'decade': decade}


def add_case_ontology_header(g: Graph, case_id: int,
                             imports: Iterable[str] = DEFAULT_IMPORTS,
                             created: Optional[datetime] = None) -> URIRef:
    """Add the owl:Ontology declaration for a case to graph g; returns its URI."""
    uri = URIRef(CASE_ONTOLOGY_URI.format(case_id=case_id))
    g.add((uri, RDF.type, OWL.Ontology))
    g.add((uri, RDFS.label, Literal(f"ProEthica Case {case_id} Ontology")))
    fields = case_header_fields(case_id)
    if fields['title']:
        g.add((uri, DCTERMS.title, Literal(fields['title'])))
    if fields['case_number']:
        g.add((uri, DCTERMS.identifier, Literal(fields['case_number'])))
    if fields['decade']:
        g.add((uri, DCTERMS.temporal, Literal(fields['decade'])))
    for imp in imports:
        g.add((uri, OWL.imports, URIRef(imp)))
    g.add((uri, DCTERMS.created, Literal(created or datetime.now(timezone.utc))))
    return uri
