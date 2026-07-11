"""One normalization for NSPE provision codes.

Raw citations arrive in many spellings: "I.1", "I.1.", "NSPE I.1", "Section II.1.a",
"II.1.a.", "I.1 Public Welfare Paramount" (code + title). The 2026-07-08 Provisions
census found 24 of 42 distinct codes carried more than one raw spelling across the
gold corpus, and every consumer (Flow-graph joins, popover lookups, A8 resolution,
decision-point backing labels) normalized its own way or not at all. This module is
the single Python-side rule; `normalizeProvisionCode` in step4-flow-graph.js is the
JS mirror.

Canonical form: the GuidelineSection casing -- Roman numerals uppercase, subsection
letters uppercase, no trailing dot ("II.1.A"), or "Preamble". Historical vocabulary
("Canon 15", "Rule 13" from pre-2007 cases) does not normalize to a modern code and
returns None; the citation-provenance annotation is the designed carrier for those.
"""
import re

_PREFIX = re.compile(r'^\s*(?:NSPE\s+)?(?:Section\s+)?(?:Code\s+)?', re.IGNORECASE)
_CODE = re.compile(r'^(Preamble|[IVXivx]+(?:\.\d+)?(?:\.[A-Za-z])?)')


def normalize_provision_code(raw) -> str | None:
    """Normalize a raw provision citation to canonical form, or None when the
    value is not a modern NSPE code (duty names, historical Canons/Rules)."""
    if not raw:
        return None
    text = _PREFIX.sub('', str(raw).strip())
    m = _CODE.match(text)
    if not m:
        return None
    code = m.group(1)
    if code.lower() == 'preamble':
        return 'Preamble'
    return code.upper().rstrip('.')


def is_provision_code(raw) -> bool:
    """True when the value cites a modern NSPE provision (possibly with a
    trailing title, e.g. 'I.1 Public Welfare Paramount')."""
    return normalize_provision_code(raw) is not None


def nspe_provision_fragment(raw) -> str | None:
    """URI local fragment for a provision code in the OntServe 'NSPE Code of
    Ethics' ontology (nspe# namespace): dots become underscores and the
    subsection letter is lowercase, matching the individuals' minting
    ('III.1.A' -> 'III_1_a'; 'Preamble' -> 'Preamble'). The entity page is
    {ONTSERVE_WEB_URL}/entity/NSPE Code of Ethics/{fragment}.
    tests/unit/test_provision_references.py verifies the rule round-trips
    against every dct:identifier in the co-located NSPE TTL."""
    code = normalize_provision_code(raw)
    if code is None:
        return None
    if code == 'Preamble':
        return 'Preamble'
    parts = code.split('.')
    if len(parts) == 3:
        parts[2] = parts[2].lower()
    return '_'.join(parts)


def provision_display_code(raw) -> str | None:
    """USER-FACING form of a provision code, matching the NSPE ontology's
    dct:identifier casing exactly (Roman numerals uppercase, subsection
    letter lowercase, no trailing dot: 'II.3.a'). Derived from
    nspe_provision_fragment so display text, entity-page URIs, and the
    ontology identifiers cannot drift apart (2026-07-10 alignment audit:
    the tab showed the raw LLM spelling 'II.3.a.' while OntServe showed the
    identifier 'II.3.a', and the internal join canonical is 'II.3.A').
    None when the value is not a modern NSPE code (historical Canons/Rules
    keep their raw spelling)."""
    frag = nspe_provision_fragment(raw)
    return frag.replace('_', '.') if frag else None
