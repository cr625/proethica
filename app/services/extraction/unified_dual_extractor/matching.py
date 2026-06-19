"""Ontology matching and individual-to-class linking for the unified dual extractor.

MatchingMixin: matches candidate classes to existing curated ontology classes
(_check_existing_matches, _labels_match), enforces the cross-category gate that
rejects a match crossing a disjoint core category (_candidate_core_category,
_reject_cross_category_match), collects definitions from matched entities
(_collect_ontology_definitions), and cascades match info from classes to their
individuals (_link_individuals_to_classes). Methods relocated verbatim from the
former unified_dual_extractor.py; UnifiedDualExtractor inherits this mixin so
self. resolution (sibling methods + self.existing_classes / self.concept_type /
self.config) is unchanged via MRO. The cross-category gate keeps its lazy import
of category_resolver.resolve_core_category, so the test monkeypatch on that
module still takes effect.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from app.services.extraction.unified_dual_extractor.config import (
    CONCEPT_TYPE_TO_CORE_CATEGORY,
)

logger = logging.getLogger(__name__)


class MatchingMixin:
    """Ontology matching + individual linking for UnifiedDualExtractor."""


    # ------------------------------------------------------------------
    # Ontology matching
    # ------------------------------------------------------------------

    def _check_existing_matches(self, classes: List[BaseModel]) -> None:
        """
        Check candidate classes against existing ontology classes.

        Updates the match_decision field on each candidate.

        For classes where the LLM already set matches_existing=True but
        provided a label (not a full URI) in matched_uri, resolves the
        proper URI from self.existing_classes.
        """
        if not self.existing_classes:
            return

        # Build label -> existing entity lookup for URI resolution
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for candidate in classes:
            if candidate.match_decision.matches_existing:
                # LLM already identified a match -- resolve URI if missing
                # or invalid (LLM only sees labels, not full URIs)
                uri = candidate.match_decision.matched_uri or ''
                if not uri.startswith('http'):
                    resolve_label = (
                        candidate.match_decision.matched_label
                        or candidate.match_decision.matched_uri
                        or ''
                    )
                    norm = resolve_label.lower().replace(
                        '_', ' '
                    ).replace('-', ' ').strip()
                    resolved = existing_by_label.get(norm)
                    if resolved:
                        candidate.match_decision.matched_uri = resolved.get('uri')
                        candidate.match_decision.matched_label = (
                            resolved.get('label')
                        )
                        logger.debug(
                            f"Resolved URI for LLM-matched class "
                            f"'{candidate.label}': {resolved.get('uri')}"
                        )
                continue

            for existing in self.existing_classes:
                existing_label = existing.get('label', '')
                if self._labels_match(candidate.label, existing_label):
                    candidate.match_decision.matches_existing = True
                    candidate.match_decision.matched_uri = existing.get('uri')
                    candidate.match_decision.matched_label = existing_label
                    candidate.match_decision.confidence = 0.9
                    candidate.match_decision.reasoning = (
                        'Label match with existing ontology class'
                    )
                    break

        # Cleanup: zero out ALL orphaned match data where no URI was resolved.
        # The LLM sometimes matches against sibling extractions (from prior
        # sections) rather than the ontology list.  Those siblings have no
        # OntServe URI, so the match is invalid.  Clear everything so the DB
        # columns stay strictly "matched to an OntServe ontology entity."
        for candidate in classes:
            if not candidate.match_decision.matched_uri:
                candidate.match_decision.confidence = 0.0
                candidate.match_decision.matches_existing = False
                candidate.match_decision.matched_label = None
                candidate.match_decision.reasoning = None

        # Cross-category gate (Layer 1). Both branches above can establish a
        # match the LLM or a label match proposed; deterministically reject any
        # match whose matched class chains (via the curated subClassOf* chain) to
        # a core category disjoint from this candidate's category. This stops a
        # genuine Obligation being merged into a class an earlier extraction
        # mis-established as a Principle, which otherwise forces a Pellet
        # disjointness clash. Runs LAST so its rejection reasoning survives the
        # orphan-cleanup pass above. See
        # docs-internal/reextraction/matcher-category-authority-design.md.
        for candidate in classes:
            self._reject_cross_category_match(candidate)

    def _candidate_core_category(self) -> Optional[str]:
        """The core category a candidate of this extractor's concept_type is."""
        return CONCEPT_TYPE_TO_CORE_CATEGORY.get(self.concept_type)

    def _reject_cross_category_match(self, candidate: BaseModel) -> None:
        """Reject a prefer-existing match that crosses a disjoint core category.

        Resolves the matched class's curated subClassOf* CHAIN core category
        (anchored in proethica-core+intermediate[-extended], NOT the stored
        OntServe entity-table category or conceptCategory literal, which are
        extraction-derived and can lie) and compares it to the candidate's core
        category. Two distinct core categories are mutually disjoint under the
        nine-way AllDisjointClasses, so the match would force an OWL-DL clash;
        drop it and let the candidate be treated as a new class. A same-category
        match, or a match whose chain category cannot be resolved, is left
        unchanged.
        """
        md = candidate.match_decision
        if not md.matches_existing:
            return

        matched_ref = md.matched_uri or md.matched_label
        if not matched_ref:
            return

        candidate_cat = self._candidate_core_category()
        if not candidate_cat:
            return

        from app.services.extraction.category_resolver import resolve_core_category
        from app.services.extraction.entity_matcher import category_compatible
        chain_cat = resolve_core_category(matched_ref)
        if not chain_cat:
            # Chain category unknown (class not in the curated tiers); cannot
            # prove a conflict, so leave the match in place.
            return

        # Compatibility decided by the shared guard. The control flow above
        # already mirrors category_compatible's chain path (early-return-keep on
        # an unresolved chain), so feed it the already-resolved chain category
        # via a constant resolver: it then compares chain_cat against this
        # concept_type's marker, which for the nine D-tuple types is exactly the
        # old ``chain_cat == candidate_cat`` test (CONCEPT_TYPE_TO_CORE_CATEGORY
        # values are the marker tokens). Behavior-preserving; normalization +
        # comparison now live in entity_matcher.
        if category_compatible(
            self.concept_type, matched_ref, chain_resolver=lambda _ref: chain_cat,
        ):
            return

        logger.warning(
            "Matcher rejected cross-category match for '%s': existing class %s "
            "chains to %s but candidate is %s",
            getattr(candidate, 'label', None) or getattr(candidate, 'identifier', '?'),
            matched_ref, chain_cat, candidate_cat,
        )
        md.matches_existing = False
        md.matched_uri = None
        md.matched_label = None
        md.confidence = 0.0
        md.reasoning = (
            f"rejected cross-category match: existing class chains to "
            f"{chain_cat} but candidate is {candidate_cat}"
        )

    def _collect_ontology_definitions(
        self, classes: List[BaseModel],
    ) -> Dict[str, Dict[str, str]]:
        """Collect definitions from matched ontology entities.

        For each candidate class that matched an existing ontology class,
        look up the ontology entity's comment (rdfs:comment) and return it
        keyed by label.

        Returns:
            Dict mapping label -> {text, source_uri, source_ontology}
        """
        result = {}
        if not self.existing_classes:
            return result

        # Build lookup: URI -> existing entity dict
        existing_by_uri = {}
        existing_by_label = {}
        for ent in self.existing_classes:
            uri = ent.get('uri', '')
            label = ent.get('label', '')
            if uri:
                existing_by_uri[uri] = ent
            if label:
                norm = label.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = ent

        for candidate in classes:
            md = candidate.match_decision
            if not md.matches_existing:
                continue

            # Find the ontology entity via matched_uri or matched_label
            ont_entity = None
            if md.matched_uri:
                ont_entity = existing_by_uri.get(md.matched_uri)
            if not ont_entity and md.matched_label:
                norm = md.matched_label.lower().replace('_', ' ').replace('-', ' ').strip()
                ont_entity = existing_by_label.get(norm)

            ont_def = (
                ont_entity.get('description')
                or ont_entity.get('comment', '')
            ) if ont_entity else ''
            if ont_def:
                result[candidate.label] = {
                    'text': ont_def,
                    'source_uri': ont_entity.get('uri', ''),
                    'source_ontology': (
                        ont_entity.get('ontology_name')
                        or ont_entity.get('source')
                        or (ont_entity.get('metadata', {}) or {}).get('ontology', '')
                    ),
                }

        return result

    def _labels_match(self, label1: str, label2: str) -> bool:
        """Case-insensitive exact label matching with normalization.

        Only matches when labels are identical after normalization.
        Substring containment is intentionally excluded -- the LLM
        already sees the full existing class list and makes deliberate
        match decisions.  Overriding with substring matching collapses
        legitimate specializations (e.g. 'Design Engineer Role' would
        falsely match 'Engineer Role').

        BEHAVIOR-PRESERVING NOTE (matcher unification 2026-06): faithful
        unification through the shared ``entity_matcher.normalize_label`` is NOT
        possible here without changing commit decisions, so the old inline
        normalization is intentionally retained.  Two divergences:
          1. This site folds '_' and '-' to spaces; ``normalize_label`` does not.
          2. ``normalize_label`` ALSO drops a trailing parenthetical and
             collapses internal whitespace; this site does NOT.
        681 candidate labels in the corpus carry a trailing '(...)' while no
        existing OntServe class label does, so routing the candidate side
        through ``normalize_label`` would drop that suffix and let
        "Foo Role (Present Case)" newly exact-match an existing "Foo Role",
        flipping a commit decision.  The separator fold IS shared with the
        ``_reject_cross_category_match`` pre-clean below.  Decision preserved;
        do not re-route through ``normalize_label``.  See the equivalence test
        ``test_labels_match_*`` in tests/extraction/test_matcher_unification.py.
        """
        norm1 = label1.lower().replace('_', ' ').replace('-', ' ').strip()
        norm2 = label2.lower().replace('_', ' ').replace('-', ' ').strip()
        return norm1 == norm2

    # ------------------------------------------------------------------
    # Individual-to-class linking
    # ------------------------------------------------------------------

    def _link_individuals_to_classes(
        self,
        individuals: List[BaseModel],
        classes: List[BaseModel],
    ) -> None:
        """
        Propagate ontology match info from classes to their individuals.

        When an individual's class reference (e.g. role_class) points to a
        newly extracted class that matched an existing ontology class, the
        individual inherits that match decision. When the reference points
        directly to an existing ontology class label, the individual gets
        a match decision linking it there.
        """
        class_ref_field = self.config['class_ref_field']

        # Build lookup: normalized label -> candidate class
        candidate_by_label = {}
        for c in classes:
            norm = c.label.lower().replace('_', ' ').replace('-', ' ').strip()
            candidate_by_label[norm] = c

        # Build lookup: normalized label -> existing ontology class dict
        existing_by_label = {}
        for existing in self.existing_classes:
            lbl = existing.get('label', '')
            if lbl:
                norm = lbl.lower().replace('_', ' ').replace('-', ' ').strip()
                existing_by_label[norm] = existing

        for individual in individuals:
            ref_value = getattr(individual, class_ref_field, None)
            if not ref_value:
                continue

            ref_norm = ref_value.lower().replace('_', ' ').replace('-', ' ').strip()

            # Case 1: individual references a new candidate class
            matched_candidate = candidate_by_label.get(ref_norm)
            if matched_candidate:
                md = matched_candidate.match_decision
                if md.matches_existing:
                    # Cascade: class matched existing -> individual inherits
                    individual.match_decision.matches_existing = True
                    individual.match_decision.matched_uri = md.matched_uri
                    individual.match_decision.matched_label = md.matched_label
                    individual.match_decision.confidence = md.confidence
                    individual.match_decision.reasoning = (
                        f"Via class '{matched_candidate.label}': "
                        f"{md.reasoning or ''}"
                    )
                    logger.debug(
                        f"Individual '{individual.identifier}' linked to "
                        f"existing '{md.matched_label}' via class "
                        f"'{matched_candidate.label}'"
                    )
                continue

            # Case 2: individual references an existing ontology class directly
            matched_existing = existing_by_label.get(ref_norm)
            if matched_existing:
                individual.match_decision.matches_existing = True
                individual.match_decision.matched_uri = matched_existing.get('uri')
                individual.match_decision.matched_label = matched_existing.get('label')
                individual.match_decision.confidence = 0.95
                individual.match_decision.reasoning = (
                    f"Individual typed as existing ontology class "
                    f"'{matched_existing.get('label')}'"
                )
                logger.debug(
                    f"Individual '{individual.identifier}' directly references "
                    f"existing class '{matched_existing.get('label')}'"
                )
                # Apply the same chain-category gate as _check_existing_matches:
                # existing_by_label is keyed off get_entities_by_category (the
                # STORED category), which can disagree with the curated subClassOf
                # CHAIN (the F2 root cause), so a direct individual->existing-class
                # link can still cross a disjoint category. Reject if so.
                self._reject_cross_category_match(individual)
