"""Behavior-preserving equivalence tests for the matcher unification (2026-06).

Three scattered dedup mechanisms were routed through the consolidated
``app.services.extraction.entity_matcher``:

  1. ``auto_commit_service._check_duplicate`` / ``_check_embedding_duplicate``
  2. ``unified_dual_extractor._labels_match`` / ``_reject_cross_category_match``
  3. ``entity_reconciliation_service._normalize_label`` (auto-mode exact merge)

Each test reconstructs the ORIGINAL predicate inline and asserts the migrated
implementation returns the SAME result, OR documents a deliberately preserved
divergence (where faithful unification would have changed a corpus decision).

DB/LLM-free: bare instances via object.__new__, fake corpus, fake embedding
search. No Flask app context, no network.
"""

import re

import pytest

from app.services.extraction import entity_matcher
from app.services.extraction.entity_matcher import normalize_label


# ---------------------------------------------------------------------------
# Original-predicate reconstructions (verbatim from the pre-migration code)
# ---------------------------------------------------------------------------

_ORIG_PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')


def _orig_labels_match(label1: str, label2: str) -> bool:
    """unified_dual_extractor._labels_match, pre-migration body."""
    norm1 = label1.lower().replace('_', ' ').replace('-', ' ').strip()
    norm2 = label2.lower().replace('_', ' ').replace('-', ' ').strip()
    return norm1 == norm2


def _orig_reconcile_normalize(label: str) -> str:
    """entity_reconciliation_service._normalize_label, pre-migration body."""
    label = label.lower().strip()
    label = _ORIG_PAREN_SUFFIX_RE.sub('', label)
    return label.strip()


def _orig_category_ok(uri: str, type_markers) -> bool:
    """auto_commit_service._check_duplicate inline guard, pre-migration."""
    return not type_markers or any(m in uri for m in type_markers)


def _orig_reject_cross_category(candidate_cat, chain_cat):
    """_reject_cross_category_match core decision (pre-migration).

    Returns True == REJECT the match, False == keep. Mirrors:
      if not chain_cat: return  (keep)
      if chain_cat == candidate_cat: return  (keep)
      else reject.
    """
    if not chain_cat:
        return False
    if chain_cat == candidate_cat:
        return False
    return True


# ---------------------------------------------------------------------------
# 1. _labels_match  (unified_dual_extractor)
# ---------------------------------------------------------------------------

class TestLabelsMatchEquivalence:
    """The migrated _labels_match must equal the original on every input,
    INCLUDING the '_'/'-' fold and the deliberately-preserved paren behavior."""

    def _migrated(self, l1, l2):
        from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor
        ext = object.__new__(UnifiedDualExtractor)
        return ext._labels_match(l1, l2)

    @pytest.mark.parametrize("l1, l2", [
        ("Engineer Role", "engineer role"),                 # case
        ("Design_Engineer_Role", "design engineer role"),   # underscore fold
        ("Design-Engineer-Role", "design engineer role"),   # hyphen fold
        ("Design_Engineer-Role", "Design-Engineer_Role"),   # mixed separators
        ("Faithful Agent", "Faithful Agent"),               # identical
        ("Engineer Role", "Design Engineer Role"),          # non-match
        ("  Engineer Role  ", "engineer role"),             # whitespace strip
        # Paren-preserving divergence: original does NOT drop a trailing
        # parenthetical, so these must NOT match (had we routed through
        # normalize_label they WOULD, flipping a commit decision).
        ("Engineer Role (Present Case)", "Engineer Role"),
        ("Public Safety (NSPE)", "Public Safety"),
    ])
    def test_matches_original(self, l1, l2):
        assert self._migrated(l1, l2) == _orig_labels_match(l1, l2)

    def test_underscore_hyphen_still_match_after_preclean(self):
        # The flagged case: labels differing only by '_'/'-' must STILL match.
        assert self._migrated("Faithful_Agent-Role", "Faithful Agent Role") is True

    def test_trailing_parenthetical_preserved_not_dropped(self):
        # Explicit divergence guard: paren NOT dropped -> no false match.
        assert self._migrated("Engineer Role (Present Case)", "Engineer Role") is False
        # And the shared normalizer WOULD have dropped it (documents the reason
        # the call site is not routed through normalize_label).
        assert normalize_label("Engineer Role (Present Case)") == "engineer role"


# ---------------------------------------------------------------------------
# 2. _reject_cross_category_match  (unified_dual_extractor)
# ---------------------------------------------------------------------------

