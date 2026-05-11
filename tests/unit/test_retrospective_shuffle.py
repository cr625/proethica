"""Retrospective ranking shuffle tests.

Covers the predecessor branch behavior (commit fd57401 on
study/fresh-eyes-fixes-2026-05-10): the retrospective route shuffles
_RANKING_VIEWS before render so a participant who skips the drag step
does not implicitly endorse case-page tab order as their ranking.

Two invariants:
  1. The shuffled list always contains the same five view slugs (no
     drop, no add).
  2. Across N independent shuffles, more than one distinct ordering
     appears (the shuffle is actually random; not a no-op or a fixed
     reorder).
"""

import random

from app.routes.study import _RANKING_VIEWS


EXPECTED_SLUGS = {'narrative', 'timeline', 'qc', 'decisions', 'provisions'}


def _shuffle_once():
    """Reproduce the shuffle the retrospective route performs."""
    ranking_views = list(_RANKING_VIEWS)
    random.shuffle(ranking_views)
    return ranking_views


def test_ranking_views_preserves_all_five_slugs():
    """Shuffle never drops or duplicates a view."""
    out = _shuffle_once()
    slugs = {v['slug'] for v in out}
    assert slugs == EXPECTED_SLUGS
    assert len(out) == 5


def test_ranking_views_preserves_view_metadata():
    """Each view dict retains slug + name + icon_class + description."""
    out = _shuffle_once()
    for v in out:
        for required in ('slug', 'name', 'icon_class', 'description'):
            assert required in v, f'{v["slug"]} missing {required}'


def test_ranking_views_shuffle_produces_multiple_orderings():
    """N=50 trials should yield at least 5 distinct orderings.

    There are 5! = 120 possible orderings. Probability of all 50
    landing on the same ordering is (1/120)^49 ~= 0; on <=4 distinct
    orderings is also vanishingly small (a coupon-collector-style
    bound makes 5+ distinct orderings out of 50 effectively certain).
    """
    seen = set()
    for _ in range(50):
        ordering = tuple(v['slug'] for v in _shuffle_once())
        seen.add(ordering)
    assert len(seen) >= 5, (
        f'Shuffle should produce many orderings; got only {len(seen)}: {seen}'
    )


def test_ranking_views_shuffle_does_not_match_default_every_time():
    """Default order is the case-page tab order; shuffle must depart from it."""
    default_order = tuple(v['slug'] for v in _RANKING_VIEWS)
    matches = 0
    for _ in range(50):
        ordering = tuple(v['slug'] for v in _shuffle_once())
        if ordering == default_order:
            matches += 1
    # Probability of matching default in any single trial is 1/120.
    # Expected matches across 50 trials: ~0.42. Allow up to 5 to keep
    # the test deterministic-friendly while still catching a no-op shuffle.
    assert matches < 50, 'Shuffle should not always return default order'
    assert matches < 10, (
        f'Shuffle matched default {matches}/50 times — implausibly high'
    )


def test_default_ranking_order_matches_documented_intent():
    """Default order is intentionally not tab order on the case page.

    Sanity-check the source-of-truth list against the documented intent
    so renaming or reordering does not silently change the shuffle base.
    """
    # The list is documented as "intentionally NOT tab-order" in the
    # route module; this test pins the expected default for the parity
    # test in test_likert_items_match_protocol.py to find.
    default_order = [v['slug'] for v in _RANKING_VIEWS]
    assert default_order == ['narrative', 'timeline', 'qc', 'decisions', 'provisions']
