"""Unit tests for the consolidated EntityMatcher component.

DB/LLM-free: the corpus is a fake list of CandidateRecord and the embedding
tier is a fake injected callable. Verifies every cascade tier, the category
guard, the band cutoffs, normalization, and the below-floor None case.
"""

import pytest

from app.services.extraction.entity_matcher import (
    Band,
    CandidateRecord,
    EntityMatcher,
    MatchResult,
    band_for,
    category_compatible,
    normalize_label,
    semantic_type_markers,
)


# ---------------------------------------------------------------------------
# normalize_label
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("Structural Engineer", "structural engineer"),     # lowercase
    ("  Structural Engineer  ", "structural engineer"),  # strip
    ("Engineer (Present Case)", "engineer"),             # trailing parenthetical
    ("Public  Safety   Obligation", "public safety obligation"),  # collapse ws
    ("  Role (X)  ", "role"),                             # combined
    ("", ""),                                             # empty
    (None, ""),                                           # None-safe
])
def test_normalize_label(raw, expected):
    assert normalize_label(raw) == expected


# ---------------------------------------------------------------------------
# band_for cutoffs
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("score, band", [
    (1.0, Band.HIGH),
    (0.85, Band.HIGH),     # boundary inclusive
    (0.8499, Band.MEDIUM),
    (0.70, Band.MEDIUM),   # boundary inclusive
    (0.6999, Band.NONE),
    (0.0, Band.NONE),
])
def test_band_for_cutoffs(score, band):
    assert band_for(score) == band


# ---------------------------------------------------------------------------
# semantic_type_markers / category_compatible (URI-substring guard)
# ---------------------------------------------------------------------------

def test_semantic_type_markers_plural_and_fallback():
    assert semantic_type_markers("roles") == ["Role"]
    assert semantic_type_markers("role") == ["Role"]
    # Unknown type -> title-cased fallback.
    assert semantic_type_markers("widget") == ["Widget"]
    assert semantic_type_markers(None) == []


def test_category_compatible_uri_marker_guard():
    role_uri = "http://proethica.org/ontology/intermediate#StructuralEngineerRole"
    principle_uri = "http://proethica.org/ontology/intermediate#PublicSafetyPrinciple"
    # Role candidate matches a Role-marked URI.
    assert category_compatible("roles", role_uri) is True
    # Role candidate must NOT match a Principle-marked URI.
    assert category_compatible("roles", principle_uri) is False
    # No candidate category -> no constraint.
    assert category_compatible(None, principle_uri) is True


def test_category_compatible_chain_resolver_authoritative():
    # A URI whose name says "Obligation" but whose curated chain resolves to
    # Principle must be rejected for an Obligation candidate (the chain wins).
    misleading_uri = "http://proethica.org/ontology/intermediate#SomeObligation"

    def resolver(target):
        return "Principle"  # authoritative chain says Principle

    assert category_compatible(
        "obligations", misleading_uri, chain_resolver=resolver
    ) is False
    # Same chain category -> compatible.
    assert category_compatible(
        "principles", misleading_uri, chain_resolver=resolver
    ) is True


def test_category_compatible_chain_unresolved_falls_back_to_marker():
    role_uri = "http://proethica.org/ontology/intermediate#DesignEngineerRole"

    def resolver(target):
        return None  # unknown to curated tiers

    # Resolver gives up -> marker guard applies; Role URI is fine for a Role.
    assert category_compatible("roles", role_uri, chain_resolver=resolver) is True
    # And a Principle candidate still fails the marker fallback on a Role URI.
    assert category_compatible("principles", role_uri, chain_resolver=resolver) is False


# ---------------------------------------------------------------------------
# Cascade fixtures
# ---------------------------------------------------------------------------

ROLE_URI = "http://proethica.org/ontology/intermediate#EngineerRole"
DESIGN_ROLE_URI = "http://proethica.org/ontology/intermediate#DesignEngineerRole"
PRINCIPLE_URI = "http://proethica.org/ontology/intermediate#PublicSafetyPrinciple"


def _corpus():
    return [
        CandidateRecord(uri=ROLE_URI, label="Engineer Role", category="roles"),
        CandidateRecord(uri=DESIGN_ROLE_URI, label="Design Engineer Role", category="roles"),
        CandidateRecord(uri=PRINCIPLE_URI, label="Public Safety", category="principles"),
    ]


# ---------------------------------------------------------------------------
# Tier 1: exact
# ---------------------------------------------------------------------------

def test_exact_match():
    m = EntityMatcher()
    res = m.match("engineer role", "roles", corpus=_corpus())
    assert isinstance(res, MatchResult)
    assert res.uri == ROLE_URI
    assert res.method == "exact"
    assert res.score == 1.0
    assert res.band == Band.HIGH


def test_exact_match_normalizes_parenthetical_and_case():
    m = EntityMatcher()
    res = m.match("Engineer Role (Present Case)", "roles", corpus=_corpus())
    assert res is not None
    assert res.method == "exact"
    assert res.uri == ROLE_URI


# ---------------------------------------------------------------------------
# Tier 2: substring
# ---------------------------------------------------------------------------

