"""Sample variable providers for the SHARED prompts.

A cross-cutting prompt (the Individual/type filter, splitter, merge, edge passes) has no case context,
so the prompt editor's Preview / Test tabs cannot resolve its variables from a case the way the main
per-component prompts do. Each provider here returns that prompt's Jinja variables filled with a small,
realistic sample, so Preview shows the prompt filled in and Test runs it live. Add a provider when
migrating another shared prompt to an editable template.
"""
from __future__ import annotations

from typing import Callable, Dict, Optional


def _individual_filter_sample() -> Dict[str, str]:
    """Two ambiguous resource individuals: a genuine artifact (keep) and a type masquerading as an
    instance (drop). Criteria come from the live CRITERIA registry so the sample tracks the code."""
    from app.services.extraction.individual_type_filter import CRITERIA
    crit = CRITERIA['resources']
    items = (
        '[0] individual: "NSPE Code of Ethics"\n'
        '    declared class: "Professional Code"\n'
        '    detail: "the code of ethics cited throughout the case"\n'
        '    signals: none\n\n'
        '[1] individual: "Peer Review Notification Standard Instance"\n'
        '    declared class: "Collegial Notification Before Reporting Standard"\n'
        '    detail: "a general norm stated in the discussion"\n'
        '    signals: LABEL IS ESSENTIALLY ITS CLASS (likely a type, not an instance)'
    )
    return {
        'component': crit.component,
        'unit': crit.unit,
        'keep_examples': crit.keep_examples,
        'drop_kinds': crit.drop_kinds,
        'items': items,
    }


# Registry keyed by the shared prompt's concept_type (matches the seeded template row).
_PROVIDERS: Dict[str, Callable[[], Dict[str, str]]] = {
    'individual_filter': _individual_filter_sample,
}


def is_shared_prompt(concept_type: str) -> bool:
    """True if `concept_type` is a shared prompt with a registered sample provider."""
    return concept_type in _PROVIDERS


def shared_prompt_sample(concept_type: str) -> Optional[Dict[str, str]]:
    """The sample Jinja variables for a shared prompt's editable template, or None if it is not a
    registered shared prompt."""
    provider = _PROVIDERS.get(concept_type)
    return provider() if provider else None