class TestRejectCrossCategoryEquivalence:
    """The migrated gate decision (reject vs keep) must equal the original for
    every (candidate_core_category, resolved_chain_category) pair."""

    def _migrated_rejects(self, candidate_cat, chain_cat, *, concept_type, matched_uri):
        """Run the real _reject_cross_category_match with a stubbed resolver and
        report whether it rejected the match."""
        from types import SimpleNamespace
        from app.services.extraction import category_resolver
        from app.services.extraction.unified_dual_extractor import UnifiedDualExtractor

        ext = object.__new__(UnifiedDualExtractor)
        ext.concept_type = concept_type
        ext.existing_classes = []

        md = SimpleNamespace(
            matches_existing=True, matched_uri=matched_uri,
            matched_label="X", confidence=0.9, reasoning="prior",
        )
        cand = SimpleNamespace(label="X", match_decision=md)

        orig = category_resolver.resolve_core_category
        category_resolver.resolve_core_category = lambda _ref: chain_cat
        try:
            ext._reject_cross_category_match(cand)
        finally:
            category_resolver.resolve_core_category = orig
        # Rejected iff matches_existing was flipped off.
        return md.matches_existing is False

    # (concept_type, candidate_core_category) pairs from CONCEPT_TYPE_TO_CORE_CATEGORY.
    @pytest.mark.parametrize("concept_type, candidate_cat", [
        ("obligations", "Obligation"),
        ("principles", "Principle"),
        ("roles", "Role"),
        ("capabilities", "Capability"),
        ("constraints", "Constraint"),
    ])
    @pytest.mark.parametrize("chain_cat", [
        "Obligation", "Principle", "Role", "Capability", "Constraint", None,
    ])
    def test_reject_decision_matches_original(self, concept_type, candidate_cat, chain_cat):
        uri = f"http://proethica.org/ontology/intermediate#Some{candidate_cat}"
        migrated = self._migrated_rejects(
            candidate_cat, chain_cat, concept_type=concept_type, matched_uri=uri,
        )
        original = _orig_reject_cross_category(candidate_cat, chain_cat)
        assert migrated == original, (concept_type, candidate_cat, chain_cat)

    def test_cross_category_is_rejected(self):
        # Obligation candidate, chain resolves to Principle -> REJECT.
        uri = "http://proethica.org/ontology/intermediate#SomeObligation"
        assert self._migrated_rejects(
            "Obligation", "Principle", concept_type="obligations", matched_uri=uri,
        ) is True

    def test_unresolved_chain_is_kept(self):
        # Chain unknown -> keep (cannot prove a conflict).
        uri = "http://proethica.org/ontology/intermediate#SomeObligation"
        assert self._migrated_rejects(
            "Obligation", None, concept_type="obligations", matched_uri=uri,
        ) is False


# ---------------------------------------------------------------------------
# 3. _normalize_label  (entity_reconciliation_service, auto-mode exact merge)
# ---------------------------------------------------------------------------

class TestReconcileNormalizeEquivalence:
    """The migrated _normalize_label must equal the original on every corpus-
    realistic input (no internal multi-whitespace exists in the corpus, so the
    shared normalizer's ws-collapse is a no-op and merge decisions are
    unchanged)."""

    def _migrated(self, label):
        from app.services.entity.entity_reconciliation_service import EntityReconciliationService
        svc = object.__new__(EntityReconciliationService)
        return svc._normalize_label(label)

    @pytest.mark.parametrize("label", [
        "Confidentiality Obligation",
        "  Public Safety  ",
        "Engineer Role (Present Case)",      # trailing parenthetical dropped (both)
        "Faithful Agent (NSPE) ",
        "ALL CAPS LABEL",
        "MixedCase Label",
        "Public Welfare Paramount",
    ])
    def test_normalize_matches_original(self, label):
        assert self._migrated(label) == _orig_reconcile_normalize(label)

    def test_auto_merge_exact_match_decision_unchanged(self):
        # Two labels that the original merged (identical normalized) still merge,
        # and a non-merge pair still does not.
        a, b = "Public Safety (Present Case)", "Public Safety"
        assert (self._migrated(a) == self._migrated(b)) == (
            _orig_reconcile_normalize(a) == _orig_reconcile_normalize(b)
        )
        c, d = "Engineer Role", "Design Engineer Role"
        assert (self._migrated(c) == self._migrated(d)) == (
            _orig_reconcile_normalize(c) == _orig_reconcile_normalize(d)
        )


# ---------------------------------------------------------------------------
# 4. _check_duplicate band/score return contract  (auto_commit_service)
# ---------------------------------------------------------------------------

