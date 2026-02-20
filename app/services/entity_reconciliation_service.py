"""
Entity Reconciliation Service

Fuzzy-match entities extracted across all extraction passes (Steps 1-3)
to detect near-duplicates not caught by the exact-label merge at storage time.
Uses difflib.SequenceMatcher for label similarity.

Thresholds:
- Auto-merge: ratio >= 0.85 AND same extraction_type (concept type)
- Human review: ratio 0.65-0.85, OR >= 0.85 with different concept type
- Keep separate: ratio < 0.65

Two modes:
- reconcile_auto(): batch processing -- auto-merge only, no review candidates
- reconcile_with_review(): interactive -- auto-merge high-confidence, return review list
"""

import logging
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from app.models import db
from app.models.temporary_rdf_storage import TemporaryRDFStorage
from app.services.entity_merge_service import EntityMergeService

logger = logging.getLogger(__name__)

AUTO_MERGE_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.65

# Pattern to strip trailing parenthetical qualifiers like "(Present Case)"
PAREN_SUFFIX_RE = re.compile(r'\s*\([^)]*\)\s*$')


@dataclass
class ReconciliationCandidate:
    """A pair of entities that may be duplicates."""
    entity_a_id: int
    entity_b_id: int
    entity_a_label: str
    entity_b_label: str
    similarity: float
    same_concept_type: bool
    recommendation: str  # 'auto_merge', 'review', 'keep_separate'


