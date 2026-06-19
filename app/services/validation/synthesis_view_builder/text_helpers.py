"""
Synthesis View Builder -- shared text-matching helpers.

Module-level citation regex, stopword set, and tokenizer used by both the
timeline view (builder.py) and the narrative view (narrative_view.py). Split out
so the two mixins/modules share one definition. `_CITATION_RE` is re-exported
from the package __init__ for callers that import it directly.
"""

import re


# A reference to a prior BER opinion, e.g. "Case 76-4", "BER Case 19-3",
# "Case 20-1". Matched ANYWHERE in a label, not just at the start, because the
# extractor emits the citation as a prefix ("BER Case 04-11 Engineer ..."), a
# suffix ("Engineer Intern BER Case 20-1"), or mid-label ("Engineer A BER Case
# 19-3 Standards Chair"). The "BER" token is optional; the "Case NN-N(N)" core
# carries the signal. Present-case people never carry this token.
_CITATION_RE = re.compile(r'\b(?:BER\s+)?Case\s+\d{2}-\d{1,2}\b', re.IGNORECASE)

# Tokens too generic to disambiguate one actor from another when matching a
# Step-3 timeline agent to a role-derived narrative character. Standard English
# stopwords plus connective noise left in eventRoleContext / professional_position.
_MATCH_STOPWORDS = frozenset({
    'a', 'an', 'and', 'or', 'the', 'of', 'to', 'in', 'on', 'for', 'with',
    'as', 'at', 'by', 'from', 'who', 'whose', 'while', 'both', 'his', 'her',
    'their', 'its', 'this', 'that', 'under', 'is', 'are', 'be', 'but', 'not',
    'no', 'all', 'any', 'some', 'such', 'than', 'then', 'also', 'may', 'will',
    'represented', 'body', 'unnamed', 'multiple', 'single', 'general',
})


def _match_tokens(text: str) -> set:
    """Lowercased alphanumeric tokens of `text`, minus generic stopwords.

    Hyphenated compounds are split (``part-time`` -> ``part``, ``time``) so a
    timeline agent's ``eventRoleContext`` and a character's label/position align
    on the same atoms. Single characters are dropped except a lone uppercase
    letter used as an NSPE disambiguator (``A`` in "Engineer A")."""
    if not text:
        return set()
    tokens = set()
    for raw in re.split(r'[^A-Za-z0-9]+', text):
        if not raw:
            continue
        if len(raw) == 1 and not raw.isalpha():
            continue
        low = raw.lower()
        if low in _MATCH_STOPWORDS:
            continue
        if len(low) == 1 and not raw.isupper():
            continue
        tokens.add(low)
    return tokens
