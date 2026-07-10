"""Single source for Step-4 question/conclusion reference lists.

Pre-rebuild checklist item 2 (2026-07-10): the synthesis store previously
keyed questions and conclusions POSITIONALLY (case-<id>#Q<k> / #C<k>, the
k-th row of an unordered enumeration), which five call sites each minted
independently and which downstream edge grounding could only resolve by
re-running the enumeration and verifying carried text. This module is the
one place reference lists are built:

- uri: the COMMITTED-URI key ``case-<id>#Question_<questionNumber>`` /
  ``#Conclusion_<conclusionNumber>`` whenever the row carries its number
  (every bridge-committed row does), so a stored reference resolves to the
  committed individual directly. Rows without a number fall back to
  entity_uri, then to the legacy positional key -- analysis_edges keeps a
  positional fallback for exactly those.
- text: carried alongside the uri so every stored reference stays
  text-verifiable (never-fabricate).

Rows are enumerated in id order, matching the historical enumeration, so
legacy positional keys remain interpretable.
"""
from typing import Dict, List, Optional


def _ref(case_id: int, row, k: int, kind: str) -> Dict:
    d = row.rdf_json_ld or {}
    if kind == 'Q':
        numkey, frag, poskey, textkey = 'questionNumber', 'Question_', 'Q', 'questionText'
    else:
        numkey, frag, poskey, textkey = 'conclusionNumber', 'Conclusion_', 'C', 'conclusionText'
    n = d.get(numkey)
    if n:
        uri = f"case-{case_id}#{frag}{int(n)}"
    else:
        uri = row.entity_uri or f"case-{case_id}#{poskey}{k}"
    return {
        'uri': uri,
        'label': row.entity_label,
        'text': d.get(textkey) or row.entity_definition or row.entity_label or '',
        'number': int(n) if n else None,
    }


def _rows(case_id: int, etype: str):
    from app.models import TemporaryRDFStorage
    return (TemporaryRDFStorage.query
            .filter_by(case_id=case_id, extraction_type=etype)
            .order_by(TemporaryRDFStorage.id).all())


def question_refs(case_id: int, rows: Optional[list] = None) -> List[Dict]:
    rows = rows if rows is not None else _rows(case_id, 'ethical_question')
    return [_ref(case_id, r, i + 1, 'Q') for i, r in enumerate(rows)]


def conclusion_refs(case_id: int, rows: Optional[list] = None) -> List[Dict]:
    rows = rows if rows is not None else _rows(case_id, 'ethical_conclusion')
    return [_ref(case_id, r, i + 1, 'C') for i, r in enumerate(rows)]