class TestCheckDuplicateContract:
    """_check_duplicate's (uri, score) contract must be byte-identical to the
    pre-migration tiers: 1.0 exact, 0.87 substring, cosine for embedding, with
    the URI-marker category guard at every tier and the 0.70 floor."""

    OBL_URI = "http://proethica.org/ontology/intermediate#ConfidentialityObligation"
    ROLE_URI = "http://proethica.org/ontology/intermediate#FaithfulAgentRole"
    CAP_URI = "http://proethica.org/ontology/intermediate#CompetenceCapability"

    CACHE = {
        OBL_URI: {'label': 'Confidentiality Obligation', 'type': 'class', 'definition': ''},
        ROLE_URI: {'label': 'Faithful Agent Role', 'type': 'class', 'definition': ''},
        CAP_URI: {'label': 'Competence Capability', 'type': 'class', 'definition': ''},
    }

    def _service(self, *, embedding_row=None):
        """Bare AutoCommitService with a stubbed embedding tier (no DB/model)."""
        from app.services.commit.auto_commit_service import AutoCommitService
        svc = object.__new__(AutoCommitService)
        svc._versioned_commit = True
        svc._ontserve_classes_cache = dict(self.CACHE)

        def _fake_search(label, definition, entity_type):
            return [embedding_row] if embedding_row is not None else []

        svc._embedding_search = _fake_search
        return svc

    def _orig_check_duplicate(self, cache, label, entity_type, embedding_row):
        """Pre-migration _check_duplicate, reconstructed inline."""
        if not cache:
            return None
        normalized_label = label.lower().strip()
        type_markers = entity_matcher.semantic_type_markers(entity_type)

        for uri, info in cache.items():
            if info.get('label', '').lower().strip() == normalized_label:
                if _orig_category_ok(uri, type_markers):
                    return uri, 1.0
        for uri, info in cache.items():
            cl = info.get('label', '').lower().strip()
            if normalized_label in cl or cl in normalized_label:
                if type_markers and not any(m in uri for m in type_markers):
                    continue
                return uri, 0.87
        # embedding (single row), 0.70 floor.
        if embedding_row is None:
            return None
        uri, _lbl, cosine = embedding_row
        if cosine < 0.70:
            return None
        return uri, cosine

    # -- exact tier --

    def test_exact_returns_1_0(self):
        svc = self._service()
        assert svc._check_duplicate("Confidentiality Obligation", "obligation") == (self.OBL_URI, 1.0)
        assert svc._check_duplicate("Confidentiality Obligation", "obligation") == \
            self._orig_check_duplicate(self.CACHE, "Confidentiality Obligation", "obligation", None)

    def test_exact_case_insensitive(self):
        svc = self._service()
        assert svc._check_duplicate("FAITHFUL AGENT ROLE", "role") == (self.ROLE_URI, 1.0)

    # -- substring tier --

    def test_substring_returns_0_87(self):
        svc = self._service()
        res = svc._check_duplicate("Faithful", "role")
        assert res == (self.ROLE_URI, 0.87)
        assert res == self._orig_check_duplicate(self.CACHE, "Faithful", "role", None)

    # -- category guard at the substring tier --

    def test_substring_wrong_category_skipped(self):
        # "Competence" substring-matches the Capability class, but an obligation
        # candidate's marker rejects the Capability URI -> falls through to
        # embedding (none) -> None.
        svc = self._service(embedding_row=None)
        res = svc._check_duplicate("Competence", "obligation")
        assert res is None
        assert res == self._orig_check_duplicate(self.CACHE, "Competence", "obligation", None)

    # -- embedding tier bands --

    @pytest.mark.parametrize("cosine, expected_band", [
        (0.92, "HIGH"),
        (0.85, "HIGH"),
        (0.77, "MEDIUM"),
        (0.70, "MEDIUM"),
        (0.69, None),
        (0.50, None),
    ])
    def test_embedding_band_and_score_contract(self, cosine, expected_band):
        row = (self.OBL_URI, "Confidentiality Obligation", cosine)
        svc = self._service(embedding_row=row)
        res = svc._check_duplicate("Novel Duty Concept", "obligation")
        orig = self._orig_check_duplicate(self.CACHE, "Novel Duty Concept", "obligation", row)
        assert res == orig
        if expected_band is None:
            assert res is None
        else:
            uri, score = res
            assert uri == self.OBL_URI
            assert score == pytest.approx(cosine)
            assert entity_matcher.band_for(score).name == expected_band

    def test_embedding_below_floor_is_none(self):
        row = (self.OBL_URI, "Confidentiality Obligation", 0.60)
        svc = self._service(embedding_row=row)
        assert svc._check_duplicate("Novel Duty Concept", "obligation") is None

    def test_check_embedding_duplicate_contract_preserved(self):
        # The public-ish _check_embedding_duplicate keeps its (uri, cosine)|None
        # contract.
        row = (self.OBL_URI, "Confidentiality Obligation", 0.88)
        svc = self._service(embedding_row=row)
        assert svc._check_embedding_duplicate("X", "", "obligation") == (self.OBL_URI, 0.88)
        svc2 = self._service(embedding_row=(self.OBL_URI, "L", 0.60))
        assert svc2._check_embedding_duplicate("X", "", "obligation") is None
