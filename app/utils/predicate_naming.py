"""Single source of truth for snake_case / spaced -> camelCase RDF predicate
local names (R3, 2026-06-04).

Two independent converters previously existed: `extraction_graph._to_camel_case`
(applied at storage, when building the rdf_json_ld props) and
`ontserve_commit_service._camelCase` (applied at commit, for property local names).
They were equivalent for real snake_case field names but were free to drift, and a
change to one would silently desync the other plus the edge readers that hardcode
the resulting camelCase predicate names (resource_edges, participant_edges,
obligation_edges, rpo_edges, defeasibility_pipeline). Both now delegate here, so the
writer and the readers share one definition. A guard test pins the contract
(tests/unit/test_predicate_naming.py).

Idempotent on an already-camelCase single token: the generic `properties` keys
arrive already camelCase (roleClass, obligationStatement, activePeriod) and must be
preserved, not lowercased -- lowercasing them is the predicate-mangling bug
(`activePeriod` -> `activeperiod`). A token with no separator is returned unchanged;
only multi-word input (snake_case or spaced) is folded.
"""


def to_camel_case(text: str) -> str:
    """snake_case / spaced -> camelCase; already-camel single tokens pass through."""
    if '_' not in text and ' ' not in text:
        return text
    words = text.replace('_', ' ').split()
    if not words:
        return text
    result = words[0].lower()
    for word in words[1:]:
        result += word.capitalize()
    return result
