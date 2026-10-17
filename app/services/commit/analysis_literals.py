"""Step-4 analysis literals at commit: replace semantics and the stale-row gate
(case 8 review, lesson L8).

The PrecedentCaseReference literals committed for case 8 (citationType,
citationContext) came from a superseded Step-4 run whose rows had been
deleted: the append commit path merges a re-seen individual ADDITIVELY
(``g.add`` is a no-op for identical triples and a union for new ones), so the
old literal values survived next to nothing that replaced them, and a later
recompute stamped ``committed_at`` on the new rows without re-emitting.

Two guards, both pure functions over an rdflib graph:

- :func:`strip_analysis_literals` removes every literal-valued triple of a
  Step-4 analysis individual before it is re-emitted, so the graph carries the
  row's current values and nothing older (replace semantics).
- :func:`stale_analysis_rows` reports the rows whose defining literals are not
  in the written graph. The commit refuses to stamp ``committed_at`` on them.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Tuple

from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import OWL, SKOS

from app.services.commit import naming

logger = logging.getLogger(__name__)

PROETHICA = Namespace("http://proethica.org/ontology/intermediate#")
PROETHICA_CASES = Namespace("http://proethica.org/ontology/cases#")
CASE_NS_TEMPLATE = "http://proethica.org/ontology/case/{case_id}#"

# The Step-4 types whose literals are owned by the row (re-emitted whole at
# every commit).
STEP4_ANALYSIS_TYPES = frozenset({
    'precedent_case_reference', 'code_provision_reference',
    'canonical_decision_point', 'resolution_pattern', 'question_emergence',
    'causal_normative_link', 'ethical_question', 'ethical_conclusion',
})


def is_step4_analysis_type(extraction_type: str) -> bool:
    return (extraction_type or '') in STEP4_ANALYSIS_TYPES


def strip_analysis_literals(g: Graph, uri: URIRef) -> int:
    """Remove every (uri, p, Literal) triple. Returns the number removed. The
    emitter re-adds the label, the typed provenance and the row's own literals
    right after, so the individual ends up carrying the current row only."""
    removed = 0
    for p, o in list(g.predicate_objects(uri)):
        if isinstance(o, Literal):
            g.remove((uri, p, o))
            removed += 1
    return removed


def analysis_individual_uri(case_id: int, entity, rdf_data: Dict) -> URIRef:
    """The URI the commit paths mint for a Step-4 analysis row (same rules as
    ``_commit_individuals_to_case_ontology`` / ``_write_case_ttl_fresh``)."""
    case_ns = Namespace(CASE_NS_TEMPLATE.format(case_id=case_id))
    etype = getattr(entity, 'extraction_type', '') or ''
    rdf_data = rdf_data or {}
    if etype == 'canonical_decision_point' and rdf_data.get('focus_id'):
        label = rdf_data['focus_id']
    elif etype == 'ethical_question' and rdf_data.get('questionNumber'):
        label = f"Question_{rdf_data['questionNumber']}"
    elif etype == 'ethical_conclusion' and rdf_data.get('conclusionNumber'):
        label = f"Conclusion_{rdf_data['conclusionNumber']}"
    else:
        label = getattr(entity, 'entity_label', None) or 'UnknownIndividual'
    return case_ns[naming.safe_label(label)]


def expected_literals(entity, rdf_data: Dict) -> List[Tuple[URIRef, Literal]]:
    """The literals that define a Step-4 analysis row in the graph: the ones
    the commit emits from the row's own fields and whose staleness the case 8
    review found. A row with none of these fields yields an empty list (only
    its presence is checked)."""
    etype = getattr(entity, 'extraction_type', '') or ''
    rdf_data = rdf_data or {}
    out: List[Tuple[URIRef, Literal]] = []
    definition = getattr(entity, 'entity_definition', None)
    if etype == 'precedent_case_reference':
        if rdf_data.get('citationType'):
            out.append((PROETHICA_CASES['citationType'], Literal(rdf_data['citationType'])))
        if definition and not rdf_data.get('definitions'):
            out.append((SKOS.definition, Literal(definition)))
    elif etype == 'canonical_decision_point':
        if rdf_data.get('board_resolution'):
            out.append((PROETHICA['boardResolution'], Literal(rdf_data['board_resolution'])))
        if rdf_data.get('decision_question'):
            out.append((PROETHICA['decisionQuestion'], Literal(rdf_data['decision_question'])))
    elif etype == 'ethical_conclusion':
        if rdf_data.get('conclusionText'):
            out.append((PROETHICA['conclusionText'], Literal(rdf_data['conclusionText'])))
    elif etype == 'ethical_question':
        if rdf_data.get('questionText'):
            out.append((PROETHICA['questionText'], Literal(rdf_data['questionText'])))
    elif etype in ('resolution_pattern', 'question_emergence', 'causal_normative_link',
                   'code_provision_reference'):
        if definition and not rdf_data.get('definitions'):
            out.append((SKOS.definition, Literal(definition)))
    return out


def stale_analysis_rows(g: Graph, case_id: int, entities: Iterable[Any],
                        rdf_data_of=None) -> List[Tuple[Any, str]]:
    """(row, reason) for every Step-4 analysis row whose individual is absent
    from ``g`` or whose defining literals are not the graph's. Rows of other
    types are never reported."""
    stale: List[Tuple[Any, str]] = []
    for entity in entities:
        etype = getattr(entity, 'extraction_type', '') or ''
        if not is_step4_analysis_type(etype):
            continue
        rdf_data = rdf_data_of(entity) if rdf_data_of else (getattr(entity, 'rdf_json_ld', None) or {})
        uri = analysis_individual_uri(case_id, entity, rdf_data)
        if (uri, RDF.type, OWL.NamedIndividual) not in g:
            stale.append((entity, f"{uri.rsplit('#', 1)[-1]} is not in the committed graph"))
            continue
        for pred, lit in expected_literals(entity, rdf_data):
            if (uri, pred, lit) not in g:
                current = [str(o) for o in g.objects(uri, pred)]
                stale.append((entity, f"{uri.rsplit('#', 1)[-1]} {pred.rsplit('#', 1)[-1]}: the row "
                                      f"carries {str(lit)[:80]!r}, the graph carries {current[:2]!r}"))
                break
    return stale
