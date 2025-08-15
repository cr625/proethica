"""
Guideline Triple Cleanup Service

Provides utilities to clean up guideline-sourced triples in the database:

- Delete guideline-specific triples that are NOT part of the core ontologies
  (engineering-ethics, proethica-intermediate, etc.).
- For triples that DO exist in core ontologies but still carry a guideline_id
  reference to a guideline that no longer exists, nullify the reference so they
  are not attributed to a deleted guideline.

Intended usage via an admin route.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Optional, Set

from sqlalchemy import and_  # noqa: F401

from app import db
from app.models.entity_triple import EntityTriple
from app.models.guideline import Guideline
from app.services.triple_duplicate_detection_service import (
    get_duplicate_detection_service,
)

logger = logging.getLogger(__name__)


class GuidelineTripleCleanupService:
    """Encapsulates cleanup logic for guideline concept triples."""

    def __init__(self) -> None:
        self.dup_service = get_duplicate_detection_service()

    def _in_core_ontology(self, t: EntityTriple) -> bool:
        obj = t.object_uri if not t.is_literal else t.object_literal
        try:
            return self.dup_service.check_triple_exists_in_ontology(
                t.subject, t.predicate, obj, t.is_literal
            )
        except Exception as e:
            logger.debug(f"Ontology check failed for triple {t.id}: {e}")
            return False

    def cleanup(
        self,
        *,
        world_id: Optional[int] = None,
        exclude_guideline_ids: Optional[Iterable[int]] = None,
        delete_non_core: bool = True,
        nullify_core_if_orphan_guideline: bool = True,
        dry_run: bool = True,
    ) -> Dict:
        """Perform cleanup and return a summary.

        Args:
            world_id: Restrict to a world if provided.
            exclude_guideline_ids: Guideline IDs to keep intact (won't delete).
            delete_non_core: Delete triples not present in core ontologies.
            nullify_core_if_orphan_guideline: If triple exists in core ontology but
                guideline_id points to a non-existent guideline, set guideline_id to NULL
                and strip any 'guideline_id' entry in triple_metadata.
            dry_run: When True, no changes are committed.

        Returns:
            Dict summary with counts and sample IDs.
        """
        exclude_set: Set[int] = set(exclude_guideline_ids or [])

        # Base query: guideline concept triples only
        q = EntityTriple.query.filter(EntityTriple.entity_type == 'guideline_concept')
        if world_id is not None:
            q = q.filter(EntityTriple.world_id == world_id)

        triples: List[EntityTriple] = q.all()

        to_delete: List[int] = []
        to_nullify: List[int] = []

        # Cache existing guideline IDs to avoid N+1
        existing_guideline_ids = {gid for (gid,) in db.session.query(Guideline.id).all()}

        for t in triples:
            # Skip protected guideline IDs
            if t.guideline_id and t.guideline_id in exclude_set:
                continue

            in_core = self._in_core_ontology(t)
            guideline_exists = (
                t.guideline_id in existing_guideline_ids if t.guideline_id is not None else True
            )
            orphan = (t.guideline_id is not None and not guideline_exists)

            if not in_core:
                # Non-core guideline triple — candidate for deletion
                if delete_non_core:
                    to_delete.append(t.id)
            else:
                # In core ontology; ensure we don't carry references to deleted guidelines
                if orphan and nullify_core_if_orphan_guideline:
                    to_nullify.append(t.id)

        summary = {
            'scoped_world_id': world_id,
            'input_exclude_guideline_ids': sorted(list(exclude_set)),
            'evaluated_triples': len(triples),
            'delete_non_core': delete_non_core,
            'nullify_core_if_orphan_guideline': nullify_core_if_orphan_guideline,
            'to_delete_count': len(to_delete),
            'to_nullify_count': len(to_nullify),
            'delete_ids_sample': to_delete[:20],
            'nullify_ids_sample': to_nullify[:20],
            'dry_run': dry_run,
        }

        if dry_run:
            return summary

        # Execute mutations in chunks for safety
        try:
            if to_nullify:
                # Nullify guideline references and scrub metadata
                chunk = 1000
                for i in range(0, len(to_nullify), chunk):
                    ids = to_nullify[i:i + chunk]
                    # Update in a single statement
                    db.session.query(EntityTriple).filter(EntityTriple.id.in_(ids)).update(
                        {EntityTriple.guideline_id: None}, synchronize_session=False
                    )
                    # For metadata, fetch and scrub in manageable batches
                    for t in db.session.query(EntityTriple).filter(EntityTriple.id.in_(ids)).all():
                        try:
                            meta = t.triple_metadata or {}
                            if 'guideline_id' in meta:
                                meta.pop('guideline_id', None)
                                t.triple_metadata = meta
                        except Exception:
                            pass

            if to_delete:
                chunk = 1000
                for i in range(0, len(to_delete), chunk):
                    ids = to_delete[i:i + chunk]
                    db.session.query(EntityTriple).filter(EntityTriple.id.in_(ids)).delete(
                        synchronize_session=False
                    )

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.exception("Failed to apply guideline triple cleanup changes")
            summary['error'] = str(e)
            return summary

        return summary


def get_guideline_triple_cleanup_service() -> GuidelineTripleCleanupService:
    return GuidelineTripleCleanupService()