def test_substring_match():
    m = EntityMatcher()
    # "engineer" is contained in "Engineer Role" -> substring tier, 0.87.
    res = m.match("Engineer", "roles", corpus=_corpus())
    assert res is not None
    assert res.method == "substring"
    assert res.score == 0.87
    assert res.band == Band.HIGH
    assert res.uri == ROLE_URI


def test_exact_preferred_over_substring():
    # "Design Engineer Role" is an exact hit AND substring-contains "Engineer
    # Role"; exact tier must win and return the exact record.
    m = EntityMatcher()
    res = m.match("Design Engineer Role", "roles", corpus=_corpus())
    assert res.method == "exact"
    assert res.uri == DESIGN_ROLE_URI


# ---------------------------------------------------------------------------
# Category guard across tiers (a Role must NOT match a Principle target)
# ---------------------------------------------------------------------------

def test_category_guard_blocks_cross_category_exact():
    corpus = [CandidateRecord(uri=PRINCIPLE_URI, label="Public Safety", category="principles")]
    m = EntityMatcher()
    # Role candidate with the same label as a Principle target -> no match.
    res = m.match("public safety", "roles", corpus=corpus)
    assert res is None


def test_category_guard_blocks_cross_category_substring():
    corpus = [CandidateRecord(uri=PRINCIPLE_URI, label="Public Safety Principle", category="principles")]
    m = EntityMatcher()
    res = m.match("Public Safety", "roles", corpus=corpus)
    assert res is None


def test_category_guard_uses_injected_chain_resolver():
    # URI name says Obligation but chain says Principle; an Obligation candidate
    # with an exact label hit must still be rejected.
    uri = "http://proethica.org/ontology/intermediate#MisleadingObligation"
    corpus = [CandidateRecord(uri=uri, label="Loyalty", category="obligations")]
    m = EntityMatcher(chain_resolver=lambda t: "Principle")
    assert m.match("Loyalty", "obligations", corpus=corpus) is None


# ---------------------------------------------------------------------------
# Tier 3: embedding (fake injected search)
# ---------------------------------------------------------------------------

def test_embedding_match_high_band():
    def fake_search(label, definition, category):
        return [(ROLE_URI, "Engineer Role", 0.91)]

    m = EntityMatcher(embedding_search=fake_search)
    # No exact/substring hit (novel label), so it falls to embedding.
    res = m.match("Civil Practitioner", "roles", corpus=[])
    assert res is not None
    assert res.method == "embedding"
    assert res.score == pytest.approx(0.91)
    assert res.band == Band.HIGH
    assert res.uri == ROLE_URI


def test_embedding_match_medium_band():
    def fake_search(label, definition, category):
        return [(ROLE_URI, "Engineer Role", 0.74)]

    m = EntityMatcher(embedding_search=fake_search)
    res = m.match("Civil Practitioner", "roles", corpus=[])
    assert res is not None
    assert res.method == "embedding"
    assert res.band == Band.MEDIUM


def test_embedding_below_floor_returns_none():
    def fake_search(label, definition, category):
        return [(ROLE_URI, "Engineer Role", 0.69)]

    m = EntityMatcher(embedding_search=fake_search)
    assert m.match("Civil Practitioner", "roles", corpus=[]) is None


def test_embedding_category_guard_skips_incompatible_then_takes_next():
    # Best hit is a Principle URI (incompatible with a Role candidate); the
    # next, compatible, above-floor hit should be returned.
    def fake_search(label, definition, category):
        return [
            (PRINCIPLE_URI, "Public Safety", 0.95),  # incompatible -> skipped
            (ROLE_URI, "Engineer Role", 0.88),       # compatible -> taken
        ]

    m = EntityMatcher(embedding_search=fake_search)
    res = m.match("Civil Practitioner", "roles", corpus=[])
    assert res is not None
    assert res.uri == ROLE_URI
    assert res.method == "embedding"


def test_embedding_stops_at_first_below_floor():
    # Results are best-first; once below the floor the loop must stop, even if a
    # later (impossible, but defensive) entry is high.
    def fake_search(label, definition, category):
        return [(ROLE_URI, "Engineer Role", 0.5)]

    m = EntityMatcher(embedding_search=fake_search)
    assert m.match("Civil Practitioner", "roles", corpus=[]) is None


# ---------------------------------------------------------------------------
# Cascade ordering and total miss
# ---------------------------------------------------------------------------

def test_no_match_no_embedding_returns_none():
    m = EntityMatcher()  # no embedding tier injected
    assert m.match("Wholly Novel Concept", "roles", corpus=_corpus()) is None


def test_deterministic_tiers_preferred_over_embedding():
    # An exact corpus hit exists; embedding_search must not even be consulted.
    sentinel = {"called": False}

    def fake_search(label, definition, category):
        sentinel["called"] = True
        return [(PRINCIPLE_URI, "Public Safety", 0.99)]

    m = EntityMatcher(embedding_search=fake_search)
    res = m.match("Engineer Role", "roles", corpus=_corpus())
    assert res.method == "exact"
    assert sentinel["called"] is False
