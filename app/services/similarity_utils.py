"""Shared similarity helpers.

Houses the pure-Python cosine used by callers that operate on plain
``List[float]`` embeddings and want the raw (unclamped) cosine value.

Scope note: this is deliberately ONLY the pure-Python, unclamped variant.
The numpy-based cosines in ``section_embedding_service``,
``precedent/similarity_service`` and ``ttl_triple_association/embedding_service``
differ in load-bearing ways (clamping to [0, 1], None handling,
length-mismatch semantics, pre-normalization) and are intentionally NOT
routed through here, because doing so would change their results.
"""

from typing import List


def cosine_similarity_list(a: List[float], b: List[float]) -> float:
    """Raw cosine similarity between two equal-length float lists.

    Returns 0.0 for empty inputs or a zero-norm vector. The result is the
    unclamped cosine (it may be negative); callers that need a [0, 1] score
    must clamp themselves. When the inputs differ in length, only the leading
    ``min(len(a), len(b))`` components are compared (matching the prior
    hand-rolled implementations).
    """
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    dot = sum(a[i] * b[i] for i in range(n))
    norm_a = sum(a[i] * a[i] for i in range(n)) ** 0.5
    norm_b = sum(b[i] * b[i] for i in range(n)) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
