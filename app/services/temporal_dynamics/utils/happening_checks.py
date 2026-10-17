"""Post-parse checks on Step-3 happenings (actions and events), case-8 review lesson L8.

* ``classify_action_modality`` / ``apply_action_modality``: an Action whose text references
  are all Board normative sentences from the discussion ("cannot ethically acquiesce", "must
  not", "would not be ethical") is a PRESCRIBED act (what the Board says the agent must or must
  not do), not a PERFORMED one. Case 8 stored the Board's "cannot ethically acquiesce" as a
  performed Action with temporal_marker "Present, unresolved endpoint".
* ``validate_fluent_links``: initiates / terminates entries are validated against the case's
  State labels (the closed list the prompt offers) and an entry equal to another Event or
  Action label is rejected. Case 8 gave an Event label where a State label was required.

Pure functions over the plain dicts the LangGraph stages carry; no DB, no LLM.
"""
from __future__ import annotations

import logging
import re
from typing import Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)

MODALITIES = ('performed', 'prescribed')

# A Board normative sentence: the Board stating what an agent must, must not, or cannot
# ethically do, or that a course would not be ethical.
BOARD_NORMATIVE_RE = re.compile(
    r"\b(?:cannot|can not|could not|may not|must not|should not|shall not|is not permitted to|"
    r"would not be (?:ethical|permitted|appropriate|consistent)|would be unethical|"
    r"is (?:not )?ethical(?:ly)?(?: (?:obligated|required|permitted))? to|"
    r"was not ethical|is unethical|has (?:an|the) (?:ethical )?(?:obligation|duty) to|"
    r"is (?:ethically )?(?:obligated|required|bound) to|ought to|should (?:have )?)\b",
    re.IGNORECASE,
)


def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _in_text(quote: str, text: str) -> bool:
    """Token-level containment (whitespace- and punctuation-insensitive)."""
    q = " ".join(_tokens(quote))
    return bool(q) and f" {q} " in f" {' '.join(_tokens(text))} "


def classify_action_modality(action: Dict, discussion_text: str = "") -> str:
    """'prescribed' when every text reference of the action is a Board normative sentence from
    the discussion, else the model's own modality (default 'performed')."""
    explicit = str(action.get("modality") or "").strip().lower()
    base = explicit if explicit in MODALITIES else "performed"
    refs = [str(r).strip() for r in (action.get("text_references") or []) if str(r).strip()]
    if not refs:
        return base
    from_discussion = (str(action.get("source_section") or "").strip().lower() == "discussion"
                       or (bool(discussion_text) and all(_in_text(r, discussion_text) for r in refs)))
    if from_discussion and all(BOARD_NORMATIVE_RE.search(r) for r in refs):
        return "prescribed"
    return base


def apply_action_modality(actions: List[Dict], discussion_text: str = "") -> List[Dict]:
    """Set ``modality`` on every action (in place); returns the list."""
    for a in actions or []:
        if not isinstance(a, dict):
            continue
        modality = classify_action_modality(a, discussion_text)
        if modality != str(a.get("modality") or "").strip().lower():
            logger.info("[happening_checks] action %r modality %s", a.get("label"), modality)
        a["modality"] = modality
    return actions


def _norm_state(label: str) -> str:
    """Normalize a state label for comparison: case, separators, and an optional trailing
    'State' head noun ("Public Safety Risk" == "Public Safety Risk State")."""
    s = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", str(label or ""))
    s = re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
    s = re.sub(r"\s+state$", "", s)
    return s


def validate_fluent_links(happenings: List[Dict], state_labels: Optional[Iterable[str]],
                          other_labels: Optional[Iterable[str]] = None,
                          kind: str = "happening") -> List[Dict]:
    """Drop invalid initiates / terminates entries in place and return a report of the drops.

    An entry is dropped when it equals (normalized) another Event or Action label in
    ``other_labels`` (a happening is not a fluent), or, when ``state_labels`` is non-empty, when
    it matches none of the case State labels (the closed list). With an empty closed list only
    the happening-label rejection applies."""
    states = {_norm_state(s) for s in (state_labels or ()) if str(s).strip()}
    others = {_norm_state(o) for o in (other_labels or ()) if str(o).strip()}
    report: List[Dict] = []
    for h in happenings or []:
        if not isinstance(h, dict):
            continue
        own = _norm_state(h.get("label", ""))
        for field in ("initiates", "terminates"):
            vals = h.get(field)
            if not isinstance(vals, list) or not vals:
                continue
            kept, dropped = [], []
            for v in vals:
                n = _norm_state(v)
                if not n:
                    continue
                if n in others and n != own or (n == own):
                    dropped.append((v, "names a happening, not a state"))
                elif states and n not in states:
                    dropped.append((v, "not a State label of this case"))
                else:
                    kept.append(v)
            if dropped:
                h[field] = kept
                for v, why in dropped:
                    report.append({"kind": kind, "label": h.get("label"), "field": field,
                                   "value": v, "reason": why})
                    logger.info("[happening_checks] %s %r: %s entry %r dropped (%s)",
                                kind, h.get("label"), field, v, why)
    return report


def state_label_block(state_labels: Optional[Iterable[str]]) -> str:
    """The closed-list prompt block for initiates / terminates, or '' when no labels are known."""
    labels = [str(s).strip() for s in (state_labels or ()) if str(s).strip()]
    if not labels:
        return ""
    lines = ["CASE STATE LABELS (the closed list for initiates / terminates):"]
    lines += [f"- {s}" for s in labels]
    lines.append("initiates and terminates MUST name labels from this list exactly. A label absent from "
                 "the list, or equal to an Action or Event label, is invalid and is dropped.")
    return "\n".join(lines)


def finalize_actions(actions: List[Dict], discussion_text: str = "",
                     state_labels: Optional[Iterable[str]] = None) -> Tuple[List[Dict], List[Dict]]:
    """Modality routing plus fluent-link validation for a parsed action batch."""
    apply_action_modality(actions, discussion_text)
    labels = [a.get("label", "") for a in actions if isinstance(a, dict)]
    report = validate_fluent_links(actions, state_labels, other_labels=labels, kind="action")
    return actions, report


def finalize_events(events: List[Dict], actions: Optional[List[Dict]] = None,
                    state_labels: Optional[Iterable[str]] = None) -> Tuple[List[Dict], List[Dict]]:
    """Fluent-link validation for a parsed event batch (against the action and event labels)."""
    labels = [a.get("label", "") for a in (actions or []) if isinstance(a, dict)]
    labels += [e.get("label", "") for e in events if isinstance(e, dict)]
    report = validate_fluent_links(events, state_labels, other_labels=labels, kind="event")
    return events, report