@dataclass
class ReconciliationResult:
    """Result of reconciliation for a case."""
    case_id: int
    auto_merged: int = 0
    review_candidates: List[ReconciliationCandidate] = field(default_factory=list)
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class EntityReconciliationService:
    """Fuzzy-match and merge near-duplicate entities for a case."""

    def __init__(self):
        self._merge_service = EntityMergeService()

    def find_candidates(self, case_id: int) -> List[ReconciliationCandidate]:
        """Find all reconciliation candidates for a case.

        Compares every pair of unpublished entities within same storage_type.
        O(n^2) but n is typically < 100 entities per case.
        """
        entities = TemporaryRDFStorage.query.filter(
            TemporaryRDFStorage.case_id == case_id,
            TemporaryRDFStorage.is_published == False  # noqa: E712
        ).all()

        if len(entities) < 2:
            return []

        # Group by storage_type (class vs individual) -- only compare within groups
        groups: Dict[str, List[TemporaryRDFStorage]] = {}
        for e in entities:
            stype = e.storage_type or 'unknown'
            if stype not in groups:
                groups[stype] = []
            groups[stype].append(e)

        candidates = []
        for group_entities in groups.values():
            candidates.extend(self._find_candidates_in_group(group_entities))

        # Sort by similarity descending (highest confidence first)
        candidates.sort(key=lambda c: c.similarity, reverse=True)
        return candidates

    def _find_candidates_in_group(
        self, entities: List[TemporaryRDFStorage]
    ) -> List[ReconciliationCandidate]:
        """Find near-match pairs within a group of entities."""
        candidates = []
        n = len(entities)

        for i in range(n):
            for j in range(i + 1, n):
                a = entities[i]
                b = entities[j]

                # Skip if same entity
                if a.id == b.id:
                    continue

                # Skip exact label match (already handled by storage-time merge)
                if (a.entity_label or '').lower().strip() == (b.entity_label or '').lower().strip():
                    continue

                similarity = self._compute_similarity(
                    a.entity_label or '', b.entity_label or ''
                )

                if similarity < REVIEW_THRESHOLD:
                    continue

                same_type = self._same_concept_type(a, b)
                recommendation = self._classify(similarity, same_type)

                candidates.append(ReconciliationCandidate(
                    entity_a_id=a.id,
                    entity_b_id=b.id,
                    entity_a_label=a.entity_label or '',
                    entity_b_label=b.entity_label or '',
                    similarity=round(similarity, 3),
                    same_concept_type=same_type,
                    recommendation=recommendation,
                ))

        return candidates

    def reconcile_auto(self, case_id: int) -> ReconciliationResult:
        """Auto-merge high-confidence duplicates only. Used by batch pipeline.

        Only merges candidates with recommendation='auto_merge'.
        Skips review-level candidates.
        """
        result = ReconciliationResult(case_id=case_id)
        candidates = self.find_candidates(case_id)

        if not candidates:
            return result

        merged_ids = set()

        for candidate in candidates:
            if candidate.recommendation != 'auto_merge':
                result.skipped += 1
                continue

            # Skip if either entity was already merged in this pass
            if candidate.entity_a_id in merged_ids or candidate.entity_b_id in merged_ids:
                result.skipped += 1
                continue

            try:
                keep_id, merge_id = self._pick_keep_merge(
                    candidate.entity_a_id, candidate.entity_b_id
                )
                success = self.merge_entities(keep_id, merge_id)
                if success:
                    result.auto_merged += 1
                    merged_ids.add(merge_id)
                    logger.info(
                        f"Auto-merged entity {merge_id} into {keep_id} "
                        f"(similarity={candidate.similarity})"
                    )
                else:
                    result.errors.append(
                        f"Failed to merge {candidate.entity_b_label} into {candidate.entity_a_label}"
                    )
            except Exception as e:
                result.errors.append(str(e))
                logger.error(f"Error merging entities: {e}", exc_info=True)

        return result

    def reconcile_with_review(self, case_id: int) -> ReconciliationResult:
        """Auto-merge high-confidence, return review list for medium-confidence.

        Used by interactive pipeline.
        """
        result = ReconciliationResult(case_id=case_id)
        candidates = self.find_candidates(case_id)

        if not candidates:
            return result

        merged_ids = set()

        for candidate in candidates:
            # Skip if either entity was already merged
            if candidate.entity_a_id in merged_ids or candidate.entity_b_id in merged_ids:
                continue

            if candidate.recommendation == 'auto_merge':
                try:
                    keep_id, merge_id = self._pick_keep_merge(
                        candidate.entity_a_id, candidate.entity_b_id
                    )
                    success = self.merge_entities(keep_id, merge_id)
                    if success:
                        result.auto_merged += 1
                        merged_ids.add(merge_id)
                    else:
                        result.errors.append(
                            f"Failed to merge {candidate.entity_b_label} into {candidate.entity_a_label}"
                        )
                except Exception as e:
                    result.errors.append(str(e))
                    logger.error(f"Error merging entities: {e}", exc_info=True)

            elif candidate.recommendation == 'review':
                result.review_candidates.append(candidate)

            else:
                result.skipped += 1

        return result

    def merge_entities(self, keep_id: int, merge_id: int) -> bool:
        """Merge entity merge_id into keep_id, then delete merge_id.

        Delegates property merging to EntityMergeService.merge_entity_properties().
        """
        keep_entity = TemporaryRDFStorage.query.get(keep_id)
        merge_entity = TemporaryRDFStorage.query.get(merge_id)

        if not keep_entity or not merge_entity:
            logger.error(f"Entity not found: keep={keep_id}, merge={merge_id}")
            return False

        if keep_entity.is_published or merge_entity.is_published:
            logger.error("Cannot merge published entities")
            return False

        try:
            # Delegate to EntityMergeService for property merging
            self._merge_service.merge_entity_properties(
                keep_entity,
                merge_entity.rdf_json_ld or {},
                merge_entity.extraction_session_id
            )

            # If the merge_entity had a shorter/cleaner label, adopt it
            keep_label = keep_entity.entity_label or ''
            merge_label = merge_entity.entity_label or ''
            preferred = self._pick_preferred_label(keep_label, merge_label)
            if preferred != keep_label:
                keep_entity.entity_label = preferred
                # Update label in rdf_json_ld too
                if keep_entity.rdf_json_ld:
                    keep_entity.rdf_json_ld['label'] = preferred

            # Delete the merged-away entity
            db.session.delete(merge_entity)
            db.session.commit()

            logger.info(
                f"Merged entity '{merge_label}' (id={merge_id}) "
                f"into '{keep_entity.entity_label}' (id={keep_id})"
            )
            return True

        except Exception as e:
            db.session.rollback()
            logger.error(f"Merge failed: {e}", exc_info=True)
            return False

    # -- Internal helpers --

    def _compute_similarity(self, label_a: str, label_b: str) -> float:
        """SequenceMatcher ratio on normalized labels.

        Normalization: lowercase, strip whitespace, remove trailing parentheticals.
        """
        norm_a = self._normalize_label(label_a)
        norm_b = self._normalize_label(label_b)
        return SequenceMatcher(None, norm_a, norm_b).ratio()

    def _normalize_label(self, label: str) -> str:
        """Normalize a label for comparison."""
        label = label.lower().strip()
        label = PAREN_SUFFIX_RE.sub('', label)
        return label.strip()

    def _same_concept_type(
        self, a: TemporaryRDFStorage, b: TemporaryRDFStorage
    ) -> bool:
        """Check if two entities belong to the same concept type."""
        type_a = (a.extraction_type or '').lower()
        type_b = (b.extraction_type or '').lower()
        return type_a == type_b and type_a != ''

    def _classify(self, similarity: float, same_type: bool) -> str:
        """Classify a candidate pair into auto_merge / review / keep_separate."""
        if similarity >= AUTO_MERGE_THRESHOLD and same_type:
            return 'auto_merge'
        if similarity >= REVIEW_THRESHOLD:
            return 'review'
        return 'keep_separate'

    def _pick_keep_merge(self, id_a: int, id_b: int) -> tuple:
        """Decide which entity to keep and which to merge away.

        Keeps the entity with the shorter/cleaner label.
        """
        a = TemporaryRDFStorage.query.get(id_a)
        b = TemporaryRDFStorage.query.get(id_b)
        label_a = a.entity_label or '' if a else ''
        label_b = b.entity_label or '' if b else ''

        preferred = self._pick_preferred_label(label_a, label_b)
        if preferred == label_b:
            return id_b, id_a
        return id_a, id_b

    def _pick_preferred_label(self, label_a: str, label_b: str) -> str:
        """Pick the preferred label -- shorter and without parenthetical suffixes."""
        a_has_paren = bool(PAREN_SUFFIX_RE.search(label_a))
        b_has_paren = bool(PAREN_SUFFIX_RE.search(label_b))

        # Prefer label without parenthetical suffix
        if a_has_paren and not b_has_paren:
            return label_b
        if b_has_paren and not a_has_paren:
            return label_a

        # Both have or neither have parens -- prefer shorter
        if len(label_a) <= len(label_b):
            return label_a
        return label_b
