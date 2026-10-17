"""
Match-link policy shared by the class and individual commit paths (case-8
review, lessons L3 and L4).

The matcher records its decision on every row (``match_decision``:
``matches_existing``, ``matched_uri``, ``confidence``). The commit honored
that decision at any confidence: ``_matched_class_override`` retyped an
individual to a class matched at 0.75 ("matched to parent with medium
confidence"), while ``class_commit`` minted PublicSafetyObligation although
its row had matched SafetyObligation at 0.95. One threshold now governs both
sides: a match at or above the link threshold is reuse (the class is not
minted, the individual is typed to the matched class), a match below it keeps
the minted class.

The default is the matcher's auto-link band minimum (``HIGH_BAND_MIN``, 0.85).
``PROETHICA_MATCH_LINK_THRESHOLD`` overrides it for a deployment, and the
commit service accepts a per-instance override (``match_link_threshold``).
"""

import logging
import os
from typing import Any, Dict, Optional

from app.services.extraction.entity_matcher import HIGH_BAND_MIN

logger = logging.getLogger(__name__)

DEFAULT_MATCH_LINK_THRESHOLD = HIGH_BAND_MIN
THRESHOLD_ENV_VAR = 'PROETHICA_MATCH_LINK_THRESHOLD'


def match_link_threshold(override: Optional[float] = None) -> float:
    """The confidence at or above which a matcher decision counts as a link.

    Resolution order: the explicit ``override`` (a commit-service instance
    attribute), the ``PROETHICA_MATCH_LINK_THRESHOLD`` environment variable,
    the matcher's auto-link band minimum.
    """
    if override is not None:
        return float(override)
    raw = os.environ.get(THRESHOLD_ENV_VAR)
    if raw:
        try:
            return float(raw)
        except ValueError:
            logger.warning("%s=%r is not a number; using the default %.2f",
                           THRESHOLD_ENV_VAR, raw, DEFAULT_MATCH_LINK_THRESHOLD)
    return DEFAULT_MATCH_LINK_THRESHOLD


def match_confidence(match_decision: Optional[Dict[str, Any]]) -> Optional[float]:
    """The numeric confidence of a match decision, or None when absent or
    unparseable."""
    if not isinstance(match_decision, dict):
        return None
    value = match_decision.get('confidence')
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def matched_local_name(matched_uri: Any) -> str:
    """Local name of a matched class IRI ('' when none)."""
    if not matched_uri:
        return ''
    return str(matched_uri).rsplit('#', 1)[-1].rsplit('/', 1)[-1]


def linked_existing_class(rdf_data: Optional[Dict[str, Any]], threshold: float) -> Optional[str]:
    """The local name of the existing class a row is LINKED to: the matcher
    said ``matches_existing`` with a ``matched_uri`` and a confidence at or
    above ``threshold``. None when the row is unmatched, below the threshold,
    or carries no confidence (the default decision carries 0.0)."""
    md = (rdf_data or {}).get('match_decision') if isinstance(rdf_data, dict) else None
    if not isinstance(md, dict) or not md.get('matches_existing'):
        return None
    local = matched_local_name(md.get('matched_uri'))
    if not local:
        return None
    confidence = match_confidence(md)
    if confidence is None or confidence < threshold:
        return None
    return local
