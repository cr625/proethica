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


def key_aliases(refs: List[Dict], kind: str) -> Dict[str, str]:
    """alias key -> canonical key, over an id-ordered reference list.

    Any join between STORED Step-4 reference keys (question_uri /
    conclusion_uri / aligned_*_uri, possibly written under the legacy
    positional convention) and an in-memory reference list must normalize
    BOTH sides through this map, or a mixed-generation store silently stops
    joining (c422755 review, major finding: the DP-synthesis and Step-5
    joins used exact string equality). Aliases cover the canonical
    committed-URI form and the legacy positional form at the same list
    position; unknown keys pass through unchanged via ``.get(k, k)``."""
    out: Dict[str, str] = {}
    pos = 'Q' if kind == 'Q' else 'C'
    for k, ref in enumerate(refs, 1):
        canon = ref.get('uri') or ''
        if not canon or '#' not in canon:
            continue
        out[canon] = canon
        out[f"{canon.split('#')[0]}#{pos}{k}"] = canon
    return out


# Board-authored rows are numbered below this base; generated analysis rows
# start at the category offsets (questions 101/201/301/401, conclusions
# 101/201/301 -- the number_bases of question_analyzer / conclusion_analyzer).
GENERATED_NUMBER_BASE = 100

_GENERATED_TYPES = frozenset({
    'implicit', 'principle_tension', 'theoretical', 'counterfactual',
    'analytical_extension', 'question_response', 'principle_synthesis',
})


def _number_of(ref: Dict, kind: str):
    keys = (('number', 'question_number', 'questionNumber') if kind == 'Q'
            else ('number', 'conclusion_number', 'conclusionNumber'))
    for key in keys:
        v = ref.get(key)
        if v not in (None, ''):
            try:
                return int(v)
            except (TypeError, ValueError):
                return None
    return None


def is_board_explicit(ref: Dict, kind: str = 'C') -> bool:
    """Whether a question (kind 'Q') or conclusion (kind 'C') dict is a Board
    record rather than Step-4 generated analysis.

    The explicit type wins when the dict carries one (question_type /
    questionType / conclusion_type / conclusionType); a dict without a
    decisive type falls back to the numbering convention (Board rows are
    numbered below GENERATED_NUMBER_BASE). A dict with neither is NOT Board:
    the board_resolution, board-choice and Board-heading paths must never
    treat unattributed text as the Board's (case 8 review, findings B, C, E).
    """
    if not isinstance(ref, dict):
        return False
    type_keys = (('question_type', 'questionType') if kind == 'Q'
                 else ('conclusion_type', 'conclusionType'))
    for key in type_keys:
        t = ref.get(key)
        if t:
            t = str(t).strip().lower()
            if t == 'board_explicit':
                return True
            if t in _GENERATED_TYPES:
                return False
            # A legacy or placeholder type ('unknown', 'board') decides by number.
            break
    n = _number_of(ref, kind)
    return n is not None and n < GENERATED_NUMBER_BASE


def board_explicit_only(refs: List[Dict], kind: str = 'C') -> List[Dict]:
    return [r for r in (refs or []) if is_board_explicit(r, kind)]


def generated_only(refs: List[Dict], kind: str = 'C') -> List[Dict]:
    return [r for r in (refs or []) if not is_board_explicit(r, kind)]


def ref_type_label(ref: Dict, kind: str = 'C') -> str:
    """Display tag for a generated record: its category when known, else
    'generated'."""
    type_keys = (('question_type', 'questionType') if kind == 'Q'
                 else ('conclusion_type', 'conclusionType'))
    for key in type_keys:
        t = ref.get(key)
        if t and str(t).strip().lower() in _GENERATED_TYPES:
            return str(t).strip().lower()
    return 'generated'
